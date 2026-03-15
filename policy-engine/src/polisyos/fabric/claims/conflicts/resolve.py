from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from polisyos.common.logger import get_logger
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.fabric.claims.errors import ClaimValidationError
from polisyos.fabric.claims.persist import load_json_artifact, write_claims_world_segment
from polisyos.fabric.io.db import SimulationDB
from polisyos.fabric.storage import DuckDBStorageAdapter, StoragePort
from polisyos.fabric.world import (
    emit_edge_fact,
    emit_world_node_facts,
    persist_conflict_set,
    persist_quality_report,
    persist_trust_assessment,
    stable_world_provenance_v1,
    validate_conflict_set_id,
)
from polisyos.ir.analytics.uncertainty import persist_uncertainty_envelope
from polisyos.ir.canon import to_canonical_bytes
from polisyos.ir.world.abi import EdgeKind, NodeKind
from polisyos.ir.world.conflict import (
    ConflictResolution,
    ConflictResolutionCandidate,
    ConflictResolutionInputs,
    ConflictSet,
    ConflictSetResolution,
)
from polisyos.ir.world.event import (
    EventKind,
    ProvActivityType,
    WorldObjectRef,
)
from polisyos.ir.world.ids import (
    quality_report_id_from_payload,
    trust_assessment_id_from_payload,
)
from polisyos.ir.world.quality import (
    QualityIssue,
    QualityIssueSeverity,
    QualityReport,
    QualityScope,
)
from polisyos.ir.world.trust import TrustAssessment, TrustTier

from ..world_events import build_claims_world_event, persist_claims_world_event
from .detect import (
    _all_claim_artifacts_from_db,
    _load_claim_refs_from_claim_sets,
    _load_claims,
    _query_claim_artifacts_from_db,
    detect_conflicts,
)
from .policies import get_conflict_policy
from .score_claims import score_claim_trust_assessments
from .score_docs import score_doc_trust_assessments
from .types import ConflictResolveOptions, ConflictResolveResult, RankedClaim
from .uncertainty_adapter import envelope_from_conflict_resolution

logger = get_logger(__name__)

_CONFLICT_RESOLUTION_SCHEMA = SchemaInfo(name="fabric.claims.conflict_resolution", version="1.0")
_Q4 = Decimal("0.0001")


def _quantize(value: Decimal) -> Decimal:
    return value.quantize(_Q4, rounding=ROUND_HALF_UP)


def _tier(score: Decimal) -> TrustTier:
    if score >= Decimal("0.75"):
        return TrustTier.HIGH
    if score >= Decimal("0.55"):
        return TrustTier.MEDIUM
    return TrustTier.LOW


def _query_conflict_set_artifacts(
    db: SimulationDB, conflict_set_ids: list[str] | None
) -> dict[str, str]:
    if conflict_set_ids:
        ids = sorted(set(conflict_set_ids))
        placeholders = ", ".join(["?"] * len(ids))
        rows = db.conn.execute(
            f"""
            SELECT conflict_set_id, meta_artifact_id
            FROM world.conflict_sets
            WHERE conflict_set_id IN ({placeholders})
              AND meta_artifact_id IS NOT NULL
            """,
            ids,
        ).fetchall()
    else:
        rows = db.conn.execute(
            """
            SELECT conflict_set_id, meta_artifact_id
            FROM world.conflict_sets
            WHERE meta_artifact_id IS NOT NULL
            """
        ).fetchall()
    return {str(conflict_set_id): str(artifact_id) for conflict_set_id, artifact_id in rows}


def _load_conflict_set(cas: FileSystemCAS, artifact_id: str) -> ConflictSet:
    payload = load_json_artifact(cas, artifact_id)
    conflict_set = ConflictSet.model_validate(payload)
    validate_conflict_set_id(conflict_set)
    return conflict_set


def _query_doc_meta_artifacts(
    db: SimulationDB | None, doc_version_ids: list[str]
) -> dict[str, str]:
    if db is None or not doc_version_ids:
        return {}
    placeholders = ", ".join(["?"] * len(doc_version_ids))
    rows = db.conn.execute(
        f"""
        SELECT doc_version_id, meta_artifact_id
        FROM world.doc_versions
        WHERE doc_version_id IN ({placeholders})
          AND meta_artifact_id IS NOT NULL
        """,
        doc_version_ids,
    ).fetchall()
    return {str(doc_version_id): str(artifact_id) for doc_version_id, artifact_id in rows}


