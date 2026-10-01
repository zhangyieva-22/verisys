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
repository history, accounts or verification execution is implemented.

System Flow uses `graph.execution_flows`; Dependency View filters the returned
graph to MODULE + IMPORTS without changing the DTO. Inspectors display actual
source locations and limitations. Repositories without a supported flow remain
valid. Repository names come from backend metadata, never the test snapshot.

The ecommerce snapshot for commit
`3d38d5ab7fa0f27bd5c28488afa354abaf2577b4` and other fixtures remain available
for tests; they are not imported by the production workspace.

```sh
npm run typecheck
npm test
npm run build
```
