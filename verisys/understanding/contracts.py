"""Understanding contracts: inferred claims about a repository, never Evidence or Verdicts.

Every claim is model-proposed from server-selected excerpts and carries citations
the server has checked against the exact text it sent. A valid citation proves the
quoted text exists at that location; it does not prove the claim is true.
"""
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, create_model

from verisys.models.base import DomainModel

INPUT_VERSION = "understanding-input-v1"
PROMPT_VERSION = "understanding-claims-v1"
INFERRED = "INFERRED_NOT_VERIFIED"
MAX_CLAIMS = 15
MAX_CITATIONS = 5
RiskCategory = Literal["security", "reliability", "performance", "data", "maintainability", "operability"]
Severity = Literal["high", "medium", "low"]


class ExcerptKind(StrEnum):
    README = "README"
    DOCUMENT = "DOCUMENT"
    MANIFEST = "MANIFEST"
    ROUTE_SOURCE = "ROUTE_SOURCE"
    INTEGRATION_SOURCE = "INTEGRATION_SOURCE"
    ENTRY_POINT = "ENTRY_POINT"
    TEST_INDEX = "TEST_INDEX"


class ExcerptLine(DomainModel):
    model_config = ConfigDict(frozen=True)
    number: int = Field(ge=1)
    text: str


class SourceExcerpt(DomainModel):
    """Exact (possibly redacted) lines sent to the model; citations are checked against them."""
    model_config = ConfigDict(frozen=True)
    id: str
    path: str
    kind: ExcerptKind
    lines: tuple[ExcerptLine, ...]
    truncated: bool = False

    def numbered_text(self) -> str:
        return "\n".join(f"{line.number}| {line.text}" for line in self.lines)


class ModelExcerpt(DomainModel):
    id: str
    path: str
    kind: ExcerptKind
    numbered_text: str


class UnderstandingInput(DomainModel):
    """Repository-derived text is untrusted data, separate from trusted instructions."""
    schema_version: str = INPUT_VERSION
    architecture_id: str
    repository: str
    architecture_summary: dict[str, list[str]]
    excerpts: list[ModelExcerpt]
    input_truncated: bool


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LLMCitation(StrictModel):
    excerpt_id: str
    start_line: int
    end_line: int
    quote: str


class LLMRequirement(StrictModel):
    title: str
    description: str
    citations: list[LLMCitation]


class LLMRisk(StrictModel):
    title: str
    description: str
    category: RiskCategory
    severity: Severity
    citations: list[LLMCitation]


class LLMUnderstanding(StrictModel):
    functional_requirements: list[LLMRequirement] = Field(max_length=MAX_CLAIMS)
    risks: list[LLMRisk] = Field(max_length=MAX_CLAIMS)


def understanding_schema(excerpt_ids: tuple[str, ...]) -> type[BaseModel]:
    """Constrain citations to this request's excerpt IDs, like discovery's option enum."""
    citation = create_model("Citation", __base__=LLMCitation, excerpt_id=(Literal[excerpt_ids], ...))
    requirement = create_model("FunctionalRequirement", __base__=LLMRequirement,
                               citations=(list[citation], Field(max_length=MAX_CITATIONS)))
    risk = create_model("Risk", __base__=LLMRisk, citations=(list[citation], Field(max_length=MAX_CITATIONS)))
    return create_model("RepositoryUnderstanding", __base__=LLMUnderstanding,
                        functional_requirements=(list[requirement], Field(max_length=MAX_CLAIMS)),
                        risks=(list[risk], Field(max_length=MAX_CLAIMS)))


class Citation(DomainModel):
    model_config = ConfigDict(frozen=True)
    path: str
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)
    quote: str
    excerpt_kind: ExcerptKind


class InferredRequirement(DomainModel):
    id: str
    title: str
    description: str
    citations: list[Citation] = Field(min_length=1)
    status: Literal["INFERRED_NOT_VERIFIED"] = INFERRED


class InferredRisk(DomainModel):
    id: str
    title: str
    description: str
    category: RiskCategory
    severity: Severity
    citations: list[Citation] = Field(min_length=1)
    status: Literal["INFERRED_NOT_VERIFIED"] = INFERRED


class SourceSummary(DomainModel):
    path: str
    kind: ExcerptKind
    first_line: int
    last_line: int
    line_count: int
    truncated: bool


class UnderstandingResult(DomainModel):
    architecture_id: str
    provider: str
    model: str
    prompt_version: str = PROMPT_VERSION
    functional_requirements: list[InferredRequirement] = Field(default_factory=list)
    risks: list[InferredRisk] = Field(default_factory=list)
    sources: list[SourceSummary] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    input_truncated: bool = False
    rejected_claims: int = 0
    rejected_citations: int = 0
