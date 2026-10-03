import test from "node:test";
import assert from "node:assert/strict";
import { demoGraph } from "../lib/architecture/demo";
import { toReactFlow } from "../lib/architecture/to-react-flow";

test("real snapshot keeps execution transitions distinct from imports", () => {
  const flow = demoGraph.execution_flows![0];
  assert.equal(flow.name, "POST /chat → build_graph");
  assert.equal(flow.transitions.length, 8);
  assert.deepEqual(flow.transitions.filter(edge => edge.condition).map(edge => edge.condition), ["should_use_tools: tools", "should_use_tools: response", "after_tools: retry", "after_tools: response"]);
  assert.equal(demoGraph.edges.length, 26);
  assert.ok(demoGraph.edges.every(edge => edge.type === "IMPORTS"));
  const tools = flow.steps.filter(step => step.type === "TOOL_EXECUTION");
  assert.equal(tools.length, 1);
  assert.equal(tools[0].candidate_tool_ids.length, 7);
  assert.ok(tools[0].candidate_tool_ids.every(id => demoGraph.nodes.some(node => node.id === id && node.type === "TOOL")));
  assert.ok(!flow.steps.some(step => demoGraph.nodes.some(node => node.id === step.component_id && ["DATASTORE", "EXTERNAL_SERVICE"].includes(node.type))));
});

test("Dependency adapter preserves previous component and import topology", () => {
  const flow = toReactFlow(demoGraph, null);
  assert.deepEqual(new Set(flow.nodes.map(node => node.id)), new Set(demoGraph.nodes.map(node => node.id)));
  assert.deepEqual(flow.edges.map(edge => [edge.source, edge.target]), demoGraph.edges.map(edge => [edge.source, edge.target]));
});
