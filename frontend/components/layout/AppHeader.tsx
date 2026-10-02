import { ArrowLeft, SquareStack } from 'lucide-react';
export function AppHeader({ name, identity, onProjects }: {name?: string; identity?: string; onProjects?: () => void}) {
  return <header className="app-header">
    <div className="brand"><span className="brand-mark"><SquareStack size={21}/></span>verisys</div>
    {name && <div className="project-identity"><strong>{name}</strong><span>{identity}</span></div>}
    {onProjects && <button className="all-projects" onClick={onProjects}><ArrowLeft size={15}/>All Projects</button>}
    {!name && <span className="global-context">Projects</span>}
  </header>;
}
