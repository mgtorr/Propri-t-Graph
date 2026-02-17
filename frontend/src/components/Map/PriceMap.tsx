import { useEffect, useRef, useMemo } from 'react'
import L from 'leaflet'
import { MapContainer, TileLayer, CircleMarker, Popup, useMap } from 'react-leaflet'
import type { HeatmapPoint, SpeculationHeatmapPoint } from '@/types'
import { formatPrixM2, formatNumber, getPriceHeatColor } from '@/utils/format'

interface PriceMapProps {
  data: HeatmapPoint[]
  mode?: 'prices' | 'speculation'
  speculationData?: SpeculationHeatmapPoint[]
  onCommuneClick?: (code_commune: string, commune: string) => void
  center?: [number, number]
  zoom?: number
}

// France center
const FRANCE_CENTER: [number, number] = [46.8, 2.35]

function MapUpdater({ center, zoom }: { center: [number, number]; zoom: number }) {
  const map = useMap()
  useEffect(() => {
    map.setView(center, zoom)
  }, [center, zoom, map])
  return null
}

export function PriceMap({
  data,
  mode = 'prices',
  speculationData = [],
  onCommuneClick,
  center = FRANCE_CENTER,
  zoom = 6,
}: PriceMapProps) {
  const validData = data.filter((d) => d.lat && d.lng && d.prix_median_m2)

  const { minPrice, maxPrice } = useMemo(() => {
    const prices = validData.map((d) => d.prix_median_m2!).filter(Boolean)
    return {
      minPrice: Math.min(...prices),
      maxPrice: Math.max(...prices),
    }
  }, [validData])

  const validSpecData = speculationData.filter((d) => d.lat && d.lng)

  return (
    <MapContainer
      center={center}
      zoom={zoom}
      className="w-full h-full rounded-xl"
      style={{ background: '#0F172A' }}
    >
      <TileLayer
        url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
        maxZoom={19}
      />
      <MapUpdater center={center} zoom={zoom} />

      {mode === 'prices' &&
        validData.map((point) => {
          const color = getPriceHeatColor(point.prix_median_m2!, minPrice, maxPrice)
          const radius = Math.max(6, Math.min(20, Math.sqrt(point.nb_transactions)))

          return (
            <CircleMarker
              key={`${point.code_commune}-${point.iris_code}`}
              center={[point.lat!, point.lng!]}
              radius={radius}
              pathOptions={{
                color: 'transparent',
                fillColor: color,
                fillOpacity: 0.75,
              }}
              eventHandlers={{
                click: () => onCommuneClick?.(point.code_commune, point.commune),
              }}
            >
              <Popup className="price-popup">
                <div className="p-2 min-w-[180px]">
                  <p className="font-semibold text-sm">{point.commune}</p>
                  <p className="text-xs text-slate-500 mb-2">{point.code_commune}</p>
                  <div className="space-y-1">
                    <div className="flex justify-between text-sm">
                      <span className="text-slate-400">Prix médian</span>
                      <span className="font-medium">{formatPrixM2(point.prix_median_m2)}</span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-slate-400">Transactions</span>
                      <span className="font-medium">{formatNumber(point.nb_transactions)}</span>
                    </div>
                  </div>
                  {onCommuneClick && (
                    <button
                      onClick={() => onCommuneClick(point.code_commune, point.commune)}
                      className="mt-3 w-full text-xs bg-primary-600 hover:bg-primary-700 text-white py-1.5 px-3 rounded transition-colors"
                    >
                      Analyser cette commune →
                    </button>
                  )}
                </div>
              </Popup>
            </CircleMarker>
          )
        })}

      {mode === 'speculation' &&
        validSpecData.map((point) => {
          const opacity = 0.3 + (point.speculation_score / 100) * 0.6
          const color =
            point.level === 'high'
              ? '#E63946'
              : point.level === 'medium'
              ? '#F4A261'
              : '#2A9D8F'

          return (
            <CircleMarker
              key={point.code_commune}
              center={[point.lat!, point.lng!]}
              radius={Math.max(5, Math.min(18, point.speculation_score / 4))}
              pathOptions={{
                color: 'transparent',
                fillColor: color,
                fillOpacity: opacity,
              }}
              eventHandlers={{
                click: () => onCommuneClick?.(point.code_commune, point.commune),
              }}
            >
              <Popup>
                <div className="p-2 min-w-[180px]">
                  <p className="font-semibold text-sm">{point.commune}</p>
                  <div className="mt-2 space-y-1 text-sm">
                    <div className="flex justify-between">
                      <span className="text-slate-400">Score spéculation</span>
                      <span
                        className="font-bold"
                        style={{ color }}
                      >
                        {point.speculation_score.toFixed(0)}/100
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-400">Taux de flip</span>
                      <span>{point.flip_rate.toFixed(1)} %</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-400">Volatilité prix</span>
                      <span>{point.prix_volatility.toFixed(1)} %</span>
                    </div>
                  </div>
                </div>
              </Popup>
            </CircleMarker>
          )
        })}
    </MapContainer>
  )
}

// Legend component
export function PriceLegend({ min, max }: { min: number; max: number }) {
  return (
    <div className="absolute bottom-6 right-4 z-[1000] bg-surface-900/90 backdrop-blur rounded-xl p-3 border border-surface-700 text-xs">
      <p className="font-medium mb-2 text-slate-300">Prix au m²</p>
      <div className="flex items-center gap-2">
        <div
          className="w-24 h-3 rounded"
          style={{
            background: 'linear-gradient(to right, rgba(96,165,250,0.9), rgba(251,191,36,0.9), rgba(239,68,68,0.9))',
          }}
        />
      </div>
      <div className="flex justify-between mt-1 text-slate-400">
        <span>{formatPrixM2(min)}</span>
        <span>{formatPrixM2(max)}</span>
      </div>
    </div>
  )
}
