# Verisys frontend

The workspace opens on Projects. **Analyze Repository** accepts a
public GitHub repository URL/ref and loads the real backend result. Local paths are a secondary development option. It exposes EMPTY,
ANALYZING, READY and ERROR states, with no silent fixture fallback.

Start the backend from the project root as described in the root README, then:

```sh
npm ci
npm run dev
```

Open http://127.0.0.1:3000. Next.js proxies `/api/analyze` to
`http://127.0.0.1:8000`; set `VERISYS_BACKEND_URL` before starting Next.js to
change the backend address. Only public GitHub and local development paths are supported. No private/OAuth/SSH
intake, repository history or accounts are implemented. Only the installed static timeout verifier is executable.

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

## Repository URL and modes (M7)

Repository URL is primary, with an optional branch/tag/commit. PROACTIVE finds
important engineering checks; ON_DEMAND reveals a bounded concern field. An
explicit remote Analyze action makes one automatic discovery request after
analysis; rerenders/StrictMode do not repeat it. Local development uses explicit
discovery. Empty on-demand selection says no current evaluation matches.

The API returns a tagged pinned source and resolved_commit_sha. Clients forward
that full SHA with expected_architecture_id to discovery and verification. UI
shows owner/repository and short SHA, never server materialization paths. Source,
ref or mode changes invalidate prior state. Only installed timeout verification
executes; other candidates stay disabled. No source execution or fake result exists.

## Project-centric workspace (M8)

Projects is the initial landing page. Analyze Repository opens URL/ref and clear
Proactive/On-demand cards; the concern field appears only for On-demand. One remote
Analyze action starts analysis and grounded discovery, then opens Overview. Project
navigation exposes Overview, Architecture and Verifications; no Runs placeholder.
Navigation within a project does not repeat discovery or discard its latest result.
All Projects returns to recent repositories. Switching preserves separate session
results and aborts/ignores outstanding requests from the previous project.

`lib/projects.ts` validates/version-tags and whitelists recent-project localStorage
metadata. No raw concern, IR, discovery output, Evidence, Verdict, credentials or
local filesystem path is stored. Invalid storage is safely ignored; unavailable
storage leaves the session usable. Reopening after reload re-analyzes the stored
full SHA authoritatively and requires explicit discovery. Restored On-demand
projects require re-entering the concern. Storage is not a backend/team database.
