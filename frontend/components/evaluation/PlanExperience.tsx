"use client";
import {useEffect,useRef,useState} from 'react';
import {generatePlan,PlanningError,type PlanningResult} from '@/lib/evaluation/planning-client';
import type {RepositorySource} from '@/lib/repository-source';
export function PlanExperience({source,architectureId,targetId,functional=false,disabled=false,onAnalyze}:{source:RepositorySource|string;architectureId:string;targetId:string;functional?:boolean;disabled?:boolean;onAnalyze:()=>void}){
 const [state,setState]=useState<'IDLE'|'GENERATING'|'READY'|'ERROR'>('IDLE');
 const [result,setResult]=useState<PlanningResult|null>(null);
 const [error,setError]=useState<string|null>(null);const [stale,setStale]=useState(false);
 const pending=useRef<AbortController|null>(null);const context=JSON.stringify([source,architectureId,targetId]);
 useEffect(()=>{setState('IDLE');setResult(null);setError(null);setStale(false);return()=>{pending.current?.abort();pending.current=null;};},[context]);
 const generate=async()=>{
  if(pending.current||disabled||stale)return;
  const request=new AbortController();pending.current=request;setState('GENERATING');setResult(null);setError(null);
  try{const next=await generatePlan(source,architectureId,targetId,request.signal);if(!request.signal.aborted){setResult(next);setState('READY');}}
  catch(e){if(!request.signal.aborted){setState('ERROR');setError(e instanceof Error?e.message:'Planning failed.');setStale(e instanceof PlanningError&&e.code==='ANALYSIS_STALE');}}
  finally{if(pending.current===request)pending.current=null;}
 };
 return <div className="plan-experience" data-plan-state={state}>
  <button className={functional ? "primary-button" : "secondary-button"} disabled={disabled||stale||state==='GENERATING'} onClick={()=>void generate()}>{state==='GENERATING'?'Generating plan…':result?'Regenerate plan':functional?'Generate functional test plans':'Generate verification plan'}</button>
  <p className="plan-disclosure">AI drafting · sends bounded documentation and source excerpts with likely secrets redacted. Nothing executes.</p>
  {state==='GENERATING'&&<p role="status">Drafting test steps and checking source citations…</p>}
  {state==='ERROR'&&<div role="alert" className="discovery-error"><p>{error}</p>{stale&&<button onClick={onAnalyze}>Analyze Repository again →</button>}</div>}
  {result&&<div className="plan-results"><p className="plan-label">AI PLAN DRAFT · NOT EXECUTED</p>{!result.plans.length&&<p>No grounded plan was returned. No verification was executed.</p>}
    {result.plans.map((plan,i)=><article className="plan-draft" key={i}><h3>{plan.title}</h3><p className="check-capability">Plan draft · Execution required · Not executed</p><p>{plan.objective}</p>
     <div className="plan-draft-columns"><div><h4>Prepare</h4><ul>{plan.prerequisites.map((v,j)=><li key={j}>{v}</li>)}</ul><h4>Test steps</h4><ol>{plan.steps.map((v,j)=><li key={j}>{v}</li>)}</ol></div><div><h4>Evidence to collect</h4><ul>{plan.required_evidence.map((v,j)=><li key={j}>{v}</li>)}</ul><h4>Acceptance criteria to confirm</h4><ul>{plan.acceptance_questions.map((v,j)=><li key={j}>{v}</li>)}</ul></div></div>
     <details><summary>Source grounding</summary>{plan.citations.map((c,j)=><div className="plan-citation" key={j}><code>{c.path}:{c.start_line}{c.end_line!==c.start_line?`–${c.end_line}`:''}</code><blockquote>{c.quote}</blockquote></div>)}</details>
    </article>)}<details><summary>Scope and limitations{result.input_truncated?' · input truncated':''}</summary><p>Model: {result.model}</p><ul>{result.limitations.map((v,i)=><li key={i}>{v}</li>)}</ul></details>
  </div>}
 </div>;
}
