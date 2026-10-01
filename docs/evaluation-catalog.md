# Verisys Engineering Evaluation Catalog

## 1. Purpose

The Evaluation Catalog defines engineering properties that Verisys may verify.

The catalog does NOT mean every evaluation should run against every repository.

The Evaluation Profiler uses ArchitectureIR to determine:

- whether an evaluation is applicable,
- why it is applicable,
- what evidence would be required,
- what verification mode is appropriate,
- whether the current Verisys implementation can execute it.

The core question is:

> Given this architecture, which engineering properties are worth verifying?

---

## Current implementation and sequencing

M0 Domain Models, M1 Safe Repository Discovery, and M2 Architecture Analyzer are COMPLETE.

The implemented pipeline is:

Local Repository → Safe Repository Discovery → Static Python AST Analysis → ArchitectureIR.

The analyzer supports a bounded set: Python, FastAPI / APIRouter routes, OpenAI, Stripe, Twilio, simple internal import dependencies, source-grounded locations, and explicit limitations for unsupported or ambiguous patterns. It is not a generalized Python static-analysis engine. No verification executor or automatic Evaluation Profiler is implemented yet.

Catalog execution-support labels below describe the completed MVP target, not tools already available at M2. Timeout Coverage becomes executable in M4. Architecture graph projection (M3A), frontend visualization (M3B), and minimal API wiring (M3C) come first; result UI follows in M5 and automatic Evaluation Profiling in M6.

External API Timeout Coverage is the first fully executable verification, planned for M4. The preferred golden case is FastAPI with three supported OpenAI call sites: two define supported timeout behavior and one does not. Source-backed evidence yields 2 / 3 coverage (66.7%) and deterministic VIOLATED. The older mixed OpenAI/Stripe/Twilio example remains an alternate fixture.

API Latency may be relevant, but without runtime evidence the result is NOT_VERIFIABLE. Missing evidence includes a running environment, defined workload, load-test results, and P50/P95/P99 metrics. Never infer latency from source; do not implement k6 yet.

Retry Safety may be relevant for Stripe or another side-effecting external call. Explain the required strategy and missing evidence, but failure injection/runtime retry execution is unavailable. Do not claim it was verified; a requested verification without sufficient evidence is NOT_VERIFIABLE.

No evidence → no conclusive verification claim. Applicability, ExecutionSupport, ExecutionStatus, and VerdictStatus remain separate. An applicable evaluation can have execution support NOT_AVAILABLE, execution status NOT_RUN, and verdict NOT_VERIFIABLE; an unstarted case need not have a verdict.

Architecture diagrams in catalog examples illustrate relevance scenarios. They do not authorize graph edges: relationships must already have source-backed support in ArchitectureIR.

---

## 2. Evaluation Model

Each catalog entry should conceptually define:

    id
    name
    category
    description
    applicability_conditions
    required_evidence
    verification_mode
    acceptance_condition
    execution_support
    limitations

Verification modes:

- STATIC
- RUNTIME
- PERFORMANCE
- INFRASTRUCTURE

Applicability values:

- APPLICABLE
- NOT_APPLICABLE
- UNKNOWN

Product-level verdicts:

- VERIFIED
- VIOLATED
- NOT_VERIFIABLE

Applicability and execution support must not be confused with verdict.

---

## 3. Reliability

### 3.1 External API Timeout Coverage

Category:

Reliability

Purpose:

Determine whether detected external API call sites define bounded timeout behavior.

Applicability:

Applicable when supported external network/API calls are detected.

Required evidence:

- detected external call sites,
- source locations,
- timeout configuration for each call site.

Verification mode:

STATIC

MVP execution support:

SUPPORTED

MVP acceptance condition:

    calls_with_timeout == total_supported_external_calls

If all supported external calls have a timeout:

    VERIFIED

If at least one supported external call is missing a timeout:

    VIOLATED

If external calls are detected but the analyzer cannot reliably determine timeout behavior:

    NOT_VERIFIABLE for the ambiguous portion or run,
    depending on implementation semantics.

