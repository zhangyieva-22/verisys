# Verisys Architecture

## 1. Architecture Goal

Verisys is an architecture-aware Engineering Verification Agent.

The architecture must support this product flow:

Repository
→ System Understanding
→ Architecture IR
→ Evaluation Discovery
→ Verification Planning
→ Tool Execution
→ Evidence Collection
→ Deterministic Judgment
→ Structured Verification Trace

The implementation must preserve a strict separation between:

1. understanding the system,
2. deciding what is worth verifying,
3. deciding how to verify it,
4. executing tools,
5. collecting evidence,
6. judging evidence,
7. presenting results.

Repository analysis is not the final product.
It exists to support engineering verification.

---

## 2. Architectural Principles

### 2.1 Structured state over prose

Core stages must exchange typed structured objects.

Do not use Markdown, free-form LLM text, or architecture diagrams as internal system state.

Primary domain objects:

- ArchitectureIR
- EvaluationCandidate
- EngineeringRequirement
- VerificationPlan
- Evidence
- Verdict
- TraceEvent
- VerificationRun

Markdown, JSON, CLI output, Mermaid diagrams, and the planned MVP UI are renderers over these objects.

---

### 2.2 Reasoning is separate from execution

Reasoning components may decide:

- what an architecture contains,
- which evaluations are relevant,
- how a requirement should be verified,
- which tool is appropriate.

Execution components perform bounded engineering operations.

A reasoning component must never fabricate a tool result.

---

### 2.3 Evidence is separate from judgment

Tools produce evidence.

The Judge consumes:

- requirement or evaluation,
- acceptance condition,
- evidence.

The Judge produces the verdict.

When the acceptance condition is computable, judgment must be deterministic.

---

### 2.4 Missing evidence is explicit

If required evidence cannot be collected:

Verdict:

NOT_VERIFIABLE

The system must never fill missing runtime evidence using source-code inference or model speculation.

---

### 2.5 One orchestrator

The MVP should use one bounded orchestration pipeline.

Do not create multiple autonomous agents that communicate with each other.

Normal Python control flow is preferred for the first vertical slice.

---

## 3. High-Level Architecture

Long-term conceptual architecture, not current implementation status or milestone order:

    Repository / Requirement
             |
             v
    +----------------------+
    |     Orchestrator     |
    +----------------------+
             |
             v
    +----------------------+
    | Repository Ingestion |
    +----------------------+
             |
             v
    +----------------------+
    | Architecture Analyzer|
    +----------------------+
             |
             v
       ArchitectureIR
             |
       +-----+------+
       |            |
       v            v
    Evaluation   Requirement
     Profiler     Compiler
       |            |
       +-----+------+
             |
             v
    Verification Planner
             |
             v
       VerificationPlan
             |
             v
        Tool Executor
             |
       +-----+-------------------+
       |             |           |
       v             v           v
     Static        Runtime   Performance
     Tools          Tools       Tools
       |             |           |
       +-------------+-----------+
                     |
                     v
                  Evidence
                     |
                     v
           Deterministic Judge
                     |
                     v
                  Verdict
                     |
                     v
            Verification Trace
                     |
                     v
             Output Renderer

Only the static verification path is required in the first MVP.

Runtime and performance executors are future extension points.

---

## 4. Orchestrator

This describes the target verification lifecycle, not an implemented M2 component. Automatic profiling is added in M4.5; earlier representative cases use explicit selection.

The Orchestrator owns the lifecycle of a VerificationRun.

Responsibilities:

1. Validate input.
2. Invoke repository discovery.
3. Build ArchitectureIR.
4. Invoke Evaluation Profiler.
5. Accept either:
   - a proactively discovered evaluation, or
   - an explicit EngineeringRequirement.
6. Request a VerificationPlan.
7. Check whether execution support exists.
8. Execute the selected tool when supported.
9. Collect Evidence.
10. Invoke the Judge.
11. Record TraceEvents.
12. Return structured results.

The Orchestrator must not contain tool-specific parsing logic.

It coordinates modules but does not replace them.

For the first MVP, this may be implemented with normal Python functions/classes.

Do not add LangGraph solely for orchestration.

---

## 5. Repository Ingestion

### Purpose

Safely discover repository content that may be analyzed.

