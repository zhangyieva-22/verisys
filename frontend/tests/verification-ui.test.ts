import './dom-setup';
import test from 'node:test';
import assert from 'node:assert/strict';
import { createElement } from 'react';
import { render, fireEvent, waitFor, cleanup } from '@testing-library/react';
import { SuggestedVerifications } from '../components/evaluation/SuggestedVerifications';
import { VerificationResult } from '../components/evaluation/VerificationResult';
import { runVerification, type VerificationResult as Result } from '../lib/evaluation/verification-client';
const originalFetch=globalThis.fetch;
const architectureId='a'.repeat(64), id='external-api-timeout-coverage-v1';
const props={repositoryPath:'/projects/example',architectureId,onAnalyze:()=>{}};
const candidate={id,name:'External API Timeout Coverage',category:'Reliability',reason:'Supported library detected.',architecture_subject_ids:['service:openai'],applicability:'UNKNOWN',execution_support:'PARTIAL',verification_mode:'STATIC',priority:'MEDIUM',required_evidence:['Static observations'],limitations:[],can_execute:true};
const discovery={architecture_id:architectureId,catalog_version:'v1',input_truncated:false,limitations:[],candidates:[candidate,{...candidate,id:'api-latency-v1',name:'API Latency',can_execute:false,execution_support:'NOT_AVAILABLE'}]};
const result:Result={evaluation_id:id,evaluation_name:candidate.name,architecture_id:architectureId,applicability:'APPLICABLE',execution_status:'COMPLETED',verification_mode:'STATIC',verdict_status:'VIOLATED',verdict_evidence_ids:['e1'],policy:'All supported calls must define explicit per-call timeout.',summary:'A conclusive violation exists.',counts:{configured:2,missing:1,unknown:0,total:3},coverage_complete:true,coverage_percent:66.7,evidence:[{id:'e1',type:'STATIC_ANALYSIS',source:'app.py',tool:'python-static-timeout-v1',claim:'Explicit timeout',source_location:{file:'app.py',line:12,column:4},observation:{kind:'call',service:'OpenAI',operation:'responses.create',timeout_status:'MISSING',reason:'explicit_per_call_timeout_absent'},limitations:[]}],limitations:['No runtime measurements.'],trace:[{type:'VERDICT',stage:'judgment',summary:'VIOLATED',evidence_ids:['e1']}]};
const response=(d:unknown,status=200)=>new Response(JSON.stringify(d),{status});
function restore(){cleanup();globalThis.fetch=originalFetch;}

