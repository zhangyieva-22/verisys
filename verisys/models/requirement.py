"""User requirements retain their original text without normalization."""
from pydantic import Field, JsonValue

from .base import DomainModel


class EngineeringRequirement(DomainModel):
    id: str
    raw_requirement: str = Field(min_length=1, frozen=True)
    target: str | None = None
    property: str | None = None
    metric: str | None = None
    operator: str | None = None
    threshold: JsonValue = None
    unit: str | None = None
    workload: dict[str, JsonValue] = Field(default_factory=dict)
    source: str | None = None
