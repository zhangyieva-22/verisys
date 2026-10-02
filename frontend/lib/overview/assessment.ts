import type { ArchitectureGraph, ExecutionFlow, ExecutionStep } from '../architecture/types';
import type { SuggestedVerification } from '../evaluation/discovery-client';
import type { VerificationState, VerificationResult } from '../evaluation/verification-client';

export type AssessmentItem = { title: string; explanation: string; status: string };
export type NextAction = { title: string; explanation: string; destination: 'Architecture' | 'Verifications' };
export function resultStatus(result: VerificationResult): string {
  if (result.applicability === 'NOT_APPLICABLE') return 'Not applicable';
  if (result.execution_status === 'FAILED') return 'Execution failed — no engineering conclusion';
  if (result.execution_status !== 'COMPLETED') return 'Verification not completed';
  return ({ VERIFIED: 'Verified', VIOLATED: 'Violation found', NOT_VERIFIABLE: 'Not verifiable with current evidence' } as const)[result.verdict_status!] ?? 'No verdict recorded';
}
export function technicalStatus(candidate: SuggestedVerification, verification: VerificationState): string {
  if (verification.status === 'RESULT' && verification.result.evaluation_id === candidate.id) return resultStatus(verification.result);
  if (candidate.applicability === 'NOT_APPLICABLE') return 'Not applicable';
  if (candidate.applicability === 'UNKNOWN') return 'Relevance identified — applicability not fully established';
  if (candidate.execution_support === 'PARTIAL') return candidate.can_execute ? 'Ready to verify — limited verification coverage' : 'Limited verification coverage — verification not available yet';
  if (!candidate.can_execute) return 'Verification not available yet';
  return 'Ready to verify';
}
export const flowLabel = (step: ExecutionStep) => step.type === 'WORKFLOW' ? 'Agent Workflow' : step.type === 'TOOL_EXECUTION' ? 'Tool Execution' : step.label === 'Handler return' ? 'Return to API' : step.label;
/** Each row is a supplied transition group, never an inferred execution path. */
export function flowRows(flow: ExecutionFlow) {
  const steps = new Map(flow.steps.map(step => [step.id, step]));
  const ordered: ExecutionStep[] = [];
  const queue = flow.trigger ? [flow.trigger] : flow.steps.filter(s => !flow.transitions.some(t => t.target === s.id)).map(s => s.id);
  const seen = new Set<string>();
  while (queue.length) {
    const id = queue.shift()!;
    if (seen.has(id) || !steps.has(id)) continue;
    seen.add(id); ordered.push(steps.get(id)!);
    queue.push(...flow.transitions.filter(t => t.source === id).map(t => t.target));
  }
  ordered.push(...flow.steps.filter(s => !seen.has(s.id)));
  return ordered.flatMap(step => {
    const outgoing = flow.transitions.filter(t => t.source === step.id && steps.has(t.target));
    return outgoing.length ? [{ source: flowLabel(step), targets: outgoing.map(t => ({
      label: flowLabel(steps.get(t.target)!), condition: t.condition,
    })) }] : [];
  });
}
export function nonTechnicalItems(graph: ArchitectureGraph, candidates: SuggestedVerification[]): AssessmentItem[] {
  const items: AssessmentItem[] = [];
  if (graph.execution_flows?.some(flow => flow.transitions.some(t => t.type === 'CONDITIONAL' && t.condition?.split(':').at(-1)?.trim() === 'retry'))) {
    items.push({title:'Operational resilience', explanation:'A source-declared retry branch is visible. This establishes a possible control path, not recovery behavior under production failures.',status:'Requires runtime evidence'});
  }
  if (graph.nodes.some(n => n.type === 'TOOL')) items.push({title:'Operational ownership of tools', explanation:'Declared tools are present. The current architecture data does not identify who owns their operation or approves their use.',status:'Requires external / organizational evidence'});
  if (graph.nodes.some(n => n.type === 'DATASTORE')) items.push({title:'Data governance',explanation:`${graph.nodes.filter(n => n.type === 'DATASTORE').map(n => n.label).join(', ')} is detected. Storage presence does not establish retention, privacy policy, or access governance.`,status:'Not established'});
  if (candidates.some(c => c.verification_mode === 'PERFORMANCE' || c.verification_mode === 'RUNTIME')) items.push({title:'Runtime operating conditions',explanation:'Selected evaluations require runtime or performance evidence. Deployment workload and operating conditions are not represented by this static architecture assessment.',status:'Not assessed'});
  return items;
}
export function nextActions(candidates: SuggestedVerification[], verification: VerificationState, context: AssessmentItem[] = []): NextAction[] {
  const result = verification.status === 'RESULT' ? verification.result : null;
  const completed = result?.execution_status === 'COMPLETED';
  const actions: NextAction[] = candidates.filter(c => c.can_execute && c.applicability !== 'NOT_APPLICABLE' && !(completed && result?.evaluation_id === c.id)).map(c => ({title:`Run ${c.name}`,explanation:c.execution_support === 'PARTIAL' ? 'An installed verifier can collect evidence within its limited supported scope.' : 'An installed verifier can collect evidence for this check.',destination:'Verifications'}));
  if (completed && result?.verdict_status === 'VIOLATED') actions.push({title:`Review ${result.evaluation_name} evidence`,explanation:'Review the source-backed finding and coverage limitations before deciding on a change.',destination:'Verifications'});
  if (completed && result?.verdict_status === 'NOT_VERIFIABLE') actions.push({title:`Establish evidence for ${result.evaluation_name}`,explanation:result.limitations[0] ?? 'Review the recorded evidence limitations to identify what remains unresolved.',destination:'Verifications'});
  for (const c of candidates.filter(c => !c.can_execute && c.applicability !== 'NOT_APPLICABLE')) actions.push({title:`Plan evidence collection for ${c.name}`,explanation:`Verification is not available yet. Required evidence: ${c.required_evidence.join('; ') || 'review the evaluation requirements in Verifications'}.`,destination:'Verifications'});
  for (const item of context) {
    const evidence = item.title === 'Data governance' ? 'retention, privacy and access-policy documentation' : item.title === 'Operational ownership of tools' ? 'ownership and operational approval documentation' : 'controlled runtime observations and defined operating conditions';
    actions.push({title:`Establish ${item.title.toLowerCase()} context`,explanation:`This context is not established by static source structure. Collect ${evidence}.`,destination:'Architecture'});
  }
  return actions.slice(0,3);
}
