"use client";
import { useEffect, useRef, useState } from "react";
import { DiscoveryApiError, discoverVerifications, idleDiscovery, type DiscoveryState } from "@/lib/evaluation/discovery-client";

export function SuggestedVerifications({ repositoryPath, architectureId, onAnalyze }: { repositoryPath: string; architectureId: string; onAnalyze: () => void }) {
  const [state, setState] = useState<DiscoveryState>(idleDiscovery);
  const request = useRef<AbortController | null>(null);
  useEffect(() => () => { request.current?.abort(); request.current = null; }, [repositoryPath, architectureId]);
  const discover = async () => {
    if (request.current) return;
    const current = new AbortController(); request.current = current;
    setState({ status: "DISCOVERING", result: null, error: null });
    try {
      const result = await discoverVerifications(repositoryPath, architectureId, current.signal);
      if (!current.signal.aborted) setState({ status: result.candidates.length ? "READY" : "EMPTY", result, error: null });
    } catch (error) {
      if (!current.signal.aborted) setState({ status: "ERROR", result: null, error: error instanceof Error ? error.message : "Discovery could not be completed.", stale: error instanceof DiscoveryApiError && error.code === "ANALYSIS_STALE" });
    } finally { if (request.current === current) request.current = null; }
  };
  return <section className="suggested-verifications" aria-labelledby="suggested-title" data-state={state.status}>
    <div className="suggested-heading"><div><h2 id="suggested-title">Suggested Verifications</h2><p>Worthwhile engineering checks for this architecture. None has been executed.</p></div>
      <button className="primary-button" disabled={state.status === "DISCOVERING" || (state.status === "ERROR" && state.stale)} onClick={discover}>{state.status === "DISCOVERING" ? "Discovering…" : "Discover Verifications"}</button></div>
    {state.status === "IDLE" && <p className="discovery-note">Discover grounded suggestions using the configured model. Normalized architecture metadata is sent to the provider.</p>}
    {state.status === "DISCOVERING" && <p role="status" className="discovery-note">Selecting worthwhile checks and validating their architecture grounding…</p>}
    {state.status === "ERROR" && <div role="alert" className="discovery-error" data-stale={state.stale}><p>{state.error}</p>{state.stale && <button onClick={onAnalyze}>Analyze Repository again →</button>}</div>}
    {state.status === "EMPTY" && <p role="status" className="discovery-note">No recommendations were selected. This does not establish that the system meets any requirement.</p>}
    {state.result && <>
      <div className="discovery-context"><span>{state.result.catalog_version}</span><span title={state.result.architecture_id}>Snapshot <code>{state.result.architecture_id.slice(0, 12)}</code></span><span>Fresh server-side analysis</span></div>
      {state.result.candidates.map(item => <article className="suggestion" key={item.id}>
        <div className="suggestion-title"><h3>{item.name}</h3><span>{item.category}</span></div><p>{item.reason}</p>
        <dl className="suggestion-labels">
          <div><dt>Applicability</dt><dd className={`suggestion-applicability ${item.applicability.toLowerCase()}`}>{item.applicability}</dd></div>
          <div><dt>Execution support</dt><dd className={`suggestion-support ${item.execution_support.toLowerCase()}`}>{item.execution_support}</dd></div>
          <div><dt>Mode</dt><dd>{item.verification_mode}</dd></div><div><dt>Priority</dt><dd>{item.priority}</dd></div>
        </dl>
        {item.execution_support === "NOT_AVAILABLE" && <p className="discovery-note">Worth investigating, but Verisys cannot execute this verification yet.</p>}
        {item.execution_support === "PARTIAL" && <p className="discovery-note">Relevant to this architecture, but current executable coverage is limited.</p>}
        <details><summary>Grounding and required evidence</summary>
          <div className="suggestion-detail"><strong>Architecture subjects</strong>{item.architecture_subject_ids.map(id => <code key={id}>{id}</code>)}
          <strong>Required evidence · not collected</strong><ul>{item.required_evidence.map(text => <li key={text}>{text}</li>)}</ul>
          {item.limitations.length > 0 && <><strong>Limitations</strong><ul>{item.limitations.map(text => <li key={text}>{text}</li>)}</ul></>}</div>
        </details>
      </article>)}
      {(state.result.input_truncated || state.result.limitations.length > 0) && <details className="discovery-limitations"><summary>Discovery limitations{state.result.input_truncated ? " · input truncated" : ""}</summary>{state.result.limitations.map(text => <p key={text}>{text}</p>)}</details>}
    </>}
  </section>;
}
