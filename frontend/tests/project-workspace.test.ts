import './dom-setup';
import test from 'node:test';
import assert from 'node:assert/strict';
import {createElement, StrictMode} from 'react';
import {render,fireEvent,waitFor,cleanup,within} from '@testing-library/react';
import {ProjectWorkspace} from '../components/projects/ProjectWorkspace';
import {apiErrorMessage} from '../lib/api-errors';
import {PROJECTS_KEY,readProjects,writeProjects} from '../lib/projects';
import {demoGraph} from '../lib/architecture/demo';

const originalFetch=globalThis.fetch;
const sha='3d38d5ab7fa0f27bd5c28488afa354abaf2577b4',hash='a'.repeat(64),url='https://github.com/owner/first';
function analyzed(repo=url){return {architecture_id:hash,repository:{name:repo.replace('https://github.com/',''),path:null,source:{type:'github',url:repo,ref:sha},repository_url:repo,resolved_commit_sha:sha,requested_ref:'main'},architecture:{},graph:demoGraph};}
const candidate={id:'external-api-timeout-coverage-v1',name:'External API Timeout Coverage',category:'Reliability',reason:'Source-backed direct calls.',architecture_subject_ids:['service:openai'],applicability:'APPLICABLE',priority:'MEDIUM',required_evidence:['Static observations'],verification_mode:'STATIC',execution_support:'SUPPORTED',limitations:[],can_execute:true};
const discovered={architecture_id:hash,catalog_version:'v1',input_truncated:false,limitations:[],candidates:[candidate,{...candidate,id:'api-latency-v1',name:'API Latency',execution_support:'NOT_AVAILABLE',can_execute:false}]};
const verified={evaluation_id:candidate.id,evaluation_name:candidate.name,architecture_id:hash,applicability:'APPLICABLE',execution_status:'COMPLETED',verification_mode:'STATIC',verdict_status:'VIOLATED',verdict_evidence_ids:['e1'],policy:'Explicit per-call timeouts required.',summary:'One explicit timeout is missing.',counts:{configured:0,missing:1,unknown:0,total:1},coverage_complete:true,coverage_percent:0,evidence:[{id:'e1',type:'STATIC_ANALYSIS',source:'app.py',source_location:{file:'app.py',line:12,column:0},tool:'python-static-timeout-v1',claim:'Explicit per-call timeout',observation:{kind:'call',service:'OpenAI',operation:'responses.create',timeout_status:'MISSING',reason:'explicit_per_call_timeout_absent'},limitations:[]}],limitations:['Static configuration only.'],trace:[{type:'VERDICT',stage:'judgment',summary:'VIOLATED',evidence_ids:['e1']}]};
const response=(data:unknown,status=200)=>new Response(JSON.stringify(data),{status});
const metadata={url,requestedRef:'main',sha,name:'first',ownerRepository:'owner/first',architectureId:hash,analyzedAt:'2026-10-01T12:00:00.000Z',mode:'PROACTIVE'};
function reset(){cleanup();window.localStorage.clear();globalThis.fetch=originalFetch;}
function mock(){const calls:{url:unknown;body:Record<string,any>}[]=[];globalThis.fetch=async(u,o)=>{const body=JSON.parse(String(o?.body));calls.push({url:u,body});return response(u==='/api/analyze'?analyzed(body.source.url):u==='/api/evaluations/discover'?discovered:verified);};return calls;}
function start(ui:ReturnType<typeof render>,repo=url){fireEvent.click(ui.getByRole('button',{name:'Analyze Repository'}));fireEvent.change(ui.getByLabelText('Repository URL'),{target:{value:repo}});}
function submit(ui:ReturnType<typeof render>){fireEvent.click(within(ui.getByRole('dialog')).getByRole('button',{name:'Analyze Repository'}));}
async function ready(ui:ReturnType<typeof render>){await waitFor(()=>assert.ok(ui.getByRole('button',{name:'View Verifications'})));}

