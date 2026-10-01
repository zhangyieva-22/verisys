"""Frontend-neutral architecture projection models; no verification state."""

from enum import StrEnum

from pydantic import Field, JsonValue

from .architecture import SourceLocation
from .base import DomainModel


class ArchitectureNodeType(StrEnum):
    FRAMEWORK = "FRAMEWORK"
    API_ROUTE = "API_ROUTE"
    EXTERNAL_SERVICE = "EXTERNAL_SERVICE"
    MODULE = "MODULE"


class ArchitectureEdgeType(StrEnum):
    CONTAINS = "CONTAINS"
    IMPORTS = "IMPORTS"
    CALLS = "CALLS"


class ArchitectureNode(DomainModel):
    id: str
    type: ArchitectureNodeType
    label: str
    subtitle: str | None = None
    source_locations: list[SourceLocation] = Field(default_factory=list)
    metadata: dict[str, JsonValue] = Field(default_factory=dict)


class ArchitectureEdge(DomainModel):
    id: str
    source: str
    target: str
    type: ArchitectureEdgeType
    source_locations: list[SourceLocation] = Field(default_factory=list)


class ArchitectureGraph(DomainModel):
    nodes: list[ArchitectureNode] = Field(default_factory=list)
    edges: list[ArchitectureEdge] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
