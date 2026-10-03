import {sourceBody, type RepositorySource} from '../repository-source';
import {citation, type Citation} from '../understanding/understanding-client';
export type PlanDraft={title:string;objective:string;prerequisites:string[];steps:string[];required_evidence:string[];acceptance_questions:string[];citations:Citation[];status:'DRAFT_NOT_EXECUTED'};
export type PlanningResult={architecture_id:string;target_id:string;kind:'FUNCTIONAL'|'NON_FUNCTIONAL';model:string;prompt_version:string;plans:PlanDraft[];limitations:string[];input_truncated:boolean};
export class PlanningError extends Error { constructor(message:string,readonly code:string){super(message);} }
const strings=(v:unknown):v is string[]=>Array.isArray(v)&&v.every(x=>typeof x==='string');
const draft=(v:any):v is PlanDraft=>v&&['title','objective'].every(k=>typeof v[k]==='string')&&['prerequisites','steps','required_evidence','acceptance_questions'].every(k=>strings(v[k])&&v[k].length>0&&v[k].length<=8)&&v.status==='DRAFT_NOT_EXECUTED'&&Array.isArray(v.citations)&&v.citations.length>0&&v.citations.length<=5&&v.citations.every(citation);
export async function generatePlan(source:RepositorySource|string,architectureId:string,targetId:string,signal:AbortSignal):Promise<PlanningResult>{
 let r:Response;
 try {r=await fetch('/api/evaluations/plan',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...sourceBody(source),expected_architecture_id:architectureId,target_id:targetId}),signal});}
 catch {throw new PlanningError('Cannot reach the planning service. Check the local backend connection.','PLAN_CONNECTION_FAILED');}
 let d;try{d=await r.json();}catch{throw new PlanningError(r.ok?'Planning returned an invalid response.':`The planning service connection failed (HTTP ${r.status}). No plan was returned; it may still be generating on the backend.`,r.ok?'PLAN_INVALID_RESPONSE':'PLAN_GATEWAY_FAILED');}
 if(!r.ok)throw new PlanningError(typeof d?.error?.message==='string'?d.error.message:'Planning could not be completed.',String(d?.error?.code??'PLAN_FAILED'));
 if(!d||!Array.isArray(d.plans)||d.plans.length>5||!d.plans.every(draft)||!strings(d.limitations)||typeof d.input_truncated!=='boolean'||typeof d.model!=='string'||typeof d.prompt_version!=='string')throw new Error('Planning returned an invalid response.');
 if(d.architecture_id!==architectureId)throw new PlanningError('The repository snapshot changed. Analyze again.','ANALYSIS_STALE');
 if(d.target_id!==targetId||d.kind!==(targetId==='functional-requirements'?'FUNCTIONAL':'NON_FUNCTIONAL'))throw new Error('Planning returned a different target.');
 return d;
}
