import type { ArchitectureGraph } from "./types";

// Illustrative mock, matching the M3A serialized example. No repository was read.
export const repositoryName = "documents-api";
export const architectureFixture: ArchitectureGraph = {
  nodes: [
    {
      id: "external:OpenAI:openai", type: "EXTERNAL_SERVICE", label: "OpenAI", subtitle: "openai",
      source_locations: [{ file: "app.py", line: 2, column: 0 }, { file: "app.py", line: 12, column: 0 }],
      metadata: { call_sites: [{ file: "app.py", line: 12, column: 0 }] },
    },
    {
      id: "framework:FastAPI", type: "FRAMEWORK", label: "FastAPI", subtitle: null,
      source_locations: [], metadata: {},
    },
    {
      id: "route:POST:%2Fdocuments:documents:app.py:10:0", type: "API_ROUTE", label: "POST /documents", subtitle: "documents",
      source_locations: [{ file: "app.py", line: 10, column: 0 }], metadata: {},
    },
  ],
  edges: [],
  limitations: [],
};
