"""Local-only analysis API. No persistence, repository imports or execution."""
from pathlib import Path
import os
from typing import Literal

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import Field, ValidationError, model_validator

from verisys.architecture import analyze_architecture, project_architecture_graph
from verisys.models.architecture import ArchitectureIR
from verisys.models.base import DomainModel
from verisys.models.graph import ArchitectureGraph
from verisys.repository import discover_repository
from verisys.repository.source import RepositorySource, LocalRepositorySource, GitHubRepositorySource, SHA_PATTERN
from verisys.repository.github import RepositoryMaterializer, IntakeError
import re
from verisys.evaluation.catalog import CATALOG
from verisys.verification.registry import get_verifier
from .verification import VerificationResult, project_result
from verisys.models.enums import Applicability, ExecutionSupport, VerificationMode
from verisys.evaluation import (DiscoveryError, StructuredGenerationClient, OpenAIClient,
                                OpenAIConfig, discover_evaluations, normalize_architecture)


class AnalyzeRequest(DomainModel):
    source: RepositorySource | None = None
    # Local-only compatibility for existing development clients. Cannot be combined.
    repository_path: str | None = Field(default=None, min_length=1, max_length=4096, strict=True)

    @model_validator(mode="after")
    def one_source(self):
        if (self.source is None) == (self.repository_path is None):
            raise ValueError("Provide one tagged repository source")
        return self

    def repository_source(self):
        return self.source or LocalRepositorySource(path=self.repository_path)


class EvaluationDiscoveryRequest(AnalyzeRequest):
    expected_architecture_id: str = Field(pattern=r"^[0-9a-f]{64}$", strict=True)
    mode: Literal["PROACTIVE", "ON_DEMAND"] = "PROACTIVE"
    request_text: str | None = Field(default=None, min_length=1, max_length=2000, strict=True)

    @model_validator(mode="after")
    def selection_intent(self):
        if self.mode == "ON_DEMAND" and (not self.request_text or not self.request_text.strip()):
            raise ValueError("On-demand selection requires a bounded request")
        if self.mode == "PROACTIVE" and self.request_text is not None:
            raise ValueError("Proactive selection has no request text")
        return self


class RepositoryIdentity(DomainModel):
    name: str
    path: str | None = None
    source: RepositorySource | None = None
    repository_url: str | None = None
    requested_ref: str | None = None
    resolved_commit_sha: str | None = None


class AnalyzeResponse(DomainModel):
    architecture_id: str
    repository: RepositoryIdentity
    architecture: ArchitectureIR
    graph: ArchitectureGraph


def repository_materializer():
    return RepositoryMaterializer()


def error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}})


app = FastAPI(title="Verisys local analysis", debug=False)


@app.middleware("http")
async def local_browser_boundary(request: Request, call_next):
    # Same-origin Next proxy or trusted local HTTP clients; no wildcard CORS.
    origin = request.headers.get("origin")
    if origin and origin not in {"http://127.0.0.1:3000", "http://localhost:3000"}:
        return error(403, "ORIGIN_NOT_ALLOWED", "This local API does not accept that browser origin.")
    return await call_next(request)


@app.exception_handler(RequestValidationError)
async def invalid_request(_request: Request, _exception: RequestValidationError):
    if _request.url.path == "/api/evaluations/verify":
        return error(400, "VERIFICATION_BAD_REQUEST", "Provide a repository source, evaluation ID and expected architecture ID only.")
    return error(400, "INVALID_REPOSITORY_SOURCE", "Provide a valid repository source and bounded selection request.")


@app.exception_handler(Exception)
async def analysis_error(_request: Request, _exception: Exception):
    return error(500, "ANALYSIS_FAILED", "Repository analysis could not be completed.")