### MVP input

Local filesystem path.

### Future input

GitHub repository URL.

### Responsibilities

- validate repository root,
- enumerate supported files,
- enforce exclusions,
- enforce file-size limits,
- enforce total-file/input limits,
- prevent path traversal,
- prevent external symlink traversal,
- record skipped files and reasons.

### MVP supported language

Python.

### Exclusions

At minimum:

- .git
- .env
- virtual environments
- node_modules
- binary files
- generated artifacts
- vendor directories where appropriate
- oversized files
- secrets where identifiable

Repository content must always be treated as untrusted data.

Repository ingestion must not execute source code. Completed discovery skips all child symlinks and stores effective DiscoveryLimits. Analysis reuses those limits by default; explicit analyzer overrides can only tighten them. Safe reads revalidate containment, regular-file status and size, and constrain ingestion by remaining aggregate budget. OS errors use sanitized reason categories; filesystem races remain a documented limitation.

---

## 6. Architecture Analyzer

### Purpose

Convert repository evidence into a structured ArchitectureIR.

The goal is not to write an architecture essay.

The goal is to create machine-readable system understanding that downstream verification can consume.

### Completed M2 detection scope

M0 Domain Models, M1 Safe Repository Discovery, and M2 Architecture Analyzer are COMPLETE.

The implemented pipeline is:

Local Repository → Safe Repository Discovery → Static Python AST Analysis → ArchitectureIR.

The analyzer supports a bounded set: Python, FastAPI / APIRouter routes, OpenAI, Stripe, Twilio, simple internal import dependencies, source-grounded locations, and explicit limitations for unsupported or ambiguous patterns. It is not a generalized Python static-analysis engine. M4 Core now provides explicit static OpenAI timeout verification. M4.5 Core adds catalog-bounded LLM evaluation discovery independently of the frontend and HTTP API.

Broader future detection targets, only when actually supported:

- Python modules
- imports
- functions
- classes
- FastAPI application
- FastAPI routes
- internal dependencies
- external client usage
- known external services
- datastore indicators
- queue/worker indicators

### Evidence requirement

Important detected architecture elements should reference source evidence.

Example:

    ExternalService:
      name: OpenAI
      source:
        file: app/services/llm.py
        line: 18

---

## 7. ArchitectureIR

ArchitectureIR is the structured representation of the analyzed software system.

Long-term conceptual schema, not a claim that M2 extracts every listed concept:

    ArchitectureIR
      repository
      languages[]
      frameworks[]
      entrypoints[]
      components[]
      datastores[]
      queues[]
      workers[]
      external_services[]
      dependencies[]
      runtime_flows[]
      evidence_ids[]
      limitations[]

### EntryPoint

May include:

    type
    method
    path
    handler
    source_location

Example:

    type: HTTP
    method: POST
    path: /documents
    handler: create_document
    source_location:
      file: app/api/documents.py
      line: 42

### ExternalService

Current fields include:

    name
    client_library
    call_sites[]
    source_locations[]

source_locations supports observed service presence and may include imports, client construction and supported calls. call_sites contains concrete supported external API call expressions: these are the locations a later timeout verification tool may inspect. Neither field implies timeout coverage or route-to-service relationships.

### Dependency

May include:

    source_component
    target_component
    dependency_type
    evidence_ids[]

ArchitectureIR must distinguish observed architecture from inferred architecture.

---

## 8. Evaluation Profiler

### Purpose

Determine which engineering evaluations are relevant to the detected architecture.

Core question:

> Given this architecture, what is worth verifying?

The profiler consumes:

ArchitectureIR

and produces:

EvaluationCandidate[]

### Important behavior

The profiler must not select every known evaluation.

Selection must depend on architecture characteristics.

Examples:

If external API calls exist:

    External API Timeout Coverage
    -> potentially applicable

If synchronous external calls occur on HTTP request paths:

    API Latency
    -> potentially applicable

If a queue and worker are detected:

    Worker Recovery
    -> potentially applicable

If a retryable worker performs an external side effect:

    Retry Safety
    Idempotency
    -> potentially applicable

If no worker exists:

    Worker Recovery
    -> NOT_APPLICABLE

### MVP implementation

