"""Public materialize projections module API."""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Iterable, Sequence

import pandas as pd

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import from_canonical_bytes
from polisyos.fabric.world.store.validate import (
    validate_claim_id,
    validate_conflict_set_id,
    validate_doc_fragment_ids,
    validate_doc_meta_ids,
    validate_quality_report_id,
    validate_trust_assessment_id,
    validate_world_event_id,
)
from polisyos.ir.canon import to_canonical_bytes
from polisyos.ir.world.claim import Claim
from polisyos.ir.world.conflict import ConflictSet
from polisyos.ir.world.doc import DocFragment, DocMeta
from polisyos.ir.world.event import WorldEvent
from polisyos.ir.world.quality import QualityReport
from polisyos.ir.world.trust import TrustAssessment

from .errors import WorldArtifactReadError, WorldMergeConflict


@dataclass
class ProjectionUpdateStats:
    """Projection update stats public type."""
    doc_versions: int = 0
    doc_sources: int = 0
    doc_fragments: int = 0
    claims: int = 0
    conflict_sets: int = 0
    trust_assessments: int = 0
    quality_reports: int = 0
    world_events: int = 0
    claim_citations: int = 0
    conflict_members: int = 0

    @property
    def total_updates(self) -> int:
        return (
            self.doc_versions
            + self.doc_sources
            + self.doc_fragments
            + self.claims
            + self.conflict_sets
            + self.trust_assessments
            + self.quality_reports
            + self.world_events
            + self.claim_citations
            + self.conflict_members
        )


def _canonical_json(value) -> str | None:
    if value is None:
        return None
    return to_canonical_bytes(value).decode("utf-8")


def _load_json_artifact(cas: FileSystemCAS, artifact_id: str) -> dict:
    try:
        aid = ArtifactID.model_validate(artifact_id)
        payload = from_canonical_bytes(cas.get_bytes(aid))
        if not isinstance(payload, dict):
            raise ValueError("artifact JSON must be an object")
        return payload
    except Exception as exc:  # pragma: no cover - defensive
        raise WorldArtifactReadError(
            f"failed to read artifact {artifact_id}: {exc}"
        ) from exc


def _load_doc_meta(cas: FileSystemCAS, artifact_id: str) -> DocMeta:
    try:
        payload = _load_json_artifact(cas, artifact_id)
        meta = DocMeta.model_validate(payload)
        validate_doc_meta_ids(meta)
        return meta
    except Exception as exc:
        if isinstance(exc, WorldArtifactReadError):
            raise
        raise WorldArtifactReadError(
            f"failed to load DocMeta artifact {artifact_id}: {exc}"
        ) from exc


def _load_doc_fragment(cas: FileSystemCAS, artifact_id: str) -> DocFragment:
    try:
        payload = _load_json_artifact(cas, artifact_id)
        fragment = DocFragment.model_validate(payload)
        validate_doc_fragment_ids(fragment)
        return fragment
    except Exception as exc:
        if isinstance(exc, WorldArtifactReadError):
            raise
        raise WorldArtifactReadError(
            f"failed to load DocFragment artifact {artifact_id}: {exc}"
        ) from exc


def _load_claim(cas: FileSystemCAS, artifact_id: str) -> Claim:
    try:
        payload = _load_json_artifact(cas, artifact_id)
        claim = Claim.model_validate(payload)
        validate_claim_id(claim)
        return claim
    except Exception as exc:
        if isinstance(exc, WorldArtifactReadError):
            raise
        raise WorldArtifactReadError(
            f"failed to load Claim artifact {artifact_id}: {exc}"
        ) from exc


def _load_conflict_set(cas: FileSystemCAS, artifact_id: str) -> ConflictSet:
    try:
        payload = _load_json_artifact(cas, artifact_id)
        conflict_set = ConflictSet.model_validate(payload)
        validate_conflict_set_id(conflict_set)
        return conflict_set
    except Exception as exc:
        if isinstance(exc, WorldArtifactReadError):
            raise
        raise WorldArtifactReadError(
            f"failed to load ConflictSet artifact {artifact_id}: {exc}"
        ) from exc


def _load_trust_assessment(cas: FileSystemCAS, artifact_id: str) -> TrustAssessment:
    try:
        payload = _load_json_artifact(cas, artifact_id)
        assessment = TrustAssessment.model_validate(payload)
        validate_trust_assessment_id(assessment)
        return assessment
    except Exception as exc:
        if isinstance(exc, WorldArtifactReadError):
            raise
        raise WorldArtifactReadError(
            f"failed to load TrustAssessment artifact {artifact_id}: {exc}"
        ) from exc


