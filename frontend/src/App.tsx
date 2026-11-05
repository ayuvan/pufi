import { useState, useEffect } from 'react'
import ObligationsPage from './pages/ObligationsPage'
import ImportPage from './pages/ImportPage'
import BatchesPage from './pages/BatchesPage'
import AnalysisPage from './pages/AnalysisPage'
import './App.css'

type Page = 'obligations' | 'import' | 'batches' | 'analysis'

function App() {
  const [page, setPage] = useState<Page>('obligations')

  // Simple hash-based navigation so each page is bookmarkable
  useEffect(() => {
    function onHashChange() {
      const hash = window.location.hash.replace('#', '') as Page
      if (['obligations', 'import', 'batches', 'analysis'].includes(hash)) {
        setPage(hash)
      }
    }
    window.addEventListener('hashchange', onHashChange)
    onHashChange()
    return () => window.removeEventListener('hashchange', onHashChange)
  }, [])

  function navigate(p: Page) {
    window.location.hash = p
    setPage(p)
  }

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
        <button
          className={`nav-link ${page === 'obligations' ? 'active' : ''}`}
          onClick={() => navigate('obligations')}
        >
          Obligations
        </button>
        <button
          className={`nav-link ${page === 'import' ? 'active' : ''}`}
          onClick={() => navigate('import')}
        >
          Import
        </button>
        <button
          className={`nav-link ${page === 'batches' ? 'active' : ''}`}
          onClick={() => navigate('batches')}
        >
          Batches
        </button>
        <button
          className={`nav-link ${page === 'analysis' ? 'active' : ''}`}
          onClick={() => navigate('analysis')}
        >
          Analysis
        </button>
        <button className="nav-link disabled" aria-disabled="true" disabled>
          Audit (Day 5)
        </button>
      </nav>

      <main className="app-main">
        {page === 'obligations' && <ObligationsPage />}
        {page === 'import' && <ImportPage />}
        {page === 'batches' && <BatchesPage />}
        {page === 'analysis' && <AnalysisPage />}
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
