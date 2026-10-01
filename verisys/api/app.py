"""Local-only analysis API. No persistence, repository imports or execution."""
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import Field

from verisys.architecture import analyze_architecture, project_architecture_graph
from verisys.models.architecture import ArchitectureIR
from verisys.models.base import DomainModel
from verisys.models.graph import ArchitectureGraph
from verisys.repository import discover_repository


class AnalyzeRequest(DomainModel):
    repository_path: str = Field(min_length=1, max_length=4096, strict=True)


class RepositoryIdentity(DomainModel):
    name: str
    path: str


class AnalyzeResponse(DomainModel):
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
            repository=RepositoryIdentity(name=discovery.repository_root.name or "/", path=str(discovery.repository_root)),
            architecture=architecture, graph=graph,
        )
    except Exception:
        return error(500, "ANALYSIS_FAILED", "Repository analysis could not be completed.")
