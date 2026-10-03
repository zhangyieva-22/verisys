"use client";
import { useCallback, useEffect, useRef, useState } from 'react';
import { FolderGit2, ArrowRight, Plus } from 'lucide-react';
import { ProjectOverview } from './ProjectOverview';
import { AppHeader } from '../layout/AppHeader';
import { AppSidebar, type ProjectSection } from '../layout/AppSidebar';
import { ArchitectureView } from '../architecture/ArchitectureGraph';
import { RepositoryInput } from '../architecture/RepositoryInput';
import { SuggestedVerifications } from '../evaluation/SuggestedVerifications';
import { UnderstandingView } from '../understanding/UnderstandingView';
import { analyzeRepository, type AnalysisResult } from '@/lib/architecture/analysis-client';
import { idleDiscovery, type DiscoveryState } from '@/lib/evaluation/discovery-client';
import { idleVerification, type VerificationState } from '@/lib/evaluation/verification-client';
import { idleUnderstanding, type UnderstandingState } from '@/lib/understanding/understanding-client';
import { DiagramApiError, enrichDiagram, idleEnrichment, type EnrichmentState } from '@/lib/architecture/diagram-client';
import { readProjects, writeProjects, recentProject, type RecentProject } from '@/lib/projects';
import type { RepositorySubmission } from '@/lib/repository-source';

