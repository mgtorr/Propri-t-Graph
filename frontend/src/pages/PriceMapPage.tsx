import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { PriceMap, PriceLegend } from '@/components/Map/PriceMap'
import { PriceChart } from '@/components/Charts/PriceChart'
import { usePriceHeatmap, usePriceHistory, usePricePrediction } from '@/hooks/useMapData'
import { priceApi } from '@/utils/api'
import { formatPrixM2, formatPct, formatNumber, getEvolutionColor } from '@/utils/format'
import type { MapFilters } from '@/types'

const DEPARTEMENTS = [
  { code: '75', name: 'Paris (75)' },
  { code: '69', name: 'Rhône (69)' },
  { code: '13', name: 'Bouches-du-Rhône (13)' },
  { code: '33', name: 'Gironde (33)' },
  { code: '31', name: 'Haute-Garonne (31)' },
  { code: '06', name: 'Alpes-Maritimes (06)' },
  { code: '59', name: 'Nord (59)' },
  { code: '67', name: 'Bas-Rhin (67)' },
  { code: '44', name: 'Loire-Atlantique (44)' },
  { code: '34', name: 'Hérault (34)' },
]

export function PriceMapPage() {
  const [filters, setFilters] = useState<MapFilters>({
    departement: '75',
    commune: '',
    typeLocal: 'Appartement',
    year: 2023,
    mode: 'prices',
  })
  const [selectedCommune, setSelectedCommune] = useState<{ code: string; name: string } | null>(null)
  const [showPrediction, setShowPrediction] = useState(false)

  const { data: heatmapData = [], isLoading } = usePriceHeatmap(filters)
  const { data: priceHistory = [] } = usePriceHistory(
    selectedCommune?.code || '',
    filters.typeLocal
  )
  const { data: prediction } = usePricePrediction(
    selectedCommune?.code || '',
    filters.typeLocal,
    showPrediction && !!selectedCommune
  )

  const { data: rankingData } = useQuery({
    queryKey: ['ranking', filters.departement, filters.typeLocal],
    queryFn: async () => {
      const res = await priceApi.getEvolutionRanking({
        code_departement: filters.departement,
        type_local: filters.typeLocal,
        top_n: 10,
      })
      return res.data
    },
    enabled: !!filters.departement,
    staleTime: 1000 * 60 * 30,
  })

  const validData = heatmapData.filter((d: any) => d.prix_median_m2)
  const prices = validData.map((d: any) => d.prix_median_m2)
  const minPrice = prices.length > 0 ? Math.min(...prices) : 0
  const maxPrice = prices.length > 0 ? Math.max(...prices) : 0

  return (
    <div className="flex h-full gap-4 p-4">
      {/* Left panel: filters + stats */}
      <div className="w-80 shrink-0 flex flex-col gap-4 overflow-y-auto">
        {/* Filters */}
        <div className="bg-surface-800 rounded-xl p-4 border border-surface-700">
          <h2 className="font-semibold text-sm mb-3 text-slate-200">Filtres</h2>

          <div className="space-y-3">
            <div>
              <label className="text-xs text-slate-400 mb-1 block">Département</label>
              <select
                className="w-full bg-surface-900 border border-surface-700 rounded-lg px-3 py-2 text-sm text-slate-200 focus:border-primary-500 focus:outline-none"
                value={filters.departement}
                onChange={(e) => setFilters((f) => ({ ...f, departement: e.target.value }))}
              >
                {DEPARTEMENTS.map((d) => (
                  <option key={d.code} value={d.code}>{d.name}</option>
                ))}
              </select>
            </div>

            <div>
              <label className="text-xs text-slate-400 mb-1 block">Type de bien</label>
              <div className="flex gap-2">
                {(['Appartement', 'Maison'] as const).map((type) => (
                  <button
                    key={type}
                    onClick={() => setFilters((f) => ({ ...f, typeLocal: type }))}
                    className={`flex-1 text-xs py-2 rounded-lg border transition-colors ${
                      filters.typeLocal === type
                        ? 'bg-primary-600 border-primary-600 text-white'
                        : 'border-surface-600 text-slate-400 hover:border-slate-500'
                    }`}
                  >
                    {type}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <label className="text-xs text-slate-400 mb-1 block">Année: {filters.year}</label>
              <input
                type="range"
                min={2018}
                max={2023}
                value={filters.year}
                onChange={(e) => setFilters((f) => ({ ...f, year: +e.target.value }))}
                className="w-full accent-primary-500"
              />
              <div className="flex justify-between text-xs text-slate-500 mt-0.5">
                <span>2018</span><span>2023</span>
              </div>
            </div>
          </div>
        </div>

        {/* Summary stats */}
        {heatmapData.length > 0 && (
          <div className="bg-surface-800 rounded-xl p-4 border border-surface-700">
            <h2 className="font-semibold text-sm mb-3 text-slate-200">Résumé {filters.year}</h2>
            <div className="grid grid-cols-2 gap-3">
              <StatCard
                label="Prix min"
                value={formatPrixM2(minPrice)}
                className="text-blue-400"
              />
              <StatCard
                label="Prix max"
                value={formatPrixM2(maxPrice)}
                className="text-red-400"
              />
              <StatCard
                label="Zones analysées"
                value={formatNumber(heatmapData.length)}
              />
              <StatCard
                label="Transactions"
                value={formatNumber(heatmapData.reduce((s: number, d: any) => s + d.nb_transactions, 0))}
              />
            </div>
          </div>
        )}

        {/* Evolution ranking */}
        {rankingData?.top_gainers?.length > 0 && (
          <div className="bg-surface-800 rounded-xl p-4 border border-surface-700">
            <h2 className="font-semibold text-sm mb-3 text-slate-200">Top hausses 1 an</h2>
            <div className="space-y-2">
              {rankingData.top_gainers.slice(0, 5).map((item: any) => (
                <div
                  key={item.code_commune}
                  className="flex items-center justify-between py-1.5 px-2 rounded hover:bg-surface-700 cursor-pointer transition-colors"
                  onClick={() => setSelectedCommune({ code: item.code_commune, name: item.commune })}
                >
                  <span className="text-xs text-slate-300 truncate">{item.commune}</span>
                  <span className={`text-xs font-medium ${getEvolutionColor(item.evolution_1an_pct)}`}>
                    {formatPct(item.evolution_1an_pct)}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Selected commune panel */}
        {selectedCommune && (
          <div className="bg-surface-800 rounded-xl p-4 border border-primary-600/30">
            <div className="flex items-center justify-between mb-3">
              <h2 className="font-semibold text-sm text-slate-200">{selectedCommune.name}</h2>
              <button
                onClick={() => setSelectedCommune(null)}
                className="text-slate-500 hover:text-slate-300 text-sm"
              >
                ✕
              </button>
            </div>

            {priceHistory.length > 0 && (
              <PriceChart
                historical={priceHistory}
                forecast={prediction?.forecast}
                height={200}
              />
            )}

            <button
              onClick={() => setShowPrediction(!showPrediction)}
              className="mt-3 w-full text-xs bg-primary-600/20 hover:bg-primary-600/30 text-primary-300 border border-primary-600/30 py-2 px-3 rounded-lg transition-colors"
            >
              {showPrediction ? 'Masquer' : 'Afficher'} prévision 12 mois
            </button>

            {prediction?.evolution_prevue_pct != null && (
              <div className="mt-2 p-2 bg-surface-700 rounded-lg">
                <p className="text-xs text-slate-400">Évolution prévue (+12 mois)</p>
                <p className={`text-lg font-bold ${getEvolutionColor(prediction.evolution_prevue_pct)}`}>
                  {formatPct(prediction.evolution_prevue_pct)}
                </p>
                <p className="text-xs text-slate-500 mt-0.5">Modèle: {prediction.model}</p>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Map */}
      <div className="flex-1 relative rounded-xl overflow-hidden">
        {isLoading && (
          <div className="absolute inset-0 z-10 flex items-center justify-center bg-surface-900/70 rounded-xl">
            <div className="text-slate-400 text-sm">Chargement des données…</div>
          </div>
        )}
        <PriceMap
          data={heatmapData}
          onCommuneClick={(code, name) => setSelectedCommune({ code, name })}
        />
        <PriceLegend min={minPrice} max={maxPrice} />
      </div>
    </div>
  )
}

function StatCard({ label, value, className = '' }: { label: string; value: string; className?: string }) {
  return (
    <div className="bg-surface-700/50 rounded-lg p-2.5">
      <p className="text-xs text-slate-500">{label}</p>
      <p className={`text-sm font-semibold mt-0.5 ${className || 'text-slate-200'}`}>{value}</p>
    </div>
  )
}