test('fresh Projects dashboard has one entry action, no graph/inspector/project navigation/zero metrics/Runs',()=>{
 try{const ui=render(createElement(ProjectWorkspace));assert.ok(ui.getByRole('heading',{name:'Your repositories'}));assert.ok(ui.getByText('No repositories analyzed yet.'));assert.equal(ui.getAllByRole('button',{name:'Analyze Repository'}).length,1);assert.equal(ui.queryByRole('navigation'),null);assert.equal(ui.queryByText('Runs'),null);assert.equal(ui.queryByText('Inspector'),null);assert.equal(ui.container.querySelector('.graph-canvas'),null);assert.equal(ui.container.querySelector('.overview-counts'),null);}finally{reset();}
});
test('setup mode cards, validation and conditional concern form one coherent action',()=>{
 const calls=mock();try{const ui=render(createElement(ProjectWorkspace));start(ui,'https://evil.example/repo');const dialog=within(ui.getByRole('dialog'));assert.ok(dialog.getByRole('button',{name:'Analyze Repository'}).hasAttribute('disabled'));fireEvent.change(ui.getByLabelText('Repository URL'),{target:{value:url}});assert.equal(dialog.getByRole('button',{name:'Analyze Repository'}).hasAttribute('disabled'),false);assert.equal(ui.queryByLabelText('What do you want to verify?'),null);fireEvent.click(ui.getByLabelText('On-demand'));assert.ok(dialog.getByRole('button',{name:'Analyze Repository'}).hasAttribute('disabled'));fireEvent.change(ui.getByLabelText('What do you want to verify?'),{target:{value:'Check explicit timeouts'}});assert.equal(dialog.getByRole('button',{name:'Analyze Repository'}).hasAttribute('disabled'),false);fireEvent.click(ui.getByLabelText('Proactive'));assert.equal(ui.queryByLabelText('What do you want to verify?'),null);fireEvent.click(dialog.getByRole('button',{name:'Cancel'}));assert.equal(ui.queryByRole('dialog'),null);assert.equal(calls.length,0);}finally{reset();}
});
test('analysis loading has no blank graph and prevents duplicate submissions',async()=>{
 let finish!:(r:Response)=>void,calls=0;globalThis.fetch=async()=>{calls++;return new Promise<Response>(r=>{finish=r;});};
 try{const ui=render(createElement(ProjectWorkspace));start(ui);submit(ui);fireEvent.click(ui.getByRole('button',{name:'Analyzing…'}));assert.equal(calls,1);assert.ok(ui.getAllByText('Resolving repository and analyzing architecture…').length);assert.equal(ui.container.querySelector('.graph-canvas'),null);finish(response({error:{code:'REMOTE_TIMEOUT',message:'Repository request timed out.'}},504));await waitFor(()=>assert.ok(ui.getByRole('alert')));assert.equal(ui.queryByRole('navigation'),null);}finally{reset();}
});
test('project creation enters Overview, persists only navigation metadata, and pages retain one discovery',async()=>{
 const calls=mock();try{const ui=render(createElement(StrictMode,null,createElement(ProjectWorkspace)));start(ui);submit(ui);await ready(ui);await waitFor(()=>assert.ok(ui.getByText('2 identified · suggestions are not verification results.')));assert.ok(ui.getByText('owner/first · 3d38d5a'));assert.ok(ui.getByRole('heading',{name:'Overview'}));assert.equal(ui.queryByLabelText('Verification result'),null);assert.equal(ui.queryByText('Runs'),null);
 const saved=JSON.parse(window.localStorage.getItem(PROJECTS_KEY)!);assert.equal(saved.length,1);assert.deepEqual(Object.keys(saved[0]).sort(),Object.keys(metadata).sort());assert.equal(saved[0].sha,sha);assert.equal(saved[0].architectureId,hash);
 fireEvent.click(ui.getByRole('button',{name:'Architecture'}));assert.ok(ui.getByText('Agent Workflow'));fireEvent.click(ui.getByText('Dependency View'));assert.equal(ui.container.querySelectorAll('.react-flow__node').length,14);fireEvent.click(ui.getByRole('button',{name:'Verifications'}));assert.ok(ui.getByRole('button',{name:'Run Verification'}));assert.ok(ui.getByRole('button',{name:'Verification not available yet'}).hasAttribute('disabled'));fireEvent.click(ui.getByRole('button',{name:'Overview'}));assert.equal(calls.filter(c=>c.url==='/api/evaluations/discover').length,1);
 }finally{reset();}
});
test('on-demand auto discovery sends bounded concern but never persists it',async()=>{
 const calls=mock();try{const ui=render(createElement(ProjectWorkspace));start(ui);fireEvent.click(ui.getByLabelText('On-demand'));const concern='Check external API calls for explicit timeouts';fireEvent.change(ui.getByLabelText('What do you want to verify?'),{target:{value:concern}});submit(ui);await ready(ui);await waitFor(()=>assert.equal(calls.length,2));assert.equal(calls[1].body.mode,'ON_DEMAND');assert.equal(calls[1].body.request_text,concern);assert.equal(calls[1].body.source.ref,sha);assert.equal(window.localStorage.getItem(PROJECTS_KEY)!.includes(concern),false);assert.equal(readProjects(window.localStorage)[0].mode,'ON_DEMAND');}finally{reset();}
});
test('no-match is an honest empty state and provider failure remains actionable',async()=>{
 globalThis.fetch=async u=>response(u==='/api/analyze'?analyzed():{...discovered,candidates:[]});try{const ui=render(createElement(ProjectWorkspace));start(ui);fireEvent.click(ui.getByLabelText('On-demand'));fireEvent.change(ui.getByLabelText('What do you want to verify?'),{target:{value:'Outside the catalog'}});submit(ui);await ready(ui);await waitFor(()=>assert.ok(ui.getAllByText('No currently supported evaluation matches this request.').length));fireEvent.click(ui.getByRole('button',{name:'Verifications'}));assert.equal(ui.queryByRole('button',{name:'Run Verification'}),null);assert.equal(ui.queryByText('NOT_VERIFIABLE'),null);globalThis.fetch=async()=>response({error:{code:'DISCOVERY_PROVIDER_FAILED',message:'Discovery is unavailable. Try again later.'}},502);fireEvent.click(ui.getByRole('button',{name:'Discover Verifications'}));await waitFor(()=>assert.ok(ui.getByRole('alert')));assert.equal(ui.queryByText('No currently supported evaluation matches this request.'),null);}finally{reset();}
});
test('two projects preserve separate session architecture/suggestions/result without a paid reopen call',async()=>{
 const calls=mock();try{const ui=render(createElement(ProjectWorkspace));start(ui);submit(ui);await ready(ui);fireEvent.click(ui.getByRole('button',{name:'Verifications'}));await waitFor(()=>assert.ok(ui.getByRole('button',{name:'Run Verification'})));fireEvent.click(ui.getByRole('button',{name:'Run Verification'}));await waitFor(()=>assert.ok(ui.getByLabelText('Verification result')));assert.ok(ui.getByText('app.py:12'));
 fireEvent.click(ui.getByRole('button',{name:'All Projects'}));assert.ok(ui.getByText(/Latest: External API Timeout Coverage/));start(ui,'https://github.com/owner/second');submit(ui);await ready(ui);assert.ok(ui.getByText('owner/second · 3d38d5a'));assert.equal(ui.queryByLabelText('Verification result'),null);fireEvent.click(ui.getByRole('button',{name:'All Projects'}));assert.equal(ui.getAllByRole('button',{name:'Open Project'}).length,2);const before=calls.length;
 fireEvent.click(within(ui.getByText('first',{selector:'h3'}).closest('article')!).getByRole('button',{name:'Open Project'}));await ready(ui);assert.ok(ui.getByText('owner/first · 3d38d5a'));fireEvent.click(ui.getByRole('button',{name:'Verifications'}));await waitFor(()=>assert.ok(ui.getByLabelText('Verification result')));assert.equal(calls.length,before);assert.equal(readProjects(window.localStorage).length,2);
 }finally{reset();}
});
test('stored project reopen uses exact SHA and fresh backend truth without automatic discovery',async()=>{
 window.localStorage.setItem(PROJECTS_KEY,JSON.stringify([{...metadata,architectureId:'b'.repeat(64),architecture:{invented:true},verdict:'VERIFIED'}]));const calls=mock();try{const ui=render(createElement(ProjectWorkspace));assert.ok(ui.getByText(/Reopening re-analyzes/));fireEvent.click(ui.getByRole('button',{name:'Open Project'}));await ready(ui);assert.deepEqual(calls[0].body,{source:{type:'github',url,ref:sha}});assert.equal(calls.length,1);assert.ok(ui.getByText('Snapshot '+hash.slice(0,12)));assert.equal(ui.queryByText('VERIFIED'),null);assert.equal(ui.queryByRole('button',{name:'Run Verification'}),null);}finally{reset();}
});
test('restored on-demand project needs a new concern before discovery',async()=>{
 window.localStorage.setItem(PROJECTS_KEY,JSON.stringify([{...metadata,mode:'ON_DEMAND'}]));const calls=mock();try{const ui=render(createElement(ProjectWorkspace));fireEvent.click(ui.getByRole('button',{name:'Open Project'}));await ready(ui);fireEvent.click(ui.getByRole('button',{name:'Verifications'}));fireEvent.click(ui.getByRole('button',{name:'Discover Verifications'}));assert.equal(calls.length,1);assert.ok(ui.getByRole('dialog'));assert.equal(ui.getByLabelText('What do you want to verify?').getAttribute('value'),null);assert.ok(within(ui.getByRole('dialog')).getByRole('button',{name:'Analyze Repository'}).hasAttribute('disabled'));}finally{reset();}
});
test('switching projects aborts/ignores late discovery; no hidden automatic retry on reopen',async()=>{
 let late!:(r:Response)=>void,signal:AbortSignal|null|undefined,discoveries=0;
 globalThis.fetch=async(u,o)=>{const body=JSON.parse(String(o?.body));if(u==='/api/analyze')return response(analyzed(body.source.url));discoveries++;if(discoveries===1){signal=o?.signal;return new Promise<Response>(r=>{late=r;});}return response({...discovered,candidates:[]});};
 try{const ui=render(createElement(ProjectWorkspace));start(ui);submit(ui);await ready(ui);await waitFor(()=>assert.equal(discoveries,1));fireEvent.click(ui.getByRole('button',{name:'All Projects'}));assert.equal(signal?.aborted,true);start(ui,'https://github.com/owner/second');submit(ui);await ready(ui);late(response(discovered));await waitFor(()=>assert.ok(ui.getByText('0 identified · suggestions are not verification results.')));assert.equal(ui.queryByText('External API Timeout Coverage'),null);fireEvent.click(ui.getByRole('button',{name:'All Projects'}));fireEvent.click(within(ui.getByText('first',{selector:'h3'}).closest('article')!).getByRole('button',{name:'Open Project'}));await ready(ui);assert.equal(discoveries,2);assert.equal(ui.queryByRole('button',{name:'Run Verification'}),null);}finally{reset();}
});
test('concern changes invalidate prior workspace, and rejected URL/ref/mode never leak selected data',async()=>{
 mock();try{const ui=render(createElement(ProjectWorkspace));start(ui);fireEvent.click(ui.getByLabelText('On-demand'));fireEvent.change(ui.getByLabelText('What do you want to verify?'),{target:{value:'Timeouts'}});submit(ui);await ready(ui);fireEvent.click(ui.getByRole('button',{name:'Re-analyze Repository'}));fireEvent.change(ui.getByLabelText('What do you want to verify?'),{target:{value:'Latency'}});assert.equal(ui.queryByRole('navigation'),null);assert.equal(ui.queryByRole('button',{name:'Run Verification'}),null);assert.equal(ui.queryByText('owner/first · 3d38d5a'),null);}finally{reset();}
});
test('malformed/outdated/localStorage entries are safely rejected and unknown fields stripped',()=>{
 for(const raw of ['bad json','null','{}',JSON.stringify([{...metadata,url:'https://evil.example/repo'}]),JSON.stringify([{...metadata,sha:'main'}]),JSON.stringify([{...metadata,mode:'OTHER'}])]){window.localStorage.setItem(PROJECTS_KEY,raw);assert.deepEqual(readProjects(window.localStorage),[]);}
 window.localStorage.setItem(PROJECTS_KEY,JSON.stringify([{...metadata,api_key:'untrusted-extra',request_text:'private concern'},metadata]));assert.deepEqual(readProjects(window.localStorage),[metadata]);assert.deepEqual(readProjects({getItem(){throw Error('storage blocked');}}),[]);assert.equal(writeProjects({setItem(){throw Error('quota');}},[]),false);reset();
});
test('malformed storage produces usable fresh landing',()=>{
 window.localStorage.setItem(PROJECTS_KEY,'broken');try{const ui=render(createElement(ProjectWorkspace));assert.ok(ui.getByText('No repositories analyzed yet.'));assert.ok(ui.getByRole('button',{name:'Analyze Repository'}));}finally{reset();}
});