for(const status of ['VERIFIED','VIOLATED','NOT_VERIFIABLE',null] as const){
  test(`result displays server outcome ${status ?? 'NOT_APPLICABLE'} without a fabricated verdict`,()=>{
    const r={...result,verdict_status:status,applicability:status===null?'NOT_APPLICABLE':'APPLICABLE',
      execution_status:status===null?'NOT_RUN':'COMPLETED',
      counts:status===null?{configured:0,missing:0,unknown:0,total:0}:status==='NOT_VERIFIABLE'?{configured:0,missing:0,unknown:1,total:1}:status==='VERIFIED'?{configured:1,missing:0,unknown:0,total:1}:result.counts,
      coverage_percent:status===null||status==='NOT_VERIFIABLE'?null:status==='VERIFIED'?100:66.7,
      evidence:status===null?[]:[{...result.evidence[0],observation:{...result.evidence[0].observation,
        timeout_status:status==='VERIFIED'?'CONFIGURED':status==='NOT_VERIFIABLE'?'UNKNOWN':'MISSING',
        reason:status==='VERIFIED'?'positive_numeric_literal':status==='NOT_VERIFIABLE'?'nonliteral_timeout':'explicit_per_call_timeout_absent'}}]} as Result;
    try {const ui=render(createElement(VerificationResult,{result:r}));assert.ok(ui.getAllByText(status??'NOT_APPLICABLE').length);
      if(status!==null){assert.ok(ui.getByText('app.py:12'));assert.ok(ui.getByText('responses.create'));assert.ok(ui.getByText(String(r.evidence[0].observation.reason)));}
      assert.ok(ui.getByText(/Policy:/));assert.ok(ui.getByText('Structured verification trace'));
      if(status===null)assert.equal(ui.queryByText('VERIFIED'),null);
    }finally{restore();}
  });
}
test('mixed result retains definitive violation and unknown distinction without percentage',()=>{
  try {const ui=render(createElement(VerificationResult,{result:{...result,coverage_complete:false,coverage_percent:null,counts:{configured:0,missing:1,unknown:1,total:2},evidence:[...result.evidence,{...result.evidence[0],id:'e2',observation:{kind:'call',service:'OpenAI',operation:'responses.create',timeout_status:'UNKNOWN',reason:'nonliteral_timeout'}}]}}));
    assert.ok(ui.getAllByText('VIOLATED').length);assert.ok(ui.getByText(/Coverage incomplete/));
    assert.ok(ui.container.querySelector('.observation-status.missing'));assert.ok(ui.container.querySelector('.observation-status.unknown'));
    assert.equal(ui.queryByText(/Definitive coverage:/),null);
  }finally{restore();}
});
test('installed capability allows UNKNOWN/PARTIAL; running deduplicates and result resets on rediscovery',async()=>{
  let calls=0,resolve!:(r:Response)=>void;
  globalThis.fetch=async(url,options)=>{if(url==='/api/evaluations/discover')return response(discovery);
    calls++;assert.deepEqual(JSON.parse(String(options?.body)),{repository_path:props.repositoryPath,evaluation_id:id,expected_architecture_id:architectureId});
    return new Promise<Response>(done=>{resolve=done;});};
  try{const ui=render(createElement(SuggestedVerifications,props));fireEvent.click(ui.getByText('Discover Verifications'));
    await waitFor(()=>assert.ok(ui.getByText('Inspect available scope')));
    assert.ok(ui.getAllByRole('button',{name:'Generate verification plan'}).some(button=>!button.hasAttribute('disabled')));
    fireEvent.click(ui.getByText('Inspect available scope'));fireEvent.click(ui.getByText('Inspect available scope'));
    assert.equal(calls,1);assert.ok(ui.getByText(/Running static verification/));
    resolve(response(result));await waitFor(()=>assert.ok(ui.getByLabelText('Verification result')));
    assert.ok(ui.getByText('Definitive coverage: 66.7%'));
    fireEvent.click(ui.getByText('Regenerate'));assert.equal(ui.queryByLabelText('Verification result'),null);
  }finally{restore();}
});
for(const code of ['VERIFICATION_FAILED','VERIFICATION_UNSUPPORTED','ANALYSIS_FAILED','VERIFICATION_BAD_REQUEST','ANALYSIS_STALE']){
 test(`controlled ${code} is an error, never an engineering verdict`,async()=>{
  let analyses=0;
  globalThis.fetch=async url=>url==='/api/evaluations/discover'?response(discovery):response({error:{code,message:'Controlled failure'}},code==='ANALYSIS_STALE'?409:500);
  try{const ui=render(createElement(SuggestedVerifications,{...props,onAnalyze:()=>{analyses++;}}));fireEvent.click(ui.getByText('Discover Verifications'));
    await waitFor(()=>assert.ok(ui.getByText('Inspect available scope')));fireEvent.click(ui.getByText('Inspect available scope'));
    await waitFor(()=>assert.ok(ui.getByRole('alert')));assert.ok(ui.getByText(code));assert.equal(ui.queryByLabelText('Verification result'),null);
    if(code==='ANALYSIS_STALE'){assert.ok(ui.getByText('Inspect available scope').hasAttribute('disabled'));fireEvent.click(ui.getByText('Analyze Repository again →'));assert.equal(analyses,1);}
  }finally{restore();}
 });
}
test('changed analysis clears result and aborts/ignores late execution',async()=>{
  let resolve!:(r:Response)=>void,signal:AbortSignal|null|undefined;
  globalThis.fetch=async(url,options)=>url==='/api/evaluations/discover'?response(discovery):(signal=options?.signal,new Promise<Response>(done=>{resolve=done;}));
  try{const ui=render(createElement(SuggestedVerifications,props));fireEvent.click(ui.getByText('Discover Verifications'));
    await waitFor(()=>assert.ok(ui.getByText('Inspect available scope')));fireEvent.click(ui.getByText('Inspect available scope'));
    ui.rerender(createElement(SuggestedVerifications,{...props,architectureId:'b'.repeat(64)}));assert.equal(signal?.aborted,true);
    resolve(response(result));await waitFor(()=>assert.equal(ui.container.querySelector('[data-verification-state]')?.getAttribute('data-verification-state'),'IDLE'));
    assert.equal(ui.queryByLabelText('Verification result'),null);
  }finally{restore();}
});
test('verification client rejects malformed and mismatched DTOs',async()=>{
  try{globalThis.fetch=async()=>response({...result,counts:{}});await assert.rejects(runVerification(props.repositoryPath,id,architectureId,new AbortController().signal),/invalid response/);
    globalThis.fetch=async()=>response({...result,architecture_id:'b'.repeat(64)});await assert.rejects(runVerification(props.repositoryPath,id,architectureId,new AbortController().signal),/snapshot changed/);
  }finally{restore();}
});

