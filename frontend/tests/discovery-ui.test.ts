import "./dom-setup";
import test from "node:test";
import assert from "node:assert/strict";
import { createElement } from "react";
import { render, fireEvent, waitFor, cleanup } from "@testing-library/react";
import { SuggestedVerifications } from "../components/evaluation/SuggestedVerifications";
import { discoverVerifications, type DiscoveryResult } from "../lib/evaluation/discovery-client";
import { demoGraph } from "../lib/architecture/demo";

const originalFetch = globalThis.fetch;
const architectureId = 'a'.repeat(64);
const props = { repositoryPath: '/projects/agent', architectureId, onAnalyze: () => {} };
const path = '/projects/agent';
const base = { id: 'api-latency-v1', name: 'API Latency', category: 'Performance', reason: 'Detected HTTP route.',
  architecture_subject_ids: ['route:fixture'], applicability: 'APPLICABLE', priority: 'MEDIUM',
  required_evidence: ['Executed load-test measurements'], verification_mode: 'PERFORMANCE',
  execution_support: 'NOT_AVAILABLE', limitations: ['No runtime verifier.'] } as const;
const result: DiscoveryResult = { architecture_id: 'a'.repeat(64), catalog_version: 'engineering-evaluations-v1',
  input_truncated: false, limitations: ['A source limitation.'], candidates: [{ ...base,
    architecture_subject_ids: [...base.architecture_subject_ids], required_evidence: [...base.required_evidence], limitations: [...base.limitations] }] };
function response(data: unknown, status=200) { return new Response(JSON.stringify(data), { status }); }
function restore() { cleanup(); globalThis.fetch = originalFetch; }

test('idle discovery is deliberate; repeated clicks cannot duplicate an in-flight call', async () => {
  let calls = 0;
  let resolve!: (value: Response) => void;
  globalThis.fetch = async (url, options) => {
    calls++; assert.equal(url, '/api/evaluations/discover');
    assert.deepEqual(JSON.parse(String(options?.body)), { repository_path: path, expected_architecture_id: architectureId });
    return await new Promise<Response>(done => { resolve=done; });
  };
  try {
    const ui=render(createElement(SuggestedVerifications, props));
    assert.equal(calls,0); assert.equal(ui.container.querySelector('section')?.getAttribute('data-state'),'IDLE');
    const button=ui.getByRole('button',{name:'Discover Verifications'});
    fireEvent.click(button); fireEvent.click(button);
    assert.equal(calls,1); assert.ok(ui.getByRole('button',{name:'Discovering…'}).hasAttribute('disabled'));
    assert.equal(ui.container.querySelector('section')?.getAttribute('data-state'),'DISCOVERING');
    resolve(response(result));
    await waitFor(()=>assert.ok(ui.getByText('API Latency')));
    assert.equal(ui.container.querySelector('section')?.getAttribute('data-state'),'READY');
    assert.ok(ui.getByText('APPLICABLE')); assert.ok(ui.getByText('NOT_AVAILABLE'));
    assert.ok(ui.getByText('PERFORMANCE')); assert.ok(ui.getByText('MEDIUM'));
    assert.ok(ui.getByText('Worth investigating, but Verisys cannot execute this verification yet.'));
    assert.ok(ui.getByText('Executed load-test measurements'));
    assert.equal(ui.queryByText('VERIFIED'),null); assert.equal(ui.queryByText('VIOLATED'),null);
  } finally {restore();}
});

test('unknown/partial and applicable/supported display distinct server fields', async () => {
  globalThis.fetch=async()=>response({...result,candidates:[{...result.candidates[0],id:'external-api-timeout-coverage-v1',name:'Timeout Coverage',applicability:'UNKNOWN',execution_support:'PARTIAL',verification_mode:'STATIC'},
    {...result.candidates[0],id:'direct-coverage-fixture',name:'Direct Call Coverage',execution_support:'SUPPORTED'}]});
  try {
    const ui=render(createElement(SuggestedVerifications,props));
    fireEvent.click(ui.getByRole('button',{name:'Discover Verifications'}));
    await waitFor(()=>assert.ok(ui.getByText('Timeout Coverage')));
    assert.ok(ui.getByText('UNKNOWN')); assert.ok(ui.getByText('PARTIAL')); assert.ok(ui.getByText('SUPPORTED'));
    assert.ok(ui.getByText('Relevant to this architecture, but current executable coverage is limited.'));
  } finally {restore();}
});