Implemented independently in M4.5 Core after the stable M4 checkpoint. ArchitectureIR → bounded normalized summary → minimal LLM selection → deterministic validation → EvaluationCandidate[]. No HTTP or frontend discovery integration is included.

Applicability, execution support, priority, rationale validation and candidate construction use deterministic rules.

M4.5 uses an optional LLM only for grounded catalog selection. Server validation and candidate fields remain deterministic; fake clients cover routine tests without credentials.

---

## 9. EvaluationCandidate

Long-term conceptual schema, not a claim that M2 extracts every listed concept:

    EvaluationCandidate
      id
      name
      category
      applicability
      priority
      reason
      required_evidence[]
      verification_mode
      execution_support
      related_architecture_evidence_ids[]

Applicability:

- APPLICABLE
- NOT_APPLICABLE
- UNKNOWN

Priority may be:

- HIGH
- MEDIUM
- LOW

Priority is used for product presentation and execution ordering.

It is not an overall architecture quality score.

Verification mode may include:

- STATIC
- RUNTIME
- PERFORMANCE
- INFRASTRUCTURE

Execution support should explicitly state whether the current implementation can execute the evaluation.

---

## 10. Requirement Compiler

### Purpose

Convert an explicit user engineering requirement into a structured EngineeringRequirement.

Example input:

    POST /documents P95 < 500 ms at 100 RPS

Possible structured representation:

    property: latency
    metric: p95
    target: POST /documents
    operator: <
    threshold: 500
    unit: ms
    workload:
      rps: 100

Another input:

    Payment operations must be safe to retry.

This may not map to a simple numeric threshold.

The raw requirement must always be preserved.

### MVP status

A general natural-language Requirement Compiler is not required for the first vertical slice.

The architecture must leave a clean boundary for it.

The Timeout Coverage MVP may use a predefined evaluation contract.

---

## 11. Verification Planner

### Purpose

Determine how an evaluation or engineering requirement can be proved or disproved.

Core question:

> What evidence would prove or disprove this claim?

Input:

- ArchitectureIR
- EvaluationCandidate or EngineeringRequirement

Output:

VerificationPlan

### VerificationPlan should define

- claim,
- target,
- verification mode,
- required evidence,
- tool,
- procedure,
- acceptance condition,
- limitations.

### Example: Timeout Coverage

Claim:

    All detected external API call sites define an explicit timeout.

Required evidence:

    all detected external call sites
    timeout configuration for each call site

Tool:

    Python static analyzer

Acceptance condition:

    calls_with_timeout == total_external_calls

Verification mode:

    STATIC

### Example: Future P95 Latency

Claim:

    POST /documents P95 < 500 ms at 100 RPS

Required evidence:

    measured P95 latency
    actual achieved request rate
    error rate
    workload duration

Tool:

    k6

Verification mode:

    PERFORMANCE

If k6 is unavailable or no runnable environment exists:

    NOT_VERIFIABLE

The planner must not substitute static inference for required runtime evidence.

---

## 12. Tool Executor

### Purpose

Execute bounded verification procedures.

Tool execution must be separate from planning and judgment.

Conceptual tool interface:

    ToolInput
        ↓
    Tool
        ↓
    ToolResult
        ↓
    Evidence

Potential future tools:

- AST scanner
- code search
- dependency graph analyzer
- pytest runner
- failure injector
- k6 runner
- database inspector
- infrastructure inspector
- runtime tracer

### MVP tool

External API Timeout Analyzer.

It statically identifies supported external API call sites and determines whether an explicit timeout is configured.

It must not execute repository code.

---

## 13. External API Timeout Analyzer

Implemented in M4 Core as the first fully executable verification; it remains separate from the Architecture Analyzer and evaluation discovery.

This is the first complete verification tool.

### Input

Python repository files and relevant ArchitectureIR context.

### Output

Structured evidence for detected external call sites.

Example:

    [
      {
        service: "OpenAI",
        file: "app/services/llm.py",
        line: 22,
        timeout_present: true
      },
      {
        service: "Stripe",
        file: "app/services/payment.py",
        line: 31,
        timeout_present: true
      },
      {
        service: "Twilio",
        file: "app/services/sms.py",
        line: 17,
        timeout_present: false
      }
    ]

