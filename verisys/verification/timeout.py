"""Explicit per-call OpenAI policy. No evaluation, inheritance, or execution."""
from pathlib import Path

from verisys.architecture.python_ast import SourceAnalyzer
from verisys.models import ArchitectureIR, Evidence
from verisys.repository.discovery import DiscoveryResult
from .static_timeouts import (
    CallObservation, TimeoutPolicy, TimeoutStatus, inspect_call_timeouts, numeric_literal, positive_finite, stable_id,
)

__all__ = ["CLAIM", "POLICY", "POLICY_ID", "POLICY_LIMITS", "TOOL", "TimeoutStatus", "classify",
           "inspect_timeouts", "stable_id"]

POLICY_ID = "external-api-timeout-coverage-v1"
TOOL = "python-static-timeout-v1"
CLAIM = "All supported OpenAI API call sites must define an explicit per-call timeout."
POLICY_LIMITS = [
    "Explicit per-call configuration only; SDK defaults and client-level inheritance are not evaluated.",
    "No variable evaluation, wrapper resolution, runtime timeout behavior, or network reliability is established.",
]


def classify(call):
    timeouts = [kw.value for kw in call.keywords if kw.arg == "timeout"]
    if any(kw.arg is None for kw in call.keywords):
        return TimeoutStatus.UNKNOWN, bool(timeouts), None, "expanded_keywords"
    if not timeouts:
        return TimeoutStatus.MISSING, False, None, "explicit_per_call_timeout_absent"
    if len(timeouts) != 1:
        return TimeoutStatus.UNKNOWN, True, None, "duplicate_timeout_keywords"
    is_literal, literal = numeric_literal(timeouts[0])
    if not is_literal:
        return TimeoutStatus.UNKNOWN, True, None, "nonliteral_timeout"
    if positive_finite(literal):
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


def _observe(path, expected, tree):
    observer = _CallObserver(path, expected)
    observer.visit(tree)
    return {key: CallObservation(operation, *classify(node)) for key, (node, operation) in observer.calls.items()}


POLICY = TimeoutPolicy(
    policy_id=POLICY_ID, tool=TOOL, claim=CLAIM, limitations=tuple(POLICY_LIMITS),
    libraries=frozenset({"openai"}), service_names={"openai": "OpenAI"}, observe=_observe,
    outside_note="{library}: timeout semantics outside this OpenAI per-call grammar.",
)


def inspect_timeouts(discovery: DiscoveryResult, architecture: ArchitectureIR,
                     source_hashes: dict[Path, str]) -> list[Evidence]:
    return inspect_call_timeouts(POLICY, discovery, architecture, source_hashes)