test('empty selection and provider error are separate states without fallback', async () => {
  globalThis.fetch=async()=>response({...result,candidates:[]});
  try {
    const ui=render(createElement(SuggestedVerifications,props));
    fireEvent.click(ui.getByRole('button',{name:'Discover Verifications'}));
    await waitFor(()=>assert.equal(ui.container.querySelector('section')?.getAttribute('data-state'),'EMPTY'));
    assert.ok(ui.getByText(/No recommendations were selected/));
    globalThis.fetch=async()=>response({error:{code:'DISCOVERY_PROVIDER_FAILED',message:'Provider could not complete discovery.'}},502);
    fireEvent.click(ui.getByRole('button',{name:'Discover Verifications'}));
    await waitFor(()=>assert.equal(ui.container.querySelector('section')?.getAttribute('data-state'),'ERROR'));
    assert.equal(ui.getByRole('alert').textContent,'Provider could not complete discovery.');
    assert.equal(ui.queryByText(/No recommendations were selected/),null);
    assert.equal(ui.queryByText('API Latency'),null);
  } finally {restore();}
});

test('new analysis invalidates recommendations, aborts in-flight requests and ignores late responses', async () => {
  let discoveryCalls=0;
  let resolve!: (value: Response)=>void;
  let abortedSignal: AbortSignal | null | undefined;
  const analysis={architecture_id:architectureId,repository:{name:'agent',path},architecture:{},graph:demoGraph};
  globalThis.fetch=async(url,options)=>{
    if(url==='/api/analyze')return response(analysis);
    assert.deepEqual(JSON.parse(String(options?.body)),{repository_path:path,expected_architecture_id:architectureId});
    discoveryCalls++;
    if(discoveryCalls===1)return response(result);
    abortedSignal=options?.signal;
    return await new Promise<Response>(done=>{resolve=done;});
  };
  try {
    const { ArchitectureWorkspace }=await import('../components/architecture/ArchitectureGraph');
    const ui=render(createElement(ArchitectureWorkspace));
    async function analyze(repositoryPath:string) {
      fireEvent.click(ui.getByRole('button',{name:'Analyze Repository'}));
      fireEvent.change(ui.getByLabelText('Local repository path'),{target:{value:repositoryPath}});
      fireEvent.click(ui.getByRole('button',{name:'Analyze'}));
      await waitFor(()=>assert.ok(ui.getByRole('button',{name:'Discover Verifications'})));
    }
    await analyze(path);
    fireEvent.click(ui.getByRole('button',{name:'Discover Verifications'}));
    await waitFor(()=>assert.ok(ui.getByText('API Latency')));
    await analyze(path); // Even the same path gets a fresh analysis revision.
    assert.equal(ui.queryByText('API Latency'),null);
    fireEvent.click(ui.getByRole('button',{name:'Discover Verifications'}));
    await analyze('/projects/other');
    assert.equal(abortedSignal?.aborted,true);
    resolve(response(result));
    await waitFor(()=>assert.equal(ui.container.querySelector('.suggested-verifications')?.getAttribute('data-state'),'IDLE'));
    assert.equal(ui.queryByText('API Latency'),null);
    assert.equal(discoveryCalls,2);
    fireEvent.click(ui.getByRole('button',{name:'Dependency View'}));
    assert.equal(ui.container.querySelectorAll('.react-flow__node').length,14);
  } finally {restore();}
});

test('malformed DTO and network failures remain errors', async () => {
  const signal=new AbortController().signal;
  try {
    globalThis.fetch=async()=>response({...result,candidates:[{...result.candidates[0],execution_support:'VERIFIED'}]});
    await assert.rejects(discoverVerifications(path,architectureId,signal),/invalid response/);
    globalThis.fetch=async()=>{throw new Error('private socket details');};
    await assert.rejects(discoverVerifications(path,architectureId,signal),/Cannot reach discovery/);
  } finally {restore();}
});

test('stale analysis clears suggestions and prompts explicit reanalysis without retry', async () => {
  let calls=0, analyses=0;
  globalThis.fetch=async()=>{
    calls++;
    return calls===1 ? response(result) : response({error:{code:'ANALYSIS_STALE',message:'The repository changed. Analyze the repository again before discovering verifications.'}},409);
  };
  try {
    const ui=render(createElement(SuggestedVerifications,{...props,onAnalyze:()=>{analyses++;}}));
    fireEvent.click(ui.getByRole('button',{name:'Discover Verifications'}));
    await waitFor(()=>assert.ok(ui.getByText('API Latency')));
    fireEvent.click(ui.getByRole('button',{name:'Discover Verifications'}));
    await waitFor(()=>assert.equal(ui.getByRole('alert').getAttribute('data-stale'),'true'));
    assert.equal(ui.queryByText('API Latency'),null);
    assert.ok(ui.getByRole('button',{name:'Discover Verifications'}).hasAttribute('disabled'));
    assert.equal(calls,2); assert.equal(analyses,0);
    fireEvent.click(ui.getByRole('button',{name:'Analyze Repository again →'}));
    assert.equal(analyses,1); assert.equal(calls,2);
  } finally {restore();}
});

test('client rejects a mismatched success snapshot instead of displaying suggestions', async () => {
  globalThis.fetch=async()=>response({...result,architecture_id:'b'.repeat(64)});
  try { await assert.rejects(discoverVerifications(path,architectureId,new AbortController().signal),/snapshot differs/); }
  finally {restore();}
});