### MVP detection strategy

Use deterministic static analysis.

Prefer Python AST where practical.

Target a small documented set of patterns for the golden demo.

Do not attempt universal detection of every Python HTTP/client library in the first MVP.

### Limitations

The tool must report unsupported or ambiguous call patterns.

It must not silently classify uncertain cases as safe.

---

## 14. Evidence

Evidence is immutable observed information used to support a verification result.

Conceptual schema:

    Evidence
      id
      type
      source
      claim
      observed_value
      unit
      source_location
      tool
      limitations
      metadata

Evidence types may include:

- CODE
- CONFIG
- STATIC_ANALYSIS
- RUNTIME
- TEST_RESULT
- METRIC

### SourceLocation

    file
    line
    column

Every source-based finding should include a SourceLocation whenever possible.

### Runtime invariant

A runtime Evidence object must never be produced unless a runtime tool actually executed.

A metric Evidence object representing latency, throughput, runtime error rate, CPU, or memory must never be synthesized by an LLM.

---

## 15. Deterministic Judge

### Purpose

Compare evidence against an explicit acceptance condition.

Input:

    VerificationPlan
    Evidence[]

Output:

    Verdict

Example:

    total_external_calls = 3
    calls_with_timeout = 2

Acceptance condition:

    calls_with_timeout == total_external_calls

Evaluation:

    2 == 3
    false

Verdict:

    VIOLATED

The Judge should be deterministic when the condition is computable.

The LLM may generate an explanation after judgment.

It must not change the verdict.

---

## 16. Verdict

Conceptual schema:

    Verdict
      status
      requirement_or_evaluation_id
      evidence_ids[]
      expected
      observed
      summary
      limitations[]

Allowed product-level status:

- VERIFIED
- VIOLATED
- NOT_VERIFIABLE

### VERIFIED

Sufficient evidence exists and satisfies the acceptance condition.

### VIOLATED

Sufficient evidence exists and does not satisfy the acceptance condition.

### NOT_VERIFIABLE

The system cannot collect sufficient evidence to evaluate the claim.

This is different from tool execution failure and different from NOT_APPLICABLE.

---

## 17. Structured Verification Trace

Every VerificationRun should produce TraceEvents.

Conceptual schema:

    TraceEvent
      id
      timestamp
      type
      stage
      summary
      related_evidence_ids[]
      metadata

Types:

- DECISION
- ACTION
- OBSERVATION
- EVIDENCE
- VERDICT

Example:

    DECISION
    External API dependencies detected.

    DECISION
    Timeout Coverage is applicable.

    ACTION
    Run static timeout analyzer.

    OBSERVATION
    Three external call sites detected.

    EVIDENCE
    Two contain explicit timeout configuration.

    EVIDENCE
    Twilio call at app/services/sms.py:17
    has no detected timeout.

    VERDICT
    VIOLATED.

Trace must not expose hidden chain-of-thought.

---

## 18. VerificationRun

VerificationRun is the top-level state object for one verification attempt.

Conceptually:

    VerificationRun
      id
      repository
      architecture
      evaluation
      requirement
      plan
      execution_status
      evidence[]
      verdict
      trace[]
      limitations[]

This object should make the entire result auditable.

---

## 19. Presentation Layer

Architecture presentation projects ArchitectureIR; verification presentation renders structured verification state. Neither may create unsupported facts or results.

ArchitectureIR → ArchitectureGraph → Frontend graph renderer.

ArchitectureGraph is a deterministic presentation/projection layer. ArchitectureIR remains the source of truth; projection must not perform another round of architecture inference.

Initial node types may include FRAMEWORK, API_ROUTE, EXTERNAL_SERVICE, and MODULE. DATASTORE, QUEUE, and WORKER may be added only when ArchitectureIR actually supports them. Edge types may include CONTAINS, IMPORTS, and CALLS, but every relationship must have source-backed support in ArchitectureIR.

Never connect an API route to OpenAI merely because both exist. Current service call locations do not establish route-to-service relationships. Omit any edge the IR cannot prove; never invent edges for visual completeness.

The planned frontend uses Next.js, TypeScript, Tailwind, @xyflow/react / React Flow, and Lucide icons where useful. M3B may use clearly labeled fixture/mock ArchitectureGraph data before M3C connects real analysis. Mock data must never be presented as real analysis or verification.

