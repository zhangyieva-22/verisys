# MVP milestones and acceptance

## Goal and status convention

Deliver a working verification vertical slice for local Python repositories:
understand source, make architecture visible, discover worthwhile investigations,
execute one real static policy, and expose evidence-backed judgment.

**Implemented** means the capability exists and has focused validation, not that
it is available in every interface. **Planned** requires separate authorization.
This document describes the current checkout, including M4.5 hardening that may
still await a commit/review. Git history and PRs identify shared checkpoints.

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

## Planned: M5 — verification experience/integration

Not implemented. Scope must be approved before coding. The intended visible slice
connects grounded recommendations and selected verification to real backend outputs,
showing separate applicability/support/execution/verdict states, source evidence,
limitations and trace. Discovery must not execute tools merely because it recommends
an evaluation. UI must not invent scores, findings or results.

General requirement compilation, richer planning/orchestration, additional verifiers,
runtime tools and hosted ingestion require their own scoped work. The old M6
profiling sequence is superseded by implemented M4.5 Core; do not maintain two
conflicting discovery roadmaps.

## MVP acceptance and non-goals

The completed product slice should make it possible to analyze a repository,
understand source-backed architecture, discover worthwhile evaluations, run the
supported static policy and inspect real evidence/judgment/trace. Current Python
cores work independently; frontend integration is still needed for the full story.

No runtime results may be inferred from static analysis. No required evidence may
be replaced with an LLM guess. Unsupported recommendations remain explicit about
missing execution support. Limits/unsupported scope remain visible.

Current non-goals include generalized static analysis/cross-file resolution,
GitHub URL ingestion, arbitrary requirement compilation, multi-agent/distributed
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
