"""SKG versioning and retraction handling utilities."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from polisyos.academic.knowledge.skg_store import (
    aggregate_edge_confidence,
    ensure_skg_schema,
    finalize_skg_version,
    next_skg_version,
    normalize_strength,
)
from polisyos.common.logger import get_logger

if TYPE_CHECKING:
    import duckdb

logger = get_logger(__name__)


@dataclass(frozen=True)
class RetractionReport:
    """Retraction report data model."""

    affected_edges: list[str]
    removed_edges: list[str]


class SKGVersionManager:
    """Manage reproducible SKG versions and retraction updates."""

    def create_version(
        self,
        conn: duckdb.DuckDBPyConnection,
        description: str = "",
    ) -> int:
        return next_skg_version(conn, description=description)

    def finalize_version(
        self,
        conn: duckdb.DuckDBPyConnection,
        *,
        version_id: int,
        n_articles: int,
        n_edges: int,
        n_variables: int,
    ) -> None:
        finalize_skg_version(
            conn,
            version_id=version_id,
            n_articles=n_articles,
            n_edges=n_edges,
            n_variables=n_variables,
        )

    def check_retractions(
        self,
        conn: duckdb.DuckDBPyConnection,
        openalex_client: Any,
    ) -> list[str]:
        """Check SKG articles against OpenAlex and return newly retracted ids."""
        ensure_skg_schema(conn)
        ids = [
            str(row[0])
            for row in conn.execute(
                "SELECT openalex_id FROM ac_skg_articles WHERE retracted = FALSE"
            ).fetchall()
        ]

        retracted_ids: list[str] = []
        for openalex_id in ids:
            is_retracted = self._query_retracted_status(openalex_client, openalex_id)
            if is_retracted:
                self.handle_retraction(conn, openalex_id)
                retracted_ids.append(openalex_id)
        return retracted_ids

    def _query_retracted_status(self, openalex_client: Any, openalex_id: str) -> bool:
        # Preferred API: get_work(id) -> dict
        if hasattr(openalex_client, "get_work"):
            try:
                payload = openalex_client.get_work(openalex_id)
                if isinstance(payload, dict):
                    return bool(payload.get("is_retracted"))
            except Exception as exc:
                logger.debug(
                    "Retraction check failed for %s: %s",
                    openalex_id,
                    exc,
                )
                return False

        # Fallback for async list_works clients is intentionally conservative.
        return False

    def handle_retraction(
        self,
        conn: duckdb.DuckDBPyConnection,
        openalex_id: str,
    ) -> dict[str, list[str]]:
        """
        1) mark article as retracted
        2) recompute affected edge confidence
        3) remove orphan edges
        """
        ensure_skg_schema(conn)
        conn.execute(
            "UPDATE ac_skg_articles SET retracted = TRUE WHERE openalex_id = ?",
            [openalex_id],
        )

        rows = conn.execute(
            "SELECT edge_id, article_refs, evidence_strength, confidence FROM ac_skg_edges"
        ).fetchall()

        affected_edges: list[str] = []
        removed_edges: list[str] = []

        for edge_id, article_refs_json, evidence_strength, confidence in rows:
            try:
                refs = json.loads(str(article_refs_json or "[]"))
                if not isinstance(refs, list):
                    refs = []
            except json.JSONDecodeError:
                refs = []

            refs_norm = [str(ref) for ref in refs if str(ref)]
            if openalex_id not in refs_norm:
                continue

            affected_edges.append(str(edge_id))
            refs_next = [ref for ref in refs_norm if ref != openalex_id]
            if not refs_next:
                conn.execute("DELETE FROM ac_skg_edges WHERE edge_id = ?", [edge_id])
                removed_edges.append(str(edge_id))
                continue

            strength = normalize_strength(evidence_strength)
            # Per-article evidence is not stored yet; approximate with remaining refs count.
            base_conf = float(confidence or 0.0)
            synthetic_conf = max(0.05, min(1.0, base_conf - 0.05))
            recalculated = aggregate_edge_confidence(
                [(strength, synthetic_conf) for _ in refs_next]
            )

            conn.execute(
                """
                UPDATE ac_skg_edges
                SET article_refs = ?, n_articles = ?, confidence = ?, evidence_strength = ?
                WHERE edge_id = ?
                """,
                [
                    json.dumps(refs_next, ensure_ascii=False),
                    len(refs_next),
                    recalculated,
                    strength,
                    edge_id,
                ],
            )

        return {
            "affected_edges": affected_edges,
            "removed_edges": removed_edges,
        }


__all__ = ["RetractionReport", "SKGVersionManager"]
