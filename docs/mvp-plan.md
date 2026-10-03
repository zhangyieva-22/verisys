# MVP milestones and acceptance

## Goal and status convention

Deliver a working verification vertical slice for local Python repositories:
understand source, make architecture visible, discover worthwhile investigations,
execute one real static policy, and expose evidence-backed judgment.

**Implemented** means the capability exists and has focused validation, not that
it is available in every interface. **Planned** requires separate authorization.
This document describes the current checkout. Git history and PRs identify
shared checkpoints.

## Implemented milestones

### M0 — typed domain foundation

Python 3.11+, Pydantic domain models, distinct enums, source provenance, immutable
observations, raw requirement preservation and subject-link invariants. Tests cover
construction, validation, serialization and default isolation. Models do no work.

### M1 — safe local repository discovery

Validate root, recursively discover Python paths deterministically, apply exclusion
and binary checks, skip child symlinks, enforce size/file/entry/aggregate budgets,
retain effective limits and record omissions/truncation. Never execute/import source.

### M2 — architecture analysis

Bounded AST facts for supported FastAPI/routes, external libraries and simple
internal imports. Preserve locations, binding ambiguity and parse/read limitations.
Rebinding/local collisions cannot become confident facts. No verification logic.

### M2.5 — semantic presence detections

ChatOpenAI wrapper presence, explicitly decorated tools and sqlite3.connect presence.
Do not infer concrete wrapper calls, tool side effects, database contents or edges.

### M2.6 — source-declared execution flow

Finite StateGraph extraction and bounded FastAPI handler → imported compiled graph
association. Retain proof for each transition. Candidate tools remain an unordered
set. Components/imports/flows remain separate; no generalized cross-file call graph.

### M3A — ArchitectureGraph projection

Pure deterministic projection over ArchitectureIR, with stable identities, honest
source references and only supported relationships. No secondary inference.

### M3B — frontend architecture workspace

Next.js/TypeScript workspace, source Inspector, System Flow and Dependency View.
Conditional labels, retry loops, candidate tool details and unconnected components
remain honest. UI geometry is outside the domain DTO. Snapshots are labeled fixtures.

### M3C — local backend/API wiring

Analyze Repository connects real local discovery/analysis/projection to the frontend.
Controlled errors, loopback development boundary and no silent fixture fallback.
No discovery/verification endpoint or persistence is implied.

### M4 Core — golden timeout verification

Executable direct OpenAI per-call policy, fixed requirement/plan, fresh safe scope,
immutable static Evidence, evidence-only deterministic Judge and structured Run/Trace.
The bundled golden case yields 2/3, 66.7%, VIOLATED; symbolic timeout yields
NOT_VERIFIABLE. Empty complete scope remains irrelevant without a manufactured verdict.
See [the catalog](evaluation-catalog.md) for exact grammar and acceptance rules.

### M4.5 Core — LLM evaluation discovery and hardening

ArchitectureIR → bounded canonical subjects → deterministic eligible options →
optional LLM option selection → strict validation → server-owned candidates.
Four catalog entries; only timeout has an installed verifier. Selection is semantic,
not automatic return of all eligible options. Schema enum/option IDs prevent
model-authored rationale/subject combinations; snapshot validation remains mandatory.

The first live call returned structurally valid but invalid semantic combinations.
Validation rejected them. After option-contract hardening, one new live call
validated successfully against the pinned ecommerce fixture; it selected timeout,
latency and tool safety, leaving retry safety unselected. This is smoke-test evidence
for integration, not a deterministic expectation for future model selections or an
engineering Verdict. Routine tests use fakes/mocks; live testing remains opt-in.

## Implemented: M5 — Suggested Verifications Experience

A user-controlled Discover Verifications action after analysis calls the local
discovery endpoint with its displayed architecture_id as a freshness precondition.
Fresh server analysis rejects mismatches before model generation and feeds the unchanged grounded
M4.5 core. The UI shows validated candidate reasons, applicability, support, mode,
priority, required evidence and limitations. IDLE/DISCOVERING/READY/EMPTY/ERROR,
request deduplication and invalidation on new analysis are covered by integration
tests. Routine backend/frontend validation passes without live credentials.
No verifier executes and no Evidence/Verdict is generated.

## Implemented: M6 — verification execution and result experience

