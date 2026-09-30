"""Concise event summaries, never hidden reasoning or chain-of-thought."""
from pydantic import Field, JsonValue

from .base import DomainModel
from .enums import TraceEventType


class TraceEvent(DomainModel):
    id: str
    type: TraceEventType
    stage: str
    summary: str
    related_evidence_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, JsonValue] = Field(default_factory=dict)