Use modern developer tools such as CodeRabbit only as inspiration: clean, dense, restrained, developer-focused, evidence-first, code-centric, with clear status hierarchy. Do not copy branding, assets, exact layouts, wording, or proprietary visual elements.

The workspace concept is navigation/repository context on the left, architecture graph/primary workspace in the center, and selected-node inspector/verification details on the right. Prioritize one convincing workflow over many pages.

The graph should become a verification navigation surface: select nodes, inspect architecture facts, source locations and concrete call sites, choose/launch verification cases, and view evidence and verdicts. For example, an OpenAI node may show three source-backed calls at app/services/llm.py:42, :67, and :81, then offer External API Timeout Coverage. These locations are illustrative until backed by actual analysis.

M5 displays verification name, separately labeled verdict/applicability/execution support/execution status, concise explanation, evidence, sources, missing evidence, limitations and structured trace where available. Timeout Coverage is the first polished result. CLI, Markdown, JSON and Mermaid remain optional renderers. Change planning is outside this MVP.

---

## 20. First MVP Module Boundaries

Prospective Python boundaries below are not current file inventory or required scaffolding. CLI/reporting are optional; graph projection arrives in M3A, a separate frontend in M3B, and a minimal API adapter in M3C. Verification modules arrive in M4 and evaluation profiling in M4.5.

A reasonable target Python package structure is:

    verisys/
      __init__.py

      cli.py

      models/
        architecture.py
        evaluation.py
        requirement.py
        verification.py
        evidence.py
        trace.py

      repository/
        discovery.py

      architecture/
        analyzer.py
        python_ast.py

      evaluation/
        catalog.py
        profiler.py

      verification/
        planner.py
        judge.py

      tools/
        timeout_analyzer.py

      orchestration/
        runner.py

      reporting/
        markdown.py

The exact filenames may evolve.

The architectural boundaries should remain.

---

## 21. Dependency Direction

Preferred dependency direction:

    models
      ↑
    repository
      ↑
    architecture
      ↑
    evaluation
      ↑
    verification
      ↑
    tools
      ↑
    orchestration
      ↑
    cli / reporting

Shared domain models must not depend on presentation code.

The Judge must not depend on Markdown rendering.

The timeout analyzer must not depend on CLI code.

The Architecture Analyzer must not depend on the Evaluation Profiler.

This keeps stages independently testable.

---

## 22. MVP Execution Path

M0 Domain Models, M1 Safe Repository Discovery, and M2 Architecture Analyzer are COMPLETE.

The implemented pipeline is:

Local Repository → Safe Repository Discovery → Static Python AST Analysis → ArchitectureIR.

The analyzer supports a bounded set: Python, FastAPI / APIRouter routes, OpenAI, Stripe, Twilio, simple internal import dependencies, source-grounded locations, and explicit limitations for unsupported or ambiguous patterns. It is not a generalized Python static-analysis engine. M4 Core now provides explicit static OpenAI timeout verification. M4.5 Core adds catalog-bounded LLM evaluation discovery independently of the frontend and HTTP API.

### Revised implementation order

1. M0 — Domain Models — COMPLETE
2. M1 — Safe Repository Discovery — COMPLETE
3. M2 — Architecture Analyzer — COMPLETE
4. M3A — Architecture Graph Projection — NEXT
5. M3B — Frontend Product Shell + Architecture Visualization
6. M3C — Minimal Backend/API Wiring
7. M4 — Golden Verification Cases
8. M4.5 — LLM Evaluation Discovery Core
9. M5 — Verification Result UI

### Visible analysis wiring (M3C)

Repository → Discovery → Architecture Analyzer → ArchitectureIR → ArchitectureGraph → Frontend. Keep API wiring small and preserve discovery limits, safe-read checks and explicit limitations.

### Preferred verification demo (M4–M5)

Repository → Analyze → Visible Architecture → Select architecture component → Choose/launch verification → Execute one real verification → Inspect source-backed evidence → Receive grounded verdict.

External API Timeout Coverage is the hero verification. This visible workflow takes priority over adding many invisible backend capabilities. M4.5 Core provides optional LLM selection with deterministic validation; current frontend demos still use explicitly selected representative cases.

