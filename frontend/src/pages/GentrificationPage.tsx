import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { MapContainer, TileLayer, CircleMarker, Popup } from 'react-leaflet'
import { speculationApi, banApi } from '@/utils/api'
import { PriceChart } from '@/components/Charts/PriceChart'
import { formatPct, formatPrixM2 } from '@/utils/format'

const FRANCE_CENTER: [number, number] = [46.8, 2.35]

const STAGE_CONFIG = {
  stable: { color: '#2A9D8F', label: 'Stable', description: 'Marché équilibré, pas de pression spéculative' },
  early: { color: '#E9C46A', label: 'Début', description: 'Premières tensions, vigilance recommandée' },
  active: { color: '#F4A261', label: 'Actif', description: 'Gentrification en cours, hausse significative des prix' },
  advanced: { color: '#E63946', label: 'Avancé', description: 'Gentrification avancée, risque élevé de déplacement' },
  post: { color: '#8B5CF6', label: 'Post-gentrification', description: 'Transformation complète du tissu social' },
}

export function GentrificationPage() {
  const [selectedCommune, setSelectedCommune] = useState<{ code: string; name: string } | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState<any[]>([])
  const [isSearching, setIsSearching] = useState(false)

  const { data: gentrif, isLoading } = useQuery({
    queryKey: ['gentrification-detail', selectedCommune?.code],
    queryFn: async () => {
      const res = await speculationApi.getGentrification({ code_commune: selectedCommune!.code })
      return res.data
    },
    enabled: !!selectedCommune,
    staleTime: 1000 * 60 * 30,
  })

  const handleSearch = async (q: string) => {
    setSearchQuery(q)
    if (q.length < 2) { setSearchResults([]); return }
    setIsSearching(true)
    try {
      const communes = await banApi.searchCommunes(q)
      setSearchResults(communes.slice(0, 8))
    } catch {
      setSearchResults([])
    } finally {
      setIsSearching(false)
    }
  }

  const stage = gentrif?.stage as keyof typeof STAGE_CONFIG | undefined
  const stageConfig = stage ? STAGE_CONFIG[stage] : null

  return (
    <div className="flex h-full gap-4 p-4">
      {/* Left panel */}
      <div className="w-80 shrink-0 flex flex-col gap-4 overflow-y-auto">
        {/* Commune search */}
        <div className="bg-surface-800 rounded-xl p-4 border border-surface-700">
          <h2 className="font-semibold text-sm mb-3 text-slate-200">Analyser une commune</h2>

          <div className="relative">
            <input
              type="text"
              placeholder="Rechercher une commune…"
              value={searchQuery}
              onChange={(e) => handleSearch(e.target.value)}
              className="w-full bg-surface-900 border border-surface-700 rounded-lg px-3 py-2 text-sm text-slate-200 focus:border-primary-500 focus:outline-none"
            />
            {searchResults.length > 0 && (
              <div className="absolute top-full left-0 right-0 z-20 mt-1 bg-surface-900 border border-surface-700 rounded-lg overflow-hidden shadow-xl">
                {searchResults.map((c) => (
                  <button
                    key={c.code}
                    className="w-full text-left px-3 py-2.5 hover:bg-surface-800 transition-colors border-b border-surface-700 last:border-0"
                    onClick={() => {
                      setSelectedCommune({ code: c.code, name: c.nom })
                      setSearchQuery(c.nom)
                      setSearchResults([])
                    }}
                  >
                    <p className="text-sm text-slate-200">{c.nom}</p>
                    <p className="text-xs text-slate-500">
                      {c.departement?.nom} · {c.codesPostaux?.[0]}
                      {c.population && ` · ${c.population.toLocaleString('fr-FR')} hab.`}
                    </p>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Stage guide */}
        <div className="bg-surface-800 rounded-xl p-4 border border-surface-700">
          <h2 className="font-semibold text-sm mb-3 text-slate-200">Stades de gentrification</h2>
          <div className="space-y-2">
            {Object.entries(STAGE_CONFIG).map(([key, config]) => (
              <div key={key} className="flex items-start gap-2.5">
                <div
                  className="w-3 h-3 rounded-full shrink-0 mt-0.5"
                  style={{ background: config.color }}
                />
                <div>
                  <p className="text-xs font-medium text-slate-300">{config.label}</p>
                  <p className="text-xs text-slate-500">{config.description}</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Methodology note */}
        <div className="bg-surface-800 rounded-xl p-4 border border-surface-700">
          <h2 className="font-semibold text-sm mb-2 text-slate-200">Méthodologie</h2>
          <p className="text-xs text-slate-400 leading-relaxed">
            L'indice de gentrification combine l'évolution des prix sur 5 et 10 ans,
            la vitesse de rotation des biens, l'accélération des prix et le volume
            de transactions. Score sur 100 basé sur données DVF.
          </p>
        </div>
      </div>

      {/* Main content */}
      <div className="flex-1 flex flex-col gap-4">
        {!selectedCommune && (
          <div className="flex-1 bg-surface-800 rounded-xl border border-surface-700 flex items-center justify-center">
            <div className="text-center">
              <div className="text-5xl mb-4">🏘</div>
              <p className="text-slate-400 text-sm">Recherchez une commune pour analyser sa gentrification</p>
              <p className="text-xs text-slate-500 mt-2">Basé sur les données DVF depuis 2014</p>
            </div>
          </div>
        )}

        {selectedCommune && (
          <>
            {isLoading && (
              <div className="flex-1 bg-surface-800 rounded-xl border border-surface-700 flex items-center justify-center">
                <p className="text-slate-400 text-sm">Analyse en cours…</p>
              </div>
            )}

            {gentrif && !gentrif.error && stageConfig && (
              <>
                {/* Score cards */}
                <div className="grid grid-cols-4 gap-3">
                  <div className="bg-surface-800 rounded-xl p-4 border border-surface-700 col-span-1">
                    <p className="text-xs text-slate-400 mb-1">Stade</p>
                    <div
                      className="text-lg font-bold"
                      style={{ color: stageConfig.color }}
                    >
                      {stageConfig.label}
                    </div>
                    <p className="text-xs text-slate-500 mt-1">{stageConfig.description}</p>
                  </div>

                  <div className="bg-surface-800 rounded-xl p-4 border border-surface-700">
                    <p className="text-xs text-slate-400 mb-1">Score gentrification</p>
                    <div className="flex items-end gap-1">
                      <span className="text-2xl font-bold text-slate-200">
                        {gentrif.gentrification_score.toFixed(0)}
                      </span>
                      <span className="text-slate-500 mb-1">/100</span>
                    </div>
                    <div className="w-full bg-surface-700 rounded-full h-1.5 mt-2">
                      <div
                        className="h-1.5 rounded-full"
                        style={{ width: `${gentrif.gentrification_score}%`, background: stageConfig.color }}
                      />
                    </div>
                  </div>

                  <div className="bg-surface-800 rounded-xl p-4 border border-surface-700">
                    <p className="text-xs text-slate-400 mb-1">Risque déplacement</p>
                    <div className="flex items-end gap-1">
                      <span className="text-2xl font-bold text-red-400">
                        {gentrif.displacement_risk.toFixed(0)}
                      </span>
                      <span className="text-slate-500 mb-1">/100</span>
                    </div>
                    <div className="w-full bg-surface-700 rounded-full h-1.5 mt-2">
                      <div
                        className="h-1.5 rounded-full bg-red-500"
                        style={{ width: `${gentrif.displacement_risk}%` }}
                      />
                    </div>
                  </div>

                  <div className="bg-surface-800 rounded-xl p-4 border border-surface-700">
                    <p className="text-xs text-slate-400 mb-1">Prix médian actuel</p>
                    <p className="text-xl font-bold text-slate-200">{formatPrixM2(gentrif.prix_actuel_m2)}</p>
                    <p className={`text-xs mt-1 font-medium ${
                      (gentrif.evolution_5ans_pct || 0) > 30 ? 'text-red-400' :
                      (gentrif.evolution_5ans_pct || 0) > 15 ? 'text-orange-400' : 'text-emerald-400'
                    }`}>
                      {formatPct(gentrif.evolution_5ans_pct)} sur 5 ans
                    </p>
                  </div>
                </div>

                {/* Price chart */}
                <div className="bg-surface-800 rounded-xl p-4 border border-surface-700">
                  <h3 className="text-sm font-medium text-slate-200 mb-3">
                    Évolution des prix — {selectedCommune.name}
                  </h3>
                  <PriceChart
                    historical={(gentrif.price_history || []).map((h: any) => ({
                      date: `${h.year}-07-01`,
                      prix_median_m2: h.prix_median_m2,
                      prix_p25_m2: null,
                      prix_p75_m2: null,
                      nb_transactions: h.nb_transactions,
                    }))}
                    height={220}
                  />
                </div>

                {/* Signals */}
                {gentrif.signals?.length > 0 && (
                  <div className="bg-surface-800 rounded-xl p-4 border border-surface-700">
                    <h3 className="text-sm font-medium text-slate-200 mb-3">Signaux détectés</h3>
                    <div className="grid grid-cols-2 gap-2">
                      {gentrif.signals.map((s: any, i: number) => (
                        <div key={i} className="flex items-center gap-3 p-2.5 bg-surface-700/50 rounded-lg">
                          <div
                            className="w-8 h-8 rounded-lg flex items-center justify-center text-sm font-bold shrink-0"
                            style={{ background: stageConfig.color + '20', color: stageConfig.color }}
                          >
                            +{s.weight}
                          </div>
                          <div className="min-w-0">
                            <p className="text-xs font-medium text-slate-300 capitalize">
                              {s.signal.replace(/_/g, ' ')}
                            </p>
                            <p className="text-xs text-slate-500">
                              Valeur: {typeof s.value === 'number' ? s.value.toFixed(1) : s.value}
                            </p>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </>
            )}

            {gentrif?.error && (
              <div className="flex-1 bg-surface-800 rounded-xl border border-surface-700 flex items-center justify-center">
                <div className="text-center">
                  <p className="text-slate-400 text-sm">Données insuffisantes pour cette commune</p>
                  <p className="text-xs text-slate-500 mt-2">Minimum 3 années de données requises</p>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}
