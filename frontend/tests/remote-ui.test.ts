import './dom-setup';
import test from 'node:test';
import assert from 'node:assert/strict';
import { createElement, StrictMode } from 'react';
import { render, fireEvent, waitFor, cleanup } from '@testing-library/react';
import { ArchitectureWorkspace } from '../components/architecture/ArchitectureGraph';
import { SuggestedVerifications } from '../components/evaluation/SuggestedVerifications';
import { validGitHubURL } from '../lib/repository-source';
import { demoGraph } from '../lib/architecture/demo';
const originalFetch=globalThis.fetch;
const sha='3d38d5ab7fa0f27bd5c28488afa354abaf2577b4', hash='a'.repeat(64), url='https://github.com/owner/repo';
const source={type:'github' as const,url,ref:sha};
const analysis={architecture_id:hash,repository:{name:'owner/repo',path:null,source,repository_url:url,requested_ref:'main',resolved_commit_sha:sha},architecture:{},graph:demoGraph};
const timeout={id:'external-api-timeout-coverage-v1',name:'External API Timeout Coverage',category:'Reliability',reason:'Direct calls detected',architecture_subject_ids:['service:openai'],applicability:'APPLICABLE',execution_support:'SUPPORTED',verification_mode:'STATIC',priority:'MEDIUM',required_evidence:['Static evidence'],limitations:[],can_execute:true};
const discovery={architecture_id:hash,catalog_version:'v1',input_truncated:false,limitations:[],candidates:[timeout,{...timeout,id:'api-latency-v1',name:'API Latency',execution_support:'NOT_AVAILABLE',can_execute:false}]};
const response=(d:unknown,status=200)=>new Response(JSON.stringify(d),{status});
function restore(){cleanup();globalThis.fetch=originalFetch;}
function enter(ui:ReturnType<typeof render>){fireEvent.click(ui.getByRole('button',{name:ui.queryByRole('button',{name:'Re-analyze Repository'})?'Re-analyze Repository':'Analyze Repository'}));fireEvent.change(ui.getByLabelText('Repository URL'),{target:{value:url}});}

test('GitHub is primary; ref/mode/concern fields produce bounded intent',async()=>{
 const bodies:Record<string,unknown>[]=[];
 globalThis.fetch=async(u,o)=>{bodies.push(JSON.parse(String(o?.body)));return response(u==='/api/analyze'?analysis:discovery);};
 try{const ui=render(createElement(ArchitectureWorkspace));enter(ui);assert.equal(ui.queryByLabelText('Local repository path'),null);
  fireEvent.change(ui.getByLabelText('Branch / tag / commit (optional)'),{target:{value:'main'}});
  assert.equal(ui.queryByLabelText('What do you want to verify?'),null);
  fireEvent.click(ui.getByLabelText('On-demand'));fireEvent.change(ui.getByLabelText('What do you want to verify?'),{target:{value:'Check OpenAI timeouts'}});
  fireEvent.click(ui.getAllByRole('button',{name:'Analyze Repository'}).at(-1)!);
  await waitFor(()=>assert.ok(ui.getByText('Run Verification')));
  assert.deepEqual(bodies[0],{source:{type:'github',url,ref:'main'}});
  assert.deepEqual(bodies[1],{source,expected_architecture_id:hash,mode:'ON_DEMAND',request_text:'Check OpenAI timeouts'});
  assert.ok(ui.getByText(/owner\/repo · 3d38d5a/));fireEvent.click(ui.getByRole('button',{name:'Architecture'}));assert.ok(ui.getByText('Agent Workflow'));
  assert.ok(ui.getByText('Verification not available yet').hasAttribute('disabled'));
 }finally{restore();}
});

test('proactive auto discovery happens once, uses immutable SHA and not a moving branch',async()=>{
 let analysisCalls=0,discoveryCalls=0;
 globalThis.fetch=async(u,o)=>{if(u==='/api/analyze'){analysisCalls++;return response(analysis);}discoveryCalls++;
  assert.deepEqual(JSON.parse(String(o?.body)),{source,expected_architecture_id:hash,mode:'PROACTIVE'});return response(discovery);};
 try{const ui=render(createElement(ArchitectureWorkspace));enter(ui);fireEvent.click(ui.getAllByRole('button',{name:'Analyze Repository'}).at(-1)!);fireEvent.click(ui.getByRole('button',{name:'Analyzing…'}));
  await waitFor(()=>assert.ok(ui.getByText('Run Verification')));
  fireEvent.click(ui.getByRole('button',{name:'Architecture'}));fireEvent.click(ui.getByText('Dependency View'));fireEvent.click(ui.getByText('System Flow'));
  assert.equal(analysisCalls,1);assert.equal(discoveryCalls,1);
 }finally{restore();}
});

