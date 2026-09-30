# Verisys MVP Plan

## 1. Goal

Build the smallest end-to-end vertical slice that proves the Verisys product abstraction.

The MVP must demonstrate:

Repository
→ Architecture Understanding
→ Evaluation Discovery
→ Verification Planning
→ Real Tool Execution
→ Evidence
→ Deterministic Verdict
→ Structured Trace

Breadth is not the goal.

One complete verification path is more important than many incomplete checks.

---

## 2. MVP Definition

Input:

    Local Python repository path

Primary output:

    Structured verification result

The MVP must:

1. safely discover repository files,
2. build a basic ArchitectureIR,
3. identify relevant engineering evaluations,
4. recommend External API Timeout Coverage when applicable,
5. create a VerificationPlan,
6. execute a real static timeout analyzer,
7. produce source-backed Evidence,
8. compute a deterministic Verdict,
9. produce a structured Verification Trace,
10. render the result for a human.

The complete executable evaluation is:

    External API Timeout Coverage

---

## 3. Hard Scope

### Required

- Python 3.11+
- local repository input
- bounded safe file discovery
- Python AST analysis
- basic ArchitectureIR
- basic FastAPI detection
- API route detection where practical
- external service/call detection for supported patterns
- deterministic Evaluation Profiler
- Timeout Coverage VerificationPlan
- Timeout Analyzer
- Evidence objects
- source file and line references
- deterministic Judge
- VERIFIED / VIOLATED / NOT_VERIFIABLE
- structured TraceEvents
- CLI
- readable output
- bundled golden example repository
- automated tests
- no API key required

### Optional only after required path works

- Mermaid rendering
- Markdown export
- JSON export
- circular dependency reporting
- richer architecture detection
- optional LLM explanation

---

## 4. Explicitly Out of Scope

Do NOT implement during the first vertical slice:

- GitHub URL ingestion
- web UI
- React
- Next.js
- LangGraph
- LangSmith
- multi-agent architecture
- Docker sandbox
- arbitrary repository execution
- dependency installation for analyzed repos
- pytest runtime verification
- failure injection
- k6
- runtime latency measurement
- retry-safety execution
- idempotency execution
- DLQ inspection
- cloud infrastructure integrations
- production observability integrations
- automatic code modification
- remediation agent
- change planner
- automatic architecture migration

Do not expand scope unless the required vertical slice is complete and tested.

---

## 5. Required Package Shape

Start with a small Python package.

Suggested structure:

    verisys/
      __init__.py
      cli.py

      models/
        __init__.py
        architecture.py
        evaluation.py
        requirement.py
        verification.py
        evidence.py
        trace.py

      repository/
        __init__.py
        discovery.py

      architecture/
        __init__.py
        analyzer.py
        python_ast.py

      evaluation/
        __init__.py
        catalog.py
        profiler.py

      verification/
        __init__.py
        planner.py
        judge.py

      tools/
        __init__.py
        timeout_analyzer.py

      orchestration/
        __init__.py
        runner.py

      reporting/
        __init__.py
        console.py

    tests/

    examples/
      timeout_demo/

    pyproject.toml

The exact file structure may change if there is a clear reason.

Do not collapse all responsibilities into one file.

Do not create unnecessary abstraction layers.

---

## 6. Milestone 0 — Domain Models

Implement typed models first.

Minimum required models:

### SourceLocation

Fields:

    file
    line
    column optional

### ArchitectureIR

Minimum useful fields:

    repository_root
    languages
    frameworks
    api_routes
    external_services
    dependencies
    limitations

### EvaluationCandidate

Fields:

    id
    name
    category
    applicability
    priority
    reason
    required_evidence
    verification_mode
    execution_support

### VerificationPlan

Fields:

    evaluation_id
    claim
    verification_mode
    required_evidence
    tool
    acceptance_condition
    limitations

### Evidence

Fields:

    id
    type
    source
    claim
    observed_value
    unit optional
    source_location optional
    tool
    limitations

### Verdict

Fields:

    status
    evaluation_id
    evidence_ids
    expected
    observed
    summary
    limitations

Allowed status:

    VERIFIED
    VIOLATED
    NOT_VERIFIABLE

### TraceEvent

Fields:

    id
    type
    stage
    summary
    related_evidence_ids
    metadata

### VerificationRun

Fields:

    id
    architecture
    evaluation
    plan
    execution_status
    evidence
    verdict
    trace

Do not build presentation logic before the core objects exist.

---

## 7. Milestone 1 — Repository Discovery

Implement safe local repository discovery.

Requirements:

- accept a repository root,
- validate that it exists,
- discover Python files,
- exclude unsafe/unnecessary paths,
- enforce a per-file size limit,
- enforce a total file-count/input limit,
- reject or skip external symlinks,
- record skipped files and reasons.

