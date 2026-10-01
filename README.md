# Verisys

Architecture-aware engineering verification, currently providing safe local
Python architecture analysis and a source-grounded architecture workspace.
Verification execution is a later milestone.

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
