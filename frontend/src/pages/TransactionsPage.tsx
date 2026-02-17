import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { propertiesApi } from '@/utils/api'
import { formatEuro, formatPrixM2, formatSurface, formatDate } from '@/utils/format'

export function TransactionsPage() {
  const [filters, setFilters] = useState({
    code_commune: '',
    code_departement: '75',
    type_local: '',
    year: '',
    page: 1,
  })

  const { data, isLoading } = useQuery({
    queryKey: ['transactions', filters],
    queryFn: async () => {
      const res = await propertiesApi.getTransactions({
        ...filters,
        code_commune: filters.code_commune || undefined,
        type_local: filters.type_local || undefined,
        year: filters.year ? +filters.year : undefined,
        page_size: 50,
      } as any)
      return res.data
    },
    staleTime: 1000 * 60 * 5,
  })

  const transactions = data?.transactions || []
  const total = data?.total || 0
  const pages = data?.pages || 0

  return (
    <div className="flex flex-col h-full p-4 gap-4">
      {/* Filters bar */}
      <div className="bg-surface-800 rounded-xl p-4 border border-surface-700">
        <div className="flex flex-wrap gap-3 items-end">
          <div>
            <label className="text-xs text-slate-400 mb-1 block">Département</label>
            <input
              type="text"
              placeholder="ex: 75"
              value={filters.code_departement}
              onChange={(e) => setFilters((f) => ({ ...f, code_departement: e.target.value, page: 1 }))}
              className="bg-surface-900 border border-surface-700 rounded-lg px-3 py-2 text-sm text-slate-200 w-24 focus:border-primary-500 focus:outline-none"
            />
          </div>
          <div>
            <label className="text-xs text-slate-400 mb-1 block">Commune INSEE</label>
            <input
              type="text"
              placeholder="ex: 75056"
              value={filters.code_commune}
              onChange={(e) => setFilters((f) => ({ ...f, code_commune: e.target.value, page: 1 }))}
              className="bg-surface-900 border border-surface-700 rounded-lg px-3 py-2 text-sm text-slate-200 w-28 focus:border-primary-500 focus:outline-none"
            />
          </div>
          <div>
            <label className="text-xs text-slate-400 mb-1 block">Type de bien</label>
            <select
              value={filters.type_local}
              onChange={(e) => setFilters((f) => ({ ...f, type_local: e.target.value, page: 1 }))}
              className="bg-surface-900 border border-surface-700 rounded-lg px-3 py-2 text-sm text-slate-200 focus:border-primary-500 focus:outline-none"
            >
              <option value="">Tous</option>
              <option value="Appartement">Appartement</option>
              <option value="Maison">Maison</option>
              <option value="Local industriel">Local industriel</option>
              <option value="Dépendance">Dépendance</option>
            </select>
          </div>
          <div>
            <label className="text-xs text-slate-400 mb-1 block">Année</label>
            <select
              value={filters.year}
              onChange={(e) => setFilters((f) => ({ ...f, year: e.target.value, page: 1 }))}
              className="bg-surface-900 border border-surface-700 rounded-lg px-3 py-2 text-sm text-slate-200 focus:border-primary-500 focus:outline-none"
            >
              <option value="">Toutes</option>
              {[2023, 2022, 2021, 2020, 2019, 2018].map((y) => (
                <option key={y} value={y}>{y}</option>
              ))}
            </select>
          </div>
          <div className="ml-auto text-xs text-slate-400">
            {total.toLocaleString('fr-FR')} résultats
          </div>
        </div>
      </div>

      {/* Table */}
      <div className="flex-1 bg-surface-800 rounded-xl border border-surface-700 overflow-hidden flex flex-col">
        <div className="overflow-auto flex-1">
          <table className="w-full text-xs">
            <thead className="sticky top-0 bg-surface-900 border-b border-surface-700">
              <tr>
                {['Date', 'Type', 'Adresse', 'Commune', 'Prix', 'Surface', 'Prix/m²', 'Nature'].map((h) => (
                  <th key={h} className="text-left px-4 py-3 text-slate-400 font-medium whitespace-nowrap">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {isLoading && (
                <tr>
                  <td colSpan={8} className="text-center py-8 text-slate-400">
                    Chargement…
                  </td>
                </tr>
              )}
              {!isLoading && transactions.length === 0 && (
                <tr>
                  <td colSpan={8} className="text-center py-8 text-slate-400">
                    Aucune transaction trouvée
                  </td>
                </tr>
              )}
              {transactions.map((tx: any) => (
                <tr
                  key={tx.mutation_id}
                  className="border-b border-surface-700/50 hover:bg-surface-700/30 transition-colors"
                >
                  <td className="px-4 py-2.5 text-slate-400 whitespace-nowrap">{formatDate(tx.date_mutation)}</td>
                  <td className="px-4 py-2.5 whitespace-nowrap">
                    <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-surface-700 text-slate-300">
                      {tx.type_local || '—'}
                    </span>
                  </td>
                  <td className="px-4 py-2.5 text-slate-300 max-w-[200px] truncate">{tx.adresse || '—'}</td>
                  <td className="px-4 py-2.5 text-slate-400 whitespace-nowrap">{tx.commune}</td>
                  <td className="px-4 py-2.5 font-medium text-slate-200 whitespace-nowrap">
                    {formatEuro(tx.valeur_fonciere)}
                  </td>
                  <td className="px-4 py-2.5 text-slate-400 whitespace-nowrap">{formatSurface(tx.surface_m2)}</td>
                  <td className="px-4 py-2.5 text-slate-300 whitespace-nowrap">{formatPrixM2(tx.prix_m2)}</td>
                  <td className="px-4 py-2.5 text-slate-400">{tx.nature_mutation}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {pages > 1 && (
          <div className="border-t border-surface-700 px-4 py-3 flex items-center justify-between">
            <p className="text-xs text-slate-400">
              Page {filters.page} / {pages}
            </p>
            <div className="flex gap-2">
              <button
                disabled={filters.page <= 1}
                onClick={() => setFilters((f) => ({ ...f, page: f.page - 1 }))}
                className="px-3 py-1.5 text-xs rounded-lg border border-surface-600 text-slate-400 hover:border-slate-500 disabled:opacity-40 disabled:cursor-not-allowed"
              >
                ← Précédent
              </button>
              <button
                disabled={filters.page >= pages}
                onClick={() => setFilters((f) => ({ ...f, page: f.page + 1 }))}
                className="px-3 py-1.5 text-xs rounded-lg border border-surface-600 text-slate-400 hover:border-slate-500 disabled:opacity-40 disabled:cursor-not-allowed"
              >
                Suivant →
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
