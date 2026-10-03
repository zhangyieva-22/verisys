"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { DiscoveryApiError, discoverVerifications, idleDiscovery, type DiscoveryState } from "@/lib/evaluation/discovery-client";

import { idleVerification, runVerification, type VerificationState } from "@/lib/evaluation/verification-client";
import { VerificationResult } from "./VerificationResult";

import type { RepositorySource, AnalysisIntent } from "@/lib/repository-source";
import { savedNote } from "@/lib/stored";
export function SuggestedVerifications({ repositoryPath, source, intent, autoDiscover = false, architectureId, onAnalyze, initialDiscovery, initialVerification, onStateChange }: { repositoryPath?: string; source?: RepositorySource; intent?: AnalysisIntent; autoDiscover?: boolean; architectureId: string; onAnalyze: () => void; initialDiscovery?: DiscoveryState; initialVerification?: VerificationState; onStateChange?: (discovery: DiscoveryState, verification: VerificationState) => void }) {
  const input = source ?? repositoryPath ?? "";
  const contextKey = JSON.stringify([input, intent, architectureId]);
  const [state, setState] = useState<DiscoveryState>(initialDiscovery ?? idleDiscovery);
  const [verification, setVerification] = useState<VerificationState>(initialVerification ?? idleVerification);
  const resultPanel = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (verification.status === 'RESULT' && !resultPanel.current?.closest('[hidden]')) {
      resultPanel.current?.scrollIntoView?.({block:'start'});
      resultPanel.current?.focus();
    }
  }, [verification]);
  const execution = useRef<AbortController | null>(null);
  const request = useRef<AbortController | null>(null);
  const previousContext = useRef(contextKey);
  useEffect(() => {
    if (previousContext.current !== contextKey) { setVerification(idleVerification); setState(idleDiscovery); previousContext.current = contextKey; }
    return () => { request.current?.abort(); request.current = null; execution.current?.abort(); execution.current = null; };
  }, [contextKey]);
  const autoStarted = useRef<string | null>(initialDiscovery && initialDiscovery.status !== "IDLE" ? contextKey : null);
  useEffect(() => { onStateChange?.(state, verification); }, [state, verification, onStateChange]);
  const discover = useCallback(async (refresh = false) => {
    if (request.current || execution.current) return;
    if (intent?.mode === "ON_DEMAND" && !intent.request_text?.trim()) { onAnalyze(); return; }
    setVerification(idleVerification);
    const current = new AbortController(); request.current = current;
    setState({ status: "DISCOVERING", result: null, error: null });
    try {
      const result = await discoverVerifications(input, architectureId, current.signal, intent, refresh);
      if (!current.signal.aborted) setState({ status: result.candidates.length ? "READY" : "EMPTY", result, error: null });
    } catch (error) {
      if (!current.signal.aborted) setState({ status: "ERROR", result: null, error: error instanceof Error ? error.message : "Discovery could not be completed.", stale: error instanceof DiscoveryApiError && error.code === "ANALYSIS_STALE" });
    } finally { if (request.current === current) request.current = null; }
  }, [contextKey]);
  useEffect(() => {
    let active = true;
    // Defer until effect setup settles; StrictMode replay cannot duplicate/abort a paid call.
    queueMicrotask(() => {
      if (active && autoDiscover && autoStarted.current !== contextKey) { autoStarted.current = contextKey; void discover(); }
    });
    return () => { active = false; };
  }, [autoDiscover, discover, contextKey]);
  const verify = async (id: string, refresh = false) => {
    if (execution.current || request.current || (verification.status === "ERROR" && verification.code === "ANALYSIS_STALE")) return;
    const current = new AbortController(); execution.current = current;
    setVerification({ status: "RUNNING", result: null, error: null });
    try {
      const result = await runVerification(input, id, architectureId, current.signal, refresh);
      if (!current.signal.aborted) setVerification({ status: "RESULT", result, error: null });
    } catch (error) {
      if (!current.signal.aborted) setVerification({ status: "ERROR", result: null, error: error instanceof Error ? error.message : "Verification failed.", code: error instanceof DiscoveryApiError ? error.code : "VERIFICATION_FAILED" });
    } finally { if (execution.current === current) execution.current = null; }
  };
  const stale = verification.status === "ERROR" && verification.code === "ANALYSIS_STALE";
  return <section className="suggested-verifications" aria-labelledby="suggested-title" data-state={state.status}>
    <div className="suggested-heading"><div><h2 id="suggested-title">Suggested Verifications</h2><p>Grounded suggestions for this architecture. Run an installed check to collect evidence.</p></div>
      <button className="primary-button" disabled={verification.status === "RUNNING" || stale || state.status === "DISCOVERING" || (state.status === "ERROR" && state.stale)} onClick={() => discover(Boolean(state.result))}>{state.status === "DISCOVERING" ? "Discovering…" : state.status === "READY" ? "Regenerate" : "Discover Verifications"}</button></div>
    {state.status === "IDLE" && <p className="discovery-note">Discover grounded suggestions using the configured model. Normalized architecture metadata is sent to the provider.</p>}
    {state.status === "DISCOVERING" && <p role="status" className="discovery-note">Selecting worthwhile checks and validating their architecture grounding…</p>}
    {state.status === "ERROR" && <div role="alert" className="discovery-error" data-stale={state.stale}><p>{state.error}</p>{state.stale && <button onClick={onAnalyze}>Analyze Repository again →</button>}</div>}
    {state.status === "EMPTY" && <p role="status" className="discovery-note">{intent?.mode === "ON_DEMAND" ? "No currently supported evaluation matches this request." : "No supported evaluation was selected. This does not establish that the system meets any requirement."}</p>}
    <div ref={resultPanel} tabIndex={-1} className="verification-state-panel" data-verification-state={verification.status}>
      {verification.status === "IDLE" && <p className="discovery-note">Run an available verification to collect evidence.</p>}
      {verification.status === "RUNNING" && <p role="status">Running static verification and collecting source-backed evidence…</p>}
      {verification.status === "ERROR" && <div role="alert" className="discovery-error"><code>{verification.code}</code><p>{verification.error}</p>{stale && <button onClick={onAnalyze}>Analyze Repository again →</button>}</div>}
      {verification.status === "RESULT" && <VerificationResult result={verification.result} onRerun={() => verify(verification.result.evaluation_id, true)} />}
    </div>
    {state.result && <>
      <div className="discovery-context"><span>{state.result.catalog_version}</span><span title={state.result.architecture_id}>Snapshot <code>{state.result.architecture_id.slice(0, 12)}</code></span><span>{savedNote(state.result.stored) ?? "Fresh server-side analysis"}</span></div>
      {state.result.candidates.map(item => <article className="suggestion" key={item.id}>
        <div className="suggestion-title"><h3>{item.name}</h3><span>{item.category}</span></div><p>{item.reason}</p>
        <dl className="suggestion-labels">
          <div><dt>Applicability</dt><dd className={`suggestion-applicability ${item.applicability.toLowerCase()}`}>{item.applicability}</dd></div>
          <div><dt>Execution support</dt><dd className={`suggestion-support ${item.execution_support.toLowerCase()}`}>{item.execution_support}</dd></div>
          <div><dt>Mode</dt><dd>{item.verification_mode}</dd></div><div><dt>Priority</dt><dd>{item.priority}</dd></div>
        </dl>
        {item.execution_support === "NOT_AVAILABLE" && <p className="discovery-note">Worth investigating, but Verisys cannot execute this verification yet.</p>}
        {item.execution_support === "PARTIAL" && <p className="discovery-note">Relevant to this architecture, but current executable coverage is limited.</p>}
        <button className="primary-button" disabled={!item.can_execute || verification.status === "RUNNING" || stale} onClick={() => verify(item.id)}>{item.can_execute ? "Run Verification" : "Verification not available yet"}</button>
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
