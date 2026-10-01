# Verisys

Verisys is an **architecture-aware Engineering Verification Agent**. It helps
answer: what is worth verifying in this system, how can we verify it, and what
real evidence supports the result?

The intended workflow is:

Repository → ArchitectureIR → Evaluation Discovery → Verification Planning →
Tool Execution → Evidence → Deterministic Verdict → Structured Trace.

## What works today

- Safe, bounded local Python repository discovery and static architecture analysis.
- Source-grounded architecture components, internal imports and a limited set of
  source-declared execution flows.
- A Next.js architecture workspace with System Flow, Dependency View and Inspector,
  connected to the local FastAPI analysis endpoint.
- M4 Core: static explicit per-call OpenAI timeout verification, producing immutable
  source-backed evidence, a deterministic verdict and structured trace.
- M4.5 Core: deterministic eligible discovery options, optional LLM selection of
  option IDs, and strict server-controlled EvaluationCandidate construction.

The UI/API expose architecture analysis and **Suggested Verifications** (M5).
After analysis, click Discover Verifications deliberately to request grounded
recommendations; no paid model call happens automatically. Verification execution
and runtime verification are not integrated. See [the milestone plan](docs/mvp-plan.md).

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

Open `http://127.0.0.1:3000`, choose **Analyze Repository**, and enter an absolute
local repository path on the backend machine. No GitHub cloning is performed.
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

Analyze a local repository, then click Discover Verifications. This sends bounded
normalized metadata to the configured provider and returns validated suggestions.
Missing configuration, provider failures and validation failures are visible errors;
none becomes fake recommendations. Empty selection is a successful distinct state.
A new analysis clears prior suggestions. Applicability/support/mode/priority come
from the server; no Evidence, Verdict or verification execution is implied.
Discovery compares fresh normalized architecture with the displayed analysis ID.
A mismatch produces a stale-analysis message; analyze again explicitly. The hash
covers normalized facts, not every source byte; keep the repository stable. Verification execution is future M6 work.

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
