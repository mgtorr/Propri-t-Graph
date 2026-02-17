# PropriétéGraph — Real Estate Intelligence Platform

Intelligence immobilière basée sur les données ouvertes françaises.

## Data Sources

| Source | Dataset | Volume | Update |
|--------|---------|--------|--------|
| [data.gouv.fr](https://www.data.gouv.fr/fr/datasets/demandes-de-valeurs-foncieres/) | Demandes de Valeurs Foncières (DVF) | ~2M trans/year | Annual |
| [adresse.data.gouv.fr](https://adresse.data.gouv.fr/) | Base Adresse Nationale (BAN) | 27M addresses | Daily |
| [cadastre.data.gouv.fr](https://cadastre.data.gouv.fr/) | Cadastre Etalab | ~67M parcels | Quarterly |

## Features

### 🗺 Price Evolution Analysis
- Monthly price heatmaps per department
- Neighborhood-level price history (2014–present)
- Predictive modeling with Prophet (12-month forecasts)
- Winner/loser commune rankings by price evolution

### 📈 Speculation Detection
- **Rapid Flips**: Properties resold < 24 months with > 20% gain
- **Mass Acquisitions**: Concentrated buying patterns in same zone
- **Price Spike Detection**: Statistical outliers per neighborhood
- **Corporate Wave Analysis**: Institutional investor concentration

### 🏘 Gentrification Tracking
- Multi-signal gentrification index (price evolution + volume + acceleration)
- Displacement risk score per commune
- Historical stage tracking: stable → early → active → advanced
- Evidence signals with weighted contributions

### 🕸 Ownership Network Mapping
- D3.js force-directed graph of ownership relationships
- Corporate vs. individual ownership breakdown
- Top property owners by zone
- Speculator detection flags
- Co-ownership and transaction chains

### 🔑 First-Time Buyer Finder
- Opportunity scoring based on affordability + stability + liquidity
- French mortgage capacity simulation (35% debt-to-income rule)
- PTZ (Prêt à Taux Zéro) zone eligibility
- Budget-constrained commune ranking

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                    Frontend (React)                   │
│  Leaflet Maps │ D3 Network │ Recharts │ React Query  │
└──────────────────────┬──────────────────────────────┘
                        │ REST API
┌──────────────────────▼──────────────────────────────┐
│                  FastAPI Backend                      │
│  /analysis │ /ownership │ /opportunities │ /properties│
└──────┬──────────────────────────┬───────────────────┘
       │                          │
┌──────▼──────┐          ┌────────▼───────┐
│ PostgreSQL  │          │    Redis Cache │
│  + PostGIS  │          └────────────────┘
│             │
│ transactions│
│ properties  │          ┌────────────────┐
│ owners      │          │  Data Pipeline │
│ price_idx   │◄─────────│  DVF / BAN /  │
│ alerts      │          │  Cadastre      │
└─────────────┘          └────────────────┘
```

## Quick Start

### Prerequisites
- Docker + Docker Compose
- 10GB+ disk space (for DVF data)

### 1. Start services

```bash
cp .env.example .env
docker compose up -d db redis api frontend
```

### 2. Download DVF data

```bash
# Download data for 2022 and 2023 (Paris, Lyon, Marseille, Bordeaux, Toulouse)
./scripts/download_dvf.sh 2023 75 69 13 33 31

# Or via Docker
docker compose run --rm dvf-ingestion
```

### 3. Access the platform

- **Frontend**: http://localhost:3000
- **API docs**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Development

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run with hot reload
uvicorn api.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev  # http://localhost:3000
```

### Data pipeline

```bash
# Ingest DVF for specific years and departments
cd backend
python -m data_pipeline.dvf_ingestion 2023 75 69

# Geocode missing coordinates via BAN
python -m data_pipeline.ban_integration

# Process cadastral data
python -m data_pipeline.cadastral_processor 75
```

## API Reference

### Price Analysis

```http
GET /api/v1/analysis/price-history?code_commune=75056&type_local=Appartement
GET /api/v1/analysis/price-prediction?code_commune=75056&horizon_months=12
GET /api/v1/analysis/heatmap?code_departement=75&year=2023
GET /api/v1/analysis/evolution-ranking?code_departement=69&type_local=Maison
```

### Speculation

```http
GET /api/v1/analysis/speculation/rapid-flips?code_departement=75&min_gain_pct=20
GET /api/v1/analysis/speculation/heatmap?code_departement=75
GET /api/v1/analysis/gentrification?code_commune=75018
GET /api/v1/analysis/mass-acquisitions?code_departement=13
```

### Ownership

```http
GET /api/v1/ownership/network?code_commune=69123&min_properties=3
GET /api/v1/ownership/corporate-stats?code_commune=75056
GET /api/v1/ownership/top-owners?code_departement=75&limit=20
```

### Opportunities

```http
GET /api/v1/opportunities/search?max_budget=250000&surface_min=45&type_local=Appartement
GET /api/v1/opportunities/budget-simulation?salaire_mensuel_net=3500&apport=30000
GET /api/v1/opportunities/ptz-zones
```

## License

Data from data.gouv.fr is available under the [Licence Ouverte / Open Licence v2.0](https://www.etalab.gouv.fr/licence-ouverte-open-licence).

This project is licensed under MIT.
