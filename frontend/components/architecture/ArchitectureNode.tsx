import { Boxes, Braces, Database, Wrench, FileCode2, Globe2, type LucideIcon } from "lucide-react";
import { Handle, Position, type NodeProps } from "@xyflow/react";
import type { ComponentNode } from "@/lib/architecture/to-react-flow";
import { callSites, type NodeType } from "@/lib/architecture/types";

export const nodePresentation: Record<NodeType, { label: string; icon: LucideIcon }> = {
  FRAMEWORK: { label: "Framework", icon: Boxes },
  API_ROUTE: { label: "API route", icon: Braces },
  EXTERNAL_SERVICE: { label: "External service", icon: Globe2 },
  TOOL: { label: "Tool", icon: Wrench },
  DATASTORE: { label: "Datastore", icon: Database },
  MODULE: { label: "Module", icon: FileCode2 },
};

export function ArchitectureNode({ data, selected }: NodeProps<ComponentNode>) {
  const node = data.architecture;
  const { label, icon: Icon } = nodePresentation[node.type];
  const isTest = node.type === "MODULE" && (node.label.startsWith("tests.") || node.source_locations.some(source => source.file.startsWith("tests/")));
  const calls = callSites(node).length;
  const source = node.source_locations[0];
  const detail = node.type === "EXTERNAL_SERVICE"
    ? `${calls} detected API call ${calls === 1 ? "site" : "sites"}`
    : node.type === "MODULE" ? `${node.source_locations.length} source references` : source ? `${source.file}:${source.line}` : "Source location unavailable";
  return (
    <div className={`architecture-node ${selected ? "is-selected" : ""} ${isTest ? "is-test" : ""}`}>
      <Handle type="target" position={Position.Top} className="inspection-handle" />
      <div className="node-top"><span className={`node-icon ${node.type.toLowerCase()}`}><Icon size={19} /></span><span>{isTest ? "Test module · tests/" : label}</span></div>
      <div className="node-title" title={node.label}>{node.type === "MODULE" ? <><span className="module-prefix">{node.label.split(".").slice(0, -1).join(".")}.</span><span className="module-name">{node.label.split(".").at(-1)}</span></> : node.label}</div>
      {node.subtitle && <div className="node-subtitle">{node.subtitle}</div>}
      <div className="node-footer"><span className="source-dot" />{detail}</div>
      <Handle type="source" position={Position.Bottom} className="inspection-handle" />
    </div>
  );
}
