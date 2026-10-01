import { MarkerType, type Edge, type Node } from "@xyflow/react";
import type { ExecutionFlow, ExecutionStep, ExecutionTransition } from "./types";

export type FlowNode = Node<{ step: ExecutionStep }, "execution">;
export type FlowEdge = Edge<{ transition: ExecutionTransition; index: number; loop: boolean; lateral: boolean }, "transition">;

/** Deterministic presentation only. Never invent transitions or tool ordering. */
export function toSystemFlow(flow: ExecutionFlow, selected: string | null) {
  const depth = new Map<string, number>();
  if (flow.trigger) depth.set(flow.trigger, 0);
  const queue = flow.trigger ? [flow.trigger] : [];
  for (let i = 0; i < queue.length; i++) {
    for (const edge of flow.transitions.filter(edge => edge.source === queue[i])) {
      if (!depth.has(edge.target)) { depth.set(edge.target, depth.get(edge.source)! + 1); queue.push(edge.target); }
    }
  }
  const rows = new Map<number, ExecutionStep[]>();
  for (const step of flow.steps) {
    const row = depth.get(step.id) ?? flow.steps.length;
    rows.set(row, [...(rows.get(row) ?? []), step]);
  }
  const nodes: FlowNode[] = flow.steps.map(step => {
    const row = depth.get(step.id) ?? flow.steps.length;
    const peers = rows.get(row)!;
    // Keep non-tool stages on the central spine; tools are an alternate branch.
    const primary = peers.find(item => item.type !== "TOOL_EXECUTION") ?? peers[0];
    const alternate = peers.filter(item => item !== primary).indexOf(step);
    return { id: step.id, type: "execution", selected: selected === step.id, data: { step },
      position: { x: step === primary ? 480 : 480 - (alternate + 1) * 390, y: row * 98 } };
  });
  const edges: FlowEdge[] = flow.transitions.map((transition, index) => {
    const loop = transition.source === transition.target;
    const lateral = !loop && depth.get(transition.source) === depth.get(transition.target);
    return { id: `transition:${index}`, type: "transition", source: transition.source, target: transition.target,
      sourceHandle: loop ? "left-out" : lateral ? "right-out" : "bottom-out",
      targetHandle: loop ? "left-in" : lateral ? "left-in" : "top-in",
      selected: selected === `transition:${index}`,
      markerEnd: { type: MarkerType.ArrowClosed, width: 18, height: 18, color: "#7da7a0" },
      data: { transition, index, loop, lateral } };
  });
  return { nodes, edges };
}

/** Display aliases only: implementation identity stays in step / transition data. */
export function stepPresentation(step: ExecutionStep) {
  if (step.type === "WORKFLOW") {
    const implementation = step.label.replace(/ · START$/, "");
    return { label: "Agent Workflow", subtitle: `LangGraph · ${implementation}` };
  }
  if (step.type === "TOOL_EXECUTION") return { label: "Tool Execution", subtitle: `${step.candidate_tool_ids.length} candidate tools` };
  if (step.type === "EXIT" && step.label === "Handler return") return { label: "Return to API", subtitle: null };
  return { label: step.label, subtitle: null };
}

export function conditionPresentation(condition: string | null) {
  if (!condition) return null;
  const separator = condition.indexOf(": ");
  return separator < 0 ? { functionName: null, branch: condition } : {
    functionName: condition.slice(0, separator), branch: condition.slice(separator + 2),
  };
}
