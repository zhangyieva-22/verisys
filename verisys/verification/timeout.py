"""Explicit per-call OpenAI policy. No evaluation, inheritance, or execution."""
import ast
import hashlib
import json
import math
from enum import StrEnum
from pathlib import Path

from verisys.architecture.python_ast import SourceAnalyzer
from verisys.models import ArchitectureIR, Evidence, SourceLocation
from verisys.repository.discovery import DiscoveryResult
from verisys.repository.safe_read import UnsafeSourceError, read_python_source

POLICY_ID = "external-api-timeout-coverage-v1"
TOOL = "python-static-timeout-v1"
CLAIM = "All supported OpenAI API call sites must define an explicit per-call timeout."
POLICY_LIMITS = [
    "Explicit per-call configuration only; SDK defaults and client-level inheritance are not evaluated.",
    "No variable evaluation, wrapper resolution, runtime timeout behavior, or network reliability is established.",
]


class TimeoutStatus(StrEnum):
    CONFIGURED = "CONFIGURED"
    MISSING = "MISSING"
    UNKNOWN = "UNKNOWN"


def stable_id(prefix, value):
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return prefix + ":" + hashlib.sha256(encoded.encode()).hexdigest()


def make_evidence(observed, source, loc=None, limitations=()):
    return Evidence(id=stable_id("timeout-evidence", [POLICY_ID, source, loc.model_dump() if loc else None, observed]),
                    type="STATIC_ANALYSIS", source=source, source_location=loc,
                    tool=TOOL, claim=CLAIM, observed_value=observed, limitations=limitations)


def classify(call):
    timeouts = [kw.value for kw in call.keywords if kw.arg == "timeout"]
    if any(kw.arg is None for kw in call.keywords):
        return TimeoutStatus.UNKNOWN, bool(timeouts), None, "expanded_keywords"
    if not timeouts:
        return TimeoutStatus.MISSING, False, None, "explicit_per_call_timeout_absent"
    if len(timeouts) != 1:
        return TimeoutStatus.UNKNOWN, True, None, "duplicate_timeout_keywords"
    value = timeouts[0]
    literal = value.value if isinstance(value, ast.Constant) else None
    if isinstance(value, ast.UnaryOp) and isinstance(value.op, (ast.USub, ast.UAdd)) and isinstance(value.operand, ast.Constant):
        number = value.operand.value
        if type(number) in (int, float):
            literal = -number if isinstance(value.op, ast.USub) else number
    is_literal = isinstance(value, ast.Constant) or literal is not None
    if not is_literal:
        return TimeoutStatus.UNKNOWN, True, None, "nonliteral_timeout"
    if type(literal) in (int, float) and (type(literal) is int or math.isfinite(literal)) and literal > 0:
        return TimeoutStatus.CONFIGURED, True, literal, "positive_numeric_literal"
    # Do not serialize arbitrary strings, objects or nonfinite values.
    return TimeoutStatus.MISSING, True, None, "invalid_timeout_literal"


class _CallObserver(SourceAnalyzer):
    """Reuse recognition; never infer scope beyond ArchitectureIR call locations."""
    def __init__(self, path, expected):
        super().__init__(path, {}, set(), ArchitectureIR(repository_root="inspection"))
        self.expected = expected
        self.calls = {}

    def visit_Call(self, node):
        key = (node.lineno, node.col_offset)
        symbol = self.qualified(node.func)
        if key in self.expected and symbol:
            normalized = symbol.removeprefix("client:")
            if normalized.startswith("openai."):
                self.calls[key] = (node, normalized.removeprefix("openai."))
        super().visit_Call(node)


def inspect_timeouts(discovery: DiscoveryResult, architecture: ArchitectureIR,
                     source_hashes: dict[Path, str]) -> list[Evidence]:
    """Bounded second read, comparing bytes observed during fresh architecture analysis.

    Any architecture limitation conservatively prevents complete-scope success;
    we do not parse limitation prose to guess completeness. This is a bounded
    detector contract, never proof that arbitrary Python contains no other calls.
    """
    sites = sorted({(loc.file, loc.line, loc.column) for service in architecture.external_services
                    if service.client_library == "openai" for loc in service.call_sites},
                   key=lambda item: (item[0], item[1], -1 if item[2] is None else item[2]))
    issues = list(architecture.limitations)
    outside = sorted({service.client_library or service.name for service in architecture.external_services
                      if service.client_library != "openai"})
    evidence = []
    consumed = 0
    # Revalidate every discovered source: a previously call-free file can change.
    # No second traversal; parse only files containing authoritative call sites.
    files = sorted({path.as_posix() for path in discovery.files} | {file for file, _, _ in sites})
    for file_index, file in enumerate(files):
        path = Path(file)
        expected = {(line, column) for name, line, column in sites if name == file}
        calls, digest, failure = {}, None, None
        if path not in discovery.files or path not in source_hashes:
            failure = "source_not_in_analyzed_scope"
        elif file_index >= discovery.limits.max_files:
            failure = "file_count_limit"
        else:
            try:
                data = read_python_source(discovery.repository_root, path,
                    max_file_bytes=discovery.limits.max_file_bytes,
                    remaining_bytes=discovery.limits.max_total_bytes - consumed)
                consumed += len(data)
                digest = hashlib.sha256(data).hexdigest()
                if digest != source_hashes[path]:
                    failure = "source_changed"
                elif expected:
                    tree = ast.parse(data, filename=file)
                    observer = _CallObserver(path, expected)
                    observer.visit(tree)
                    calls = observer.calls
            except UnsafeSourceError as error:
                consumed += error.bytes_read
                failure = error.reason.value
            except (SyntaxError, ValueError, RecursionError):
                failure = "parse_or_traversal_failed"
        if failure:
            issues.append(f"{file}: timeout inspection unavailable ({failure}).")
        for line, column in sorted(expected, key=lambda item: (item[0], -1 if item[1] is None else item[1])):
            loc = SourceLocation(file=file, line=line, column=column)
            call = calls.get((line, column))
            if failure or call is None:
                status, present, literal, reason = TimeoutStatus.UNKNOWN, None, None, failure or "call_identity_unresolved"
                operation = None
            else:
                node, operation = call
                status, present, literal, reason = classify(node)
            observed = dict(kind="call", service="OpenAI", client_library="openai", operation=operation,
                            timeout_status=status.value, timeout_argument_present=present,
                            reason=reason, source_sha256=digest)
            if literal is not None:
                observed["timeout_literal"] = literal
            evidence.append(make_evidence(observed, file, loc,
                (reason,) if status == TimeoutStatus.UNKNOWN else ()))
    complete = not issues and not discovery.truncated and set(discovery.files) == set(source_hashes)
    scope = dict(kind="scope", policy=POLICY_ID, scope_complete=complete,
                 call_evidence_ids=[item.id for item in evidence],
                 analyzed_sources={path.as_posix(): digest for path, digest in sorted(source_hashes.items())},
                 outside_grammar=outside)
    limitations = [*POLICY_LIMITS, *sorted(set(issues))]
    limitations += [f"{library}: timeout semantics outside this OpenAI per-call grammar." for library in outside]
    evidence.append(make_evidence(scope, "fresh repository discovery and architecture analysis", limitations=limitations))
    return evidence
