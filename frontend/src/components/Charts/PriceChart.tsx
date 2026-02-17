import {
  ComposedChart,
  Area,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts'
import { format, parseISO } from 'date-fns'
import { fr } from 'date-fns/locale'
import type { PriceDataPoint, PriceForecast } from '@/types'
import { formatPrixM2 } from '@/utils/format'

interface PriceChartProps {
  historical: PriceDataPoint[]
  forecast?: PriceForecast[]
  title?: string
  height?: number
}

const CustomTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null

  return (
    <div className="bg-surface-800 border border-surface-700 rounded-lg p-3 shadow-xl text-xs space-y-1.5">
      <p className="font-medium text-slate-200 mb-2">
        {label && format(parseISO(label), 'MMMM yyyy', { locale: fr })}
      </p>
      {payload.map((entry: any) => (
        <div key={entry.name} className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full" style={{ background: entry.color }} />
          <span className="text-slate-400">{entry.name}:</span>
          <span className="font-medium text-slate-200">
            {typeof entry.value === 'number' ? formatPrixM2(entry.value) : entry.value}
          </span>
        </div>
      ))}
    </div>
  )
}

export function PriceChart({ historical, forecast = [], title, height = 300 }: PriceChartProps) {
  // Combine historical + forecast
  const allData = [
    ...historical.map((d) => ({
      date: d.date,
      prix_median: d.prix_median_m2,
      prix_p25: d.prix_p25_m2,
      prix_p75: d.prix_p75_m2,
      nb_transactions: d.nb_transactions,
      type: 'historical' as const,
    })),
    ...forecast.map((f) => ({
      date: f.date,
      prix_predit: f.prix_predit_m2,
      prix_predit_min: f.prix_min_m2,
      prix_predit_max: f.prix_max_m2,
      type: 'forecast' as const,
    })),
  ]

  const forecastStartDate = historical.length > 0 ? historical[historical.length - 1].date : null

  return (
    <div>
      {title && (
        <h3 className="text-sm font-medium text-slate-300 mb-3">{title}</h3>
      )}
      <ResponsiveContainer width="100%" height={height}>
        <ComposedChart data={allData} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
          <defs>
            <linearGradient id="colorMedian" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#3B82F6" stopOpacity={0.2} />
              <stop offset="95%" stopColor="#3B82F6" stopOpacity={0} />
            </linearGradient>
            <linearGradient id="colorForecast" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#F59E0B" stopOpacity={0.15} />
              <stop offset="95%" stopColor="#F59E0B" stopOpacity={0} />
            </linearGradient>
          </defs>

          <CartesianGrid strokeDasharray="3 3" stroke="#1E293B" />
          <XAxis
            dataKey="date"
            tickFormatter={(d) => {
              try { return format(parseISO(d), 'MMM yy', { locale: fr }) }
              catch { return d }
            }}
            tick={{ fill: '#64748B', fontSize: 11 }}
            axisLine={{ stroke: '#1E293B' }}
            tickLine={false}
          />
          <YAxis
            tickFormatter={(v) => `${Math.round(v / 1000)}k€`}
            tick={{ fill: '#64748B', fontSize: 11 }}
            axisLine={false}
            tickLine={false}
            width={45}
          />
          <Tooltip content={<CustomTooltip />} />
          <Legend
            wrapperStyle={{ fontSize: 11, color: '#94A3B8' }}
            iconType="circle"
            iconSize={8}
          />

          {/* Interquartile range */}
          <Area
            dataKey="prix_p75"
            stroke="transparent"
            fill="#3B82F6"
            fillOpacity={0.08}
            name="Q75"
            legendType="none"
          />
          <Area
            dataKey="prix_p25"
            stroke="transparent"
            fill="#0F172A"
            fillOpacity={1}
            name="Q25"
            legendType="none"
          />

          {/* Median price line */}
          <Line
            type="monotone"
            dataKey="prix_median"
            stroke="#3B82F6"
            strokeWidth={2}
            dot={false}
            name="Prix médian"
            connectNulls
          />

          {/* Forecast confidence interval */}
          <Area
            dataKey="prix_predit_max"
            stroke="transparent"
            fill="#F59E0B"
            fillOpacity={0.1}
            name="Intervalle"
            legendType="none"
          />
          <Area
            dataKey="prix_predit_min"
            stroke="transparent"
            fill="#0F172A"
            fillOpacity={1}
            legendType="none"
          />

          {/* Forecast line */}
          <Line
            type="monotone"
            dataKey="prix_predit"
            stroke="#F59E0B"
            strokeWidth={2}
            strokeDasharray="5 5"
            dot={false}
            name="Prévision"
            connectNulls
          />

          {forecastStartDate && (
            <ReferenceLine
              x={forecastStartDate}
              stroke="#475569"
              strokeDasharray="3 3"
              label={{ value: 'Prévision →', fill: '#64748B', fontSize: 10, position: 'top' }}
            />
          )}
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  )
}
