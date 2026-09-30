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

Markdown, JSON, CLI output, Mermaid diagrams, and future UI are renderers over these objects.

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

Conceptually:

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

Repository ingestion must not execute source code.

---

## 6. Architecture Analyzer

### Purpose

Convert repository evidence into a structured ArchitectureIR.

The goal is not to write an architecture essay.

The goal is to create machine-readable system understanding that downstream verification can consume.

### MVP detection targets

Where possible:

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

Suggested conceptual schema:

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

May include:

    name
    client_library
    call_sites[]
    source_evidence[]

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

The first MVP may use deterministic rules.

An LLM is not required.

This is preferred for the first vertical slice because behavior is reproducible and testable.

---

## 9. EvaluationCandidate

Suggested conceptual schema:

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

Presentation is downstream from verification state.

The first MVP may render:

- CLI output
- Markdown report
- JSON output

A future web UI may render:

- architecture summary
- recommended evaluation cards
- verification progress
- evidence
- verdict
- trace
- improvement plan

Mermaid diagrams are optional presentation artifacts.

They must not become a required internal representation.

---

## 20. First MVP Module Boundaries

A reasonable initial Python package structure is:

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

The first implemented vertical slice should be:

    CLI
     ↓
    RepositoryDiscovery
     ↓
    ArchitectureAnalyzer
     ↓
    ArchitectureIR
     ↓
    EvaluationProfiler
     ↓
    TimeoutCoverage EvaluationCandidate
     ↓
    VerificationPlanner
     ↓
    TimeoutAnalyzer
     ↓
    Evidence[]
     ↓
    DeterministicJudge
     ↓
    Verdict
     ↓
    Trace[]
     ↓
    CLI / Markdown Renderer

This entire path must work without an LLM or API key.

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
