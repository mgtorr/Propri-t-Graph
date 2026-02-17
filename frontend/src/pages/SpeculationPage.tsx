import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { MapContainer, TileLayer, CircleMarker, Popup } from 'react-leaflet'
import { speculationApi } from '@/utils/api'
import { PriceChart } from '@/components/Charts/PriceChart'
import { formatEuro, formatPct, formatNumber } from '@/utils/format'

const FRANCE_CENTER: [number, number] = [46.8, 2.35]

const DEPARTEMENTS = [
  { code: '75', name: 'Paris (75)' },
  { code: '69', name: 'Rhône (69)' },
  { code: '13', name: 'Bouches-du-Rhône (13)' },
  { code: '33', name: 'Gironde (33)' },
  { code: '31', name: 'Haute-Garonne (31)' },
  { code: '06', name: 'Alpes-Maritimes (06)' },
  { code: '59', name: 'Nord (59)' },
]

type ViewMode = 'heatmap' | 'flips' | 'acquisitions'

export function SpeculationPage() {
  const [departement, setDepartement] = useState('75')
  const [viewMode, setViewMode] = useState<ViewMode>('heatmap')
  const [selectedCommune, setSelectedCommune] = useState<string | null>(null)
  const [flipParams, setFlipParams] = useState({ min_gain_pct: 20, max_hold_months: 24 })

  const heatmapQuery = useQuery({
    queryKey: ['speculation-heatmap', departement],
    queryFn: async () => {
      const res = await speculationApi.getHeatmap({ code_departement: departement })
      return res.data.heatmap
    },
    enabled: viewMode === 'heatmap',
    staleTime: 1000 * 60 * 30,
  })

  const flipsQuery = useQuery({
    queryKey: ['rapid-flips', departement, flipParams],
    queryFn: async () => {
      const res = await speculationApi.getRapidFlips({
        code_departement: departement,
        ...flipParams,
      })
      return res.data
    },
    enabled: viewMode === 'flips',
    staleTime: 1000 * 60 * 10,
  })

  const gentrificationQuery = useQuery({
    queryKey: ['gentrification', selectedCommune],
    queryFn: async () => {
      const res = await speculationApi.getGentrification({ code_commune: selectedCommune! })
      return res.data
    },
    enabled: !!selectedCommune,
    staleTime: 1000 * 60 * 30,
  })

  const heatmap = heatmapQuery.data || []
  const flips = flipsQuery.data?.flips || []
  const gentrif = gentrificationQuery.data

  const SEVERITY_COLORS = { critical: '#E63946', high: '#F4A261', medium: '#E9C46A', low: '#2A9D8F' }
  const STAGE_COLORS = { advanced: '#E63946', active: '#F4A261', early: '#E9C46A', stable: '#2A9D8F' }

  return (
    <div className="flex h-full gap-4 p-4">
      {/* Left panel */}
      <div className="w-80 shrink-0 flex flex-col gap-4 overflow-y-auto">
        {/* Controls */}
        <div className="bg-surface-800 rounded-xl p-4 border border-surface-700">
          <h2 className="font-semibold text-sm mb-3 text-slate-200">Analyse spéculative</h2>

          <div className="space-y-3">
            <div>
              <label className="text-xs text-slate-400 mb-1 block">Département</label>
              <select
                className="w-full bg-surface-900 border border-surface-700 rounded-lg px-3 py-2 text-sm text-slate-200 focus:border-primary-500 focus:outline-none"
                value={departement}
                onChange={(e) => setDepartement(e.target.value)}
              >
                {DEPARTEMENTS.map((d) => (
                  <option key={d.code} value={d.code}>{d.name}</option>
                ))}
              </select>
            </div>

            <div>
              <label className="text-xs text-slate-400 mb-2 block">Mode d'analyse</label>
              <div className="grid grid-cols-1 gap-1.5">
                {[
                  { mode: 'heatmap' as const, label: '🗺 Carte spéculation', desc: 'Score par commune' },
                  { mode: 'flips' as const, label: '🔄 Flips rapides', desc: 'Reventes à fort gain' },
                  { mode: 'acquisitions' as const, label: '🏢 Acquisitions massives', desc: 'Concentration corporate' },
                ].map((item) => (
                  <button
                    key={item.mode}
                    onClick={() => setViewMode(item.mode)}
                    className={`text-left px-3 py-2.5 rounded-lg border transition-colors ${
                      viewMode === item.mode
                        ? 'bg-red-500/15 border-red-500/40 text-red-300'
                        : 'border-surface-600 text-slate-400 hover:border-slate-500'
                    }`}
                  >
                    <p className="text-xs font-medium">{item.label}</p>
                    <p className="text-xs text-slate-500 mt-0.5">{item.desc}</p>
                  </button>
                ))}
              </div>
            </div>

            {viewMode === 'flips' && (
              <div className="space-y-2 border-t border-surface-700 pt-3">
                <div>
                  <label className="text-xs text-slate-400 mb-1 block">
                    Gain minimum: {flipParams.min_gain_pct} %
                  </label>
                  <input
                    type="range"
                    min={10}
                    max={100}
                    value={flipParams.min_gain_pct}
                    onChange={(e) => setFlipParams((p) => ({ ...p, min_gain_pct: +e.target.value }))}
                    className="w-full accent-red-500"
                  />
                </div>
                <div>
                  <label className="text-xs text-slate-400 mb-1 block">
                    Détention max: {flipParams.max_hold_months} mois
                  </label>
                  <input
                    type="range"
                    min={3}
                    max={60}
                    value={flipParams.max_hold_months}
                    onChange={(e) => setFlipParams((p) => ({ ...p, max_hold_months: +e.target.value }))}
                    className="w-full accent-red-500"
                  />
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Stats summary */}
        {viewMode === 'heatmap' && heatmap.length > 0 && (
          <div className="bg-surface-800 rounded-xl p-4 border border-surface-700">
            <h2 className="font-semibold text-sm mb-3 text-slate-200">Zones à risque</h2>
            <div className="space-y-1.5">
              {heatmap
                .filter((h: any) => h.level !== 'low')
                .slice(0, 8)
                .map((h: any) => (
                  <div
                    key={h.code_commune}
                    className="flex items-center justify-between py-1.5 px-2 rounded cursor-pointer hover:bg-surface-700 transition-colors"
                    onClick={() => setSelectedCommune(h.code_commune)}
                  >
                    <span className="text-xs text-slate-300">{h.commune}</span>
                    <span
                      className="text-xs font-bold"
                      style={{ color: h.level === 'high' ? '#E63946' : '#F4A261' }}
                    >
                      {h.speculation_score.toFixed(0)}/100
                    </span>
                  </div>
                ))}
            </div>
          </div>
        )}

        {/* Flip list */}
        {viewMode === 'flips' && flips.length > 0 && (
          <div className="bg-surface-800 rounded-xl p-4 border border-surface-700">
            <h2 className="font-semibold text-sm mb-1 text-slate-200">
              {flips.length} flips détectés
            </h2>
            <p className="text-xs text-slate-500 mb-3">
              Biens revendus en &lt;{flipParams.max_hold_months} mois avec +{flipParams.min_gain_pct}% de gain
            </p>
            <div className="space-y-2 max-h-60 overflow-y-auto">
              {flips.slice(0, 20).map((flip: any, i: number) => (
                <div key={i} className="p-2.5 rounded-lg bg-surface-700/50 text-xs">
                  <div className="flex items-start justify-between">
                    <div>
                      <p className="font-medium text-slate-200">{flip.commune}</p>
                      <p className="text-slate-500 mt-0.5">{flip.type_local}</p>
                    </div>
                    <span
                      className="font-bold text-sm"
                      style={{ color: SEVERITY_COLORS[flip.severity as keyof typeof SEVERITY_COLORS] }}
                    >
                      +{flip.gain_pct.toFixed(0)} %
                    </span>
                  </div>
                  <div className="mt-1.5 flex gap-3 text-slate-400">
                    <span>{flip.holding_days} jours</span>
                    <span>{formatEuro(flip.prix_achat)} → {formatEuro(flip.prix_revente)}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Gentrification panel for selected commune */}
        {gentrif && !gentrif.error && (
          <div className="bg-surface-800 rounded-xl p-4 border border-surface-700">
            <div className="flex items-center justify-between mb-3">
              <h2 className="font-semibold text-sm text-slate-200">Gentrification</h2>
              <span
                className="text-xs px-2 py-0.5 rounded-full font-medium"
                style={{
                  background: STAGE_COLORS[gentrif.stage as keyof typeof STAGE_COLORS] + '20',
                  color: STAGE_COLORS[gentrif.stage as keyof typeof STAGE_COLORS],
                }}
              >
                {gentrif.stage}
              </span>
            </div>

            <div className="grid grid-cols-2 gap-2 mb-3">
              <div className="bg-surface-700/50 rounded-lg p-2.5">
                <p className="text-xs text-slate-500">Score</p>
                <p className="text-lg font-bold text-slate-200">{gentrif.gentrification_score}/100</p>
              </div>
              <div className="bg-surface-700/50 rounded-lg p-2.5">
                <p className="text-xs text-slate-500">Risque déplacement</p>
                <p className="text-lg font-bold text-red-400">{gentrif.displacement_risk.toFixed(0)}/100</p>
              </div>
            </div>

            {gentrif.price_history?.length > 0 && (
              <PriceChart historical={gentrif.price_history.map((h: any) => ({
                date: `${h.year}-01-01`,
                prix_median_m2: h.prix_median_m2,
                prix_p25_m2: null,
                prix_p75_m2: null,
                nb_transactions: h.nb_transactions,
              }))} height={150} />
            )}

            <div className="mt-2 space-y-1">
              {gentrif.signals?.map((s: any, i: number) => (
                <div key={i} className="flex items-center gap-2 text-xs">
                  <div className="w-1.5 h-1.5 rounded-full bg-orange-400 shrink-0" />
                  <span className="text-slate-400">{s.signal.replace(/_/g, ' ')}</span>
                  <span className="text-orange-400 font-medium ml-auto">+{s.weight}pts</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Map */}
      <div className="flex-1 bg-surface-800 rounded-xl border border-surface-700 overflow-hidden relative">
        <MapContainer
          center={FRANCE_CENTER}
          zoom={departement ? 9 : 6}
          className="w-full h-full"
          style={{ background: '#0F172A' }}
        >
          <TileLayer
            url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
            attribution='&copy; OpenStreetMap &copy; CARTO'
            maxZoom={19}
          />

          {/* Speculation heatmap */}
          {viewMode === 'heatmap' &&
            heatmap
              .filter((h: any) => h.lat && h.lng)
              .map((h: any) => (
                <CircleMarker
                  key={h.code_commune}
                  center={[h.lat, h.lng]}
                  radius={Math.max(5, h.speculation_score / 5)}
                  pathOptions={{
                    fillColor: h.level === 'high' ? '#E63946' : h.level === 'medium' ? '#F4A261' : '#2A9D8F',
                    fillOpacity: 0.5 + h.speculation_score / 200,
                    color: selectedCommune === h.code_commune ? '#fff' : 'transparent',
                    weight: 2,
                  }}
                  eventHandlers={{ click: () => setSelectedCommune(h.code_commune) }}
                >
                  <Popup>
                    <div className="p-2 text-sm">
                      <p className="font-semibold">{h.commune}</p>
                      <p className="text-xs text-slate-500 mt-1">Score: {h.speculation_score.toFixed(0)}/100</p>
                      <p className="text-xs text-slate-500">Flips: {h.flip_rate.toFixed(1)} %</p>
                    </div>
                  </Popup>
                </CircleMarker>
              ))}

          {/* Flips map */}
          {viewMode === 'flips' &&
            flips
              .filter((f: any) => f.latitude && f.longitude)
              .map((f: any, i: number) => (
                <CircleMarker
                  key={i}
                  center={[f.latitude, f.longitude]}
                  radius={4 + f.gain_pct / 20}
                  pathOptions={{
                    fillColor: SEVERITY_COLORS[f.severity as keyof typeof SEVERITY_COLORS],
                    fillOpacity: 0.75,
                    color: 'transparent',
                  }}
                >
                  <Popup>
                    <div className="p-2 text-sm">
                      <p className="font-semibold">{f.commune}</p>
                      <p className="text-xs mt-1">
                        <span className="font-bold text-red-500">+{f.gain_pct.toFixed(0)} %</span>
                        {' en '}{f.holding_days} jours
                      </p>
                      <p className="text-xs text-slate-500 mt-0.5">{f.type_local}</p>
                      <p className="text-xs text-slate-500">{f.adresse}</p>
                    </div>
                  </Popup>
                </CircleMarker>
              ))}
        </MapContainer>

        {/* Legend */}
        <div className="absolute bottom-4 right-4 z-[1000] bg-surface-900/90 backdrop-blur rounded-xl p-3 border border-surface-700 text-xs">
          {viewMode === 'heatmap' && (
            <>
              <p className="font-medium mb-2 text-slate-300">Niveau spéculation</p>
              {[['#E63946', 'Élevé'], ['#F4A261', 'Moyen'], ['#2A9D8F', 'Faible']].map(([c, l]) => (
                <div key={l} className="flex items-center gap-2 mb-1">
                  <div className="w-3 h-3 rounded-full" style={{ background: c }} />
                  <span className="text-slate-400">{l}</span>
                </div>
              ))}
            </>
          )}
          {viewMode === 'flips' && (
            <>
              <p className="font-medium mb-2 text-slate-300">Sévérité flip</p>
              {Object.entries(SEVERITY_COLORS).map(([sev, color]) => (
                <div key={sev} className="flex items-center gap-2 mb-1">
                  <div className="w-3 h-3 rounded-full" style={{ background: color }} />
                  <span className="text-slate-400 capitalize">{sev}</span>
                </div>
              ))}
            </>
          )}
        </div>
      </div>
    </div>
  )
}
