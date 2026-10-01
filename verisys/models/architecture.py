"""Minimal structured architecture state and source references."""
from pydantic import ConfigDict, Field

from .base import DomainModel


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
    dependencies: list[Dependency] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
