# Verisys MVP Plan

## 1. Goal

Build the smallest end-to-end vertical slice that proves the Verisys product abstraction.

The canonical product workflow is unchanged. The completed MVP must demonstrate:

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

    Visible architecture and structured verification results

M0 Domain Models, M1 Safe Repository Discovery, and M2 Architecture Analyzer are COMPLETE.

The implemented pipeline is:

Local Repository → Safe Repository Discovery → Static Python AST Analysis → ArchitectureIR.

The analyzer supports a bounded set: Python, FastAPI / APIRouter routes, OpenAI, Stripe, Twilio, simple internal import dependencies, source-grounded locations, and explicit limitations for unsupported or ambiguous patterns. It is not a generalized Python static-analysis engine. No verification executor or automatic Evaluation Profiler is implemented yet.

The preferred demo story is:

Repository → Analyze → Visible Architecture → Select architecture component → Choose/launch verification → Execute one real verification → Inspect source-backed evidence → Receive grounded verdict.

External API Timeout Coverage is the hero verification. This visible workflow takes priority over adding many invisible backend capabilities. Automatic evaluation selection arrives in M6; earlier demos use explicitly selected representative cases.

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
- deterministic Evaluation Profiler (M6)
- Timeout Coverage VerificationPlan
- Timeout Analyzer
- Evidence objects
- source file and line references
- deterministic Judge
- VERIFIED / VIOLATED / NOT_VERIFIABLE
- structured TraceEvents
- ArchitectureGraph projection and product frontend
- minimal backend/API wiring
- verification result UI
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

The revised MVP does not require generalized Python static analysis, generalized cross-file symbol resolution, LLM architecture inference, LangGraph, LangSmith, Docker sandboxing, k6 execution, failure injection, Change Planner, automatic code modification, architecture health scores, broad evaluation catalog execution, or generalized runtime verification.

Do not expand scope unless the required vertical slice is complete and tested.

---

## 5. Planned Package Boundaries

Start with a small Python package.

Prospective Python structure, not a list of files to scaffold now (CLI/reporting are optional interfaces):

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

Graph projection (M3A), a separate frontend (M3B), and a minimal API adapter (M3C) will be added at their milestones. Evaluation code arrives in M6; verification/tool/judgment/trace coordination arrives in M4. Do not create unused scaffolding.

The exact file structure may change if there is a clear reason.

Do not collapse all responsibilities into one file.

Do not create unnecessary abstraction layers.

---

## 6. Milestone 0 — Domain Models — COMPLETE

Typed models are implemented. The field lists below describe minimum concepts, not an exhaustive schema. EngineeringRequirement preserves raw text; plans/runs support evaluation and/or requirement subjects. Evidence and its source locations are immutable observations. Source lines are one-based; AST columns are zero-based UTF-8 byte offsets.

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

## 7. Milestone 1 — Safe Repository Discovery — COMPLETE

Safe local repository discovery is implemented. It conservatively skips all child symlinks, including internal ones, and records deterministic reasons and visible truncation. DiscoveryResult retains effective DiscoveryLimits; analysis reuses them by default and explicit overrides can only tighten them.

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

## 8. Milestone 2 — Architecture Analyzer — COMPLETE

Deterministic Python AST analysis is implemented for the bounded patterns described in the current status above. Safe reads revalidate containment, regular files and size; remaining aggregate input budget constrains ingestion. Unsafe reads, parse failures, dynamic routes, unresolved bindings/prefixes and known local-library collisions produce limitations. No cross-file client resolver exists.

ExternalService.source_locations supports service presence (imports, constructions, supported calls); call_sites contains concrete supported external API call expressions for later verification. Architecture analysis performs no timeout verification, evaluation selection, Evidence creation or judgment.

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

## 9. Milestone 3A — Architecture Graph Projection — NEXT

ArchitectureIR → ArchitectureGraph → Frontend graph renderer.

ArchitectureGraph is a deterministic presentation/projection layer. ArchitectureIR remains the source of truth; projection must not perform another round of architecture inference.

Initial node types may include FRAMEWORK, API_ROUTE, EXTERNAL_SERVICE, and MODULE. DATASTORE, QUEUE, and WORKER may be added only when ArchitectureIR actually supports them. Edge types may include CONTAINS, IMPORTS, and CALLS, but every relationship must have source-backed support in ArchitectureIR.

