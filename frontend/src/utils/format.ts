/**
 * French locale formatting utilities.
 */

const euroFormatter = new Intl.NumberFormat('fr-FR', {
  style: 'currency',
  currency: 'EUR',
  maximumFractionDigits: 0,
})

const numberFormatter = new Intl.NumberFormat('fr-FR')

const compactFormatter = new Intl.NumberFormat('fr-FR', {
  notation: 'compact',
  maximumFractionDigits: 1,
})

export const formatEuro = (value: number | null | undefined): string => {
  if (value == null) return '—'
  return euroFormatter.format(value)
}

export const formatEuroCompact = (value: number | null | undefined): string => {
  if (value == null) return '—'
  return compactFormatter.format(value) + ' €'
}

export const formatPrixM2 = (value: number | null | undefined): string => {
  if (value == null) return '—'
  return `${numberFormatter.format(Math.round(value))} €/m²`
}

export const formatNumber = (value: number | null | undefined): string => {
  if (value == null) return '—'
  return numberFormatter.format(value)
}

export const formatPct = (value: number | null | undefined, decimals = 1): string => {
  if (value == null) return '—'
  const sign = value > 0 ? '+' : ''
  return `${sign}${value.toFixed(decimals)} %`
}

export const formatSurface = (value: number | null | undefined): string => {
  if (value == null) return '—'
  return `${Math.round(value)} m²`
}

export const formatDate = (dateStr: string | null | undefined): string => {
  if (!dateStr) return '—'
  return new Date(dateStr).toLocaleDateString('fr-FR', {
    year: 'numeric',
    month: 'long',
  })
}

export const getEvolutionColor = (pct: number | null): string => {
  if (pct == null) return 'text-slate-400'
  if (pct >= 20) return 'text-red-400'
  if (pct >= 10) return 'text-orange-400'
  if (pct >= 0) return 'text-emerald-400'
  return 'text-blue-400'
}

export const getScoreColor = (score: number): string => {
  if (score >= 75) return '#2A9D8F'
  if (score >= 50) return '#E9C46A'
  if (score >= 25) return '#F4A261'
  return '#E63946'
}

export const getPriceHeatColor = (value: number, min: number, max: number): string => {
  const ratio = (value - min) / (max - min || 1)
  // Blue (cheap) → Yellow → Red (expensive)
  if (ratio < 0.33) return `rgba(96, 165, 250, ${0.6 + ratio * 0.4})`
  if (ratio < 0.66) return `rgba(251, 191, 36, ${0.6 + (ratio - 0.33) * 0.6})`
  return `rgba(239, 68, 68, ${0.6 + (ratio - 0.66) * 1.2})`
}
