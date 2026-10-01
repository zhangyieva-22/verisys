import type { VerificationResult as Result } from '@/lib/evaluation/verification-client';

export function VerificationResult({ result }: { result: Result }) {
  return <section className="verification-result" aria-label="Verification result">
    <header><span>STATIC VERIFICATION RESULT</span><h3>{result.evaluation_name}</h3></header>
    <div className={`verification-outcome result-status ${(result.verdict_status ?? result.applicability).toLowerCase()}`}>{result.verdict_status ?? result.applicability}</div>
    <dl className="suggestion-labels"><div><dt>Applicability</dt><dd>{result.applicability}</dd></div>
      <div><dt>Execution</dt><dd>{result.execution_status}</dd></div><div><dt>Mode</dt><dd>{result.verification_mode}</dd></div>
      {result.verdict_status && <div><dt>Verdict</dt><dd className={`result-status ${result.verdict_status.toLowerCase()}`}>{result.verdict_status}</dd></div>}</dl>
    <p><strong>Policy:</strong> {result.policy}</p>
    <p>{result.summary}</p>
    <div className="verification-counts">{Object.entries(result.counts).map(([label, value]) => <span key={label}><strong>{value}</strong> {label}</span>)}</div>
    <p className="coverage">{result.coverage_percent !== null ? `Definitive coverage: ${result.coverage_percent}%` : result.applicability === 'NOT_APPLICABLE' ? 'Coverage is not applicable.' : 'Coverage incomplete · no definitive percentage available.'}</p>
    <p className="discovery-note">Static per-call configuration only. No runtime timeout behavior or reliability was measured.</p>
    <h4>Source-backed evidence</h4>
    {result.evidence.map(e => <article className="verification-evidence" key={e.id}>
      <code>{e.source_location ? `${e.source_location.file}:${e.source_location.line}` : e.source}</code>
      {e.observation.kind === 'call' ? <><div><strong>{String(e.observation.service)}</strong> · <code>{e.observation.operation == null ? 'Operation unresolved' : String(e.observation.operation)}</code></div>
        <span className={`observation-status ${String(e.observation.timeout_status).toLowerCase()}`}>{String(e.observation.timeout_status)}</span>
        <p>Classification reason: <code>{String(e.observation.reason)}</code></p>
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
