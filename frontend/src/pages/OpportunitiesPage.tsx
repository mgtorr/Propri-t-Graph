import { useState } from 'react'
import { MapContainer, TileLayer, CircleMarker, Popup } from 'react-leaflet'
import { useOpportunities } from '@/hooks/useMapData'
import { opportunityApi } from '@/utils/api'
import { useQuery } from '@tanstack/react-query'
import { formatEuro, formatPrixM2, formatNumber } from '@/utils/format'
import type { Opportunity, BudgetSimulation } from '@/types'

const FRANCE_CENTER: [number, number] = [46.8, 2.35]

const PTZ_ZONE_COLORS: Record<string, string> = {
  A: '#E63946',
  Abis: '#E63946',
  B1: '#F4A261',
  B2: '#E9C46A',
  C: '#2A9D8F',
}

export function OpportunitiesPage() {
  const [mode, setMode] = useState<'budget' | 'simulation'>('budget')
  const [params, setParams] = useState({
    max_budget: 250000,
    surface_min: 45,
    type_local: 'Appartement',
    departements: '',
  })
  const [simulation, setSimulation] = useState({
    salaire_mensuel_net: 3000,
    apport: 20000,
    duree_ans: 25,
    taux_interet: 0.038,
  })
  const [selectedOpportunity, setSelectedOpportunity] = useState<Opportunity | null>(null)

  const opportunitiesQuery = useOpportunities(
    mode === 'budget' ? params : { max_budget: 0, surface_min: params.surface_min, type_local: params.type_local }
  )

  const simulationQuery = useQuery({
    queryKey: ['simulation', simulation, params.type_local],
    queryFn: async () => {
      const res = await opportunityApi.simulate({
        ...simulation,
        departements: params.departements || undefined,
      })
      return res.data as BudgetSimulation
    },
    enabled: mode === 'simulation',
    staleTime: 1000 * 60 * 10,
  })

  const data = mode === 'budget'
    ? opportunitiesQuery.data
    : simulationQuery.data

  const opportunities: Opportunity[] = data?.opportunities || []
  const summary = data?.summary
  const simResult = mode === 'simulation' ? simulationQuery.data?.simulation : null

  const validOpps = opportunities.filter((o) => o.lat && o.lng)

  return (
    <div className="flex h-full gap-4 p-4">
      {/* Left panel */}
      <div className="w-80 shrink-0 flex flex-col gap-4 overflow-y-auto">
        {/* Mode selector */}
        <div className="bg-surface-800 rounded-xl p-4 border border-surface-700">
          <div className="flex gap-2 mb-4">
            <button
              onClick={() => setMode('budget')}
              className={`flex-1 text-xs py-2 rounded-lg border transition-colors ${
                mode === 'budget'
                  ? 'bg-opportunity/20 border-opportunity/50 text-emerald-300'
                  : 'border-surface-600 text-slate-400'
              }`}
            >
              Budget fixe
            </button>
            <button
              onClick={() => setMode('simulation')}
              className={`flex-1 text-xs py-2 rounded-lg border transition-colors ${
                mode === 'simulation'
                  ? 'bg-opportunity/20 border-opportunity/50 text-emerald-300'
                  : 'border-surface-600 text-slate-400'
              }`}
            >
              Simuler capacité
            </button>
          </div>

          {mode === 'budget' && (
            <div className="space-y-3">
              <div>
                <label className="text-xs text-slate-400 mb-1 block">
                  Budget max: {formatEuro(params.max_budget)}
                </label>
                <input
                  type="range"
                  min={80000}
                  max={800000}
                  step={5000}
                  value={params.max_budget}
                  onChange={(e) => setParams((p) => ({ ...p, max_budget: +e.target.value }))}
                  className="w-full accent-emerald-500"
                />
                <div className="flex justify-between text-xs text-slate-500">
                  <span>80k€</span><span>800k€</span>
                </div>
              </div>

              <div>
                <label className="text-xs text-slate-400 mb-1 block">
                  Surface min: {params.surface_min} m²
                </label>
                <input
                  type="range"
                  min={20}
                  max={150}
                  value={params.surface_min}
                  onChange={(e) => setParams((p) => ({ ...p, surface_min: +e.target.value }))}
                  className="w-full accent-emerald-500"
                />
              </div>

              <div>
                <label className="text-xs text-slate-400 mb-1 block">Type de bien</label>
                <div className="flex gap-2">
                  {(['Appartement', 'Maison'] as const).map((t) => (
                    <button
                      key={t}
                      onClick={() => setParams((p) => ({ ...p, type_local: t }))}
                      className={`flex-1 text-xs py-2 rounded-lg border transition-colors ${
                        params.type_local === t
                          ? 'bg-emerald-600/20 border-emerald-600/50 text-emerald-300'
                          : 'border-surface-600 text-slate-400'
                      }`}
                    >
                      {t}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}

          {mode === 'simulation' && (
            <div className="space-y-3">
              <div>
                <label className="text-xs text-slate-400 mb-1 block">
                  Salaire net mensuel: {formatEuro(simulation.salaire_mensuel_net)}
                </label>
                <input
                  type="range"
                  min={1500}
                  max={10000}
                  step={100}
                  value={simulation.salaire_mensuel_net}
                  onChange={(e) => setSimulation((s) => ({ ...s, salaire_mensuel_net: +e.target.value }))}
                  className="w-full accent-emerald-500"
                />
              </div>

              <div>
                <label className="text-xs text-slate-400 mb-1 block">
                  Apport: {formatEuro(simulation.apport)}
                </label>
                <input
                  type="range"
                  min={0}
                  max={200000}
                  step={1000}
                  value={simulation.apport}
                  onChange={(e) => setSimulation((s) => ({ ...s, apport: +e.target.value }))}
                  className="w-full accent-emerald-500"
                />
              </div>

              <div>
                <label className="text-xs text-slate-400 mb-1 block">
                  Durée: {simulation.duree_ans} ans
                </label>
                <input
                  type="range"
                  min={10}
                  max={30}
                  value={simulation.duree_ans}
                  onChange={(e) => setSimulation((s) => ({ ...s, duree_ans: +e.target.value }))}
                  className="w-full accent-emerald-500"
                />
              </div>

              <div>
                <label className="text-xs text-slate-400 mb-1 block">
                  Taux d'intérêt: {(simulation.taux_interet * 100).toFixed(1)} %
                </label>
                <input
                  type="range"
                  min={0.015}
                  max={0.08}
                  step={0.001}
                  value={simulation.taux_interet}
                  onChange={(e) => setSimulation((s) => ({ ...s, taux_interet: +e.target.value }))}
                  className="w-full accent-emerald-500"
                />
              </div>
            </div>
          )}
        </div>

        {/* Simulation results */}
        {simResult && (
          <div className="bg-surface-800 rounded-xl p-4 border border-emerald-600/30">
            <h2 className="font-semibold text-sm mb-3 text-slate-200">Capacité d'emprunt</h2>
            <div className="grid grid-cols-2 gap-2">
              <div className="bg-surface-700/50 rounded-lg p-2.5">
                <p className="text-xs text-slate-500">Mensualité max</p>
                <p className="text-sm font-bold text-emerald-400">{formatEuro(simResult.mensualite_max)}</p>
              </div>
              <div className="bg-surface-700/50 rounded-lg p-2.5">
                <p className="text-xs text-slate-500">Capacité emprunt</p>
                <p className="text-sm font-bold text-emerald-400">{formatEuro(simResult.capacite_emprunt)}</p>
              </div>
              <div className="bg-surface-700/50 rounded-lg p-2.5 col-span-2">
                <p className="text-xs text-slate-500">Budget bien net (hors frais notaire)</p>
                <p className="text-lg font-bold text-emerald-300">{formatEuro(simResult.budget_bien_net)}</p>
              </div>
              <div className="bg-surface-700/50 rounded-lg p-2.5 col-span-2">
                <p className="text-xs text-slate-500">Frais de notaire estimés</p>
                <p className="text-sm font-medium text-slate-300">{formatEuro(simResult.frais_notaire_estimes)}</p>
              </div>
            </div>
            <p className="text-xs text-slate-500 mt-2">
              Taux d'endettement max: {simResult.taux_endettement_pct} % (norme bancaire française)
            </p>
          </div>
        )}

        {/* Opportunities list */}
        {opportunities.length > 0 && (
          <div className="bg-surface-800 rounded-xl p-4 border border-surface-700">
            <h2 className="font-semibold text-sm mb-3 text-slate-200">
              {opportunities.length} opportunités trouvées
            </h2>
            <div className="space-y-2 max-h-80 overflow-y-auto">
              {opportunities.map((opp) => (
                <div
                  key={opp.code_commune}
                  onClick={() => setSelectedOpportunity(opp)}
                  className={`p-3 rounded-lg border cursor-pointer transition-colors ${
                    selectedOpportunity?.code_commune === opp.code_commune
                      ? 'border-emerald-600/50 bg-emerald-600/10'
                      : 'border-surface-600 hover:border-surface-500 hover:bg-surface-700'
                  }`}
                >
                  <div className="flex items-start justify-between">
                    <div className="min-w-0">
                      <p className="text-xs font-medium text-slate-200 truncate">{opp.commune}</p>
                      <p className="text-xs text-slate-500">{opp.code_departement} · Zone PTZ {opp.zone_ptz}</p>
                    </div>
                    <div className="text-right ml-2 shrink-0">
                      <p className="text-sm font-bold text-emerald-400">{opp.score_opportunite}/100</p>
                      <p className="text-xs text-slate-500">{formatPrixM2(opp.prix_median_m2)}</p>
                    </div>
                  </div>
                  {opp.eligible_ptz && (
                    <span className="mt-1 inline-block text-xs bg-emerald-500/15 text-emerald-400 px-1.5 py-0.5 rounded">
                      PTZ éligible
                    </span>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Map */}
      <div className="flex-1 relative rounded-xl overflow-hidden">
        <MapContainer
          center={FRANCE_CENTER}
          zoom={6}
          className="w-full h-full"
          style={{ background: '#0F172A' }}
        >
          <TileLayer
            url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
            attribution='&copy; OpenStreetMap &copy; CARTO'
            maxZoom={19}
          />

          {validOpps.map((opp) => (
            <CircleMarker
              key={opp.code_commune}
              center={[opp.lat!, opp.lng!]}
              radius={6 + opp.score_opportunite / 15}
              pathOptions={{
                fillColor: '#2A9D8F',
                fillOpacity: 0.5 + opp.score_opportunite / 200,
                color: selectedOpportunity?.code_commune === opp.code_commune ? '#fff' : 'transparent',
                weight: 2,
              }}
              eventHandlers={{ click: () => setSelectedOpportunity(opp) }}
            >
              <Popup>
                <div className="p-2 min-w-[180px]">
                  <p className="font-semibold text-sm">{opp.commune}</p>
                  <p className="text-xs text-slate-500 mb-2">{opp.code_departement}</p>
                  <div className="space-y-1 text-xs">
                    <div className="flex justify-between">
                      <span>Score</span>
                      <span className="font-bold text-emerald-600">{opp.score_opportunite}/100</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Prix médian</span>
                      <span>{formatPrixM2(opp.prix_median_m2)}</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Zone PTZ</span>
                      <span style={{ color: PTZ_ZONE_COLORS[opp.zone_ptz] || '#64748B' }}>
                        {opp.zone_ptz} {opp.eligible_ptz ? '✓' : ''}
                      </span>
                    </div>
                  </div>
                </div>
              </Popup>
            </CircleMarker>
          ))}
        </MapContainer>

        {/* PTZ legend */}
        <div className="absolute bottom-4 right-4 z-[1000] bg-surface-900/90 backdrop-blur rounded-xl p-3 border border-surface-700 text-xs">
          <p className="font-medium mb-2 text-slate-300">Zones PTZ</p>
          {Object.entries(PTZ_ZONE_COLORS).map(([zone, color]) => (
            <div key={zone} className="flex items-center gap-2 mb-1">
              <div className="w-3 h-3 rounded-full" style={{ background: color }} />
              <span className="text-slate-400">Zone {zone}</span>
            </div>
          ))}
        </div>

        {/* Summary overlay */}
        {summary && (
          <div className="absolute top-4 left-4 z-[1000] bg-surface-900/90 backdrop-blur rounded-xl p-3 border border-surface-700 text-xs">
            <p className="text-slate-300 font-medium">{summary.nb_opportunites} opportunités</p>
            {summary.prix_min && summary.prix_max && (
              <p className="text-slate-400 mt-1">
                {formatPrixM2(summary.prix_min)} – {formatPrixM2(summary.prix_max)}
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
