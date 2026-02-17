from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from api.database import get_db
from api.services.price_analysis import PriceAnalysisService
from api.services.speculation_detector import SpeculationDetector

router = APIRouter(prefix="/analysis", tags=["Analysis"])


@router.get("/price-history")
async def get_price_history(
    code_commune: Optional[str] = Query(None, description="INSEE commune code (5 digits)"),
    iris_code: Optional[str] = Query(None, description="IRIS code (9 digits)"),
    type_local: str = Query("Appartement", enum=["Appartement", "Maison", "Local industriel", "Dépendance"]),
    start_year: int = Query(2018, ge=2014, le=2024),
    db: AsyncSession = Depends(get_db),
):
    """Get monthly price history for a commune or IRIS zone."""
    if not code_commune and not iris_code:
        raise HTTPException(status_code=400, detail="Provide code_commune or iris_code")

    service = PriceAnalysisService(db)
    df = await service.get_price_history(
        code_commune=code_commune,
        iris_code=iris_code,
        type_local=type_local,
        start_year=start_year,
    )

    if df.empty:
        raise HTTPException(status_code=404, detail="No data found for this zone")

    return {"data": service._format_historical(df), "type_local": type_local}


@router.get("/price-prediction")
async def predict_prices(
    code_commune: str = Query(..., description="INSEE commune code"),
    type_local: str = Query("Appartement", enum=["Appartement", "Maison"]),
    horizon_months: int = Query(12, ge=3, le=36),
    db: AsyncSession = Depends(get_db),
):
    """
    Predict price evolution for the next N months.
    Uses Prophet time-series model with yearly seasonality.
    """
    service = PriceAnalysisService(db)
    result = await service.predict_prices(
        code_commune=code_commune,
        type_local=type_local,
        horizon_months=horizon_months,
    )

    if "error" in result:
        raise HTTPException(status_code=422, detail=result["error"])

    return result


@router.get("/heatmap")
async def get_heatmap(
    code_departement: str = Query(..., description="Department code (2 digits, e.g. '75')"),
    type_local: str = Query("Appartement"),
    year: int = Query(2023, ge=2014, le=2024),
    db: AsyncSession = Depends(get_db),
):
    """Get price heatmap data for all zones in a department."""
    service = PriceAnalysisService(db)
    data = await service.compute_neighborhood_heatmap(
        code_departement=code_departement,
        type_local=type_local,
        year=year,
    )
    return {"heatmap": data, "departement": code_departement, "year": year, "type_local": type_local}


@router.get("/evolution-ranking")
async def get_evolution_ranking(
    code_departement: str = Query(...),
    type_local: str = Query("Appartement"),
    top_n: int = Query(20, ge=5, le=50),
    db: AsyncSession = Depends(get_db),
):
    """Rank communes by price evolution - best and worst performers."""
    service = PriceAnalysisService(db)
    return await service.get_price_evolution_ranking(
        code_departement=code_departement,
        type_local=type_local,
        top_n=top_n,
    )


@router.get("/speculation/rapid-flips")
async def get_rapid_flips(
    code_commune: Optional[str] = Query(None),
    code_departement: Optional[str] = Query(None),
    min_gain_pct: float = Query(20.0, ge=5.0, le=100.0),
    max_hold_months: int = Query(24, ge=1, le=60),
    db: AsyncSession = Depends(get_db),
):
    """
    Detect rapid property flips (bought and resold at high profit within N months).
    Signals speculative investment pressure.
    """
    if not code_commune and not code_departement:
        raise HTTPException(status_code=400, detail="Provide code_commune or code_departement")

    detector = SpeculationDetector(db)
    flips = await detector.detect_rapid_flips(
        code_commune=code_commune,
        code_departement=code_departement,
        min_gain_pct=min_gain_pct,
        max_hold_months=max_hold_months,
    )
    return {
        "flips": flips,
        "nb_detected": len(flips),
        "params": {"min_gain_pct": min_gain_pct, "max_hold_months": max_hold_months},
    }


@router.get("/speculation/heatmap")
async def get_speculation_heatmap(
    code_departement: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Get speculation intensity map for all communes in a department."""
    detector = SpeculationDetector(db)
    data = await detector.get_speculation_heatmap(code_departement=code_departement)
    return {"heatmap": data, "departement": code_departement}


@router.get("/gentrification")
async def get_gentrification_index(
    code_commune: str = Query(..., description="INSEE commune code"),
    db: AsyncSession = Depends(get_db),
):
    """
    Compute gentrification index and displacement risk for a commune.
    Returns stage (stable/early/active/advanced), score, and evidence signals.
    """
    detector = SpeculationDetector(db)
    result = await detector.compute_gentrification_index(code_commune=code_commune)

    if "error" in result:
        raise HTTPException(status_code=422, detail=result["error"])

    return result


@router.get("/mass-acquisitions")
async def get_mass_acquisitions(
    code_departement: str = Query(...),
    min_properties: int = Query(5, ge=3, le=50),
    window_months: int = Query(24, ge=6, le=60),
    db: AsyncSession = Depends(get_db),
):
    """Detect concentrated acquisition patterns (potential institutional investors)."""
    detector = SpeculationDetector(db)
    acquisitions = await detector.detect_mass_acquisitions(
        code_departement=code_departement,
        min_properties=min_properties,
        window_months=window_months,
    )
    return {
        "acquisitions": acquisitions,
        "nb_detected": len(acquisitions),
    }