def _load_quality_report(cas: FileSystemCAS, artifact_id: str) -> QualityReport:
    try:
        payload = _load_json_artifact(cas, artifact_id)
        report = QualityReport.model_validate(payload)
        validate_quality_report_id(report)
        return report
    except Exception as exc:
        if isinstance(exc, WorldArtifactReadError):
            raise
        raise WorldArtifactReadError(
            f"failed to load QualityReport artifact {artifact_id}: {exc}"
        ) from exc


def _load_world_event(cas: FileSystemCAS, artifact_id: str) -> WorldEvent:
    try:
        payload = _load_json_artifact(cas, artifact_id)
        event = WorldEvent.model_validate(payload)
        validate_world_event_id(event)
        return event
    except Exception as exc:
        if isinstance(exc, WorldArtifactReadError):
            raise
        raise WorldArtifactReadError(
            f"failed to load WorldEvent artifact {artifact_id}: {exc}"
        ) from exc


def _register_df(conn, df: pd.DataFrame, *, prefix: str) -> str:
    safe_prefix = prefix.replace(".", "_").replace("-", "_")
    name = f"{safe_prefix}_{uuid.uuid4().hex}"
    conn.register(name, df)
    return name


def _apply_rows(conn, table: str, pk_col: str, rows: list[dict]) -> int:
    if not rows:
        return 0
    df = pd.DataFrame(rows)
    if df.empty:
        return 0
    df = df.drop_duplicates(subset=[pk_col], keep="last")
    ids_df = df[[pk_col]].drop_duplicates()
    ids_name = _register_df(conn, ids_df, prefix=f"{pk_col}_ids")
    try:
        conn.execute(
            f"DELETE FROM {table} WHERE {pk_col} IN (SELECT {pk_col} FROM {ids_name})"
        )
    finally:
        conn.unregister(ids_name)

    data_name = _register_df(conn, df, prefix=f"{table}_rows")
    try:
        cols = ", ".join(df.columns)
        conn.execute(f"INSERT INTO {table} ({cols}) SELECT {cols} FROM {data_name}")
    finally:
        conn.unregister(data_name)
    return 1


def _build_doc_version_rows(
    cas: FileSystemCAS,
    artifact_ids: Iterable[str],
) -> tuple[list[dict], list[DocMeta]]:
    rows: list[dict] = []
    metas: list[DocMeta] = []
    for artifact_id in artifact_ids:
        meta = _load_doc_meta(cas, artifact_id)
        metas.append(meta)
        rows.append(
            {
                "doc_version_id": meta.doc_version_id,
                "doc_source_id": meta.doc_source_id,
                "retrieved_at": meta.retrieved_at,
                "mime": meta.mime,
                "license": meta.license,
                "jurisdiction": meta.jurisdiction,
                "language": meta.language,
                "raw_ref": meta.raw_ref,
                "normalized_ref": meta.normalized_ref,
                "structure_ref": meta.structure_ref,
                "chunks_ref": meta.chunks_ref,
                "props_json": _canonical_json(meta.props),
                "meta_artifact_id": artifact_id,
            }
        )
    return rows, metas


def _build_doc_source_rows(metas: Iterable[DocMeta]) -> list[dict]:
    sources: dict[str, dict] = {}
    for meta in metas:
        entry = sources.setdefault(
            meta.doc_source_id,
            {
                "doc_source_id": meta.doc_source_id,
                "canonical_url": None,
                "official_id": None,
                "jurisdiction": None,
                "language": None,
                "_jurisdiction_time": None,
                "_language_time": None,
            },
        )
        if meta.canonical_url is not None:
            if entry["canonical_url"] and entry["canonical_url"] != meta.canonical_url:
                raise WorldMergeConflict(
                    f"doc_source_id {meta.doc_source_id} canonical_url conflict"
                )
            entry["canonical_url"] = meta.canonical_url
        if meta.official_id is not None:
            if entry["official_id"] and entry["official_id"] != meta.official_id:
                raise WorldMergeConflict(
                    f"doc_source_id {meta.doc_source_id} official_id conflict"
                )
            entry["official_id"] = meta.official_id

        if meta.jurisdiction is not None:
            prev = entry.get("_jurisdiction_time")
            if prev is None or meta.retrieved_at > prev:
                entry["jurisdiction"] = meta.jurisdiction
                entry["_jurisdiction_time"] = meta.retrieved_at

        if meta.language is not None:
            prev = entry.get("_language_time")
            if prev is None or meta.retrieved_at > prev:
                entry["language"] = meta.language
                entry["_language_time"] = meta.retrieved_at

    rows: list[dict] = []
    for entry in sources.values():
        entry.pop("_jurisdiction_time", None)
        entry.pop("_language_time", None)
        rows.append(entry)
    return rows


