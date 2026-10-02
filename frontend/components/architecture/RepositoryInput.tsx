"use client";
import { useState, type FormEvent } from "react";
import { validGitHubURL, type RepositorySubmission } from '@/lib/repository-source';

export function RepositoryInput({ busy, error, onSubmit, onClose, onChange }: { busy: boolean; error: string | null; onSubmit: (input: RepositorySubmission) => void; onClose: () => void; onChange: () => void }) {
  const [local, setLocal] = useState(false);
  const [url, setURL] = useState('');
  const [ref, setRef] = useState('');
  const [path, setPath] = useState('');
  const [mode, setMode] = useState<'PROACTIVE'|'ON_DEMAND'>('PROACTIVE');
  const [request, setRequest] = useState('');
  const [validation, setValidation] = useState<string | null>(null);
  const changed = () => { setValidation(null); onChange(); };
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (busy) return;
    if (local ? !path.startsWith('/') : !validGitHubURL(url)) { setValidation(local ? 'Enter an absolute local repository path.' : 'Enter an HTTPS public GitHub owner/repository URL.'); return; }
    if (!local && ref && (!/^[A-Za-z0-9_][A-Za-z0-9_./-]{0,255}$/.test(ref) || ref.includes('..') || ref.includes('//') || ref.endsWith('/'))) { setValidation('Enter a valid branch, tag or commit.'); return; }
    if (mode==='ON_DEMAND' && (!request.trim() || request.length>2000)) { setValidation('Enter a concern of at most 2000 characters.'); return; }
    setValidation(null);
    onSubmit({source:local?{type:'local',path}:{type:'github',url,...(ref?{ref}:{})},intent:{mode,...(mode==='ON_DEMAND'?{request_text:request}:{})},autoDiscover:!local});
  };
  return <div className="repository-input-backdrop"><section role="dialog" aria-modal="true" aria-labelledby="repository-input-title" className="repository-input">
    <h2 id="repository-input-title">Analyze Repository</h2><p>Inspect a public GitHub Python repository. Repository code is never executed.</p>
    <form onSubmit={submit}>
      {!local ? <><label htmlFor="repository-url">Repository URL</label><input id="repository-url" value={url} onChange={event=>{setURL(event.target.value);changed();}} placeholder="https://github.com/owner/repository" autoFocus required disabled={busy} />
        <label htmlFor="repository-ref">Branch / tag / commit (optional)</label><input id="repository-ref" value={ref} onChange={event=>{setRef(event.target.value);changed();}} placeholder="Default branch" maxLength={256} disabled={busy} /></> : <><label htmlFor="repository-path">Local repository path</label><input id="repository-path" value={path} onChange={event=>{setPath(event.target.value);changed();}} placeholder="/Users/me/projects/my-agent" required disabled={busy} /></>}
      <fieldset className="analysis-mode" disabled={busy}><legend>Analysis mode</legend>
        <label><input type="radio" name="mode" checked={mode==='PROACTIVE'} onChange={()=>{setMode('PROACTIVE');changed();}} />PROACTIVE · Find important engineering checks for me</label>
        <label><input type="radio" name="mode" checked={mode==='ON_DEMAND'} onChange={()=>{setMode('ON_DEMAND');changed();}} />ON-DEMAND · I have a specific requirement or concern</label>
      </fieldset>
      {mode==='ON_DEMAND' && <><label htmlFor="repository-concern">What do you want Verisys to check?</label><textarea id="repository-concern" value={request} onChange={event=>{setRequest(event.target.value);changed();}} maxLength={2000} required disabled={busy} /><p className="discovery-note">Matches are bounded by the existing evaluation catalog. Most evaluations are not executable yet.</p></>}
      <button type="button" className="local-source-toggle" disabled={busy} onClick={()=>{setLocal(!local);changed();}}>{local?'Use public GitHub repository':'Local path · development option'}</button>
      {(validation ?? error) && <p role="alert" className="repository-error">{validation ?? error}</p>}
      {busy && <p role="status">Analyzing repository…</p>}
      <div className="repository-input-actions"><button type="button" disabled={busy} onClick={onClose}>Cancel</button><button type="submit" className="primary-button" disabled={busy}>{busy ? 'Analyzing…' : 'Analyze'}</button></div>
    </form>
  </section></div>;
}