Candidate → registered verifier when available → real Evidence → deterministic
Judge → Verdict and trace → narrow API result → frontend evidence panel.
User-triggered execution supports only the existing static timeout policy. Fresh
architecture preconditions, registry-owned capability, request deduplication,
result invalidation and controlled system errors are covered by deterministic
API/UI tests. No provider is called during verification. Runtime verification,
general orchestration and additional verifiers remain future work.

## Implemented: M7 — public GitHub intake and analysis modes

The primary URL/ref input resolves a public GitHub revision and materializes a bounded
archive into a cleaned temporary root. Existing discovery/analyzer/verifier layers
remain local-root consumers. PROACTIVE starts one grounded discovery; ON_DEMAND
adds a bounded untrusted concern and selects only eligible option IDs, allowing
no-match. Full commit SHA plus architecture_id protect follow-up requests. Only the
existing timeout verifier executes. Local paths remain development/testing support.
Private/OAuth/SSH/other hosts, persistent cloning and runtime execution are excluded.

## MVP acceptance and non-goals

The completed product slice should make it possible to analyze a repository,
understand source-backed architecture, discover worthwhile evaluations, run the
supported static policy and inspect real evidence/judgment/trace. M5 connects discovery to the frontend; M6 completes execution and source-backed result presentation for the single installed policy.

No runtime results may be inferred from static analysis. No required evidence may
be replaced with an LLM guess. Unsupported recommendations remain explicit about
missing execution support. Limits/unsupported scope remain visible.

Current non-goals include generalized static analysis/cross-file resolution,
private GitHub/other-provider ingestion, arbitrary requirement compilation, multi-agent/distributed
orchestration, sandboxed runtime execution, k6/failure injection, Langfuse/LangSmith,
production databases, automatic code modification and aggregate architecture scores.

## Validation and handoff

Each milestone includes focused deterministic behavior tests and documented limits.
Python changes run the full routine pytest suite. Frontend changes run typecheck,
tests and build. `git diff --check` must be clean. Live provider tests require
explicit approval and configuration; they are never ordinary regression tests.

A handoff lists scope, files/contracts changed, exact validation results, known
limitations and next approved work. Report dirty/uncommitted work accurately.
Never start another milestone merely because this document describes it. See
[contributing.md](contributing.md) for branch/PR workflow and credential rules.

## Implemented: M8 — project-centric multi-repository workspace

Projects is the landing page. URL/ref and Proactive/On-demand setup lead to a
repository Overview, with Architecture and Verifications as functional project
sections. All Projects supports recent-repository switching. Browser-local recent
metadata is navigation only; cold reopening obtains fresh pinned server analysis
without automatic discovery. Session-only evidence/results are never persisted as
authority. Runs is hidden pending a real history model. Domain/backend contracts
and the single executable timeout policy remain unchanged.

## Implemented: HTTP client timeout coverage

A second executable static verification checks outbound `requests` and `httpx` calls, reusing the M4 evidence model, judge, API and verification UI.
The policy follows each library's real defaults: `requests` has no timeout by default, while `httpx` defaults to five seconds; each finite timeout records whether it comes from the call, the client or the library default.
The analyzer now inspects `with` / `async with` bodies, which makes OpenAI calls inside them visible.
Catalog v2 adds the evaluation; because the catalog is hashed into `architecture_id`, every architecture ID changed once.
OpenAI verification evidence is unchanged for repositories without `with` blocks.
See [the design](http-client-timeout.md) and [the catalog](evaluation-catalog.md).

## Implemented: understanding layer

On an explicit user request, a language model proposes functional requirements and engineering risks for the analyzed repository.
The server selects README, documentation, source around routes and integrations, entry points and test names within fixed budgets, and redacts likely secrets before sending them.
The server keeps only citations whose quoted text appears in the lines it sent, and drops claims left without a valid citation.
Every item is labelled inferred, not verified, and appears in a separate Understanding section; it is never Evidence or a Verdict.
See [the understanding layer](understanding-layer.md).
The Architecture tab now shows only the Dependency View; the System Flow canvas was removed because it was empty for repositories without a LangGraph `StateGraph`.
The Architecture tab's default view is a layered System Diagram built from detected facts; Enrich with AI adds cited, inferred components (such as client, frontend and infrastructure) and a request path, drawn as visibly inferred.
