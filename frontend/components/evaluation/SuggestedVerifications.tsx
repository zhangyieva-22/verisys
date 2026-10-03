"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { DiscoveryApiError, discoverVerifications, idleDiscovery, type DiscoveryState } from "@/lib/evaluation/discovery-client";

import { idleVerification, runVerification, type VerificationState } from "@/lib/evaluation/verification-client";
import { PlanExperience } from "./PlanExperience";
import { VerificationResult } from "./VerificationResult";

import type { RepositorySource, AnalysisIntent } from "@/lib/repository-source";
import { savedNote } from "@/lib/stored";
export function SuggestedVerifications({ repositoryPath, source, intent, autoDiscover = false, architectureId, onAnalyze, initialDiscovery, initialVerification, onStateChange }: { repositoryPath?: string; source?: RepositorySource; intent?: AnalysisIntent; autoDiscover?: boolean; architectureId: string; onAnalyze: () => void; initialDiscovery?: DiscoveryState; initialVerification?: VerificationState; onStateChange?: (discovery: DiscoveryState, verification: VerificationState) => void }) {
  const input = source ?? repositoryPath ?? "";
  const contextKey = JSON.stringify([input, intent, architectureId]);
  const [state, setState] = useState<DiscoveryState>(initialDiscovery ?? idleDiscovery);
  const [verification, setVerification] = useState<VerificationState>(initialVerification ?? idleVerification);
  const [activeEvaluationId, setActiveEvaluationId] = useState<string | null>(
    initialVerification?.status === 'RESULT' ? initialVerification.result.evaluation_id : null);
  // Ephemeral presentation state only: never sent to the API or persisted via onStateChange.
  const [demoOutcomes, setDemoOutcomes] = useState<Record<string, 'VERIFIED'> | null>(null);
  const simulate = () => setDemoOutcomes(Object.fromEntries(
    (state.result?.candidates ?? []).filter(item => item.can_execute)
      .map(item => [item.id, 'VERIFIED'])));
  const execution = useRef<AbortController | null>(null);
  const request = useRef<AbortController | null>(null);
  const previousContext = useRef(contextKey);
  useEffect(() => {
    if (previousContext.current !== contextKey) { setDemoOutcomes(null); setVerification(idleVerification); setActiveEvaluationId(null); setState(idleDiscovery); previousContext.current = contextKey; }
    return () => { request.current?.abort(); request.current = null; execution.current?.abort(); execution.current = null; };
  }, [contextKey]);
  const autoStarted = useRef<string | null>(initialDiscovery && initialDiscovery.status !== "IDLE" ? contextKey : null);
  useEffect(() => { onStateChange?.(state, verification); }, [state, verification, onStateChange]);
  const discover = useCallback(async (refresh = false) => {
    if (request.current || execution.current) return;
    if (intent?.mode === "ON_DEMAND" && !intent.request_text?.trim()) { onAnalyze(); return; }
    setDemoOutcomes(null);
    setVerification(idleVerification);
    setActiveEvaluationId(null);
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
    setActiveEvaluationId(id);
    setVerification({ status: "RUNNING", result: null, error: null });
    try {
      const result = await runVerification(input, id, architectureId, current.signal, refresh);
      if (!current.signal.aborted) setVerification({ status: "RESULT", result, error: null });
    } catch (error) {
      if (!current.signal.aborted) setVerification({ status: "ERROR", result: null, error: error instanceof Error ? error.message : "Verification failed.", code: error instanceof DiscoveryApiError ? error.code : "VERIFICATION_FAILED" });
    } finally { if (execution.current === current) execution.current = null; }
  };
  const stale = verification.status === "ERROR" && verification.code === "ANALYSIS_STALE";
  const verificationPanel = (
<div className="verification-state-panel" data-verification-state={verification.status}>
      {verification.status === "IDLE" && <p className="discovery-note">Run an available verification to collect evidence.</p>}
      {verification.status === "RUNNING" && <p role="status">Running static verification and collecting source-backed evidence…</p>}
      {verification.status === "ERROR" && <div role="alert" className="discovery-error"><code>{verification.code}</code><p>{verification.error}</p>{stale && <button onClick={onAnalyze}>Analyze Repository again →</button>}</div>}
      {verification.status === "RESULT" && <VerificationResult result={verification.result} onRerun={() => verify(verification.result.evaluation_id, true)} />}
    </div>
  );
  return <section className="suggested-verifications" aria-labelledby="suggested-title" data-state={state.status}>
    <section className="verification-group functional-group" aria-labelledby="functional-checks-title"><div className="verification-group-heading"><h2 id="functional-checks-title">Functional Verification</h2><p>Check API behavior, user workflows, inputs and expected outputs. Each source-grounded behavior gets its own test plan. No functional executor is installed yet: AI drafts the steps and evidence needed, but does not run tests.</p></div>
      <PlanExperience key={contextKey + ':functional'} source={input} architectureId={architectureId} targetId="functional-requirements" functional onAnalyze={onAnalyze}/>
    </section>
    <div className="verification-group-heading"><h2>Non-functional Verification</h2><p>Check reliability, timeout handling, performance and side-effect safety. Run each installed check directly. For checks without an executor, generate a concrete AI plan with setup, steps and required evidence.</p></div>
    <div className="suggested-heading"><div><h2 id="suggested-title">Suggested Verifications</h2><p>Identify concrete checks for this architecture, then run a check or draft its plan.</p></div>
      <button className="primary-button" disabled={verification.status === "RUNNING" || stale || state.status === "DISCOVERING" || (state.status === "ERROR" && state.stale)} onClick={() => discover(Boolean(state.result))}>{state.status === "DISCOVERING" ? "Discovering…" : state.status === "READY" ? "Regenerate" : "Discover Verifications"}</button></div>
    {state.status === "IDLE" && <p className="discovery-note">Discover grounded suggestions using the configured model. Normalized architecture metadata is sent to the provider.</p>}
    {state.status === "DISCOVERING" && <p role="status" className="discovery-note">Selecting worthwhile checks and validating their architecture grounding…</p>}
    {state.status === "ERROR" && <div role="alert" className="discovery-error" data-stale={state.stale}><p>{state.error}</p>{state.stale && <button onClick={onAnalyze}>Analyze Repository again →</button>}</div>}
    {state.status === "EMPTY" && <p role="status" className="discovery-note">{intent?.mode === "ON_DEMAND" ? "No currently supported evaluation matches this request." : "No supported evaluation was selected. This does not establish that the system meets any requirement."}</p>}
    {!demoOutcomes && (!activeEvaluationId || !state.result?.candidates.some(item => item.id === activeEvaluationId)) && verificationPanel}
    {state.result && <>
      <div className="verification-demo-controls">
        <button className="secondary-button" disabled={verification.status === 'RUNNING'} onClick={simulate}>{demoOutcomes ? 'Refresh demo results' : 'Show demo results'}</button>
        {demoOutcomes && <button className="secondary-button" onClick={() => setDemoOutcomes(null)}>Exit demo mode</button>}
        <p>Demo preview only · Simulated labels are not verification results.</p>
      </div>
      {demoOutcomes && <div className="verification-demo-banner" role="status"><strong>DEMO MODE · SIMULATED · NOT ACTUALLY VERIFIED</strong><p>模拟结果 · 未实际验证。Labels below are simulated, unrelated to repository correctness. No verifier ran; no Evidence or Verdict was created or saved. Exit demo mode to view real inspection results.</p></div>}
      <div className="discovery-context"><span>{state.result.catalog_version}</span><span title={state.result.architecture_id}>Snapshot <code>{state.result.architecture_id.slice(0, 12)}</code></span><span>{savedNote(state.result.stored) ?? "Fresh server-side analysis"}</span></div>
      {state.result.candidates.map(item => {
        const outcome = verification.status === 'RESULT' && verification.result.evaluation_id === item.id ? verification.result : null;
        const cannotVerify = !item.can_execute || item.applicability !== 'APPLICABLE' || outcome?.verdict_status === 'NOT_VERIFIABLE' || outcome?.applicability === 'NOT_APPLICABLE';
        const capability = outcome?.verdict_status === 'VERIFIED' || outcome?.verdict_status === 'VIOLATED'
          ? `Verification result · ${outcome.verdict_status}`
          : cannotVerify ? 'Cannot verify conclusively with current support' : 'Ready for static inspection · Result pending';
        return <article className="suggestion" key={item.id}>
        <div className="suggestion-title"><h3>{item.name}</h3><span>{item.category}</span></div><p className="check-capability">{demoOutcomes ? "Demo preview · Not executed" : capability}</p><p>{item.reason}</p>
        {demoOutcomes && <div className="simulated-check-result" aria-label="Simulated result"><strong>SIMULATED · NOT ACTUALLY VERIFIED</strong>{item.can_execute ? <p className={`result-status ${demoOutcomes[item.id]?.toLowerCase()}`}><b>{demoOutcomes[item.id]}</b> · simulated demo label</p> : <p>Cannot execute · No installed verifier. No simulated verification result.</p>}</div>}
        {!demoOutcomes && cannotVerify && <p className="check-unavailable">{outcome?.verdict_status === 'NOT_VERIFIABLE' ? 'Inspection completed, but required evidence or scope is unresolved. No pass/fail conclusion is available.' : !item.can_execute ? 'No installed verifier can execute this check. An AI plan is a draft, not a verification result.' : 'Applicability is not established. You can inspect available scope, but a conclusive result is not guaranteed.'}</p>}
        <dl className="suggestion-labels">
          <div><dt>Applicability</dt><dd className={`suggestion-applicability ${item.applicability.toLowerCase()}`}>{item.applicability}</dd></div>
          <div><dt>Execution support</dt><dd className={`suggestion-support ${item.execution_support.toLowerCase()}`}>{item.execution_support}</dd></div>
          <div><dt>Mode</dt><dd>{item.verification_mode}</dd></div><div><dt>Priority</dt><dd>{item.priority}</dd></div>
        </dl>
        {item.execution_support === "NOT_AVAILABLE" && <p className="discovery-note">Plan needed · No executor is installed for this check. Generate steps, prerequisites and evidence to collect.</p>}
        {item.execution_support === "PARTIAL" && <p className="discovery-note">Relevant to this architecture, but current executable coverage is limited.</p>}
        {!demoOutcomes && (item.can_execute ? <button className="primary-button" disabled={verification.status === "RUNNING" || stale} onClick={() => verify(item.id)}>{cannotVerify ? "Inspect available scope" : "Run Verification"}</button> : <PlanExperience key={contextKey + ':' + item.id} source={input} architectureId={architectureId} targetId={item.id} disabled={verification.status === "RUNNING" || stale} onAnalyze={onAnalyze}/>) }
        <div className="check-evidence"><strong>Evidence needed for this check</strong><ul>{item.required_evidence.map(text => <li key={text}>{text}</li>)}</ul><p>No new evidence is collected until a check is run.</p></div>
        <details><summary>Grounding and required evidence</summary>
          <div className="suggestion-detail"><strong>Architecture subjects</strong>{item.architecture_subject_ids.map(id => <code key={id}>{id}</code>)}

          {item.limitations.length > 0 && <><strong>Limitations</strong><ul>{item.limitations.map(text => <li key={text}>{text}</li>)}</ul></>}</div>
        </details>
        {!demoOutcomes && activeEvaluationId === item.id && verificationPanel}
        {!demoOutcomes && item.can_execute && (item.execution_support === 'PARTIAL' || (verification.status === 'RESULT' && verification.result.evaluation_id === item.id && verification.result.verdict_status === 'NOT_VERIFIABLE')) && <div className="plan-followup"><p className="discovery-note">Need to investigate beyond the static check? Draft a source-grounded plan for the remaining behavior.</p><PlanExperience key={contextKey + ':followup:' + item.id} source={input} architectureId={architectureId} targetId={item.id} disabled={verification.status === 'RUNNING' || stale} onAnalyze={onAnalyze}/></div>}
      </article>; })}
      {(state.result.input_truncated || state.result.limitations.length > 0) && <details className="discovery-limitations"><summary>Discovery limitations{state.result.input_truncated ? " · input truncated" : ""}</summary>{state.result.limitations.map(text => <p key={text}>{text}</p>)}</details>}
    </>}

  </section>;
}
