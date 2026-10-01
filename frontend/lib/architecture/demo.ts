import graph from "./ecommerce-agent.graph.json";
import type { ArchitectureGraph } from "./types";

/** Real offline output of discovery -> analyzer -> graph. No live API. */
export const demoGraph = graph as ArchitectureGraph;
export const repositoryName = "m-peker/ecommerce-ai-agent";
export const repositoryCommit = "3d38d5ab7fa0f27bd5c28488afa354abaf2577b4";

export function initialSelection(graph: ArchitectureGraph): string | null {
  const ordered = [...graph.nodes].sort((a, b) => a.id.localeCompare(b.id, "en"));
  return (ordered.find(node => node.type === "API_ROUTE" && node.label === "POST /chat") ?? ordered.find(node => node.type === "API_ROUTE") ?? ordered[0])?.id ?? null;
}
