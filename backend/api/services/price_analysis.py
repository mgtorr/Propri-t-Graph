"""
Price evolution analysis service with predictive modeling.
Uses Prophet for time-series forecasting and scikit-learn for spatial models.
"""
import pandas as pd
import numpy as np
from datetime import date, datetime, timedelta
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text
from loguru import logger

try:
    from prophet import Prophet
    PROPHET_AVAILABLE = True
except ImportError:
    PROPHET_AVAILABLE = False
    logger.warning("Prophet not available - using statsmodels fallback")

from statsmodels.tsa.holtwinters import ExponentialSmoothing
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.preprocessing import StandardScaler
import joblib


class PriceAnalysisService:
    """Analyzes price trends and generates predictions."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_price_history(
        self,
        code_commune: Optional[str] = None,
        iris_code: Optional[str] = None,
        type_local: str = "Appartement",
        start_year: int = 2018,
    ) -> pd.DataFrame:
        """Fetch price history from database."""
        conditions = [
            "t.type_local = :type_local",
            "EXTRACT(YEAR FROM t.date_mutation) >= :start_year",
            "t.prix_m2 > 0",
            "t.prix_m2 < 50000",  # filter obvious data errors
        ]
        params = {"type_local": type_local, "start_year": start_year}

        if code_commune:
            conditions.append("t.code_commune = :code_commune")
            params["code_commune"] = code_commune
        if iris_code:
            conditions.append("t.iris_code = :iris_code")
            params["iris_code"] = iris_code

        query = f"""
            SELECT
                DATE_TRUNC('month', t.date_mutation) AS period,
                COUNT(*) AS nb_transactions,
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY t.prix_m2) AS prix_median_m2,
                AVG(t.prix_m2) AS prix_moyen_m2,
                PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY t.prix_m2) AS prix_p25_m2,
                PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY t.prix_m2) AS prix_p75_m2,
                AVG(t.surface_reelle_bati) AS surface_mediane
            FROM transactions t
            WHERE {' AND '.join(conditions)}
            GROUP BY DATE_TRUNC('month', t.date_mutation)
            ORDER BY period
        """
        result = await self.db.execute(text(query), params)
        rows = result.fetchall()

        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame(rows, columns=[
            "period", "nb_transactions", "prix_median_m2", "prix_moyen_m2",
            "prix_p25_m2", "prix_p75_m2", "surface_mediane"
        ])
        df["period"] = pd.to_datetime(df["period"])
        return df

    async def predict_prices(
        self,
        code_commune: str,
        type_local: str = "Appartement",
        horizon_months: int = 12,
    ) -> dict:
        """Generate price forecast using Prophet or fallback model."""
        df = await self.get_price_history(code_commune=code_commune, type_local=type_local)

        if df.empty or len(df) < 12:
            return {"error": "Insufficient data for prediction", "min_required": 12}

        # Fill gaps in monthly data
        df = df.set_index("period").resample("MS").median().reset_index()
        df["prix_median_m2"] = df["prix_median_m2"].interpolate(method="linear")

        current_price = df["prix_median_m2"].iloc[-1]
        current_date = df["period"].iloc[-1]

        if PROPHET_AVAILABLE:
            prediction = self._predict_with_prophet(df, horizon_months)
        else:
            prediction = self._predict_with_ets(df, horizon_months)

        # Compute expected evolution
        if prediction["forecast"]:
            last_forecast = prediction["forecast"][-1]["prix_predit_m2"]
            evolution_pct = ((last_forecast - current_price) / current_price) * 100
        else:
            evolution_pct = None

        return {
            "code_commune": code_commune,
            "type_local": type_local,
            "prix_actuel_m2": round(float(current_price), 2),
            "date_reference": current_date.strftime("%Y-%m-%d"),
            "horizon_months": horizon_months,
            "evolution_prevue_pct": round(evolution_pct, 2) if evolution_pct else None,
            "model": prediction["model"],
            "forecast": prediction["forecast"],
            "historical": self._format_historical(df),
        }

    def _predict_with_prophet(self, df: pd.DataFrame, horizon: int) -> dict:
        """Use Meta Prophet for time-series forecasting."""
        prophet_df = df[["period", "prix_median_m2"]].rename(
            columns={"period": "ds", "prix_median_m2": "y"}
        )
        prophet_df = prophet_df.dropna()

        model = Prophet(
            yearly_seasonality=True,
            weekly_seasonality=False,
            daily_seasonality=False,
            seasonality_mode="multiplicative",
            changepoint_prior_scale=0.05,
            interval_width=0.80,
        )
        model.fit(prophet_df)

        future = model.make_future_dataframe(periods=horizon, freq="MS")
        forecast = model.predict(future)
        future_forecast = forecast[forecast["ds"] > prophet_df["ds"].max()]

        return {
            "model": "prophet",
            "forecast": [
                {
                    "date": row["ds"].strftime("%Y-%m-%d"),
                    "prix_predit_m2": round(max(0, row["yhat"]), 2),
                    "prix_min_m2": round(max(0, row["yhat_lower"]), 2),
                    "prix_max_m2": round(max(0, row["yhat_upper"]), 2),
                }
                for _, row in future_forecast.iterrows()
            ],
        }

    def _predict_with_ets(self, df: pd.DataFrame, horizon: int) -> dict:
        """Fallback: Holt-Winters Exponential Smoothing."""
        series = df["prix_median_m2"].dropna()

        try:
            model = ExponentialSmoothing(
                series,
                trend="add",
                seasonal="add" if len(series) >= 24 else None,
                seasonal_periods=12 if len(series) >= 24 else None,
            )
            fitted = model.fit(optimized=True, use_brute=True)
            forecast_values = fitted.forecast(horizon)
        except Exception:
            # Linear extrapolation as last resort
            x = np.arange(len(series))
            coeffs = np.polyfit(x, series.values, 1)
            forecast_values = [coeffs[0] * (len(series) + i) + coeffs[1] for i in range(horizon)]

        last_date = df["period"].iloc[-1]
        forecast_dates = pd.date_range(
            start=last_date + timedelta(days=32),
            periods=horizon,
            freq="MS"
        )

        # Simple confidence interval: ±10%
        return {
            "model": "exponential_smoothing",
            "forecast": [
                {
                    "date": d.strftime("%Y-%m-%d"),
                    "prix_predit_m2": round(max(0, float(v)), 2),
                    "prix_min_m2": round(max(0, float(v) * 0.90), 2),
                    "prix_max_m2": round(max(0, float(v) * 1.10), 2),
                }
                for d, v in zip(forecast_dates, forecast_values)
            ],
        }

    def _format_historical(self, df: pd.DataFrame) -> list:
        return [
            {
                "date": row["period"].strftime("%Y-%m-%d"),
                "prix_median_m2": round(float(row["prix_median_m2"]), 2) if pd.notna(row["prix_median_m2"]) else None,
                "prix_p25_m2": round(float(row["prix_p25_m2"]), 2) if pd.notna(row["prix_p25_m2"]) else None,
                "prix_p75_m2": round(float(row["prix_p75_m2"]), 2) if pd.notna(row["prix_p75_m2"]) else None,
                "nb_transactions": int(row["nb_transactions"]) if pd.notna(row["nb_transactions"]) else 0,
            }
            for _, row in df.iterrows()
        ]

    async def compute_neighborhood_heatmap(
        self,
        code_departement: str,
        type_local: str = "Appartement",
        year: int = 2023,
    ) -> list[dict]:
        """Compute price heatmap data for a department."""
        query = """
            SELECT
                t.iris_code,
                t.code_commune,
                t.commune,
                COUNT(*) AS nb_transactions,
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY t.prix_m2) AS prix_median_m2,
                AVG(t.prix_m2) AS prix_moyen_m2,
                AVG(t.latitude) AS lat,
                AVG(t.longitude) AS lng
            FROM transactions t
            WHERE t.code_departement = :dept
              AND t.type_local = :type_local
              AND EXTRACT(YEAR FROM t.date_mutation) = :year
              AND t.prix_m2 > 0
              AND t.latitude IS NOT NULL
            GROUP BY t.iris_code, t.code_commune, t.commune
            HAVING COUNT(*) >= 5
            ORDER BY prix_median_m2 DESC
        """
        result = await self.db.execute(
            text(query),
            {"dept": code_departement, "type_local": type_local, "year": year}
        )
        rows = result.fetchall()

        return [
            {
                "iris_code": r[0],
                "code_commune": r[1],
                "commune": r[2],
                "nb_transactions": int(r[3]),
                "prix_median_m2": round(float(r[4]), 2) if r[4] else None,
                "prix_moyen_m2": round(float(r[5]), 2) if r[5] else None,
                "lat": float(r[6]) if r[6] else None,
                "lng": float(r[7]) if r[7] else None,
            }
            for r in rows
        ]

    async def get_price_evolution_ranking(
        self,
        code_departement: str,
        type_local: str = "Appartement",
        top_n: int = 20,
    ) -> dict:
        """Rank communes by price evolution (winners and losers)."""
        query = """
            WITH yearly AS (
                SELECT
                    code_commune,
                    commune,
                    EXTRACT(YEAR FROM date_mutation) AS year,
                    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY prix_m2) AS prix_median_m2,
                    COUNT(*) AS nb
                FROM transactions
                WHERE code_departement = :dept
                  AND type_local = :type_local
                  AND prix_m2 > 0
                GROUP BY code_commune, commune, EXTRACT(YEAR FROM date_mutation)
                HAVING COUNT(*) >= 10
            ),
            pivot AS (
                SELECT
                    code_commune,
                    commune,
                    MAX(CASE WHEN year = EXTRACT(YEAR FROM NOW()) - 1 THEN prix_median_m2 END) AS prix_n1,
                    MAX(CASE WHEN year = EXTRACT(YEAR FROM NOW()) - 2 THEN prix_median_m2 END) AS prix_n2,
                    MAX(CASE WHEN year = EXTRACT(YEAR FROM NOW()) - 4 THEN prix_median_m2 END) AS prix_n4,
                    MAX(CASE WHEN year = EXTRACT(YEAR FROM NOW()) - 6 THEN prix_median_m2 END) AS prix_n6
                FROM yearly
                GROUP BY code_commune, commune
            )
            SELECT
                code_commune,
                commune,
                prix_n1,
                CASE WHEN prix_n2 > 0 THEN ROUND(((prix_n1 - prix_n2) / prix_n2 * 100)::numeric, 1) END AS evol_1an,
                CASE WHEN prix_n4 > 0 THEN ROUND(((prix_n1 - prix_n4) / prix_n4 * 100)::numeric, 1) END AS evol_3ans,
                CASE WHEN prix_n6 > 0 THEN ROUND(((prix_n1 - prix_n6) / prix_n6 * 100)::numeric, 1) END AS evol_5ans
            FROM pivot
            WHERE prix_n1 IS NOT NULL
            ORDER BY evol_1an DESC NULLS LAST
        """
        result = await self.db.execute(text(query), {"dept": code_departement, "type_local": type_local})
        rows = result.fetchall()

        formatted = [
            {
                "code_commune": r[0],
                "commune": r[1],
                "prix_median_m2": round(float(r[2]), 2) if r[2] else None,
                "evolution_1an_pct": float(r[3]) if r[3] else None,
                "evolution_3ans_pct": float(r[4]) if r[4] else None,
                "evolution_5ans_pct": float(r[5]) if r[5] else None,
            }
            for r in rows
        ]

        return {
            "top_gainers": [f for f in formatted if f["evolution_1an_pct"] and f["evolution_1an_pct"] > 0][:top_n],
            "top_losers": [f for f in reversed(formatted) if f["evolution_1an_pct"] and f["evolution_1an_pct"] < 0][:top_n],
            "all": formatted,
        }