test('empty architecture has an intentional explanation, no giant blank graph or Inspector',async()=>{
 globalThis.fetch=async u=>response(u==='/api/analyze'?{...analyzed(),graph:{nodes:[],edges:[],execution_flows:[],limitations:['No supported architecture found.']}}:{...discovered,candidates:[]});
 try{const ui=render(createElement(ProjectWorkspace));start(ui);submit(ui);await ready(ui);fireEvent.click(ui.getByRole('button',{name:'Architecture'}));assert.ok(ui.getByText('No architecture components were detected.'));assert.equal(ui.container.querySelector('.graph-canvas'),null);assert.equal(ui.queryByText('Inspector'),null);assert.ok(ui.getByText('No supported architecture found.'));}finally{reset();}
});
test('late verification cannot attach its evidence to a newly selected repository',async()=>{
 let late!:(r:Response)=>void,signal:AbortSignal|null|undefined;
 globalThis.fetch=async(u,o)=>{const body=JSON.parse(String(o?.body));if(u==='/api/analyze')return response(analyzed(body.source.url));if(u==='/api/evaluations/discover')return response(discovered);signal=o?.signal;return new Promise<Response>(r=>{late=r;});};
 try{const ui=render(createElement(ProjectWorkspace));start(ui);submit(ui);await ready(ui);fireEvent.click(ui.getByRole('button',{name:'Verifications'}));await waitFor(()=>assert.ok(ui.getByRole('button',{name:'Run Verification'})));fireEvent.click(ui.getByRole('button',{name:'Run Verification'}));fireEvent.click(ui.getByRole('button',{name:'All Projects'}));assert.equal(signal?.aborted,true);start(ui,'https://github.com/owner/second');submit(ui);await ready(ui);late(response(verified));fireEvent.click(ui.getByRole('button',{name:'Verifications'}));await waitFor(()=>assert.ok(ui.getByRole('button',{name:'Run Verification'})));assert.equal(ui.queryByLabelText('Verification result'),null);assert.equal(ui.queryByText('app.py:12'),null);assert.ok(ui.getByText('owner/second · 3d38d5a'));}finally{reset();}
});
test('storage rejects type-coerced snapshot IDs',()=>{
 window.localStorage.setItem(PROJECTS_KEY,JSON.stringify([{...metadata,sha:[sha]},{...metadata,architectureId:[hash]}]));assert.deepEqual(readProjects(window.localStorage),[]);reset();
});

test('controlled error categories receive actionable presentation text',()=>{
 assert.match(apiErrorMessage('REPOSITORY_NOT_FOUND_OR_PRIVATE','internal'),/public repository/);
 assert.equal(apiErrorMessage('ANALYSIS_STALE','internal'),'The repository snapshot changed. Analyze it again before continuing.');
 assert.equal(apiErrorMessage('DISCOVERY_PROVIDER_FAILED','internal'),'Verification discovery is temporarily unavailable. Try again later.');
 assert.equal(apiErrorMessage('UNKNOWN','Safe fallback'),'Safe fallback');
});