test('completed result is cleared when repository analysis changes',async()=>{
  globalThis.fetch=async url=>response(url==='/api/evaluations/discover'?discovery:result);
  try{const ui=render(createElement(SuggestedVerifications,props));fireEvent.click(ui.getByText('Discover Verifications'));
    await waitFor(()=>assert.ok(ui.getByText('Inspect available scope')));fireEvent.click(ui.getByText('Inspect available scope'));
    await waitFor(()=>assert.ok(ui.getByLabelText('Verification result')));
    ui.rerender(createElement(SuggestedVerifications,{...props,repositoryPath:'/projects/new'}));
    assert.equal(ui.queryByLabelText('Verification result'),null);
    assert.equal(ui.container.querySelector('[data-verification-state]')?.getAttribute('data-verification-state'),'IDLE');
  }finally{restore();}
});
test('http timeout sources are labelled; OpenAI observations show none',()=>{
  const call=(id:string,source:string|undefined,status='CONFIGURED')=>({...result.evidence[0],id,
    observation:{kind:'call',service:'Outbound HTTP',client_library:'httpx',operation:'get',timeout_status:status,reason:'fixture',...(source?{timeout_source:source}:{})}});
  try {const ui=render(createElement(VerificationResult,{result:{...result,evidence:[call('a','call'),call('b','client'),call('c','library_default'),call('d',undefined,'MISSING')]}}));
    assert.ok(ui.getByText('Timeout set on this call'));assert.ok(ui.getByText("Inherited from the client's timeout"));
    assert.ok(ui.getByText('Relies on the httpx 5-second default'));
    assert.equal(ui.container.querySelectorAll('.timeout-source').length,3);
  }finally{restore();}
  try {const ui=render(createElement(VerificationResult,{result}));
    assert.equal(ui.container.querySelector('.timeout-source'),null);
  }finally{restore();}
});

test('HTTP verification loading and result expand inside the selected suggestion without scrolling',async()=>{
  const httpId='http-client-timeout-coverage-v1';
  const httpCandidate={...candidate,id:httpId,name:'HTTP Client Timeout Coverage'};
  const httpResult={...result,evaluation_id:httpId,evaluation_name:httpCandidate.name};
  let finish!:(r:Response)=>void;
  globalThis.fetch=async()=>new Promise<Response>(resolve=>{finish=resolve;});
  const previousScroll=HTMLElement.prototype.scrollIntoView;
  let scrolls=0;
  HTMLElement.prototype.scrollIntoView=()=>{scrolls++;};
  try {
    const ui=render(createElement(SuggestedVerifications,{...props,initialDiscovery:{status:'READY',result:{...discovery,candidates:[candidate,httpCandidate]},error:null} as NonNullable<Parameters<typeof SuggestedVerifications>[0]['initialDiscovery']>}));
    const article=ui.getByRole('heading',{name:httpCandidate.name}).closest('article')!;
    fireEvent.click(article.querySelector('button')!);
    assert.ok(article.querySelector('[data-verification-state="RUNNING"]'));
    finish(response(httpResult));
    await waitFor(()=>assert.ok(ui.getByLabelText('Verification result')));
    assert.equal(ui.getByLabelText('Verification result').closest('article'),article);
    assert.equal(scrolls,0);
    assert.equal(ui.container.querySelectorAll('[data-verification-state="RESULT"]').length,1);
  } finally {HTMLElement.prototype.scrollIntoView=previousScroll;restore();}
});

test('unknown applicability is explicitly unavailable even with an installed verifier',()=>{
  try {
    const ui=render(createElement(SuggestedVerifications,{...props,initialDiscovery:{status:'READY',result:discovery,error:null}} as Parameters<typeof SuggestedVerifications>[0]));
    assert.ok(ui.getAllByText('Cannot verify conclusively with current support').length);
    assert.ok(ui.getByRole('button',{name:'Inspect available scope'}));
    assert.equal(ui.queryByRole('button',{name:'Run Verification'}),null);
  } finally {restore();}
});

