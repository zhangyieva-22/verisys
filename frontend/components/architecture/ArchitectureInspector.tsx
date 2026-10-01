import { ArrowUpRight, ChevronRight, FileCode2, MousePointer2, ShieldCheck, X } from "lucide-react";
import { useState } from "react";
import { callSites, type ArchitectureGraph, type ArchitectureNode, type SourceLocation } from "@/lib/architecture/types";
import { nodePresentation } from "./ArchitectureNode";

function SourceReferences({ locations }: { locations: SourceLocation[] }) {
  const [active, setActive] = useState<SourceLocation | null>(null);
  return <>
    <div className="source-list">{locations.map(location => <button className="source-reference" key={`${location.file}:${location.line}:${location.column}`} onClick={() => setActive(location)}>
      <FileCode2 size={14} /><code>{location.file}<span>:{location.line}</span></code><ArrowUpRight size={13} />
    </button>)}</div>
    {active && <div className="inline-note" role="status"><code>{active.file}:{active.line}</code> is a source reference returned by analysis. Source navigation is not connected.</div>}
  </>;
}

export function ArchitectureInspector({ node, graph, onSelect, onClear }: { node: ArchitectureNode | null; graph: ArchitectureGraph; onSelect: (id: string) => void; onClear: () => void }) {
  const [showPlaceholder, setShowPlaceholder] = useState(false);
  if (!node) return <aside className="inspector" aria-label="Component inspector">
    <div className="panel-heading">Inspector<span>COMPONENT DETAILS</span></div>
    <div className="inspector-empty"><div className="empty-icon"><MousePointer2 size={23} /></div><h3>A closer look</h3><p>Select a component to inspect its architecture evidence.</p><span>Source references, observed facts,<br />and concrete API call sites.</span></div>
    <div className="inspector-bottom"><ShieldCheck size={15} /><span>Architecture facts first.<br />Verification comes next.</span></div>
  </aside>;
  const { label, icon: Icon } = nodePresentation[node.type];
  const calls = callSites(node);
  return <aside className="inspector" aria-label="Component inspector">
    <div className="panel-heading">Inspector<button className="icon-button" onClick={onClear} aria-label="Clear selection"><X size={16} /></button></div>
    <div className="inspector-content">
      <div className="inspector-identity"><div className="inspector-icon"><Icon size={23} /></div><div><h2>{node.label}</h2><span className="eyebrow">{label.toUpperCase()}</span></div></div>
      <div className="fixture-caption">SOURCE-GROUNDED ARCHITECTURE</div>
      <section><h3>COMPONENT DETAILS</h3><dl className="facts">{node.subtitle && <div><dt>{node.type === "EXTERNAL_SERVICE" ? "Detected library" : node.type === "TOOL" ? "Module" : node.type === "DATASTORE" ? "Engine" : "Handler"}</dt><dd><code>{node.subtitle}</code></dd></div>}</dl></section>
      <section><h3>SOURCE EVIDENCE <span>{node.source_locations.length}</span></h3><p className="section-description">Imports, construction, and supported usage.</p>{node.source_locations.length ? <SourceReferences locations={node.source_locations} /> : <p className="inline-note">The current graph has no source location for this component.</p>}</section>
      {Object.keys(node.metadata).length > 0 && <section><h3>METADATA</h3><pre className="metadata-source">{JSON.stringify(node.metadata, null, 2)}</pre></section>}
      {(["incoming", "outgoing"] as const).map(direction => {
        const edges = graph.edges.filter(edge => direction === "incoming" ? edge.target === node.id : edge.source === node.id);
        return edges.length > 0 && <section key={direction}><h3>{direction.toUpperCase()} RELATIONSHIPS <span>{edges.length}</span></h3><div className="relationship-list">{edges.map(edge => {
          const otherId = direction === "incoming" ? edge.source : edge.target;
          const other = graph.nodes.find(item => item.id === otherId);
          return <div key={edge.id}><button onClick={() => onSelect(otherId)}><span>{edge.type} {direction === "incoming" ? "from" : "to"}</span><code>{other?.label ?? otherId}</code></button><SourceReferences locations={edge.source_locations} /></div>;
        })}</div></section>;
      })}
      {node.type === "EXTERNAL_SERVICE" && <section><h3>CONCRETE API CALL SITES <span>{calls.length}</span></h3><p className="section-description">Supported call expressions only; excludes imports and construction.</p>{calls.length ? <SourceReferences locations={calls} /> : <p className="inline-note">No supported call sites detected. This is not proof that no calls exist. See analysis limitations for unsupported patterns.</p>}</section>}
      {node.type === "EXTERNAL_SERVICE" && <section className="verification-section"><div className="eyebrow">VERIFICATION</div><h3>External API Timeout Coverage</h3><p>Check explicit timeout behavior at supported external API call sites.</p><button className="primary-button verify-button" onClick={() => setShowPlaceholder(true)}><ShieldCheck size={16} />Verify timeout coverage<ChevronRight size={16} /></button><span className="action-caption">UI preview · execution not connected</span>{showPlaceholder && <div className="inline-note" role="status">Verification integration is not connected yet. No verification has run.</div>}</section>}
    </div>
  </aside>;
}