def _doc_meta_artifacts_from_claim_sets(
    *,
    cas: FileSystemCAS,
    claim_set_artifact_ids: list[str],
) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for artifact_id in sorted(set(claim_set_artifact_ids)):
        payload = load_json_artifact(cas, artifact_id)
        doc_version_id = payload.get("doc_version_id")
        doc_meta_artifact_id = payload.get("doc_meta_artifact_id")
        if not isinstance(doc_version_id, str) or not isinstance(doc_meta_artifact_id, str):
            continue
        current = mapping.get(doc_version_id)
        if current is None or doc_meta_artifact_id < current:
            mapping[doc_version_id] = doc_meta_artifact_id
    return mapping


def _query_fragment_anchor_kinds(
    db: SimulationDB | None, fragment_ids: list[str]
) -> dict[str, str]:
    if db is None or not fragment_ids:
        return {}
    placeholders = ", ".join(["?"] * len(fragment_ids))
    rows = db.conn.execute(
        f"""
        SELECT fragment_id, anchor_kind
        FROM world.doc_fragments
        WHERE fragment_id IN ({placeholders})
        """,
        fragment_ids,
    ).fetchall()
    return {str(fragment_id): str(anchor_kind) for fragment_id, anchor_kind in rows}


def _query_agent_ids_by_claim(db: SimulationDB | None, claim_ids: list[str]) -> dict[str, str]:
    if db is None or not claim_ids:
        return {}
    placeholders = ", ".join(["?"] * len(claim_ids))
    rows = db.conn.execute(
        f"""
        SELECT generated.src_id AS claim_id, MIN(agent.dst_id) AS agent_id
        FROM world.world_edges generated
        JOIN world.world_edges agent
          ON agent.src_id = generated.dst_id
         AND agent.kind = 'prov.was_associated_with'
        WHERE generated.kind = 'prov.was_generated_by'
          AND generated.src_id IN ({placeholders})
        GROUP BY generated.src_id
        """,
        claim_ids,
    ).fetchall()
    return {str(claim_id): str(agent_id) for claim_id, agent_id in rows}


def _extractor_ids_from_claim_sets(
    *, cas: FileSystemCAS, claim_set_artifact_ids: list[str]
) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for artifact_id in sorted(set(claim_set_artifact_ids)):
        payload = load_json_artifact(cas, artifact_id)
        extractor_id = payload.get("extractor_id")
        if not isinstance(extractor_id, str):
            continue
        claim_rows = payload.get("claims")
        if not isinstance(claim_rows, list):
            continue
        for row in claim_rows:
            if not isinstance(row, dict):
                continue
            claim_id = row.get("claim_id")
            if isinstance(claim_id, str):
                mapping.setdefault(claim_id, extractor_id)
    return mapping