Never connect an API route to OpenAI merely because both exist. Current service call locations do not establish route-to-service relationships. Omit any edge the IR cannot prove; never invent edges for visual completeness.

Acceptance: repeated identical IR input produces identical nodes and edges; every projected relationship is supported, and unsupported relationships are omitted.

---

## 10. Milestone 3B — Frontend Product Shell + Architecture Visualization

The planned frontend uses Next.js, TypeScript, Tailwind, @xyflow/react / React Flow, and Lucide icons where useful. M3B may use clearly labeled fixture/mock ArchitectureGraph data before M3C connects real analysis. Mock data must never be presented as real analysis or verification.

Use modern developer tools such as CodeRabbit only as inspiration: clean, dense, restrained, developer-focused, evidence-first, code-centric, with clear status hierarchy. Do not copy branding, assets, exact layouts, wording, or proprietary visual elements.

The workspace concept is navigation/repository context on the left, architecture graph/primary workspace in the center, and selected-node inspector/verification details on the right. Prioritize one convincing workflow over many pages.

The graph should become a verification navigation surface: select nodes, inspect architecture facts, source locations and concrete call sites, choose/launch verification cases, and view evidence and verdicts. For example, an OpenAI node may show three source-backed calls at app/services/llm.py:42, :67, and :81, then offer External API Timeout Coverage. These locations are illustrative until backed by actual analysis.

---

## 11. Milestone 3C — Minimal Backend/API Wiring

Connect Repository → Discovery → Architecture Analyzer → ArchitectureIR → ArchitectureGraph → Frontend. Keep the backend small: input validation and adapters over the existing safe analysis pipeline, not a platform. Preserve untrusted-input boundaries, effective limits, deterministic results and visible limitations.

---

## 12. Milestone 4 — Golden Verification Cases

External API Timeout Coverage is the first fully executable verification, planned for M4. The preferred golden case is FastAPI with three supported OpenAI call sites: two define supported timeout behavior and one does not. Source-backed evidence yields 2 / 3 coverage (66.7%) and deterministic VIOLATED. The older mixed OpenAI/Stripe/Twilio example remains an alternate fixture.

API Latency may be relevant, but without runtime evidence the result is NOT_VERIFIABLE. Missing evidence includes a running environment, defined workload, load-test results, and P50/P95/P99 metrics. Never infer latency from source; do not implement k6 yet.

Retry Safety may be relevant for Stripe or another side-effecting external call. Explain the required strategy and missing evidence, but failure injection/runtime retry execution is unavailable. Do not claim it was verified; a requested verification without sufficient evidence is NOT_VERIFIABLE.

No evidence → no conclusive verification claim. Applicability, ExecutionSupport, ExecutionStatus, and VerdictStatus remain separate. An applicable evaluation can have execution support NOT_AVAILABLE, execution status NOT_RUN, and verdict NOT_VERIFIABLE; an unstarted case need not have a verdict.

### Timeout verification contract

Create a deterministic VerificationPlan with:

- claim: all supported detected external API call sites define explicit timeout behavior,
- verification mode: STATIC,
- required evidence: concrete supported calls and timeout presence for each,
- tool: timeout_analyzer,
- acceptance condition: calls_with_timeout == total_supported_external_calls,
- limitations: unsupported or ambiguous behavior, including unknown timeout configuration.

The tool inspects real source without executing/importing it and produces structured per-call evidence with service/client, file, line, timeout status and limitations. Document the supported syntax. Do not silently count unknown behavior as safe or unsupported calls as covered.

The separate deterministic Judge consumes the plan and evidence. Complete evidence of 2 / 3 yields VIOLATED; 3 / 3 yields VERIFIED; insufficient evidence yields NOT_VERIFIABLE. A tool crash is an execution failure, not proof of a violation. No applicable calls must not manufacture a coverage result.

Record concise structured DECISION → ACTION → OBSERVATION → EVIDENCE → VERDICT summaries. Reference evidence IDs; never store hidden chain-of-thought.

Bundle a small golden Python/FastAPI repository with three supported OpenAI calls (two timeout-present, one missing). It requires no credentials or external network access and is inspected statically. The mixed-service fixture may be retained as an alternate case.

