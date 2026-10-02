import { Boxes, LayoutDashboard, ListChecks } from 'lucide-react';
export type ProjectSection = 'Overview' | 'Architecture' | 'Verifications';
export function AppSidebar({ section, onSelect }: {section: ProjectSection; onSelect: (section: ProjectSection) => void}) {
  const items = [{label:'Overview',icon:LayoutDashboard},{label:'Architecture',icon:Boxes},{label:'Verifications',icon:ListChecks}] as const;
  return <aside className="app-sidebar"><nav aria-label="Project navigation">{items.map(({label,icon:Icon}) =>
    <button key={label} className={`nav-item ${section===label?'active':''}`} aria-current={section===label?'page':undefined} onClick={()=>onSelect(label)}><Icon size={18}/><span>{label}</span></button>)}</nav>
    <div className="sidebar-footer"><p>Architecture informs the check.<br/>Evidence supports the result.</p></div>
  </aside>;
}