def _query_extractor_ids_by_claim_from_db(
    *,
    cas: FileSystemCAS,
    db: SimulationDB | None,
    claim_ids: list[str],
) -> dict[str, str]:
    if db is None or not claim_ids:
        return {}
    placeholders = ", ".join(["?"] * len(claim_ids))
    rows = db.conn.execute(
        f"""
        SELECT generated.src_id AS claim_id, output.src_id AS artifact_world_id
        FROM world.world_edges generated
        JOIN world.world_edges output
          ON output.dst_id = generated.dst_id
         AND output.kind = 'prov.was_generated_by'
        WHERE generated.kind = 'prov.was_generated_by'
          AND generated.src_id IN ({placeholders})
          AND output.src_id LIKE 'artifact.%'
        """,
        claim_ids,
    ).fetchall()
    if not rows:
        return {}

    artifact_world_ids = sorted({str(world_id) for _, world_id in rows})
    placeholders_nodes = ", ".join(["?"] * len(artifact_world_ids))
    node_rows = db.conn.execute(
        f"""
        SELECT node_id, artifact_id
        FROM world.world_nodes
        WHERE node_id IN ({placeholders_nodes})
          AND artifact_id IS NOT NULL
        """,
        artifact_world_ids,
    ).fetchall()
    artifact_by_world = {str(node_id): str(artifact_id) for node_id, artifact_id in node_rows}

    candidates: dict[str, list[tuple[int, str, str]]] = {}
    for claim_id, artifact_world_id in rows:
        artifact_id = artifact_by_world.get(str(artifact_world_id))
        if artifact_id is None:
            continue
        try:
            manifest = cas.get_manifest(ArtifactID.model_validate(artifact_id))
        except Exception:
            logger.debug(
                "Failed to load manifest for artifact %s", artifact_id, exc_info=True,
            )
            continue
        if manifest.kind != "fabric.claims.claim_set":
            continue
        payload = load_json_artifact(cas, artifact_id)
        claim_rows = payload.get("claims")
        if not isinstance(claim_rows, list):
            continue
        if not any(
            isinstance(row, dict) and row.get("claim_id") == str(claim_id) for row in claim_rows
        ):
            continue
        extractor_id = payload.get("extractor_id")
        if not isinstance(extractor_id, str):
            continue
        stage = str(payload.get("stage", ""))
        stage_rank = 0 if stage == "normalize_v1" else 1 if stage == "extract_v1" else 2
        candidates.setdefault(str(claim_id), []).append((stage_rank, artifact_id, extractor_id))

    mapping: dict[str, str] = {}
    for claim_id, values in candidates.items():
        _, _, extractor_id = sorted(values)[0]
        mapping[claim_id] = extractor_id
    return mapping


def rank_conflict_candidates(
    *,
    member_claim_ids: list[str],
    claim_breakdown_by_id: dict[str, dict[str, Decimal]],
    claim_assessment_by_id: dict[str, TrustAssessment],
) -> list[RankedClaim]:
    ranked: list[RankedClaim] = []
    for claim_id in member_claim_ids:
        assessment = claim_assessment_by_id[claim_id]
        ranked.append(
            RankedClaim(
                claim_id=claim_id,
                score_total=assessment.score,
                score_breakdown=claim_breakdown_by_id.get(claim_id, {}),
            )
        )
    ranked.sort(key=lambda row: (-row.score_total, row.claim_id))
    return ranked


def _persist_conflict_resolution(cas: FileSystemCAS, resolution: ConflictResolution) -> str:
    ref = cas.put_json(
        resolution.model_dump(),
        opts=PutOptions(
            kind="fabric.claims.conflict_resolution",
            media_type="application/json",
            schema=_CONFLICT_RESOLUTION_SCHEMA,
        ),
    )
    return str(ref.artifact_id)


def _build_cset_assessment(
    *,
    policy_id: str,
    algorithm_version: str,
    conflict_set_id: str,
    winner_claim_id: str,
    members_count: int,
    score: Decimal,
    conflict_kind: str,
) -> TrustAssessment:
    tier = _tier(score)
    features = {
        "winner_claim_id": winner_claim_id,
        "members_count": members_count,
        "winner_score": str(score),
    }
    rationale = [
        {"feature": "winner_claim_id", "value": winner_claim_id},
        {"feature": "winner_score", "value": str(score)},
    ]
    props = {"conflict_kind": conflict_kind}
    payload = {
        "policy_id": policy_id,
        "algorithm_version": algorithm_version,
        "target_world_id": conflict_set_id,
        "score": score,
        "tier": tier.value,
        "features": features,
        "rationale": rationale,
        "props": props,
    }
    return TrustAssessment(
        trust_assessment_id=trust_assessment_id_from_payload(payload=payload),
        policy_id=policy_id,
        algorithm_version=algorithm_version,
        target_world_id=conflict_set_id,
        score=score,
        tier=tier,
        features=features,
        rationale=rationale,
        props=props,
    )


