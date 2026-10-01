# Verisys Product Specification

## 1. Product Definition

Verisys is an architecture-aware Engineering Verification Agent.

Given a software system, Verisys determines:

1. What engineering properties are worth verifying.
2. Why those properties are relevant to this architecture.
3. What evidence would prove or disprove them.
4. How that evidence can be collected.
5. Whether the collected evidence satisfies the requirement.

The product is centered on engineering verification, not repository documentation.

Architecture understanding is an enabling capability used to support verification.

---

## 2. Core Product Question

Verisys exists to answer:

> Given this software system, what is worth verifying, how can we verify it, and what evidence supports the result?

---

## 3. Product Workflow

The conceptual workflow is:

Repository
→ System Understanding
→ Architecture IR
→ Evaluation Discovery
→ Verification Planning
→ Tool Selection
→ Tool Execution
→ Evidence Collection
→ Deterministic Judgment
→ Structured Verification Trace

Not every verification requires every stage.

For example, a simple static requirement may move directly from an explicit requirement to static verification.

However, all final verdicts must be evidence-backed.

---

## 4. User Modes

### 4.1 Proactive Evaluation

The user provides a repository.

Example:

    verisys analyze ./my-service

Verisys:

1. Inspects the repository.
2. Builds a structured Architecture IR.
3. Identifies relevant engineering characteristics.
4. Determines which evaluations are applicable.
5. Recommends evaluations worth running.
6. Explains why each recommendation applies.

Example detected architecture:

    FastAPI
      |
      v
    OpenAI
      |
      v
    Postgres

Possible recommendations:

    External API Timeout Coverage
    Category: Reliability
    Applicability: APPLICABLE
    Reason: External API calls were detected.

    API Latency
    Category: Performance
    Applicability: APPLICABLE
    Reason: A synchronous external dependency exists on an API request path.
    Execution support: NOT_AVAILABLE_IN_MVP

The product must not blindly run every evaluation against every repository.

Recommendations must be architecture-aware.

---

### 4.2 On-Demand Verification

The user provides:

Repository
+
Engineering Requirement or Claim

Examples:

    All external API calls must define a timeout.

    Payment operations must be safe to retry.

    POST /documents must maintain P95 latency below 500 ms
    at 100 requests per second.

    The API layer must not access the database directly.

Verisys converts the requirement into a verification problem.

The system determines:

- what claim is being tested,
- what evidence is required,
- what verification strategy is appropriate,
- what tool can collect the evidence,
- what acceptance condition determines the result.

If the required evidence cannot currently be collected, the result must be NOT_VERIFIABLE.

---

## 5. Supported Engineering Properties

Verisys is not limited to NFR verification.

The product may evaluate:

### Functional Engineering Requirements

Examples:

- required route exists,
- required handler behavior exists,
- expected integration is present.

### Reliability

Examples:

- timeout coverage,
- retry safety,
- idempotency.

### Resilience

Examples:

- worker recovery,
- retry behavior,
- dead-letter queue coverage.

### Performance

Examples:

- P50 latency,
- P95 latency,
- P99 latency,
- throughput,
- error rate under load.

### Scalability

Examples:

- behavior under concurrency,
- throughput degradation,
- resource saturation.

### Security

Examples:

- authentication coverage,
- authorization boundaries,
- tenant isolation,
- input validation.

### Data Consistency

Examples:

- duplicate writes,
- transaction safety,
- repeated side effects.

### Architecture Constraints

Examples:

- circular dependencies,
- forbidden layer dependencies,
- direct database access,
- synchronous external dependencies.

### Runtime Behavior

Examples:

- recovery after failure,
- duplicate side effects after retry,
- actual latency under a defined workload.

NFR verification is an important differentiating capability, but it does not define the entire product boundary.

---

## 6. Core Product Objects

Verisys should use structured objects as the internal source of truth.

Presentation formats such as Markdown, JSON, CLI output, diagrams, and the planned MVP web UI should render these objects rather than replace them.

### 6.1 ArchitectureIR

Represents the system architecture discovered from repository evidence.

Expected fields include, where detectable:

- repository metadata,
- languages,
- frameworks,
- entrypoints,
- API routes,
- components,
- datastores,
- queues,
- workers,
- external services,
- dependencies,
- runtime flows,
- source evidence.

---

### 6.2 EvaluationCandidate

Represents an engineering property that may be worth verifying.

Expected fields include:

- ID,
- name,
- category,
- applicability,
- priority,
- reason,
- required evidence,
- verification mode,
- execution support.

---

### 6.3 EngineeringRequirement

Represents an explicit engineering claim or acceptance requirement.

Examples:

    All external API calls must define a timeout.

