from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from api.database import get_db
from api.services.ownership_graph import OwnershipGraphService

router = APIRouter(prefix="/ownership", tags=["Ownership Network"])


@router.get("/network")
async def get_ownership_network(
    code_commune: Optional[str] = Query(None, description="INSEE commune code"),
    code_departement: Optional[str] = Query(None, description="Department code"),
    owner_id: Optional[str] = Query(None, description="Owner UUID for ego-network"),
    depth: int = Query(2, ge=1, le=3, description="Network expansion depth"),
    min_properties: int = Query(2, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
):
    """
    Build and return property ownership network as nodes + edges.
    Suitable for D3.js force-directed graph visualization.
    """
    if not any([code_commune, code_departement, owner_id]):
        raise HTTPException(
            status_code=400,
            detail="Provide one of: code_commune, code_departement, owner_id"
        )

    service = OwnershipGraphService(db)
    return await service.get_ownership_network(
        code_commune=code_commune,
        code_departement=code_departement,
        owner_id=owner_id,
        depth=depth,
        min_properties=min_properties,
    )


@router.get("/corporate-stats")
async def get_corporate_stats(
    code_commune: Optional[str] = Query(None),
    code_departement: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Breakdown of ownership by entity type (individual, SCI, company, public).
    Shows corporate vs. individual ownership concentration.
    """
    if not code_commune and not code_departement:
        raise HTTPException(status_code=400, detail="Provide code_commune or code_departement")

    service = OwnershipGraphService(db)
    return await service.get_corporate_ownership_stats(
        code_commune=code_commune,
        code_departement=code_departement,
    )


@router.get("/top-owners")
async def get_top_owners(
    code_commune: Optional[str] = Query(None),
    code_departement: Optional[str] = Query(None),
    limit: int = Query(20, ge=5, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List largest property owners in a zone by number of properties."""
    if not code_commune and not code_departement:
        raise HTTPException(status_code=400, detail="Provide code_commune or code_departement")

    service = OwnershipGraphService(db)
    owners = await service.get_top_owners(
        code_commune=code_commune,
        code_departement=code_departement,
        limit=limit,
    )

    return {
        "owners": owners,
        "nb_owners": len(owners),
        "scope": {
            "type": "commune" if code_commune else "departement",
            "code": code_commune or code_departement,
        },
    }


@router.get("/owner/{owner_id}")
async def get_owner_detail(
    owner_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get detailed profile and properties for a specific owner."""
    service = OwnershipGraphService(db)
    network = await service._get_owner_centered_network(owner_id=owner_id, depth=1)

    if not network["nodes"]:
        raise HTTPException(status_code=404, detail="Owner not found")

    return network
