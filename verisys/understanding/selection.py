"""Deterministic, bounded excerpt selection for the opt-in understanding layer.

Only discovered files are read, through the same safe readers as analysis. The
server, not the model, chooses what is sent: README and docs first, then manifests
(package.json, pyproject.toml, Dockerfile, compose files, requirements.txt), then source
around detected routes, integrations and entry points, then test names. Likely
secrets are redacted before any text leaves this module.
"""
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from verisys.models import ArchitectureIR, SourceLocation
from verisys.repository.discovery import MANIFEST_NAMES, DiscoveryResult
from verisys.repository.safe_read import UnsafeSourceError, read_document, read_python_source
from .contracts import ExcerptKind, ExcerptLine, SourceExcerpt


@dataclass(frozen=True)
class SelectionLimits:
    max_total_lines: int = 1500
    max_total_bytes: int = 96 * 1024
    max_excerpt_lines: int = 200
    max_line_chars: int = 400
    max_documents: int = 6
    max_manifests: int = 6
    manifest_lines: int = 60
    max_test_files: int = 20
    max_summary_items: int = 50


ENTRY_POINT_NAMES = {"main.py", "app.py", "__main__.py", "cli.py", "manage.py", "wsgi.py", "asgi.py", "server.py"}
DOC_DIRECTORIES = {"docs", "doc", "documentation"}
SKIPPED_ROOT_DOCS = {"CHANGELOG", "CHANGES", "HISTORY", "LICENSE", "LICENCE", "CODE_OF_CONDUCT", "NOTICE", "AUTHORS"}
TEST_LINE = re.compile(r"^\s*(?:async\s+def|def)\s+test\w*|^\s*class\s+Test\w*")
REDACTED = "[REDACTED]"
SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_-]{16,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),
    re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._~+/-]{20,}=*"),
    re.compile(r"""(?ix)\b(api[_-]?key|secret[_-]?key|secret|password|passwd|token|access[_-]?key|client[_-]?secret)
                   (["']?\s*[:=]\s*)(["'])[^"'\s]{8,}(["'])"""),
)
PRIVATE_KEY = re.compile(r"-----(BEGIN|END) [A-Z ]*PRIVATE KEY-----")


@dataclass
class _Budget:
    lines: int
    bytes: int
    truncated: bool = False


def _redact(lines: list[str]) -> tuple[list[str], int]:
    redacted, count, in_key = [], 0, False
    for text in lines:
        marker = PRIVATE_KEY.search(text)
        if marker or in_key:
            in_key = (marker.group(1) == "BEGIN") if marker else in_key
            redacted.append(REDACTED)
            count += 1
            continue
        for pattern in SECRET_PATTERNS:
            if pattern.groups == 4:
                text, hits = pattern.subn(lambda m: f"{m.group(1)}{m.group(2)}{m.group(3)}{REDACTED}{m.group(4)}", text)
            elif pattern.groups == 1:
                text, hits = pattern.subn(lambda m: m.group(1) + REDACTED, text)
            else:
                text, hits = pattern.subn(REDACTED, text)
            count += hits
        redacted.append(text)
    return redacted, count


def _windows(locations: list[SourceLocation], before: int, after: int, total: int) -> list[int]:
    numbers = set()
    for location in locations:
        numbers.update(range(max(1, location.line - before), min(total, location.line + after) + 1))
    return sorted(numbers)


def _is_test(path: Path) -> bool:
    return (path.name.startswith("test_") or path.name.endswith("_test.py")
            or any(part in {"tests", "test"} for part in path.parts[:-1]))


def _document_rank(path: Path) -> tuple | None:
    if path.parent == Path(".") and path.name.upper().startswith("README"):
        return (0, path.suffix != ".md", path.as_posix())
    if path.suffix not in {".md", ".rst"}:
        return None
    if path.parent == Path("."):
        return None if path.stem.upper() in SKIPPED_ROOT_DOCS else (1, False, path.as_posix())
    if path.parts[0].lower() in DOC_DIRECTORIES:
        return (2, len(path.parts), path.as_posix())
    return None


def architecture_summary(architecture: ArchitectureIR, limits: SelectionLimits = SelectionLimits()) -> dict[str, list[str]]:
    """Compact, server-written facts; repository-derived strings stay bounded."""
    def at(location):
        return f"{location.file}:{location.line}"
    summary = {
        "languages": list(architecture.languages),
        "frameworks": list(architecture.frameworks),
        "routes": [f"{route.method} {route.path} -> {route.handler} ({at(route.source_location)})"
                   for route in architecture.api_routes],
        "external_services": [f"{service.name} ({service.client_library}): {len(service.call_sites)} supported call sites"
                              for service in architecture.external_services],
        "datastores": [f"{store.name} ({store.engine})" for store in architecture.datastores],
        "tools": [f"{tool.name} ({at(tool.source_location)})" for tool in architecture.tools],
        "execution_flows": [flow.name for flow in architecture.execution_flows],
    }
    return {key: [text[:200] for text in values[:limits.max_summary_items]] for key, values in summary.items()}


