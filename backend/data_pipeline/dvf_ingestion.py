"""
DVF (Demandes de Valeurs Foncières) data ingestion pipeline.
Downloads and processes mutation data from data.gouv.fr.

Data covers all real property transactions in France from 2014.
Source: https://www.data.gouv.fr/fr/datasets/demandes-de-valeurs-foncieres/
~2M+ records per year, updated annually.
"""
import os
import io
import hashlib
import asyncio
import httpx
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
from loguru import logger
from tqdm import tqdm
import asyncpg


DVF_BASE_URL = "https://files.data.gouv.fr/geo-dvf/latest/csv"
RAW_DATA_DIR = Path("/data/raw/dvf")
PROCESSED_DIR = Path("/data/processed")

# geo-dvf provides geocoded data with lat/long
DEPARTEMENTS = [
    "01", "02", "03", "04", "05", "06", "07", "08", "09",
    "10", "11", "12", "13", "14", "15", "16", "17", "18", "19",
    "21", "22", "23", "24", "25", "26", "27", "28", "29",
    "30", "31", "32", "33", "34", "35", "36", "37", "38", "39",
    "40", "41", "42", "43", "44", "45", "46", "47", "48", "49",
    "50", "51", "52", "53", "54", "55", "56", "57", "58", "59",
    "60", "61", "62", "63", "64", "65", "66", "67", "68", "69",
    "70", "71", "72", "73", "74", "75", "76", "77", "78", "79",
    "80", "81", "82", "83", "84", "85", "86", "87", "88", "89",
    "90", "91", "92", "93", "94", "95",
    "971", "972", "973", "974", "976",  # DOM
]

COLUMN_MAPPING = {
    "id_mutation": "mutation_id",
    "date_mutation": "date_mutation",
    "nature_mutation": "nature_mutation",
    "valeur_fonciere": "valeur_fonciere",
    "adresse_numero": "adresse_numero",
    "adresse_suffixe": "adresse_suffixe",
    "adresse_nom_voie": "adresse_nom_voie",
    "adresse_code_voie": "adresse_code_voie",
    "code_postal": "code_postal",
    "code_commune": "code_commune",
    "nom_commune": "commune",
    "code_departement": "code_departement",
    "ancien_code_commune": "ancien_code_commune",
    "ancien_nom_commune": "ancien_nom_commune",
    "id_parcelle": "id_parcelle",
    "numero_volume": "numero_volume",
    "lot1_numero": "lot1_numero",
    "lot1_surface_carrez": "lot1_surface_carrez",
    "lot2_numero": "lot2_numero",
    "lot2_surface_carrez": "lot2_surface_carrez",
    "lot3_numero": "lot3_numero",
    "lot3_surface_carrez": "lot3_surface_carrez",
    "lot4_numero": "lot4_numero",
    "lot4_surface_carrez": "lot4_surface_carrez",
    "lot5_numero": "lot5_numero",
    "lot5_surface_carrez": "lot5_surface_carrez",
    "nombre_lots": "nombre_lots",
    "code_type_local": "code_type_local",
    "type_local": "type_local",
    "identifiant_local": "identifiant_local",
    "surface_reelle_bati": "surface_reelle_bati",
    "nombre_pieces_principales": "nombre_pieces_principales",
    "code_nature_culture": "code_nature_culture",
    "nature_culture": "nature_culture",
    "code_nature_culture_speciale": "code_nature_culture_speciale",
    "nature_culture_speciale": "nature_culture_speciale",
    "surface_terrain": "surface_terrain",
    "longitude": "longitude",
    "latitude": "latitude",
}


