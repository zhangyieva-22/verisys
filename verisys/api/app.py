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
from verisys.understanding import DiagramEnrichment, UnderstandingResult, enrich_diagram, understand_repository
from verisys.understanding.contracts import INPUT_VERSION as UNDERSTANDING_INPUT_VERSION, PROMPT_VERSION as UNDERSTANDING_PROMPT_VERSION
from verisys.evaluation.catalog import CATALOG_VERSION
from verisys.evaluation.contracts import PROMPT_VERSION as DISCOVERY_PROMPT_VERSION
from verisys.store import ResultStore


class StoredResult(DomainModel):
    """Whether this response reuses a saved result, and when that result was saved."""
    reused: bool
    saved_at: str | None = None


def result_store() -> ResultStore:
    return ResultStore()


def immutable_identity(source) -> dict | None:
    """Only a GitHub source pinned to a full SHA cannot change under a saved result."""
    if isinstance(source, GitHubRepositorySource) and source.ref and re.fullmatch(SHA_PATTERN, source.ref):
        return {"type": "github", "url": source.url, "commit": source.ref}
    return None


def source_identity(source) -> dict:
    return immutable_identity(source) or {"type": "local", "path": str(Path(source.path))}


def reuse(store: ResultStore, kind: str, key: dict, model):
    """A validated saved response, or None on a miss or an invalid file."""
    found = store.get(kind, key)
    if found is None:
        return None
    payload, saved_at = found
    try:
        return model.model_validate({**payload, "stored": {"reused": True, "saved_at": saved_at}})
    except ValidationError:
        return None


def save(store: ResultStore, kind: str, key: dict, response):
    saved_at = store.put(kind, key, response.model_dump(mode="json", exclude={"stored"}))
    response.stored = StoredResult(reused=False, saved_at=saved_at)
    return response


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
    refresh: bool = Field(default=False, strict=True)
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
    result = _analyze(repository)
    return result if isinstance(result, JSONResponse) else result[1]


def _analyze(repository):
    """(discovery, AnalyzeResponse) or a controlled error response."""
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
        return discovery, AnalyzeResponse(
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
    stored: StoredResult | None = None


def can_execute(evaluation_id: str) -> bool:
    definition = CATALOG.get(evaluation_id)
    return bool(definition and definition.verifier_available and get_verifier(evaluation_id) is not None)


def with_capability(response: EvaluationDiscoveryResponse) -> EvaluationDiscoveryResponse:
    """Execution capability is the server's current state, never trusted from a saved result."""
    for candidate in response.candidates:
        candidate.can_execute = can_execute(candidate.id)
    return response


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
                         materializer=Depends(repository_materializer), store: ResultStore = Depends(result_store)):
    source = request.repository_source()
    require_pinned(source)
    # Discovery input is the normalized architecture only, so architecture_id plus the
    # request, model and versions fully determine it, for local and GitHub sources alike.
    def key(architecture_id):
        return {"source": source_identity(source), "architecture_id": architecture_id, "mode": request.mode,
                "request_text": request.request_text, "model": str(client.model), "catalog_version": CATALOG_VERSION,
                "prompt_version": DISCOVERY_PROMPT_VERSION}
    if immutable_identity(source) and not request.refresh:
        saved = reuse(store, "discovery", key(request.expected_architecture_id), EvaluationDiscoveryResponse)
        if saved is not None:
            return with_capability(saved)
    with materializer.materialize(source) as repository:
        result = analyze_root(repository)
        if isinstance(result, JSONResponse):
            return result
        if result.architecture_id != request.expected_architecture_id:
            return error(409, "ANALYSIS_STALE", "The repository changed since the displayed analysis. Analyze the repository again before discovering verifications.")
        if not request.refresh:
            saved = reuse(store, "discovery", key(result.architecture_id), EvaluationDiscoveryResponse)
            if saved is not None:
                return with_capability(saved)
        try:
            discovered = discover_evaluations(result.architecture, client, request_text=request.request_text)
            fields = set(SuggestedVerification.model_fields)
            return save(store, "discovery", key(result.architecture_id), EvaluationDiscoveryResponse(
                candidates=[SuggestedVerification.model_validate({**candidate.model_dump(include=fields),
                                                                  "can_execute": can_execute(candidate.id)})
                            for candidate in discovered.candidates],
                architecture_id=discovered.architecture_id,
                catalog_version=discovered.catalog_version,
                limitations=discovered.limitations, input_truncated=discovered.input_truncated,
            ))
        except DiscoveryError as failure:
            return discovery_error(failure.code)
        except Exception:
            return error(500, "DISCOVERY_FAILED", "Discovery could not be completed. No suggestions were produced.")


@app.exception_handler(DiscoveryError)
async def configuration_error(request: Request, exception: DiscoveryError):
    if request.url.path in OPT_IN_PREFIXES:
        return opt_in_error(exception.code, OPT_IN_PREFIXES[request.url.path])
    return discovery_error(exception.code)


class VerificationRequest(AnalyzeRequest):
    expected_architecture_id: str = Field(pattern=r"^[0-9a-f]{64}$", strict=True)
    evaluation_id: str = Field(min_length=1, max_length=128, strict=True)
    refresh: bool = Field(default=False, strict=True)