The tool must expose limitations rather than silently treating unknown patterns as safe.

Example:

    OpenAI -> timeout present
    Stripe -> timeout present
    Twilio -> timeout missing

Observed:

    2 / 3

Verdict:

    VIOLATED

---

### 3.2 Retry Safety

Category:

Reliability

Purpose:

Determine whether retrying a logical operation can cause unintended duplicate effects.

Typical applicability:

- retryable workers,
- queue consumers,
- external side effects,
- payment operations,
- email/message sending,
- webhook processing.

Required evidence may include:

- repeated execution of the same logical operation,
- external invocation count,
- persisted record count,
- idempotency behavior.

Verification mode:

RUNTIME

MVP execution support:

NOT_AVAILABLE

Static code may provide signals that Retry Safety is worth evaluating.

Static code alone must not claim that runtime retry behavior is verified.

---

### 3.3 Idempotency

Category:

Reliability

Purpose:

Determine whether repeating the same logical operation produces at most one intended side effect.

Typical applicability:

- payments,
- order creation,
- webhook handlers,
- queue consumers,
- retryable write operations.

Required evidence may include:

- stable operation identity,
- idempotency key behavior,
- duplicate invocation behavior,
- persisted state after retries.

Verification mode:

STATIC and/or RUNTIME depending on the claim.

MVP execution support:

NOT_AVAILABLE

---

## 4. Resilience

### 4.1 Worker Recovery

Category:

Resilience

Purpose:

Determine whether background processing recovers correctly from failures.

Typical applicability:

- queue consumers,
- asynchronous workers,
- scheduled jobs,
- background task systems.

Required evidence may include:

- injected failure,
- worker restart/retry,
- final processing state,
- duplicate side effects,
- lost work.

Verification mode:

RUNTIME

MVP execution support:

NOT_AVAILABLE

---

### 4.2 Retry Behavior

Category:

Resilience

Purpose:

Determine whether retry behavior is bounded and consistent with the intended failure policy.

Potential evidence:

- retry configuration,
- retry count,
- backoff behavior,
- terminal failure behavior.

Verification mode:

STATIC and/or RUNTIME

MVP execution support:

NOT_AVAILABLE

---

### 4.3 Dead-Letter Queue Coverage

Category:

Resilience

Purpose:

Determine whether failed asynchronous messages have a defined terminal failure path.

Typical applicability:

- queue-based architectures,
- retryable workers.

Potential evidence:

- queue configuration,
- retry/redrive configuration,
- DLQ configuration,
- worker failure path.

Verification mode:

INFRASTRUCTURE or STATIC

MVP execution support:

NOT_AVAILABLE

---

## 5. Performance

### 5.1 API Latency

Category:

Performance

Purpose:

Measure request latency under a defined workload.

Metrics may include:

- P50
- P95
- P99

Applicability:

HTTP/API entrypoints.

Required evidence:

- executed workload,
- achieved request rate,
- sample count,
- test duration,
- measured latency distribution,
- error rate.

Verification mode:

PERFORMANCE

MVP execution support:

NOT_AVAILABLE

Example requirement:

    POST /documents P95 < 500 ms at 100 RPS

Without an executed load test:

    NOT_VERIFIABLE

Verisys must never estimate measured latency from source code.

---

### 5.2 Throughput

Category:

Performance / Scalability

Purpose:

Measure completed operations per unit time under a defined workload.

Required evidence:

- executed workload,
- completed request count,
- duration,
- error rate,
- achieved throughput.

Verification mode:

PERFORMANCE

MVP execution support:

NOT_AVAILABLE

---

### 5.3 Error Rate Under Load

Category:

Performance / Reliability

Purpose:

Measure failed operations while the system is under a defined workload.

Required evidence:

- workload definition,
- request count,
- failure count,
- error classification.

Verification mode:

PERFORMANCE

MVP execution support:

NOT_AVAILABLE

---

## 6. Scalability

