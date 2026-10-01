"""Discovery-only contracts and diagnostics, never verification Evidence/Trace."""
from dataclasses import dataclass
from typing import Annotated, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, JsonValue, create_model
from verisys.models import EvaluationCandidate
from verisys.models.base import DomainModel

SCHEMA_VERSION = "evaluation-discovery-input-v2"
PROMPT_VERSION = "evaluation-option-selection-v2"


class DiscoveryError(ValueError):
    def __init__(self, code: str):
        self.code = code
        self.diagnostics = {}
        super().__init__(f"Evaluation discovery failed ({code}).")


class DiscoveryLimits(DomainModel):
    model_config = ConfigDict(frozen=True)
    max_objects: int = Field(default=1024, ge=0)
    max_subjects: int = Field(default=128, ge=0)
    max_string_chars: int = Field(default=512, ge=16)
    max_input_bytes: int = Field(default=64 * 1024, ge=1024)


class ArchitectureSubject(DomainModel):
    id: str
    kind: str
    facts: dict[str, JsonValue]


class EligibleOption(DomainModel):
    model_config = ConfigDict(frozen=True)
    option_id: str
    architecture_id: str
    evaluation_id: str
    relevance_reason: str
    allowed_subject_ids: list[str]
    architecture_summary: str


class DiscoveryInput(DomainModel):
    schema_version: str = SCHEMA_VERSION
    architecture_id: str
    catalog_version: str
    languages: list[str]
    subjects: list[ArchitectureSubject]
    architecture_limitations: list[str]
    input_truncated: bool
    discovery_limitations: list[str]
    catalog: list[dict[str, JsonValue]]
    eligible_options: list[EligibleOption] = Field(default_factory=list)


class GroundedSelection(DomainModel):
    evaluation_id: str = Field(min_length=1, max_length=128, strict=True)
    architecture_subject_ids: list[Annotated[str, Field(min_length=1, max_length=512, strict=True)]] = Field(min_length=1, max_length=128)
    relevance_reason: str = Field(min_length=1, max_length=64, strict=True)


class GroundedSelections(DomainModel):
    candidates: list[GroundedSelection] = Field(max_length=4)


class LLMSelections(DomainModel):
    selected_option_ids: list[Annotated[str, Field(min_length=1, max_length=80, strict=True)]] = Field(max_length=5)


def selection_schema(options):
    """Constrain this request's structured-output enum to supplied option IDs."""
    identifiers = tuple(option.option_id for option in options)
    if not identifiers:
        return LLMSelections
    return create_model("EligibleOptionSelection", __base__=LLMSelections,
        selected_option_ids=(list[Literal[identifiers]], Field(max_length=5)))


@dataclass(frozen=True)
class StructuredGenerationResult:
    payload: JsonValue = None
    status: Literal["COMPLETED", "REFUSED", "INCOMPLETE", "INVALID"] = "COMPLETED"
    request_id: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None


class StructuredGenerationClient(Protocol):
    provider: str
    model: str

    def generate(self, *, instructions: str, structured_input: DiscoveryInput,
                 response_schema: type[BaseModel]) -> StructuredGenerationResult: ...


class DiscoveryResult(DomainModel):
    candidates: list[EvaluationCandidate] = Field(default_factory=list)
    architecture_id: str
    catalog_version: str
    limitations: list[str] = Field(default_factory=list)
    input_truncated: bool
    diagnostics: dict[str, JsonValue] = Field(default_factory=dict)
