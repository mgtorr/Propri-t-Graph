from sqlalchemy import Column, String, Float, Integer, Date, DateTime, Text, Index, Numeric
from sqlalchemy.dialects.postgresql import UUID, JSONB
from geoalchemy2 import Geometry
import uuid
from datetime import datetime
from api.database import Base


class Transaction(Base):
    """Demandes de Valeurs Foncières - property transaction record."""
    __tablename__ = "transactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    mutation_id = Column(String(50), unique=True, index=True)
    date_mutation = Column(Date, index=True, nullable=False)
    nature_mutation = Column(String(100), index=True)  # Vente, Adjudication, etc.
    valeur_fonciere = Column(Numeric(15, 2), nullable=False)

    # Address fields
    adresse_numero = Column(String(10))
    adresse_suffixe = Column(String(5))
    adresse_nom_voie = Column(String(200))
    adresse_code_voie = Column(String(10))
    code_postal = Column(String(5), index=True)
    commune = Column(String(100), index=True)
    code_commune = Column(String(5), index=True)
    code_departement = Column(String(3), index=True)
    ancien_code_commune = Column(String(5))
    ancien_nom_commune = Column(String(100))
    id_parcelle = Column(String(50), index=True)

    # Property details
    numero_volume = Column(String(20))
    lot1_numero = Column(String(10))
    lot1_surface_carrez = Column(Float)
    lot2_numero = Column(String(10))
    lot2_surface_carrez = Column(Float)
    lot3_numero = Column(String(10))
    lot3_surface_carrez = Column(Float)
    lot4_numero = Column(String(10))
    lot4_surface_carrez = Column(Float)
    lot5_numero = Column(String(10))
    lot5_surface_carrez = Column(Float)
    nombre_lots = Column(Integer)
    code_type_local = Column(String(5), index=True)
    type_local = Column(String(100), index=True)  # Maison, Appartement, etc.
    identifiant_local = Column(String(50))
    surface_reelle_bati = Column(Float)
    nombre_pieces_principales = Column(Integer)
    code_nature_culture = Column(String(5))
    nature_culture = Column(String(100))
    code_nature_culture_speciale = Column(String(5))
    nature_culture_speciale = Column(String(100))
    surface_terrain = Column(Float)

    # Geospatial
    longitude = Column(Float, index=True)
    latitude = Column(Float, index=True)
    geom = Column(Geometry("POINT", srid=4326))

    # Computed fields
    prix_m2 = Column(Numeric(12, 2))
    quartier = Column(String(100), index=True)
    iris_code = Column(String(9), index=True)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_transactions_date_commune", "date_mutation", "code_commune"),
        Index("idx_transactions_type_commune", "type_local", "code_commune"),
        Index("idx_transactions_prix", "valeur_fonciere"),
        Index("idx_transactions_geom", "geom", postgresql_using="gist"),
    )


class PriceIndex(Base):
    """Aggregated price index per neighborhood and period."""
    __tablename__ = "price_indices"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code_commune = Column(String(5), nullable=False, index=True)
    commune = Column(String(100))
    code_departement = Column(String(3), index=True)
    iris_code = Column(String(9), index=True)
    quartier = Column(String(100))
    type_local = Column(String(100), nullable=False)
    year = Column(Integer, nullable=False, index=True)
    quarter = Column(Integer)  # 1-4

    # Statistics
    nb_transactions = Column(Integer)
    prix_median_m2 = Column(Numeric(12, 2))
    prix_moyen_m2 = Column(Numeric(12, 2))
    prix_min_m2 = Column(Numeric(12, 2))
    prix_max_m2 = Column(Numeric(12, 2))
    prix_p25_m2 = Column(Numeric(12, 2))
    prix_p75_m2 = Column(Numeric(12, 2))
    surface_mediane = Column(Float)
    valeur_totale_mediane = Column(Numeric(15, 2))

    # Evolution
    evolution_1an = Column(Float)   # % change vs 1 year ago
    evolution_3ans = Column(Float)  # % change vs 3 years ago
    evolution_5ans = Column(Float)  # % change vs 5 years ago

    geom = Column(Geometry("POLYGON", srid=4326))
    computed_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_price_indices_commune_year", "code_commune", "year"),
        Index("idx_price_indices_iris_year", "iris_code", "year"),
    )
