import test from "node:test";
import assert from "node:assert/strict";
import { demoGraph } from "../lib/architecture/demo";
import { toSystemFlow } from "../lib/architecture/to-system-flow";
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

test("System Flow adapter is deterministic and preserves every grounded transition", () => {
  const flow = demoGraph.execution_flows![0];
  const original = JSON.stringify(flow);
  const adapted = toSystemFlow(flow, null);
  assert.deepEqual(adapted, toSystemFlow(flow, null));
  assert.equal(adapted.nodes.length, flow.steps.length);
  assert.equal(adapted.edges.length, flow.transitions.length);
  assert.deepEqual(adapted.edges.map(edge => edge.data!.transition), flow.transitions);
  assert.equal(adapted.edges.filter(edge => edge.data!.loop).length, 1);
  assert.equal(adapted.edges.filter(edge => edge.data!.lateral).length, 1);
  assert.ok(adapted.edges.every(edge => edge.data!.transition.source_locations.length > 0));
  assert.equal(JSON.stringify(flow), original);
  const entry = adapted.nodes.find(node => node.id === flow.trigger)!;
  assert.equal(entry.position.y, 0);
  assert.ok(adapted.nodes.filter(node => node.id !== flow.trigger).every(node => node.position.y > 0));
  assert.equal(toSystemFlow(flow, "transition:2").edges.filter(edge => edge.selected).length, 1);
});

test("Dependency adapter preserves previous component and import topology", () => {
  const flow = toReactFlow(demoGraph, null);
  assert.deepEqual(new Set(flow.nodes.map(node => node.id)), new Set(demoGraph.nodes.map(node => node.id)));
  assert.deepEqual(flow.edges.map(edge => [edge.source, edge.target]), demoGraph.edges.map(edge => [edge.source, edge.target]));
});

test("presentation aliases retain raw identities and align the main path", async () => {
  const { stepPresentation, conditionPresentation } = await import("../lib/architecture/to-system-flow");
  const flow = demoGraph.execution_flows![0];
  const raw = JSON.stringify(flow);
  const workflow = flow.steps.find(step => step.type === "WORKFLOW")!;
  assert.deepEqual(stepPresentation(workflow), { label: "Agent Workflow", subtitle: "LangGraph · build_graph" });
  assert.equal(stepPresentation(flow.steps.find(step => step.label === "Handler return")!).label, "Return to API");
  assert.deepEqual(flow.transitions.filter(edge => edge.condition).map(edge => conditionPresentation(edge.condition)), [
    { functionName: "should_use_tools", branch: "tools" }, { functionName: "should_use_tools", branch: "response" },
    { functionName: "after_tools", branch: "retry" }, { functionName: "after_tools", branch: "response" },
  ]);
  const adapted = toSystemFlow(flow, null);
  const spine = adapted.nodes.filter(node => node.data.step.type !== "TOOL_EXECUTION");
  assert.equal(new Set(spine.map(node => node.position.x)).size, 1);
  assert.ok(adapted.nodes.find(node => node.data.step.type === "TOOL_EXECUTION")!.position.x < spine[0].position.x);
  assert.equal(JSON.stringify(flow), raw);
});
