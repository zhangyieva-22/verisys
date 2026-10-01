"use client";
import { createContext, useContext, useMemo } from "react";
import { Background, BackgroundVariant, BaseEdge, Controls, EdgeLabelRenderer, Handle, Position, ReactFlow, getSmoothStepPath, type EdgeProps, type NodeProps } from "@xyflow/react";
import { GitBranch, ArrowDown, X } from "lucide-react";
import type { ArchitectureGraph, ExecutionFlow, SourceLocation } from "@/lib/architecture/types";
import { toSystemFlow, stepPresentation, conditionPresentation, type FlowEdge, type FlowNode } from "@/lib/architecture/to-system-flow";

export function SourceList({ locations }: { locations: SourceLocation[] }) {
  return <div className="source-list">{locations.map(loc => <button className="source-reference" key={`${loc.file}:${loc.line}:${loc.column}`} title="Source navigation is not connected" onClick={event => { event.currentTarget.title = "Real source reference · navigation not connected"; }}><code>{loc.file}:{loc.line}</code><span>↗</span></button>)}</div>;
}
function ExecutionNode({ data, selected }: NodeProps<FlowNode>) {
  const step = data.step;
  const presentation = stepPresentation(step);
  const terminal = step.type === "EXIT" && step.label === "Handler return";
  return <div className={`execution-node ${selected ? "is-selected" : ""} ${step.type === "EXIT" ? "execution-exit" : ""} ${terminal ? "execution-return" : ""}`}>
    <Handle type="target" position={Position.Top} id="top-in" />
    <Handle type="source" position={Position.Bottom} id="bottom-out" />
    <Handle type="source" position={Position.Left} id="left-out" style={{ top: "65%" }} />
    <Handle type="target" position={Position.Left} id="left-in" style={{ top: "35%" }} />
    <Handle type="source" position={Position.Right} id="right-out" />
    {!terminal && <div className="execution-type">{step.type.replaceAll("_", " ")}</div>}
    <strong>{presentation.label}</strong>
    {!terminal && <small>{presentation.subtitle ?? `${step.source_locations.length} source references`}</small>}
  </div>;
}
const SelectTransition = createContext<(id: string) => void>(() => {});
function TransitionEdge(props: EdgeProps<FlowEdge>) {
  const onSelect = useContext(SelectTransition);
  const { sourceX, sourceY, targetX, targetY, data } = props;
  let path: string, labelX: number, labelY: number;
  if (data?.loop) {
    path = `M ${sourceX} ${sourceY} C ${sourceX - 155} ${sourceY + 95}, ${targetX - 155} ${targetY - 95}, ${targetX} ${targetY}`;
    labelX = sourceX - 125; labelY = (sourceY + targetY) / 2;
  } else {
    [path, labelX, labelY] = getSmoothStepPath({ sourceX, sourceY, targetX, targetY, sourcePosition: props.sourcePosition, targetPosition: props.targetPosition, borderRadius: 8 });
  }
  const label = conditionPresentation(data?.transition.condition ?? null)?.branch ?? (data?.transition.type === "INVOKE" ? "invoke" : data?.transition.type === "RETURN" ? "return" : null);
  return <><BaseEdge id={props.id} path={path} markerEnd={props.markerEnd} interactionWidth={24} style={{ stroke: props.selected ? "#b5e0d1" : "#7da7a0", strokeWidth: props.selected ? 2.5 : 1.6 }} />
    {label && <EdgeLabelRenderer><button className={`transition-label nodrag nopan ${props.selected ? "selected" : ""}`} style={{ transform: `translate(-50%, -50%) translate(${labelX}px,${labelY}px)` }} onClick={() => onSelect(props.id)}>{label}</button></EdgeLabelRenderer>}</>;
}
const nodeTypes = { execution: ExecutionNode };
const edgeTypes = { transition: TransitionEdge };

