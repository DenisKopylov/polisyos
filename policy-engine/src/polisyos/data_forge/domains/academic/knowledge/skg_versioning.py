"""SKG versioning and retraction handling utilities."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from polisyos.common.logger import get_logger
from polisyos.data_forge.domains.academic.knowledge.skg_store import (
    aggregate_edge_confidence,
    ensure_skg_schema,
    finalize_skg_version,
    next_skg_version,
    normalize_strength,
)

if TYPE_CHECKING:
    import duckdb

logger = get_logger(__name__)

# Accepted measurement identity, not a filename/DDL/vocabulary heuristic. See HC-F01,
# HC-F12, HC-F18 and Event 23 of 2026-09-05-historical-cohorts.md. No chronology or
# historical generator invocation is inferred. This registry grants no authority.
_HISTORICAL_SNAPSHOT_SHA256 = "583233169ab729bbcf4c7189c60ff97ba98e3b5146aded44402c87eaccf3a967"


@dataclass(frozen=True)
class ConfidenceLayerOutcome:
    """Accepted retained-membership outcome for one complete measured layer."""

    table: str
    row_count: int
    current_rule_outcome: Literal["zero_confidence", "not_emitted"]


@dataclass(frozen=True)
class ConfidenceLayerVintage:
    """Content-bound limitation on a snapshot, never a per-row evidence judgment."""

    snapshot_sha256: str
    schema_version: Literal["academic.confidence_layer_vintage.v1"] = (
        "academic.confidence_layer_vintage.v1"
    )
    claim_evidence_axis: Literal["absent"] = "absent"
    confidence_reproducibility: Literal["not_reproducible_under_current_rule"] = (
        "not_reproducible_under_current_rule"
    )
    consumer_action: Literal["withhold_confidence_forwarding"] = "withhold_confidence_forwarding"
    binding_status: Literal["recomputed"] = "recomputed"
    measurement_basis: Literal["independently_reconciled"] = "independently_reconciled"
    rule_ref: str = "claim-explicit-evidence-axis/B1-B2; historical-cohorts/HC-F11-HC-F14"
    evidence_ref: str = "docs/superpowers/journals/2026-09-05-historical-cohorts.md"
    declared_on: str = "2026-09-07"
    claim_subtrees: int = 137714
    extraction_documents: int = 310829
    layers: tuple[ConfidenceLayerOutcome, ...] = (
        ConfidenceLayerOutcome("ac_skg_edges", 7607, "zero_confidence"),
        ConfidenceLayerOutcome("ac_skg_family_edges", 15945, "zero_confidence"),
        ConfidenceLayerOutcome("ac_skg_contested_edges", 723, "not_emitted"),
    )
    # Separate severity axis: these are evidence rows, not aggregate rows.
    adjudication_contradicting_evidence_rows: int = 342
    published_evidence_rows: int = 7868
    contradiction_basis: str = (
        "HC-F06/HC-F07; stored observational contradicts retained adjudication"
    )
    limitation: str = (
        "Stored values remain historical audit bytes. Outcomes describe retained memberships, "
        "not a full data-pass replay, paper truth, or the generating rule. "
        "Unregistered or rewritten databases require their own declaration; "
        "absence of this restriction is not evidence of current-rule reproducibility."
    )

    def to_payload(self) -> dict[str, Any]:
        """Emit the snapshot-level declaration for machine/audit consumers."""
        return asdict(self)


def confidence_layer_vintage(db_path: Path | str) -> ConfidenceLayerVintage | None:
    """Resolve the accepted declaration by complete file bytes, including renamed copies.

    This looks up an established measurement; it does not rerun its corpus census.
    Unregistered bytes return no known restriction, never a currentness verdict.
    Unreadable or changing input is ambiguous and cannot silently return no restriction.
    """
    path = Path(db_path)
    try:
        before = path.stat()
        with path.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        after = path.stat()
        if (before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
            after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns
        ):
            raise OSError("snapshot changed during vintage binding")
    except OSError as exc:
        raise ValueError("confidence_layer_vintage: ambiguous snapshot bytes") from exc
    if digest != _HISTORICAL_SNAPSHOT_SHA256:
        return None
    return ConfidenceLayerVintage(snapshot_sha256=digest)


def require_forwardable_confidence(db_path: Path | str) -> None:
    """Refuse forwarding registered historical confidence without replacing stored values."""
    declaration = confidence_layer_vintage(db_path)
    if declaration is not None:
        raise ValueError(json.dumps({"confidence_layer_vintage": declaration.to_payload()}))


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
