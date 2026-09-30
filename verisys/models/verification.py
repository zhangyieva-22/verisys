"""Verification contracts and run state; no verification logic."""
from typing import Self

from pydantic import ConfigDict, Field, JsonValue, model_validator

from .architecture import ArchitectureIR
from .base import DomainModel
from .enums import ExecutionStatus, VerdictStatus, VerificationMode
from .evaluation import EvaluationCandidate
from .evidence import Evidence
from .requirement import EngineeringRequirement
from .trace import TraceEvent


class VerificationPlan(DomainModel):
    evaluation_id: str | None = Field(default=None, frozen=True)
    requirement_id: str | None = Field(default=None, frozen=True)
    claim: str
    target: str | None = None
    verification_mode: VerificationMode
    required_evidence: list[str] = Field(default_factory=list)
    tool: str
    procedure: list[str] = Field(default_factory=list)
    acceptance_condition: str
    limitations: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_subject(self) -> Self:
        if not (self.evaluation_id or self.requirement_id):
            raise ValueError("An evaluation_id or requirement_id is required")
        return self


class Verdict(DomainModel):
    # Status and evidence links change together only in a validated replacement.
    model_config = ConfigDict(frozen=True)

    status: VerdictStatus
    evaluation_id: str | None = Field(default=None, frozen=True)
    requirement_id: str | None = Field(default=None, frozen=True)
    evidence_ids: tuple[str, ...] = Field(default_factory=tuple)
    expected: JsonValue = None
    observed: JsonValue = None
    summary: str
    limitations: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_subject(self) -> Self:
        if not (self.evaluation_id or self.requirement_id):
            raise ValueError("An evaluation_id or requirement_id is required")
        if self.status != VerdictStatus.NOT_VERIFIABLE and not self.evidence_ids:
            raise ValueError("VERIFIED and VIOLATED require at least one evidence ID")
        return self


class VerificationRun(DomainModel):
    id: str
    architecture: ArchitectureIR
    evaluation: EvaluationCandidate | None = Field(default=None, frozen=True)
    requirement: EngineeringRequirement | None = Field(default=None, frozen=True)
    plan: VerificationPlan | None = None
    execution_status: ExecutionStatus = ExecutionStatus.PENDING
    evidence: list[Evidence] = Field(default_factory=list)
    verdict: Verdict | None = None
    trace: list[TraceEvent] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_subject(self) -> Self:
        if self.evaluation is None and self.requirement is None:
            raise ValueError("An evaluation or requirement is required")
        return self
