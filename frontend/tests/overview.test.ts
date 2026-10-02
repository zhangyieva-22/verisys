import './dom-setup';
import test from 'node:test';
import assert from 'node:assert/strict';
import {createElement} from 'react';
import {render,cleanup,fireEvent,within} from '@testing-library/react';
import {ProjectOverview} from '../components/projects/ProjectOverview';
import {technicalStatus,nonTechnicalItems,nextActions,flowRows,resultStatus} from '../lib/overview/assessment';
import type {AnalysisResult} from '../lib/architecture/analysis-client';
import type {SuggestedVerification,DiscoveryState} from '../lib/evaluation/discovery-client';
import type {VerificationResult,VerificationState} from '../lib/evaluation/verification-client';
import {demoGraph} from '../lib/architecture/demo';

const hash='a'.repeat(64);
const candidate:SuggestedVerification={id:'timeout',name:'External API Timeout Coverage',category:'Reliability',reason:'Supported direct calls are present.',architecture_subject_ids:[],applicability:'APPLICABLE',priority:'MEDIUM',required_evidence:['Per-call static timeout observations'],verification_mode:'STATIC',execution_support:'SUPPORTED',limitations:[],can_execute:true};
const idle:VerificationState={status:'IDLE',result:null,error:null};
const latest:VerificationResult={evaluation_id:candidate.id,evaluation_name:candidate.name,architecture_id:hash,applicability:'APPLICABLE',execution_status:'COMPLETED',verification_mode:'STATIC',verdict_status:'VIOLATED',verdict_evidence_ids:['e1'],policy:'fixture',summary:'One call lacks a timeout.',counts:{configured:2,missing:1,unknown:0,total:3},coverage_complete:true,coverage_percent:66.7,evidence:[{id:'e1',type:'STATIC_ANALYSIS',source:'app.py',tool:'static',claim:'timeout',source_location:{file:'app.py',line:12,column:0},observation:{},limitations:[]}],limitations:['Symbolic settings are unresolved.'],trace:[]};
const result:AnalysisResult={architecture_id:hash,repository:{name:'owner/fixture',path:null},architecture:{},graph:demoGraph};
const discovered=(candidates=[candidate]):DiscoveryState=>({status:candidates.length?'READY':'EMPTY',result:{architecture_id:hash,catalog_version:'v1',input_truncated:false,limitations:[],candidates},error:null});
function mount(overrides:Partial<Parameters<typeof ProjectOverview>[0]>={}) {return render(createElement(ProjectOverview,{result,discovery:discovered(),verification:idle,analyzedAt:'2026-10-01T12:00:00Z',onArchitecture:()=>{},onVerifications:()=>{},onReanalyze:()=>{},...overrides}));}