def select_excerpts(discovery: DiscoveryResult, architecture: ArchitectureIR,
                    limits: SelectionLimits = SelectionLimits()) -> tuple[list[SourceExcerpt], bool, list[str]]:
    """Return (excerpts, input_truncated, limitations) in a stable priority order."""
    root = discovery.repository_root
    python_files = set(discovery.files)
    budget = _Budget(limits.max_total_lines, limits.max_total_bytes)
    excerpts: list[SourceExcerpt] = []
    limitations: list[str] = []
    redactions = 0
    cache: dict[Path, list[str] | None] = {}

    def read(path: Path, document: bool) -> list[str] | None:
        if path not in cache:
            try:
                reader = read_document if document else read_python_source
                data = reader(root, path, max_file_bytes=discovery.limits.max_file_bytes)
                cache[path] = data.decode("utf-8", errors="replace").splitlines()
            except UnsafeSourceError as error:
                limitations.append(f"{path.as_posix()}: not read for understanding ({error.reason.value}).")
                cache[path] = None
        return cache[path]

    def add(path: Path, kind: ExcerptKind, numbers: list[int] | None, document: bool = False) -> None:
        nonlocal redactions
        lines = read(path, document)
        if not lines:
            return
        numbers = numbers if numbers is not None else list(range(1, len(lines) + 1))
        numbers = [number for number in numbers if 1 <= number <= len(lines)]
        truncated = len(numbers) > limits.max_excerpt_lines
        numbers = numbers[:limits.max_excerpt_lines]
        texts, hits = _redact([lines[number - 1][:limits.max_line_chars] for number in numbers])
        kept = []
        for number, text in zip(numbers, texts):
            size = len(text.encode()) + 8
            if budget.lines < 1 or budget.bytes < size:
                truncated = budget.truncated = True
                break
            budget.lines -= 1
            budget.bytes -= size
            kept.append(ExcerptLine(number=number, text=text))
        if not kept:
            return
        redactions += hits
        excerpts.append(SourceExcerpt(id=f"E{len(excerpts) + 1}", path=PurePosixPath(path).as_posix(),
                                      kind=kind, lines=tuple(kept), truncated=truncated))

    ranked = sorted((rank, path) for path in discovery.documents if (rank := _document_rank(path)) is not None)
    readmes = [path for rank, path in ranked if rank[0] == 0][:1]
    others = [path for rank, path in ranked if rank[0] != 0][:max(0, limits.max_documents - len(readmes))]
    for path in readmes:
        add(path, ExcerptKind.README, None, document=True)
    for path in others:
        add(path, ExcerptKind.DOCUMENT, None, document=True)
    manifests = sorted((path for path in discovery.documents if path.name in MANIFEST_NAMES or path.name == "requirements.txt"),
                       key=lambda path: (len(path.parts), path.as_posix()))
    for path in manifests[:limits.max_manifests]:
        add(path, ExcerptKind.MANIFEST, list(range(1, limits.manifest_lines + 1)), document=True)

    def grouped(locations):
        by_file: dict[Path, list[SourceLocation]] = {}
        for location in locations:
            path = Path(location.file)
            if path in python_files:
                by_file.setdefault(path, []).append(location)
        return sorted(by_file.items(), key=lambda item: item[0].as_posix())

    selected: set[Path] = set()
    for path, locations in grouped(route.source_location for route in architecture.api_routes):
        lines = read(path, False) or []
        add(path, ExcerptKind.ROUTE_SOURCE, _windows(locations, 3, 40, len(lines)))
        selected.add(path)
    integration = [location for service in architecture.external_services
                   for location in [*service.source_locations, *service.call_sites]]
    integration += [location for store in architecture.datastores for location in store.source_locations]
    integration += [tool.source_location for tool in architecture.tools]
    for path, locations in grouped(integration):
        if path in selected:
            continue
        lines = read(path, False) or []
        add(path, ExcerptKind.INTEGRATION_SOURCE, _windows(locations, 5, 15, len(lines)))
        selected.add(path)
    for path in sorted(python_files, key=lambda item: (len(item.parts), item.as_posix())):
        if path.name in ENTRY_POINT_NAMES and path not in selected and not _is_test(path):
            add(path, ExcerptKind.ENTRY_POINT, list(range(1, 81)))
            selected.add(path)
    tests = [path for path in sorted(python_files, key=lambda item: item.as_posix()) if _is_test(path)]
    if len(tests) > limits.max_test_files:
        budget.truncated = True
    for path in tests[:limits.max_test_files]:
        lines = read(path, False) or []
        add(path, ExcerptKind.TEST_INDEX, [number for number, text in enumerate(lines, 1) if TEST_LINE.match(text)])

    if redactions:
        limitations.append(f"{redactions} likely secret value(s) were redacted before sending excerpts to the model.")
    if budget.truncated:
        limitations.append("The excerpt budget was reached; some documentation or source was not sent to the model.")
    if discovery.documents_truncated:
        limitations.append("Repository documentation exceeded the recorded document limit; some files were not considered.")
    return excerpts, budget.truncated or discovery.documents_truncated, sorted(set(limitations))
