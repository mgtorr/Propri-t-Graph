from sqlalchemy import Column, String, Float, Integer, Date, DateTime, Boolean, ForeignKey, Text, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.orm import relationship
from geoalchemy2 import Geometry
import uuid
from datetime import datetime
from api.database import Base


class Owner(Base):
    """Property owner - individual or corporate entity."""
    __tablename__ = "owners"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_hash = Column(String(64), unique=True, index=True)  # anonymized identifier
    owner_type = Column(String(20), index=True)  # "individual", "company", "sci", "public"

    # For companies
    siren = Column(String(9), index=True)
    siret = Column(String(14), index=True)
    raison_sociale = Column(String(300))
    forme_juridique = Column(String(100))
    code_naf = Column(String(6))
    secteur_activite = Column(String(200))

    # Portfolio stats (computed)
    nb_biens = Column(Integer, default=0)
    valeur_portfolio = Column(Float)
    surface_totale = Column(Float)
    departements = Column(JSONB)  # list of dept codes
    communes = Column(JSONB)       # list of commune codes
    type_biens = Column(JSONB)     # breakdown by property type

    # Flags
    is_sci = Column(Boolean, default=False)
    is_fonciere = Column(Boolean, default=False)  # real estate company
    is_public = Column(Boolean, default=False)
    is_speculator = Column(Boolean, default=False)  # detected speculative behavior

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    properties = relationship("PropertyOwnership", back_populates="owner")

    __table_args__ = (
        Index("idx_owners_siren", "siren"),
        Index("idx_owners_type", "owner_type"),
    )


class Property(Base):
    """Cadastral property (parcelle)."""
    __tablename__ = "properties"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    parcelle_id = Column(String(50), unique=True, index=True)  # section+numero
    commune_code = Column(String(5), index=True)
    commune_name = Column(String(100))
    departement = Column(String(3), index=True)
    section = Column(String(5))
    numero_plan = Column(String(5))

    # Physical attributes
    surface_parcelle = Column(Float)
    surface_bati = Column(Float)
    type_local = Column(String(100), index=True)
    usage = Column(String(100))  # habitation, commercial, etc.
    nb_batiments = Column(Integer)
    annee_construction = Column(Integer)
    nb_logements = Column(Integer)

    # Valuation
    valeur_venale_estimee = Column(Float)
    derniere_mutation_date = Column(Date)
    derniere_mutation_prix = Column(Float)

    # Location
    adresse = Column(Text)
    code_postal = Column(String(5))
    longitude = Column(Float)
    latitude = Column(Float)
    geom = Column(Geometry("POLYGON", srid=4326))
    iris_code = Column(String(9), index=True)
    quartier = Column(String(100))

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    ownerships = relationship("PropertyOwnership", back_populates="property")
    transactions = relationship("PropertyTransaction", back_populates="property")

    __table_args__ = (
        Index("idx_properties_commune", "commune_code"),
        Index("idx_properties_geom", "geom", postgresql_using="gist"),
        Index("idx_properties_iris", "iris_code"),
    )


class PropertyOwnership(Base):
    """Ownership link between owner and property."""
    __tablename__ = "property_ownerships"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    property_id = Column(UUID(as_uuid=True), ForeignKey("properties.id"), nullable=False)
    owner_id = Column(UUID(as_uuid=True), ForeignKey("owners.id"), nullable=False)

    share_percentage = Column(Float, default=100.0)
    ownership_type = Column(String(50))  # pleine propriété, usufruit, nue-propriété
    since_date = Column(Date)
    acquisition_price = Column(Float)
    source = Column(String(50))  # "cadastre", "dvf", "inferred"

    property = relationship("Property", back_populates="ownerships")
    owner = relationship("Owner", back_populates="properties")

    __table_args__ = (
        Index("idx_ownership_property", "property_id"),
        Index("idx_ownership_owner", "owner_id"),
    )


class PropertyTransaction(Base):
    """Transaction history for a property."""
    __tablename__ = "property_transactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    property_id = Column(UUID(as_uuid=True), ForeignKey("properties.id"))
    mutation_id = Column(String(50), index=True)
    date_mutation = Column(Date, nullable=False)
    prix = Column(Float, nullable=False)
    prix_m2 = Column(Float)
    nature_mutation = Column(String(100))
    seller_owner_id = Column(UUID(as_uuid=True), ForeignKey("owners.id"))
    buyer_owner_id = Column(UUID(as_uuid=True), ForeignKey("owners.id"))

    property = relationship("Property", back_populates="transactions")

    __table_args__ = (
        Index("idx_prop_transactions_property", "property_id"),
        Index("idx_prop_transactions_date", "date_mutation"),
    )


class OwnershipNetwork(Base):
    """Pre-computed ownership network edges for graph visualization."""
    __tablename__ = "ownership_network"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_owner_id = Column(UUID(as_uuid=True), ForeignKey("owners.id"), nullable=False)
    target_owner_id = Column(UUID(as_uuid=True), ForeignKey("owners.id"))
    property_id = Column(UUID(as_uuid=True), ForeignKey("properties.id"))
    edge_type = Column(String(50))  # "co-owner", "successive-buyer", "related-company"
    weight = Column(Float, default=1.0)  # nb of shared properties
    metadata = Column(JSONB)

    __table_args__ = (
        Index("idx_network_source", "source_owner_id"),
        Index("idx_network_target", "target_owner_id"),
    )
