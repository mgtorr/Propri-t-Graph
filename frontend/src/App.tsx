import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Toaster } from 'react-hot-toast'
import { Sidebar } from '@/components/Layout/Sidebar'
import { PriceMapPage } from '@/pages/PriceMapPage'
import { SpeculationPage } from '@/pages/SpeculationPage'
import { GentrificationPage } from '@/pages/GentrificationPage'
import { OwnershipPage } from '@/pages/OwnershipPage'
import { OpportunitiesPage } from '@/pages/OpportunitiesPage'
import { TransactionsPage } from '@/pages/TransactionsPage'
import 'leaflet/dist/leaflet.css'

// Fix Leaflet default marker icons in Vite
import L from 'leaflet'
import markerIcon2x from 'leaflet/dist/images/marker-icon-2x.png'
import markerIcon from 'leaflet/dist/images/marker-icon.png'
import markerShadow from 'leaflet/dist/images/marker-shadow.png'

delete (L.Icon.Default.prototype as any)._getIconUrl
L.Icon.Default.mergeOptions({
  iconUrl: markerIcon,
  iconRetinaUrl: markerIcon2x,
  shadowUrl: markerShadow,
})

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
})

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <div className="flex h-screen bg-surface-900 text-slate-100 font-sans overflow-hidden">
          <Sidebar />
          <main className="flex-1 overflow-hidden">
            <Routes>
              <Route path="/" element={<PriceMapPage />} />
              <Route path="/speculation" element={<SpeculationPage />} />
              <Route path="/gentrification" element={<GentrificationPage />} />
              <Route path="/ownership" element={<OwnershipPage />} />
              <Route path="/opportunities" element={<OpportunitiesPage />} />
              <Route path="/transactions" element={<TransactionsPage />} />
            </Routes>
          </main>
        </div>
        <Toaster
          position="bottom-right"
          toastOptions={{
            style: {
              background: '#1E293B',
              color: '#E2E8F0',
              border: '1px solid #334155',
            },
          }}
        />
      </BrowserRouter>
    </QueryClientProvider>
  )
}
