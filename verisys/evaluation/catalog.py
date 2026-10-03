"""Five trusted definitions. Selection does not redefine policy or capability."""
from dataclasses import asdict, dataclass
from types import MappingProxyType

CATALOG_VERSION = "engineering-evaluations-v2"


@dataclass(frozen=True)
class EvaluationDefinition:
    id: str
    name: str
    category: str
    property: str
    purpose: str
    allowed_signals: tuple[str, ...]
    rationale_codes: tuple[str, ...]
    required_evidence: tuple[str, ...]
    verification_mode: str
    execution_support_rule: str
    default_priority: str
    limitations: tuple[str, ...]
    verifier_available: bool

    def input_record(self):
        return asdict(self)


_COMMON = "Architecture signals justify investigation; they do not establish a verification result."
DEFINITIONS = (
    EvaluationDefinition("external-api-timeout-coverage-v1", "External API Timeout Coverage", "Reliability",
        "explicit_per_call_timeout_configuration", "Investigate explicit per-call OpenAI timeout configuration.",
        ("EXTERNAL_SERVICE",), ("supported_openai_calls", "openai_wrapper_presence"),
        ("Fresh supported concrete OpenAI call sites", "Per-call static timeout observations"), "STATIC",
        "SUPPORTED for direct openai calls; PARTIAL for presence-only or uncertain scope", "MEDIUM",
        (_COMMON, "Only the existing OpenAI per-call grammar is executable; wrapper behavior and effective runtime timeouts are not established."), True),
    EvaluationDefinition("http-client-timeout-coverage-v1", "HTTP Client Timeout Coverage", "Reliability",
        "finite_http_client_timeout", "Investigate finite timeouts on requests and httpx calls.",
        ("EXTERNAL_SERVICE",), ("supported_http_client_calls", "http_client_presence"),
        ("Fresh supported concrete requests/httpx call sites", "Per-call static timeout observations"), "STATIC",
        "SUPPORTED for direct requests/httpx calls; PARTIAL for presence-only or uncertain scope", "MEDIUM",
        (_COMMON, "Only direct requests/httpx calls are executable; wrappers, adapters and effective runtime timeouts are not established."), True),
    EvaluationDefinition("retry-safety-v1", "Retry Safety", "Reliability", "retry_safety",
        "Investigate safety of repeated workflow actions.", ("EXECUTION_FLOW",), ("source_declared_retry_loop",),
        ("Explicit retry-safety requirement", "Actual side effects and controlled retry experiment"), "RUNTIME",
        "NOT_AVAILABLE", "MEDIUM", (_COMMON, "A possible repeated path does not prove external side effects, actual retries, or safe retry behavior."), False),
    EvaluationDefinition("api-latency-v1", "API Latency", "Performance", "api_latency",
        "Investigate API latency under a defined workload.", ("API_ROUTE",), ("http_api_routes",),
        ("Running environment", "Defined workload and acceptance threshold", "Executed load-test measurements"), "PERFORMANCE",
        "NOT_AVAILABLE", "MEDIUM", (_COMMON, "No latency is inferred from source; no load-test verifier exists."), False),
    EvaluationDefinition("tool-side-effect-safety-v1", "Tool Side-Effect Safety", "Reliability", "tool_side_effect_safety",
        "Investigate side effects of workflow tool candidates.", ("EXECUTION_FLOW", "TOOL"), ("tool_candidates_in_workflow",),
        ("Actual tool side effects", "Explicit safety requirement", "Controlled runtime observations"), "RUNTIME",
        "NOT_AVAILABLE", "MEDIUM", (_COMMON, "Candidate tools do not establish side effects, execution order, or per-request selection."), False),
)
CATALOG = MappingProxyType({entry.id: entry for entry in DEFINITIONS})
