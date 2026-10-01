"""Local-only analysis API. No persistence, repository imports or execution."""
from pathlib import Path
import os
from typing import Literal

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import Field, ValidationError

from verisys.architecture import analyze_architecture, project_architecture_graph
from verisys.models.architecture import ArchitectureIR
from verisys.models.base import DomainModel
from verisys.models.graph import ArchitectureGraph
from verisys.repository import discover_repository
from verisys.models.enums import Applicability, ExecutionSupport, VerificationMode
from verisys.evaluation import (DiscoveryError, StructuredGenerationClient, OpenAIClient,
                                OpenAIConfig, discover_evaluations, normalize_architecture)


class AnalyzeRequest(DomainModel):
    repository_path: str = Field(min_length=1, max_length=4096, strict=True)


class EvaluationDiscoveryRequest(AnalyzeRequest):
    expected_architecture_id: str = Field(pattern=r"^[0-9a-f]{64}$", strict=True)


class RepositoryIdentity(DomainModel):
    name: str
    path: str


class AnalyzeResponse(DomainModel):
    architecture_id: str
    repository: RepositoryIdentity
    architecture: ArchitectureIR
    graph: ArchitectureGraph


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
    return error(400, "INVALID_REPOSITORY_PATH", "Provide an absolute local repository path.")


@app.exception_handler(Exception)
async def analysis_error(_request: Request, _exception: Exception):
    return error(500, "ANALYSIS_FAILED", "Repository analysis could not be completed.")


@app.post("/api/analyze", response_model=AnalyzeResponse)
def analyze(request: AnalyzeRequest):
    path = Path(request.repository_path)
    if not path.is_absolute() or "\x00" in request.repository_path:
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
        return AnalyzeResponse(
            architecture_id=normalize_architecture(architecture).architecture_id,
            repository=RepositoryIdentity(name=discovery.repository_root.name or "/", path=str(discovery.repository_root)),
            architecture=architecture, graph=graph,
        )
    except Exception:
        return error(500, "ANALYSIS_FAILED", "Repository analysis could not be completed.")


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
def evaluations_discover(request: EvaluationDiscoveryRequest, client: StructuredGenerationClient = Depends(discovery_client)):
    # Browser-authored IR/candidates are rejected by AnalyzeRequest. Reuse authoritative
    # safe analysis, with no caching or new inference layer.
    result = analyze(AnalyzeRequest(repository_path=request.repository_path))
    if isinstance(result, JSONResponse):
        return result
    if result.architecture_id != request.expected_architecture_id:
        return error(409, "ANALYSIS_STALE", "The repository changed since the displayed analysis. Analyze the repository again before discovering verifications.")
    try:
        discovered = discover_evaluations(result.architecture, client)
        fields = set(SuggestedVerification.model_fields)
        return EvaluationDiscoveryResponse(
            candidates=[SuggestedVerification.model_validate(candidate.model_dump(include=fields))
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