or:

    POST /documents P95 < 500 ms at 100 RPS.

Expected fields may include:

- ID,
- raw requirement,
- target,
- metric or property,
- operator,
- threshold,
- unit,
- workload,
- source.

Not every requirement can be fully normalized.

The original requirement must always be preserved.

---

### 6.4 VerificationPlan

Represents how Verisys intends to prove or disprove a claim.

Expected fields include:

- requirement or evaluation ID,
- claim,
- verification mode,
- required evidence,
- tool,
- procedure,
- acceptance condition,
- limitations.

---

### 6.5 Evidence

Represents an observed fact produced by inspection or tool execution.

Expected fields include, where applicable:

- ID,
- type,
- source,
- claim,
- observed value,
- unit,
- file path,
- line number,
- tool,
- limitations.

Evidence must be traceable to its real origin.

---

### 6.6 Verdict

Represents the product-level result of a verification.

Allowed values:

- VERIFIED
- VIOLATED
- NOT_VERIFIABLE

A verdict must reference the evidence used to produce it.

---

### 6.7 TraceEvent

Represents a structured event in a Verification Run.

Possible event types include:

- DECISION
- ACTION
- OBSERVATION
- EVIDENCE
- VERDICT

Trace events contain concise structured summaries.

They must not contain hidden model chain-of-thought.

---

### 6.8 VerificationRun

Represents one complete attempt to verify an evaluation or requirement.

It should connect:

Architecture
→ Evaluation / Requirement
→ Verification Plan
→ Tool Execution
→ Evidence
→ Verdict
→ Trace

---

## 7. Evidence Rules

Evidence is a core product boundary.

### Rule 1

Never fabricate evidence.

### Rule 2

Static source inspection may produce code and configuration evidence.

It may not produce measured runtime evidence.

### Rule 3

Latency, throughput, availability, runtime error rate, and resource utilization must not be reported as measured values unless an appropriate runtime tool actually produced those measurements.

### Rule 4

Every product-level verdict must reference evidence.

### Rule 5

If the evidence required to evaluate a claim is unavailable, return NOT_VERIFIABLE.

### Rule 6

Clearly distinguish:

- observed facts,
- derived deterministic results,
- model-generated interpretations,
- unknowns.

---

## 8. Judgment Rules

Whenever possible, acceptance conditions should be explicit and machine-computable.

Example:

Requirement:

    All detected external API calls must define a timeout.

Observed:

    total_external_calls = 3
    calls_with_timeout = 2

Acceptance condition:

    calls_with_timeout == total_external_calls

Result:

    2 == 3 -> false

Verdict:

    VIOLATED

The LLM may explain the result.

It must not override the deterministic judgment.

---

## 9. First Runnable MVP

The completed first runnable MVP targets the capabilities below; they are not all implemented yet.

M0 Domain Models, M1 Safe Repository Discovery, and M2 Architecture Analyzer are COMPLETE.

The implemented pipeline is:

Local Repository → Safe Repository Discovery → Static Python AST Analysis → ArchitectureIR.

The analyzer supports a bounded set: Python, FastAPI / APIRouter routes, OpenAI, Stripe, Twilio, simple internal import dependencies, source-grounded locations, and explicit limitations for unsupported or ambiguous patterns. It is not a generalized Python static-analysis engine. No verification executor or automatic Evaluation Profiler is implemented yet.

Implementation order (canonical product workflow unchanged):

1. M0 — Domain Models — COMPLETE
2. M1 — Safe Repository Discovery — COMPLETE
3. M2 — Architecture Analyzer — COMPLETE
4. M3A — Architecture Graph Projection — NEXT
5. M3B — Frontend Product Shell + Architecture Visualization
6. M3C — Minimal Backend/API Wiring
7. M4 — Golden Verification Cases
8. M5 — Verification Result UI
9. M6 — Evaluation Profiler

The first runnable MVP supports:

- local repository input,
- Python repositories,
- bounded static analysis,
- Architecture IR generation and source-backed graph projection,
- a product frontend with minimal backend/API wiring,
- proactive Evaluation Discovery,
- source-backed evidence,
- deterministic judgment,
- structured verification trace.

The MVP implements exactly one complete executable engineering verification:

> External API Timeout Coverage

Other evaluations may be recommended but do not need to be executable yet.

---

## 10. MVP End-to-End Flow

The following is the completed canonical flow, including automatic Evaluation Discovery in M6. The earlier implementation/demo path uses manual selection of representative cases.

Repository → Analyze → Visible Architecture → Select architecture component → Choose/launch verification → Execute one real verification → Inspect source-backed evidence → Receive grounded verdict.