test('StrictMode effect replay does not duplicate or abort automatic selection',async()=>{
 let calls=0;
 globalThis.fetch=async()=>{calls++;return response(discovery);};
 try{const component=createElement(SuggestedVerifications,{source,architectureId:hash,intent:{mode:'PROACTIVE'},autoDiscover:true,onAnalyze:()=>{}});
  const ui=render(createElement(StrictMode,null,component));await waitFor(()=>assert.ok(ui.getByText('Run Verification')));
  ui.rerender(createElement(StrictMode,null,component));assert.equal(calls,1);
 }finally{restore();}
});

test('on-demand empty is a no-match, not a verdict; provider error is distinct',async()=>{
 let calls=0;
 globalThis.fetch=async()=>response(++calls===1?{...discovery,candidates:[]}:{error:{code:'DISCOVERY_PROVIDER_FAILED',message:'Provider unavailable'}},calls===1?200:502);
 try{const ui=render(createElement(SuggestedVerifications,{source,architectureId:hash,intent:{mode:'ON_DEMAND',request_text:'Unsupported request'},autoDiscover:true,onAnalyze:()=>{}}));
  await waitFor(()=>assert.ok(ui.getByText('No currently supported evaluation matches this request.')));assert.equal(ui.queryByText('NOT_VERIFIABLE'),null);
  fireEvent.click(ui.getByText('Discover Verifications'));await waitFor(()=>assert.ok(ui.getByText('Verification discovery is temporarily unavailable. Try again later.')));
  assert.equal(ui.queryByText('No currently supported evaluation matches this request.'),null);
 }finally{restore();}
});

test('invalid URLs never reach backend and acquisition failures never show fixture architecture',async()=>{
 let calls=0;
 globalThis.fetch=async()=>{calls++;return response({error:{code:'REPOSITORY_TOO_LARGE',message:'Repository exceeds acquisition limit.'}},413);};
 try{const ui=render(createElement(ArchitectureWorkspace));enter(ui);
  fireEvent.change(ui.getByLabelText('Repository URL'),{target:{value:'https://evil.example/repo'}});fireEvent.click(ui.getAllByRole('button',{name:'Analyze Repository'}).at(-1)!);
  assert.equal(calls,0);assert.ok(ui.getAllByRole('button',{name:'Analyze Repository'}).at(-1)!.hasAttribute('disabled'));
  fireEvent.change(ui.getByLabelText('Repository URL'),{target:{value:url}});fireEvent.click(ui.getAllByRole('button',{name:'Analyze Repository'}).at(-1)!);
  await waitFor(()=>assert.ok(ui.getByRole('alert')));assert.equal(ui.queryByText('Agent Workflow'),null);assert.equal(calls,1);
 }finally{restore();}
});

for(const field of ['Repository URL','Branch / tag / commit (optional)','mode']){
 test(`changing ${field} clears architecture/suggestions/results before a new action`,async()=>{
  globalThis.fetch=async u=>response(u==='/api/analyze'?analysis:discovery);
  try{const ui=render(createElement(ArchitectureWorkspace));enter(ui);fireEvent.click(ui.getAllByRole('button',{name:'Analyze Repository'}).at(-1)!);await waitFor(()=>assert.ok(ui.getByText('Run Verification')));
    fireEvent.click(ui.getByRole('button',{name:ui.queryByRole('button',{name:'Re-analyze Repository'})?'Re-analyze Repository':'Analyze Repository'}));
    if(field==='mode')fireEvent.click(ui.getByLabelText('On-demand'));else fireEvent.change(ui.getByLabelText(field),{target:{value:field==='Repository URL'?'https://github.com/new/repo':'new-branch'}});
    assert.equal(ui.queryByText('Run Verification'),null);assert.equal(ui.queryByText('Agent Workflow'),null);assert.equal(ui.queryByText(/owner\/repo · 3d38d5a/),null);
  }finally{restore();}
 });
}

test('remote execution sends pinned source with no intent/provider request',async()=>{
 const requests:Record<string,unknown>[]=[];
 globalThis.fetch=async(u,o)=>{if(u==='/api/evaluations/discover')return response(discovery);requests.push(JSON.parse(String(o?.body)));return response({error:{code:'VERIFICATION_FAILED',message:'Controlled tool failure'}},500);};
 try{const ui=render(createElement(SuggestedVerifications,{source,architectureId:hash,intent:{mode:'PROACTIVE'},autoDiscover:true,onAnalyze:()=>{}}));
  await waitFor(()=>assert.ok(ui.getByText('Run Verification')));fireEvent.click(ui.getByText('Run Verification'));
  await waitFor(()=>assert.ok(ui.getByText('Controlled tool failure')));
  assert.deepEqual(requests,[{source,evaluation_id:timeout.id,expected_architecture_id:hash}]);
 }finally{restore();}
});

test('client URL validation rejects credentials/query/fragments/non-GitHub inputs',()=>{
 for(const bad of ['http://github.com/o/r','https://u:p@github.com/o/r','https://github.com/o/r?','https://github.com/o/r#','https://github.com/o/r/tree/main','https://127.0.0.1/o/r'])assert.equal(validGitHubURL(bad),false);
 assert.equal(validGitHubURL(url+'.git'),true);
});
