"""Deterministic timeout judgment from immutable Evidence only; no filesystem IO."""
from dataclasses import dataclass

from verisys.models import Applicability, Evidence, Verdict
from .timeout import POLICY_ID, TOOL, TimeoutStatus


@dataclass(frozen=True)
class TimeoutCounts:
    configured: int
    missing: int
    unknown: int

    @property
    def total(self):
        return self.configured + self.missing + self.unknown

    def observed(self, complete):
        return dict(configured=self.configured, missing=self.missing, unknown=self.unknown,
                    total=self.total, coverage_complete=complete and self.unknown == 0,
                    coverage_percent=round(100 * self.configured / self.total, 1)
                    if complete and self.unknown == 0 and self.total else None)


@dataclass(frozen=True)
class TimeoutJudgment:
    applicability: Applicability
    counts: TimeoutCounts
    verdict: Verdict | None


def judge_timeouts(evidence: list[Evidence]) -> TimeoutJudgment:
    ids = [item.id for item in evidence]
    if len(ids) != len(set(ids)) or any(item.tool != TOOL or item.type != "STATIC_ANALYSIS" for item in evidence):
        raise ValueError("Invalid timeout evidence provenance or duplicate IDs")
    scopes = [item for item in evidence if item.observed_value.get("kind") == "scope"]
    calls = [item for item in evidence if item.observed_value.get("kind") == "call"]
    if len(scopes) != 1 or len(calls) + 1 != len(evidence):
        raise ValueError("Exactly one scope observation and its call observations are required")
    scope = scopes[0]
    manifest = scope.observed_value
    if manifest.get("policy") != POLICY_ID or manifest.get("call_evidence_ids") != [item.id for item in calls]:
        raise ValueError("Call evidence must match the inspected scope manifest")
    statuses = [TimeoutStatus(item.observed_value["timeout_status"]) for item in calls]
    counts = TimeoutCounts(*(statuses.count(status) for status in TimeoutStatus))
    complete = manifest.get("scope_complete") is True
    if counts.total == 0 and complete:
        return TimeoutJudgment(Applicability.NOT_APPLICABLE, counts, None)
    applicability = Applicability.APPLICABLE if counts.total else Applicability.UNKNOWN
    if counts.missing:
        status, rule = "VIOLATED", "A call conclusively fails the explicit per-call timeout policy."
    elif counts.unknown or not complete or not counts.total:
        status, rule = "NOT_VERIFIABLE", "Required call observations or scope completeness are unresolved."
    else:
        status, rule = "VERIFIED", "Every call in the complete supported scope satisfies the per-call policy."
    limitations = list(scope.limitations)
    if counts.unknown or not complete:
        limitations.append("Overall timeout coverage is incomplete; unknown calls are not missing calls.")
    verdict = Verdict(status=status, requirement_id=POLICY_ID, evidence_ids=ids,
                      expected={"ratio": 1.0, "unknown": 0, "scope_complete": True},
                      observed=counts.observed(complete), summary=rule, limitations=limitations)
    return TimeoutJudgment(applicability, counts, verdict)
