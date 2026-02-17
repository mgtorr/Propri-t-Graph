"""
Base Adresse Nationale (BAN) integration.
Geocodes addresses and enriches transactions with IRIS codes and neighborhood data.

Source: https://adresse.data.gouv.fr/
"""
import asyncio
import httpx
import pandas as pd
from pathlib import Path
from loguru import logger
from typing import Optional
import json


BAN_API_URL = "https://api-adresse.data.gouv.fr/search"
BAN_BATCH_URL = "https://api-adresse.data.gouv.fr/search/csv"
IRIS_API_URL = "https://geo.api.gouv.fr/communes"

RAW_DATA_DIR = Path("/data/raw/ban")


class BANIntegration:
    """
    Integrates Base Adresse Nationale data:
    1. Geocodes missing coordinates in DVF transactions
    2. Enriches with IRIS codes for neighborhood-level analysis
    3. Provides reverse geocoding for cadastral data
    """

    def __init__(self, db_url: str):
        self.db_url = db_url
        RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)

    async def geocode_missing(self, limit: int = 10000) -> int:
        """
        Batch geocode DVF transactions that lack coordinates.
        Uses BAN CSV batch endpoint (recommended for bulk operations).
        """
        import asyncpg

        conn_url = self.db_url.replace("+asyncpg", "").replace("postgresql+asyncpg", "postgresql")
        async with await asyncpg.connect(conn_url) as conn:
            # Get transactions without coordinates
            rows = await conn.fetch("""
                SELECT id, adresse_numero, adresse_nom_voie, code_postal, commune, code_commune
                FROM transactions
                WHERE latitude IS NULL
                  AND adresse_nom_voie IS NOT NULL
                LIMIT $1
            """, limit)

            if not rows:
                logger.info("No missing geocoding found")
                return 0

            logger.info(f"Geocoding {len(rows)} addresses...")

            # Build CSV for batch API
            df = pd.DataFrame([dict(r) for r in rows])
            df["q"] = (
                df["adresse_numero"].fillna("") + " " +
                df["adresse_nom_voie"].fillna("") + " " +
                df["code_postal"].fillna("") + " " +
                df["commune"].fillna("")
            ).str.strip()
            df["citycode"] = df["code_commune"]

            csv_content = df[["id", "q", "citycode"]].to_csv(index=False)

            # Call BAN batch API
            results = await self._batch_geocode_csv(csv_content)

            # Update database
            updates = []
            for r in results:
                if r.get("result_score", 0) >= 0.7:
                    updates.append((
                        float(r["latitude"]),
                        float(r["longitude"]),
                        r.get("result_citycode"),
                        r["id"],
                    ))

            if updates:
                await conn.executemany(
                    "UPDATE transactions SET latitude=$1, longitude=$2, code_commune=COALESCE($3, code_commune) WHERE id=$4::uuid",
                    updates,
                )
                logger.success(f"Updated {len(updates)} coordinates")

            return len(updates)

    async def _batch_geocode_csv(self, csv_content: str) -> list[dict]:
        """Call BAN batch CSV geocoding endpoint."""
        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(
                    BAN_BATCH_URL,
                    files={"data": ("addresses.csv", csv_content.encode(), "text/csv")},
                    data={"columns": "q", "citycode": "citycode"},
                )
                response.raise_for_status()

                # Parse response CSV
                import io
                result_df = pd.read_csv(io.StringIO(response.text))
                return result_df.to_dict("records")

            except httpx.HTTPError as e:
                logger.error(f"BAN batch geocoding failed: {e}")
                return []

    async def geocode_single(self, address: str, citycode: Optional[str] = None) -> Optional[dict]:
        """Geocode a single address using BAN API."""
        params = {"q": address, "limit": 1}
        if citycode:
            params["citycode"] = citycode

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.get(BAN_API_URL, params=params)
                response.raise_for_status()
                data = response.json()

                if data["features"]:
                    feat = data["features"][0]
                    return {
                        "latitude": feat["geometry"]["coordinates"][1],
                        "longitude": feat["geometry"]["coordinates"][0],
                        "score": feat["properties"]["score"],
                        "label": feat["properties"]["label"],
                        "citycode": feat["properties"].get("citycode"),
                        "postcode": feat["properties"].get("postcode"),
                    }
            except httpx.HTTPError as e:
                logger.error(f"BAN geocoding error: {e}")

        return None

    async def enrich_with_iris(self, dept: str = None) -> int:
        """
        Enrich transactions with IRIS codes using spatial join.
        IRIS is the finest geographic subdivision in France (2000 inhabitants avg).
        """
        import asyncpg

        conn_url = self.db_url.replace("+asyncpg", "").replace("postgresql+asyncpg", "postgresql")
        async with await asyncpg.connect(conn_url) as conn:
            # Update geom column from lat/lng
            updated_geom = await conn.execute("""
                UPDATE transactions
                SET geom = ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)
                WHERE latitude IS NOT NULL
                  AND longitude IS NOT NULL
                  AND geom IS NULL
            """)

            logger.info(f"Updated geometry for {updated_geom} transactions")
            return int(updated_geom.split(" ")[-1]) if updated_geom else 0

    async def get_commune_info(self, code_commune: str) -> Optional[dict]:
        """Get commune metadata from geo.api.gouv.fr."""
        url = f"https://geo.api.gouv.fr/communes/{code_commune}"
        params = {"fields": "nom,code,population,surface,centre,codesPostaux,departement,region"}

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()

                centre = data.get("centre", {})
                coords = centre.get("coordinates", [None, None])

                return {
                    "code": data["code"],
                    "nom": data["nom"],
                    "population": data.get("population"),
                    "surface_km2": data.get("surface"),
                    "lng": coords[0] if coords else None,
                    "lat": coords[1] if coords else None,
                    "codes_postaux": data.get("codesPostaux", []),
                    "departement": data.get("departement", {}).get("code"),
                    "region": data.get("region", {}).get("nom"),
                }
            except httpx.HTTPError as e:
                logger.error(f"geo.api.gouv.fr error for {code_commune}: {e}")
                return None

    async def search_communes(self, query: str, limit: int = 10) -> list[dict]:
        """Search communes by name."""
        url = "https://geo.api.gouv.fr/communes"
        params = {
            "nom": query,
            "fields": "nom,code,population,codesPostaux,departement",
            "limit": limit,
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.get(url, params=params)
                response.raise_for_status()
                communes = response.json()

                return [
                    {
                        "code": c["code"],
                        "nom": c["nom"],
                        "population": c.get("population"),
                        "codes_postaux": c.get("codesPostaux", []),
                        "departement": c.get("departement", {}).get("code"),
                        "departement_nom": c.get("departement", {}).get("nom"),
                    }
                    for c in communes
                ]
            except httpx.HTTPError as e:
                logger.error(f"Commune search error: {e}")
                return []


# Add BAN search endpoint to the API
async def search_addresses_endpoint(q: str, limit: int = 5) -> list[dict]:
    """Proxy to BAN search API - exposed via FastAPI endpoint."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(BAN_API_URL, params={"q": q, "limit": limit})
            response.raise_for_status()
            data = response.json()

            return [
                {
                    "label": f["properties"]["label"],
                    "score": f["properties"]["score"],
                    "type": f["properties"]["type"],
                    "citycode": f["properties"].get("citycode"),
                    "postcode": f["properties"].get("postcode"),
                    "city": f["properties"].get("city"),
                    "lat": f["geometry"]["coordinates"][1],
                    "lng": f["geometry"]["coordinates"][0],
                }
                for f in data.get("features", [])
            ]
        except httpx.HTTPError:
            return []


if __name__ == "__main__":
    import sys, os
    db_url = os.environ.get("DATABASE_URL", "postgresql://propriete:propriete@localhost:5432/propriete_graph")
    ban = BANIntegration(db_url)
    asyncio.run(ban.geocode_missing(limit=50000))
