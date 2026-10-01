import test from "node:test";
import assert from "node:assert/strict";
import { demoGraph } from "../lib/architecture/demo";
import { toDependencyFlow, readableDependencyViewport, isTestModule } from "../lib/architecture/to-dependency-flow";

test("dependency presentation renders only 14 modules and all 26 grounded imports", () => {
  const before = JSON.stringify(demoGraph);
  const flow = toDependencyFlow(demoGraph, null);
  assert.equal(flow.nodes.length, 14);
  assert.equal(flow.edges.length, 26);
  assert.ok(flow.nodes.every(node => node.data.architecture.type === "MODULE"));
  assert.ok(flow.edges.every(edge => edge.label === "IMPORTS"));
  assert.deepEqual(new Set(flow.edges.map(edge => edge.id)), new Set(demoGraph.edges.map(edge => edge.id)));
  assert.equal(demoGraph.nodes.length, 26);
  assert.equal(JSON.stringify(demoGraph), before);
  assert.deepEqual(toDependencyFlow({ ...demoGraph, nodes: [...demoGraph.nodes].reverse(), edges: [...demoGraph.edges].reverse() }, null), flow);
  const positions = new Map(flow.nodes.map(node => [node.id, node.position]));
  for (const edge of flow.edges.filter(edge => !isTestModule(flow.nodes.find(node => node.id === edge.source)!.data.architecture))) {
    assert.ok(positions.get(edge.source)!.y < positions.get(edge.target)!.y);
  }
});

test("test imports do not change production positions or readable default zoom", () => {
  const flow = toDependencyFlow(demoGraph, null);
  const production = demoGraph.nodes.filter(node => node.type === "MODULE" && !isTestModule(node));
  const ids = new Set(production.map(node => node.id));
  const withoutTests = toDependencyFlow({ ...demoGraph, nodes: production, edges: demoGraph.edges.filter(edge => ids.has(edge.source) && ids.has(edge.target)) }, null);
  assert.deepEqual(flow.nodes.filter(node => ids.has(node.id)).map(node => [node.id, node.position]), withoutTests.nodes.map(node => [node.id, node.position]));
  assert.deepEqual(readableDependencyViewport(flow.nodes, 930), readableDependencyViewport(withoutTests.nodes, 930));
  assert.equal(readableDependencyViewport(flow.nodes, 930).zoom, 1);
  const selected = production[0].id;
  assert.deepEqual(toDependencyFlow(demoGraph, selected).nodes.filter(node => node.selected).map(node => node.id), [selected]);
});

test("filter excludes non-import edges and handles isolated modules / empty graph", () => {
  const module = demoGraph.nodes.find(node => node.type === "MODULE")!;
  const service = demoGraph.nodes.find(node => node.type === "EXTERNAL_SERVICE")!;
  const flow = toDependencyFlow({ nodes: [module, service], edges: [{ id: "call", source: module.id, target: service.id, type: "CALLS", source_locations: [] }], limitations: [] }, null);
  assert.equal(flow.nodes.length, 1);
  assert.equal(flow.edges.length, 0);
  assert.ok(Number.isFinite(flow.nodes[0].position.y));
  assert.deepEqual(toDependencyFlow({ nodes: [], edges: [], limitations: [] }, null), { nodes: [], edges: [] });
});