def _build_doc_fragment_rows(
    cas: FileSystemCAS,
    artifact_ids: Iterable[str],
) -> list[dict]:
    rows: list[dict] = []
    for artifact_id in artifact_ids:
        fragment = _load_doc_fragment(cas, artifact_id)
        locator = fragment.locator
        rows.append(
            {
                "fragment_id": fragment.fragment_id,
                "doc_version_id": fragment.doc_version_id,
                "anchor_kind": locator.anchor_kind.value,
                "anchor_path": locator.anchor_path,
                "offset_start": locator.offset_start,
                "offset_end": locator.offset_end,
                "page_start": locator.page_start,
                "page_end": locator.page_end,
                "text_hash": fragment.text_hash,
                "quote_preview": fragment.quote_preview,
                "props_json": _canonical_json(fragment.props),
                "meta_artifact_id": artifact_id,
            }
        )
    return rows


def _build_claim_rows(
    cas: FileSystemCAS,
    artifact_ids: Iterable[str],
) -> list[dict]:
    rows: list[dict] = []
    for artifact_id in artifact_ids:
        claim = _load_claim(cas, artifact_id)
        rows.append(
            {
                "claim_id": claim.claim_id,
                "predicate_id": claim.predicate_id,
                "subject_id": claim.subject_id,
                "subject_text": claim.subject_text,
                "value_text": claim.value_text,
                "value_decimal": (
                    str(claim.value_decimal) if claim.value_decimal is not None else None
                ),
                "unit_id": claim.unit_id,
                "confidence": str(claim.confidence) if claim.confidence is not None else None,
                "source_kind": claim.source_kind.value,
                "jurisdiction": claim.jurisdiction,
                "domain": claim.domain,
                "valid_from": claim.valid_from,
                "valid_to": claim.valid_to,
                "qualifiers_json": _canonical_json(claim.qualifiers),
                "props_json": _canonical_json(claim.props),
                "meta_artifact_id": artifact_id,
            }
        )
    return rows


def _build_conflict_set_rows(
    cas: FileSystemCAS,
    artifact_ids: Iterable[str],
) -> list[dict]:
    rows: list[dict] = []
    for artifact_id in artifact_ids:
        conflict_set = _load_conflict_set(cas, artifact_id)
        rows.append(
            {
                "conflict_set_id": conflict_set.conflict_set_id,
                "conflict_key": conflict_set.conflict_key,
                "conflict_kind": conflict_set.conflict_kind.value,
                "winner_claim_id": (
                    conflict_set.resolution.winner_claim_id
                    if conflict_set.resolution is not None
                    else None
                ),
                "resolution_policy_id": (
                    conflict_set.resolution.policy_id
                    if conflict_set.resolution is not None
                    else None
                ),
                "resolution_confidence": (
                    str(conflict_set.resolution.confidence)
                    if conflict_set.resolution is not None
                    else None
                ),
                "resolution_artifact_id": (
                    conflict_set.resolution.resolution_artifact_id
                    if conflict_set.resolution is not None
                    else None
                ),
                "meta_artifact_id": artifact_id,
                "props_json": _canonical_json(conflict_set.props),
            }
        )
    return rows


def _build_trust_assessment_rows(
    cas: FileSystemCAS,
    artifact_ids: Iterable[str],
) -> list[dict]:
    rows: list[dict] = []
    for artifact_id in artifact_ids:
        assessment = _load_trust_assessment(cas, artifact_id)
        rows.append(
            {
                "trust_assessment_id": assessment.trust_assessment_id,
                "target_world_id": assessment.target_world_id,
                "policy_id": assessment.policy_id,
                "algorithm_version": assessment.algorithm_version,
                "score": str(assessment.score),
                "tier": assessment.tier.value,
                "features_json": _canonical_json(assessment.features),
                "rationale_json": _canonical_json(assessment.rationale),
                "props_json": _canonical_json(assessment.props),
                "meta_artifact_id": artifact_id,
            }
        )
    return rows


