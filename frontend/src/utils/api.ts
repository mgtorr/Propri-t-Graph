import axios from 'axios'

const API_BASE = import.meta.env.VITE_API_URL || '/api/v1'

export const api = axios.create({
  baseURL: API_BASE,
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
})

// Price analysis
export const priceApi = {
  getHistory: (params: { code_commune?: string; iris_code?: string; type_local?: string; start_year?: number }) =>
    api.get('/analysis/price-history', { params }),

  getPrediction: (params: { code_commune: string; type_local?: string; horizon_months?: number }) =>
    api.get('/analysis/price-prediction', { params }),

  getHeatmap: (params: { code_departement: string; type_local?: string; year?: number }) =>
    api.get('/analysis/heatmap', { params }),

  getEvolutionRanking: (params: { code_departement: string; type_local?: string; top_n?: number }) =>
    api.get('/analysis/evolution-ranking', { params }),
}

// Speculation
export const speculationApi = {
  getRapidFlips: (params: { code_commune?: string; code_departement?: string; min_gain_pct?: number; max_hold_months?: number }) =>
    api.get('/analysis/speculation/rapid-flips', { params }),

  getHeatmap: (params: { code_departement: string }) =>
    api.get('/analysis/speculation/heatmap', { params }),

  getGentrification: (params: { code_commune: string }) =>
    api.get('/analysis/gentrification', { params }),

  getMassAcquisitions: (params: { code_departement: string; min_properties?: number }) =>
    api.get('/analysis/mass-acquisitions', { params }),
}

// Ownership
export const ownershipApi = {
  getNetwork: (params: { code_commune?: string; code_departement?: string; owner_id?: string; depth?: number; min_properties?: number }) =>
    api.get('/ownership/network', { params }),

  getCorporateStats: (params: { code_commune?: string; code_departement?: string }) =>
    api.get('/ownership/corporate-stats', { params }),

  getTopOwners: (params: { code_commune?: string; code_departement?: string; limit?: number }) =>
    api.get('/ownership/top-owners', { params }),
}

// Opportunities
export const opportunityApi = {
  search: (params: { max_budget: number; surface_min?: number; type_local?: string; departements?: string; prefer_stable_prices?: boolean; limit?: number }) =>
    api.get('/opportunities/search', { params }),

  simulate: (params: { salaire_mensuel_net: number; apport?: number; duree_ans?: number; taux_interet?: number; departements?: string }) =>
    api.get('/opportunities/budget-simulation', { params }),
}

// Properties
export const propertiesApi = {
  getTransactions: (params: Record<string, string | number | undefined>) =>
    api.get('/properties/transactions', { params }),

  getParcelleHistory: (parcelle_id: string) =>
    api.get(`/properties/parcelle/${parcelle_id}`),

  getCommuneStats: (code_commune: string) =>
    api.get(`/properties/stats/commune/${code_commune}`),
}

// BAN address search (proxy)
export const banApi = {
  search: async (q: string, limit = 5) => {
    const response = await axios.get('https://api-adresse.data.gouv.fr/search', {
      params: { q, limit },
      timeout: 5000,
    })
    return response.data.features.map((f: any) => ({
      label: f.properties.label,
      score: f.properties.score,
      citycode: f.properties.citycode,
      postcode: f.properties.postcode,
      city: f.properties.city,
      lat: f.geometry.coordinates[1],
      lng: f.geometry.coordinates[0],
    }))
  },

  searchCommunes: async (q: string) => {
    const response = await axios.get('https://geo.api.gouv.fr/communes', {
      params: { nom: q, fields: 'nom,code,population,codesPostaux,departement', limit: 10 },
      timeout: 5000,
    })
    return response.data
  },
}
