import { ChevronDown, FolderGit2, ScanLine, SquareStack } from "lucide-react";
import { repositoryName } from "@/lib/architecture/demo";

export function AppHeader() {
  return <header className="app-header">
    <div className="brand"><span className="brand-mark"><SquareStack size={21} strokeWidth={2.2} /></span>verisys<span className="brand-divider" /></div>
    <div className="repository-context"><FolderGit2 size={17} /><span>{repositoryName}</span><ChevronDown size={13} /></div>
    <div className="header-right"><span className="demo-badge">OFFLINE SNAPSHOT</span><button className="analyze-button" disabled title="Repository analysis will be connected in M3C"><ScanLine size={16} />Analyze Repository</button></div>
  </header>;
}
