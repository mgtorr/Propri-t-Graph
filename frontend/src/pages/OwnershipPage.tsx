import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { NetworkGraph, NetworkLegend } from '@/components/OwnershipGraph/NetworkGraph'
import { ownershipApi } from '@/utils/api'
import { formatEuroCompact, formatNumber } from '@/utils/format'
import type { NetworkNode, CorporateStats } from '@/types'

const DEPARTEMENTS = [
  { code: '75', name: 'Paris' },
  { code: '69', name: 'Rhône' },
  { code: '13', name: 'Bouches-du-Rhône' },
  { code: '33', name: 'Gironde' },
  { code: '31', name: 'Haute-Garonne' },
]

export function OwnershipPage() {
  const [scope, setScope] = useState<{ type: 'commune' | 'departement'; code: string }>({
    type: 'departement',
    code: '75',
  })
  const [selectedNode, setSelectedNode] = useState<NetworkNode | null>(null)
  const [minProperties, setMinProperties] = useState(3)

  const networkQuery = useQuery({
    queryKey: ['ownership-network', scope, minProperties],
    queryFn: async () => {
      const params =
        scope.type === 'commune'
          ? { code_commune: scope.code }
          : { code_departement: scope.code }
      const res = await ownershipApi.getNetwork({ ...params, min_properties: minProperties })
      return res.data
    },
    staleTime: 1000 * 60 * 10,
  })

  const corporateQuery = useQuery({
    queryKey: ['corporate-stats', scope],
    queryFn: async () => {
      const params =
        scope.type === 'commune'
          ? { code_commune: scope.code }
          : { code_departement: scope.code }
      const res = await ownershipApi.getCorporateStats(params)
      return res.data as CorporateStats
    },
    staleTime: 1000 * 60 * 10,
  })

  const topOwnersQuery = useQuery({
    queryKey: ['top-owners', scope],
    queryFn: async () => {
      const params =
        scope.type === 'commune'
          ? { code_commune: scope.code }
          : { code_departement: scope.code }
      const res = await ownershipApi.getTopOwners({ ...params, limit: 15 })
      return res.data.owners
    },
    staleTime: 1000 * 60 * 10,
  })

  const network = networkQuery.data
  const corporate = corporateQuery.data

  return (
    <div className="flex h-full gap-4 p-4">
      {/* Left: controls + stats */}
      <div className="w-80 shrink-0 flex flex-col gap-4 overflow-y-auto">
        {/* Scope selector */}
        <div className="bg-surface-800 rounded-xl p-4 border border-surface-700">
          <h2 className="font-semibold text-sm mb-3 text-slate-200">Zone d'analyse</h2>
          <div className="space-y-3">
            <div>
              <label className="text-xs text-slate-400 mb-1 block">Département</label>
              <select
                className="w-full bg-surface-900 border border-surface-700 rounded-lg px-3 py-2 text-sm text-slate-200 focus:border-primary-500 focus:outline-none"
                value={scope.type === 'departement' ? scope.code : ''}
                onChange={(e) => setScope({ type: 'departement', code: e.target.value })}
              >
                {DEPARTEMENTS.map((d) => (
                  <option key={d.code} value={d.code}>{d.name}</option>
                ))}
              </select>
            </div>

            <div>
              <label className="text-xs text-slate-400 mb-1 block">
                Propriétaires avec au moins {minProperties} biens
              </label>
              <input
                type="range"
                min={2}
                max={20}
                value={minProperties}
                onChange={(e) => setMinProperties(+e.target.value)}
                className="w-full accent-primary-500"
              />
              <div className="flex justify-between text-xs text-slate-500 mt-0.5">
                <span>2</span><span>20</span>
              </div>
            </div>
          </div>
        </div>

        {/* Corporate breakdown */}
        {corporate && (
          <div className="bg-surface-800 rounded-xl p-4 border border-surface-700">
            <div className="flex items-center justify-between mb-3">
              <h2 className="font-semibold text-sm text-slate-200">Répartition propriétaires</h2>
              <span
                className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                  corporate.concentration_risk === 'high'
                    ? 'bg-red-500/20 text-red-400'
                    : corporate.concentration_risk === 'medium'
                    ? 'bg-orange-500/20 text-orange-400'
                    : 'bg-emerald-500/20 text-emerald-400'
                }`}
              >
                {corporate.concentration_risk === 'high' ? 'Concentration élevée' :
                 corporate.concentration_risk === 'medium' ? 'Concentration moyenne' : 'Normale'}
              </span>
            </div>

            <div className="space-y-2">
              {corporate.breakdown.map((item) => (
                <div key={item.owner_type}>
                  <div className="flex justify-between text-xs mb-1">
                    <span className="text-slate-400 capitalize">{translateOwnerType(item.owner_type)}</span>
                    <span className="text-slate-300 font-medium">{item.part_pct} %</span>
                  </div>
                  <div className="w-full bg-surface-700 rounded-full h-1.5">
                    <div
                      className="h-1.5 rounded-full transition-all"
                      style={{
                        width: `${item.part_pct}%`,
                        background: getOwnerTypeColor(item.owner_type),
                      }}
                    />
                  </div>
                </div>
              ))}
            </div>

            <div className="mt-3 p-2 bg-surface-700/50 rounded-lg">
              <p className="text-xs text-slate-400">Part corporate (entreprises + SCI)</p>
              <p className={`text-lg font-bold ${
                corporate.corporate_share_pct >= 40 ? 'text-red-400' :
                corporate.corporate_share_pct >= 20 ? 'text-orange-400' : 'text-emerald-400'
              }`}>{corporate.corporate_share_pct} %</p>
            </div>
          </div>
        )}

        {/* Top owners */}
        {(topOwnersQuery.data || []).length > 0 && (
          <div className="bg-surface-800 rounded-xl p-4 border border-surface-700">
            <h2 className="font-semibold text-sm mb-3 text-slate-200">Grands propriétaires</h2>
            <div className="space-y-2">
              {(topOwnersQuery.data || []).slice(0, 8).map((owner: any) => (
                <div
                  key={owner.owner_id}
                  className="flex items-start justify-between py-2 px-2 rounded hover:bg-surface-700 transition-colors cursor-pointer"
                >
                  <div className="min-w-0 flex-1">
                    <p className="text-xs font-medium text-slate-300 truncate">
                      {owner.name}
                    </p>
                    <p className="text-xs text-slate-500 mt-0.5">
                      {translateOwnerType(owner.owner_type)}
                      {owner.is_speculator && ' · ⚠ Spéculateur'}
                    </p>
                  </div>
                  <div className="text-right ml-2 shrink-0">
                    <p className="text-xs font-medium text-slate-200">{owner.nb_biens} biens</p>
                    {owner.surface_totale_m2 && (
                      <p className="text-xs text-slate-500">{Math.round(owner.surface_totale_m2)} m²</p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Legend */}
        <div className="bg-surface-800 rounded-xl p-4 border border-surface-700">
          <h2 className="font-semibold text-sm mb-3 text-slate-200">Légende</h2>
          <NetworkLegend />
          <p className="text-xs text-slate-500 mt-3">
            La taille des nœuds reflète le nombre de biens possédés dans la zone.
            Les arêtes représentent des biens co-détenus ou transactions successives.
          </p>
        </div>
      </div>

      {/* Network graph */}
      <div className="flex-1 bg-surface-800 rounded-xl border border-surface-700 overflow-hidden relative">
        {networkQuery.isLoading && (
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="text-slate-400 text-sm">Construction du réseau…</div>
          </div>
        )}

        {network && (
          <>
            {/* Network metrics */}
            <div className="absolute top-4 left-4 z-10 flex gap-3">
              <div className="bg-surface-900/80 backdrop-blur rounded-lg px-3 py-1.5 text-xs border border-surface-700">
                <span className="text-slate-400">Nœuds: </span>
                <span className="text-slate-200 font-medium">{network.nodes?.length || 0}</span>
              </div>
              <div className="bg-surface-900/80 backdrop-blur rounded-lg px-3 py-1.5 text-xs border border-surface-700">
                <span className="text-slate-400">Liens: </span>
                <span className="text-slate-200 font-medium">{network.edges?.length || 0}</span>
              </div>
              {network.metrics?.density != null && (
                <div className="bg-surface-900/80 backdrop-blur rounded-lg px-3 py-1.5 text-xs border border-surface-700">
                  <span className="text-slate-400">Densité: </span>
                  <span className="text-slate-200 font-medium">{network.metrics.density.toFixed(3)}</span>
                </div>
              )}
              {network.is_demo && (
                <div className="bg-amber-500/10 border border-amber-500/30 rounded-lg px-3 py-1.5 text-xs text-amber-400">
                  Demo data
                </div>
              )}
            </div>

            <NetworkGraph
              nodes={network.nodes || []}
              edges={network.edges || []}
              onNodeClick={setSelectedNode}
            />
          </>
        )}

        {/* Selected node detail */}
        {selectedNode && (
          <div className="absolute bottom-4 right-4 z-10 w-64 bg-surface-900/90 backdrop-blur rounded-xl p-4 border border-surface-700">
            <div className="flex items-start justify-between mb-2">
              <h3 className="text-sm font-semibold text-slate-200 truncate">{selectedNode.label}</h3>
              <button
                onClick={() => setSelectedNode(null)}
                className="text-slate-500 hover:text-slate-300 ml-2 shrink-0"
              >
                ✕
              </button>
            </div>
            <div className="space-y-1 text-xs">
              <div className="flex justify-between">
                <span className="text-slate-400">Type</span>
                <span className="text-slate-200">{translateOwnerType(selectedNode.type)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Biens (zone)</span>
                <span className="text-slate-200">{selectedNode.nb_biens_zone}</span>
              </div>
              {selectedNode.nb_biens_total != null && (
                <div className="flex justify-between">
                  <span className="text-slate-400">Biens (total)</span>
                  <span className="text-slate-200">{selectedNode.nb_biens_total}</span>
                </div>
              )}
              {selectedNode.valeur_portfolio != null && (
                <div className="flex justify-between">
                  <span className="text-slate-400">Portfolio</span>
                  <span className="text-slate-200">{formatEuroCompact(selectedNode.valeur_portfolio)}</span>
                </div>
              )}
              {selectedNode.siren && (
                <div className="flex justify-between">
                  <span className="text-slate-400">SIREN</span>
                  <span className="text-slate-200 font-mono">{selectedNode.siren}</span>
                </div>
              )}
              {selectedNode.is_speculator && (
                <div className="mt-2 p-2 bg-red-500/10 border border-red-500/20 rounded-lg text-red-400">
                  ⚠ Comportement spéculatif détecté
                </div>
              )}
            </div>
          </div>
        )}

        {!network && !networkQuery.isLoading && (
          <div className="absolute inset-0 flex flex-col items-center justify-center text-center">
            <div className="text-4xl mb-4">🕸</div>
            <p className="text-slate-400 text-sm">Sélectionnez une zone pour afficher le réseau</p>
          </div>
        )}
      </div>
    </div>
  )
}

function translateOwnerType(type: string): string {
  const map: Record<string, string> = {
    individual: 'Particulier',
    company: 'Société',
    sci: 'SCI',
    public: 'Organisme public',
  }
  return map[type] || type
}

function getOwnerTypeColor(type: string): string {
  const colors: Record<string, string> = {
    individual: '#A8DADC',
    company: '#457B9D',
    sci: '#F4A261',
    public: '#2A9D8F',
  }
  return colors[type] || '#64748B'
}