External API Timeout Coverage is the hero verification. This visible workflow takes priority over adding many invisible backend capabilities. Automatic evaluation selection arrives in M6; earlier demos use explicitly selected representative cases.

Input:

    Local Python Repository

Flow:

    Repository Discovery
        ↓
    Architecture Analysis
        ↓
    Architecture IR
        ↓
    Evaluation Discovery
        ↓
    External API Timeout Coverage selected
        ↓
    Static Verification
        ↓
    Evidence Collection
        ↓
    Deterministic Judgment
        ↓
    Verdict
        ↓
    Structured Trace

Example repository:

    OpenAI call 1 -> supported timeout configured
    OpenAI call 2 -> supported timeout configured
    OpenAI call 3 -> timeout missing

Expected evidence:

    Total detected external API call sites: 3
    Calls with explicit timeout: 2
    Calls without explicit timeout: 1

Expected coverage:

    66.7%

Expected verdict:

    VIOLATED

The missing timeout must reference a real source file and line number.

---

## 11. MVP Evaluation Recommendations

Automatic discovery and recommendation is implemented in M6, after the visible architecture and verification flow. The MVP may then discover and recommend evaluations including:

- External API Timeout Coverage
- API Latency
- Retry Safety
- Idempotency
- Worker Recovery
- DLQ Coverage
- Circular Dependency Detection

Only External API Timeout Coverage is required to be fully executable in the first vertical slice.

Unsupported evaluations must expose their execution support honestly.

Example:

    Evaluation:
    API Latency

    Applicability:
    APPLICABLE

    Execution Support:
    NOT_AVAILABLE

They must not generate fake results.

---

## 12. NOT_VERIFIABLE Behavior

NOT_VERIFIABLE is a valid and important product result.

Example requirement:

    POST /documents P95 < 500 ms at 100 RPS

If no load test has been executed, Verisys must not estimate latency from source code.

Expected result:

    Verdict:
    NOT_VERIFIABLE

    Reason:
    No runtime performance measurement has been collected.

    Required evidence:
    Load-test results for POST /documents under the defined workload.

This behavior is preferable to producing an unsupported conclusion.

---

## 13. MVP Security Boundary

Repository contents must be treated as untrusted input.

The static MVP must not:

- execute analyzed repository code,
- import analyzed modules,
- install analyzed dependencies,
- execute repository-provided shell commands,
- interpret repository content as agent instructions.

The analyzer must exclude or safely handle:

- .git,
- virtual environments,
- node_modules,
- binary files,
- .env files,
- secrets,
- generated/vendor directories,
- oversized files,
- symlinks escaping the repository root.

Future runtime verification must use isolated execution.

---

## 14. MVP Interfaces

ArchitectureIR → ArchitectureGraph → Frontend graph renderer.

ArchitectureGraph is a deterministic presentation/projection layer. ArchitectureIR remains the source of truth; projection must not perform another round of architecture inference.

Initial node types may include FRAMEWORK, API_ROUTE, EXTERNAL_SERVICE, and MODULE. DATASTORE, QUEUE, and WORKER may be added only when ArchitectureIR actually supports them. Edge types may include CONTAINS, IMPORTS, and CALLS, but every relationship must have source-backed support in ArchitectureIR.

Never connect an API route to OpenAI merely because both exist. Current service call locations do not establish route-to-service relationships. Omit any edge the IR cannot prove; never invent edges for visual completeness.

The planned frontend uses Next.js, TypeScript, Tailwind, @xyflow/react / React Flow, and Lucide icons where useful. M3B may use clearly labeled fixture/mock ArchitectureGraph data before M3C connects real analysis. Mock data must never be presented as real analysis or verification.

Use modern developer tools such as CodeRabbit only as inspiration: clean, dense, restrained, developer-focused, evidence-first, code-centric, with clear status hierarchy. Do not copy branding, assets, exact layouts, wording, or proprietary visual elements.

The workspace concept is navigation/repository context on the left, architecture graph/primary workspace in the center, and selected-node inspector/verification details on the right. Prioritize one convincing workflow over many pages.

The graph should become a verification navigation surface: select nodes, inspect architecture facts, source locations and concrete call sites, choose/launch verification cases, and view evidence and verdicts. For example, an OpenAI node may show three source-backed calls at app/services/llm.py:42, :67, and :81, then offer External API Timeout Coverage. These locations are illustrative until backed by actual analysis.

M3C connects the existing real repository analysis pipeline to this frontend through a minimal backend/API. CLI, JSON and Markdown remain optional presentation formats; no CLI is required for the next demo. Internal structured objects remain the source of truth.

