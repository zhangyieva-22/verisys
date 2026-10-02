"""Finite-timeout policy for requests and httpx calls. No evaluation or execution.

The policy follows each library's documented behavior: requests never times out
by default (per call, and Session has no timeout setting), while httpx defaults
to five seconds and client methods inherit the client's timeout. Timeouts may
be disabled with None in both. Custom requests adapters can supply a timeout,
so calls without one on a session with .mount(...) are UNKNOWN, never MISSING.
"""
import ast
from pathlib import Path

from verisys.architecture.python_ast import CONSTRUCTORS, HTTP_CALLS, SourceAnalyzer
from verisys.models import ArchitectureIR, Evidence
from verisys.repository.discovery import DiscoveryResult
from .static_timeouts import (
    CallObservation, TimeoutPolicy, TimeoutStatus, inspect_call_timeouts, numeric_literal, positive_finite,
)

POLICY_ID = "http-client-timeout-coverage-v1"
TOOL = "python-static-http-timeout-v1"
CLAIM = "Every supported requests and httpx call site has a finite timeout."
POLICY_LIMITS = [
    "Only direct requests/httpx calls on module functions or simply bound clients are inspected; "
    "wrappers, adapters and clients passed between functions are not resolved.",
    "library_default relies on the documented five-second httpx default; the installed httpx version is not checked.",
    "A finite timeout does not establish that its value is appropriate, or any runtime or network behavior.",
]
LIBRARIES = frozenset(HTTP_CALLS)
TUPLE_LENGTHS = {"requests": 2, "httpx": 4}

CONFIGURED, MISSING, UNKNOWN = TimeoutStatus.CONFIGURED, TimeoutStatus.MISSING, TimeoutStatus.UNKNOWN


def _value(value, library, qualified):
    """(status, literal, reason) for one explicit timeout expression."""
    is_literal, literal = numeric_literal(value)
    if is_literal:
        if literal is None:
            return MISSING, None, "timeout_disabled"
        if positive_finite(literal):
            return CONFIGURED, literal, "positive_numeric_literal"
        return MISSING, None, "invalid_timeout_literal"
    if isinstance(value, ast.Tuple):
        if len(value.elts) != TUPLE_LENGTHS[library]:
            return MISSING, None, "invalid_timeout_literal"
        parts = [_value(item, library, qualified) for item in value.elts]
    elif library == "httpx" and isinstance(value, ast.Call) and qualified(value.func) == "httpx.Timeout":
        if not (value.args or value.keywords) or any(keyword.arg is None for keyword in value.keywords):
            return UNKNOWN, None, "unsupported_timeout_object"
        parts = [_value(item, library, qualified) for item in [*value.args, *(kw.value for kw in value.keywords)]]
    else:
        return UNKNOWN, None, "nonliteral_timeout"
    # A disabled or invalid part is conclusive even when another part is unresolved.
    for status in (MISSING, UNKNOWN):
        failed = next((part for part in parts if part[0] == status), None)
        if failed:
            return status, None, failed[2]
    literal = [part[1] for part in parts] if isinstance(value, ast.Tuple) else None
    return CONFIGURED, literal, "positive_timeout_literals" if literal else "positive_timeout_object"


def _keyword(call):
    """(state, value): 'expanded', 'duplicate', 'absent' or 'present'."""
    values = [keyword.value for keyword in call.keywords if keyword.arg == "timeout"]
    if any(keyword.arg is None for keyword in call.keywords):
        return "expanded", None
    if len(values) > 1:
        return "duplicate", None
    return ("present", values[0]) if values else ("absent", None)


class _HttpCallObserver(SourceAnalyzer):
    """Match analyzer call locations; client identity includes its constructor location."""

    def __init__(self, path, expected):
        super().__init__(path, {}, set(), ArchitectureIR(repository_root="inspection"))
        self.expected = expected
        self.constructors: dict[str, ast.Call] = {}
        self.mounted: set[str] = set()
        self.calls = {}

    def assign(self, targets, value):
        constructor = self.qualified(value.func) if isinstance(value, ast.Call) else None
        super().assign(targets, value)
        library = CONSTRUCTORS.get(constructor)
        if library in LIBRARIES:
            identity = f"{library}@{value.lineno}:{value.col_offset}"
            self.constructors[identity] = value
            for target in targets:
                if isinstance(target, ast.Name):
                    self.bindings[target.id] = "client:" + identity

    def visit_Call(self, node):
        symbol = self.qualified(node.func)
        if symbol and symbol.startswith("client:"):
            identity, _, operation = symbol.removeprefix("client:").partition(".")
            library = identity.partition("@")[0]
            if library == "requests" and operation == "mount":
                self.mounted.add(identity)
            if (node.lineno, node.col_offset) in self.expected and operation in HTTP_CALLS.get(library, ()):
                self.calls[(node.lineno, node.col_offset)] = (node, library, operation, identity)
        elif symbol:
            library, _, operation = symbol.partition(".")
            if (node.lineno, node.col_offset) in self.expected and operation in HTTP_CALLS.get(library, ()):
                self.calls[(node.lineno, node.col_offset)] = (node, library, operation, None)
        super().visit_Call(node)

    def classify(self, node, library, operation, identity):
        def observed(status, present, literal, reason, source=None):
            extra = (("timeout_source", source),) if source else ()
            return CallObservation(operation, status, present, literal, reason, extra)

        state, value = _keyword(node)
        if state == "expanded":
            return observed(UNKNOWN, None, None, "expanded_keywords")
        if state == "duplicate":
            return observed(UNKNOWN, True, None, "duplicate_timeout_keywords")
        if state == "present":
            status, literal, reason = _value(value, library, self.qualified)
            return observed(status, True, literal, reason, "call" if status == CONFIGURED else None)
        if library == "requests":
            if identity in self.mounted:
                return observed(UNKNOWN, False, None, "custom_adapter_may_set_timeout")
            return observed(MISSING, False, None, "requests_has_no_default_timeout")
        if identity is None:
            return observed(CONFIGURED, False, None, "httpx_default_timeout", "library_default")
        client_state, client_value = _keyword(self.constructors[identity])
        if client_state in ("expanded", "duplicate"):
            return observed(UNKNOWN, False, None, "client_timeout_unresolved")
        if client_state == "absent":
            return observed(CONFIGURED, False, None, "httpx_default_timeout", "library_default")
        status, literal, reason = _value(client_value, library, self.qualified)
        if status == CONFIGURED:
            return observed(CONFIGURED, False, literal, "client_timeout_configured", "client")
        return observed(status, False, None, "client_" + reason)


def _observe(path, expected, tree):
    observer = _HttpCallObserver(path, expected)
    observer.visit(tree)
    # Classify after the whole module is visited: a later .mount(...) still applies.
    return {key: observer.classify(*call) for key, call in observer.calls.items()}


POLICY = TimeoutPolicy(
    policy_id=POLICY_ID, tool=TOOL, claim=CLAIM, limitations=tuple(POLICY_LIMITS),
    libraries=LIBRARIES, service_names={library: "Outbound HTTP" for library in LIBRARIES}, observe=_observe,
    outside_note="{library}: timeout semantics outside this requests/httpx grammar.",
)


def inspect_http_timeouts(discovery: DiscoveryResult, architecture: ArchitectureIR,
                          source_hashes: dict[Path, str]) -> list[Evidence]:
    return inspect_call_timeouts(POLICY, discovery, architecture, source_hashes)
