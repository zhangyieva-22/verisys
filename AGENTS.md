# Project: Verisys

## Product identity

Verisys is an architecture-aware Engineering Verification Agent.

Its purpose is NOT merely to:
- review code,
- generate documentation,
- generate architecture diagrams,
- summarize a repository,
- or check NFRs.

Its core purpose is:

Given a software system, determine what is worth verifying, determine how it can be verified, execute the appropriate engineering tools when possible, collect real evidence, and return an evidence-backed verdict.

The core workflow is:

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

Architecture understanding is an enabling layer.
Verification is the product.

---

## Product scope

Verisys may verify:

- Functional engineering requirements
- Non-Functional Requirements (NFRs)
- Reliability requirements
- Resilience requirements
- Performance requirements
- Scalability requirements
- Security requirements
- Data consistency requirements
- Architecture constraints
- Runtime behavior
- Engineering claims

NFR verification is an important differentiating capability and potential moat, but Verisys is NOT an NFR-only checker.

---

## Trigger modes

Verisys supports two primary trigger modes.

### 1. Proactive Evaluation

Input:

Repository

The system must:

1. Understand the repository.
2. Produce a structured Architecture IR.
3. Determine which engineering evaluations are applicable.
4. Recommend evaluations that are worth running.
5. Explain why each evaluation is relevant.

The user should NOT need to know in advance what should be checked.

Example:

Detected architecture:

API
→ SQS
→ Worker
→ Stripe
→ Postgres

Potential recommended evaluations:

- Retry Safety
- Idempotency
- Worker Recovery
- DLQ Coverage
- External API Timeout Coverage

The system must not blindly run every evaluation against every repository.

---

### 2. On-Demand Verification

Input:

Repository
+
Engineering Requirement / Claim

Examples:

- "All external API calls must define a timeout."
- "Payment operations must be safe to retry."
- "POST /documents must maintain P95 latency below 500 ms at 100 RPS."
- "The API layer must not access the database directly."

The system must determine how the requirement can be verified and what evidence would prove or disprove it.

---

## Core principles

### 1. LLMs reason; tools collect evidence

LLMs may:

- classify,
- reason,
- plan,
- select evaluations,
- select verification strategies,
- explain results.

LLMs must NOT fabricate measured evidence.

Real engineering tools must produce measurable evidence.

---

### 2. Evidence before verdict

Every product-level verdict must reference evidence.

Evidence may come from:

- source code,
- configuration,
- static analysis,
- runtime execution,
- tests,
- performance tools,
- infrastructure inspection,
- observability systems.

If sufficient evidence cannot be collected, the correct result is NOT_VERIFIABLE.

Never replace missing evidence with an LLM guess.

---

### 3. Deterministic judgment when possible

When an acceptance condition can be computed from evidence, the final verdict must be deterministic.

Example:

Requirement:

P95 latency < 500 ms

Measured evidence:

P95 latency = 821 ms

Judgment:

821 < 500 = false

Verdict:

VIOLATED

The LLM must not override this result.

---

## Product-level verdicts

Every completed verification must result in exactly one of:

- VERIFIED
- VIOLATED
- NOT_VERIFIABLE

These are product-level verdicts.

Execution status is separate and may include states such as:

- PENDING
- RUNNING
- COMPLETED
- FAILED
- NOT_RUN

Applicability is also separate and may include:

- APPLICABLE
- NOT_APPLICABLE
- UNKNOWN

Do not mix execution status, applicability, and verification verdict.

---

## Architecture IR

Repository analysis must produce a structured, machine-readable Architecture IR.

Architecture analysis is NOT primarily a prose-generation task.

Where detectable, Architecture IR should represent:

- repository metadata
- languages
- frameworks
- entrypoints
- API routes
- components
- services
- datastores
- queues
- workers
- external services
- internal dependencies
- runtime flows
- source evidence

Important architecture claims should reference real source locations whenever possible.

