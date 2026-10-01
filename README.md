# Verisys

Architecture-aware engineering verification, currently providing safe local
Python architecture analysis and a source-grounded architecture workspace.
M4 Core provides static timeout verification; M4.5 Core provides independent, optional LLM evaluation discovery.

## Local development

Use Python 3.11+ and Node.js 20.9+.

From the Verisys root, install **Verisys** dependencies and start the backend:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[test]'
.venv/bin/python -m uvicorn verisys.api.app:app --host 127.0.0.1 --port 8000
```

In a second terminal:

```sh
cd frontend
npm ci
npm run dev
```

Open http://127.0.0.1:3000, click **Analyze Repository**, enter an absolute path
such as `/Users/me/projects/my-agent`, and click **Analyze**. The backend calls
Discovery → Architecture Analyzer → ArchitectureIR → ArchitectureGraph. The
returned graph includes source-declared execution flows and actual limitations.
System Flow, Dependency View and Inspector render that result. An empty flow
list is valid; Dependency View remains available. Failed analysis never falls
back to a demo. The checked-in snapshots remain test fixtures only.

`POST /api/analyze` accepts `{"repository_path":"/absolute/local/path"}` and
returns `{repository: {name, path}, architecture: ArchitectureIR, graph:
ArchitectureGraph}`. `graph.execution_flows` and `graph.limitations` retain the
existing models without duplicate copies in the API envelope. Controlled errors
use `{error: {code, message}}`; no exception text or stack traces are returned.

The Next.js server proxies `/api/analyze` to `http://127.0.0.1:8000`. Override
`VERISYS_BACKEND_URL` when starting Next.js if the backend uses another port.
Keep both servers on loopback. The API permits browser origins
`http://127.0.0.1:3000` and `http://localhost:3000`, without wildcard CORS.

This milestone accepts local paths on the backend machine only. It does not
clone GitHub repositories, install analyzed dependencies, import repository
modules, execute repository code, persist history, or run verification. Existing
file, discovery and source-input budgets and symlink protections still apply.
Source locations are displayed; IDE navigation is not connected. Architecture
extraction remains limited to the previously supported patterns.

## Validation

```sh
.venv/bin/python -m pytest
.venv/bin/python -m pytest tests/test_api.py
cd frontend
npm run typecheck
npm test
npm run build
```

## M4 Core: explicit OpenAI per-call timeout verification

No API key or repository dependency installation is needed. Inspect the bundled
example through the Python function (the example itself is never executed):

```python
from verisys.verification import verify_timeout_coverage
run = verify_timeout_coverage("examples/timeout-coverage")
print(run.model_dump_json(indent=2))
```

The golden result is 2 configured / 1 missing / 0 unknown, 66.7%, VIOLATED.
`examples/timeout-unknown` yields NOT_VERIFIABLE for a symbolic timeout.
A conclusively irrelevant repository yields NOT_APPLICABLE and NOT_RUN with no
verdict. This core is not yet connected to the frontend Verify button or HTTP API.

v1 requires an explicit positive finite numeric per-call `timeout` literal on
already-supported OpenAI calls. Missing or invalid literals fail this policy;
symbolic values and expanded keywords are unknown. A client constructor timeout
does not satisfy this per-call policy. Stripe/Twilio and ChatOpenAI wrappers are
outside its grammar. It does not establish effective runtime behavior or SDK
defaults. Evidence retains exact source locations and content hashes, never
runtime measurements, secrets or source dumps. See the evaluation catalog for
scope completeness, conservative limitations and deterministic judgment rules.

Keep the repository stable while analyzing/verifying. Safe reads and content
hash comparison protect bounded inspection, but do not provide an atomic
filesystem snapshot. Invalid roots and unexpected internal errors propagate to
the Python caller rather than being converted into an engineering violation.


## M4.5 Core: catalog-bounded evaluation discovery

`verisys.evaluation.discover_evaluations(architecture, client)` accepts an existing
ArchitectureIR, not a repository path. It does not read repository files, import
repository modules, invoke verifiers, produce Evidence/Verdict, or change the UI.
The current HTTP API and Verify button are unchanged.

The LLM selects known evaluation IDs and supplied architecture subject IDs using
catalog-approved rationale codes. The catalog/server owns semantics, applicability,
execution support, MEDIUM default priority, required evidence and limitations.
Verification tools collect Evidence; the deterministic Judge produces Verdict.
See [the catalog](docs/evaluation-catalog.md#m45-core-discovery-contract).

Live discovery sends a **normalized architecture summary** (relative source
references, names, routes, tools, declared flows and limitations) to the configured
OpenAI provider. It does not send raw source, repository root, config values,
credentials, runtime measurements or verification results. Architecture labels
remain untrusted data, separate from instructions. The model has no tools.
Review architecture metadata sensitivity before deliberately enabling live use.

The OpenAI SDK is optional; fake-client discovery and M4 work without it:

```sh
.venv/bin/python -m pip install -e '.[test,discovery]'
```

Configure `OPENAI_API_KEY` outside this repository (for example, in your shell),
then set `VERISYS_DISCOVERY_MODEL` to a model supporting Responses structured
outputs. No model or universal temperature setting is hardcoded. SDK requests use
strict schema parsing, no tools, `store=False`, disabled input truncation, a
30-second timeout, no automatic retries and a 2048-token output budget; timeout
and output budget are adapter configuration fields.

The live test is **skipped in normal pytest**, requires explicit opt-in and runs
safe architecture analysis before discovery; it never executes verification:

```sh
VERISYS_LIVE_DISCOVERY=1 \
VERISYS_DISCOVERY_MODEL=your-structured-output-model \
VERISYS_LIVE_REPOSITORY=/absolute/path/to/ecommerce-ai-agent \
.venv/bin/python -m pytest tests/test_evaluation_live.py -s
```

There is no implicit fixture fallback. Missing credentials, provider errors,
refusals, incomplete output and invalid selections raise sanitized DiscoveryError,
not an empty recommendation list. Valid empty selections succeed. Empty complete
architecture can skip the provider; empty incomplete/truncated context fails
explicitly. Provider diagnostics are bounded metadata, not engineering Evidence
or verification Trace, and never retain raw response text or chain-of-thought.