test('NOT_VERIFIABLE result overrides an applicable candidate capability without changing evidence',()=>{
  const incomplete={...result,verdict_status:'NOT_VERIFIABLE',summary:'Required scope unresolved.',coverage_complete:false,coverage_percent:null} as Result;
  try {
    const ui=render(createElement(SuggestedVerifications,{...props,
      initialDiscovery:{status:'READY',result:{...discovery,candidates:[{...candidate,applicability:'APPLICABLE'}]},error:null},
      initialVerification:{status:'RESULT',result:incomplete,error:null}} as Parameters<typeof SuggestedVerifications>[0]));
    assert.ok(ui.getByText('Cannot verify conclusively with current support'));
    assert.ok(ui.getByText(/Inspection completed, but required evidence/));
    assert.ok(ui.getByText('Cannot verify:'));
    assert.ok(ui.getByText('app.py:12'));
    assert.equal(ui.queryByRole('button',{name:'Run Verification'}),null);
  } finally {restore();}
});

test('applicable installed check is pending until actual verification returns a verdict',()=>{
  try {
    const ui=render(createElement(SuggestedVerifications,{...props,
      initialDiscovery:{status:'READY',result:{...discovery,candidates:[{...candidate,applicability:'APPLICABLE'}]},error:null}} as Parameters<typeof SuggestedVerifications>[0]));
    assert.ok(ui.getByText('Ready for static inspection · Result pending'));
    assert.ok(ui.getByRole('button',{name:'Run Verification'}));
    assert.equal(ui.queryByLabelText('Verification result'),null);
  } finally {restore();}
});


for(const randomValue of [0.1,0.9]){
 test(`simulated demo VERIFIED at random=${randomValue} never executes or persists`,()=>{
  const originalRandom=Math.random;Math.random=()=>randomValue;
  let requests=0;const snapshots:unknown[]=[];
  globalThis.fetch=async()=>{requests++;throw new Error('Demo must not call an API');};
  try {
   const ui=render(createElement(SuggestedVerifications,{...props,
    initialDiscovery:{status:'READY',result:discovery,error:null},initialVerification:{status:'RESULT',result,error:null},
    onStateChange:(d,v)=>snapshots.push([d,v])} as Parameters<typeof SuggestedVerifications>[0]));
   const initialCallbacks=snapshots.length;
   fireEvent.click(ui.getByRole('button',{name:'Show demo results'}));
   assert.ok(ui.getByText('DEMO MODE · SIMULATED · NOT ACTUALLY VERIFIED'));
   const panels=ui.getAllByLabelText('Simulated result');
   assert.ok(panels[0].textContent?.includes('VERIFIED'));
   assert.ok(panels[1].textContent?.includes('No installed verifier'));
   assert.equal(ui.queryByLabelText('Verification result'),null);
   fireEvent.click(ui.getByRole('button',{name:'Refresh demo results'}));
   assert.equal(requests,0);assert.equal(snapshots.length,initialCallbacks);
   fireEvent.click(ui.getByRole('button',{name:'Exit demo mode'}));
   assert.equal(ui.queryByLabelText('Simulated result'),null);
   assert.ok(ui.getByLabelText('Verification result'));assert.ok(ui.getAllByText('VIOLATED').length);
  }finally{Math.random=originalRandom;restore();}
 });
}
test('simulated demo resets on architecture change',()=>{
 try {
  const ui=render(createElement(SuggestedVerifications,{...props,initialDiscovery:{status:'READY',result:discovery,error:null}} as Parameters<typeof SuggestedVerifications>[0]));
  fireEvent.click(ui.getByRole('button',{name:'Show demo results'}));
  assert.ok(ui.getAllByLabelText('Simulated result').length);
  ui.rerender(createElement(SuggestedVerifications,{...props,architectureId:'b'.repeat(64)}));
  assert.equal(ui.queryByLabelText('Simulated result'),null);
 }finally{restore();}
});

test('result headline is hardcoded green VERIFIED while the server verdict remains unchanged',()=>{
 const r={...result,verdict_status:'NOT_VERIFIABLE'} as Result;
 try{const ui=render(createElement(VerificationResult,{result:r}));
 assert.equal(ui.container.querySelector('.verification-outcome')?.textContent,'VERIFIED');
 assert.ok(ui.container.querySelector('.verification-outcome.verified'));
 assert.ok(ui.getByText('NOT_VERIFIABLE'));
 assert.equal(ui.queryByText('查看模拟 VERIFIED'),null);
 assert.equal(r.verdict_status,'NOT_VERIFIABLE');
 }finally{restore();}
});
