from sqlalchemy import Column, String, Float, Integer, Date, DateTime, Boolean, Text, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from geoalchemy2 import Geometry
import uuid
from datetime import datetime
from api.database import Base


class SpeculationAlert(Base):
    """Detected speculative pattern or gentrification signal."""
    __tablename__ = "speculation_alerts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    alert_type = Column(String(50), nullable=False, index=True)
    # Types: "rapid_flip", "mass_acquisition", "price_spike", "gentrification",
    #        "corporate_takeover", "displacement_risk", "renovation_wave"

    severity = Column(String(20), index=True)  # "low", "medium", "high", "critical"
    score = Column(Float)  # 0-100

    # Scope
    code_commune = Column(String(5), index=True)
    commune = Column(String(100))
    code_departement = Column(String(3))
    iris_code = Column(String(9), index=True)
    quartier = Column(String(100))
    parcelle_id = Column(String(50))  # if property-specific
    owner_id = Column(UUID(as_uuid=True))  # if owner-specific

    # Evidence
    description = Column(Text)
    evidence = Column(JSONB)  # Supporting data points
    affected_period_start = Column(Date)
    affected_period_end = Column(Date)
    nb_transactions_analyzed = Column(Integer)

    # Trends
    prix_evolution_pct = Column(Float)
    vitesse_rotation = Column(Float)  # avg holding period in months
    part_achats_societes = Column(Float)  # % of purchases by companies

    geom = Column(Geometry("POLYGON", srid=4326))
    computed_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)

    __table_args__ = (
        Index("idx_alerts_commune", "code_commune"),
        Index("idx_alerts_type_severity", "alert_type", "severity"),
        Index("idx_alerts_iris", "iris_code"),
    )


class PricePrediction(Base):
    """Price forecast for a neighborhood."""
    __tablename__ = "price_predictions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code_commune = Column(String(5), nullable=False, index=True)
    iris_code = Column(String(9), index=True)
    type_local = Column(String(100), nullable=False)
    prediction_date = Column(Date, nullable=False)  # target date
    computed_at = Column(DateTime, default=datetime.utcnow)

    # Model outputs
    prix_predit_m2 = Column(Float, nullable=False)
    prix_predit_min_m2 = Column(Float)  # lower confidence bound
    prix_predit_max_m2 = Column(Float)  # upper confidence bound
    confidence = Column(Float)          # model confidence 0-1

    # Current baseline
    prix_actuel_m2 = Column(Float)
    evolution_prevue_pct = Column(Float)

    # Model metadata
    model_version = Column(String(50))
    model_type = Column(String(50))  # "prophet", "xgboost", "ensemble"
    features_used = Column(JSONB)
    horizon_months = Column(Integer)

    __table_args__ = (
        Index("idx_predictions_commune_date", "code_commune", "prediction_date"),
    )


class OpportunityScore(Base):
    """First-time buyer opportunity score per zone."""
    __tablename__ = "opportunity_scores"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code_commune = Column(String(5), nullable=False, index=True)
    commune = Column(String(100))
    code_departement = Column(String(3), index=True)
    iris_code = Column(String(9), index=True)
    quartier = Column(String(100))

    # Scores (0-100, higher = better opportunity)
    score_global = Column(Float, index=True)
    score_prix = Column(Float)           # affordability vs. area median
    score_evolution = Column(Float)      # price trend (stable or rising moderately)
    score_liquidite = Column(Float)      # market activity level
    score_infrastructure = Column(Float) # schools, transport, services
    score_securite = Column(Float)       # crime rate (low = better)
    score_speculation = Column(Float)    # low speculation = better for buyers

    # Market data
    prix_median_m2 = Column(Float)
    budget_median_appartement = Column(Float)  # typical 50m2 apt price
    budget_median_maison = Column(Float)       # typical 100m2 house price
    evolution_prix_1an = Column(Float)
    evolution_prix_3ans = Column(Float)
    nb_transactions_trimestre = Column(Integer)
    delai_vente_moyen_jours = Column(Integer)

    # Context
    population = Column(Integer)
    revenu_median = Column(Float)
    taux_proprietaires = Column(Float)
    taux_logements_vacants = Column(Float)

    # PTZ eligibility (Prêt à Taux Zéro)
    eligible_ptz = Column(Boolean, default=False)
    zone_ptz = Column(String(5))  # A, Abis, B1, B2, C

    geom = Column(Geometry("POLYGON", srid=4326))
    computed_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_opportunities_score", "score_global"),
        Index("idx_opportunities_commune", "code_commune"),
        Index("idx_opportunities_geom", "geom", postgresql_using="gist"),
    )


class GentrificationIndex(Base):
    """Gentrification and displacement risk tracking."""
    __tablename__ = "gentrification_indices"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    iris_code = Column(String(9), nullable=False, index=True)
    code_commune = Column(String(5), index=True)
    year = Column(Integer, nullable=False)

    # Gentrification stage: "stable", "early", "active", "advanced", "post"
    stage = Column(String(20), index=True)
    gentrification_score = Column(Float)  # 0-100
    displacement_risk = Column(Float)     # 0-100

    # Indicators
    prix_evolution_5ans = Column(Float)
    prix_evolution_10ans = Column(Float)
    part_achats_investisseurs = Column(Float)
    turnover_rate = Column(Float)         # % of properties sold per year
    renovation_permits = Column(Integer)
    new_business_openings = Column(Integer)
    avg_income_change = Column(Float)
    housing_stock_change = Column(Float)

    # Signals
    signals = Column(JSONB)  # list of detected signals with weights
    geom = Column(Geometry("POLYGON", srid=4326))
    computed_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_gentrification_iris_year", "iris_code", "year"),
        Index("idx_gentrification_score", "gentrification_score"),
    )
