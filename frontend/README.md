# Verisys frontend — M3B

The workspace currently displays a real offline ArchitectureGraph snapshot from
m-peker/ecommerce-ai-agent, revision 3d38d5ab7fa0f27bd5c28488afa354abaf2577b4.
It was generated with the bounded Discovery → Analyzer → Projection pipeline.
No backend/API is connected; Analyze remains disabled. The original mock fixture
is retained for adapter tests.

The M2.6 snapshot preserves 26 nodes (14 MODULE, 7 TOOL, 2 API_ROUTE,
1 FRAMEWORK, 1 EXTERNAL_SERVICE, 1 DATASTORE) and the original 26 source-backed
IMPORTS edges. ChatOpenAI presence, seven bare @tool functions and sqlite3.connect
are deterministic source facts. Their independent nodes imply no runtime edges.
POST /chat remains the decorator literal; mounted prefix composition and Langfuse
semantics remain unsupported. A separate source-declared execution flow links
POST /chat → build_graph / START → triage → conditional tools / response → END
→ handler return. Tool Execution shows seven candidates in the Inspector, not
seven ordered execution steps. Conditions retain their exact source-defined labels.
OpenAI and SQLite remain under Other detected components with no execution links. The OpenAI wrapper has no
supported concrete API call_sites; constructors are presence references only.
All 40 limitations are accessible below the graph. Labels retain their complete
source identity. This snapshot was generated statically without executing the repo.

With Node.js 20.9+ and npm:

```sh
cd frontend
npm ci
npm run dev
```

Open http://127.0.0.1:3000. System Flow is the default. Select a step or transition to inspect its source
proof; select Tool Execution to inspect the candidate set. Dependency View keeps
the existing component nodes and IMPORTS edges. Neither view represents a runtime trace.
Verification remains an M4 placeholder for external-service nodes; the wrapper presence node does not imply supported verification execution. Source navigation
is not connected.

```sh
npm run typecheck
npm test
npm run build
```

`lib/architecture/ecommerce-agent.graph.json` is the actual serialized projection;
`demo.ts` labels its provenance; `to-react-flow.ts` and `to-system-flow.ts` own presentation geometry.
No domain relationships are derived by the UI. The external repository was not changed or executed. The extractor
reads already safely parsed ASTs without importing repository modules. No M3C integration is included.
