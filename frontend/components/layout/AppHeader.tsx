import { ChevronDown, FolderGit2, ScanLine, SquareStack } from "lucide-react";

export function AppHeader({ repositoryName, analyzing, ready, onAnalyze }: { repositoryName: string; analyzing: boolean; ready: boolean; onAnalyze: () => void }) {
  return <header className="app-header">
    <div className="brand"><span className="brand-mark"><SquareStack size={21} strokeWidth={2.2} /></span>verisys<span className="brand-divider" /></div>
    <div className="repository-context"><FolderGit2 size={17} /><span>{repositoryName}</span><ChevronDown size={13} /></div>
    <div className="header-right"><span className="demo-badge">{ready ? "REAL ANALYSIS" : analyzing ? "ANALYZING" : "LOCAL REPOSITORY"}</span><button className="analyze-button" disabled={analyzing} onClick={onAnalyze}><ScanLine size={16} />Analyze Repository</button></div>
  </header>;
}
