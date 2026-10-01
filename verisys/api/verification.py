"""Public result projection of existing immutable evidence and deterministic judgment.

No source reads, classification, judgment or provider calls happen here.
"""
from pydantic import Field, JsonValue
from verisys.models import VerificationRun, SourceLocation
from verisys.models.base import DomainModel
from verisys.models.enums import Applicability, ExecutionStatus, VerificationMode, VerdictStatus, EvidenceType, TraceEventType


class ResultEvidence(DomainModel):
    id: str
    type: EvidenceType
    source: str
    tool: str
    claim: str
    source_location: SourceLocation | None
    observation: dict[str, JsonValue]
    limitations: list[str]


class ResultTrace(DomainModel):
    type: TraceEventType
    stage: str
    summary: str
    evidence_ids: list[str]


class VerificationResult(DomainModel):
    evaluation_id: str
    evaluation_name: str
    architecture_id: str
    applicability: Applicability
    execution_status: ExecutionStatus
    verification_mode: VerificationMode
    verdict_status: VerdictStatus | None
    verdict_evidence_ids: list[str]
    policy: str
    summary: str
    counts: dict[str, int]
    coverage_complete: bool
    coverage_percent: float | None
    evidence: list[ResultEvidence] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    trace: list[ResultTrace] = Field(default_factory=list)


def project_result(run: VerificationRun, architecture_id: str) -> VerificationResult:
    # The existing run already records the Judge's counts, including the no-verdict case.
    coverage = next(event.metadata for event in run.trace if event.stage == "coverage")
    return VerificationResult(
        evaluation_id=run.evaluation.id, evaluation_name=run.evaluation.name,
        architecture_id=architecture_id, applicability=run.evaluation.applicability,
        execution_status=run.execution_status, verification_mode=run.plan.verification_mode,
        verdict_status=run.verdict.status if run.verdict else None,
        verdict_evidence_ids=list(run.verdict.evidence_ids) if run.verdict else [],
        policy=run.plan.claim,
        summary=run.verdict.summary if run.verdict else "No supported calls in the complete inspected scope; this evaluation is not applicable.",
        counts={key: coverage[key] for key in ("configured", "missing", "unknown", "total")},
        coverage_complete=coverage["coverage_complete"], coverage_percent=coverage["coverage_percent"],
        evidence=[ResultEvidence(id=e.id, type=e.type, source=e.source, tool=e.tool,
            claim=e.claim, source_location=e.source_location, observation=e.observed_value,
            limitations=list(e.limitations)) for e in run.evidence],
        limitations=list(dict.fromkeys([*run.limitations, *(run.verdict.limitations if run.verdict else [])])),
        trace=[ResultTrace(type=e.type, stage=e.stage, summary=e.summary,
            evidence_ids=e.related_evidence_ids) for e in run.trace],
    )