class DVFIngestion:
    """Download and ingest DVF data into PostgreSQL."""

    def __init__(self, db_url: str):
        self.db_url = db_url
        RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
        PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    async def run(
        self,
        years: list[int] = None,
        departements: list[str] = None,
        force_download: bool = False,
    ):
        """Main ingestion pipeline."""
        years = years or list(range(2018, datetime.now().year + 1))
        departements = departements or DEPARTEMENTS

        logger.info(f"Starting DVF ingestion: {len(years)} years × {len(departements)} departments")
        total_inserted = 0

        async with await asyncpg.connect(self.db_url.replace("+asyncpg", "")) as conn:
            await self._ensure_schema(conn)

            for year in years:
                for dept in departements:
                    try:
                        csv_path = await self._download_file(year, dept, force_download)
                        if csv_path:
                            n = await self._process_and_insert(conn, csv_path, year, dept)
                            total_inserted += n
                            logger.info(f"  Inserted {n:,} records for {dept}/{year}")
                    except Exception as e:
                        logger.error(f"  Failed {dept}/{year}: {e}")
                        continue

        logger.success(f"DVF ingestion complete: {total_inserted:,} total records")
        return total_inserted

    async def _download_file(self, year: int, dept: str, force: bool) -> Path | None:
        """Download DVF CSV file for a year/department combination."""
        filename = f"{dept}.csv.gz"
        local_path = RAW_DATA_DIR / str(year) / filename

        if local_path.exists() and not force:
            logger.debug(f"  Using cached: {local_path}")
            return local_path

        url = f"{DVF_BASE_URL}/{year}/departements/{filename}"
        local_path.parent.mkdir(parents=True, exist_ok=True)

        logger.info(f"  Downloading {url}")
        async with httpx.AsyncClient(timeout=300.0, follow_redirects=True) as client:
            try:
                response = await client.get(url)
                if response.status_code == 404:
                    logger.debug(f"  Not found (may not exist for this year): {url}")
                    return None
                response.raise_for_status()

                with open(local_path, "wb") as f:
                    f.write(response.content)

                logger.debug(f"  Downloaded {len(response.content) / 1024:.1f} KB")
                return local_path

            except httpx.HTTPError as e:
                logger.warning(f"  HTTP error for {url}: {e}")
                return None

    async def _process_and_insert(
        self,
        conn: asyncpg.Connection,
        csv_path: Path,
        year: int,
        dept: str,
    ) -> int:
        """Process CSV and bulk-insert into transactions table."""
        try:
            df = pd.read_csv(
                csv_path,
                compression="gzip" if str(csv_path).endswith(".gz") else None,
                dtype=str,
                low_memory=False,
                sep=",",
            )
        except Exception as e:
            logger.error(f"  Failed to read {csv_path}: {e}")
            return 0

        # Rename columns
        df = df.rename(columns={k: v for k, v in COLUMN_MAPPING.items() if k in df.columns})

        # Type conversions
        df = self._clean_dataframe(df)

        if df.empty:
            return 0

        # Compute prix_m2
        df["prix_m2"] = np.where(
            (df["surface_reelle_bati"] > 0) & (df["valeur_fonciere"] > 0),
            df["valeur_fonciere"] / df["surface_reelle_bati"],
            None,
        )

        # Filter out unrealistic values
        df = df[
            (df["valeur_fonciere"].isna() | (df["valeur_fonciere"] > 1000)) &
            (df["prix_m2"].isna() | ((df["prix_m2"] > 100) & (df["prix_m2"] < 100000)))
        ]

        # Bulk insert using COPY
        records = df.to_dict("records")
        inserted = 0

        # Batch inserts of 5000 rows
        batch_size = 5000
        for i in range(0, len(records), batch_size):
            batch = records[i:i + batch_size]
            try:
                await self._bulk_insert(conn, batch)
                inserted += len(batch)
            except Exception as e:
                logger.warning(f"  Batch insert error: {e}")

        return inserted

    def _clean_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Type conversions and cleaning."""
        numeric_cols = [
            "valeur_fonciere", "surface_reelle_bati", "surface_terrain",
            "lot1_surface_carrez", "lot2_surface_carrez", "lot3_surface_carrez",
            "lot4_surface_carrez", "lot5_surface_carrez", "longitude", "latitude",
        ]
        int_cols = ["nombre_lots", "nombre_pieces_principales"]
        date_cols = ["date_mutation"]

        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(
                    df[col].str.replace(",", ".") if df[col].dtype == object else df[col],
                    errors="coerce"
                )

        for col in int_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")

        for col in date_cols:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors="coerce", dayfirst=True)

        # Add unique mutation_id if missing
        if "mutation_id" not in df.columns or df["mutation_id"].isna().all():
            df["mutation_id"] = df.apply(
                lambda r: hashlib.md5(
                    f"{r.get('id_parcelle','')}{r.get('date_mutation','')}{r.get('valeur_fonciere','')}".encode()
                ).hexdigest()[:20],
                axis=1,
            )

        return df.dropna(subset=["date_mutation", "valeur_fonciere"])

    async def _bulk_insert(self, conn: asyncpg.Connection, records: list[dict]):
        """Insert records using PostgreSQL COPY for performance."""
        cols = [
            "mutation_id", "date_mutation", "nature_mutation", "valeur_fonciere",
            "adresse_numero", "adresse_suffixe", "adresse_nom_voie", "adresse_code_voie",
            "code_postal", "commune", "code_commune", "code_departement",
            "id_parcelle", "code_type_local", "type_local", "surface_reelle_bati",
            "nombre_pieces_principales", "surface_terrain", "longitude", "latitude",
            "prix_m2", "nombre_lots",
        ]

        def safe_get(r, k):
            v = r.get(k)
            if pd.isna(v) if isinstance(v, float) else v is None:
                return None
            return v

        rows = [tuple(safe_get(r, c) for c in cols) for r in records]

        insert_sql = f"""
            INSERT INTO transactions ({', '.join(cols)})
            VALUES ({', '.join(['$' + str(i+1) for i in range(len(cols))])})
            ON CONFLICT (mutation_id) DO NOTHING
        """
        await conn.executemany(insert_sql, rows)

    async def _ensure_schema(self, conn: asyncpg.Connection):
        """Create PostGIS extension and schema if not exists."""
        await conn.execute("CREATE EXTENSION IF NOT EXISTS postgis")
        await conn.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
        logger.debug("Schema extensions verified")

    async def compute_price_indices(self, conn: asyncpg.Connection):
        """Pre-compute aggregated price indices for faster queries."""
        logger.info("Computing price indices...")
        await conn.execute("""
            INSERT INTO price_indices (
                code_commune, commune, code_departement, type_local,
                year, quarter, nb_transactions,
                prix_median_m2, prix_moyen_m2, prix_min_m2, prix_max_m2,
                surface_mediane, valeur_totale_mediane, computed_at
            )
            SELECT
                code_commune, commune, code_departement, type_local,
                EXTRACT(YEAR FROM date_mutation)::int AS year,
                EXTRACT(QUARTER FROM date_mutation)::int AS quarter,
                COUNT(*) AS nb_transactions,
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY prix_m2) AS prix_median_m2,
                AVG(prix_m2) AS prix_moyen_m2,
                MIN(prix_m2) AS prix_min_m2,
                MAX(prix_m2) AS prix_max_m2,
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY surface_reelle_bati) AS surface_mediane,
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY valeur_fonciere) AS valeur_totale_mediane,
                NOW()
            FROM transactions
            WHERE prix_m2 > 0 AND prix_m2 < 50000
            GROUP BY code_commune, commune, code_departement, type_local,
                     EXTRACT(YEAR FROM date_mutation), EXTRACT(QUARTER FROM date_mutation)
            ON CONFLICT DO NOTHING
        """)
        logger.success("Price indices computed")


async def main():
    import sys
    db_url = os.environ.get(
        "DATABASE_URL",
        "postgresql://propriete:propriete@localhost:5432/propriete_graph"
    )

    years = [int(y) for y in sys.argv[1:]] if len(sys.argv) > 1 else [2023, 2024]
    depts = os.environ.get("DEPARTMENTS", "").split(",") if os.environ.get("DEPARTMENTS") else None

    pipeline = DVFIngestion(db_url)
    await pipeline.run(years=years, departements=depts)


if __name__ == "__main__":
    asyncio.run(main())