type Session = { result: AnalysisResult; input: RepositorySubmission; analyzedAt: string; discovery: DiscoveryState; verification: VerificationState; understanding: UnderstandingState; enrichment: EnrichmentState };
const identity = (result: AnalysisResult) => result.repository.source?.type === 'github' ? result.repository.source.url : result.repository.path ?? result.repository.name;
function paused(session: Session): Session {
  // Leaving aborts browser requests; neither claim completion nor retry paid calls.
  return {...session,input:{...session.input,autoDiscover:false},discovery:session.discovery.status==='DISCOVERING'?idleDiscovery:session.discovery,verification:session.verification.status==='RUNNING'?idleVerification:session.verification,understanding:session.understanding.status==='GENERATING'?idleUnderstanding:session.understanding};
}
export function ProjectWorkspace() {
  const [recent,setRecent]=useState<RecentProject[]>([]);
  const [sessions,setSessions]=useState<Record<string,Session>>({});
  const [selected,setSelected]=useState<string|null>(null);
  const [section,setSection]=useState<ProjectSection>('Overview');
  const [setup,setSetup]=useState<{initial?:RepositorySubmission}|null>(null);
  const [analysis,setAnalysis]=useState<'IDLE'|'ANALYZING'|'ERROR'|'READY'>('IDLE');
  const [error,setError]=useState<string|null>(null);
  const [storageNote,setStorageNote]=useState(false);
  const [storageReady,setStorageReady]=useState(false);
  const busy=useRef(false); const request=useRef(0);
  const content = useRef<HTMLDivElement>(null);
  useEffect(()=>{content.current?.scrollIntoView?.({block:'start'});},[selected,section]);
  useEffect(()=>{try{setRecent(readProjects(window.localStorage));}catch{setStorageNote(true);}setStorageReady(true);},[]);
  useEffect(()=>{if(storageReady){try{if(!writeProjects(window.localStorage,recent))setStorageNote(true);}catch{setStorageNote(true);}}},[recent,storageReady]);
  const active=selected?sessions[selected]:undefined;
  const leave=()=>{if(selected)setSessions(p=>p[selected]?{...p,[selected]:paused(p[selected])}:p);setSelected(null);setSection('Overview');};
  const submit=async(input:RepositorySubmission,reopening=false)=>{
    if(busy.current)return;busy.current=true;const current=++request.current;
    leave();setAnalysis('ANALYZING');setError(null);
    try{
      const result=await analyzeRepository(input.source);if(current!==request.current)return;
      const key=identity(result);
      const session:Session={result,input:{...input,source:result.repository.source??input.source,autoDiscover:!reopening&&input.autoDiscover},analyzedAt:new Date().toISOString(),discovery:idleDiscovery,verification:idleVerification,understanding:idleUnderstanding,enrichment:idleEnrichment};
      setSessions(p=>({...p,[key]:session}));setSelected(key);setSection('Overview');
      const metadata=recentProject(result,input.intent);
      if(metadata)setRecent(p=>[metadata,...p.filter(item=>item.url!==metadata.url)].slice(0,20));
      setAnalysis('READY');setSetup(null);
    }catch(failure){if(current!==request.current)return;setAnalysis('ERROR');setError(failure instanceof Error?failure.message:'Repository analysis could not be completed.');}
    finally{if(current===request.current)busy.current=false;}
  };
  const open=(project:RecentProject)=>{
    if(busy.current)return;
    if(sessions[project.url]){setSelected(project.url);setSection('Overview');setAnalysis('READY');setError(null);return;}
    // Metadata is navigation only: acquire fresh server-owned IR at the saved pin.
    void submit({source:{type:'github',url:project.url,ref:project.sha},intent:{mode:project.mode},autoDiscover:false},true);
  };
  const stateChanged=useCallback((discovery:DiscoveryState,verification:VerificationState)=>{
    if(selected)setSessions(p=>p[selected]?{...p,[selected]:{...p[selected],discovery,verification}}:p);
  },[selected]);
  const understandingChanged=useCallback((understanding:UnderstandingState)=>{
    if(selected)setSessions(p=>p[selected]?{...p,[selected]:{...p[selected],understanding}}:p);
  },[selected]);
  // Enrichment lives with the session, not the view: leaving Architecture never discards a paid call.
  const enriching=useRef(new Set<string>());
  const enrich=async()=>{
    const key=selected;const session=key?sessions[key]:undefined;
    if(!key||!session||enriching.current.has(key))return;
    enriching.current.add(key);
    const update=(enrichment:EnrichmentState)=>setSessions(p=>p[key]&&p[key].analyzedAt===session.analyzedAt?{...p,[key]:{...p[key],enrichment}}:p);
    update({status:'ENRICHING',result:null,error:null});
    try{update({status:'READY',result:await enrichDiagram(session.result.repository.source??session.input.source,session.result.architecture_id),error:null});}
    catch(failure){update({status:'ERROR',result:null,error:failure instanceof Error?failure.message:'Diagram enrichment could not be completed.',stale:failure instanceof DiagramApiError&&failure.code==='ANALYSIS_STALE'});}
    finally{enriching.current.delete(key);}
  };
  const reanalyze=()=>{if(active)setSetup({initial:{...active.input,autoDiscover:active.input.source.type==='github'}});};
  const name=active?.result.repository.name.split('/').pop();
  const repoIdentity=active?`${active.result.repository.name}${active.result.repository.resolved_commit_sha?` · ${active.result.repository.resolved_commit_sha.slice(0,7)}`:''}`:undefined;
  return <div className="app-shell project-app"><AppHeader name={name} identity={repoIdentity} onProjects={active?leave:undefined}/>
    {!active?<main className="projects-page"><div className="page-heading"><div><h1>Your repositories</h1><p>Analyze repositories, understand their architecture, and verify engineering properties with evidence.</p></div><button className="primary-button" disabled={analysis==='ANALYZING'} onClick={()=>{setError(null);setSetup({});}}><Plus size={16}/>Analyze Repository</button></div>
      {analysis==='ANALYZING'&&<div className="workspace-notice" role="status"><strong>Resolving repository and analyzing architecture…</strong><p>Fetching the requested revision and inspecting source safely. Repository code is never executed.</p></div>}
      {analysis==='ERROR'&&!setup&&<div className="workspace-notice error" role="alert"><strong>Analysis failed</strong><p>{error}</p><button onClick={()=>setSetup({})}>Try another repository</button></div>}
      {storageNote&&<p className="workspace-notice">Recent projects could not be saved in this browser. Your current session is still available.</p>}
      {recent.length===0&&Object.keys(sessions).length===0?<div className="projects-empty"><FolderGit2 size={36}/><h2>Analyze your first repository</h2><p>No repositories analyzed yet.</p><p>Start with a public GitHub Python repository.</p></div>:<><div className="projects-list-heading"><h2>Recent projects</h2><span>Stored in this browser · not a team database</span></div><div className="projects-list">
        {recent.map(project=>{const session=sessions[project.url];const latest=session?.verification.status==='RESULT'?session.verification.result:null;
          return <article className="project-row" key={project.url}><div className="project-row-icon"><FolderGit2 size={22}/></div><div className="project-row-identity"><h3>{project.name}</h3><p>{project.ownerRepository}</p><div className="project-row-meta"><code>{project.sha.slice(0,7)}</code><span>{project.mode==='PROACTIVE'?'Proactive':'On-demand'}</span><time dateTime={session?.analyzedAt??project.analyzedAt}>Last analyzed {new Date(session?.analyzedAt??project.analyzedAt).toLocaleString()}</time></div>
            {session?.discovery.result&&<p>{session.discovery.result.candidates.length} suggested checks</p>}{latest&&<p>Latest: {latest.evaluation_name} · {latest.verdict_status??latest.applicability}</p>}{!session&&<small>Reopening re-analyzes this pinned commit. Saved suggestions and results are reused when you run them again.</small>}</div><button disabled={analysis==='ANALYZING'} onClick={()=>open(project)}>Open Project <ArrowRight size={14}/></button></article>;})}
        {Object.entries(sessions).filter(([,s])=>s.input.source.type==='local').map(([key,s])=><article className="project-row" key={key}><div className="project-row-identity"><h3>{s.result.repository.name}</h3><p>Local development · current session only</p></div><button disabled={analysis==='ANALYZING'} onClick={()=>{setSelected(key);setSection('Overview');}}>Open Project <ArrowRight size={14}/></button></article>)}
      </div></>}
    </main>:<div className="project-layout"><AppSidebar section={section} onSelect={setSection}/><div ref={content} className="project-content">
      {section==='Overview'&&<ProjectOverview result={active.result} discovery={active.discovery} verification={active.verification} analyzedAt={active.analyzedAt} onArchitecture={()=>setSection('Architecture')} onVerifications={()=>setSection('Verifications')} onReanalyze={reanalyze}/>}
      {section==='Architecture'&&<ArchitectureView key={selected} result={active.result} enrichment={active.enrichment} onEnrich={()=>void enrich()}/>}
      {/* Keep paid-call controllers mounted across sections: navigation never repeats or aborts them. */}
      <div hidden={section!=='Understanding'}><UnderstandingView key={`${selected}:${active.analyzedAt}`} source={active.result.repository.source??active.input.source} architectureId={active.result.architecture_id} initialState={active.understanding} onStateChange={understandingChanged} onAnalyze={reanalyze}/></div>
      <main className="project-verifications" hidden={section!=='Verifications'}><div className="page-heading"><div><h1>Verifications</h1><p>Run an available check to collect real evidence. Unsupported checks remain suggestions.</p></div></div>
        {active.input.intent.mode==='ON_DEMAND'&&<p className="concern-context">Concern: {active.input.intent.request_text??'Re-analyze with a concern to select matching checks.'}</p>}
        <SuggestedVerifications key={`${selected}:${active.analyzedAt}`} source={active.result.repository.source??active.input.source} intent={active.input.intent.mode==='ON_DEMAND'||active.input.source.type==='github'?active.input.intent:undefined} autoDiscover={active.input.autoDiscover} architectureId={active.result.architecture_id} initialDiscovery={active.discovery} initialVerification={active.verification} onStateChange={stateChanged} onAnalyze={reanalyze}/>
      </main>
    </div></div>}
    {setup&&<RepositoryInput initial={setup.initial} busy={analysis==='ANALYZING'} error={error} onSubmit={input=>void submit(input)} onClose={()=>{setSetup(null);setError(null);}} onChange={()=>{if(!busy.current){leave();setError(null);}}}/>}
  </div>;
}
