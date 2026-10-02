"use client";
import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { validGitHubURL, type RepositorySubmission } from '@/lib/repository-source';

export function RepositoryInput({ busy, error, onSubmit, onClose, onChange, initial }: { initial?: RepositorySubmission; busy: boolean; error: string | null; onSubmit: (input: RepositorySubmission) => void; onClose: () => void; onChange: () => void }) {
  const dialog = useRef<HTMLElement>(null);
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    dialog.current?.querySelector<HTMLInputElement>('input')?.focus();
    return () => { if (previous?.isConnected) previous.focus(); };
  }, []);
  const keyboard = (event: KeyboardEvent) => {
    if (event.key === 'Escape' && !busy) { event.preventDefault(); onClose(); }
    if (event.key !== 'Tab') return;
    const controls = Array.from(dialog.current?.querySelectorAll<HTMLElement>('input:not(:disabled),textarea:not(:disabled),button:not(:disabled)') ?? []);
    const first = controls[0], last = controls.at(-1);
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
    if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
  };
  const [local, setLocal] = useState(initial?.source.type === "local");
  const [url, setURL] = useState(initial?.source.type === 'github' ? initial.source.url : '');
  const [ref, setRef] = useState(initial?.source.type === 'github' ? initial.source.ref ?? '' : '');
  const [path, setPath] = useState(initial?.source.type === 'local' ? initial.source.path : '');
  const [mode, setMode] = useState<'PROACTIVE'|'ON_DEMAND'>(initial?.intent.mode ?? 'PROACTIVE');
  const [request, setRequest] = useState(initial?.intent.request_text ?? '');
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
  const validRef = !ref || (/^[A-Za-z0-9_][A-Za-z0-9_./-]{0,255}$/.test(ref) && !ref.includes('..') && !ref.includes('//') && !ref.endsWith('/'));
  const canSubmit = (local ? path.startsWith('/') : validGitHubURL(url) && validRef) && (mode === 'PROACTIVE' || (request.trim().length > 0 && request.length <= 2000));
  return <div className="repository-input-backdrop"><section ref={dialog} onKeyDown={keyboard} role="dialog" aria-modal="true" aria-labelledby="repository-input-title" className="repository-input">
    <h2 id="repository-input-title">Analyze Repository</h2><p>Inspect a public GitHub Python repository. Repository code is never executed.</p>
    <form onSubmit={submit}>
      {!local ? <><label htmlFor="repository-url">Repository URL</label><input id="repository-url" value={url} onChange={event=>{setURL(event.target.value);changed();}} placeholder="https://github.com/owner/repository" maxLength={512} autoFocus required disabled={busy} />
        <label htmlFor="repository-ref">Branch / tag / commit (optional)</label><input id="repository-ref" value={ref} onChange={event=>{setRef(event.target.value);changed();}} placeholder="Default branch" maxLength={256} disabled={busy} /></> : <><label htmlFor="repository-path">Local repository path</label><input id="repository-path" value={path} onChange={event=>{setPath(event.target.value);changed();}} placeholder="/Users/me/projects/my-agent" maxLength={4096} required disabled={busy} /></>}
      <fieldset className="analysis-mode" disabled={busy}><legend>How do you want Verisys to analyze it?</legend>
        <label className={mode==='PROACTIVE'?'mode-choice selected':'mode-choice'}><input type="radio" name="mode" checked={mode==='PROACTIVE'} onChange={()=>{setMode('PROACTIVE');changed();}} aria-label="Proactive" /><span><strong>Find important checks for me</strong><small>Understand the architecture and identify engineering properties worth investigating.</small></span></label>
        <label className={mode==='ON_DEMAND'?'mode-choice selected':'mode-choice'}><input type="radio" name="mode" checked={mode==='ON_DEMAND'} onChange={()=>{setMode('ON_DEMAND');changed();}} aria-label="On-demand" /><span><strong>I know what I want checked</strong><small>Investigate a specific engineering requirement or concern.</small></span></label>
      </fieldset>
      {mode==='ON_DEMAND' && <><label htmlFor="repository-concern">What do you want to verify?</label><textarea id="repository-concern" value={request} onChange={event=>{setRequest(event.target.value);changed();}} placeholder="Check whether external API calls define explicit timeouts." maxLength={2000} required disabled={busy} /><p className="discovery-note">Matches are bounded by the existing evaluation catalog. Most evaluations are not executable yet.</p></>}
      <button type="button" className="local-source-toggle" disabled={busy} onClick={()=>{setLocal(!local);changed();}}>{local?'Use public GitHub repository':'Local path · development option'}</button>
      {(validation ?? error) && <p role="alert" className="repository-error">{validation ?? error}</p>}
      {busy && <p role="status">Resolving repository and analyzing architecture…</p>}
      <div className="repository-input-actions"><button type="button" disabled={busy} onClick={onClose}>Cancel</button><button type="submit" className="primary-button" disabled={busy || !canSubmit}>{busy ? 'Analyzing…' : 'Analyze Repository'}</button></div>
    </form>
  </section></div>;
}
