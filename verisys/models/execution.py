"""Source-declared possible control flow, never runtime Evidence or Trace."""
from enum import StrEnum

from pydantic import Field, model_validator

from .base import DomainModel
from .architecture import SourceLocation


class ExecutionStepType(StrEnum):
    ENTRY = "ENTRY"
    WORKFLOW = "WORKFLOW"
    WORKFLOW_STEP = "WORKFLOW_STEP"
    TOOL_EXECUTION = "TOOL_EXECUTION"
    EXIT = "EXIT"


class ExecutionTransitionType(StrEnum):
    INVOKE = "INVOKE"
    ENTRY = "ENTRY"
    NEXT = "NEXT"
    CONDITIONAL = "CONDITIONAL"
    RETURN = "RETURN"


class ExecutionStep(DomainModel):
    id: str
    type: ExecutionStepType
    label: str
    component_id: str | None = None
    source_locations: list[SourceLocation] = Field(min_length=1)
    candidate_tool_ids: list[str] = Field(default_factory=list)


class ExecutionTransition(DomainModel):
    source: str
    target: str
    type: ExecutionTransitionType
    source_locations: list[SourceLocation] = Field(min_length=1)
    condition: str | None = None


class ExecutionFlow(DomainModel):
    id: str
    name: str
    trigger: str | None = None
    steps: list[ExecutionStep] = Field(default_factory=list)
    transitions: list[ExecutionTransition] = Field(default_factory=list)
    source_locations: list[SourceLocation] = Field(min_length=1)
    limitations: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def valid_endpoints(self):
        ids = {step.id for step in self.steps}
        if len(ids) != len(self.steps):
            raise ValueError("Execution step IDs must be unique")
        if self.trigger is not None and self.trigger not in ids:
            raise ValueError("Execution trigger must reference a step")
        if any(edge.source not in ids or edge.target not in ids for edge in self.transitions):
            raise ValueError("Execution transitions must reference steps in this flow")
        return self
