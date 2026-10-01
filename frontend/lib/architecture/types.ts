/** DTO mirrors M3A's Pydantic JSON; presentation geometry stays in the adapter. */
export type SourceLocation = { file: string; line: number; column: number | null };
export type NodeType = "FRAMEWORK" | "API_ROUTE" | "EXTERNAL_SERVICE" | "MODULE" | "TOOL" | "DATASTORE";
export type EdgeType = "CONTAINS" | "IMPORTS" | "CALLS";
export type JsonValue = string | number | boolean | null | JsonValue[] | { [key: string]: JsonValue };
export type ArchitectureNode = {
  id: string;
  type: NodeType;
  label: string;
  subtitle: string | null;
  source_locations: SourceLocation[];
  metadata: Record<string, JsonValue>;
};
export type ArchitectureEdge = {
  id: string;
  source: string;
  target: string;
  type: EdgeType;
  source_locations: SourceLocation[];
};
export type ArchitectureGraph = {
  nodes: ArchitectureNode[];
  edges: ArchitectureEdge[];
  limitations: string[];
  execution_flows?: ExecutionFlow[];
};

/** Read the existing M3A call_sites metadata without conflating presence sources. */
export function callSites(node: ArchitectureNode): SourceLocation[] {
  const value = node.metadata.call_sites;
  if (!Array.isArray(value)) return [];
  return value.filter((item): item is SourceLocation =>
    typeof item === "object" && item !== null && !Array.isArray(item) &&
    typeof item.file === "string" && typeof item.line === "number" &&
    Number.isInteger(item.line) && item.line >= 1 &&
    (item.column === null || (typeof item.column === "number" && Number.isInteger(item.column) && item.column >= 0))
  );
}

/** Possible source-declared control flow, separate from component/import topology. */
export type ExecutionStep = {
  id: string; type: "ENTRY" | "WORKFLOW" | "WORKFLOW_STEP" | "TOOL_EXECUTION" | "EXIT";
  label: string; component_id: string | null; source_locations: SourceLocation[];
  candidate_tool_ids: string[];
};
export type ExecutionTransition = {
  source: string; target: string; type: "INVOKE" | "ENTRY" | "NEXT" | "CONDITIONAL" | "RETURN";
  condition: string | null; source_locations: SourceLocation[];
};
export type ExecutionFlow = {
  id: string; name: string; trigger: string | null; steps: ExecutionStep[];
  transitions: ExecutionTransition[]; source_locations: SourceLocation[]; limitations: string[];
};
