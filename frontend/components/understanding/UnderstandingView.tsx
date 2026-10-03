"use client";
import { useEffect, useRef, useState } from "react";
import { generateUnderstanding, idleUnderstanding, UnderstandingApiError, type Citation, type InferredRequirement, type InferredRisk, type UnderstandingState } from "@/lib/understanding/understanding-client";
import type { RepositorySource } from "@/lib/repository-source";
import { savedNote } from "@/lib/stored";

export const KIND_LABELS = { README: "README", DOCUMENT: "Documentation", MANIFEST: "Manifest", ROUTE_SOURCE: "Route source", INTEGRATION_SOURCE: "Integration source", ENTRY_POINT: "Entry point", TEST_INDEX: "Test names" } as const;
const SEVERITY_ORDER = { high: 0, medium: 1, low: 2 } as const;

export function Citations({ citations }: { citations: Citation[] }) {
  return <ul className="claim-citations" aria-label="Source citations">{citations.map((c, i) =>
    <li key={i}><code>{c.path}:{c.start_line === c.end_line ? `L${c.start_line}` : `L${c.start_line}–L${c.end_line}`}</code>
      <span className="citation-kind">{KIND_LABELS[c.excerpt_kind]}</span><blockquote>{c.quote}</blockquote></li>)}</ul>;
}
function Claim({ claim, risk }: { claim: InferredRequirement; risk?: InferredRisk }) {
  return <article className="inferred-claim" data-severity={risk?.severity}>
    <div className="claim-title"><h3>{claim.title}</h3><span className="inferred-badge">Inferred — not verified</span></div>
    {risk && <dl className="claim-labels"><div><dt>Category</dt><dd>{risk.category}</dd></div><div><dt>Severity</dt><dd className={`severity ${risk.severity}`}>{risk.severity}</dd></div></dl>}
    <p>{claim.description}</p><Citations citations={claim.citations}/>
  </article>;
}

export function UnderstandingView({ source, architectureId, initialState, onStateChange, onAnalyze }: {
  source: RepositorySource | string; architectureId: string; initialState?: UnderstandingState;
  onStateChange?: (state: UnderstandingState) => void; onAnalyze: () => void;
}) {
  const [state, setState] = useState<UnderstandingState>(initialState ?? idleUnderstanding);
  const request = useRef<AbortController | null>(null);
  useEffect(() => { onStateChange?.(state); }, [state, onStateChange]);
  useEffect(() => () => { request.current?.abort(); request.current = null; }, []);
  const generate = async (refresh = false) => {
    // One paid call at a time; never retried automatically.
    if (request.current) return;
    const current = new AbortController(); request.current = current;
    setState({ status: "GENERATING", result: null, error: null });
    try {
      const result = await generateUnderstanding(source, architectureId, current.signal, refresh);
      if (!current.signal.aborted) setState({ status: "READY", result, error: null });
    } catch (error) {
      if (!current.signal.aborted) setState({ status: "ERROR", result: null, error: error instanceof Error ? error.message : "Understanding could not be completed.", stale: error instanceof UnderstandingApiError && error.code === "ANALYSIS_STALE" });
    } finally { if (request.current === current) request.current = null; }
  };
  const result = state.status === "READY" ? state.result : null;
  const risks = result ? [...result.risks].sort((a, b) => SEVERITY_ORDER[a.severity] - SEVERITY_ORDER[b.severity]) : [];
  return <main className="project-understanding" data-state={state.status}>
    <div className="page-heading"><div><h1>Understanding</h1><p>Functional requirements and engineering risks proposed by a language model from selected documentation and source. Every item cites where it comes from and is inferred, not verified.</p></div>
      <button className="primary-button" disabled={state.status === "GENERATING" || (state.status === "ERROR" && state.stale)} onClick={() => generate(Boolean(result))}>{state.status === "GENERATING" ? "Generating…" : result ? "Regenerate" : "Generate Understanding"}</button></div>
    {state.status === "IDLE" && <p className="discovery-note">Nothing is sent until you click. Generating sends the README, documentation and selected source excerpts, with likely secrets redacted, to the configured model.</p>}
    {state.status === "GENERATING" && <p role="status" className="discovery-note">Reading selected excerpts and checking every citation against the text that was sent…</p>}
    {state.status === "ERROR" && <div role="alert" className="discovery-error" data-stale={state.stale}><p>{state.error}</p>{state.stale && <button onClick={onAnalyze}>Analyze Repository again →</button>}</div>}
    {result && <>
      {savedNote(result.stored) && <p className="saved-note">{savedNote(result.stored)}</p>}
      <p className="understanding-meta">Model <code>{result.model}</code> · {result.sources.length} excerpts sent{result.input_truncated ? " · input truncated" : ""}{result.rejected_claims ? ` · ${result.rejected_claims} unsupported claim(s) dropped` : ""}</p>
      <section className="claim-group" aria-labelledby="requirements-title"><h2 id="requirements-title">Functional requirements <span>{result.functional_requirements.length}</span></h2>
        {result.functional_requirements.length ? result.functional_requirements.map(c => <Claim key={c.id} claim={c}/>) : <p className="discovery-note">No functional requirement was proposed with a valid citation.</p>}</section>
      <section className="claim-group" aria-labelledby="risks-title"><h2 id="risks-title">Risks <span>{risks.length}</span></h2>
        {risks.length ? risks.map(r => <Claim key={r.id} claim={r} risk={r}/>) : <p className="discovery-note">No risk was proposed with a valid citation. This does not establish that the repository has no risks.</p>}</section>
      <details className="understanding-sources"><summary>What was sent to the model</summary><ul>{result.sources.map((s, i) =>
        <li key={i}><code>{s.path}</code> · {KIND_LABELS[s.kind]} · lines {s.first_line}–{s.last_line} ({s.line_count} lines{s.truncated ? ", truncated" : ""})</li>)}</ul></details>
      {result.limitations.length > 0 && <details><summary>Limitations</summary><ul>{result.limitations.map((l, i) => <li key={i}>{l}</li>)}</ul></details>}
    </>}
  </main>;
}
