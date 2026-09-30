"""Caller-supplied observed evidence; models never collect measurements."""
import json

from pydantic import (
    ConfigDict, Field, JsonValue, TypeAdapter, field_validator, model_serializer,
)

from .architecture import SourceLocation
from .base import DomainModel
from .enums import EvidenceType


class Evidence(DomainModel):
    """Immutable observation with a JSON snapshot of caller-supplied data.

    observed_value returns a fresh decoded copy. Editing that copy, or the
    original input, cannot mutate Evidence-owned data. Dumps expose ordinary
    JSON values, not the internal snapshot string. Limitations are a tuple.
    """

    model_config = ConfigDict(frozen=True)

    id: str
    type: EvidenceType
    source: str = Field(min_length=1)
    claim: str
    observation_json: str = Field(validation_alias="observed_value", repr=False)
    unit: str | None = None
    source_location: SourceLocation | None = None
    tool: str = Field(min_length=1)
    limitations: tuple[str, ...] = Field(default_factory=tuple)

    @field_validator("observation_json", mode="before")
    @classmethod
    def snapshot_observation(cls, value: JsonValue) -> str:
        validated = TypeAdapter(JsonValue).validate_python(value)
        return json.dumps(validated, ensure_ascii=False, allow_nan=False)

    @property
    def observed_value(self) -> JsonValue:
        return json.loads(self.observation_json)

    @model_serializer(mode="wrap")
    def serialize_observation(self, handler):
        data = handler(self)
        if "observation_json" in data:
            data["observed_value"] = json.loads(data.pop("observation_json"))
        return data