def _build_quality_report_rows(
    cas: FileSystemCAS,
    artifact_ids: Iterable[str],
) -> list[dict]:
    rows: list[dict] = []
    for artifact_id in artifact_ids:
        report = _load_quality_report(cas, artifact_id)
        rows.append(
            {
                "quality_report_id": report.quality_report_id,
                "scope": report.scope.value,
                "run_event_id": report.run_event_id,
                "policy_id": report.policy_id,
                "algorithm_version": report.algorithm_version,
                "metrics_json": _canonical_json(report.metrics),
                "issues_json": _canonical_json(
                    [issue.model_dump(mode="python") for issue in report.issues]
                ),
                "props_json": _canonical_json(report.props),
                "meta_artifact_id": artifact_id,
            }
        )
    return rows


def _build_world_event_rows(
    cas: FileSystemCAS,
    artifact_ids: Iterable[str],
) -> list[dict]:
    rows: list[dict] = []
    for artifact_id in artifact_ids:
        event = _load_world_event(cas, artifact_id)
        rows.append(
            {
                "event_id": event.event_id,
                "event_kind": event.event_kind.value,
                "agent_id": event.agent.agent_id,
                "agent_type": event.agent.agent_type.value,
                "agent_label": event.agent.label,
                "activity_id": event.activity.activity_id,
                "activity_type": event.activity.activity_type.value,
                "activity_label": event.activity.label,
                "started_at": event.activity.started_at,
                "ended_at": event.activity.ended_at,
                "evidence_ref": event.evidence_ref,
                "provenance_ref": event.provenance_ref,
                "props_json": _canonical_json(event.props),
                "meta_artifact_id": artifact_id,
            }
        )
    return rows


def _update_claim_citations(
    conn,
    *,
    touched_claim_ids: Sequence[str],
    touched_fragment_ids: Sequence[str],
) -> int:
    if not touched_claim_ids and not touched_fragment_ids:
        return 0

    claim_df = pd.DataFrame(
        {"claim_id": pd.Series(list(touched_claim_ids), dtype="string")}
    )
    fragment_df = pd.DataFrame(
        {"fragment_id": pd.Series(list(touched_fragment_ids), dtype="string")}
    )

    claim_name = _register_df(conn, claim_df, prefix="claim_ids")
    fragment_name = _register_df(conn, fragment_df, prefix="fragment_ids")
    try:
        conn.execute(
            f"""
            DELETE FROM world.claim_citations
            WHERE claim_id IN (SELECT claim_id FROM {claim_name})
               OR fragment_id IN (SELECT fragment_id FROM {fragment_name})
            """
        )

        conn.execute(
            f"""
            INSERT INTO world.claim_citations (claim_id, fragment_id, edge_id)
            SELECT
                src_id AS claim_id,
                dst_id AS fragment_id,
                MIN(edge_id) AS edge_id
            FROM world.world_edges
            WHERE kind = 'claim.cites'
              AND (
                src_id IN (SELECT claim_id FROM {claim_name})
                OR dst_id IN (SELECT fragment_id FROM {fragment_name})
              )
            GROUP BY src_id, dst_id
            """
        )
    finally:
        conn.unregister(claim_name)
        conn.unregister(fragment_name)
    return 1


def _update_conflict_members(
    conn,
    *,
    touched_conflict_set_ids: Sequence[str],
    touched_claim_ids: Sequence[str],
) -> int:
    if not touched_conflict_set_ids and not touched_claim_ids:
        return 0

    conflict_df = pd.DataFrame(
        {"conflict_set_id": pd.Series(list(touched_conflict_set_ids), dtype="string")}
    )
    claim_df = pd.DataFrame(
        {"claim_id": pd.Series(list(touched_claim_ids), dtype="string")}
    )

    conflict_name = _register_df(conn, conflict_df, prefix="conflict_set_ids")
    claim_name = _register_df(conn, claim_df, prefix="claim_ids")
    try:
        conn.execute(
            f"""
            DELETE FROM world.conflict_members
            WHERE conflict_set_id IN (SELECT conflict_set_id FROM {conflict_name})
               OR claim_id IN (SELECT claim_id FROM {claim_name})
            """
        )

        conn.execute(
            f"""
            INSERT INTO world.conflict_members (
                conflict_set_id,
                claim_id,
                edge_id,
                role,
                rank
            )
            SELECT
                dst_id AS conflict_set_id,
                src_id AS claim_id,
                MIN(edge_id) AS edge_id,
                'member' AS role,
                NULL AS rank
            FROM world.world_edges
            WHERE kind = 'claim.in_conflict_set'
              AND (
                dst_id IN (SELECT conflict_set_id FROM {conflict_name})
                OR src_id IN (SELECT claim_id FROM {claim_name})
              )
            GROUP BY dst_id, src_id
            """
        )
    finally:
        conn.unregister(conflict_name)
        conn.unregister(claim_name)
    return 1


