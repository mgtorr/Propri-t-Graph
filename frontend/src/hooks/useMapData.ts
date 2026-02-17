import { useQuery } from '@tanstack/react-query'
import { priceApi, speculationApi, opportunityApi } from '@/utils/api'
import type { MapFilters } from '@/types'

export function usePriceHeatmap(filters: MapFilters) {
  return useQuery({
    queryKey: ['heatmap', filters.departement, filters.typeLocal, filters.year],
    queryFn: async () => {
      if (!filters.departement) return []
      const res = await priceApi.getHeatmap({
        code_departement: filters.departement,
        type_local: filters.typeLocal === 'Tous' ? 'Appartement' : filters.typeLocal,
        year: filters.year,
      })
      return res.data.heatmap
    },
    enabled: !!filters.departement,
    staleTime: 1000 * 60 * 10, // 10 min
  })
}

export function useSpeculationHeatmap(departement: string) {
  return useQuery({
    queryKey: ['speculation-heatmap', departement],
    queryFn: async () => {
      const res = await speculationApi.getHeatmap({ code_departement: departement })
      return res.data.heatmap
    },
    enabled: !!departement,
    staleTime: 1000 * 60 * 30,
  })
}

export function usePriceHistory(code_commune: string, type_local: string) {
  return useQuery({
    queryKey: ['price-history', code_commune, type_local],
    queryFn: async () => {
      const res = await priceApi.getHistory({ code_commune, type_local })
      return res.data.data
    },
    enabled: !!code_commune,
    staleTime: 1000 * 60 * 60,
  })
}

export function usePricePrediction(code_commune: string, type_local: string, enabled: boolean) {
  return useQuery({
    queryKey: ['price-prediction', code_commune, type_local],
    queryFn: async () => {
      const res = await priceApi.getPrediction({ code_commune, type_local, horizon_months: 12 })
      return res.data
    },
    enabled: enabled && !!code_commune,
    staleTime: 1000 * 60 * 60 * 24,
  })
}

export function useGentrification(code_commune: string, enabled: boolean) {
  return useQuery({
    queryKey: ['gentrification', code_commune],
    queryFn: async () => {
      const res = await speculationApi.getGentrification({ code_commune })
      return res.data
    },
    enabled: enabled && !!code_commune,
    staleTime: 1000 * 60 * 60,
  })
}

export function useOpportunities(params: {
  max_budget: number
  surface_min: number
  type_local: string
  departements?: string
}) {
  return useQuery({
    queryKey: ['opportunities', params],
    queryFn: async () => {
      const res = await opportunityApi.search({ ...params, limit: 30 })
      return res.data
    },
    staleTime: 1000 * 60 * 30,
  })
}