Architecture diagrams and Markdown reports are presentation layers over Architecture IR.

They are not the core product.

---

## Evaluation Discovery

Verisys maintains an Engineering Evaluation Catalog.

An Evaluation Profiler determines which evaluations are applicable to a repository based on Architecture IR.

The core question is:

"Given this system architecture, what is worth verifying?"

Each Evaluation Candidate should contain, where possible:

- category
- name
- applicability
- priority
- reason
- required evidence
- verification mode
- current execution support

Example:

Name:
External API Timeout Coverage

Category:
Reliability

Applicability:
APPLICABLE

Reason:
External API calls were detected.

Verification mode:
STATIC

---

## Verification Planning

Verification Planning is a core product capability.

For an evaluation or explicit engineering requirement, the system should determine:

- the claim being tested,
- the target,
- the required evidence,
- the verification strategy,
- the experiment or analysis to perform,
- the tool required,
- the acceptance condition,
- known limitations.

The core question is:

"What evidence would prove or disprove this engineering claim?"

Example:

Requirement:

"Payment must be safe to retry."

Possible verification plan:

Hypothesis:
Retrying the same logical payment must not create multiple external charges.

Required evidence:
- external payment invocation count
- persisted payment record count

Experiment:
1. Execute payment.
2. Allow the external charge to succeed.
3. Inject a failure before local persistence completes.
4. Retry the operation.
5. Inspect external invocation count.
6. Inspect persisted records.

Acceptance condition:
external_charges <= 1
AND
payment_records <= 1

Verification mode:
RUNTIME

This example describes future runtime capability and must not be simulated by the static MVP.

---

## Tool execution

Tools execute verification procedures.

Tools do not decide product meaning.

Potential tools include:

- repository discovery
- AST analysis
- code search
- dependency graph analysis
- pytest
- failure injection
- k6
- infrastructure inspection
- runtime tracing

The orchestration layer decides which tool to use.

Tool outputs must be captured as structured evidence.

---

## Evidence model

Evidence must be traceable to its actual source.

Evidence types may include:

- CODE
- CONFIG
- STATIC_ANALYSIS
- RUNTIME
- TEST_RESULT
- METRIC

Evidence should contain, where applicable:

- evidence ID
- type
- source
- claim
- observed value
- unit
- file path
- line number
- tool
- limitations

A runtime measurement must never exist unless an actual runtime tool produced it.

Static analysis must never claim measured latency, throughput, availability, or runtime reliability.

---

## Structured verification trace

Every Verification Run must expose a structured trace.

The conceptual trace is:

Decision
→ Action
→ Observation
→ Evidence
→ Verdict

Example:

DECISION
External API calls detected.

DECISION
Timeout Coverage is applicable.

ACTION
Run static timeout verification.

OBSERVATION
Three external call sites detected.

EVIDENCE
Two define timeouts.
One does not.

VERDICT
VIOLATED.

The trace must contain concise, structured decision summaries.

Never expose hidden model chain-of-thought.

---

## First runnable MVP

The completed MVP targets local Python repositories, bounded static inspection, visible architecture, proactive Evaluation Discovery, and one complete executable verification. The canonical product workflow above is unchanged; only implementation/demo sequencing changes.

### Current implementation status

M0 Domain Models, M1 Safe Repository Discovery, and M2 Architecture Analyzer are COMPLETE.

The implemented pipeline is:

Local Repository → Safe Repository Discovery → Static Python AST Analysis → ArchitectureIR.

The analyzer supports a bounded set: Python, FastAPI / APIRouter routes, OpenAI, Stripe, Twilio, simple internal import dependencies, source-grounded locations, and explicit limitations for unsupported or ambiguous patterns. It is not a generalized Python static-analysis engine. No verification executor or automatic Evaluation Profiler is implemented yet.

### Implementation order

