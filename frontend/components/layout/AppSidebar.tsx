import { Boxes, GitBranch, LayoutDashboard, ListChecks, Play, ChevronRight } from "lucide-react";

export function AppSidebar({ repositoryName, repositoryPath }: { repositoryName: string; repositoryPath: string | null }) {
  const items = [
    { label: "Overview", icon: LayoutDashboard }, { label: "Architecture", icon: Boxes },
    { label: "Verifications", icon: ListChecks }, { label: "Runs", icon: Play },
  ];
  return <aside className="app-sidebar">
    <div className="sidebar-label">WORKSPACE</div>
    <nav aria-label="Workspace navigation">{items.map(({ label, icon: Icon }) => <button key={label} aria-label={label} className={`nav-item ${label === "Architecture" ? "active" : ""}`} aria-current={label === "Architecture" ? "page" : undefined} disabled={label !== "Architecture"} title={label !== "Architecture" ? "Available in a later milestone" : undefined}><Icon size={17} /><span>{label}</span>{label === "Architecture" && <ChevronRight size={14} />}</button>)}</nav>
    <div className="sidebar-repository"><div className="sidebar-label">REPOSITORY</div><div><GitBranch size={15} /><span>{repositoryName}</span></div><p title={repositoryPath ?? undefined}>{repositoryPath ?? "No repository analyzed yet"}</p></div>
    <div className="sidebar-footer"><span className="sidebar-label">LOCAL STATIC ANALYSIS</span><p>Architecture inspection.<br />Source-backed architecture.</p></div>
  </aside>;
}