External API Timeout Coverage is the first fully executable verification, planned for M4. The preferred golden case is FastAPI with three supported OpenAI call sites: two define supported timeout behavior and one does not. Source-backed evidence yields 2 / 3 coverage (66.7%) and deterministic VIOLATED. The older mixed OpenAI/Stripe/Twilio example remains an alternate fixture.

API Latency may be relevant, but without runtime evidence the result is NOT_VERIFIABLE. Missing evidence includes a running environment, defined workload, load-test results, and P50/P95/P99 metrics. Never infer latency from source; do not implement k6 yet.

Retry Safety may be relevant for Stripe or another side-effecting external call. Explain the required strategy and missing evidence, but failure injection/runtime retry execution is unavailable. Do not claim it was verified; a requested verification without sufficient evidence is NOT_VERIFIABLE.

No evidence → no conclusive verification claim. Applicability, ExecutionSupport, ExecutionStatus, and VerdictStatus remain separate. An applicable evaluation can have execution support NOT_AVAILABLE, execution status NOT_RUN, and verdict NOT_VERIFIABLE; an unstarted case need not have a verdict.

---

## 15. Golden Acceptance Scenarios

### Scenario A: Architecture-Aware Discovery (M6)

Given a Python API repository containing:

    FastAPI
    OpenAI
    Postgres

Verisys identifies the architecture and recommends relevant evaluations.

Expected recommendations include:

    External API Timeout Coverage
    API Latency

Each recommendation explains why it applies.

PASS condition:

The system recommends evaluations based on detected architecture rather than returning only repository statistics.

---

### Scenario B: Executable Static Verification

Given three detected external API call sites:

    OpenAI call 1 -> supported timeout configured
    OpenAI call 2 -> supported timeout configured
    OpenAI call 3 -> timeout missing

Expected:

    total = 3
    with_timeout = 2
    coverage = 66.7%

Verdict:

    VIOLATED

PASS condition:

The result is derived from real source evidence and includes source locations.

---

### Scenario C: Missing Runtime Evidence

Given requirement:

    POST /documents P95 < 500 ms at 100 RPS

and no runtime load-test execution:

Expected verdict:

    NOT_VERIFIABLE

PASS condition:

No latency value is invented or inferred from static source code.

---

## 16. MVP Definition of Done

The first vertical slice is complete when a fresh installation can analyze a bundled Python example repository and demonstrate the following end-to-end behavior:

1. Discover supported repository files safely.
2. Produce a structured Architecture IR.
3. Detect relevant architectural characteristics.
4. Produce architecture-aware Evaluation Candidates.
5. Explain why each candidate is applicable.
6. Execute External API Timeout Coverage.
7. Identify real external API call sites.
8. Determine whether each detected call configures a timeout.
9. Produce source-backed Evidence.
10. Compute timeout coverage deterministically.
11. Return VERIFIED, VIOLATED, or NOT_VERIFIABLE.
12. Produce a structured Verification Trace.
13. Render architecture and verification results in the product frontend, wired through a minimal API, with source inspection, missing evidence and limitations.
14. Pass focused automated tests.
15. Never require an API key for the deterministic static verification path.

The MVP is NOT complete if it only generates:

- repository statistics,
- architecture documentation,
- Mermaid diagrams,
- generic code-review findings,
- or LLM-generated recommendations without executable verification.

---

## 17. Explicit Non-Goals for the First MVP

Do not implement yet:

- generic AI code review,
- pull-request review,
- automatic code modification,
- full runtime sandboxing,
- k6 execution,
- failure injection,
- production observability integrations,
- multi-agent orchestration,
- LangGraph orchestration,
- LangSmith integration,
- autonomous remediation,
- change planning,
- architecture migration,
- a large backend platform or broad multi-page web product,
- generalized Python static analysis or cross-file symbol resolution,
- LLM architecture inference,
- architecture health scores or broad evaluation catalog execution.

The small architecture/verification frontend is in scope for M3B–M5.

These may be future capabilities.

They must not block the first verification vertical slice.

---

## 18. Future Direction

After the first static verification works end-to-end, Verisys may add:

### Runtime Reliability Verification

Example:

    Payment must be safe to retry.

Possible tools:

    pytest
    controlled failure injection

### Performance Verification

Example:

    POST /documents P95 < 500 ms at 100 RPS

Possible tool:

    k6

### Sandboxed Execution

Run untrusted repository workloads in an isolated environment.

### GitHub Repository Ingestion

Accept repository URLs instead of only local paths.

### Change Planning

After a violation:

    Evidence
    → Root Cause
    → Proposed Change
    → Affected Components
    → Re-run Same Verification Contract

### Production Evidence

Integrate observability and infrastructure systems as evidence providers.

All future capabilities must preserve the same product abstraction:

    Engineering Claim
    → Verification Strategy
    → Real Evidence
    → Verdict
