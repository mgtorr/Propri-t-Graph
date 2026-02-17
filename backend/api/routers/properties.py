from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import Optional
from api.database import get_db

router = APIRouter(prefix="/properties", tags=["Properties & Transactions"])


@router.get("/transactions")
async def get_transactions(
    code_commune: Optional[str] = Query(None),
    code_departement: Optional[str] = Query(None),
    type_local: Optional[str] = Query(None),
    year: Optional[int] = Query(None),
    min_prix: Optional[float] = Query(None),
    max_prix: Optional[float] = Query(None),
    min_surface: Optional[float] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=10, le=500),
    db: AsyncSession = Depends(get_db),
):
    """List property transactions with filters. Paginated."""
    conditions = ["1=1"]
    params = {"offset": (page - 1) * page_size, "limit": page_size}

    if code_commune:
        conditions.append("code_commune = :code_commune")
        params["code_commune"] = code_commune
    if code_departement:
        conditions.append("code_departement = :code_departement")
        params["code_departement"] = code_departement
    if type_local:
        conditions.append("type_local = :type_local")
        params["type_local"] = type_local
    if year:
        conditions.append("EXTRACT(YEAR FROM date_mutation) = :year")
        params["year"] = year
    if min_prix:
        conditions.append("valeur_fonciere >= :min_prix")
        params["min_prix"] = min_prix
    if max_prix:
        conditions.append("valeur_fonciere <= :max_prix")
        params["max_prix"] = max_prix
    if min_surface:
        conditions.append("surface_reelle_bati >= :min_surface")
        params["min_surface"] = min_surface

    where = " AND ".join(conditions)

    count_query = f"SELECT COUNT(*) FROM transactions WHERE {where}"
    data_query = f"""
        SELECT
            mutation_id, date_mutation, nature_mutation, valeur_fonciere,
            adresse_numero, adresse_nom_voie, code_postal, commune, code_commune,
            type_local, surface_reelle_bati, nombre_pieces_principales,
            prix_m2, latitude, longitude, id_parcelle
        FROM transactions
        WHERE {where}
        ORDER BY date_mutation DESC
        LIMIT :limit OFFSET :offset
    """

    try:
        total = (await db.execute(text(count_query), params)).scalar()
        result = await db.execute(text(data_query), params)
        rows = result.fetchall()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size if total else 0,
        "transactions": [
            {
                "mutation_id": r[0],
                "date_mutation": r[1].isoformat() if r[1] else None,
                "nature_mutation": r[2],
                "valeur_fonciere": float(r[3]) if r[3] else None,
                "adresse": f"{r[4] or ''} {r[5] or ''}".strip(),
                "code_postal": r[6],
                "commune": r[7],
                "code_commune": r[8],
                "type_local": r[9],
                "surface_m2": float(r[10]) if r[10] else None,
                "nb_pieces": int(r[11]) if r[11] else None,
                "prix_m2": float(r[12]) if r[12] else None,
                "latitude": float(r[13]) if r[13] else None,
                "longitude": float(r[14]) if r[14] else None,
                "parcelle_id": r[15],
            }
            for r in rows
        ],
    }


@router.get("/parcelle/{parcelle_id}")
async def get_parcelle_history(
    parcelle_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get full transaction history for a specific cadastral parcel."""
    query = """
        SELECT
            mutation_id, date_mutation, nature_mutation, valeur_fonciere,
            type_local, surface_reelle_bati, nombre_pieces_principales,
            prix_m2, commune, code_commune
        FROM transactions
        WHERE id_parcelle = :parcelle_id
        ORDER BY date_mutation
    """

    try:
        result = await db.execute(text(query), {"parcelle_id": parcelle_id})
        rows = result.fetchall()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    if not rows:
        raise HTTPException(status_code=404, detail="Parcelle not found")

    transactions = [
        {
            "mutation_id": r[0],
            "date": r[1].isoformat() if r[1] else None,
            "nature": r[2],
            "prix": float(r[3]) if r[3] else None,
            "type_local": r[4],
            "surface_m2": float(r[5]) if r[5] else None,
            "nb_pieces": int(r[6]) if r[6] else None,
            "prix_m2": float(r[7]) if r[7] else None,
            "commune": r[8],
            "code_commune": r[9],
        }
        for r in rows
    ]

    # Compute flipping stats
    flip_info = None
    if len(transactions) >= 2:
        first = transactions[0]
        last = transactions[-1]
        if first["prix"] and last["prix"] and first["prix"] > 0:
            total_gain_pct = (last["prix"] - first["prix"]) / first["prix"] * 100
            flip_info = {
                "nb_mutations": len(transactions),
                "prix_premier": first["prix"],
                "prix_dernier": last["prix"],
                "gain_total_pct": round(total_gain_pct, 1),
                "date_premiere_mutation": first["date"],
                "date_derniere_mutation": last["date"],
            }

    return {
        "parcelle_id": parcelle_id,
        "transactions": transactions,
        "flip_analysis": flip_info,
    }


@router.get("/stats/commune/{code_commune}")
async def get_commune_stats(
    code_commune: str,
    db: AsyncSession = Depends(get_db),
):
    """Summary statistics for a commune."""
    query = """
        SELECT
            commune,
            code_commune,
            code_departement,
            COUNT(*) AS total_transactions,
            MIN(date_mutation) AS first_transaction,
            MAX(date_mutation) AS last_transaction,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY prix_m2) FILTER (
                WHERE type_local = 'Appartement' AND prix_m2 > 0
            ) AS prix_median_appart,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY prix_m2) FILTER (
                WHERE type_local = 'Maison' AND prix_m2 > 0
            ) AS prix_median_maison,
            COUNT(*) FILTER (WHERE type_local = 'Appartement') AS nb_apparts,
            COUNT(*) FILTER (WHERE type_local = 'Maison') AS nb_maisons
        FROM transactions
        WHERE code_commune = :code_commune
        GROUP BY commune, code_commune, code_departement
    """

    try:
        result = await db.execute(text(query), {"code_commune": code_commune})
        row = result.fetchone()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    if not row:
        raise HTTPException(status_code=404, detail="Commune not found")

    return {
        "commune": row[0],
        "code_commune": row[1],
        "code_departement": row[2],
        "total_transactions": int(row[3]),
        "periode": {
            "debut": row[4].isoformat() if row[4] else None,
            "fin": row[5].isoformat() if row[5] else None,
        },
        "prix_median_m2": {
            "appartement": round(float(row[6]), 0) if row[6] else None,
            "maison": round(float(row[7]), 0) if row[7] else None,
        },
        "nb_transactions": {
            "appartements": int(row[8]),
            "maisons": int(row[9]),
        },
    }
