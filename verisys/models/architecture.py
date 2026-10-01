"""Minimal structured architecture state and source references."""
from pydantic import ConfigDict, Field

from .base import DomainModel
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .execution import ExecutionFlow


class SourceLocation(DomainModel):
    """Immutable source reference; paths are not resolved.

    When populated directly from Python AST, line is one-based and column
    is a zero-based UTF-8 byte offset, not a character index.
    """

    model_config = ConfigDict(frozen=True)

    file: str = Field(min_length=1)
    line: int = Field(ge=1)
    column: int | None = Field(default=None, ge=0)


class APIRoute(DomainModel):
    method: str
    path: str
    handler: str
    source_location: SourceLocation


class ExternalService(DomainModel):
    name: str
    client_library: str | None = None
    call_sites: list[SourceLocation] = Field(
        default_factory=list,
        description="Concrete supported external API call expressions; locations a later tool may inspect for timeout behavior.",
    )
    source_locations: list[SourceLocation] = Field(
        default_factory=list,
        description="Locations supporting service presence: imports, client construction, and supported calls. May include call_sites.",
    )


class ArchitectureTool(DomainModel):
    """Explicitly decorated function presence, not tool execution."""
    name: str
    handler: str
    module: str
    source_location: SourceLocation


class Datastore(DomainModel):
    """Source-declared storage usage, not a running database or measured state."""
    name: str
    engine: str
    source_locations: list[SourceLocation] = Field(default_factory=list)


class Dependency(DomainModel):
    source_component: str
    target_component: str
    dependency_type: str
    source_location: SourceLocation | None = None
    evidence_ids: list[str] = Field(default_factory=list)


class ArchitectureIR(DomainModel):
    repository_root: str
    languages: list[str] = Field(default_factory=list)
    frameworks: list[str] = Field(default_factory=list)
    api_routes: list[APIRoute] = Field(default_factory=list)
    external_services: list[ExternalService] = Field(default_factory=list)
    tools: list[ArchitectureTool] = Field(default_factory=list)
    datastores: list[Datastore] = Field(default_factory=list)
    execution_flows: list["ExecutionFlow"] = Field(default_factory=list)
    dependencies: list[Dependency] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)

# Resolve the execution model after SourceLocation is defined.
from .execution import ExecutionFlow
ArchitectureIR.model_rebuild()
