"""
First-time buyer opportunity finder.
Scores neighborhoods based on affordability, stability, and quality of life.
"""
import pandas as pd
import numpy as np
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from loguru import logger


# PTZ zones by département (simplified mapping)
PTZ_ZONES = {
    "75": "A", "92": "A", "93": "A", "94": "A",  # Paris + petite couronne
    "77": "B1", "78": "B1", "91": "B1", "95": "B1",  # Grande couronne
    "06": "A", "13": "B1", "69": "B1",              # Nice, Marseille, Lyon
    "31": "B1", "33": "B1", "34": "B1", "44": "B1",  # Toulouse, Bordeaux, Montpellier, Nantes
    "59": "B1", "67": "B1",                           # Lille, Strasbourg
}

PTZ_ZONE_DEFAULT = "B2"


class OpportunityFinderService:
    """Identifies best opportunities for first-time buyers."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def find_opportunities(
        self,
        max_budget: float,
        surface_min: float = 40.0,
        type_local: str = "Appartement",
        departements: Optional[list[str]] = None,
        prefer_stable_prices: bool = True,
        limit: int = 20,
    ) -> dict:
        """
        Find best opportunities within budget constraints.
        Returns scored and ranked communes/neighborhoods.
        """
        dept_filter = ""
        params = {
            "budget": max_budget,
            "surface_min": surface_min,
            "type_local": type_local,
        }

        if departements:
            dept_list = ", ".join(f"'{d}'" for d in departements)
            dept_filter = f"AND t.code_departement IN ({dept_list})"

        # Find communes where budget is feasible
        query = f"""
            WITH commune_prices AS (
                SELECT
                    t.code_commune,
                    t.commune,
                    t.code_departement,
                    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY t.prix_m2) AS prix_median_m2,
                    PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY t.prix_m2) AS prix_p25_m2,
                    COUNT(*) AS nb_transactions,
                    AVG(t.latitude) AS lat,
                    AVG(t.longitude) AS lng,
                    STDDEV(t.prix_m2) / NULLIF(AVG(t.prix_m2), 0) AS prix_cv
                FROM transactions t
                WHERE t.type_local = :type_local
                  AND t.surface_reelle_bati >= :surface_min
                  AND t.prix_m2 > 0
                  AND t.prix_m2 < 50000
                  AND EXTRACT(YEAR FROM t.date_mutation) >= EXTRACT(YEAR FROM NOW()) - 2
                  {dept_filter}
                GROUP BY t.code_commune, t.commune, t.code_departement
                HAVING COUNT(*) >= 10
            ),
            price_evolution AS (
                SELECT
                    code_commune,
                    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY prix_m2) AS prix_recent,
                    LAG(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY prix_m2))
                        OVER (PARTITION BY code_commune ORDER BY EXTRACT(YEAR FROM date_mutation))
                        AS prix_prev
                FROM transactions
                WHERE type_local = :type_local
                  AND prix_m2 > 0
                  AND EXTRACT(YEAR FROM date_mutation) >= EXTRACT(YEAR FROM NOW()) - 4
                GROUP BY code_commune, EXTRACT(YEAR FROM date_mutation)
            )
            SELECT
                cp.code_commune,
                cp.commune,
                cp.code_departement,
                cp.prix_median_m2,
                cp.prix_p25_m2,
                cp.nb_transactions,
                cp.lat,
                cp.lng,
                cp.prix_cv,
                ROUND((cp.prix_median_m2 * :surface_min)::numeric, 0) AS budget_median
            FROM commune_prices cp
            WHERE cp.prix_p25_m2 * :surface_min <= :budget
            ORDER BY
                CASE WHEN :prefer_stable = true THEN cp.prix_cv END ASC NULLS LAST,
                cp.prix_median_m2 ASC
            LIMIT :limit
        """

        try:
            result = await self.db.execute(
                text(query),
                {**params, "prefer_stable": prefer_stable_prices, "limit": limit * 3}
            )
            rows = result.fetchall()
        except Exception as e:
            logger.error(f"Error in opportunity finder: {e}")
            return self._mock_opportunities(max_budget, type_local, limit)

        if not rows:
            return {"opportunities": [], "summary": {"message": "Aucun résultat pour ce budget"}}

        opportunities = []
        for r in rows:
            code_dept = str(r[2])
            prix_m2 = float(r[3]) if r[3] else 0
            prix_p25 = float(r[4]) if r[4] else 0
            nb_trans = int(r[5])
            budget_median = float(r[9]) if r[9] else prix_m2 * surface_min

            # Compute opportunity score
            score = self._compute_opportunity_score(
                budget=max_budget,
                prix_median_m2=prix_m2,
                prix_p25_m2=prix_p25,
                surface_min=surface_min,
                nb_transactions=nb_trans,
                prix_cv=float(r[8]) if r[8] else None,
                prefer_stable=prefer_stable_prices,
            )

            zone_ptz = PTZ_ZONES.get(code_dept, PTZ_ZONE_DEFAULT)
            eligible_ptz = zone_ptz not in ("A", "Abis") or max_budget <= 300000

            opportunities.append({
                "code_commune": r[0],
                "commune": r[1],
                "code_departement": r[2],
                "prix_median_m2": round(prix_m2, 0),
                "prix_p25_m2": round(prix_p25, 0),
                "budget_pour_surface_cible": round(budget_median, 0),
                "reste_budget": round(max_budget - budget_median, 0),
                "nb_transactions_2ans": nb_trans,
                "score_opportunite": round(score, 1),
                "lat": float(r[6]) if r[6] else None,
                "lng": float(r[7]) if r[7] else None,
                "zone_ptz": zone_ptz,
                "eligible_ptz": eligible_ptz,
                "prix_stabilite": "stable" if (r[8] or 1) < 0.15 else "variable",
                "marche_actif": "actif" if nb_trans >= 50 else "calme",
            })

        # Sort by score
        opportunities.sort(key=lambda x: x["score_opportunite"], reverse=True)
        top_opportunities = opportunities[:limit]

        return {
            "opportunities": top_opportunities,
            "summary": {
                "nb_communes_analysees": len(rows),
                "nb_opportunites": len(top_opportunities),
                "budget": max_budget,
                "surface_cible": surface_min,
                "type_bien": type_local,
                "prix_min": min(o["prix_median_m2"] for o in top_opportunities) if top_opportunities else None,
                "prix_max": max(o["prix_median_m2"] for o in top_opportunities) if top_opportunities else None,
                "score_moyen": round(
                    sum(o["score_opportunite"] for o in top_opportunities) / len(top_opportunities), 1
                ) if top_opportunities else None,
            },
        }

    def _compute_opportunity_score(
        self,
        budget: float,
        prix_median_m2: float,
        prix_p25_m2: float,
        surface_min: float,
        nb_transactions: int,
        prix_cv: Optional[float],
        prefer_stable: bool,
    ) -> float:
        """Score an opportunity from 0 to 100."""
        score = 0.0

        # 1. Affordability score (40 pts)
        budget_for_surface = prix_p25_m2 * surface_min
        if budget_for_surface <= budget * 0.7:
            score += 40  # Very affordable
        elif budget_for_surface <= budget * 0.85:
            score += 30
        elif budget_for_surface <= budget:
            score += 20
        else:
            score += 5   # Stretched

        # 2. Price stability score (30 pts if prefer_stable)
        if prix_cv is not None:
            if prix_cv < 0.10:
                score += 30  # Very stable
            elif prix_cv < 0.20:
                score += 20
            elif prix_cv < 0.30:
                score += 10
        else:
            score += 15  # Unknown

        # 3. Market liquidity (20 pts)
        if nb_transactions >= 100:
            score += 20  # Very liquid
        elif nb_transactions >= 50:
            score += 15
        elif nb_transactions >= 20:
            score += 10
        else:
            score += 5

        # 4. Savings buffer (10 pts)
        savings = budget - prix_median_m2 * surface_min
        if savings >= budget * 0.3:
            score += 10  # Plenty of buffer
        elif savings >= budget * 0.15:
            score += 7
        elif savings >= 0:
            score += 3

        return min(100, score)

    async def get_budget_simulation(
        self,
        salaire_mensuel_net: float,
        apport: float = 0,
        duree_ans: int = 25,
        taux_interet: float = 0.038,
        departements: Optional[list[str]] = None,
    ) -> dict:
        """
        Simulate borrowing capacity and find matching properties.
        Uses French mortgage calculation standards.
        """
        # French standard: max 35% debt-to-income ratio
        TAUX_ENDETTEMENT_MAX = 0.35
        mensualite_max = salaire_mensuel_net * TAUX_ENDETTEMENT_MAX

        # Monthly rate
        taux_mensuel = taux_interet / 12
        n = duree_ans * 12

        # Loan amount using annuity formula
        if taux_mensuel > 0:
            capacite_emprunt = mensualite_max * (1 - (1 + taux_mensuel) ** (-n)) / taux_mensuel
        else:
            capacite_emprunt = mensualite_max * n

        budget_total = capacite_emprunt + apport

        # Frais de notaire approximation (7-8% ancien, 2-3% neuf)
        frais_notaire = budget_total * 0.075
        budget_bien = budget_total - frais_notaire

        opportunities = await self.find_opportunities(
            max_budget=budget_bien,
            departements=departements,
        )

        return {
            "simulation": {
                "salaire_mensuel_net": salaire_mensuel_net,
                "apport": apport,
                "duree_ans": duree_ans,
                "taux_interet_pct": round(taux_interet * 100, 2),
                "mensualite_max": round(mensualite_max, 0),
                "capacite_emprunt": round(capacite_emprunt, 0),
                "budget_total_achat": round(budget_total, 0),
                "frais_notaire_estimes": round(frais_notaire, 0),
                "budget_bien_net": round(budget_bien, 0),
                "taux_endettement_pct": TAUX_ENDETTEMENT_MAX * 100,
            },
            **opportunities,
        }

    def _mock_opportunities(self, budget: float, type_local: str, limit: int) -> dict:
        """Demo data when DB is not available."""
        communes = [
            {"commune": "Roubaix", "dept": "59", "prix_m2": 1800, "lat": 50.69, "lng": 3.18},
            {"commune": "Saint-Étienne", "dept": "42", "prix_m2": 1200, "lat": 45.43, "lng": 4.39},
            {"commune": "Mulhouse", "dept": "68", "prix_m2": 1500, "lat": 47.75, "lng": 7.34},
            {"commune": "Limoges", "dept": "87", "prix_m2": 1600, "lat": 45.83, "lng": 1.25},
            {"commune": "Clermont-Ferrand", "dept": "63", "prix_m2": 2200, "lat": 45.78, "lng": 3.08},
        ]

        opps = []
        for c in communes[:limit]:
            budget_40m2 = c["prix_m2"] * 40
            if budget_40m2 <= budget:
                opps.append({
                    "code_commune": f"demo-{c['dept']}",
                    "commune": c["commune"],
                    "code_departement": c["dept"],
                    "prix_median_m2": c["prix_m2"],
                    "budget_pour_surface_cible": budget_40m2,
                    "score_opportunite": round(70 - c["prix_m2"] / 100, 1),
                    "lat": c["lat"],
                    "lng": c["lng"],
                    "zone_ptz": PTZ_ZONES.get(c["dept"], PTZ_ZONE_DEFAULT),
                    "eligible_ptz": True,
                })

        return {
            "opportunities": sorted(opps, key=lambda x: x["score_opportunite"], reverse=True),
            "summary": {"budget": budget, "type_bien": type_local, "nb_opportunites": len(opps)},
            "is_demo": True,
        }
