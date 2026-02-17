"""
Speculative pattern detection and gentrification trend analysis.
Identifies: rapid flips, mass acquisitions, price spikes, corporate takeovers.
"""
import pandas as pd
import numpy as np
from datetime import date, datetime, timedelta
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from loguru import logger


SPECULATION_WEIGHTS = {
    "rapid_flip": 30,         # property resold < 24 months at +20%
    "mass_acquisition": 25,   # same owner buys many in same zone fast
    "price_spike": 20,        # >30% above area median
    "corporate_wave": 25,     # >40% of transactions by companies
    "vacancy_increase": 15,   # rising vacant properties (investment holding)
}

GENTRIFICATION_THRESHOLDS = {
    "early": {"prix_evolution_5ans": 15, "part_investisseurs": 20},
    "active": {"prix_evolution_5ans": 30, "part_investisseurs": 35},
    "advanced": {"prix_evolution_5ans": 50, "part_investisseurs": 50},
}


class SpeculationDetector:
    """Detects speculative real estate patterns and gentrification signals."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def detect_rapid_flips(
        self,
        code_commune: Optional[str] = None,
        code_departement: Optional[str] = None,
        min_gain_pct: float = 20.0,
        max_hold_months: int = 24,
    ) -> list[dict]:
        """
        Detect properties rapidly resold with high profit margins.
        Signals: professional flippers, speculative pressure.
        """
        scope_filter = ""
        params = {
            "min_gain_pct": min_gain_pct / 100,
            "max_hold_days": max_hold_months * 30,
        }

        if code_commune:
            scope_filter = "AND t1.code_commune = :code_commune"
            params["code_commune"] = code_commune
        elif code_departement:
            scope_filter = "AND t1.code_departement = :code_departement"
            params["code_departement"] = code_departement

        query = f"""
            WITH consecutive AS (
                SELECT
                    t1.id_parcelle,
                    t1.commune,
                    t1.code_commune,
                    t1.code_departement,
                    t1.date_mutation AS date_achat,
                    t2.date_mutation AS date_revente,
                    t1.valeur_fonciere AS prix_achat,
                    t2.valeur_fonciere AS prix_revente,
                    t1.type_local,
                    t1.adresse_nom_voie,
                    t1.latitude,
                    t1.longitude,
                    (t2.date_mutation - t1.date_mutation) AS holding_days,
                    (t2.valeur_fonciere - t1.valeur_fonciere) / NULLIF(t1.valeur_fonciere, 0) AS gain_ratio
                FROM transactions t1
                JOIN transactions t2 ON t1.id_parcelle = t2.id_parcelle
                    AND t2.date_mutation > t1.date_mutation
                    AND t2.date_mutation = (
                        SELECT MIN(t3.date_mutation)
                        FROM transactions t3
                        WHERE t3.id_parcelle = t1.id_parcelle
                          AND t3.date_mutation > t1.date_mutation
                    )
                WHERE t1.valeur_fonciere > 10000
                {scope_filter}
            )
            SELECT
                id_parcelle,
                commune,
                code_commune,
                code_departement,
                date_achat,
                date_revente,
                prix_achat,
                prix_revente,
                type_local,
                adresse_nom_voie,
                latitude,
                longitude,
                holding_days,
                ROUND((gain_ratio * 100)::numeric, 1) AS gain_pct
            FROM consecutive
            WHERE holding_days <= :max_hold_days
              AND gain_ratio >= :min_gain_pct
            ORDER BY gain_ratio DESC
            LIMIT 1000
        """

        try:
            result = await self.db.execute(text(query), params)
            rows = result.fetchall()
        except Exception as e:
            logger.error(f"Error detecting rapid flips: {e}")
            return []

        flips = []
        for r in rows:
            flips.append({
                "parcelle_id": r[0],
                "commune": r[1],
                "code_commune": r[2],
                "code_departement": r[3],
                "date_achat": r[4].isoformat() if r[4] else None,
                "date_revente": r[5].isoformat() if r[5] else None,
                "prix_achat": float(r[6]) if r[6] else None,
                "prix_revente": float(r[7]) if r[7] else None,
                "type_local": r[8],
                "adresse": r[9],
                "latitude": float(r[10]) if r[10] else None,
                "longitude": float(r[11]) if r[11] else None,
                "holding_days": int(r[12]) if r[12] else None,
                "gain_pct": float(r[13]) if r[13] else None,
                "severity": self._flip_severity(float(r[13]) if r[13] else 0, int(r[12]) if r[12] else 9999),
            })

        return flips

    def _flip_severity(self, gain_pct: float, holding_days: int) -> str:
        if gain_pct >= 50 and holding_days <= 180:
            return "critical"
        if gain_pct >= 30 and holding_days <= 365:
            return "high"
        if gain_pct >= 20 and holding_days <= 548:
            return "medium"
        return "low"

    async def detect_mass_acquisitions(
        self,
        code_departement: str,
        min_properties: int = 5,
        window_months: int = 24,
    ) -> list[dict]:
        """
        Find entities buying many properties in short periods.
        Signals: institutional investors, corporate speculation.
        """
        # Proxy: same company name pattern in same zone within window
        query = """
            SELECT
                code_commune,
                commune,
                code_departement,
                COUNT(DISTINCT id_parcelle) AS nb_acquisitions,
                MIN(date_mutation) AS premiere_acquisition,
                MAX(date_mutation) AS derniere_acquisition,
                SUM(valeur_fonciere) AS valeur_totale,
                AVG(valeur_fonciere) AS valeur_moyenne,
                ARRAY_AGG(DISTINCT type_local) AS types_biens
            FROM transactions
            WHERE code_departement = :dept
              AND nature_mutation = 'Vente'
              AND valeur_fonciere > 50000
            GROUP BY code_commune, commune, code_departement,
                     DATE_TRUNC('month', date_mutation),
                     -- Approximate same buyer via correlated acquisitions
                     FLOOR(latitude::numeric * 100) / 100,
                     FLOOR(longitude::numeric * 100) / 100
            HAVING COUNT(DISTINCT id_parcelle) >= :min_props
            ORDER BY nb_acquisitions DESC
            LIMIT 500
        """

        try:
            result = await self.db.execute(
                text(query),
                {"dept": code_departement, "min_props": min_properties}
            )
            rows = result.fetchall()
        except Exception as e:
            logger.error(f"Error detecting mass acquisitions: {e}")
            return []

        return [
            {
                "code_commune": r[0],
                "commune": r[1],
                "code_departement": r[2],
                "nb_acquisitions": int(r[3]),
                "premiere_acquisition": r[4].isoformat() if r[4] else None,
                "derniere_acquisition": r[5].isoformat() if r[5] else None,
                "valeur_totale": float(r[6]) if r[6] else None,
                "valeur_moyenne": float(r[7]) if r[7] else None,
                "types_biens": list(r[8]) if r[8] else [],
                "severity": "high" if int(r[3]) >= 10 else "medium",
            }
            for r in rows
        ]

    async def compute_gentrification_index(
        self,
        code_commune: str,
    ) -> dict:
        """
        Compute gentrification stage and displacement risk score.
        Multi-factor model combining price evolution, investor share, turnover.
        """
        # Price evolution over multiple periods
        price_query = """
            SELECT
                EXTRACT(YEAR FROM date_mutation) AS year,
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY prix_m2) AS prix_median,
                COUNT(*) AS nb_transactions,
                SUM(CASE WHEN UPPER(COALESCE(nature_mutation, '')) LIKE '%VENTE%' THEN 1 ELSE 0 END) AS nb_ventes
            FROM transactions
            WHERE code_commune = :commune
              AND type_local IN ('Appartement', 'Maison')
              AND prix_m2 > 0
              AND prix_m2 < 50000
            GROUP BY EXTRACT(YEAR FROM date_mutation)
            ORDER BY year
        """

        try:
            result = await self.db.execute(text(price_query), {"commune": code_commune})
            rows = result.fetchall()
        except Exception as e:
            logger.error(f"Error computing gentrification for {code_commune}: {e}")
            return {"error": str(e)}

        if len(rows) < 3:
            return {"error": "Insufficient data", "min_required": 3}

        years = [int(r[0]) for r in rows]
        prices = [float(r[1]) for r in rows]
        transactions = [int(r[2]) for r in rows]

        current_price = prices[-1]
        current_year = years[-1]

        # Calculate evolutions
        def get_price_at_year(target_year: int) -> Optional[float]:
            if target_year in years:
                idx = years.index(target_year)
                return prices[idx]
            return None

        price_5y = get_price_at_year(current_year - 5)
        price_10y = get_price_at_year(current_year - 10)

        evol_5y = ((current_price - price_5y) / price_5y * 100) if price_5y else None
        evol_10y = ((current_price - price_10y) / price_10y * 100) if price_10y else None

        # Compute gentrification score (0-100)
        score = 0
        signals = []

        if evol_5y is not None:
            if evol_5y > 50:
                score += 40
                signals.append({"signal": "price_explosion_5y", "value": evol_5y, "weight": 40})
            elif evol_5y > 30:
                score += 25
                signals.append({"signal": "price_rise_5y", "value": evol_5y, "weight": 25})
            elif evol_5y > 15:
                score += 10
                signals.append({"signal": "price_increase_5y", "value": evol_5y, "weight": 10})

        # Volume increase (rising activity = gentrification pressure)
        if len(transactions) >= 3:
            recent_avg = np.mean(transactions[-3:])
            early_avg = np.mean(transactions[:3]) if len(transactions) >= 6 else np.mean(transactions[:3])
            if early_avg > 0:
                volume_change = (recent_avg - early_avg) / early_avg * 100
                if volume_change > 50:
                    score += 20
                    signals.append({"signal": "transaction_surge", "value": volume_change, "weight": 20})
                elif volume_change > 20:
                    score += 10
                    signals.append({"signal": "transaction_increase", "value": volume_change, "weight": 10})

        # Price acceleration (second derivative)
        if len(prices) >= 6:
            recent_growth = np.polyfit(range(3), prices[-3:], 1)[0]
            earlier_growth = np.polyfit(range(3), prices[-6:-3], 1)[0]
            if earlier_growth > 0 and recent_growth > earlier_growth * 1.5:
                score += 15
                signals.append({"signal": "accelerating_prices", "value": recent_growth / earlier_growth, "weight": 15})

        score = min(100, score)

        # Determine stage
        if score >= 70:
            stage = "advanced"
        elif score >= 45:
            stage = "active"
        elif score >= 20:
            stage = "early"
        else:
            stage = "stable"

        displacement_risk = min(100, score * 0.9 + (evol_5y or 0) * 0.2)

        return {
            "code_commune": code_commune,
            "gentrification_score": round(score, 1),
            "displacement_risk": round(displacement_risk, 1),
            "stage": stage,
            "prix_actuel_m2": round(current_price, 2),
            "evolution_5ans_pct": round(evol_5y, 1) if evol_5y else None,
            "evolution_10ans_pct": round(evol_10y, 1) if evol_10y else None,
            "signals": signals,
            "price_history": [
                {"year": y, "prix_median_m2": round(p, 2), "nb_transactions": t}
                for y, p, t in zip(years, prices, transactions)
            ],
        }

    async def get_speculation_heatmap(
        self,
        code_departement: str,
    ) -> list[dict]:
        """Aggregate speculation score per commune for heatmap display."""
        query = """
            WITH commune_stats AS (
                SELECT
                    code_commune,
                    commune,
                    AVG(latitude) AS lat,
                    AVG(longitude) AS lng,
                    COUNT(*) AS total_transactions,

                    -- Rapid flip proxy: same parcel transacted twice in 2 years
                    SUM(CASE
                        WHEN EXISTS (
                            SELECT 1 FROM transactions t2
                            WHERE t2.id_parcelle = t.id_parcelle
                              AND t2.date_mutation > t.date_mutation
                              AND t2.date_mutation <= t.date_mutation + INTERVAL '730 days'
                        ) THEN 1 ELSE 0
                    END)::float / NULLIF(COUNT(*), 0) * 100 AS flip_rate,

                    -- Price volatility
                    STDDEV(prix_m2) / NULLIF(AVG(prix_m2), 0) * 100 AS prix_cv,

                    -- High value transactions
                    SUM(CASE WHEN valeur_fonciere > 500000 THEN 1 ELSE 0 END)::float
                        / NULLIF(COUNT(*), 0) * 100 AS luxury_rate

                FROM transactions t
                WHERE code_departement = :dept
                  AND EXTRACT(YEAR FROM date_mutation) >= EXTRACT(YEAR FROM NOW()) - 5
                  AND valeur_fonciere > 0
                GROUP BY code_commune, commune
                HAVING COUNT(*) >= 20
            )
            SELECT
                code_commune,
                commune,
                lat,
                lng,
                total_transactions,
                ROUND(flip_rate::numeric, 1) AS flip_rate,
                ROUND(prix_cv::numeric, 1) AS prix_volatility,
                ROUND(luxury_rate::numeric, 1) AS luxury_rate,
                ROUND((
                    COALESCE(flip_rate, 0) * 0.4 +
                    COALESCE(prix_cv, 0) * 0.3 +
                    COALESCE(luxury_rate, 0) * 0.3
                )::numeric, 1) AS speculation_score
            FROM commune_stats
            ORDER BY speculation_score DESC
        """

        try:
            result = await self.db.execute(text(query), {"dept": code_departement})
            rows = result.fetchall()
        except Exception as e:
            logger.error(f"Error computing speculation heatmap: {e}")
            return []

        return [
            {
                "code_commune": r[0],
                "commune": r[1],
                "lat": float(r[2]) if r[2] else None,
                "lng": float(r[3]) if r[3] else None,
                "total_transactions": int(r[4]),
                "flip_rate": float(r[5]) if r[5] else 0,
                "prix_volatility": float(r[6]) if r[6] else 0,
                "luxury_rate": float(r[7]) if r[7] else 0,
                "speculation_score": float(r[8]) if r[8] else 0,
                "level": "high" if float(r[8] or 0) >= 30 else "medium" if float(r[8] or 0) >= 15 else "low",
            }
            for r in rows
        ]