### 6.1 Concurrent Request Behavior

Category:

Scalability

Purpose:

Determine how the system behaves as concurrency increases.

Potential evidence:

- latency by concurrency level,
- throughput by concurrency level,
- error rate,
- resource saturation.

Verification mode:

PERFORMANCE

MVP execution support:

NOT_AVAILABLE

---

### 6.2 Throughput Degradation

Category:

Scalability

Purpose:

Determine whether throughput or latency degrades beyond an explicit threshold as workload increases.

Verification mode:

PERFORMANCE

MVP execution support:

NOT_AVAILABLE

---

### 6.3 Resource Saturation

Category:

Scalability

Potential metrics:

- CPU
- memory
- connection pool utilization
- queue depth
- worker utilization

Verification mode:

PERFORMANCE / INFRASTRUCTURE

MVP execution support:

NOT_AVAILABLE

No resource measurement may be claimed without actual runtime or infrastructure evidence.

---

## 7. Architecture

### 7.1 Circular Dependencies

Category:

Architecture

Purpose:

Detect cycles in internal dependency relationships.

Required evidence:

- internal dependency graph,
- detected cycle path.

Verification mode:

STATIC

MVP execution support:

OPTIONAL

This may be measured descriptively in the first MVP but should not distract from the required Timeout Coverage vertical slice.

A cycle is not automatically a product-level violation unless an explicit policy or catalog acceptance condition defines it as forbidden.

---

### 7.2 Layer Violations

Category:

Architecture

Purpose:

Verify explicit dependency constraints between architectural layers.

Example requirement:

    API handlers must not import repository implementations directly.

Required evidence:

- declared layer policy,
- dependency graph,
- violating dependency edge.

Verification mode:

STATIC

MVP execution support:

NOT_AVAILABLE

Without an explicit architecture policy, Verisys may identify a pattern but must not invent a team requirement.

---

### 7.3 Direct Database Access

Category:

Architecture

Example requirement:

    API handlers must not access the database directly.

Required evidence:

- API handler locations,
- database access locations,
- dependency relationship.

Verification mode:

STATIC

MVP execution support:

NOT_AVAILABLE

---

### 7.4 Synchronous External Dependency

Category:

Architecture / Performance

Purpose:

Identify external dependencies executed synchronously on request paths.

This is primarily an architectural signal.

It may cause Verisys to recommend:

- API Latency verification,
- timeout verification,
- resilience evaluation.

Detection of a synchronous dependency does NOT prove poor latency.

Verification mode:

STATIC for detection,
PERFORMANCE for latency impact.

MVP execution support:

PARTIAL

---

## 8. Data Consistency

### 8.1 Duplicate Writes

Category:

Data Consistency

Purpose:

Determine whether retries or repeated operations create duplicate persisted records.

Verification mode:

RUNTIME

MVP execution support:

NOT_AVAILABLE

---

### 8.2 Transaction Safety

Category:

Data Consistency

Purpose:

Verify that related writes preserve required consistency when failures occur.

Required evidence depends on the explicit transaction requirement.

Verification mode:

STATIC and/or RUNTIME

MVP execution support:

NOT_AVAILABLE

---

### 8.3 Duplicate External Side Effects

Category:

Data Consistency / Reliability

Purpose:

Determine whether retries can repeat irreversible or externally visible actions.

Examples:

- duplicate payment charge,
- duplicate email,
- duplicate SMS,
- duplicate webhook.

Verification mode:

RUNTIME

MVP execution support:

NOT_AVAILABLE

---

## 9. Security

### 9.1 Authentication Coverage

Category:

Security

Purpose:

Verify that endpoints requiring authentication are protected.

Required evidence:

- explicit security policy or expected protected routes,
- detected routes,
- authentication mechanism.

Verification mode:

STATIC and/or RUNTIME

MVP execution support:

NOT_AVAILABLE

---

### 9.2 Authorization Boundaries

Category:

Security

Purpose:

Verify explicit authorization requirements around protected operations.

Verification mode:

