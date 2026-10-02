"use client";
import { useCallback, useEffect, useRef, useState } from 'react';
import { FolderGit2, ArrowRight, Plus } from 'lucide-react';
import { AppHeader } from '../layout/AppHeader';
import { AppSidebar, type ProjectSection } from '../layout/AppSidebar';
import { ArchitectureView } from '../architecture/ArchitectureGraph';
import { RepositoryInput } from '../architecture/RepositoryInput';
import { SuggestedVerifications } from '../evaluation/SuggestedVerifications';
import { analyzeRepository, type AnalysisResult } from '@/lib/architecture/analysis-client';
import { idleDiscovery, type DiscoveryState } from '@/lib/evaluation/discovery-client';
import { idleVerification, type VerificationState } from '@/lib/evaluation/verification-client';
import { readProjects, writeProjects, recentProject, type RecentProject } from '@/lib/projects';
import type { RepositorySubmission } from '@/lib/repository-source';

type Session = { result: AnalysisResult; input: RepositorySubmission; analyzedAt: string; discovery: DiscoveryState; verification: VerificationState };
const identity = (result: AnalysisResult) => result.repository.source?.type === 'github' ? result.repository.source.url : result.repository.path ?? result.repository.name;
function paused(session: Session): Session {
  // Leaving aborts browser requests; neither claim completion nor retry paid calls.
  return {...session,input:{...session.input,autoDiscover:false},discovery:session.discovery.status==='DISCOVERING'?idleDiscovery:session.discovery,verification:session.verification.status==='RUNNING'?idleVerification:session.verification};
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
      const session:Session={result,input:{...input,source:result.repository.source??input.source,autoDiscover:!reopening&&input.autoDiscover},analyzedAt:new Date().toISOString(),discovery:idleDiscovery,verification:idleVerification};
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
  const reanalyze=()=>{if(active)setSetup({initial:{...active.input,autoDiscover:active.input.source.type==='github'}});};
  const name=active?.result.repository.name.split('/').pop();
  const repoIdentity=active?`${active.result.repository.name}${active.result.repository.resolved_commit_sha?` · ${active.result.repository.resolved_commit_sha.slice(0,7)}`:''}`:undefined;
  const nodeCount=(type:string)=>active?.result.graph.nodes.filter(n=>n.type===type).length??0;
  return <div className="app-shell project-app"><AppHeader name={name} identity={repoIdentity} onProjects={active?leave:undefined}/>
    {!active?<main className="projects-page"><div className="page-heading"><div><h1>Your repositories</h1><p>Analyze repositories, understand their architecture, and verify engineering properties with evidence.</p></div><button className="primary-button" disabled={analysis==='ANALYZING'} onClick={()=>{setError(null);setSetup({});}}><Plus size={16}/>Analyze Repository</button></div>
      {analysis==='ANALYZING'&&<div className="workspace-notice" role="status"><strong>Resolving repository and analyzing architecture…</strong><p>Fetching the requested revision and inspecting source safely. Repository code is never executed.</p></div>}
      {analysis==='ERROR'&&!setup&&<div className="workspace-notice error" role="alert"><strong>Analysis failed</strong><p>{error}</p><button onClick={()=>setSetup({})}>Try another repository</button></div>}
      {storageNote&&<p className="workspace-notice">Recent projects could not be saved in this browser. Your current session is still available.</p>}
      {recent.length===0&&Object.keys(sessions).length===0?<div className="projects-empty"><FolderGit2 size={36}/><h2>Analyze your first repository</h2><p>No repositories analyzed yet.</p><p>Start with a public GitHub Python repository.</p></div>:<><div className="projects-list-heading"><h2>Recent projects</h2><span>Stored in this browser · not a team database</span></div><div className="projects-list">
        {recent.map(project=>{const session=sessions[project.url];const latest=session?.verification.status==='RESULT'?session.verification.result:null;
          return <article className="project-row" key={project.url}><div className="project-row-icon"><FolderGit2 size={22}/></div><div className="project-row-identity"><h3>{project.name}</h3><p>{project.ownerRepository}</p><div className="project-row-meta"><code>{project.sha.slice(0,7)}</code><span>{project.mode==='PROACTIVE'?'Proactive':'On-demand'}</span><time dateTime={session?.analyzedAt??project.analyzedAt}>Last analyzed {new Date(session?.analyzedAt??project.analyzedAt).toLocaleString()}</time></div>
            {session?.discovery.result&&<p>{session.discovery.result.candidates.length} suggested checks</p>}{latest&&<p>Latest: {latest.evaluation_name} · {latest.verdict_status??latest.applicability}</p>}{!session&&<small>Reopening re-analyzes this pinned commit. Suggestions and results are not stored.</small>}</div><button disabled={analysis==='ANALYZING'} onClick={()=>open(project)}>Open Project <ArrowRight size={14}/></button></article>;})}
        {Object.entries(sessions).filter(([,s])=>s.input.source.type==='local').map(([key,s])=><article className="project-row" key={key}><div className="project-row-identity"><h3>{s.result.repository.name}</h3><p>Local development · current session only</p></div><button disabled={analysis==='ANALYZING'} onClick={()=>{setSelected(key);setSection('Overview');}}>Open Project <ArrowRight size={14}/></button></article>)}
      </div></>}
    </main>:<div className="project-layout"><AppSidebar section={section} onSelect={setSection}/><div ref={content} className="project-content">
      {section==='Overview'&&<main className="project-overview"><div className="page-heading"><div><h1>Overview</h1><p>Source-grounded understanding and evidence-backed checks for {name}.</p></div><button className="secondary-button" onClick={reanalyze}>Re-analyze Repository</button></div>
        <section className="overview-section"><div className="overview-section-heading"><h2>Architecture</h2><button onClick={()=>setSection('Architecture')}>Explore Architecture <ArrowRight size={14}/></button></div><div className="overview-counts"><div><strong>{active.result.graph.nodes.length}</strong><span>components</span></div><div><strong>{nodeCount('API_ROUTE')}</strong><span>API routes</span></div><div><strong>{nodeCount('EXTERNAL_SERVICE')}</strong><span>external services</span></div><div><strong>{nodeCount('TOOL')}</strong><span>tools</span></div></div><p>Detected source structure and possible flows. Import relationships do not imply runtime execution.</p></section>
        <section className="overview-section"><div className="overview-section-heading"><h2>Suggested Verifications</h2><button onClick={()=>setSection('Verifications')}>View Verifications <ArrowRight size={14}/></button></div>
          {active.discovery.status==='DISCOVERING'?<p role="status">Discovering verifications… Selecting grounded checks for this {active.input.intent.mode==='ON_DEMAND'?'concern':'architecture'}.</p>:active.discovery.status==='ERROR'?<p role="alert">{active.discovery.error}</p>:active.discovery.result?<><p>{active.discovery.result.candidates.length} identified · suggestions are not verification results.</p><ul className="overview-suggestions">{active.discovery.result.candidates.map(c=><li key={c.id}><span>{c.name}</span><small>{c.can_execute?'Ready to run':'Verification not available yet'}</small></li>)}</ul>{active.discovery.status==='EMPTY'&&<p>{active.input.intent.mode==='ON_DEMAND'?'No currently supported evaluation matches this request.':'No supported evaluation was selected.'}</p>}</>:<p>{active.input.intent.mode==='ON_DEMAND'&&!active.input.intent.request_text?'Re-analyze with your concern to discover matching checks.':'Discover grounded checks in Verifications. No recommendations have been collected for this session.'}</p>}
        </section>
        <section className="overview-section"><h2>Latest Verification</h2>{active.verification.status==='RESULT'?<><h3>{active.verification.result.evaluation_name}</h3><p className={`overview-verdict result-status ${(active.verification.result.verdict_status??active.verification.result.applicability).toLowerCase()}`}>{active.verification.result.verdict_status??active.verification.result.applicability}</p><p>{active.verification.result.summary}</p><button onClick={()=>setSection('Verifications')}>View evidence and result <ArrowRight size={14}/></button></>:<p>{active.verification.status==='RUNNING'?'Running static verification and collecting source-backed evidence…':active.verification.status==='ERROR'?active.verification.error:'Run an available verification to collect evidence.'}</p>}</section>
        <p className="snapshot-note">Analyzed {new Date(active.analyzedAt).toLocaleString()} · {active.input.intent.mode==='PROACTIVE'?'Proactive':'On-demand'} · <code title={active.result.architecture_id}>Snapshot {active.result.architecture_id.slice(0,12)}</code></p>
      </main>}
      {section==='Architecture'&&<ArchitectureView key={selected} result={active.result}/>}
      {/* Keep session controller mounted across sections: navigation never repeats discovery. */}
      <main className="project-verifications" hidden={section!=='Verifications'}><div className="page-heading"><div><h1>Verifications</h1><p>Run an available check to collect real evidence. Unsupported checks remain suggestions.</p></div></div>
        {active.input.intent.mode==='ON_DEMAND'&&<p className="concern-context">Concern: {active.input.intent.request_text??'Re-analyze with a concern to select matching checks.'}</p>}
        <SuggestedVerifications key={`${selected}:${active.analyzedAt}`} source={active.result.repository.source??active.input.source} intent={active.input.intent.mode==='ON_DEMAND'||active.input.source.type==='github'?active.input.intent:undefined} autoDiscover={active.input.autoDiscover} architectureId={active.result.architecture_id} initialDiscovery={active.discovery} initialVerification={active.verification} onStateChange={stateChanged} onAnalyze={reanalyze}/>
      </main>
    </div></div>}
    {setup&&<RepositoryInput initial={setup.initial} busy={analysis==='ANALYZING'} error={error} onSubmit={input=>void submit(input)} onClose={()=>{setSetup(null);setError(null);}} onChange={()=>{if(!busy.current){leave();setError(null);}}}/>}
  </div>;
}
