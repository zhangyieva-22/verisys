import assert from "node:assert/strict";
import { test } from "node:test";
import { architectureFixture } from "../lib/architecture/fixture";
import { toReactFlow } from "../lib/architecture/to-react-flow";
import { callSites, type ArchitectureGraph } from "../lib/architecture/types";

test("golden fixture keeps service presence distinct from concrete calls", () => {
  const service = architectureFixture.nodes.find(n => n.type === "EXTERNAL_SERVICE")!;
  assert.equal(service.source_locations.length, 2);
  assert.deepEqual(callSites(service), [{ file: "app.py", line: 12, column: 0 }]);
  assert.equal(toReactFlow(architectureFixture, null).edges.length, 0);
});

test("adapter preserves identities, selects nodes, and never mutates DTO", () => {
  const before = JSON.stringify(architectureFixture);
  const selected = architectureFixture.nodes[0].id;
  const flow = toReactFlow(architectureFixture, selected);
  assert.deepEqual(new Set(flow.nodes.map(n => n.id)), new Set(architectureFixture.nodes.map(n => n.id)));
  assert.deepEqual(flow.nodes.filter(n => n.selected).map(n => n.id), [selected]);
  assert.ok(flow.nodes.every(n => !n.draggable && !n.connectable));
  assert.equal(JSON.stringify(architectureFixture), before);
});

test("adapter copies only provided relationships, including modules", () => {
  const graph: ArchitectureGraph = {
    nodes: ["app.api", "app.llm"].map(label => ({ id: `module:${label}`, type: "MODULE", label, subtitle: null, source_locations: [], metadata: {} })),
    edges: [{ id: "imports:app.api:app.llm", source: "module:app.api", target: "module:app.llm", type: "IMPORTS", source_locations: [{ file: "app/api.py", line: 2, column: 0 }] }], limitations: [],
  };
  const flow = toReactFlow(graph, null);
  assert.equal(flow.edges.length, 1);
  assert.equal(flow.edges[0].id, graph.edges[0].id);
  assert.equal(flow.edges[0].source, graph.edges[0].source);
  assert.equal(flow.edges[0].target, graph.edges[0].target);
  assert.equal(flow.edges[0].label, "IMPORTS");
});

test("layout is deterministic regardless of DTO order", () => {
  const reversed = { ...architectureFixture, nodes: [...architectureFixture.nodes].reverse() };
  assert.deepEqual(toReactFlow(reversed, null), toReactFlow(architectureFixture, null));
});

test("unknown or malformed call metadata is not presented as a call", () => {
  const node = { ...architectureFixture.nodes[0], metadata: { call_sites: [null, "app.py:2", { file: "app.py", line: 0, column: null }] } };
  assert.deepEqual(callSites(node), []);
});


test("real snapshot renders grounded relationships with visible incompleteness", async () => {
  const { demoGraph } = await import("../lib/architecture/demo");
  const flow = toReactFlow(demoGraph, "external:OpenAI:openai");
  assert.equal(flow.nodes.length, 26);
  assert.equal(flow.edges.length, 26);
  assert.ok(flow.edges.every(edge => edge.label === "IMPORTS"));
  assert.equal(demoGraph.limitations.length, 40);
  assert.equal(demoGraph.nodes.filter(n => n.type === "EXTERNAL_SERVICE").length, 1);
  const ids = new Set(flow.nodes.map(n => n.id));
  assert.ok(flow.edges.every(edge => ids.has(edge.source) && ids.has(edge.target)));
});

