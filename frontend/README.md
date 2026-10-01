# Verisys frontend

The workspace starts empty. **Analyze Repository** accepts an absolute local
Python repository path and loads the real backend result. It exposes EMPTY,
ANALYZING, READY and ERROR states, with no silent fixture fallback.

Start the backend from the project root as described in the root README, then:

```sh
npm ci
npm run dev
```

Open http://127.0.0.1:3000. Next.js proxies `/api/analyze` to
`http://127.0.0.1:8000`; set `VERISYS_BACKEND_URL` before starting Next.js to
change the backend address. Only local paths are supported. No GitHub ingestion,
repository history or accounts are implemented. Only the installed static timeout verifier is executable.

System Flow uses `graph.execution_flows`; Dependency View filters the returned
graph to MODULE + IMPORTS without changing the DTO. Inspectors display actual
source locations and limitations. Repositories without a supported flow remain
valid. Repository names come from backend metadata, never the test snapshot.

Offline fixture provenance and refresh instructions are in
[the canonical real-repository smoke test](../docs/contributing.md#real-repository-smoke-test).
Fixtures are not imported by the production workspace.

## Backend/frontend contracts

`lib/architecture/types.ts` manually mirrors the Python graph/execution models.
`lib/architecture/analysis-client.ts` owns the analysis response type, request and
client checks; `next.config.ts` owns proxy configuration. No types are generated.
Coordinate serialized backend changes with these files and run backend tests plus
all frontend checks below. IR is returned for other consumers; rendering uses the
graph DTO. See [shared contracts](../docs/architecture.md#shared-contracts-and-mutation).

Run commands in this directory:

```sh
npm run typecheck
npm test
npm run build
```

## Suggested Verifications (M5)

After analysis, Discover Verifications calls `/api/evaluations/discover` through
the existing Next proxy with repository_path and expected_architecture_id. The
analysis client retains architecture_id; 409/ANALYSIS_STALE clears suggestions and
prompts explicit reanalysis without automatic retry. The backend re-analyzes the
path and uses process provider
configuration; see root README. Missing configuration is a visible error, not a
fixture fallback. Suggestions are recommendations only; no verification is run.

`lib/evaluation/discovery-client.ts` mirrors the narrow backend suggestion response;
`components/evaluation/SuggestedVerifications.tsx` owns IDLE/DISCOVERING/READY/EMPTY/
ERROR presentation and blocks duplicate in-flight calls. New analysis invalidates
suggestions and ignores late responses, including same-path reanalysis. Candidate
fields remain server-owned; System Flow/Dependency View semantics are unchanged.

## Verification execution (M6)

Suggestions expose server-owned can_execute. Run Verification is available for
the installed timeout verifier, including UNKNOWN/PARTIAL recommendations; other
checks remain disabled. `/api/evaluations/verify` is proxied to the same backend
and sends repository_path, evaluation_id and expected_architecture_id only.
No model call or provider credential is needed for execution.

The execution client/result panel render the narrow server DTO: policy, separate
applicability/execution/verdict, Judge counts and definitive coverage when available,
source-backed evidence and expandable structured trace. UNKNOWN is distinct from
MISSING; incomplete coverage does not hide a VIOLATED result. Empty applicable
scope creates no fake Verdict or percentage. IDLE/RUNNING/RESULT/ERROR are separate,
in-flight executions are deduplicated, new analysis/discovery invalidates results,
and stale errors require explicit reanalysis. No timeout judgment is computed here.
