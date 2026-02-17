from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from api.database import get_db
from api.services.opportunity_finder import OpportunityFinderService

router = APIRouter(prefix="/opportunities", tags=["First-Time Buyer"])


@router.get("/search")
async def search_opportunities(
    max_budget: float = Query(..., gt=50000, description="Maximum budget in euros"),
    surface_min: float = Query(40.0, ge=20, le=200, description="Minimum surface in m²"),
    type_local: str = Query("Appartement", enum=["Appartement", "Maison"]),
    departements: Optional[str] = Query(None, description="Comma-separated department codes, e.g. '75,92,93'"),
    prefer_stable_prices: bool = Query(True),
    limit: int = Query(20, ge=5, le=50),
    db: AsyncSession = Depends(get_db),
):
    """
    Find best opportunities for first-time buyers.
    Returns scored communes matching budget and surface constraints.
    """
    dept_list = [d.strip() for d in departements.split(",")] if departements else None

    service = OpportunityFinderService(db)
    return await service.find_opportunities(
        max_budget=max_budget,
        surface_min=surface_min,
        type_local=type_local,
        departements=dept_list,
        prefer_stable_prices=prefer_stable_prices,
        limit=limit,
    )


@router.get("/budget-simulation")
async def simulate_budget(
    salaire_mensuel_net: float = Query(..., gt=1000, description="Monthly net salary in euros"),
    apport: float = Query(0, ge=0, description="Personal contribution (apport) in euros"),
    duree_ans: int = Query(25, ge=10, le=30, description="Loan duration in years"),
    taux_interet: float = Query(0.038, ge=0.01, le=0.15, description="Annual interest rate"),
    departements: Optional[str] = Query(None, description="Comma-separated department codes"),
    db: AsyncSession = Depends(get_db),
):
    """
    Simulate borrowing capacity and find matching properties.
    French standard: max 35% debt-to-income ratio.
    """
    dept_list = [d.strip() for d in departements.split(",")] if departements else None

    service = OpportunityFinderService(db)
    return await service.get_budget_simulation(
        salaire_mensuel_net=salaire_mensuel_net,
        apport=apport,
        duree_ans=duree_ans,
        taux_interet=taux_interet,
        departements=dept_list,
    )


@router.get("/ptz-zones")
async def get_ptz_zones():
    """
    Return PTZ (Prêt à Taux Zéro) zone map.
    Helpful for first-time buyers to understand zero-rate loan eligibility.
    """
    from api.services.opportunity_finder import PTZ_ZONES, PTZ_ZONE_DEFAULT

    return {
        "zones": {
            "A": {
                "label": "Zone A / A bis",
                "description": "Paris, proche banlieue, Côte d'Azur",
                "departements": [k for k, v in PTZ_ZONES.items() if v in ("A", "Abis")],
            },
            "B1": {
                "label": "Zone B1",
                "description": "Grandes agglomérations >250k hab, outre-mer",
                "departements": [k for k, v in PTZ_ZONES.items() if v == "B1"],
            },
            "B2": {
                "label": "Zone B2",
                "description": "Agglomérations >50k hab",
                "departements": [k for k, v in PTZ_ZONES.items() if v == "B2"],
            },
            "C": {
                "label": "Zone C",
                "description": "Reste du territoire",
                "departements": [],  # Everything else
            },
        },
        "note": "Les zones PTZ déterminent les conditions d'éligibilité et les montants maximum du PTZ.",
        "source": "data.gouv.fr",
    }