External API Timeout Coverage is the first fully executable verification, implemented in M4 Core. The preferred golden case is FastAPI with three supported OpenAI call sites: two define supported timeout behavior and one does not. Source-backed evidence yields 2 / 3 coverage (66.7%) and deterministic VIOLATED. The older mixed OpenAI/Stripe/Twilio example remains an alternate fixture.

API Latency may be relevant, but without runtime evidence the result is NOT_VERIFIABLE. Missing evidence includes a running environment, defined workload, load-test results, and P50/P95/P99 metrics. Never infer latency from source; do not implement k6 yet.

Retry Safety may be relevant for Stripe or another side-effecting external call. Explain the required strategy and missing evidence, but failure injection/runtime retry execution is unavailable. Do not claim it was verified; a requested verification without sufficient evidence is NOT_VERIFIABLE.

No evidence → no conclusive verification claim. Applicability, ExecutionSupport, ExecutionStatus, and VerdictStatus remain separate. An applicable evaluation can have execution support NOT_AVAILABLE, execution status NOT_RUN, and verdict NOT_VERIFIABLE; an unstarted case need not have a verdict.

### Canonical final flow

Repository → ArchitectureIR → Evaluation Profiler → EvaluationCandidate[] → VerificationPlan → Tool Execution → Evidence → Deterministic Verdict → Structured Trace. The profiler is implemented in M4.5 but remains upstream of verification in the canonical product architecture. Static architecture analysis and explicitly selected M4 verification work without an LLM or API key; optional live M4.5 discovery requires a configured provider.

The revised MVP does not require generalized Python static analysis, generalized cross-file symbol resolution, LLM architecture inference, LangGraph, LangSmith, Docker sandboxing, k6 execution, failure injection, Change Planner, automatic code modification, architecture health scores, broad evaluation catalog execution, or generalized runtime verification.

---

## 23. Future Runtime Architecture

Runtime verification is intentionally outside the first static MVP.

Future architecture may introduce:

    SandboxManager
    RuntimeToolExecutor
    PytestRunner
    FailureInjector
    K6Runner
    ObservabilityProvider

Untrusted code must execute only inside isolation.

Runtime tools must still produce Evidence objects consumed by the same Judge and Trace system.

The core domain model should not need to be replaced.

---

## 24. Non-Goals for the Initial Architecture

Do not introduce:

- multi-agent messaging,
- distributed workflow infrastructure,
- LangGraph,
- LangSmith,
- Celery,
- Kubernetes,
- production databases,
- event buses,
- complex plugin frameworks,
- generalized sandbox execution.

These may become justified later.

The MVP should be a small, deterministic Python application with clean extension boundaries.

---

## 25. Architectural Invariant

Every module should clearly belong to one of these responsibilities:

UNDERSTAND

DISCOVER

PLAN

EXECUTE

OBSERVE

JUDGE

TRACE

PRESENT

If a module mixes several of these responsibilities, reconsider its boundary.

## M2.5 — Bounded Semantic Architecture Detection

This explicitly scoped extension adds exactly three deterministic presence detections:

- Exact `langchain_openai.ChatOpenAI` imports/construction, including aliases,
  reuse ExternalService(name="OpenAI", client_library="langchain_openai").
  SDK and wrapper library identities remain separate. Constructors are presence
  locations, not API call_sites. Wrapper invoke/stream/factory resolution and
  timeout semantics are not implemented.
- Bare `@tool` resolving to `langchain_core.tools.tool` (including aliases)
  produces ArchitectureTool(name, handler, module, source_location). The location
  points to the function definition. Decorator factories are explicitly unsupported.
- An explicitly resolved `sqlite3.connect` expression produces Datastore
  (name="SQLite", engine="sqlite3", source_locations). No database path, tables,
  active connection, or measured storage state is inferred.

Existing scope/rebinding, local-library ambiguity and safe-read rules still apply.
Loops/try/with and other unsupported scopes remain limitations. Discovery-based
collision checks also cover these supported library names, without import resolution.
ArchitectureIR.tools/datastores use isolated default lists. Graph projection adds
TOOL/DATASTORE nodes, with source-backed identities and metadata; new presence
facts create no edges. No LangGraph reconstruction, Langfuse detection, router
prefix composition, generalized decorator/database/call-graph analysis, execution,
verification or M3C wiring is added.