def analyze_root(repository):
    path = repository.root
    if not path.is_absolute() or "\x00" in str(path):
        return error(400, "INVALID_REPOSITORY_PATH", "Provide an absolute local repository path.")
    try:
        discovery = discover_repository(path)
    except FileNotFoundError:
        return error(404, "REPOSITORY_NOT_FOUND", "Repository path does not exist.")
    except NotADirectoryError:
        return error(400, "REPOSITORY_NOT_DIRECTORY", "Repository path must be a directory.")
    except Exception:
        return error(500, "ANALYSIS_FAILED", "Repository analysis could not be completed.")
    try:
        architecture = analyze_architecture(discovery)
        graph = project_architecture_graph(architecture)
        remote = isinstance(repository.source, GitHubRepositorySource)
        return AnalyzeResponse(
            architecture_id=normalize_architecture(architecture).architecture_id,
            repository=RepositoryIdentity(
                name=repository.source.owner_repo if remote else discovery.repository_root.name or "/",
                path=None if remote else str(discovery.repository_root), source=repository.source,
                repository_url=repository.source.url if remote else None,
                requested_ref=repository.requested_ref, resolved_commit_sha=repository.resolved_commit_sha),
            architecture=architecture, graph=graph,
        )
    except Exception:
        return error(500, "ANALYSIS_FAILED", "Repository analysis could not be completed.")


def public_analysis(result, repository):
    if isinstance(result, JSONResponse) or isinstance(repository.source, LocalRepositorySource):
        return result
    # Only architecture root/limitation text may contain the private root. Relative source
    # locations and all architecture semantics stay unchanged; hash excludes root identity.
    root = str(repository.root)
    architecture = result.architecture.model_copy(deep=True)
    architecture.repository_root = repository.source.url
    architecture.limitations = [text.replace(root, "[repository]") for text in architecture.limitations]
    graph = result.graph.model_copy(deep=True)
    graph.limitations = [text.replace(root, "[repository]") for text in graph.limitations]
    return AnalyzeResponse(architecture_id=result.architecture_id, repository=result.repository,
                           architecture=architecture, graph=graph)


@app.exception_handler(IntakeError)
async def remote_error(_request: Request, failure: IntakeError):
    statuses = {"REPOSITORY_NOT_FOUND_OR_PRIVATE": 404, "INVALID_REPOSITORY_REF": 400,
                "PRIVATE_REPOSITORY_UNSUPPORTED": 400, "IMMUTABLE_REVISION_REQUIRED": 400, "GITHUB_RATE_LIMIT": 429,
                "REMOTE_TIMEOUT": 504, "REPOSITORY_TOO_LARGE": 413}
    return error(statuses.get(failure.code, 502), failure.code,
                 "Public GitHub acquisition failed (" + failure.code + "). No repository was analyzed.")


def require_pinned(source):
    if isinstance(source, GitHubRepositorySource) and not (source.ref and re.fullmatch(SHA_PATTERN, source.ref)):
        raise IntakeError("IMMUTABLE_REVISION_REQUIRED")


@app.post("/api/analyze", response_model=AnalyzeResponse)
def analyze(request: AnalyzeRequest, materializer=Depends(repository_materializer)):
    with materializer.materialize(request.repository_source()) as repository:
        return public_analysis(analyze_root(repository), repository)


# Discovery is a separate, user-triggered operation, never part of /api/analyze.
class SuggestedVerification(DomainModel):
    id: str
    name: str
    category: str
    reason: str
    architecture_subject_ids: list[str]
    applicability: Applicability
    priority: Literal["HIGH", "MEDIUM", "LOW"]
    required_evidence: list[str]
    verification_mode: VerificationMode
    execution_support: ExecutionSupport
    limitations: list[str]
    can_execute: bool


class EvaluationDiscoveryResponse(DomainModel):
    candidates: list[SuggestedVerification]
    architecture_id: str
    catalog_version: str
    limitations: list[str]
    input_truncated: bool


def discovery_client() -> StructuredGenerationClient:
    """API composition only: process configuration, no implicit dotenv loading."""
    model = os.getenv("VERISYS_DISCOVERY_MODEL", "").strip()
    if not model or not os.getenv("OPENAI_API_KEY", "").strip():
        raise DiscoveryError("configuration_missing")
    try:
        return OpenAIClient(OpenAIConfig(model=model))
    except ValidationError:
        raise DiscoveryError("configuration_invalid") from None


