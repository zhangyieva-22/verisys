import type { ArchitectureGraph } from "./types";
export function initialSelection(graph: ArchitectureGraph): string | null {
  const ordered = [...graph.nodes].sort((a, b) => a.id.localeCompare(b.id, "en"));
  return (ordered.find(node => node.type === "API_ROUTE" && node.label === "POST /chat") ?? ordered.find(node => node.type === "API_ROUTE") ?? ordered[0])?.id ?? null;
}