### M2.6 — source-declared execution flows

Architecture components, structural dependencies, and execution flows are three
separate concepts. `ArchitectureIR.execution_flows` and
`ArchitectureGraph.execution_flows` carry `ExecutionFlow` objects; the existing
component nodes and IMPORTS edges remain unchanged. These are architecture facts,
not Verification Evidence, a verification Trace, runtime outcomes, or results.
Each step and transition requires real source locations. Candidate tool IDs
reference component nodes; they represent a candidate set, never execution order
or per-request selection.

The extractor reuses safely read, bounded, parsed ASTs. Its finite grammar supports
an explicitly imported `langgraph.graph.StateGraph`, one named factory with a
simple local graph assignment, literal named node registrations, explicit entry,
`add_edge`, literal `add_conditional_edges` mappings with named condition functions,
and a direct `return graph.compile()`. START is the workflow boundary; END is an
explicit terminal. Unsupported dynamic declarations fail closed. Conditions are
named, not evaluated. Handler identities may use one direct import to an existing,
unambiguous discovered module; no arbitrary call traversal or re-export resolution
is performed.

One direct FastAPI handler assignment invoking an explicitly imported module-level
binding initialized by that proven local factory may establish a request entry.
Its proof retains route declaration, import, invoke, StateGraph import/construction,
factory compile and exported binding locations. A later direct return consuming
that unchanged result can represent the normal handler return after END. Exception
paths and actual successful execution are not established.

Tool candidates support only a directly imported literal tool list/tuple iterated
in the registered handler with an explicit loop-variable `.invoke`. Dynamic tool
names, collection mutation/rebinding and nested function capture are unsupported.
No tools are ordered or chosen by the analyzer. OpenAI helper factories and
business service / SQLite calls are not linked into this flow.

Frontend defaults to System Flow and keeps Dependency View for the original
MODULE + IMPORTS topology. Flow geometry, branching/self-loop presentation and
selection live only in UI adapters. Source-defined conditional labels are retained.
Unproven service/datastore participation is shown under Other detected components,
without invented edges. This remains an offline snapshot; M3C is not implemented.

### M4.5 Core implementation boundary

`verisys/evaluation` contains a pure normalizer, versioned catalog, minimal
selection DTO, strict server validator and optional OpenAI adapter. The existing
ArchitectureIR and ArchitectureGraph semantics and serialization are unchanged.
Normalization reuses graph projection identities, keeps concrete API calls
separate from service presence and includes existing flow steps, transitions,
conditions, candidate tools, source locations and limitations. It creates no
new connections; MODULE presence does not imply execution. No repository root,
raw source/config, results, credentials or UI layout enter the provider input.

Input version is `evaluation-discovery-input-v1`. Lists/subjects are canonicalized
before a SHA-256 hash and generation. Default budgets are 128 subjects, 1024
objects, 512 characters per repository-derived string and 64 KiB canonical UTF-8
JSON including the fixed trusted catalog. Catalog text is static server content,
not governed by the repository-string limit. Whole subjects are omitted when
over budget; IDs are never shortened. Flows with omitted component/tool references
are omitted, too. Truncation is explicit and propagates to candidate limitations;
it never establishes absence. Budgets too small for the fixed envelope fail.

The provider receives trusted instructions separately from structured untrusted
data, an extra-forbidden output schema (maximum four candidates, sixteen subject
references per candidate) and no tools. OpenAI uses the optional current SDK's
`responses.parse(..., text_format=LLMSelections)`. Model configuration is adapter
owned. Missing key/SDK, timeout/API errors, refusal, incomplete output and invalid
schema are controlled failures. Local semantic validation remains mandatory.

DiscoveryResult diagnostics contain bounded provider/model/request identifiers,
versions, input hash, selected IDs, outcome, sanitized failure category, token
counts and provider request latency. This latency is discovery observability,
not a runtime system measurement; no Evidence, Verdict or Trace is created.
Routine tests use fake clients; SDK tests use HTTP mocks; live use is opt-in and
sends only normalized architecture to the configured external provider.