def update_projections(
    conn,
    cas: FileSystemCAS,
    *,
    touched_node_ids: Sequence[str],
) -> ProjectionUpdateStats:
    """Update projections helper."""
    stats = ProjectionUpdateStats()
    if not touched_node_ids:
        return stats

    touched_df = pd.DataFrame({"node_id": list(touched_node_ids)})
    touched_name = _register_df(conn, touched_df, prefix="touched_nodes")
    try:
        nodes_df = conn.execute(
            f"""
            SELECT n.node_id, n.kind, n.artifact_id
            FROM world.world_nodes n
            INNER JOIN {touched_name} t
                ON n.node_id = t.node_id
            """
        ).df()
    finally:
        conn.unregister(touched_name)

    if nodes_df.empty:
        return stats

    def _artifact_ids_for(kind_value: str) -> list[str]:
        subset = nodes_df[(nodes_df["kind"] == kind_value) & nodes_df["artifact_id"].notna()]
        return [str(value) for value in subset["artifact_id"].tolist()]

    doc_version_artifacts = _artifact_ids_for("doc.version")
    if doc_version_artifacts:
        doc_version_rows, metas = _build_doc_version_rows(cas, doc_version_artifacts)
        stats.doc_versions = _apply_rows(
            conn, "world.doc_versions", "doc_version_id", doc_version_rows
        )
        doc_source_rows = _build_doc_source_rows(metas)
        stats.doc_sources = _apply_rows(
            conn, "world.doc_sources", "doc_source_id", doc_source_rows
        )

    doc_fragment_artifacts = _artifact_ids_for("doc.fragment")
    if doc_fragment_artifacts:
        doc_fragment_rows = _build_doc_fragment_rows(cas, doc_fragment_artifacts)
        stats.doc_fragments = _apply_rows(
            conn, "world.doc_fragments", "fragment_id", doc_fragment_rows
        )

    claim_artifacts = _artifact_ids_for("claim")
    if claim_artifacts:
        claim_rows = _build_claim_rows(cas, claim_artifacts)
        stats.claims = _apply_rows(conn, "world.claims", "claim_id", claim_rows)

    conflict_set_artifacts = _artifact_ids_for("conflict_set")
    if conflict_set_artifacts:
        conflict_set_rows = _build_conflict_set_rows(cas, conflict_set_artifacts)
        stats.conflict_sets = _apply_rows(
            conn, "world.conflict_sets", "conflict_set_id", conflict_set_rows
        )

    trust_assessment_artifacts = _artifact_ids_for("trust.assessment")
    if trust_assessment_artifacts:
        trust_rows = _build_trust_assessment_rows(cas, trust_assessment_artifacts)
        stats.trust_assessments = _apply_rows(
            conn,
            "world.trust_assessments",
            "trust_assessment_id",
            trust_rows,
        )

    quality_report_artifacts = _artifact_ids_for("quality.report")
    if quality_report_artifacts:
        quality_rows = _build_quality_report_rows(cas, quality_report_artifacts)
        stats.quality_reports = _apply_rows(
            conn,
            "world.quality_reports",
            "quality_report_id",
            quality_rows,
        )

    event_artifacts = _artifact_ids_for("world.event")
    if event_artifacts:
        event_rows = _build_world_event_rows(cas, event_artifacts)
        stats.world_events = _apply_rows(
            conn, "world.world_events", "event_id", event_rows
        )

    touched_claim_ids = nodes_df[nodes_df["kind"] == "claim"]["node_id"].tolist()
    touched_fragment_ids = nodes_df[nodes_df["kind"] == "doc.fragment"][
        "node_id"
    ].tolist()
    stats.claim_citations = _update_claim_citations(
        conn,
        touched_claim_ids=touched_claim_ids,
        touched_fragment_ids=touched_fragment_ids,
    )
    touched_conflict_set_ids = nodes_df[nodes_df["kind"] == "conflict_set"][
        "node_id"
    ].tolist()
    stats.conflict_members = _update_conflict_members(
        conn,
        touched_conflict_set_ids=touched_conflict_set_ids,
        touched_claim_ids=touched_claim_ids,
    )

    return stats


__all__ = [
    "ProjectionUpdateStats",
    "update_projections",
]
