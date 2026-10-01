"use client";
import { useMemo, useRef, useState } from "react";
import { Background, BackgroundVariant, Controls, Panel, ReactFlow, type ReactFlowInstance } from "@xyflow/react";
import type { ArchitectureGraph } from "@/lib/architecture/types";
import { toDependencyFlow, readableDependencyViewport } from "@/lib/architecture/to-dependency-flow";
import type { ComponentNode } from "@/lib/architecture/to-react-flow";
import { ArchitectureNode } from "./ArchitectureNode";

const nodeTypes = { component: ArchitectureNode };
export function DependencyCanvas({ graph, selected, onSelect }: { graph: ArchitectureGraph; selected: string | null; onSelect: (id: string | null) => void }) {
  const flow = useMemo(() => toDependencyFlow(graph, selected), [graph, selected]);
  const container = useRef<HTMLDivElement>(null);
  const [instance, setInstance] = useState<ReactFlowInstance<ComponentNode> | null>(null);
  const reset = (api = instance) => api?.setViewport(readableDependencyViewport(flow.nodes, container.current?.clientWidth ?? 900), { duration: 0 });
  return <div ref={container} className="dependency-canvas">
    <ReactFlow nodes={flow.nodes} edges={flow.edges} nodeTypes={nodeTypes}
      onInit={api => { setInstance(api); void reset(api); }}
      onNodeClick={(_, node) => onSelect(node.id)} onPaneClick={() => onSelect(null)}
      nodesDraggable={false} nodesConnectable={false} edgesReconnectable={false} deleteKeyCode={null}
      selectionOnDrag={false} defaultViewport={{ x: 0, y: 60, zoom: 1 }} minZoom={0.2} maxZoom={1.6}>
      <Panel position="top-right"><div className="dependency-view-actions"><button onClick={() => instance?.fitView({ padding: 0.1, minZoom: 0.2, maxZoom: 1 })}>Fit graph</button><button onClick={() => reset()}>Reset view</button></div></Panel>
      <Background variant={BackgroundVariant.Dots} gap={22} size={1} color="#263345" />
      <Controls showInteractive={false} showFitView={false} position="bottom-left" />
    </ReactFlow>
  </div>;
}