def resolve_conflicts(
    *,
    cas: FileSystemCAS,
    fact_log_root: Path,
    storage: StoragePort | None = None,
    db: SimulationDB | None = None,
    conflict_set_ids: list[str] | None = None,
    claim_ids: list[str] | None = None,
    claim_set_artifact_ids: list[str] | None = None,
    policy_id: str,
    options: ConflictResolveOptions | None = None,
    segment_name: str | None = None,
) -> ConflictResolveResult:
    resolved_db = _resolve_simulation_db(storage=storage, db=db)
    opts = options or ConflictResolveOptions()
    policy = get_conflict_policy(policy_id)

    detect_result = None
    if conflict_set_ids is None and claim_ids:
        if db is None and not claim_set_artifact_ids:
            raise ClaimValidationError(
                "resolve_conflicts with claim_ids requires db or claim_set_artifact_ids"
            )
        detect_result = detect_conflicts(
            cas=cas,
            fact_log_root=fact_log_root,
            storage=storage,
            db=resolved_db,
            claim_ids=claim_ids,
            claim_set_artifact_ids=claim_set_artifact_ids,
            policy_id=policy_id,
            segment_name=f"{segment_name or 'claims_resolve_conflicts'}_detect",
        )
        conflict_set_ids = detect_result.conflict_set_ids

    conflict_sets_by_id: dict[str, ConflictSet] = {}
    conflict_artifacts_by_id: dict[str, str] = {}
    if detect_result is not None:
        for artifact_id in detect_result.conflict_set_artifact_ids:
            conflict_set = _load_conflict_set(cas, artifact_id)
            conflict_sets_by_id[conflict_set.conflict_set_id] = conflict_set
            conflict_artifacts_by_id[conflict_set.conflict_set_id] = artifact_id

    if resolved_db is not None:
        db_artifacts = _query_conflict_set_artifacts(resolved_db, conflict_set_ids)
        for conflict_set_id, artifact_id in db_artifacts.items():
            if conflict_set_id in conflict_sets_by_id:
                continue
            conflict_set = _load_conflict_set(cas, artifact_id)
            conflict_sets_by_id[conflict_set_id] = conflict_set
            conflict_artifacts_by_id[conflict_set_id] = artifact_id

    if conflict_set_ids is not None:
        missing_conflict_set_ids = sorted(
            set(conflict_set_ids) - set(conflict_sets_by_id)
        )
        if missing_conflict_set_ids and (claim_ids or claim_set_artifact_ids):
            fallback_detect = detect_conflicts(
                cas=cas,
                fact_log_root=fact_log_root,
                storage=storage,
                db=resolved_db,
                claim_ids=claim_ids,
                claim_set_artifact_ids=claim_set_artifact_ids,
                policy_id=policy_id,
                segment_name=f"{segment_name or 'claims_resolve_conflicts'}_detect_fallback",
            )
            for artifact_id in fallback_detect.conflict_set_artifact_ids:
                conflict_set = _load_conflict_set(cas, artifact_id)
                conflict_sets_by_id[conflict_set.conflict_set_id] = conflict_set
                conflict_artifacts_by_id[conflict_set.conflict_set_id] = artifact_id
            if detect_result is None:
                detect_result = fallback_detect

    if conflict_set_ids is not None:
        for conflict_set_id in sorted(set(conflict_set_ids)):
            if conflict_set_id not in conflict_sets_by_id:
                raise ClaimValidationError(
                    "missing conflict_set artifact for "
                    f"{conflict_set_id}; require db materialization"
                )
    ordered_conflict_set_ids = sorted(conflict_sets_by_id)

    member_claim_ids = sorted(
        {
            claim_id
            for conflict_set in conflict_sets_by_id.values()
            for claim_id in conflict_set.member_claim_ids
        }
    )
    if claim_ids is not None:
        member_claim_ids = sorted(set(member_claim_ids).union(set(claim_ids)))

    claim_artifact_ids_by_id: dict[str, str] = {}
    if detect_result is not None:
        claim_artifact_ids_by_id.update(detect_result.claim_artifact_ids_by_id)
    if claim_set_artifact_ids:
        claim_artifact_ids_by_id.update(
            _load_claim_refs_from_claim_sets(cas=cas, claim_set_artifact_ids=claim_set_artifact_ids)
        )
    if resolved_db is not None:
        claim_artifact_ids_by_id.update(_query_claim_artifacts_from_db(resolved_db, member_claim_ids))
    if not claim_artifact_ids_by_id and resolved_db is not None:
        claim_artifact_ids_by_id.update(_all_claim_artifacts_from_db(resolved_db))
    claims_by_id = (
        _load_claims(
            cas=cas,
            claim_ids=member_claim_ids,
            claim_artifact_ids_by_id=claim_artifact_ids_by_id,
        )
        if member_claim_ids
        else {}
    )

    doc_version_ids = sorted(
        {
            citation.doc.doc_version_id
            for claim in claims_by_id.values()
            for citation in claim.citations
            if citation.doc.doc_version_id is not None
        }
    )
    fragment_ids = sorted(
        {
            citation.fragment_id
            for claim in claims_by_id.values()
            for citation in claim.citations
            if citation.fragment_id is not None
        }
    )

    doc_meta_artifacts_by_doc = _query_doc_meta_artifacts(resolved_db, doc_version_ids)
    if claim_set_artifact_ids:
        fallback_doc_meta = _doc_meta_artifacts_from_claim_sets(
            cas=cas,
            claim_set_artifact_ids=claim_set_artifact_ids,
        )
        for doc_version_id, artifact_id in fallback_doc_meta.items():
            doc_meta_artifacts_by_doc.setdefault(doc_version_id, artifact_id)
    missing_doc_versions = sorted(set(doc_version_ids) - set(doc_meta_artifacts_by_doc))
    doc_assessments_by_doc = score_doc_trust_assessments(
        cas=cas,
        doc_meta_artifact_ids=sorted(set(doc_meta_artifacts_by_doc.values())),
        policy=policy,
        policy_id=policy_id,
        algorithm_version=opts.trust_algorithm_version,
    )
    extractor_by_claim = {}
    if claim_set_artifact_ids:
        extractor_by_claim.update(
            _extractor_ids_from_claim_sets(cas=cas, claim_set_artifact_ids=claim_set_artifact_ids)
        )
    missing_extractors = sorted(set(member_claim_ids) - set(extractor_by_claim))
    extractor_by_claim.update(
        _query_extractor_ids_by_claim_from_db(
            cas=cas,
            db=resolved_db,
            claim_ids=missing_extractors,
        )
    )
    agent_by_claim = _query_agent_ids_by_claim(resolved_db, member_claim_ids)
    fragment_anchor_kind_by_id = _query_fragment_anchor_kinds(resolved_db, fragment_ids)
    if resolved_db is None and fragment_ids:
        for fragment_id in fragment_ids:
            fragment_anchor_kind_by_id.setdefault(fragment_id, "chunk")

    claim_assessments_by_claim, claim_breakdown_by_claim = score_claim_trust_assessments(
        claims_by_id=claims_by_id,
        conflict_sets=[conflict_sets_by_id[cid] for cid in ordered_conflict_set_ids],
        doc_trust_by_doc_version=doc_assessments_by_doc,
        extractor_id_by_claim=extractor_by_claim,
        agent_id_by_claim=agent_by_claim,
        fragment_anchor_kind_by_id=fragment_anchor_kind_by_id,
        policy=policy,
        policy_id=policy_id,
        algorithm_version=opts.trust_algorithm_version,
    )

    stable_prov = stable_world_provenance_v1()
    facts = []

    trust_artifact_by_id: dict[str, str] = {}
    all_trust_assessments: dict[str, TrustAssessment] = {}
    for assessment in doc_assessments_by_doc.values():
        all_trust_assessments[assessment.trust_assessment_id] = assessment
    for assessment in claim_assessments_by_claim.values():
        all_trust_assessments[assessment.trust_assessment_id] = assessment
    for trust_id in sorted(all_trust_assessments):
        assessment = all_trust_assessments[trust_id]
        trust_ref = persist_trust_assessment(cas, assessment)
        trust_artifact_id = str(trust_ref.artifact_id)
        trust_artifact_by_id[trust_id] = trust_artifact_id
        facts.extend(
            emit_world_node_facts(
                node_id=trust_id,
                kind=NodeKind.TRUST_ASSESSMENT,
                label=assessment.tier.value,
                artifact_id=trust_artifact_id,
                props_ref=None,
                provenance=stable_prov,
            )
        )
        facts.append(
            emit_edge_fact(
                src_id=trust_id,
                edge_kind=EdgeKind.REPORT_ABOUT,
                dst_id=assessment.target_world_id,
                provenance=stable_prov,
            )
        )

    winner_by_conflict: dict[str, str] = {}
    updated_conflict_artifacts: dict[str, str] = {}
    resolution_artifact_ids: list[str] = []
    uncertainty_envelope_artifact_ids: list[str] = []
    contradict_edges = 0
    for conflict_set_id in ordered_conflict_set_ids:
        conflict_set = conflict_sets_by_id[conflict_set_id]
        ranked = rank_conflict_candidates(
            member_claim_ids=conflict_set.member_claim_ids,
            claim_breakdown_by_id=claim_breakdown_by_claim,
            claim_assessment_by_id=claim_assessments_by_claim,
        )
        if not ranked:
            continue
        winner = ranked[0].claim_id
        winner_score = _quantize(ranked[0].score_total)
        winner_by_conflict[conflict_set_id] = winner

        member_doc_versions = sorted(
            {
                citation.doc.doc_version_id
                for claim_id in conflict_set.member_claim_ids
                for citation in claims_by_id[claim_id].citations
                if citation.doc.doc_version_id is not None
            }
        )
        trust_ids_input = sorted(
            {
                *[
                    assessment.trust_assessment_id
                    for assessment in doc_assessments_by_doc.values()
                    if assessment.target_world_id in member_doc_versions
                ],
                *[
                    claim_assessments_by_claim[claim_id].trust_assessment_id
                    for claim_id in conflict_set.member_claim_ids
                    if claim_id in claim_assessments_by_claim
                ],
            }
        )
        resolution = ConflictResolution(
            conflict_set_id=conflict_set_id,
            policy_id=policy_id,
            algorithm_version=opts.resolution_algorithm_version,
            candidates=[
                ConflictResolutionCandidate(
                    claim_id=row.claim_id,
                    score_total=str(_quantize(row.score_total)),
                    score_breakdown={
                        key: str(_quantize(value))
                        for key, value in sorted(row.score_breakdown.items())
                    },
                )
                for row in ranked
            ],
            winner_claim_id=winner,
            inputs=ConflictResolutionInputs(
                claim_ids=sorted(conflict_set.member_claim_ids),
                doc_version_ids=member_doc_versions,
                trust_assessment_ids=trust_ids_input,
            ),
            notes=[
                f"policy_version={policy.policy_version}",
                "tie_break_rule=lexicographic_claim_id",
            ],
        )
        resolution_artifact_id = _persist_conflict_resolution(cas, resolution)
        resolution_artifact_ids.append(resolution_artifact_id)

        resolution_view = ConflictSetResolution(
            winner_claim_id=winner,
            policy_id=policy_id,
            confidence=winner_score,
            rationale=f"winner={winner};score={winner_score};tie_break=lexicographic_claim_id",
            resolution_artifact_id=resolution_artifact_id,
        )
        envelope = envelope_from_conflict_resolution(
            resolution=resolution_view,
            candidates=resolution.candidates,
        )
        envelope_artifact_id: str | None = None
        if envelope is not None:
            envelope_ref = persist_uncertainty_envelope(cas, envelope)
            envelope_artifact_id = str(envelope_ref.artifact_id)
            uncertainty_envelope_artifact_ids.append(envelope_artifact_id)

        updated_props = dict(conflict_set.props)
        if envelope_artifact_id is not None:
            updated_props["uncertainty_envelope_artifact_id"] = envelope_artifact_id

        updated_conflict = ConflictSet(
            conflict_set_id=conflict_set.conflict_set_id,
            conflict_key=conflict_set.conflict_key,
            conflict_kind=conflict_set.conflict_kind,
            member_claim_ids=conflict_set.member_claim_ids,
            resolution=resolution_view,
            props=updated_props,
        )
        updated_ref = persist_conflict_set(cas, updated_conflict)
        updated_artifact_id = str(updated_ref.artifact_id)
        updated_conflict_artifacts[conflict_set_id] = updated_artifact_id

        facts.extend(
            emit_world_node_facts(
                node_id=conflict_set_id,
                kind=NodeKind.CONFLICT_SET,
                label=updated_conflict.conflict_kind.value,
                artifact_id=updated_artifact_id,
                props_ref=None,
                provenance=stable_prov,
            )
        )
        facts.append(
            emit_edge_fact(
                src_id=conflict_set_id,
                edge_kind=EdgeKind.CONFLICT_RESOLVES_TO,
                dst_id=winner,
                provenance=stable_prov,
            )
        )
        if opts.emit_contradicts_to_winner:
            for row in ranked[1:]:
                contradict_edges += 1
                facts.append(
                    emit_edge_fact(
                        src_id=row.claim_id,
                        edge_kind=EdgeKind.CLAIM_CONTRADICTS,
                        dst_id=winner,
                        provenance=stable_prov,
                    )
                )

        cset_assessment = _build_cset_assessment(
            policy_id=policy_id,
            algorithm_version=opts.trust_algorithm_version,
            conflict_set_id=conflict_set_id,
            winner_claim_id=winner,
            members_count=len(conflict_set.member_claim_ids),
            score=winner_score,
            conflict_kind=conflict_set.conflict_kind.value,
        )
        trust_ref = persist_trust_assessment(cas, cset_assessment)
        trust_artifact_id = str(trust_ref.artifact_id)
        trust_artifact_by_id[cset_assessment.trust_assessment_id] = trust_artifact_id
        all_trust_assessments[cset_assessment.trust_assessment_id] = cset_assessment
        facts.extend(
            emit_world_node_facts(
                node_id=cset_assessment.trust_assessment_id,
                kind=NodeKind.TRUST_ASSESSMENT,
                label=cset_assessment.tier.value,
                artifact_id=trust_artifact_id,
                props_ref=None,
                provenance=stable_prov,
            )
        )
        facts.append(
            emit_edge_fact(
                src_id=cset_assessment.trust_assessment_id,
                edge_kind=EdgeKind.REPORT_ABOUT,
                dst_id=cset_assessment.target_world_id,
                provenance=stable_prov,
            )
        )

    inputs: list[WorldObjectRef] = [
        WorldObjectRef(world_id=claim_id) for claim_id in member_claim_ids
    ]
    for conflict_set_id in ordered_conflict_set_ids:
        inputs.append(WorldObjectRef(world_id=conflict_set_id))
    for artifact_id in sorted(set(claim_set_artifact_ids or [])):
        ArtifactID.model_validate(artifact_id)
        inputs.append(WorldObjectRef(artifact_id=artifact_id))

    outputs: list[WorldObjectRef] = []
    for conflict_set_id in ordered_conflict_set_ids:
        outputs.append(WorldObjectRef(world_id=conflict_set_id))
        artifact_id = updated_conflict_artifacts.get(
            conflict_set_id, conflict_artifacts_by_id.get(conflict_set_id)
        )
        if artifact_id is not None:
            outputs.append(WorldObjectRef(artifact_id=artifact_id))
    for artifact_id in sorted(set(resolution_artifact_ids)):
        outputs.append(WorldObjectRef(artifact_id=artifact_id))
    for artifact_id in sorted(set(uncertainty_envelope_artifact_ids)):
        outputs.append(WorldObjectRef(artifact_id=artifact_id))
    for trust_id in sorted(trust_artifact_by_id):
        outputs.append(WorldObjectRef(world_id=trust_id))
        outputs.append(WorldObjectRef(artifact_id=trust_artifact_by_id[trust_id]))

    event = build_claims_world_event(
        event_kind=EventKind.RESOLVE_CONFLICTS,
        activity_type=ProvActivityType.RESOLVE_CONFLICTS,
        activity_id=opts.activity_id,
        activity_label="Resolve claim conflicts",
        agent_id=opts.agent_id,
        inputs=inputs,
        outputs=outputs,
        props={"policy_id": policy_id, "policy_version": policy.policy_version},
    )
    event_id = event.event_id

    issues: list[QualityIssue] = []
    if missing_doc_versions:
        issues.append(
            QualityIssue(
                code="missing_doc_meta",
                severity=QualityIssueSeverity.WARN,
                msg="Some cited doc_version_id values are missing doc meta projection",
                context_json={"doc_version_ids": missing_doc_versions},
            )
        )
    if not claim_set_artifact_ids and resolved_db is None:
        issues.append(
            QualityIssue(
                code="subject_resolution_limited",
                severity=QualityIssueSeverity.INFO,
                msg=(
                    "MVP limitation: subject resolution across documents is not enabled in v1"
                ),
                context_json={"phase": "14", "mvp": True},
            )
        )
    issues = sorted(
        issues,
        key=lambda issue: (
            issue.severity.value,
            issue.code,
            issue.msg,
            to_canonical_bytes(issue.context_json).decode("utf-8"),
        ),
    )
    quality_payload = {
        "scope": QualityScope.CONFLICT_RESOLUTION.value,
        "run_event_id": event_id,
        "policy_id": policy_id,
        "algorithm_version": opts.resolution_algorithm_version,
        "metrics": {
            "conflict_sets_seen": len(ordered_conflict_set_ids),
            "conflict_sets_resolved": len(winner_by_conflict),
            "trust_assessments_emitted": len(trust_artifact_by_id),
            "resolution_artifacts_emitted": len(resolution_artifact_ids),
            "uncertainty_envelopes_emitted": len(uncertainty_envelope_artifact_ids),
            "contradict_edges_emitted": contradict_edges,
            "missing_doc_versions": len(missing_doc_versions),
        },
        "issues": [issue.model_dump(mode="python") for issue in issues],
        "props": {"policy_version": policy.policy_version},
    }
    quality_report = QualityReport(
        quality_report_id=quality_report_id_from_payload(payload=quality_payload),
        scope=QualityScope.CONFLICT_RESOLUTION,
        run_event_id=event_id,
        policy_id=policy_id,
        algorithm_version=opts.resolution_algorithm_version,
        metrics=quality_payload["metrics"],
        issues=issues,
        props=quality_payload["props"],
    )
    quality_ref = persist_quality_report(cas, quality_report)
    quality_artifact_id = str(quality_ref.artifact_id)
    facts.extend(
        emit_world_node_facts(
            node_id=quality_report.quality_report_id,
            kind=NodeKind.QUALITY_REPORT,
            label=quality_report.scope.value,
            artifact_id=quality_artifact_id,
            props_ref=None,
            provenance=stable_prov,
        )
    )
    facts.append(
        emit_edge_fact(
            src_id=quality_report.quality_report_id,
            edge_kind=EdgeKind.REPORT_ABOUT,
            dst_id=event_id,
            provenance=stable_prov,
        )
    )

    event_artifact_id = persist_claims_world_event(cas=cas, event=event, facts=facts)

    manifest = write_claims_world_segment(
        facts=facts,
        fact_log_root=fact_log_root,
        segment_name=segment_name or "claims_resolve_conflicts",
    )

    return ConflictResolveResult(
        conflict_set_ids=ordered_conflict_set_ids,
        winner_by_conflict_set=winner_by_conflict,
        conflict_set_artifact_ids=[
            updated_conflict_artifacts.get(
                conflict_set_id, conflict_artifacts_by_id[conflict_set_id]
            )
            for conflict_set_id in ordered_conflict_set_ids
        ],
        conflict_resolution_artifact_ids=sorted(set(resolution_artifact_ids)),
        uncertainty_envelope_artifact_ids=sorted(set(uncertainty_envelope_artifact_ids)),
        trust_assessment_ids=sorted(trust_artifact_by_id),
        trust_assessment_artifact_ids_by_id={
            trust_id: trust_artifact_by_id[trust_id] for trust_id in sorted(trust_artifact_by_id)
        },
        quality_report_id=quality_report.quality_report_id,
        quality_report_artifact_id=quality_artifact_id,
        world_event_id=event_id,
        world_event_artifact_id=event_artifact_id,
        world_segment_manifest=manifest,
    )


def _resolve_simulation_db(
    *,
    storage: StoragePort | None,
    db: SimulationDB | None,
) -> SimulationDB | None:
    if db is not None:
        return db
    if storage is None:
        return None
    if isinstance(storage, DuckDBStorageAdapter):
        return storage.raw_db
    raw_db = getattr(storage, "raw_db", None)
    if isinstance(raw_db, SimulationDB):
        return raw_db
    return None


__all__ = [
    "rank_conflict_candidates",
    "resolve_conflicts",
]