1. M0 — Domain Models — COMPLETE
2. M1 — Safe Repository Discovery — COMPLETE
3. M2 — Architecture Analyzer — COMPLETE
4. M3A — Architecture Graph Projection — NEXT
5. M3B — Frontend Product Shell + Architecture Visualization
6. M3C — Minimal Backend/API Wiring
7. M4 — Golden Verification Cases
8. M5 — Verification Result UI
9. M6 — Evaluation Profiler

Evaluation Discovery remains a core capability and differentiator. M6 implements ArchitectureIR → Evaluation Profiler → EvaluationCandidate[] after architecture visibility and representative verification results. It is delayed, not removed.

### Architecture graph and frontend

ArchitectureIR → ArchitectureGraph → Frontend graph renderer.

ArchitectureGraph is a deterministic presentation/projection layer. ArchitectureIR remains the source of truth; projection must not perform another round of architecture inference.

Initial node types may include FRAMEWORK, API_ROUTE, EXTERNAL_SERVICE, and MODULE. DATASTORE, QUEUE, and WORKER may be added only when ArchitectureIR actually supports them. Edge types may include CONTAINS, IMPORTS, and CALLS, but every relationship must have source-backed support in ArchitectureIR.

Never connect an API route to OpenAI merely because both exist. Current service call locations do not establish route-to-service relationships. Omit any edge the IR cannot prove; never invent edges for visual completeness.

The planned frontend uses Next.js, TypeScript, Tailwind, @xyflow/react / React Flow, and Lucide icons where useful. M3B may use clearly labeled fixture/mock ArchitectureGraph data before M3C connects real analysis. Mock data must never be presented as real analysis or verification.

Use modern developer tools such as CodeRabbit only as inspiration: clean, dense, restrained, developer-focused, evidence-first, code-centric, with clear status hierarchy. Do not copy branding, assets, exact layouts, wording, or proprietary visual elements.

The workspace concept is navigation/repository context on the left, architecture graph/primary workspace in the center, and selected-node inspector/verification details on the right. Prioritize one convincing workflow over many pages.

The graph should become a verification navigation surface: select nodes, inspect architecture facts, source locations and concrete call sites, choose/launch verification cases, and view evidence and verdicts. For example, an OpenAI node may show three source-backed calls at app/services/llm.py:42, :67, and :81, then offer External API Timeout Coverage. These locations are illustrative until backed by actual analysis.

### Preferred demo and verification honesty

Repository → Analyze → Visible Architecture → Select architecture component → Choose/launch verification → Execute one real verification → Inspect source-backed evidence → Receive grounded verdict.

External API Timeout Coverage is the hero verification. This visible workflow takes priority over adding many invisible backend capabilities. Automatic evaluation selection arrives in M6; earlier demos use explicitly selected representative cases.

External API Timeout Coverage is the first fully executable verification, planned for M4. The preferred golden case is FastAPI with three supported OpenAI call sites: two define supported timeout behavior and one does not. Source-backed evidence yields 2 / 3 coverage (66.7%) and deterministic VIOLATED. The older mixed OpenAI/Stripe/Twilio example remains an alternate fixture.

API Latency may be relevant, but without runtime evidence the result is NOT_VERIFIABLE. Missing evidence includes a running environment, defined workload, load-test results, and P50/P95/P99 metrics. Never infer latency from source; do not implement k6 yet.

Retry Safety may be relevant for Stripe or another side-effecting external call. Explain the required strategy and missing evidence, but failure injection/runtime retry execution is unavailable. Do not claim it was verified; a requested verification without sufficient evidence is NOT_VERIFIABLE.

No evidence → no conclusive verification claim. Applicability, ExecutionSupport, ExecutionStatus, and VerdictStatus remain separate. An applicable evaluation can have execution support NOT_AVAILABLE, execution status NOT_RUN, and verdict NOT_VERIFIABLE; an unstarted case need not have a verdict.