Must exclude at minimum:

    .git
    .env
    .venv
    venv
    node_modules
    __pycache__

Do not execute repository code.

Test:

- valid repository,
- missing path,
- excluded directory,
- oversized file,
- external symlink.

---

## 8. Milestone 2 — Architecture Analyzer

Implement deterministic Python AST analysis.

MVP goals:

- parse supported Python files,
- collect imports,
- identify functions/classes as needed,
- detect FastAPI where possible,
- detect route decorators,
- identify supported external client usage,
- identify internal dependency relationships where practical,
- produce ArchitectureIR,
- attach source locations.

Do not attempt perfect architecture reconstruction.

Prefer:

    correct + limited

over:

    broad + unreliable

Parse failures must become explicit limitations.

---

## 9. Milestone 3 — Evaluation Profiler

Implement deterministic architecture-aware evaluation selection.

Minimum rule:

IF:

    supported external API calls exist

THEN recommend:

    External API Timeout Coverage

with:

    category = Reliability
    applicability = APPLICABLE
    execution_support = SUPPORTED

Additional recommendation rules may be added cheaply.

Example:

IF:

    HTTP route
    AND synchronous external dependency

THEN recommend:

    API Latency

but:

    execution_support = NOT_AVAILABLE

IF:

    queue/worker indicators exist

THEN recommendations may include:

    Worker Recovery
    Retry Safety
    Idempotency

with:

    execution_support = NOT_AVAILABLE

The profiler must explain WHY each evaluation is applicable.

Do not return the entire catalog.

---

## 10. Milestone 4 — Timeout Verification Plan

Create a deterministic VerificationPlan for:

    External API Timeout Coverage

Claim:

    All supported detected external API call sites define explicit timeout behavior.

Verification mode:

    STATIC

Required evidence:

    detected external call sites
    timeout presence for each supported call site

Tool:

    timeout_analyzer

Acceptance condition:

    calls_with_timeout == total_supported_external_calls

If there are supported external calls but analysis cannot determine timeout behavior reliably, preserve uncertainty.

Do not silently count unknown behavior as safe.

---

## 11. Milestone 5 — Timeout Analyzer

Implement the first real verification tool.

The analyzer must inspect real source code.

It must produce structured evidence for each supported external call site.

Each result should include:

    service/client
    source file
    line number
    timeout status
    relevant limitations

### Golden demo target

The bundled example repository should contain:

    OpenAI call -> timeout present
    Stripe call -> timeout present
    Twilio call -> timeout missing

Expected:

    total supported external calls = 3
    calls with timeout = 2
    calls without timeout = 1
    coverage = 66.7%

The exact demo syntax should match patterns the analyzer intentionally supports.

Do not pretend to support every external Python client.

Document supported patterns.

---

## 12. Milestone 6 — Deterministic Judge

Implement judgment separately from the analyzer.

Input:

    VerificationPlan
    Evidence[]

Compute:

    total_supported_external_calls
    calls_with_timeout

Acceptance condition:

    calls_with_timeout == total_supported_external_calls

Expected golden result:

    2 == 3
    false

Verdict:

    VIOLATED

If:

    3 == 3

Verdict:

    VERIFIED

If sufficient evidence cannot be collected:

    NOT_VERIFIABLE

The Judge must not use an LLM.

---

## 13. Milestone 7 — Structured Trace

Record structured TraceEvents throughout the run.

Minimum expected trace for golden demo:

    DECISION
    Repository contains supported external API calls.

    DECISION
    External API Timeout Coverage is applicable.

    ACTION
    Execute static timeout analyzer.

    OBSERVATION
    Three supported external call sites were analyzed.

    EVIDENCE
    OpenAI timeout detected.

    EVIDENCE
    Stripe timeout detected.

    EVIDENCE
    Twilio timeout not detected.

    VERDICT
    Timeout Coverage violated: 2 of 3 calls have explicit timeout behavior.

Trace events must reference evidence IDs where appropriate.

Do not expose hidden chain-of-thought.

---

## 14. Milestone 8 — CLI

Provide one documented command that executes the complete flow.

Target experience:

    verisys analyze ./examples/timeout_demo

The output should show, at minimum:

    Repository
    Detected Architecture
    Recommended Evaluations
    Selected/Executed Evaluation
    Evidence
    Expected
    Observed
    Verdict
    Trace

Example conceptual output:

    VERISYS

    Architecture
    ------------
    Python
    FastAPI
    External services: OpenAI, Stripe, Twilio

    Recommended Evaluations
    -----------------------
    [HIGH] External API Timeout Coverage
    [MEDIUM] API Latency (execution unavailable)

    Verification
    ------------
    External API Timeout Coverage

    OpenAI   timeout: yes   app/openai_client.py:12
    Stripe   timeout: yes   app/payment.py:18
    Twilio   timeout: no    app/sms.py:21

    Expected: 3 / 3
    Observed: 2 / 3

    Verdict: VIOLATED

