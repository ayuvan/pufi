import { useState, useEffect } from 'react'
import { PayPalScriptProvider } from '@paypal/react-paypal-js'
import { MainLayout } from './components/layout/MainLayout'
import type { NavPage } from './components/layout/AppSidebar'

import { OverviewPage } from './pages/OverviewPage'
import ObligationsPage from './pages/ObligationsPage'
import ImportPage from './pages/ImportPage'
import BatchesPage from './pages/BatchesPage'
import BatchDetailPage from './pages/BatchDetailPage'
import AnalysisPage from './pages/AnalysisPage'
import AuditPage from './pages/AuditPage'
import EcosystemPage from './pages/EcosystemPage'
import SettingsPage from './pages/SettingsPage'

export default function App() {
  const [currentPage, setCurrentPage] = useState<NavPage>('overview')
  const [batchDetailId, setBatchDetailId] = useState<string | null>(null)

  // Synchronize hash routing
  useEffect(() => {
    function onHashChange() {
      const hash = window.location.hash.replace('#', '').trim()

      if (hash.startsWith('batch/')) {
        const id = hash.slice('batch/'.length)
        setBatchDetailId(id)
        setCurrentPage('batches')
        return
      }

      const validPages: NavPage[] = [
        'overview',
        'obligations',
        'import',
        'batches',
        'analysis',
        'audit',
        'ecosystem',
        'settings',
      ]

      if (validPages.includes(hash as NavPage)) {
        setCurrentPage(hash as NavPage)
        setBatchDetailId(null)
      } else if (!hash) {
        // Default entry point
        setCurrentPage('overview')
        setBatchDetailId(null)
      }
    }

    window.addEventListener('hashchange', onHashChange)
    onHashChange()
    return () => window.removeEventListener('hashchange', onHashChange)
  }, [])

  function navigate(page: NavPage | string) {
    window.location.hash = page
    setCurrentPage(page as NavPage)
    setBatchDetailId(null)
  }

  function openBatchDetail(id: string) {
    window.location.hash = `batch/${id}`
    setBatchDetailId(id)
    setCurrentPage('batches')
  }

  return (
    <PayPalScriptProvider options={{ clientId: 'test', currency: 'USD' }}>
      <MainLayout
        currentPage={currentPage}
        onNavigate={navigate}
        onOpenSponsors={() => navigate('ecosystem')}
      >
        {currentPage === 'overview' && (
          <OverviewPage onNavigate={navigate} onOpenBatchDetail={openBatchDetail} />
        )}

        {currentPage === 'obligations' && <ObligationsPage />}

        {currentPage === 'import' && <ImportPage />}

        {currentPage === 'batches' && !batchDetailId && (
          <BatchesPage onOpenBatchDetail={openBatchDetail} />
        )}

        {currentPage === 'batches' && batchDetailId && (
          <BatchDetailPage
            batchId={batchDetailId}
            onBack={() => {
              setBatchDetailId(null)
              window.location.hash = 'batches'
            }}
          />
        )}

        {currentPage === 'analysis' && <AnalysisPage />}

        {currentPage === 'audit' && <AuditPage />}

        {currentPage === 'ecosystem' && <EcosystemPage />}

        {currentPage === 'settings' && <SettingsPage />}
      </MainLayout>
    </PayPalScriptProvider>
  )
}
