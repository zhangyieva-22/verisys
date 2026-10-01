import { MarkerType, type Edge, type Node } from "@xyflow/react";
import type { ArchitectureGraph, ArchitectureNode } from "./types";

export type ComponentNode = Node<{ architecture: ArchitectureNode }, "component">;
const compare = (a: { id: string }, b: { id: string }) => a.id < b.id ? -1 : a.id > b.id ? 1 : 0;

/** Layer only existing relationships. Geometry is presentation, never architecture inference. */
export function toReactFlow(graph: ArchitectureGraph, selectedId: string | null) {
  const ordered = [...graph.nodes].sort(compare);
  const ids = new Set(ordered.map(node => node.id));
  const relationships = [...graph.edges].sort(compare);
  const outgoing = new Map(ordered.map(node => [node.id, [] as string[]]));
  const incoming = new Map(ordered.map(node => [node.id, 0]));
  const connected = new Set<string>();
  for (const edge of relationships) {
    if (!ids.has(edge.source) || !ids.has(edge.target)) continue;
    outgoing.get(edge.source)!.push(edge.target);
    incoming.set(edge.target, incoming.get(edge.target)! + 1);
    connected.add(edge.source); connected.add(edge.target);
  }
  const rank = new Map(ordered.map(node => [node.id, 0]));
  const queue = ordered.filter(node => connected.has(node.id) && incoming.get(node.id) === 0).map(node => node.id);
  const visited = new Set<string>();
  for (let index = 0; index < queue.length; index++) {
    const id = queue[index]; visited.add(id);
    for (const target of outgoing.get(id)!) {
      rank.set(target, Math.max(rank.get(target)!, rank.get(id)! + 1));
      incoming.set(target, incoming.get(target)! - 1);
      if (incoming.get(target) === 0) queue.push(target);
    }
  }
  // Cyclic / downstream-of-cycle nodes use a stable fallback column; no inferred edges.
  const lastRank = Math.max(0, ...[...visited].map(id => rank.get(id)!));
  for (const node of ordered) if (connected.has(node.id) && !visited.has(node.id)) rank.set(node.id, lastRank + 1);
  const positions = new Map<string, { x: number; y: number }>();
  const maxRank = Math.max(0, ...ordered.filter(node => connected.has(node.id)).map(node => rank.get(node.id)!));
  for (let layer = maxRank; layer >= 0; layer--) {
    const members = ordered.filter(node => connected.has(node.id) && rank.get(node.id) === layer);
    const desiredX = (id: string) => {
      const children = outgoing.get(id)!.map(target => positions.get(target)).filter(value => value !== undefined);
      return children.length ? children.reduce((sum, point) => sum + point.x, 0) / children.length : 0;
    };
    members.sort((a, b) => desiredX(a.id) - desiredX(b.id) || compare(a, b));
    let nextX = 0;
    for (const node of members) {
      const x = Math.max(nextX, desiredX(node.id));
      positions.set(node.id, { x, y: layer * 125 }); nextX = x + 245;
    }
  }
  const observationY = connected.size ? Math.max(...[...positions.values()].map(point => point.y)) + 150 : 0;
  const ranks = { FRAMEWORK: 0, API_ROUTE: 1, EXTERNAL_SERVICE: 2, TOOL: 3, DATASTORE: 4, MODULE: 5 };
  const observations = ordered.filter(node => !connected.has(node.id)).sort((a, b) => ranks[a.type] - ranks[b.type] || compare(a, b));
  const columns = Math.min(3, Math.max(2, maxRank + 1));
  observations.forEach((node, index) => positions.set(node.id, { x: (index % columns) * 245, y: observationY + Math.floor(index / columns) * 125 }));
  const nodes: ComponentNode[] = ordered.map(node => ({
    id: node.id, type: "component", data: { architecture: node },
    position: positions.get(node.id)!, selected: node.id === selectedId,
    draggable: false, connectable: false,
    ariaLabel: `${node.label}, ${node.type.toLowerCase().replaceAll("_", " ")}`,
  }));
  const edges: Edge[] = relationships.map(edge => ({
    id: edge.id, source: edge.source, target: edge.target, label: edge.type,
    className: edge.source === selectedId || edge.target === selectedId ? "focused-relationship" : "",
    type: "smoothstep", animated: false, focusable: true,
    markerEnd: { type: MarkerType.ArrowClosed, color: "#8ca5ac", width: 16, height: 16 },
    style: { stroke: edge.source === selectedId || edge.target === selectedId ? "#b9e1d5" : "#647d87", strokeWidth: edge.source === selectedId || edge.target === selectedId ? 2 : 1 },
    labelStyle: { fill: "#c3cdd6", fontSize: 10, fontFamily: "monospace" },
    labelBgStyle: { fill: "#111b28" }, labelBgPadding: [7, 4], labelBgBorderRadius: 3,
  }));
  return { nodes, edges, observationY: observations.length ? observationY : null };
}
