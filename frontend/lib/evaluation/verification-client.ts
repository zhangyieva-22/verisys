import { DiscoveryApiError } from './discovery-client';
export type VerificationResult = {
  evaluation_id: string; evaluation_name: string; architecture_id: string;
  applicability: 'APPLICABLE' | 'NOT_APPLICABLE' | 'UNKNOWN';
  execution_status: 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED' | 'NOT_RUN';
  verification_mode: 'STATIC'; verdict_status: 'VERIFIED' | 'VIOLATED' | 'NOT_VERIFIABLE' | null;
  verdict_evidence_ids: string[]; policy: string; summary: string;
  counts: { configured: number; missing: number; unknown: number; total: number };
  coverage_complete: boolean; coverage_percent: number | null;
  evidence: { id: string; type: string; source: string; tool: string; claim: string;
    source_location: { file: string; line: number; column: number | null } | null;
    observation: Record<string, unknown>; limitations: string[] }[];
  limitations: string[]; trace: { type: string; stage: string; summary: string; evidence_ids: string[] }[];
};
export type VerificationState =
  | { status: 'IDLE' | 'RUNNING'; result: null; error: null }
  | { status: 'RESULT'; result: VerificationResult; error: null }
  | { status: 'ERROR'; result: null; error: string; code: string };
export const idleVerification: VerificationState = { status: 'IDLE', result: null, error: null };
const strings = (v: unknown): v is string[] => Array.isArray(v) && v.every(x => typeof x === 'string');
export async function runVerification(path: string, id: string, architectureId: string, signal: AbortSignal): Promise<VerificationResult> {
  let response: Response;
  try { response = await fetch('/api/evaluations/verify', { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ repository_path: path, evaluation_id: id, expected_architecture_id: architectureId }), signal }); }
  catch { throw new Error('Cannot reach verification. Check the local backend connection.'); }
  let d;
  try { d = await response.json(); } catch { throw new Error('Verification returned an invalid response.'); }
  if (!response.ok) throw new DiscoveryApiError(typeof d?.error?.message === 'string' ? d.error.message : 'Verification failed.', typeof d?.error?.code === 'string' ? d.error.code : 'VERIFICATION_FAILED');
  if (!d || d.evaluation_id !== id || typeof d.evaluation_name !== 'string' || typeof d.summary !== 'string' || typeof d.policy !== 'string' ||
    !['APPLICABLE','NOT_APPLICABLE','UNKNOWN'].includes(d.applicability) ||
    !['PENDING','RUNNING','COMPLETED','FAILED','NOT_RUN'].includes(d.execution_status) || d.verification_mode !== 'STATIC' ||
    ![null,'VERIFIED','VIOLATED','NOT_VERIFIABLE'].includes(d.verdict_status) ||
    !strings(d.verdict_evidence_ids) || !strings(d.limitations) || typeof d.coverage_complete !== 'boolean' ||
    !(d.coverage_percent === null || (typeof d.coverage_percent === 'number' && Number.isFinite(d.coverage_percent))) ||
    !['configured','missing','unknown','total'].every(k => Number.isInteger(d.counts?.[k]) && d.counts[k] >= 0) ||
    !Array.isArray(d.evidence) || !d.evidence.every((e: VerificationResult['evidence'][number]) => e &&
      ['id','type','source','tool','claim'].every(k => typeof (e as unknown as Record<string, unknown>)[k] === 'string') && strings(e.limitations) &&
      e.observation && typeof e.observation === 'object' && !Array.isArray(e.observation) &&
      (e.source_location === null || (typeof e.source_location?.file === 'string' && Number.isInteger(e.source_location.line) && e.source_location.line > 0))) ||
    !Array.isArray(d.trace) || !d.trace.every((t: VerificationResult['trace'][number]) => t && typeof t.type === 'string' && typeof t.stage === 'string' && typeof t.summary === 'string' && strings(t.evidence_ids))) throw new Error('Verification returned an invalid response.');
  if (d.architecture_id !== architectureId) throw new DiscoveryApiError('Verification snapshot changed. Analyze the repository again.', 'ANALYSIS_STALE');
  return d as VerificationResult;
}