The exact formatting may differ.

The information must remain evidence-backed.

---

## 15. Milestone 9 — Golden Example

Create:

    examples/timeout_demo/

The repository should be intentionally small.

It should demonstrate enough architecture for:

- Python detection,
- FastAPI detection,
- route detection,
- external service detection,
- Timeout Coverage applicability,
- timeout verification.

Required ground truth:

    OpenAI timeout: present
    Stripe timeout: present
    Twilio timeout: missing

The example must not require real credentials or external network access.

The analyzer reads the code but does not execute it.

---

## 16. Milestone 10 — Tests

Minimum test areas:

### Repository discovery

- exclusions,
- invalid path,
- symlink behavior,
- file limits.

### Architecture analysis

- FastAPI detection,
- route detection,
- external service detection,
- source locations,
- parse failure handling.

### Evaluation profiler

- timeout evaluation selected when external services exist,
- irrelevant evaluations not blindly selected.

### Timeout analyzer

- timeout present,
- timeout missing,
- supported call detection,
- source line accuracy,
- ambiguous/unsupported pattern handling.

### Judge

- all calls protected -> VERIFIED,
- missing timeout -> VIOLATED,
- insufficient evidence -> NOT_VERIFIABLE.

### End-to-end

Run the golden example through the full orchestrator.

Expected final verdict:

    VIOLATED

Expected observed coverage:

    2 / 3

---

## 17. MVP Acceptance Test

The primary acceptance command should be documented.

Conceptually:

    verisys analyze ./examples/timeout_demo

The result must demonstrate:

    Repository
        ↓
    ArchitectureIR
        ↓
    Evaluation Discovery
        ↓
    VerificationPlan
        ↓
    Real Static Tool Execution
        ↓
    Evidence
        ↓
    Deterministic Judge
        ↓
    VIOLATED
        ↓
    Structured Trace

If this flow works reproducibly, the core MVP succeeds.

---

## 18. Failure Behavior

The MVP must fail honestly.

### Invalid repository

Return a clear input error.

### Python parse failure

Continue where safe and record the limitation.

### Unsupported external client

Record it as unsupported/unknown.

Do not claim timeout coverage for a call pattern the tool cannot analyze reliably.

### No applicable external calls

Do not manufacture a Timeout Coverage result.

The evaluation may be:

    NOT_APPLICABLE

### Required evidence unavailable

Return:

    NOT_VERIFIABLE

### Tool internal failure

Execution status:

    FAILED

Do not automatically translate a tool crash into:

    VIOLATED

A failed verifier is not evidence that the software violated the requirement.

---

## 19. LLM Policy for MVP

An LLM is not required for the first vertical slice.

The following path must work without an API key:

    Repository
    → ArchitectureIR
    → Evaluation Discovery
    → Timeout Verification
    → Evidence
    → Verdict
    → Trace

An optional LLM may later:

- explain architecture,
- interpret natural-language requirements,
- propose verification strategies,
- summarize evidence.

It must never:

- fabricate evidence,
- create runtime metrics,
- override deterministic verdicts.

Do not block MVP completion on LLM integration.

---

## 20. Development Order

Implement in this exact priority unless a blocking technical issue requires adjustment:

1. Domain models
2. Repository discovery
3. Architecture Analyzer
4. Evaluation Profiler
5. Timeout VerificationPlan
6. Timeout Analyzer
7. Deterministic Judge
8. Structured Trace
9. Orchestrator
10. CLI
11. Golden example
12. Tests
13. README demo instructions
14. Optional presentation improvements

Do not begin optional work while the end-to-end path is broken.

---

## 21. Definition of Done

The MVP is done when:

- installation works from a fresh environment,
- no API key is required,
- the bundled example can be analyzed,
- ArchitectureIR is produced,
- architecture-aware evaluations are recommended,
- Timeout Coverage is selected as applicable,
- real source code is inspected,
- evidence contains real file/line locations,
- coverage is computed from actual analyzer output,
- verdict is deterministic,
- NOT_VERIFIABLE is supported,
- trace is structured,
- tests pass,
- README contains one reproducible demo command.

For the golden example:

    Expected:
    3 / 3 external calls should have timeout behavior.

    Observed:
    2 / 3.

    Verdict:
    VIOLATED.

---

## 22. Stop Conditions

Do not add more features merely because time remains.

After the vertical slice works:

1. run tests,
2. inspect evidence accuracy,
3. verify source line references,
4. verify the golden expected result,
5. simplify unnecessary code,
6. improve demo readability.

The MVP should optimize for:

    trustworthy evidence
    +
    clear product abstraction
    +
    reproducible demo

not feature count.
