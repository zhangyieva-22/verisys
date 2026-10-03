"""Shared static per-call timeout inspection. Policies classify; this module collects.

A policy names the client libraries in scope and classifies the calls an observer
matches at analyzer-reported locations. Scope, safe re-reads, content-hash checks,
exact call identity and the scope manifest are identical for every policy.
"""
import ast
import hashlib
import json
import math
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from verisys.models import ArchitectureIR, Evidence, SourceLocation
from verisys.repository.discovery import DiscoveryResult
from verisys.repository.safe_read import UnsafeSourceError, read_python_source


class TimeoutStatus(StrEnum):
    CONFIGURED = "CONFIGURED"
    MISSING = "MISSING"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class CallObservation:
    """One classified call; extra holds policy-specific observation fields."""
    operation: str | None
    status: TimeoutStatus
    present: bool | None
    literal: object
    reason: str
    extra: tuple[tuple[str, object], ...] = ()


# Observer contract: (file path, expected (line, column) keys, parsed module) ->
# observations for the expected calls it could match. Unmatched calls stay UNKNOWN.
Observe = Callable[[Path, set, ast.Module], dict[tuple[int, int | None], CallObservation]]


@dataclass(frozen=True)
class TimeoutPolicy:
    policy_id: str
    tool: str
    claim: str
    limitations: tuple[str, ...]
    libraries: frozenset[str]
    service_names: dict[str, str]
    observe: Observe
    outside_note: str


def stable_id(prefix, value):
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return prefix + ":" + hashlib.sha256(encoded.encode()).hexdigest()


def make_evidence(policy, observed, source, loc=None, limitations=()):
    return Evidence(id=stable_id("timeout-evidence", [policy.policy_id, source, loc.model_dump() if loc else None, observed]),
                    type="STATIC_ANALYSIS", source=source, source_location=loc,
                    tool=policy.tool, claim=policy.claim, observed_value=observed, limitations=limitations)


def numeric_literal(value):
    """(is_literal, literal) for a constant or a signed numeric constant; never evaluates names."""
    if isinstance(value, ast.Constant):
        return True, value.value
    if isinstance(value, ast.UnaryOp) and isinstance(value.op, (ast.USub, ast.UAdd)) and isinstance(value.operand, ast.Constant):
        number = value.operand.value
        if type(number) in (int, float):
            return True, -number if isinstance(value.op, ast.USub) else number
    return False, None


def positive_finite(literal):
    return type(literal) in (int, float) and (type(literal) is int or math.isfinite(literal)) and literal > 0


def inspect_call_timeouts(policy: TimeoutPolicy, discovery: DiscoveryResult, architecture: ArchitectureIR,
                          source_hashes: dict[Path, str], *, non_call_limitations=()) -> list[Evidence]:
    """Bounded second read, comparing bytes observed during fresh architecture analysis.

    Call-scope limitations conservatively prevent complete-scope success.
    Explicitly tagged route-mount presentation limitations do not affect calls;
    we never parse limitation prose to guess completeness. This is a bounded
    detector contract, never proof that arbitrary Python contains no other calls.
    """
    libraries = {(loc.file, loc.line, loc.column): service.client_library
                 for service in architecture.external_services if service.client_library in policy.libraries
                 for loc in service.call_sites}
    sites = sorted(libraries, key=lambda item: (item[0], item[1], -1 if item[2] is None else item[2]))
    issues = [item for item in architecture.limitations if item not in non_call_limitations]
    outside = sorted({service.client_library or service.name for service in architecture.external_services
                      if service.client_library not in policy.libraries})
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
                    calls = policy.observe(path, expected, ast.parse(data, filename=file))
            except UnsafeSourceError as error:
                consumed += error.bytes_read
                failure = error.reason.value
            except (SyntaxError, ValueError, RecursionError):
                failure = "parse_or_traversal_failed"
        if failure:
            issues.append(f"{file}: timeout inspection unavailable ({failure}).")
        for line, column in sorted(expected, key=lambda item: (item[0], -1 if item[1] is None else item[1])):
            loc = SourceLocation(file=file, line=line, column=column)
            library = libraries[(file, line, column)]
            call = None if failure else calls.get((line, column))
            if call is None:
                call = CallObservation(None, TimeoutStatus.UNKNOWN, None, None, failure or "call_identity_unresolved")
            observed = dict(kind="call", service=policy.service_names[library], client_library=library,
                            operation=call.operation, timeout_status=call.status.value,
                            timeout_argument_present=call.present, reason=call.reason, source_sha256=digest)
            if call.literal is not None:
                observed["timeout_literal"] = call.literal
            observed.update(call.extra)
            evidence.append(make_evidence(policy, observed, file, loc,
                (call.reason,) if call.status == TimeoutStatus.UNKNOWN else ()))
    complete = not issues and not discovery.truncated and set(discovery.files) == set(source_hashes)
    scope = dict(kind="scope", policy=policy.policy_id, scope_complete=complete,
                 call_evidence_ids=[item.id for item in evidence],
                 analyzed_sources={path.as_posix(): digest for path, digest in sorted(source_hashes.items())},
                 outside_grammar=outside)
    limitations = [*policy.limitations, *sorted(set(issues)), *sorted(set(non_call_limitations))]
    limitations += [policy.outside_note.format(library=library) for library in outside]
    evidence.append(make_evidence(policy, scope, "fresh repository discovery and architecture analysis", limitations=limitations))
    return evidence