### Focused validation

Test supported timeout presence/absence, source accuracy, ambiguous/unsupported behavior, all-protected VERIFIED, missing-timeout VIOLATED, missing-evidence NOT_VERIFIABLE, separate execution failure, and deterministic end-to-end evidence/trace. API Latency and Retry Safety cases must demonstrate honest missing evidence rather than simulated execution.

---

## 13. Milestone 5 — Verification Result UI

Display verification name, separately labeled verdict/applicability/execution support/execution status, concise explanation, evidence, source locations, missing evidence, limitations, and structured trace where available. External API Timeout Coverage is the first polished result. Connect it to the selected architecture component without inventing graph relationships.

---

## 14. Milestone 6 — Evaluation Profiler

Implement ArchitectureIR → Evaluation Profiler → EvaluationCandidate[]. This automatically answers: “What engineering properties are worth verifying for this architecture?” It remains a core capability and differentiator; only its implementation is delayed.

Use deterministic, explainable rules. Supported external call sites make Timeout Coverage applicable with SUPPORTED execution once M4 exists. HTTP API routes can make API Latency relevant with NOT_AVAILABLE runtime execution. Supported side-effecting service facts may make Retry Safety relevant with NOT_AVAILABLE execution. Do not infer request-path relationships from mere co-occurrence.

Do not return the entire catalog. Queue/worker recommendations require actual IR support; catalog examples are not permission to extend architecture analysis here.

---

## 15. Cross-Milestone Tests

Tests accompany each milestone rather than waiting until the end. Preserve completed model/discovery/analyzer tests. Add deterministic projection and relationship provenance tests in M3A, honest fixture labeling and inspector behavior in M3B, real pipeline wiring in M3C, verification/evidence/judgment/trace tests in M4, result/status UI tests in M5, and applicable/irrelevant selection tests in M6.

---

## 16. Preferred MVP Demo

Repository → Analyze → Visible Architecture → Select architecture component → Choose/launch verification → Execute one real verification → Inspect source-backed evidence → Receive grounded verdict.

External API Timeout Coverage is the hero verification. This visible workflow takes priority over adding many invisible backend capabilities. Automatic evaluation selection arrives in M6; earlier demos use explicitly selected representative cases.

---

## 17. MVP Acceptance Test

Document a reproducible frontend/API demo against the bundled repository. Analyze it, display source-backed architecture, select OpenAI, launch Timeout Coverage, inspect three real call-site results, and receive VIOLATED from 2 / 3 coverage with evidence and trace. Show API Latency as NOT_VERIFIABLE without runtime evidence and Retry Safety as unavailable rather than verified.

After M6, also demonstrate automatic architecture-aware EvaluationCandidates and relevance explanations. The canonical pipeline retains Evaluation Discovery before verification; manual selection in the earlier demo is an implementation sequencing step. CLI/Markdown/JSON are optional renderers, not required next interfaces or implemented commands.

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

1. M0 — Domain Models — COMPLETE
2. M1 — Safe Repository Discovery — COMPLETE
3. M2 — Architecture Analyzer — COMPLETE
4. M3A — Architecture Graph Projection — NEXT
5. M3B — Frontend Product Shell + Architecture Visualization
6. M3C — Minimal Backend/API Wiring
7. M4 — Golden Verification Cases
8. M5 — Verification Result UI
9. M6 — Evaluation Profiler

Add focused tests and reproducible demo instructions with each milestone. The canonical product workflow in section 1 is unchanged. Do not begin implementation merely because this documentation describes planned work.

---

## 21. Definition of Done

The MVP is done when:

- installation works from a fresh environment,
- no API key is required,
- the bundled example can be analyzed,
- ArchitectureIR is produced and projected into deterministic source-backed architecture nodes/edges,
- the frontend is wired to real analysis through a minimal API,
- node inspection and representative verification selection are visible,
- architecture-aware evaluations are recommended,
- Timeout Coverage is selected as applicable,
- real source code is inspected,
- evidence contains real file/line locations,
- coverage is computed from actual analyzer output,
- verdict is deterministic,
- NOT_VERIFIABLE is supported,
- trace is structured,
- tests pass,
- verification results show evidence, source references, limitations, missing evidence and trace,
- README contains reproducible product demo instructions.

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
