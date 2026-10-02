# Verisys

Verisys is an **architecture-aware Engineering Verification Agent**. It helps
answer: what is worth verifying in this system, how can we verify it, and what
real evidence supports the result?

The intended workflow is:

Repository → ArchitectureIR → Evaluation Discovery → Verification Planning →
Tool Execution → Evidence → Deterministic Verdict → Structured Trace.

## What works today

- Public GitHub URL intake with pinned commits and bounded archive materialization.
- Safe, bounded Python repository discovery and static architecture analysis; local paths remain a development/testing option.
- Source-grounded architecture components, internal imports and a limited set of
  source-declared execution flows.
- A Next.js architecture workspace with System Flow, Dependency View and Inspector,
  connected to the local FastAPI analysis endpoint.
- M4 Core: static explicit per-call OpenAI timeout verification, producing immutable
  source-backed evidence, a deterministic verdict and structured trace.
- M4.5 Core: deterministic eligible discovery options, optional LLM selection of
  option IDs, and strict server-controlled EvaluationCandidate construction.

The UI/API expose architecture analysis and **Suggested Verifications** (M5).
Choose PROACTIVE to find important checks, or ON_DEMAND with a bounded concern.
For GitHub input, Analyze runs one grounded discovery automatically after architecture
analysis; choosing Analyze authorizes that configured model call. No render retries it. Verification execution
is now available for the installed static OpenAI timeout policy (M6), with source-backed evidence, deterministic verdict and trace. Runtime verification and other suggested checks remain unavailable. See [the milestone plan](docs/mvp-plan.md).

## Local setup

Use Python 3.11+ and Node.js 20.9+. The current filesystem safety implementation
uses POSIX directory descriptors; macOS/Linux are the intended local platforms.

Install Verisys's dependencies, not dependencies from repositories being analyzed:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[test]'
.venv/bin/python -m uvicorn verisys.api.app:app --host 127.0.0.1 --port 8000
```

In another terminal:

```sh
cd frontend
npm ci
npm run dev
```

Open `http://127.0.0.1:3000`, choose **Analyze Repository**, enter a public GitHub
URL and optional branch/tag/commit, then select PROACTIVE or ON_DEMAND. The server
resolves a full commit SHA and materializes a bounded archive without git checkout,
hooks, filters, submodules or repository execution. Discovery and verification
reacquire that exact commit. Local path intake is a secondary development option.
Failed analysis never silently falls back to a demo. Checked-in graph snapshots
are explicitly illustrative or offline real-repository fixtures, not live results.

The frontend proxies `/api/analyze` to `http://127.0.0.1:8000`. Set
`VERISYS_BACKEND_URL` for a different backend address. Keep both servers on
loopback; this is a local development interface, not a hosted multi-user service.

## Run the static golden verification

This requires no model/API key and never executes the example's code:

```python
from verisys.verification import verify_timeout_coverage

run = verify_timeout_coverage("examples/timeout-coverage")
print(run.model_dump_json(indent=2))
```

Expected: 2 configured / 1 missing / 0 unknown, 66.7% coverage, `VIOLATED`.
`examples/timeout-unknown` yields `NOT_VERIFIABLE` for a symbolic timeout.
The policy checks explicit positive finite numeric per-call `timeout` literals
on supported direct OpenAI calls. It does not prove effective runtime timeouts,
client defaults or wrapper behavior. See [the exact policy](docs/evaluation-catalog.md).

## Optional LLM evaluation discovery

Install the optional provider/local-development dependencies:

```sh
.venv/bin/python -m pip install -e '.[test,discovery]'
cp .env.example .env
```

Fill `OPENAI_API_KEY` and `VERISYS_DISCOVERY_MODEL` locally. Choose a model that
supports Responses structured outputs; the implementation does not hardcode one.
Existing process environment variables take precedence over `.env`.

**Never commit or push `.env` or credentials.** The blank `.env.example` is safe
to share. Only the opt-in live test loads `.env` within application/test code; importing Verisys,
starting the backend and routine pytest do not load it implicitly.

The live test sends a bounded normalized architecture summary to OpenAI. It sends
relative source references, labels, declared flow facts and catalog options, not
raw source, repository root, config values, credentials or verification results.
Architecture metadata can still be sensitive; run live discovery deliberately.
The model receives no tools and selects only supplied eligible option IDs.

```sh
VERISYS_LIVE_DISCOVERY=1 \
VERISYS_LIVE_REPOSITORY=/absolute/path/to/ecommerce-ai-agent \
.venv/bin/python -m pytest tests/test_evaluation_live.py -s --tb=short
```

