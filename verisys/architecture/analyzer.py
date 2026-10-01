"""Discovery output -> safe source reads -> static ArchitectureIR."""

import ast
from pathlib import Path
from collections.abc import Callable

from verisys.models.architecture import ArchitectureIR
from verisys.repository.discovery import DiscoveryLimits, DiscoveryResult
from verisys.repository.safe_read import ReadReason, UnsafeSourceError, read_python_source

from .python_ast import SERVICES, SourceAnalyzer, collect_dependencies, module_name


def _known_local_collisions(discovery: DiscoveryResult) -> set[str]:
    """Only names present in discovery, without inferring import/source roots.

    A supported-named .py module or containing package directory is a collision
    candidate, even if skipped. This does not claim it shadows an import at
    runtime; it makes external-library identity uncertain.
    """
    collisions = set()
    paths = [*discovery.files, *(item.path for item in discovery.skipped)]
    for path in paths:
        if path.is_absolute() or ".." in path.parts:
            continue
        if path.suffix == ".py" and path.stem in {*SERVICES, "sqlite3", "langchain_core", "langgraph"}:
            collisions.add(path.stem)
        collisions.update(part for part in path.parts if part in {*SERVICES, "sqlite3", "langchain_core", "langgraph"})
    return collisions


def analyze_architecture(
    discovery: DiscoveryResult, *, limits: DiscoveryLimits | None = None,
    on_source: Callable[[Path, bytes], None] | None = None,
) -> ArchitectureIR:
    """Inspect only discovered paths. No imports, execution, or file walking.

    Discovery's effective limits are reused. An explicit override can only
    tighten each limit (the minimum of the two configurations is used).
    The combined source byte/file limits are enforced again. Discovery
    omissions and parse/read failures remain explicit limitations.
    on_source observes safely read bytes for consistency checks; it does not
    alter ArchitectureIR or permit another filesystem traversal.
    """
    limits = discovery.limits if limits is None else DiscoveryLimits(**{
        name: min(getattr(discovery.limits, name), getattr(limits, name))
        for name in DiscoveryLimits.model_fields
    })
    root = discovery.repository_root
    result = ArchitectureIR(repository_root=str(root), limitations=list(discovery.limitations))
    if discovery.truncated:
        result.limitations.append("Repository discovery was truncated; architecture is incomplete.")
    for skipped in discovery.skipped:
        if skipped.path.suffix == ".py" or skipped.reason.value == "IO_ERROR":
            result.limitations.append(f"Discovery skipped {skipped.path.as_posix()}: {skipped.reason.value}")

    paths = sorted(set(discovery.files), key=lambda path: path.as_posix())
    modules: dict[str, Path] = {}
    ambiguous = set()
    for path in paths:
        if path.is_absolute() or ".." in path.parts or path.suffix != ".py":
            continue
        name = module_name(path)
        if name in modules:
            ambiguous.add(name)
        else:
            modules[name] = path
    for name in sorted(ambiguous):
        modules.pop(name)
        result.limitations.append(f"Ambiguous local module name: {name}; imports will not be resolved.")

    parsed = {}
    total_bytes = 0
    collisions = _known_local_collisions(discovery)
    for index, relative in enumerate(paths):
        label = relative.as_posix()
        if index >= limits.max_files:
            result.limitations.append(f"{label}: architecture file-count limit reached; remaining files not read.")
            break
        try:
            data = read_python_source(root, relative, max_file_bytes=limits.max_file_bytes,
                                      remaining_bytes=limits.max_total_bytes - total_bytes)
        except UnsafeSourceError as error:
            total_bytes += error.bytes_read
            result.limitations.append(f"{label}: safe read rejected ({error.reason.value}).")
            if error.reason == ReadReason.AGGREGATE_BUDGET_EXHAUSTED:
                result.limitations.append(f"{label}: total source byte limit reached; remaining files not read.")
                break
            continue
        total_bytes += len(data)
        if on_source is not None:
            on_source(relative, data)
        result.languages = ["Python"]
        try:
            tree = ast.parse(data, filename=label)
        except (SyntaxError, ValueError, RecursionError) as error:
            line = getattr(error, "lineno", None)
            result.limitations.append(f"{label}: Python parse failed ({type(error).__name__}, line {line}).")
            continue
        parsed[relative] = tree
        try:
            collect_dependencies(tree, relative, modules, ambiguous, result)
            SourceAnalyzer(relative, modules, ambiguous, result, collisions=collisions).visit(tree)
        except RecursionError:
            result.limitations.append(f"{label}: AST traversal depth exceeded; file only partially inspected.")

    from .execution_flow import extract_execution_flows
    extract_execution_flows(parsed, result, collisions, ambiguous)

    result.frameworks = sorted(set(result.frameworks))
    result.api_routes.sort(key=lambda route: (
        route.source_location.file, route.source_location.line, route.source_location.column or 0,
        route.method, route.path, route.handler,
    ))
    result.external_services.sort(key=lambda service: (service.name, service.client_library or ""))
    result.tools.sort(key=lambda tool: (tool.module, tool.source_location.line, tool.name))
    result.datastores.sort(key=lambda store: (store.name, store.engine))
    for store in result.datastores:
        store.source_locations.sort(key=lambda loc: (loc.file, loc.line, loc.column or 0))
    for service in result.external_services:
        for locations in (service.source_locations, service.call_sites):
            locations.sort(key=lambda location: (location.file, location.line, location.column or 0))
    result.dependencies.sort(key=lambda dependency: (
        dependency.source_component, dependency.target_component,
        dependency.source_location.line if dependency.source_location else 0,
    ))
    result.limitations = sorted(set(result.limitations))
    return result
