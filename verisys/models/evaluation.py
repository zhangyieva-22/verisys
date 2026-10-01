"""Architecture-aware evaluation candidate schema."""
from typing import Literal

from pydantic import Field

from .base import DomainModel
from .enums import Applicability, ExecutionSupport, VerificationMode


class EvaluationCandidate(DomainModel):
    id: str
    name: str
    category: str
    applicability: Applicability
    priority: Literal["HIGH", "MEDIUM", "LOW"]
    reason: str
    required_evidence: list[str] = Field(default_factory=list)
    verification_mode: VerificationMode
    execution_support: ExecutionSupport
    related_architecture_evidence_ids: list[str] = Field(default_factory=list)
    architecture_subject_ids: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