test("dependencies flow top to bottom and unconnected observations stay separate", async () => {
  const { demoGraph } = await import("../lib/architecture/demo");
  const flow = toReactFlow(demoGraph, null);
  const nodes = new Map(flow.nodes.map(node => [node.id, node]));
  const connected = new Set(flow.edges.flatMap(edge => [edge.source, edge.target]));
  for (const edge of flow.edges) {
    assert.ok(nodes.get(edge.source)!.position.y < nodes.get(edge.target)!.position.y);
    assert.ok(edge.markerEnd);
  }
  const bottom = Math.max(...flow.nodes.filter(node => connected.has(node.id)).map(node => node.position.y + 120));
  assert.ok(flow.nodes.filter(node => !connected.has(node.id)).every(node => node.position.y > bottom));
  for (let i = 0; i < flow.nodes.length; i++) for (let j = i + 1; j < flow.nodes.length; j++) {
    const a = flow.nodes[i].position, b = flow.nodes[j].position;
    assert.ok(Math.abs(a.x - b.x) >= 210 || Math.abs(a.y - b.y) >= 120, "nodes must not overlap");
  }
  assert.deepEqual(toReactFlow({ ...demoGraph, nodes: [...demoGraph.nodes].reverse(), edges: [...demoGraph.edges].reverse() }, null), flow);
});

test("cycles terminate deterministically with unchanged topology", () => {
  const nodes: ArchitectureGraph["nodes"] = ["a", "b", "c"].map(id => ({id, type: "MODULE", label: id, subtitle: null, source_locations: [], metadata: {}}));
  const edges: ArchitectureGraph["edges"] = [["a", "b"], ["b", "a"], ["b", "c"]].map(([source, target]) => ({id: `${source}-${target}`, source, target, type: "IMPORTS", source_locations: []}));
  const graph = {nodes, edges, limitations: []};
  const flow = toReactFlow(graph, null);
  assert.equal(flow.edges.length, 3);
  assert.ok(flow.nodes.every(node => Number.isFinite(node.position.x) && Number.isFinite(node.position.y)));
  assert.deepEqual(toReactFlow({...graph, nodes: [...nodes].reverse(), edges: [...edges].reverse()}, null), flow);
});


test("demo selects a real chat route with deterministic empty-graph fallback", async () => {
  const { demoGraph, initialSelection } = await import("../lib/architecture/demo");
  assert.equal(demoGraph.nodes.find(node => node.id === initialSelection(demoGraph))?.label, "POST /chat");
  assert.equal(initialSelection({nodes: [], edges: [], limitations: []}), null);
  assert.equal(initialSelection({...demoGraph, nodes: [...demoGraph.nodes].reverse()}), initialSelection(demoGraph));
});

test("real demo adapter preserves every edge and its underlying evidence", async () => {
  const { demoGraph } = await import("../lib/architecture/demo");
  const before = JSON.stringify(demoGraph);
  const flow = toReactFlow(demoGraph, null);
  assert.deepEqual(flow.edges.map(edge => [edge.id, edge.source, edge.target, edge.label]), [...demoGraph.edges].sort((a,b) => a.id < b.id ? -1 : a.id > b.id ? 1 : 0).map(edge => [edge.id, edge.source, edge.target, edge.type]));
  assert.deepEqual(flow.nodes.map(node => node.data.architecture), [...demoGraph.nodes].sort((a,b) => a.id < b.id ? -1 : a.id > b.id ? 1 : 0));
  assert.equal(JSON.stringify(demoGraph), before);
  const width = Math.max(...flow.nodes.map(node => node.position.x + 210)) - Math.min(...flow.nodes.map(node => node.position.x));
  assert.ok(width < 1100, "compact layout must avoid the previous 2088px span");
});


test("semantic node types retain grounded locations and wrapper call separation", async () => {
  const { demoGraph } = await import("../lib/architecture/demo");
  assert.equal(demoGraph.nodes.filter(n => n.type === "TOOL").length, 7);
  const store = demoGraph.nodes.find(n => n.type === "DATASTORE")!;
  assert.equal(store.label, "SQLite");
  assert.equal(store.source_locations[0].line, 20);
  const service = demoGraph.nodes.find(n => n.type === "EXTERNAL_SERVICE")!;
  assert.equal(service.subtitle, "langchain_openai");
  assert.deepEqual(callSites(service), []);
  assert.ok(demoGraph.nodes.filter(n => n.type === "TOOL").every(n => n.source_locations.length > 0));
});
