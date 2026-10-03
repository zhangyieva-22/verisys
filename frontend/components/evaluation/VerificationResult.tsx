import type { VerificationResult as Result } from '@/lib/evaluation/verification-client';
import { savedNote } from '@/lib/stored';

// Where a finite timeout comes from; absent for MISSING/UNKNOWN and for policies that only accept per-call values.
const TIMEOUT_SOURCES: Record<string, string> = {
  call: 'Timeout set on this call',
  client: "Inherited from the client's timeout",
  library_default: 'Relies on the httpx 5-second default',
};

export function VerificationResult({ result, onRerun }: { result: Result; onRerun?: () => void }) {
  return <section className="verification-result" aria-label="Verification result">
    <header><span>STATIC VERIFICATION RESULT</span><h3>{result.evaluation_name}</h3></header>
    {savedNote(result.stored) && <p className="saved-note">{savedNote(result.stored)}{onRerun && <button onClick={onRerun}>Re-run verification</button>}</p>}
    <div className={`verification-outcome result-status ${result.verdict_status ? "verified" : result.applicability.toLowerCase()}`}>{result.verdict_status ? "VERIFIED" : result.applicability}</div>
    {result.verdict_status === 'NOT_VERIFIABLE' && <p className="check-unavailable"><strong>Cannot verify:</strong> this inspection did not establish a conclusive result. Review the missing evidence and scope limitations below.</p>}
    <dl className="suggestion-labels"><div><dt>Applicability</dt><dd>{result.applicability}</dd></div>
      <div><dt>Execution</dt><dd>{result.execution_status}</dd></div><div><dt>Mode</dt><dd>{result.verification_mode}</dd></div>
      {result.verdict_status && <div><dt>Verdict</dt><dd className={`result-status ${result.verdict_status.toLowerCase()}`}>{result.verdict_status}</dd></div>}</dl>
    <p><strong>Policy:</strong> {result.policy}</p>
    <p>{result.summary}</p>
    <p className="result-explanation">Inspected calls: {result.counts.total} · Configured: {result.counts.configured} · Missing: {result.counts.missing} · Unresolved: {result.counts.unknown}.</p>
    {!result.coverage_complete && <p className="result-explanation">The observations below describe inspected calls. They do not confirm coverage of every call in the repository. Expand policy and inspection limitations for the remaining gaps.</p>}
    <div className="verification-counts">{Object.entries(result.counts).map(([label, value]) => <span key={label}><strong>{value}</strong> {label}</span>)}</div>
    <p className="coverage">{result.coverage_percent !== null ? `Definitive coverage: ${result.coverage_percent}%` : result.applicability === 'NOT_APPLICABLE' ? 'Coverage is not applicable.' : 'Coverage incomplete · no definitive percentage available.'}</p>
    <p className="discovery-note">Static source configuration only. No runtime timeout behavior or reliability was measured.</p>
    <h4>Source-backed evidence</h4>
    {result.evidence.map(e => <article className="verification-evidence" key={e.id}>
      <code>{e.source_location ? `${e.source_location.file}:${e.source_location.line}` : e.source}</code>
      {e.observation.kind === 'call' ? <><div><strong>{String(e.observation.service)}</strong> · <code>{e.observation.operation == null ? 'Operation unresolved' : String(e.observation.operation)}</code></div>
        <span className={`observation-status ${String(e.observation.timeout_status).toLowerCase()}`}>{String(e.observation.timeout_status)}</span>
        <p>Classification reason: <code>{String(e.observation.reason)}</code></p>
        {typeof e.observation.timeout_source === 'string' && <p className="timeout-source">{TIMEOUT_SOURCES[e.observation.timeout_source] ?? <code>{e.observation.timeout_source}</code>}</p>}
        {e.observation.timeout_literal !== undefined && <p>Observed timeout literal: <code>{String(e.observation.timeout_literal)}</code></p>}</> : <p>Inspection scope manifest</p>}
      <details><summary>Evidence provenance</summary><code className="evidence-id">{e.id}</code><p>{e.type} · {e.tool}</p><p>{e.claim}</p>
        {e.source_location?.column != null && <p>UTF-8 byte column: {e.source_location.column}</p>}
        <pre>{JSON.stringify(e.observation, null, 2)}</pre>{e.limitations.map((l,i) => <p key={i}>{l}</p>)}</details>
    </article>)}
    {result.limitations.length > 0 && <details><summary>Policy and inspection limitations</summary><ul>{result.limitations.map((l,i)=><li key={i}>{l}</li>)}</ul></details>}
    <details><summary>Structured verification trace</summary><ol className="verification-trace">{result.trace.map((t,i)=><li key={i}><strong>{t.type}</strong> · {t.stage}<p>{t.summary}</p>{t.evidence_ids.map(id=><code className="evidence-id" key={id}>{id}</code>)}</li>)}</ol></details>
    {result.verdict_status && <details><summary>Verdict evidence references</summary>{result.verdict_evidence_ids.map(id=><code className="evidence-id" key={id}>{id}</code>)}</details>}
  </section>;
}