class VerificationResponse(VerificationResult):
    stored: StoredResult | None = None


@app.post("/api/evaluations/verify", response_model=VerificationResponse)
def evaluations_verify(request: VerificationRequest, materializer=Depends(repository_materializer),
                       store: ResultStore = Depends(result_store)):
    source = request.repository_source()
    require_pinned(source)
    # Verification reads source bytes that architecture_id does not fully cover, so a saved
    # result is reused only for an immutable pinned commit; local runs are saved, never reused.
    key = {"source": source_identity(source), "architecture_id": request.expected_architecture_id,
           "evaluation_id": request.evaluation_id, "catalog_version": CATALOG_VERSION}
    if immutable_identity(source) and not request.refresh:
        saved = reuse(store, "verification", key, VerificationResponse)
        if saved is not None:
            return saved
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
            return save(store, "verification", key, VerificationResponse(**project_result(run, result.architecture_id).model_dump()))
        except Exception:
            return error(500, "VERIFICATION_FAILED", "The verification tool could not complete. No engineering verdict is available.")


# Understanding is a separate, user-triggered operation: it sends selected, redacted
# source and documentation excerpts to the configured model. Never part of analysis.
class UnderstandingRequest(AnalyzeRequest):
    expected_architecture_id: str = Field(pattern=r"^[0-9a-f]{64}$", strict=True)
    refresh: bool = Field(default=False, strict=True)


class UnderstandingResponse(UnderstandingResult):
    stored: StoredResult | None = None


def understanding_client() -> StructuredGenerationClient:
    """API composition only: process configuration, no implicit dotenv loading."""
    model = (os.getenv("VERISYS_UNDERSTANDING_MODEL", "").strip()
             or os.getenv("VERISYS_DISCOVERY_MODEL", "").strip())
    if not model or not os.getenv("OPENAI_API_KEY", "").strip():
        raise DiscoveryError("configuration_missing")
    try:
        return OpenAIClient(OpenAIConfig(model=model, timeout_seconds=90, max_output_tokens=6000))
    except ValidationError:
        raise DiscoveryError("configuration_invalid") from None


# Opt-in model operations share pinned-source, freshness and error handling.
OPT_IN_PREFIXES = {"/api/understanding": "UNDERSTANDING", "/api/diagram/enrich": "DIAGRAM"}


def opt_in_error(code: str, prefix: str) -> JSONResponse:
    if code.startswith("configuration_"):
        return error(503, f"{prefix}_CONFIGURATION_MISSING", "This feature is unavailable. Configure the backend provider and model.")
    if code == "provider_timeout":
        return error(504, f"{prefix}_PROVIDER_FAILED", "The model provider timed out. No inferred content was produced.")
    if code in {"provider_unavailable", "provider_refusal", "provider_incomplete"}:
        return error(502, f"{prefix}_PROVIDER_FAILED", "The model provider could not complete this request. No inferred content was produced.")
    return error(502, f"{prefix}_VALIDATION_FAILED", "The model response could not be validated. No inferred content was produced.")


def run_opt_in(request: UnderstandingRequest, client, materializer, operation, prefix: str):
    source = request.repository_source()
    require_pinned(source)
    with materializer.materialize(source) as repository:
        analysis = _analyze(repository)
        if isinstance(analysis, JSONResponse):
            return analysis
        discovery, result = analysis
        if result.architecture_id != request.expected_architecture_id:
            return error(409, "ANALYSIS_STALE", "The repository changed since the displayed analysis. Analyze the repository again before continuing.")
        try:
            return operation(discovery, result.architecture, architecture_id=result.architecture_id,
                             repository=result.repository.name, client=client)
        except DiscoveryError as failure:
            return opt_in_error(failure.code, prefix)
        except Exception:
            return error(500, f"{prefix}_FAILED", "This operation could not be completed. No inferred content was produced.")


@app.post("/api/understanding", response_model=UnderstandingResponse)
def understanding(request: UnderstandingRequest, client: StructuredGenerationClient = Depends(understanding_client),
                  materializer=Depends(repository_materializer), store: ResultStore = Depends(result_store)):
    source = request.repository_source()
    require_pinned(source)
    # Excerpts are raw source bytes: reuse only for an immutable pinned commit.
    key = {"source": source_identity(source), "architecture_id": request.expected_architecture_id,
           "model": str(client.model), "prompt_version": UNDERSTANDING_PROMPT_VERSION, "input_version": UNDERSTANDING_INPUT_VERSION}
    if immutable_identity(source) and not request.refresh:
        saved = reuse(store, "understanding", key, UnderstandingResponse)
        if saved is not None:
            return saved
    result = run_opt_in(request, client, materializer, understand_repository, "UNDERSTANDING")
    if isinstance(result, JSONResponse):
        return result
    return save(store, "understanding", key, UnderstandingResponse(**result.model_dump()))


# Detected diagram layers come from the analysis graph; this adds inferred components only.
@app.post("/api/diagram/enrich", response_model=DiagramEnrichment)
def diagram_enrich(request: UnderstandingRequest, client: StructuredGenerationClient = Depends(understanding_client),
                   materializer=Depends(repository_materializer)):
    return run_opt_in(request, client, materializer, enrich_diagram, "DIAGRAM")