export function SystemFlowCanvas({ flow, selected, onSelect }: { flow: ExecutionFlow; selected: string | null; onSelect: (id: string | null) => void }) {
  const adapted = useMemo(() => toSystemFlow(flow, selected), [flow, selected]);
  return <SelectTransition.Provider value={onSelect}><ReactFlow nodes={adapted.nodes} edges={adapted.edges} nodeTypes={nodeTypes} edgeTypes={edgeTypes}
    onNodeClick={(_, node) => onSelect(node.id)} onEdgeClick={(_, edge) => onSelect(edge.id)} onPaneClick={() => onSelect(null)}
    nodesDraggable={false} nodesConnectable={false} edgesReconnectable={false} deleteKeyCode={null}
    fitView fitViewOptions={{ padding: 0.5, minZoom: 0.3, maxZoom: 1.6 }} minZoom={0.3} maxZoom={1.6}>
    <Background variant={BackgroundVariant.Dots} gap={22} size={1} color="#263345" />
    <Controls showInteractive={false} position="bottom-left" />
  </ReactFlow></SelectTransition.Provider>;
}

export function FlowInspector({ flow, graph, selected, onSelect }: { flow: ExecutionFlow; graph: ArchitectureGraph; selected: string | null; onSelect: (id: string | null) => void }) {
  const step = flow.steps.find(item => item.id === selected);
  const index = selected?.startsWith("transition:") ? Number(selected.slice(11)) : -1;
  const transition = flow.transitions[index];
  const condition = conditionPresentation(transition?.condition ?? null);
  const label = (id: string) => flow.steps.find(item => item.id === id)?.label ?? id;
  const related = step ? flow.transitions.map((item, index) => ({ item, index })).filter(({ item }) => item.source === step.id || item.target === step.id) : [];
  return <aside className="inspector" aria-label="Execution flow inspector"><div className="panel-heading">Inspector<button className="icon-button" onClick={() => onSelect(null)} aria-label="Clear selection"><X size={16} /></button></div><div className="inspector-content">
    <div className="inspector-identity"><div className="inspector-icon"><GitBranch size={23} /></div><div><h2>{step?.type === "TOOL_EXECUTION" ? "Tool Execution" : step?.label ?? (transition ? "Transition" : "System Flow")}</h2><span className="eyebrow">{step?.type.replaceAll("_", " ") ?? (transition ? transition.type : "SOURCE-DECLARED FLOW")}</span></div></div>
    <p className="section-description">Possible paths declared in source. No execution or condition outcome has been observed.</p>
    {transition && <section><h3>DECLARED TRANSITION</h3><div className="transition-detail"><code>{label(transition.source)}</code><ArrowDown size={15} /><code>{label(transition.target)}</code></div>{condition && <><dl className="facts"><div><dt>Condition function</dt><dd><code>{condition.functionName ?? "Not specified"}</code></dd></div><div><dt>Branch value</dt><dd><code>{condition.branch}</code></dd></div></dl><p><code>{transition.condition}</code></p></>}<h3>SOURCE EVIDENCE</h3><SourceList locations={transition.source_locations} /></section>}
    {step && <section><h3>SOURCE EVIDENCE <span>{step.source_locations.length}</span></h3><SourceList locations={step.source_locations} /></section>}
    {step?.candidate_tool_ids.length ? <section><h3>CANDIDATE TOOLS <span>{step.candidate_tool_ids.length}</span></h3><p className="section-description">Source-grounded candidate set. No execution order or per-request selection is implied.</p>{step.candidate_tool_ids.map(id => { const tool = graph.nodes.find(node => node.id === id); return tool && <div className="candidate-tool" key={id}><code>{tool.label}</code><SourceList locations={tool.source_locations} /></div>; })}</section> : null}
    {related.length > 0 && <section><h3>TRANSITIONS <span>{related.length}</span></h3>{related.map(({ item, index }) => <button className="flow-transition-reference" key={index} onClick={() => onSelect(`transition:${index}`)}><code>{label(item.source)} → {label(item.target)}</code><span>{item.condition ?? item.type}</span></button>)}</section>}
    {!step && !transition && <section><h3>FLOW SOURCE EVIDENCE</h3><SourceList locations={flow.source_locations} /></section>}
    <section><h3>EXTRACTION LIMITATIONS</h3>{flow.limitations.map(item => <p className="section-description" key={item}>{item}</p>)}</section>
  </div></aside>;
}
