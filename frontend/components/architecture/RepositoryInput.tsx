"use client";
import { useState, type FormEvent } from "react";

export function RepositoryInput({ busy, error, onSubmit, onClose }: { busy: boolean; error: string | null; onSubmit: (path: string) => void; onClose: () => void }) {
  const [path, setPath] = useState("");
  const [validation, setValidation] = useState<string | null>(null);
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!path.startsWith("/")) { setValidation("Enter an absolute local repository path."); return; }
    setValidation(null); onSubmit(path);
  };
  return <div className="repository-input-backdrop"><section role="dialog" aria-modal="true" aria-labelledby="repository-input-title" className="repository-input">
    <h2 id="repository-input-title">Analyze Repository</h2><p>Inspect a local Python repository using bounded static analysis. Repository code is never executed.</p>
    <form onSubmit={submit}><label htmlFor="repository-path">Local repository path</label><input id="repository-path" value={path} onChange={event => setPath(event.target.value)} placeholder="/Users/me/projects/my-agent" autoFocus required disabled={busy} />
      {(validation ?? error) && <p role="alert" className="repository-error">{validation ?? error}</p>}
      {busy && <p role="status">Analyzing repository…</p>}
      <div className="repository-input-actions"><button type="button" disabled={busy} onClick={onClose}>Cancel</button><button type="submit" className="primary-button" disabled={busy}>{busy ? "Analyzing…" : "Analyze"}</button></div>
    </form>
  </section></div>;
}