STATIC and/or RUNTIME

MVP execution support:

NOT_AVAILABLE

---

### 9.3 Tenant Isolation

Category:

Security / Data Consistency

Purpose:

Verify that one tenant cannot access another tenant's protected data.

Verification mode:

RUNTIME

MVP execution support:

NOT_AVAILABLE

---

### 9.4 Input Validation

Category:

Security / Reliability

Purpose:

Verify explicit validation requirements for external inputs.

Verification mode:

STATIC and/or RUNTIME

MVP execution support:

NOT_AVAILABLE

---

## 10. Functional Engineering Requirements

Verisys may also verify concrete functional engineering claims.

Examples:

    POST /documents route must exist.

    The document endpoint must enqueue background processing.

    Payment creation must persist an order identifier.

These are not necessarily NFRs.

Verification strategy depends on the claim.

Possible modes:

- STATIC
- RUNTIME

The catalog must remain extensible beyond NFRs.

---

## 11. Evaluation Selection Rules

The Evaluation Profiler, implemented in M6, should use architecture-aware selection. Earlier demos choose representative cases explicitly; automatic recommendations remain a core product capability.

Examples:

### Architecture A

    FastAPI
      |
      v
    OpenAI
      |
      v
    Postgres

Relevant candidates may include:

- External API Timeout Coverage
- API Latency
- Synchronous External Dependency

Not automatically relevant:

- Worker Recovery
- DLQ Coverage

---

### Architecture B

    API
     |
     v
    SQS
     |
     v
    Worker
     |
     +----> Stripe
     |
     v
    Postgres

Relevant candidates may include:

- Retry Safety
- Idempotency
- Worker Recovery
- DLQ Coverage
- External API Timeout Coverage
- Duplicate External Side Effects

---

### Architecture C

    Pure local Python library

Potentially relevant:

- dependency architecture constraints,
- static functional requirements.

Likely not applicable without additional runtime context:

- API Latency,
- DLQ Coverage,
- Worker Recovery.

---

## 12. Standards and Thresholds

Acceptance standards should follow this priority:

### 1. Explicit user requirement

Highest priority.

Example:

    P95 < 500 ms

### 2. Project or team policy

Example:

    All external API calls require explicit timeout configuration.

### 3. Product recommended baseline

Verisys may provide a recommended baseline when clearly labeled as such.

A product recommendation must never be represented as if it were a user requirement.

### 4. Hard structural invariant

Some checks may have deterministic built-in conditions when the catalog explicitly defines them.

Example:

For the MVP Timeout Coverage policy:

    required coverage = 100%

The source of the acceptance condition must be visible.

---

## 13. No Aggregate Architecture Score

The MVP must not generate unsupported scores such as:

    Architecture Health: 72 / 100

Such scores hide evidence and introduce arbitrary weighting.

Prefer explicit evaluation results:

    Timeout Coverage
    VIOLATED

    API Latency
    NOT_VERIFIABLE

    Worker Recovery
    Applicability: NOT_APPLICABLE

    Circular Dependencies
    Execution support: NOT_AVAILABLE

Each result should remain independently inspectable.

---

## 14. MVP Catalog Scope

M4 must fully execute the first verification:

    External API Timeout Coverage

After M6, the first MVP may automatically recommend:

    API Latency
    Retry Safety
    Idempotency
    Worker Recovery
    DLQ Coverage
    Circular Dependencies
    Synchronous External Dependency

Only Timeout Coverage is required to complete:

    Evaluation
    → Plan
    → Tool Execution
    → Evidence
    → Verdict
    → Trace

Do not delay the MVP to implement additional evaluation executors.

---

## 15. Catalog Invariant

An evaluation is useful only if Verisys can answer:

1. Why is this relevant to this architecture?
2. What claim is being tested?
3. What evidence would be required?
4. How could that evidence be collected?
5. What condition would determine the verdict?
6. Can the current system actually execute that verification?

If these questions cannot be answered, the evaluation definition is incomplete.
