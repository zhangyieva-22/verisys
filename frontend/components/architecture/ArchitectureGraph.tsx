"use client";

import { useReducer, useState } from "react";
import { Info, MousePointer2 } from "lucide-react";
import { initialSelection } from "@/lib/architecture/selection";
import { analyzeRepository, analysisReducer, emptyAnalysis } from "@/lib/architecture/analysis-client";
import type { ArchitectureGraph } from "@/lib/architecture/types";
import { RepositoryInput } from "./RepositoryInput";
import { AppHeader } from "../layout/AppHeader";
import { AppSidebar } from "../layout/AppSidebar";
import { DependencyCanvas } from "./DependencyCanvas";
import { ArchitectureInspector } from "./ArchitectureInspector";
import { SystemFlowCanvas, FlowInspector } from "./SystemFlow";


const emptyGraph: ArchitectureGraph = { nodes: [], edges: [], execution_flows: [], limitations: [] };
export function ArchitectureWorkspace() {
  const [analysis, dispatch] = useReducer(analysisReducer, emptyAnalysis);
  const [showInput, setShowInput] = useState(false);
  const graph = analysis.result?.graph ?? emptyGraph;
  const repositoryName = analysis.result?.repository.name ?? "No repository selected";
  const repositoryPath = analysis.result?.repository.path ?? null;
  const executionFlows = graph.execution_flows ?? [];
  const [view, setView] = useState<"system" | "dependency">("system");
  const [flowId, setFlowId] = useState<string | undefined>(executionFlows[0]?.id);
  const execution = executionFlows.find(item => item.id === flowId) ?? executionFlows[0];
  const [flowSelection, setFlowSelection] = useState<string | null>(execution?.trigger ?? null);
  const otherComponents = graph.nodes.filter(node => ["EXTERNAL_SERVICE", "DATASTORE"].includes(node.type) && !execution?.steps.some(step => step.component_id === node.id));
  const [inspectedOther, setInspectedOther] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const submit = async (path: string) => {
    dispatch({ type: "start" }); setSelectedId(null); setFlowSelection(null); setInspectedOther(null);
    try {
      const result = await analyzeRepository(path);
      dispatch({ type: "success", result }); setShowInput(false); setView("system");
      const first = result.graph.execution_flows?.[0]; setFlowId(first?.id); setFlowSelection(first?.trigger ?? null);
      setSelectedId(initialSelection(result.graph));
    } catch (error) { dispatch({ type: "error", message: error instanceof Error ? error.message : "Repository analysis could not be completed." }); }
  };
  const selected = graph.nodes.find(node => node.id === selectedId) ?? null;
  const routes = graph.nodes.filter(node => node.type === "API_ROUTE").length;
  const modules = graph.nodes.filter(node => node.type === "MODULE").length;
  const services = graph.nodes.filter(node => node.type === "EXTERNAL_SERVICE").length;
  return <div className="app-shell">
    <AppHeader repositoryName={repositoryName} analyzing={analysis.status === "ANALYZING"} ready={analysis.status === "READY"} onAnalyze={() => setShowInput(true)} />
    <div className="workspace-layout"><AppSidebar repositoryName={repositoryName} repositoryPath={repositoryPath} />
      <main className="architecture-workspace">
        <div className="workspace-breadcrumb">Workspace<span>/</span><strong>Architecture</strong></div>
        <div className="architecture-heading"><div><div className="eyebrow">SYSTEM UNDERSTANDING</div><h1>Architecture</h1><p>Architecture reflects source-grounded relationships detected by Verisys.</p></div><div className="architecture-view-switch" aria-label="Architecture view"><button className={view === "system" ? "active" : ""} onClick={() => { setView("system"); setInspectedOther(null); }}>System Flow</button><button className={view === "dependency" ? "active" : ""} onClick={() => { setView("dependency"); setInspectedOther(null); if (!graph.nodes.some(node => node.id === selectedId && node.type === "MODULE")) setSelectedId(null); }}>Dependency View</button></div></div>
        <div className="architecture-summary"><span><strong>{graph.nodes.length}</strong> components</span><i /><span><strong>{routes}</strong> API {routes === 1 ? "route" : "routes"}</span><i /><span><strong>{services}</strong> external {services === 1 ? "service" : "services"}</span><i /><span><strong>{modules}</strong> modules</span><i /><span><strong>{graph.edges.length}</strong> relationships</span></div>
        <div className="graph-evidence-note"><Info size={14} />Only evidence-backed relationships are connected.<span>{analysis.status === "READY" ? "Real local analysis" : "Local static analysis"}</span></div>
        <div className="graph-canvas" aria-label="Architecture inspection graph">
          {analysis.status !== "READY" ? <div className="analysis-empty" role={analysis.status === "ERROR" ? "alert" : "status"}><h2>{analysis.status === "ANALYZING" ? "Analyzing repository…" : analysis.status === "ERROR" ? "Analysis failed" : "Understand your repository"}</h2><p>{analysis.error ?? (analysis.status === "ANALYZING" ? "Discovering safe source files and extracting source-grounded architecture." : "Analyze a local Python repository to inspect its architecture, dependencies, and supported execution flows.")}</p>{analysis.status !== "ANALYZING" && <button className="primary-button" onClick={() => setShowInput(true)}>Analyze a local repository</button>}</div> : view === "system" ? <>
            <div className="graph-legend"><span>↓ Execution direction</span><span>Source-declared possible paths · not runtime tracing</span>{executionFlows.length > 1 && <select aria-label="Execution flow" value={flowId} onChange={event => { const next = executionFlows.find(item => item.id === event.target.value)!; setFlowId(next.id); setFlowSelection(next.trigger); setInspectedOther(null); }}>{executionFlows.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select>}</div>
            {execution ? <SystemFlowCanvas key={execution.id} flow={execution} selected={flowSelection} onSelect={id => { setFlowSelection(id); setInspectedOther(null); }} /> : <div className="flow-empty">No supported source-declared execution flow was detected. Inspect structural dependencies in Dependency View.</div>}
          </> : <>
          <div className="graph-legend"><span><i className="legend-module" />Source-backed dependencies</span><span><i className="legend-test" />Test modules</span><span>Arrows indicate imports, not runtime calls</span></div>
          <DependencyCanvas graph={graph} selected={selectedId} onSelect={setSelectedId} />
          </>}
          <div className="canvas-caption"><MousePointer2 size={13} />{view === "system" ? "Select a step or transition to inspect its source evidence" : "Arrows represent imports · select to inspect"}</div>
        </div>
        {view === "system" && otherComponents.length > 0 && <div className="other-components"><div><strong>Other detected components</strong><span>Participation in this execution flow is not proven.</span></div>{otherComponents.map(node => <button className={inspectedOther === node.id ? "selected" : ""} key={node.id} onClick={() => setInspectedOther(node.id)}>{node.label}<code>{node.subtitle}</code></button>)}</div>}
        <footer className="workspace-status"><span><span className="neutral-dot" />{analysis.status === "READY" ? "Real analysis" : analysis.status}</span><span>{view === "system" ? `${execution?.transitions.length ?? 0} source-declared transitions` : `${graph.edges.length} structural dependencies`} · read-only</span></footer>
        {graph.limitations.length > 0 && <details className="graph-limitations"><summary>Analysis limitations ({graph.limitations.length})</summary>{graph.limitations.map(item => <p key={item}>{item}</p>)}</details>}
      </main>
      {view === "system" && execution && !inspectedOther ? <FlowInspector flow={execution} graph={graph} selected={flowSelection} onSelect={setFlowSelection} /> : <ArchitectureInspector key={selectedId ?? "empty"} node={inspectedOther ? graph.nodes.find(node => node.id === inspectedOther) ?? null : selected} graph={graph} onSelect={setSelectedId} onClear={() => { setSelectedId(null); setInspectedOther(null); }} />}
    </div>
    {showInput && <RepositoryInput busy={analysis.status === "ANALYZING"} error={analysis.error} onSubmit={submit} onClose={() => setShowInput(false)} />}
  </div>;
}
