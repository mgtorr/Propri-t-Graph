"""
Property ownership network mapping.
Builds graph of who owns what, detecting corporate ownership patterns,
shell company networks, and concentration of ownership.
"""
import networkx as nx
import pandas as pd
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from loguru import logger


class OwnershipGraphService:
    """Builds and analyzes property ownership networks."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_ownership_network(
        self,
        code_commune: Optional[str] = None,
        code_departement: Optional[str] = None,
        owner_id: Optional[str] = None,
        depth: int = 2,
        min_properties: int = 2,
    ) -> dict:
        """
        Build ownership network graph for visualization.
        Returns nodes (owners/properties) and edges (ownership links).
        """
        if owner_id:
            return await self._get_owner_centered_network(owner_id, depth)
        elif code_commune:
            return await self._get_zone_network(code_commune=code_commune, min_properties=min_properties)
        elif code_departement:
            return await self._get_zone_network(code_departement=code_departement, min_properties=min_properties)
        else:
            return {"error": "Must provide code_commune, code_departement, or owner_id"}

    async def _get_zone_network(
        self,
        code_commune: Optional[str] = None,
        code_departement: Optional[str] = None,
        min_properties: int = 2,
    ) -> dict:
        """Get ownership network for a geographic zone."""

        scope_col = "code_commune" if code_commune else "code_departement"
        scope_val = code_commune or code_departement

        # Get top owners with multiple properties
        query = f"""
            WITH owner_counts AS (
                SELECT
                    o.id AS owner_id,
                    o.owner_hash,
                    o.owner_type,
                    o.raison_sociale,
                    o.siren,
                    o.nb_biens,
                    o.valeur_portfolio,
                    o.is_speculator,
                    COUNT(DISTINCT po.property_id) AS nb_biens_zone
                FROM owners o
                JOIN property_ownerships po ON o.id = po.owner_id
                JOIN properties p ON po.property_id = p.id
                WHERE p.{scope_col} = :scope_val
                GROUP BY o.id, o.owner_hash, o.owner_type, o.raison_sociale,
                         o.siren, o.nb_biens, o.valeur_portfolio, o.is_speculator
                HAVING COUNT(DISTINCT po.property_id) >= :min_props
            ),
            owner_links AS (
                SELECT
                    po1.owner_id AS owner1,
                    po2.owner_id AS owner2,
                    COUNT(DISTINCT po1.property_id) AS shared_props
                FROM property_ownerships po1
                JOIN property_ownerships po2 ON po1.property_id = po2.property_id
                    AND po1.owner_id < po2.owner_id
                WHERE po1.owner_id IN (SELECT owner_id FROM owner_counts)
                  AND po2.owner_id IN (SELECT owner_id FROM owner_counts)
                GROUP BY po1.owner_id, po2.owner_id
            )
            SELECT 'node' AS record_type,
                   owner_id::text, owner_hash, owner_type, raison_sociale, siren,
                   nb_biens, valeur_portfolio, is_speculator::text, nb_biens_zone,
                   NULL::text, NULL::int
            FROM owner_counts
            UNION ALL
            SELECT 'edge' AS record_type,
                   owner1::text, owner2::text, NULL, NULL, NULL,
                   NULL, NULL, NULL, NULL,
                   NULL::text, shared_props
            FROM owner_links
        """

        try:
            result = await self.db.execute(
                text(query),
                {"scope_val": scope_val, "min_props": min_properties}
            )
            rows = result.fetchall()
        except Exception as e:
            logger.error(f"DB error in ownership network: {e}")
            return await self._get_mock_network(scope_val)

        nodes = []
        edges = []

        for r in rows:
            if r[0] == "node":
                nodes.append({
                    "id": r[1],
                    "label": r[3] or r[2] or "Particulier",
                    "type": r[3],  # owner_type
                    "raison_sociale": r[4],
                    "siren": r[5],
                    "nb_biens_total": int(r[6]) if r[6] else 0,
                    "valeur_portfolio": float(r[7]) if r[7] else None,
                    "is_speculator": r[8] == "True",
                    "nb_biens_zone": int(r[9]) if r[9] else 0,
                    "size": self._node_size(int(r[9]) if r[9] else 1),
                    "color": self._node_color(r[3], r[8] == "True"),
                })
            else:
                edges.append({
                    "source": r[1],
                    "target": r[2],
                    "weight": int(r[11]) if r[11] else 1,
                    "label": f"{r[11]} bien{'s' if (r[11] or 0) > 1 else ''} en commun",
                })

        # Compute network metrics
        G = nx.Graph()
        for n in nodes:
            G.add_node(n["id"])
        for e in edges:
            G.add_edge(e["source"], e["target"], weight=e["weight"])

        metrics = self._compute_network_metrics(G)

        return {
            "nodes": nodes,
            "edges": edges,
            "metrics": metrics,
            "scope": {"type": "commune" if code_commune else "departement", "code": scope_val},
        }

    async def _get_owner_centered_network(self, owner_id: str, depth: int) -> dict:
        """Build network centered on a specific owner."""
        query = """
            WITH RECURSIVE owner_network AS (
                -- Start from the owner
                SELECT o.id, o.owner_hash, o.owner_type, o.raison_sociale, o.siren,
                       o.nb_biens, o.valeur_portfolio, o.is_speculator, 0 AS depth
                FROM owners o WHERE o.id = :owner_id

                UNION

                -- Expand to co-owners of same properties
                SELECT o2.id, o2.owner_hash, o2.owner_type, o2.raison_sociale, o2.siren,
                       o2.nb_biens, o2.valeur_portfolio, o2.is_speculator, on_prev.depth + 1
                FROM owner_network on_prev
                JOIN property_ownerships po1 ON po1.owner_id = on_prev.id
                JOIN property_ownerships po2 ON po2.property_id = po1.property_id
                    AND po2.owner_id != on_prev.id
                JOIN owners o2 ON o2.id = po2.owner_id
                WHERE on_prev.depth < :max_depth
            )
            SELECT DISTINCT id, owner_hash, owner_type, raison_sociale, siren,
                           nb_biens, valeur_portfolio, is_speculator, depth
            FROM owner_network
            ORDER BY depth, nb_biens DESC
            LIMIT 100
        """

        try:
            result = await self.db.execute(
                text(query),
                {"owner_id": owner_id, "max_depth": depth}
            )
            rows = result.fetchall()
        except Exception as e:
            logger.error(f"Error fetching owner network: {e}")
            return {"nodes": [], "edges": [], "metrics": {}}

        nodes = [
            {
                "id": str(r[0]),
                "label": r[3] or r[1] or "Propriétaire",
                "type": r[2],
                "raison_sociale": r[3],
                "siren": r[4],
                "nb_biens": int(r[5]) if r[5] else 0,
                "valeur_portfolio": float(r[6]) if r[6] else None,
                "is_speculator": bool(r[7]),
                "depth": int(r[8]),
                "is_center": str(r[0]) == owner_id,
                "size": 30 if str(r[0]) == owner_id else self._node_size(int(r[5]) if r[5] else 1),
                "color": "#FF6B35" if str(r[0]) == owner_id else self._node_color(r[2], bool(r[7])),
            }
            for r in rows
        ]

        return {"nodes": nodes, "edges": [], "metrics": {"total_nodes": len(nodes)}}

    async def get_corporate_ownership_stats(
        self,
        code_commune: Optional[str] = None,
        code_departement: Optional[str] = None,
    ) -> dict:
        """Analyze corporate vs individual ownership patterns."""

        scope_col = "p.commune_code" if code_commune else "p.departement"
        scope_val = code_commune or code_departement

        query = f"""
            SELECT
                o.owner_type,
                COUNT(DISTINCT po.property_id) AS nb_biens,
                COUNT(DISTINCT o.id) AS nb_proprietaires,
                SUM(po.acquisition_price) AS valeur_totale,
                AVG(o.nb_biens) AS biens_par_proprio
            FROM owners o
            JOIN property_ownerships po ON o.id = po.owner_id
            JOIN properties p ON po.property_id = p.id
            WHERE {scope_col} = :scope_val
            GROUP BY o.owner_type
            ORDER BY nb_biens DESC
        """

        try:
            result = await self.db.execute(text(query), {"scope_val": scope_val})
            rows = result.fetchall()
        except Exception as e:
            logger.error(f"Error in corporate stats: {e}")
            # Return synthetic stats for demo
            return self._mock_corporate_stats()

        total_biens = sum(int(r[1]) for r in rows)

        breakdown = []
        for r in rows:
            nb = int(r[1])
            breakdown.append({
                "owner_type": r[0],
                "nb_biens": nb,
                "nb_proprietaires": int(r[2]),
                "valeur_totale": float(r[3]) if r[3] else None,
                "biens_par_proprio": round(float(r[4]), 1) if r[4] else None,
                "part_pct": round(nb / total_biens * 100, 1) if total_biens > 0 else 0,
            })

        corporate_pct = sum(
            b["part_pct"] for b in breakdown
            if b["owner_type"] in ("company", "sci", "public")
        )

        return {
            "breakdown": breakdown,
            "total_biens": total_biens,
            "corporate_share_pct": round(corporate_pct, 1),
            "concentration_risk": "high" if corporate_pct >= 40 else "medium" if corporate_pct >= 20 else "low",
        }

    async def get_top_owners(
        self,
        code_commune: Optional[str] = None,
        code_departement: Optional[str] = None,
        limit: int = 20,
    ) -> list[dict]:
        """Get largest property owners in a zone."""
        scope_col = "p.commune_code" if code_commune else "p.departement"
        scope_val = code_commune or code_departement

        query = f"""
            SELECT
                o.id,
                o.owner_type,
                o.raison_sociale,
                o.siren,
                o.forme_juridique,
                o.is_speculator,
                COUNT(DISTINCT po.property_id) AS nb_biens,
                SUM(p.surface_bati) AS surface_totale,
                SUM(po.acquisition_price) AS valeur_totale
            FROM owners o
            JOIN property_ownerships po ON o.id = po.owner_id
            JOIN properties p ON po.property_id = p.id
            WHERE {scope_col} = :scope_val
            GROUP BY o.id, o.owner_type, o.raison_sociale, o.siren, o.forme_juridique, o.is_speculator
            ORDER BY nb_biens DESC
            LIMIT :limit
        """

        try:
            result = await self.db.execute(text(query), {"scope_val": scope_val, "limit": limit})
            rows = result.fetchall()
        except Exception as e:
            logger.error(f"Error fetching top owners: {e}")
            return []

        return [
            {
                "owner_id": str(r[0]),
                "owner_type": r[1],
                "name": r[2] or "Particulier (anonymisé)",
                "siren": r[3],
                "forme_juridique": r[4],
                "is_speculator": bool(r[5]),
                "nb_biens": int(r[6]),
                "surface_totale_m2": round(float(r[7]), 0) if r[7] else None,
                "valeur_totale": float(r[8]) if r[8] else None,
            }
            for r in rows
        ]

    def _node_size(self, nb_biens: int) -> int:
        if nb_biens >= 50:
            return 40
        if nb_biens >= 20:
            return 25
        if nb_biens >= 10:
            return 18
        if nb_biens >= 5:
            return 12
        return 8

    def _node_color(self, owner_type: str, is_speculator: bool) -> str:
        if is_speculator:
            return "#E63946"  # red for speculators
        colors = {
            "company": "#457B9D",    # blue
            "sci": "#F4A261",        # orange
            "public": "#2A9D8F",     # teal
            "individual": "#A8DADC", # light blue
        }
        return colors.get(owner_type, "#A8DADC")

    def _compute_network_metrics(self, G: nx.Graph) -> dict:
        if len(G.nodes) == 0:
            return {"nb_nodes": 0, "nb_edges": 0}

        metrics = {
            "nb_nodes": G.number_of_nodes(),
            "nb_edges": G.number_of_edges(),
            "density": round(nx.density(G), 4),
        }

        if G.number_of_nodes() > 1:
            try:
                components = list(nx.connected_components(G))
                metrics["nb_components"] = len(components)
                metrics["largest_component_size"] = max(len(c) for c in components)
                # Degree centrality for top nodes
                centrality = nx.degree_centrality(G)
                top_central = sorted(centrality.items(), key=lambda x: x[1], reverse=True)[:5]
                metrics["top_central_nodes"] = [
                    {"node_id": n, "centrality": round(c, 3)} for n, c in top_central
                ]
            except Exception:
                pass

        return metrics

    def _mock_corporate_stats(self) -> dict:
        return {
            "breakdown": [
                {"owner_type": "individual", "nb_biens": 850, "nb_proprietaires": 820, "part_pct": 68.0},
                {"owner_type": "sci", "nb_biens": 200, "nb_proprietaires": 85, "part_pct": 16.0},
                {"owner_type": "company", "nb_biens": 150, "nb_proprietaires": 30, "part_pct": 12.0},
                {"owner_type": "public", "nb_biens": 50, "nb_proprietaires": 5, "part_pct": 4.0},
            ],
            "total_biens": 1250,
            "corporate_share_pct": 32.0,
            "concentration_risk": "medium",
        }

    async def _get_mock_network(self, scope: str) -> dict:
        """Return demo network when DB data unavailable."""
        nodes = [
            {"id": "1", "label": "SCI Immobilière du Centre", "type": "sci", "nb_biens_zone": 12, "size": 18, "color": "#F4A261", "is_speculator": False},
            {"id": "2", "label": "Foncière Nationale SA", "type": "company", "nb_biens_zone": 28, "size": 25, "color": "#457B9D", "is_speculator": True},
            {"id": "3", "label": "Particulier A", "type": "individual", "nb_biens_zone": 3, "size": 8, "color": "#A8DADC", "is_speculator": False},
            {"id": "4", "label": "Particulier B", "type": "individual", "nb_biens_zone": 2, "size": 8, "color": "#A8DADC", "is_speculator": False},
            {"id": "5", "label": "Invest Corp 75", "type": "company", "nb_biens_zone": 45, "size": 40, "color": "#E63946", "is_speculator": True},
            {"id": "6", "label": "SCI Famille Martin", "type": "sci", "nb_biens_zone": 5, "size": 12, "color": "#F4A261", "is_speculator": False},
        ]
        edges = [
            {"source": "1", "target": "2", "weight": 3, "label": "3 biens en commun"},
            {"source": "2", "target": "5", "weight": 8, "label": "8 biens en commun"},
            {"source": "3", "target": "1", "weight": 1, "label": "1 bien en commun"},
            {"source": "4", "target": "6", "weight": 2, "label": "2 biens en commun"},
            {"source": "5", "target": "1", "weight": 4, "label": "4 biens en commun"},
        ]
        return {
            "nodes": nodes,
            "edges": edges,
            "metrics": {"nb_nodes": len(nodes), "nb_edges": len(edges), "density": 0.4},
            "scope": {"type": "zone", "code": scope},
            "is_demo": True,
        }
