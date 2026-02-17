"""
Cadastral data processor.
Downloads and processes French cadastre (land registry) data from data.gouv.fr.

Source: https://cadastre.data.gouv.fr/data/etalab-cadastre/latest/geojson/
Provides: parcel geometries, building footprints, and owner information.
"""
import asyncio
import httpx
import json
import geopandas as gpd
import pandas as pd
from pathlib import Path
from loguru import logger
from shapely.geometry import shape
from typing import Optional
import asyncpg


CADASTRE_BASE = "https://cadastre.data.gouv.fr/data/etalab-cadastre/latest/geojson/communes"
RAW_CADASTRE_DIR = Path("/data/raw/cadastre")


class CadastralProcessor:
    """
    Downloads and processes cadastral (land registry) data.
    Links cadastral parcels to DVF transactions for ownership tracking.
    """

    def __init__(self, db_url: str):
        self.db_url = db_url.replace("+asyncpg", "").replace("postgresql+asyncpg", "postgresql")
        RAW_CADASTRE_DIR.mkdir(parents=True, exist_ok=True)

    async def process_commune(self, code_commune: str, force: bool = False) -> dict:
        """Download and process cadastral data for a commune."""
        dept = code_commune[:2] if len(code_commune) == 5 else code_commune[:3]

        # Download parcelles (land parcel boundaries)
        parcelles_path = await self._download_layer(code_commune, "parcelles", force)
        batiments_path = await self._download_layer(code_commune, "batiments", force)

        results = {"commune": code_commune, "parcelles": 0, "batiments": 0}

        if parcelles_path:
            n = await self._ingest_parcelles(parcelles_path, code_commune)
            results["parcelles"] = n

        if batiments_path:
            n = await self._ingest_batiments(batiments_path, code_commune)
            results["batiments"] = n

        return results

    async def process_departement(self, code_dept: str) -> dict:
        """Process all communes in a department."""
        communes = await self._get_communes_list(code_dept)
        logger.info(f"Processing {len(communes)} communes in dept {code_dept}")

        total = {"parcelles": 0, "batiments": 0, "communes": 0}

        for commune in communes:
            try:
                result = await self.process_commune(commune["code"])
                total["parcelles"] += result["parcelles"]
                total["batiments"] += result["batiments"]
                total["communes"] += 1
            except Exception as e:
                logger.error(f"Failed commune {commune['code']}: {e}")

        return total

    async def _download_layer(
        self,
        code_commune: str,
        layer: str,
        force: bool = False,
    ) -> Optional[Path]:
        """Download a GeoJSON layer (parcelles or batiments) for a commune."""
        dept = code_commune[:2]
        filename = f"{code_commune}-{layer}.json.gz"
        local_path = RAW_CADASTRE_DIR / dept / filename

        if local_path.exists() and not force:
            return local_path

        url = f"{CADASTRE_BASE}/{dept}/{code_commune}/{layer}.json.gz"
        local_path.parent.mkdir(parents=True, exist_ok=True)

        async with httpx.AsyncClient(timeout=120.0) as client:
            try:
                response = await client.get(url)
                if response.status_code == 404:
                    return None
                response.raise_for_status()

                with open(local_path, "wb") as f:
                    f.write(response.content)

                return local_path

            except httpx.HTTPError as e:
                logger.error(f"Download failed for {url}: {e}")
                return None

    async def _ingest_parcelles(self, path: Path, code_commune: str) -> int:
        """Ingest parcelle boundaries into properties table."""
        try:
            gdf = gpd.read_file(path).to_crs("EPSG:4326")
        except Exception as e:
            logger.error(f"Failed to read parcelles {path}: {e}")
            return 0

        if gdf.empty:
            return 0

        async with await asyncpg.connect(self.db_url) as conn:
            inserted = 0

            for _, row in gdf.iterrows():
                try:
                    parcelle_id = row.get("id", "")
                    if not parcelle_id:
                        continue

                    geom_json = row.geometry.__geo_interface__ if row.geometry else None
                    geom_wkt = row.geometry.wkt if row.geometry else None
                    centroid = row.geometry.centroid if row.geometry else None

                    await conn.execute("""
                        INSERT INTO properties (
                            parcelle_id, commune_code, commune_name, departement,
                            section, numero_plan, surface_parcelle, longitude, latitude,
                            geom, created_at
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9,
                            ST_GeomFromText($10, 4326), NOW())
                        ON CONFLICT (parcelle_id) DO UPDATE SET
                            surface_parcelle = EXCLUDED.surface_parcelle,
                            geom = EXCLUDED.geom,
                            updated_at = NOW()
                    """,
                        parcelle_id,
                        code_commune,
                        row.get("commune", ""),
                        code_commune[:2],
                        row.get("section", ""),
                        row.get("numero", ""),
                        float(row.get("contenance", 0)) if row.get("contenance") else None,
                        centroid.x if centroid else None,
                        centroid.y if centroid else None,
                        geom_wkt,
                    )
                    inserted += 1

                except Exception as e:
                    logger.debug(f"Row insert error: {e}")

            return inserted

    async def _ingest_batiments(self, path: Path, code_commune: str) -> int:
        """Ingest building footprints and update properties with building info."""
        try:
            gdf = gpd.read_file(path).to_crs("EPSG:4326")
        except Exception as e:
            logger.error(f"Failed to read batiments {path}: {e}")
            return 0

        if gdf.empty:
            return 0

        # Aggregate building stats per parcelle
        async with await asyncpg.connect(self.db_url) as conn:
            processed = 0
            for parcelle_id, group in gdf.groupby("id_parcelle") if "id_parcelle" in gdf.columns else []:
                total_surface = group.geometry.area.sum() * 10000  # approx m2 from deg2

                await conn.execute("""
                    UPDATE properties SET
                        nb_batiments = $2,
                        surface_bati = $3
                    WHERE parcelle_id = $1
                """, parcelle_id, len(group), float(total_surface))
                processed += 1

            return processed

    async def link_dvf_to_cadastre(self, code_commune: Optional[str] = None) -> int:
        """
        Spatial join: link DVF transactions to cadastral parcels by id_parcelle.
        This enables ownership tracking through successive transactions.
        """
        async with await asyncpg.connect(self.db_url) as conn:
            query = """
                UPDATE transactions t
                SET
                    surface_terrain = COALESCE(t.surface_terrain, p.surface_parcelle)
                FROM properties p
                WHERE t.id_parcelle = p.parcelle_id
                  AND t.id_parcelle IS NOT NULL
            """
            if code_commune:
                query += " AND t.code_commune = $1"
                result = await conn.execute(query + " RETURNING 1", code_commune)
            else:
                result = await conn.execute(query)

            count = int(result.split(" ")[-1]) if isinstance(result, str) else 0
            logger.info(f"Linked {count} DVF transactions to cadastral parcels")
            return count

    async def detect_ownership_from_dvf(self) -> int:
        """
        Infer ownership from DVF mutation chains.
        The last buyer of a property is its likely current owner.
        Creates Owner and PropertyOwnership records from transaction data.
        """
        async with await asyncpg.connect(self.db_url) as conn:
            # Get last transaction per parcelle (most recent buyer = current owner)
            await conn.execute("""
                INSERT INTO properties (parcelle_id, commune_code, departement)
                SELECT DISTINCT
                    id_parcelle,
                    code_commune,
                    code_departement
                FROM transactions
                WHERE id_parcelle IS NOT NULL
                ON CONFLICT (parcelle_id) DO UPDATE SET
                    commune_code = EXCLUDED.commune_code
            """)

            # Create synthetic ownership records from DVF
            # In production, MAJIC (tax data) would give real ownership;
            # DVF gives us buying history as a proxy
            result = await conn.execute("""
                WITH latest_mutations AS (
                    SELECT DISTINCT ON (id_parcelle)
                        id_parcelle,
                        mutation_id,
                        date_mutation,
                        valeur_fonciere,
                        nature_mutation
                    FROM transactions
                    WHERE id_parcelle IS NOT NULL
                      AND nature_mutation ILIKE '%vente%'
                    ORDER BY id_parcelle, date_mutation DESC
                )
                INSERT INTO property_transactions (property_id, mutation_id, date_mutation, prix, nature_mutation)
                SELECT
                    p.id,
                    lm.mutation_id,
                    lm.date_mutation,
                    lm.valeur_fonciere,
                    lm.nature_mutation
                FROM latest_mutations lm
                JOIN properties p ON p.parcelle_id = lm.id_parcelle
                ON CONFLICT DO NOTHING
            """)

            count = int(result.split(" ")[-1]) if isinstance(result, str) else 0
            logger.info(f"Created {count} property transaction records")
            return count

    async def _get_communes_list(self, code_dept: str) -> list[dict]:
        """Get list of communes from geo.api.gouv.fr."""
        url = f"https://geo.api.gouv.fr/departements/{code_dept}/communes"
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(url, params={"fields": "code,nom"})
                response.raise_for_status()
                return response.json()
            except httpx.HTTPError as e:
                logger.error(f"Failed to get communes for dept {code_dept}: {e}")
                return []


if __name__ == "__main__":
    import sys, os
    db_url = os.environ.get("DATABASE_URL", "postgresql://propriete:propriete@localhost:5432/propriete_graph")
    dept = sys.argv[1] if len(sys.argv) > 1 else "75"

    processor = CadastralProcessor(db_url)
    asyncio.run(processor.process_departement(dept))