def discovery_error(code: str) -> JSONResponse:
    if code.startswith("configuration_"):
        return error(503, "DISCOVERY_CONFIGURATION_MISSING", "Discovery is unavailable. Configure the backend provider and model.")
    if code == "provider_timeout":
        return error(504, "DISCOVERY_PROVIDER_FAILED", "The discovery provider timed out. No suggestions were produced.")
    if code in {"provider_unavailable", "provider_refusal", "provider_incomplete"}:
        return error(502, "DISCOVERY_PROVIDER_FAILED", "The discovery provider could not complete this request. No suggestions were produced.")
    return error(502, "DISCOVERY_VALIDATION_FAILED", "Discovery could not validate a grounded selection. No suggestions were produced.")


@app.post("/api/evaluations/discover", response_model=EvaluationDiscoveryResponse)
def evaluations_discover(request: EvaluationDiscoveryRequest, client: StructuredGenerationClient = Depends(discovery_client),
                         materializer=Depends(repository_materializer)):
    source = request.repository_source()
    require_pinned(source)
    with materializer.materialize(source) as repository:
        result = analyze_root(repository)
        if isinstance(result, JSONResponse):
            return result
        if result.architecture_id != request.expected_architecture_id:
            return error(409, "ANALYSIS_STALE", "The repository changed since the displayed analysis. Analyze the repository again before discovering verifications.")
        try:
            discovered = discover_evaluations(result.architecture, client, request_text=request.request_text)
            fields = set(SuggestedVerification.model_fields)
            return EvaluationDiscoveryResponse(
                candidates=[SuggestedVerification.model_validate({**candidate.model_dump(include=fields),
                    "can_execute": bool(CATALOG[candidate.id].verifier_available and get_verifier(candidate.id) is not None)})
                            for candidate in discovered.candidates],
                architecture_id=discovered.architecture_id,
                catalog_version=discovered.catalog_version,
                limitations=discovered.limitations, input_truncated=discovered.input_truncated,
            )
        except DiscoveryError as failure:
            return discovery_error(failure.code)
        except Exception:
            return error(500, "DISCOVERY_FAILED", "Discovery could not be completed. No suggestions were produced.")


@app.exception_handler(DiscoveryError)
async def configuration_error(_request: Request, exception: DiscoveryError):
    return discovery_error(exception.code)


class VerificationRequest(AnalyzeRequest):
    expected_architecture_id: str = Field(pattern=r"^[0-9a-f]{64}$", strict=True)
    evaluation_id: str = Field(min_length=1, max_length=128, strict=True)


@app.post("/api/evaluations/verify", response_model=VerificationResult)
def evaluations_verify(request: VerificationRequest, materializer=Depends(repository_materializer)):
    source = request.repository_source()
    require_pinned(source)
    with materializer.materialize(source) as repository:
        result = analyze_root(repository)
        if isinstance(result, JSONResponse):
            return result
        if result.architecture_id != request.expected_architecture_id:
            return error(409, "ANALYSIS_STALE", "The repository changed. Analyze the repository again before verification.")
        definition = CATALOG.get(request.evaluation_id)
        verifier = get_verifier(request.evaluation_id)
        if definition is None or not definition.verifier_available or verifier is None:
            return error(400, "VERIFICATION_UNSUPPORTED", "No installed verifier is available for this evaluation.")
        try:
            run = verifier(repository.root)
            if normalize_architecture(run.architecture).architecture_id != request.expected_architecture_id:
                return error(409, "ANALYSIS_STALE", "The repository changed during verification. Analyze the repository again.")
            return project_result(run, result.architecture_id)
        except Exception:
            return error(500, "VERIFICATION_FAILED", "The verification tool could not complete. No engineering verdict is available.")
