import ObligationsPage from './pages/ObligationsPage'
import './App.css'

function App() {
  return (
    <div className="app">
      <header className="app-header">
        <div className="header-inner">
          <div className="brand">
            <span className="brand-name">PUFI</span>
            <span className="brand-sub">Enterprise Payment Coordination</span>
          </div>
          <div className="header-badges">
            <span className="badge badge-sandbox">PayPal Sandbox</span>
            <span className="badge badge-demo">Demo Build</span>
          </div>
        </div>
      </header>

      <nav className="app-nav">
        <a href="#obligations" className="nav-link active">Obligations</a>
        <a href="#batches" className="nav-link disabled" aria-disabled="true">Batches (Day 2)</a>
        <a href="#analysis" className="nav-link disabled" aria-disabled="true">Analysis (Day 3)</a>
        <a href="#audit" className="nav-link disabled" aria-disabled="true">Audit (Day 5)</a>
      </nav>

      <main className="app-main">
        <ObligationsPage />
      </main>

      <footer className="app-footer">
        <p>
          PUFI is a hackathon prototype. Not a bank, wallet, or payment rail.&nbsp;
          All data is synthetic. PayPal Sandbox only.
        </p>
      </footer>
    </div>
  )
}

export default App