Use [the canonical real-repository smoke test](docs/contributing.md#real-repository-smoke-test)
for the ecommerce URL, pinned checkout and offline snapshot procedure.

Routine tests skip the live test. Provider/discovery failures are controlled errors,
not empty successful recommendations. Opt-in test configuration/setup failures can
occur before discovery (missing variables or invalid configuration). Live discovery
never executes verification. See [discovery/provider test guidance](docs/contributing.md#discoveryprovider-tests)
for optional dependencies needed to run mocked SDK tests without credentials.

## Suggested Verifications backend configuration

Install `.[test,discovery]`. For M5, OPENAI_API_KEY and VERISYS_DISCOVERY_MODEL must
be in the backend process environment. The application does not load `.env`.
You may explicitly use Uvicorn's local-development env-file option instead of
manually exporting credentials (existing process values retain precedence):

```sh
.venv/bin/python -m uvicorn verisys.api.app:app --host 127.0.0.1 --port 8000 --env-file .env
```

Analyze a GitHub repository in the selected mode (one automatic discovery), or use
the local development option and click Discover Verifications explicitly. This sends bounded
normalized metadata to the configured provider and returns validated suggestions.
Missing configuration, provider failures and validation failures are visible errors;
none becomes fake recommendations. Empty selection is a successful distinct state.
A new analysis clears prior suggestions. Applicability/support/mode/priority come
from the server; no Evidence, Verdict or verification execution is implied.
Discovery compares fresh normalized architecture with the displayed analysis ID.
A mismatch produces a stale-analysis message; analyze again explicitly. The hash
covers normalized facts, not every source byte; keep the repository stable. Run Verification executes the installed timeout policy without a provider call or API key. Other suggestions remain non-executable. New analysis or discovery clears prior results.

## Validation and collaboration

```sh
.venv/bin/python -m pytest
cd frontend
npm run typecheck
npm test
npm run build
```

Run `git diff --check` from the project root. Do not enable live testing as part
of ordinary validation.

Start with [the contribution guide](docs/contributing.md) for branch/PR workflow,
module coordination, checks and secret handling. [AGENTS.md](AGENTS.md) contains
repository-wide contributor and coding-agent invariants.

## Documentation map

- [Product specification](docs/product-spec.md): users, product workflow and boundaries.
- [Architecture](docs/architecture.md): current modules, contracts and safe-read boundaries.
- [Evaluation catalog](docs/evaluation-catalog.md): discovery options and executable timeout policy.
- [Milestone plan](docs/mvp-plan.md): implemented work, acceptance criteria and future scope.
- [Contribution guide](docs/contributing.md): setup, collaboration, testing and handoffs.

Keep these documents aligned with implementation. Planned behavior must be
labeled as planned; a recommendation, architecture diagram or provider response
is never evidence that an engineering requirement was verified.

## Repository sources and on-demand limits (M7)

The primary API source is tagged:

```json
{"source":{"type":"github","url":"https://github.com/owner/repository","ref":"main"}}
```

Analyze returns repository_url, requested_ref, resolved_commit_sha and architecture_id.
Subsequent discover/verify requests send source.ref as the returned **full commit SHA**
and expected_architecture_id. Discovery additionally accepts mode PROACTIVE, or
ON_DEMAND with request_text (1–2000 characters). On-demand matching is limited to
server-generated catalog options; an unmatched request returns no supported
evaluation, never a fabricated result. Only timeout coverage has an installed verifier.
Private repositories, OAuth, SSH and other Git providers are unsupported.

Development intake uses `{"source":{"type":"local","path":"/absolute/path"}}`.
The old repository_path-only body remains a local compatibility path; combining it
with source is rejected. Remote temporary filesystem paths are never returned.
Acquisition uses independent download/extraction limits; see the architecture doc.

## Project workspace (M8)

The app opens on **Projects**, with one Analyze Repository entry. Choose Proactive
to find checks, or On-demand to supply a concern. Successful analysis opens the
repository's Overview; Architecture contains System Flow/Dependency View and the
Inspector, while Verifications contains suggestions and evidence-backed results.
Use All Projects to switch between repositories. Runs is hidden: no durable run
history exists.

Recent GitHub projects are lightweight browser-local navigation metadata (up to
20 repositories), not authoritative persistence or a production team database.
A reload restores names/revisions only; Open Project obtains fresh server analysis
at the saved commit, without an automatic paid discovery. Discover explicitly, or
re-analyze with a new concern. Architecture, suggestions, evidence and results live
only in the current session. Local development paths are never persisted.
