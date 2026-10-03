import './dom-setup';
import test from 'node:test';
import assert from 'node:assert/strict';
import {createElement} from 'react';
import {render,fireEvent,waitFor,cleanup} from '@testing-library/react';
import {PlanExperience} from '../components/evaluation/PlanExperience';
import {generatePlan} from '../lib/evaluation/planning-client';
const originalFetch=globalThis.fetch;
const props={source:'/projects/test',architectureId:'a'.repeat(64),targetId:'api-latency-v1',onAnalyze:()=>{}};
const citation={path:'app.py',start_line:3,end_line:3,quote:'@app.post("/notes")',excerpt_kind:'ROUTE_SOURCE'};
const payload={architecture_id:props.architectureId,target_id:props.targetId,kind:'NON_FUNCTIONAL',model:'fake',prompt_version:'v1',input_truncated:false,limitations:['Draft only.'],plans:[{title:'Measure the notes endpoint',objective:'Measure latency with a confirmed workload.',prerequisites:['Isolated running test environment.'],steps:['Send representative requests.'],required_evidence:['Latency measurements.'],acceptance_questions:['Confirm the latency threshold.'],citations:[citation],status:'DRAFT_NOT_EXECUTED'}]};
const response=(d:unknown,status=200)=>new Response(JSON.stringify(d),{status});
function reset(){cleanup();globalThis.fetch=originalFetch;}

test('planning is opt-in, deduplicated and displays a grounded draft without verdict',async()=>{
 let calls=0,finish!:(r:Response)=>void;
 globalThis.fetch=async(u,o)=>{calls++;assert.equal(u,'/api/evaluations/plan');assert.deepEqual(JSON.parse(String(o?.body)),{repository_path:props.source,expected_architecture_id:props.architectureId,target_id:props.targetId});return new Promise<Response>(resolve=>{finish=resolve;});};
 try{const ui=render(createElement(PlanExperience,props));assert.equal(calls,0);fireEvent.click(ui.getByRole('button',{name:'Generate verification plan'}));fireEvent.click(ui.getByRole('button',{name:'Generating plan…'}));assert.equal(calls,1);finish(response(payload));await waitFor(()=>assert.ok(ui.getByText(payload.plans[0].title)));assert.ok(ui.getByText('AI PLAN DRAFT · NOT EXECUTED'));assert.ok(ui.getByText('app.py:3'));assert.ok(ui.getByText('Confirm the latency threshold.'));assert.equal(ui.queryByText('VERIFIED'),null);assert.equal(ui.queryByRole('button',{name:'Run Verification'}),null);}finally{reset();}
});

test('provider error remains error and is never an empty successful plan',async()=>{
 globalThis.fetch=async()=>response({error:{code:'PLAN_PROVIDER_FAILED',message:'Provider unavailable.'}},502);
 try{const ui=render(createElement(PlanExperience,props));fireEvent.click(ui.getByRole('button',{name:'Generate verification plan'}));await waitFor(()=>assert.ok(ui.getByRole('alert')));assert.equal(ui.queryByText('AI PLAN DRAFT · NOT EXECUTED'),null);}finally{reset();}
});

test('functional empty draft is honest and separately classified',async()=>{
 globalThis.fetch=async()=>response({...payload,target_id:'functional-requirements',kind:'FUNCTIONAL',plans:[]});
 try{const ui=render(createElement(PlanExperience,{...props,targetId:'functional-requirements',functional:true}));fireEvent.click(ui.getByRole('button',{name:'Generate functional test plans'}));await waitFor(()=>assert.ok(ui.getByText('No grounded plan was returned. No verification was executed.')));}finally{reset();}
});

test('context change aborts pending plan and ignores late old response',async()=>{
 let finish!:(r:Response)=>void,signal:AbortSignal|null|undefined;
 globalThis.fetch=async(_,o)=>{signal=o?.signal;return new Promise<Response>(resolve=>{finish=resolve;});};
 try{const ui=render(createElement(PlanExperience,props));fireEvent.click(ui.getByRole('button',{name:'Generate verification plan'}));ui.rerender(createElement(PlanExperience,{...props,architectureId:'b'.repeat(64)}));assert.equal(signal?.aborted,true);finish(response(payload));await new Promise(resolve=>setTimeout(resolve,10));assert.equal(ui.queryByText(payload.plans[0].title),null);assert.ok(ui.getByRole('button',{name:'Generate verification plan'}));}finally{reset();}
});

test('client rejects wrong snapshot, target and invented executed status',async()=>{
 try{for(const changed of [{architecture_id:'b'.repeat(64)},{target_id:'other'},{plans:[{...payload.plans[0],status:'VERIFIED'}]}]){globalThis.fetch=async()=>response({...payload,...changed});await assert.rejects(generatePlan(props.source,props.architectureId,props.targetId,new AbortController().signal));}}finally{reset();}
});


test('proxy non-JSON failure is reported as a connection error, not model validation',async()=>{
 try{globalThis.fetch=async()=>new Response('Internal Server Error',{status:500});
 await assert.rejects(generatePlan(props.source,props.architectureId,props.targetId,new AbortController().signal),/connection failed \(HTTP 500\)/);
 }finally{reset();}
});
