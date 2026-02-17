// Core domain types for PropriétéGraph

export interface PriceDataPoint {
  date: string
  prix_median_m2: number | null
  prix_p25_m2: number | null
  prix_p75_m2: number | null
  nb_transactions: number
}

export interface PriceForecast {
  date: string
  prix_predit_m2: number
  prix_min_m2: number
  prix_max_m2: number
}

export interface PricePrediction {
  code_commune: string
  type_local: string
  prix_actuel_m2: number
  date_reference: string
  horizon_months: number
  evolution_prevue_pct: number | null
  model: string
  forecast: PriceForecast[]
  historical: PriceDataPoint[]
}

export interface HeatmapPoint {
  iris_code: string
  code_commune: string
  commune: string
  nb_transactions: number
  prix_median_m2: number | null
  prix_moyen_m2: number | null
  lat: number | null
  lng: number | null
}

export interface EvolutionRanking {
  code_commune: string
  commune: string
  prix_median_m2: number | null
  evolution_1an_pct: number | null
  evolution_3ans_pct: number | null
  evolution_5ans_pct: number | null
}

// Speculation types
export interface RapidFlip {
  parcelle_id: string
  commune: string
  code_commune: string
  code_departement: string
  date_achat: string
  date_revente: string
  prix_achat: number
  prix_revente: number
  type_local: string
  adresse: string
  latitude: number | null
  longitude: number | null
  holding_days: number
  gain_pct: number
  severity: 'low' | 'medium' | 'high' | 'critical'
}

export interface SpeculationHeatmapPoint {
  code_commune: string
  commune: string
  lat: number | null
  lng: number | null
  total_transactions: number
  flip_rate: number
  prix_volatility: number
  luxury_rate: number
  speculation_score: number
  level: 'low' | 'medium' | 'high'
}

export interface GentrificationResult {
  code_commune: string
  gentrification_score: number
  displacement_risk: number
  stage: 'stable' | 'early' | 'active' | 'advanced'
  prix_actuel_m2: number
  evolution_5ans_pct: number | null
  evolution_10ans_pct: number | null
  signals: GentrificationSignal[]
  price_history: { year: number; prix_median_m2: number; nb_transactions: number }[]
}

export interface GentrificationSignal {
  signal: string
  value: number
  weight: number
}

// Ownership network types
export interface NetworkNode {
  id: string
  label: string
  type: 'individual' | 'company' | 'sci' | 'public'
  raison_sociale?: string
  siren?: string
  nb_biens_zone: number
  nb_biens_total?: number
  valeur_portfolio?: number | null
  is_speculator: boolean
  size: number
  color: string
  depth?: number
  is_center?: boolean
}

export interface NetworkEdge {
  source: string
  target: string
  weight: number
  label: string
}

export interface OwnershipNetwork {
  nodes: NetworkNode[]
  edges: NetworkEdge[]
  metrics: NetworkMetrics
  scope: { type: string; code: string }
  is_demo?: boolean
}

export interface NetworkMetrics {
  nb_nodes: number
  nb_edges: number
  density?: number
  nb_components?: number
  largest_component_size?: number
}

export interface CorporateStats {
  breakdown: OwnershipBreakdown[]
  total_biens: number
  corporate_share_pct: number
  concentration_risk: 'low' | 'medium' | 'high'
}

export interface OwnershipBreakdown {
  owner_type: string
  nb_biens: number
  nb_proprietaires: number
  valeur_totale?: number | null
  biens_par_proprio?: number | null
  part_pct: number
}

// Opportunity finder types
export interface Opportunity {
  code_commune: string
  commune: string
  code_departement: string
  prix_median_m2: number
  prix_p25_m2?: number
  budget_pour_surface_cible: number
  reste_budget?: number
  nb_transactions_2ans?: number
  score_opportunite: number
  lat: number | null
  lng: number | null
  zone_ptz: string
  eligible_ptz: boolean
  prix_stabilite?: 'stable' | 'variable'
  marche_actif?: 'actif' | 'calme'
}

export interface BudgetSimulation {
  simulation: {
    salaire_mensuel_net: number
    apport: number
    duree_ans: number
    taux_interet_pct: number
    mensualite_max: number
    capacite_emprunt: number
    budget_total_achat: number
    frais_notaire_estimes: number
    budget_bien_net: number
    taux_endettement_pct: number
  }
  opportunities: Opportunity[]
  summary: OpportunitySummary
}

export interface OpportunitySummary {
  nb_communes_analysees?: number
  nb_opportunites: number
  budget?: number
  surface_cible?: number
  type_bien?: string
  prix_min?: number | null
  prix_max?: number | null
  score_moyen?: number | null
}

// Transaction types
export interface Transaction {
  mutation_id: string
  date_mutation: string
  nature_mutation: string
  valeur_fonciere: number
  adresse: string
  code_postal: string
  commune: string
  code_commune: string
  type_local: string
  surface_m2: number | null
  nb_pieces: number | null
  prix_m2: number | null
  latitude: number | null
  longitude: number | null
  parcelle_id: string
}

// Filter state
export interface MapFilters {
  departement: string
  commune: string
  typeLocal: 'Appartement' | 'Maison' | 'Tous'
  year: number
  mode: 'prices' | 'speculation' | 'gentrification' | 'opportunities'
}