test('Overview is an assessment with summary, scope, flow, semantic components and separate groups',()=>{
 try{const ui=mount();for(const name of ['Executive Summary','System Scope','How the System Works','Key System Components','Engineering Assessment','Technical Assessment','Non-Technical Assessment','Verification Status','Recommended Next Actions','Analysis Coverage & Limitations'])assert.ok(ui.getByRole('heading',{name}));assert.ok(ui.getByText('Observed / In Scope'));assert.ok(ui.getByText('Not Established / Not Measured'));assert.ok(ui.getAllByText(/FastAPI/).length);assert.ok(ui.getAllByText(/lookup order/).length);assert.equal(ui.queryByText(/AI-powered ecommerce/),null);assert.equal(ui.queryByText('VERIFIED'),null);assert.equal(ui.queryByText('VIOLATED'),null);}finally{cleanup();}
});
test('Technical items contain exactly title, server reason and readable status without inventing candidates',()=>{
 try{const ui=mount();const group=ui.getByRole('heading',{name:'Technical Assessment'}).closest('section')!;const item=group.querySelector('article')!;assert.ok(within(item).getByRole('heading',{name:candidate.name}));assert.ok(within(item).getByText(candidate.reason));assert.ok(within(item).getByText('Explanation'));assert.ok(within(item).getByText('Status'));assert.ok(within(item).getByText('Ready to verify'));assert.equal(group.querySelectorAll('article').length,1);assert.equal(within(group).queryByText('API Latency'),null);}finally{cleanup();}
});
test('Canonical candidate statuses map independently without claiming verification',()=>{
 assert.equal(technicalStatus(candidate,idle),'Ready to verify');
 assert.equal(technicalStatus({...candidate,can_execute:false,execution_support:'NOT_AVAILABLE'},idle),'Verification not available yet');
 assert.match(technicalStatus({...candidate,execution_support:'PARTIAL'},idle),/limited verification coverage/);
 assert.match(technicalStatus({...candidate,applicability:'UNKNOWN'},idle),/applicability not fully established/);
 assert.equal(technicalStatus({...candidate,applicability:'NOT_APPLICABLE'},idle),'Not applicable');
});
test('Completed server verdicts map directly, with irrelevant and failed execution kept separate',()=>{
 for(const [verdict,status] of [['VERIFIED','Verified'],['VIOLATED','Violation found'],['NOT_VERIFIABLE','Not verifiable with current evidence']] as const)assert.equal(resultStatus({...latest,verdict_status:verdict}),status);
 assert.equal(resultStatus({...latest,applicability:'NOT_APPLICABLE',verdict_status:null}),'Not applicable');
 assert.match(resultStatus({...latest,execution_status:'FAILED',verdict_status:null}),/no engineering conclusion/);
 assert.equal(technicalStatus(candidate,{status:'RESULT',result:{...latest,evaluation_id:'another'},error:null}),'Ready to verify');
});
test('Latest result uses server counts and coverage, no recomputed verdict, and one retained result only',()=>{
 try{const ui=mount({verification:{status:'RESULT',result:latest,error:null}});assert.ok(ui.getAllByText('Violation found').length);assert.ok(ui.getByText(/2 configured · 1 missing · 0 unknown · 3 inspected · 66.7% confirmed coverage/));assert.ok(ui.getByText(/1 completed result retained/));assert.ok(ui.getByRole('button',{name:'View Evidence'}));assert.ok(ui.getAllByRole('heading',{name:'Review External API Timeout Coverage evidence'})[0]);}finally{cleanup();}
});
test('NOT_VERIFIABLE recommends evidence limitations; no result invents no completion or evidence',()=>{
 const state:VerificationState={status:'RESULT',result:{...latest,verdict_status:'NOT_VERIFIABLE',coverage_percent:null},error:null};assert.match(nextActions([candidate],state)[0].title,/Establish evidence/);assert.equal(nextActions([candidate],state)[0].explanation,latest.limitations[0]);
 try{const ui=mount();assert.ok(ui.getByText(/0 completed results retained/));assert.equal(ui.queryByText('Evidence-backed static verification'),null);assert.equal(ui.queryByRole('button',{name:'View Evidence'}),null);}finally{cleanup();}
});
test('Recommendations prioritize installed unrun checks then recorded violations and required evidence',()=>{
 const other={...candidate,id:'another',name:'Another installed check'};
 assert.equal(nextActions([candidate,other],{status:'RESULT',result:latest,error:null})[0].title,'Run Another installed check');
 const runtime={...candidate,name:'API Latency',can_execute:false,execution_support:'NOT_AVAILABLE' as const,verification_mode:'PERFORMANCE' as const,required_evidence:['Load-test workload and measured latency']};
 assert.match(nextActions([runtime],idle)[0].explanation,/Load-test workload and measured latency/);
 assert.deepEqual(nextActions([],idle),[]);assert.deepEqual(nextActions([{...candidate,applicability:'NOT_APPLICABLE'}],idle),[]);
});
test('Non-technical context is grounded and never claims compliance or security readiness',()=>{
 const items=nonTechnicalItems(demoGraph,[]);assert.ok(items.some(i=>i.title==='Operational resilience'));assert.ok(items.some(i=>i.title==='Data governance'));
 for(const item of items){assert.ok(item.title&&item.explanation&&item.status);assert.ok(!['VERIFIED','VIOLATED','Verified','Violation found'].includes(item.status));}
 assert.ok(!items.some(i=>/Compliance|Security|Production readiness/i.test(i.title)));
 assert.deepEqual(nonTechnicalItems({nodes:[],edges:[],limitations:[],execution_flows:[]},[]),[]);
 assert.match(nextActions([],idle,items)[0].explanation,/runtime observations/);
 assert.ok(nonTechnicalItems({nodes:[],edges:[],limitations:[]},[{...candidate,verification_mode:'RUNTIME'}]).some(i=>i.status==='Not assessed'));
});
test('No flow and sparse facts are honest, and imports never become execution arrows',()=>{
 const sparse={...result,graph:{nodes:demoGraph.nodes.filter(n=>n.type==='MODULE').slice(0,2),edges:demoGraph.edges.filter(e=>e.type==='IMPORTS').slice(0,1),limitations:['Supported patterns only.'],execution_flows:[]}};
 try{const ui=mount({result:sparse,discovery:discovered([])});assert.ok(ui.getByText(/No supported ExecutionFlow was extracted/));assert.ok(ui.getByText('No supported evaluation was selected.'));assert.ok(ui.getByText(/No grounded operational or governance assessment/));assert.equal(ui.container.querySelector('.brief-flow-row'),null);assert.equal(ui.queryByText('LangGraph'),null);assert.equal(ui.queryByText('Source-grounded workflow detection'),null);}finally{cleanup();}
});
test('Flow brief copies every supplied transition and full conditions without inventing a linear path',()=>{
 const flow=demoGraph.execution_flows![0];const rows=flowRows(flow);assert.equal(rows.reduce((n,row)=>n+row.targets.length,0),flow.transitions.length);
 assert.deepEqual(rows.flatMap(row=>row.targets.map(t=>t.condition)).filter(Boolean).sort(),flow.transitions.map(t=>t.condition).filter(Boolean).sort());
 assert.ok(rows.some(row=>row.source==='Tool Execution'&&row.targets.some(t=>t.condition==='after_tools: retry')));
});
test('Coverage reflects actual stages and limitations stay expandable; input data is unchanged',()=>{
 const snapshot=JSON.stringify({result,latest,candidate});
 try{const ui=mount({verification:{status:'RESULT',result:latest,error:null},discovery:{...discovered(),result:{...discovered().result!,input_truncated:true,limitations:['Bounded selection input.']}} as DiscoveryState});assert.ok(ui.getByText('Evidence-backed static verification'));assert.ok(ui.getByText(/Discovery input was truncated/));const details=ui.getByText(/View limitations/).closest('details')!;assert.equal(details.open,false);assert.ok(within(details).getByText('Bounded selection input.'));assert.ok(within(details).getByText(latest.limitations[0]));assert.equal(JSON.stringify({result,latest,candidate}),snapshot);}finally{cleanup();}
});
test('Overview links navigate only, never invoke providers or verifiers',()=>{
 let architecture=0,verifications=0;try{const ui=mount({onArchitecture:()=>architecture++,onVerifications:()=>verifications++});fireEvent.click(ui.getByRole('button',{name:'Explore Architecture'}));fireEvent.click(ui.getByRole('button',{name:'View Verifications'}));fireEvent.click(ui.getAllByRole('button',{name:'Run Verification'})[0]);assert.equal(architecture,1);assert.equal(verifications,2);}finally{cleanup();}
});
