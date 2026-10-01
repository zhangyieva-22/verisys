"use client";

import { useState } from "react";
import { Info, MousePointer2 } from "lucide-react";
import { demoGraph, repositoryCommit, initialSelection } from "@/lib/architecture/demo";
import { AppHeader } from "../layout/AppHeader";
import { AppSidebar } from "../layout/AppSidebar";
import { DependencyCanvas } from "./DependencyCanvas";
import { ArchitectureInspector } from "./ArchitectureInspector";
import { SystemFlowCanvas, FlowInspector } from "./SystemFlow";


export function ArchitectureWorkspace() {
  const executionFlows = demoGraph.execution_flows ?? [];
  const [view, setView] = useState<"system" | "dependency">("system");
  const [flowId, setFlowId] = useState(executionFlows[0]?.id);
  const execution = executionFlows.find(item => item.id === flowId) ?? executionFlows[0];
  const [flowSelection, setFlowSelection] = useState<string | null>(execution?.trigger ?? null);
  const otherComponents = demoGraph.nodes.filter(node => ["EXTERNAL_SERVICE", "DATASTORE"].includes(node.type) && !execution?.steps.some(step => step.component_id === node.id));
  const [inspectedOther, setInspectedOther] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(() => initialSelection(demoGraph));
  const selected = demoGraph.nodes.find(node => node.id === selectedId) ?? null;
  const routes = demoGraph.nodes.filter(node => node.type === "API_ROUTE").length;
  const modules = demoGraph.nodes.filter(node => node.type === "MODULE").length;
  const services = demoGraph.nodes.filter(node => node.type === "EXTERNAL_SERVICE").length;
  return <div className="app-shell">
    <AppHeader />
    <div className="workspace-layout"><AppSidebar />
      <main className="architecture-workspace">
        <div className="workspace-breadcrumb">Workspace<span>/</span><strong>Architecture</strong></div>
        <div className="architecture-heading"><div><div className="eyebrow">SYSTEM UNDERSTANDING</div><h1>Architecture</h1><p>Architecture reflects source-grounded relationships detected by Verisys.</p></div><div className="architecture-view-switch" aria-label="Architecture view"><button className={view === "system" ? "active" : ""} onClick={() => { setView("system"); setInspectedOther(null); }}>System Flow</button><button className={view === "dependency" ? "active" : ""} onClick={() => { setView("dependency"); setInspectedOther(null); if (!demoGraph.nodes.some(node => node.id === selectedId && node.type === "MODULE")) setSelectedId(null); }}>Dependency View</button></div></div>
        <div className="architecture-summary"><span><strong>{demoGraph.nodes.length}</strong> components</span><i /><span><strong>{routes}</strong> API {routes === 1 ? "route" : "routes"}</span><i /><span><strong>{services}</strong> external {services === 1 ? "service" : "services"}</span><i /><span><strong>{modules}</strong> modules</span><i /><span><strong>{demoGraph.edges.length}</strong> relationships</span></div>
        <div className="graph-evidence-note"><Info size={14} />Only evidence-backed relationships are connected.<span>Real source snapshot</span></div>
        <div className="graph-canvas" aria-label="Architecture inspection graph">
          {view === "system" ? <>
            <div className="graph-legend"><span>↓ Execution direction</span><span>Source-declared possible paths · not runtime tracing</span>{executionFlows.length > 1 && <select aria-label="Execution flow" value={flowId} onChange={event => { const next = executionFlows.find(item => item.id === event.target.value)!; setFlowId(next.id); setFlowSelection(next.trigger); setInspectedOther(null); }}>{executionFlows.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select>}</div>
            {execution ? <SystemFlowCanvas key={execution.id} flow={execution} selected={flowSelection} onSelect={id => { setFlowSelection(id); setInspectedOther(null); }} /> : <div className="flow-empty">No supported source-declared execution flow was detected. Inspect structural dependencies in Dependency View.</div>}
          </> : <>
          <div className="graph-legend"><span><i className="legend-module" />Source-backed dependencies</span><span><i className="legend-test" />Test modules</span><span>Arrows indicate imports, not runtime calls</span></div>
          <DependencyCanvas graph={demoGraph} selected={selectedId} onSelect={setSelectedId} />
          </>}
          <div className="canvas-caption"><MousePointer2 size={13} />{view === "system" ? "Select a step or transition to inspect its source evidence" : "Arrows represent imports · select to inspect"}</div>
        </div>
        {view === "system" && otherComponents.length > 0 && <div className="other-components"><div><strong>Other detected components</strong><span>Participation in this execution flow is not proven.</span></div>{otherComponents.map(node => <button className={inspectedOther === node.id ? "selected" : ""} key={node.id} onClick={() => setInspectedOther(node.id)}>{node.label}<code>{node.subtitle}</code></button>)}</div>}
        <footer className="workspace-status"><span><span className="neutral-dot" />Snapshot · {repositoryCommit.slice(0, 7)}</span><span>{view === "system" ? `${execution?.transitions.length ?? 0} source-declared transitions` : `${demoGraph.edges.length} structural dependencies`} · read-only</span></footer>
        {demoGraph.limitations.length > 0 && <details className="graph-limitations"><summary>Analysis limitations ({demoGraph.limitations.length}) · incomplete call-site coverage</summary>{demoGraph.limitations.map(item => <p key={item}>{item}</p>)}</details>}
      </main>
      {view === "system" && execution && !inspectedOther ? <FlowInspector flow={execution} graph={demoGraph} selected={flowSelection} onSelect={setFlowSelection} /> : <ArchitectureInspector key={selectedId ?? "empty"} node={inspectedOther ? demoGraph.nodes.find(node => node.id === inspectedOther) ?? null : selected} graph={demoGraph} onSelect={setSelectedId} onClear={() => { setSelectedId(null); setInspectedOther(null); }} />}
    </div>
  </div>;
}