The revised MVP does not require generalized Python static analysis, generalized cross-file symbol resolution, LLM architecture inference, LangGraph, LangSmith, Docker sandboxing, k6 execution, failure injection, Change Planner, automatic code modification, architecture health scores, broad evaluation catalog execution, or generalized runtime verification.

---

## Additional MVP recommendations

Automatic recommendations are implemented in M6. The system may then recommend evaluations such as:

- API Latency
- Retry Safety
- Idempotency
- Worker Recovery
- DLQ Coverage

These evaluations do NOT need to be executable in the first MVP.

If execution support is unavailable, the system must say so explicitly.

It must never generate simulated results.

For example:

Requirement:

POST /documents P95 < 500 ms at 100 RPS

If no load test was actually executed:

Verdict:

NOT_VERIFIABLE

Reason:

No runtime performance evidence has been collected.

Required evidence:

A load-test result under a defined workload.

---

## Security rules for the first MVP

Treat repository contents as untrusted data.

The initial static MVP must NOT execute analyzed repository code.

It must NOT:

- install analyzed repository dependencies,
- execute imported modules,
- execute shell commands from repository content,
- treat repository text as agent instructions.

Skip:

- secrets,
- .env files,
- binary files,
- virtual environments,
- node_modules,
- .git,
- generated/vendor directories where appropriate.

Do not follow symlinks outside the repository.

Bound:

- file size,
- total files,
- total analyzed input.

Future runtime verification must execute untrusted code only inside an isolated sandbox.

---

## Engineering guidelines

- Read AGENTS.md and docs/ before implementing.
- Report conflicts between implementation requests and product architecture.
- Prefer typed structured models over free-form text.
- Keep reasoning separate from execution.
- Keep tool execution separate from judgment.
- Prefer deterministic code where possible.
- Keep modules small and testable.
- Add focused tests for deterministic components.
- Do not silently change shared schemas.
- Do not add unnecessary infrastructure.
- Do not introduce a multi-agent architecture for the MVP.
- Do not add LangGraph merely for orchestration that normal Python can handle.
- Do not add LangSmith until tracing needs justify it.
- Do not implement features outside the current milestone without explicit approval.
- Optimize for an end-to-end working vertical slice before breadth.

---

## Golden scenarios

These are target acceptance scenarios: automatic recommendations arrive in M6; verification cases arrive in M4. The preferred hero fixture uses three OpenAI calls (two timeouts, one missing); Scenario 2 below is an alternate mixed-service fixture.

### Scenario 1: Proactive evaluation discovery

Detected architecture:

FastAPI
→ OpenAI
→ Postgres

Expected evaluation recommendations include:

- External API Timeout Coverage
- API Latency

The recommendation must explain why each evaluation is relevant.

The output must not merely report repository statistics.

---

### Scenario 2: Static timeout verification

Repository contains three detected external API call sites:

OpenAI:
timeout configured

Stripe:
timeout configured

Twilio:
timeout missing

Expected:

External API Timeout Coverage:
2 / 3

Verdict:
VIOLATED

Evidence:
real file paths and line references.

---

### Scenario 3: Runtime requirement without runtime evidence

Requirement:

POST /documents P95 < 500 ms at 100 RPS

No runtime load test has been executed.

Expected:

NOT_VERIFIABLE

The system must explain that runtime evidence is missing.

It must never estimate or invent latency from static source code.

---

## Future capabilities

After the static vertical slice works end-to-end, future milestones may add:

- GitHub URL ingestion
- Requirement Compiler
- richer Verification Planning
- pytest runtime verification
- failure injection
- k6 performance verification
- sandboxed execution
- trace export
- observability integrations
- change planning
- automatic re-verification

These future capabilities must extend the same core abstractions rather than replace them.

---

## Product invariant

Every implementation decision should support this question:

"Given this software system, what is worth verifying, how can we verify it, and what evidence supports the result?"
