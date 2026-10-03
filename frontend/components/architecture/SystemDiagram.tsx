"use client";
import { ArrowDown, ArrowRight, Sparkles, X } from "lucide-react";
import type { DiagramItem, DiagramLayer, DiagramPath, SystemDiagram } from "@/lib/architecture/system-diagram";
import type { EnrichmentState } from "@/lib/architecture/diagram-client";
import { Citations, KIND_LABELS } from "../understanding/UnderstandingView";
import { SourceReferences } from "./ArchitectureInspector";

function Item({ item, selected, onSelect }: { item: DiagramItem; selected: boolean; onSelect: (item: DiagramItem) => void }) {
  return <button className={`diagram-item ${selected ? "selected" : ""}`} data-origin={item.origin} onClick={() => onSelect(item)}>
    <strong>{item.label}</strong>{item.detail && <span>{item.detail}</span>}
    {item.origin === "INFERRED" && <em className="inferred-mark">Inferred</em>}
    {item.chips.length > 0 && <ul className="diagram-chips">{item.chips.slice(0, 12).map(chip => <li key={chip.nodeId}><code>{chip.label}</code></li>)}{item.chips.length > 12 && <li>+{item.chips.length - 12} more</li>}</ul>}
  </button>;
}
function Band({ layer, selected, onSelect }: { layer: DiagramLayer; selected: string | null; onSelect: (item: DiagramItem) => void }) {
  return <section className={`diagram-band layer-${layer.kind.toLowerCase()}`} aria-label={`${layer.title} layer`}>
    <h3>{layer.title}</h3><div className="diagram-items">{layer.items.map(item => <Item key={item.id} item={item} selected={selected === item.id} onSelect={onSelect}/>)}</div>
  </section>;
}
function Path({ path }: { path: DiagramPath }) {
  return <section className="diagram-path" data-origin={path.origin}>
    <h3>{path.origin === "DETECTED" ? "Source-declared flow" : "Request path"} · {path.title}{path.origin === "INFERRED" && <em className="inferred-mark">Inferred</em>}</h3>
    <ol>{path.steps.map((step, i) => <li key={i}>{i > 0 && <ArrowRight size={14} aria-hidden/>}<span title={step.citations.map(c => `${c.path}:${c.start_line}`).join(", ")}>{step.label}</span></li>)}</ol>
  </section>;
}

export function SystemDiagramView({ diagram, enrichment, selected, onSelect, onEnrich }: {
  diagram: SystemDiagram; enrichment: EnrichmentState; selected: string | null;
  onSelect: (item: DiagramItem) => void; onEnrich: () => void;
}) {
  const main = diagram.main.filter(layer => layer.items.length);
  const side = diagram.side.filter(layer => layer.items.length);
  const detected = [...diagram.main, ...diagram.side].flatMap(layer => layer.items).filter(item => item.origin === "DETECTED").length;
  const result = enrichment.status === "READY" ? enrichment.result : null;
  return <div className="system-diagram" data-enrichment={enrichment.status}>
    <div className="diagram-toolbar">
      <p><strong>{detected}</strong> detected component groups{result ? <> · <strong>{result.components.length}</strong> inferred</> : null}</p>
      <button className="primary-button" disabled={enrichment.status === "ENRICHING" || (enrichment.status === "ERROR" && enrichment.stale)} onClick={onEnrich}>
        <Sparkles size={14}/>{enrichment.status === "ENRICHING" ? "Enriching…" : result ? "Re-enrich" : "Enrich with AI"}</button>
    </div>
    {enrichment.status === "IDLE" && <p className="diagram-note">Boxes come from static analysis. Enrich with AI to add layers analysis cannot see, such as the client, frontend and request path. Enriching sends selected documentation, manifests and source excerpts, with likely secrets redacted, to the configured model.</p>}
    {enrichment.status === "ENRICHING" && <p className="diagram-note" role="status">Reading selected excerpts and checking every citation…</p>}
    {enrichment.status === "ERROR" && <p className="diagram-note error" role="alert">{enrichment.error}</p>}
    <div className="diagram-grid">
      <div className="diagram-main">{main.length ? main.map((layer, i) => <div key={layer.kind}>{i > 0 && <div className="diagram-arrow" aria-hidden><ArrowDown size={16}/></div>}<Band layer={layer} selected={selected} onSelect={onSelect}/></div>)
        : <p className="diagram-note">No API, package or AI-service component was detected.</p>}</div>
      {side.length > 0 && <aside className="diagram-side">{side.map(layer => <Band key={layer.kind} layer={layer} selected={selected} onSelect={onSelect}/>)}</aside>}
    </div>
    {diagram.paths.map((path, i) => <Path key={i} path={path}/>)}
    <div className="diagram-legend"><span className="legend-detected">Detected from source</span><span className="legend-inferred">Inferred — not verified</span>
      {diagram.testModules > 0 && <span>{diagram.testModules} test modules hidden</span>}<span>Missing layers mean not detected, not absent.</span></div>
    {result && result.limitations.length > 0 && <details className="diagram-limitations"><summary>Enrichment details</summary><ul>{result.limitations.map((l, i) => <li key={i}>{l}</li>)}</ul>
      <p>Sent to <code>{result.model}</code>: {result.sources.map(s => `${s.path} (${KIND_LABELS[s.kind]})`).join(", ")}</p></details>}
  </div>;
}

export function DiagramItemInspector({ item, layer, onClear }: { item: DiagramItem; layer: string; onClear: () => void }) {
  return <aside className="inspector" aria-label="Diagram item inspector">
    <div className="panel-heading">Inspector<button className="icon-button" onClick={onClear} aria-label="Clear selection"><X size={16}/></button></div>
    <div className="inspector-content">
      <div className="inspector-identity"><div><h2>{item.label}</h2><span className="eyebrow">{layer.toUpperCase()}</span></div></div>
      <div className="fixture-caption">{item.origin === "DETECTED" ? "DETECTED FROM SOURCE" : "INFERRED — NOT VERIFIED"}</div>
      {item.detail && <section><h3>DETAILS</h3><p className="section-description">{item.detail}</p></section>}
      {item.members.length > 0 && <section><h3>MODULES <span>{item.members.length}</span></h3><ul className="diagram-members">{item.members.map(name => <li key={name}><code>{name}</code></li>)}</ul></section>}
      {item.sources.length > 0 && <section><h3>SOURCE EVIDENCE <span>{item.sources.length}</span></h3><SourceReferences locations={item.sources}/></section>}
      {item.citations.length > 0 && <section><h3>CITATIONS <span>{item.citations.length}</span></h3><p className="section-description">Quoted text was checked against the excerpts sent to the model; the component itself is inferred.</p><Citations citations={item.citations}/></section>}
    </div>
  </aside>;
}
