import "./styles.css";

const navItems = ["Home", "Sources", "Review", "Transactions", "Reports", "Settings"];

export function App() {
  return (
    <div className="app-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">Family financial operating system</p>
          <h1>Dillon Finances</h1>
        </div>
        <div className="status-strip" aria-label="Runtime status">
          <span>Data: Local only</span>
          <span>Last refresh: Not run</span>
          <span>Close: Not started</span>
        </div>
      </header>

      <div className="workspace">
        <nav className="sidebar" aria-label="Primary">
          {navItems.map((item) => (
            <a key={item} href={`#${item.toLowerCase().replaceAll(" ", "-")}`}>
              {item}
            </a>
          ))}
        </nav>

        <main className="content">
          <section className="status-panel" aria-labelledby="current-status">
            <div>
              <p className="eyebrow">Current status</p>
              <h2 id="current-status">Ready for scaffold verification</h2>
            </div>
            <p>
              App implementation has started with the local Docker shell only. Financial workflows remain
              gated behind later milestone PRs.
            </p>
          </section>

          <section className="grid" aria-label="Operator overview">
            <div>
              <h3>Data boundary</h3>
              <p>Runtime data must stay in DATA_ROOT outside git.</p>
            </div>
            <div>
              <h3>Validation</h3>
              <p>No imports have run. Synthetic tests drive the first milestone.</p>
            </div>
            <div>
              <h3>Next action</h3>
              <p>Complete scaffold, Docker, and repository safety checks.</p>
            </div>
          </section>
        </main>
      </div>
    </div>
  );
}
