import type { ArchitectureGraph, ArchitectureNode } from "./types";
import { toReactFlow, type ComponentNode } from "./to-react-flow";

export function isTestModule(node: ArchitectureNode) {
  return node.label.startsWith("tests.") || node.source_locations.some(source => source.file.startsWith("tests/"));
}

/** Display subset only; the complete DTO and its evidence remain untouched. */
export function toDependencyFlow(graph: ArchitectureGraph, selected: string | null) {
  const modules = graph.nodes.filter(node => node.type === "MODULE");
  const ids = new Set(modules.map(node => node.id));
  const imports = graph.edges.filter(edge => edge.type === "IMPORTS" && ids.has(edge.source) && ids.has(edge.target));
  const production = modules.filter(node => !isTestModule(node));
  const productionIds = new Set(production.map(node => node.id));
  const subset = { ...graph, nodes: modules, edges: imports };
  const adapted = toReactFlow(subset, selected);
  // Test imports remain rendered, but never determine production ranks/scale.
  const layout = toReactFlow({ ...graph, nodes: production, edges: imports.filter(edge => productionIds.has(edge.source) && productionIds.has(edge.target)) }, null);
  const positions = new Map(layout.nodes.map(node => [node.id, { x: node.position.x, y: node.position.y / 125 * 128 }]));
  const tests = modules.filter(isTestModule).sort((a, b) => a.id.localeCompare(b.id));
  tests.forEach((node, index) => {
    const y = index * 128;
    const siblings = [...positions.values()].filter(point => point.y === y);
    const x = Math.max(0, ...siblings.map(point => point.x)) + 270;
    positions.set(node.id, { x, y });
  });
  return { nodes: adapted.nodes.map(node => ({ ...node, position: positions.get(node.id)! })), edges: adapted.edges };
}

export function readableDependencyViewport(nodes: ComponentNode[], width: number) {
  const production = nodes.filter(node => !isTestModule(node.data.architecture));
  const primary = production.length ? production : nodes;
  const left = Math.min(0, ...primary.map(node => node.position.x));
  const right = Math.max(230, ...primary.map(node => node.position.x + 230));
  return { x: width / 2 - (left + right) / 2, y: 60, zoom: 1 };
}
