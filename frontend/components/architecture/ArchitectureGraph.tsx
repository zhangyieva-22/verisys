"use client";
import { useMemo, useState } from "react";
import { Info, MousePointer2 } from "lucide-react";
import { initialSelection } from "@/lib/architecture/selection";
import type { AnalysisResult } from "@/lib/architecture/analysis-client";
import { DependencyCanvas } from "./DependencyCanvas";
import { ArchitectureInspector } from "./ArchitectureInspector";
import { DiagramItemInspector, SystemDiagramView } from "./SystemDiagram";
import { buildSystemDiagram, mergeEnrichment, type DiagramItem } from "@/lib/architecture/system-diagram";
import { idleEnrichment, type EnrichmentState } from "@/lib/architecture/diagram-client";

// Preserve the public entry component while the application becomes project-centric.
export { ProjectWorkspace as ArchitectureWorkspace } from "../projects/ProjectWorkspace";
export function ArchitectureView({ result, enrichment = idleEnrichment, onEnrich = () => {} }: { result: AnalysisResult; enrichment?: EnrichmentState; onEnrich?: () => void }) {
  const graph = result.graph;
  const [view, setView] = useState<"diagram" | "dependency">("diagram");
  const [selectedId, setSelectedId] = useState<string | null>(initialSelection(graph));
  const [diagramItem, setDiagramItem] = useState<DiagramItem | null>(null);
  const selected = graph.nodes.find(node => node.id === selectedId) ?? null;
  const diagram = useMemo(() => {
    const detected = buildSystemDiagram(graph);
    return enrichment.status === "READY" ? mergeEnrichment(detected, enrichment.result.components, enrichment.result.request_path) : detected;
  }, [graph, enrichment]);
  const itemLayer = diagramItem ? [...diagram.main, ...diagram.side].find(layer => layer.items.some(item => item.id === diagramItem.id))?.title ?? "" : "";
  const selectDiagramItem = (item: DiagramItem) => { setDiagramItem(item); if (item.nodeId) setSelectedId(item.nodeId); };
  const clear = () => { setSelectedId(null); setDiagramItem(null); };
  const routes = graph.nodes.filter(node => node.type === "API_ROUTE").length;
  const modules = graph.nodes.filter(node => node.type === "MODULE").length;
  const services = graph.nodes.filter(node => node.type === "EXTERNAL_SERVICE").length;
  if (!graph.nodes.length) return <main className="project-overview"><h1>Architecture</h1><div className="workspace-notice"><h2>No architecture components were detected.</h2><p>The supported static analysis found no inspectable architecture in this snapshot.</p></div>{graph.limitations.length > 0 && <details><summary>Analysis limitations ({graph.limitations.length})</summary>{graph.limitations.map(item => <p key={item}>{item}</p>)}</details>}</main>;
  return <div className="architecture-layout">
      <main className="architecture-workspace">
        <div className="workspace-breadcrumb">Workspace<span>/</span><strong>Architecture</strong></div>
        <div className="architecture-heading"><div><div className="eyebrow">SYSTEM UNDERSTANDING</div><h1>Architecture</h1><p>Architecture reflects source-grounded relationships detected by Verisys.</p></div><div className="architecture-view-switch" aria-label="Architecture view"><button className={view === "diagram" ? "active" : ""} onClick={() => setView("diagram")}>System Diagram</button><button className={view === "dependency" ? "active" : ""} onClick={() => { setView("dependency"); setDiagramItem(null); }}>Dependency View</button></div></div>
        <div className="architecture-summary"><span><strong>{graph.nodes.length}</strong> components</span><i /><span><strong>{routes}</strong> API {routes === 1 ? "route" : "routes"}</span><i /><span><strong>{services}</strong> external {services === 1 ? "service" : "services"}</span><i /><span><strong>{modules}</strong> modules</span><i /><span><strong>{graph.edges.length}</strong> relationships</span></div>
        <div className="graph-evidence-note"><Info size={14} />Only evidence-backed relationships are connected.<span>Source-backed analysis</span></div>
        {view === "diagram" ? <SystemDiagramView diagram={diagram} enrichment={enrichment} selected={diagramItem?.id ?? null} onSelect={selectDiagramItem} onEnrich={onEnrich} /> :
        <div className="graph-canvas" aria-label="Architecture inspection graph">
          <div className="graph-legend"><span><i className="legend-module" />Source-backed dependencies</span><span><i className="legend-test" />Test modules</span><span>Arrows indicate imports, not runtime calls</span></div>
          <DependencyCanvas graph={graph} selected={selectedId} onSelect={setSelectedId} />
          <div className="canvas-caption"><MousePointer2 size={13} />Arrows represent imports · select to inspect</div>
        </div>}
        <footer className="workspace-status"><span><span className="neutral-dot" />Source-backed analysis</span><span>{graph.edges.length} structural dependencies · read-only</span></footer>
        {graph.limitations.length > 0 && <details className="graph-limitations"><summary>Analysis limitations ({graph.limitations.length})</summary>{graph.limitations.map(item => <p key={item}>{item}</p>)}</details>}
      </main>
      {view === "diagram" && diagramItem && !diagramItem.nodeId ? <DiagramItemInspector item={diagramItem} layer={itemLayer} onClear={clear} /> :
        <ArchitectureInspector key={selectedId ?? "empty"} node={selected} graph={graph} onSelect={id => { setSelectedId(id); setDiagramItem(null); }} onClear={clear} />}
  </div>;
}
