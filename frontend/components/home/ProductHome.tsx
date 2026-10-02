import { ArrowRight, GitBranch, ScanSearch, ShieldCheck } from 'lucide-react';

export function ProductHome() {
  return <div className="product-home">
    <header className="home-header"><a className="brand" href="/" aria-label="Verisys home"><GitBranch size={25} className="brand-mark"/>verisys</a><a className="home-workspace-link" href="/projects">Projects <ArrowRight size={16}/></a></header>
    <main>
      <section className="home-hero" aria-labelledby="home-title">
        <p className="home-eyebrow">ARCHITECTURE-AWARE ENGINEERING VERIFICATION</p>
        <h1 id="home-title">Understand your system.<br/><span>Verify with evidence.</span></h1>
        <p className="home-description">Verisys reads your repository to understand its architecture, identify engineering properties worth checking, and turn supported checks into source-backed results.</p>
        <a className="primary-button home-cta" href="/projects">Enter Projects <ArrowRight size={18}/></a>
        <p className="home-caption">Start with a public GitHub Python repository.</p>
      </section>
      <section className="home-process" aria-labelledby="home-process-title">
        <div className="home-section-heading"><p className="home-eyebrow">FROM SOURCE TO CONFIDENCE</p><h2 id="home-process-title">Architecture is the starting point.<br/>Evidence is the result.</h2></div>
        <div className="home-steps">
          <article><span className="home-step-number">01</span><GitBranch size={22}/><h3>Understand the system</h3><p>Inspect source safely. Explore detected components, dependencies, and source-declared execution flows.</p></article>
          <article><span className="home-step-number">02</span><ScanSearch size={22}/><h3>Find what to verify</h3><p>Discover architecture-grounded checks proactively, or focus on a specific engineering concern.</p></article>
          <article><span className="home-step-number">03</span><ShieldCheck size={22}/><h3>Inspect real evidence</h3><p>Run an available verifier and inspect its source evidence, limitations, and deterministic judgment.</p></article>
        </div>
      </section>
      <section className="home-scope" aria-labelledby="home-scope-title"><div><p className="home-eyebrow">AVAILABLE TODAY</p><h2 id="home-scope-title">A focused engineering workspace.</h2></div><div><p>Analyze public GitHub Python repositories, explore their architecture, and discover suggested verifications.</p><p>Explicit per-call timeout coverage for supported direct OpenAI calls is the current executable static check. Other checks remain suggestions; diagrams describe possible flow, not observed runtime behavior.</p></div></section>
    </main>
    <footer className="home-footer"><span>Verisys</span><p>Engineering verification, grounded in your code.</p></footer>
  </div>;
}
