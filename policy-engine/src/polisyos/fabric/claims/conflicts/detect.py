"""Detect claim groups that conflict and emit the corresponding world artifacts and facts."""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Iterable

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.fabric.claims.errors import ClaimValidationError
from polisyos.fabric.claims.persist import (
    claim_artifact_ids_by_claim_id,
    load_claim,
    write_claims_world_segment,
)
from polisyos.fabric.io.db import SimulationDB
from polisyos.fabric.storage import DuckDBStorageAdapter, StoragePort
from polisyos.fabric.world import (
    emit_edge_fact,
    emit_world_node_facts,
    persist_conflict_set,
    stable_world_provenance_v1,
)
from polisyos.ir.world.abi import EdgeKind, NodeKind
from polisyos.ir.world.claim import Claim
from polisyos.ir.world.conflict import ConflictKind, ConflictSet
from polisyos.ir.world.event import (
    EventKind,
    ProvActivityType,
    WorldObjectRef,
)
from polisyos.ir.world.ids import conflict_set_id_from_key

from ..world_events import build_claims_world_event, persist_claims_world_event
from .key import compare_v1, conflict_key_v1
from .types import ConflictDetectOptions, ConflictDetectResult


def _query_claim_artifacts_from_db(db: SimulationDB, claim_ids: Iterable[str]) -> dict[str, str]:
    values = sorted(set(claim_ids))
    if not values:
        return {}
    placeholders = ", ".join(["?"] * len(values))
    rows = db.conn.execute(
        f"""
        SELECT claim_id, meta_artifact_id
        FROM world.claims
        WHERE claim_id IN ({placeholders})
          AND meta_artifact_id IS NOT NULL
        """,
        values,
    ).fetchall()
    return {str(claim_id): str(artifact_id) for claim_id, artifact_id in rows}


def _load_claim_refs_from_claim_sets(
    *,
    cas: FileSystemCAS,
    claim_set_artifact_ids: Iterable[str],
) -> dict[str, str]:
    return claim_artifact_ids_by_claim_id(
        cas=cas,
        claim_set_artifact_ids=list(claim_set_artifact_ids),
    )


def _all_claim_artifacts_from_db(db: SimulationDB) -> dict[str, str]:
    rows = db.conn.execute(
        """
        SELECT claim_id, meta_artifact_id
        FROM world.claims
        WHERE meta_artifact_id IS NOT NULL
        """
    ).fetchall()
    return {str(claim_id): str(artifact_id) for claim_id, artifact_id in rows}


def _load_claims(
    *,
    cas: FileSystemCAS,
    claim_ids: Iterable[str],
    claim_artifact_ids_by_id: dict[str, str],
) -> dict[str, Claim]:
    claims: dict[str, Claim] = {}
    for claim_id in sorted(set(claim_ids)):
        artifact_id = claim_artifact_ids_by_id.get(claim_id)
        if artifact_id is None:
            raise ClaimValidationError(f"missing claim_artifact_id for claim_id={claim_id}")
        claim = load_claim(cas, artifact_id)
        if claim.claim_id != claim_id:
            raise ClaimValidationError(
                f"claim artifact mismatch: expected {claim_id}, got {claim.claim_id}"
            )
        claims[claim_id] = claim
    return claims


def _conflict_kind_for_group(claims: list[Claim], *, tolerance: Decimal) -> ConflictKind:
    seen: set[ConflictKind] = set()
    for i, left in enumerate(claims):
        for right in claims[i + 1 :]:
            seen.add(compare_v1(left, right, tolerance=tolerance))
    for kind in (
        ConflictKind.TEMPORAL_MISMATCH,
        ConflictKind.UNIT_MISMATCH,
        ConflictKind.DEFINITION_MISMATCH,
        ConflictKind.VALUE_MISMATCH,
    ):
        if kind in seen:
            return kind
    return ConflictKind.DUPLICATE


def detect_conflicts(
    *,
    cas: FileSystemCAS,
    fact_log_root: Path,
    storage: StoragePort | None = None,
    db: SimulationDB | None = None,
    claim_ids: list[str] | None = None,
    claim_set_artifact_ids: list[str] | None = None,
    policy_id: str,
    options: ConflictDetectOptions | None = None,
    segment_name: str | None = None,
) -> ConflictDetectResult:
    """Group comparable claims into conflict sets, persist them, and write world-event outputs."""
    del policy_id  # conflict detection is policy-agnostic in v1
    resolved_db = _resolve_simulation_db(storage=storage, db=db)
    opts = options or ConflictDetectOptions()
    refs_by_claim: dict[str, str] = {}

    if claim_set_artifact_ids:
        refs_by_claim.update(
            claim_artifact_ids_by_claim_id(cas=cas, claim_set_artifact_ids=claim_set_artifact_ids)
        )

    selected_claim_ids: list[str]
    if claim_ids is not None:
        selected_claim_ids = sorted(set(claim_ids))
        if resolved_db is not None:
            refs_by_claim.update(_query_claim_artifacts_from_db(resolved_db, selected_claim_ids))
        if resolved_db is None and not claim_set_artifact_ids:
            raise ClaimValidationError(
                "claim_ids require db or claim_set_artifact_ids to resolve claim artifacts"
            )
    else:
        if refs_by_claim:
            selected_claim_ids = sorted(refs_by_claim)
        elif resolved_db is not None:
            refs_by_claim.update(_all_claim_artifacts_from_db(resolved_db))
            selected_claim_ids = sorted(refs_by_claim)
        else:
            raise ClaimValidationError(
                "detect_conflicts requires claim_ids, claim_set_artifact_ids, or db"
            )

    claims_by_id = _load_claims(
        cas=cas,
        claim_ids=selected_claim_ids,
        claim_artifact_ids_by_id=refs_by_claim,
    )

    groups: dict[str, list[Claim]] = {}
    for claim in claims_by_id.values():
        key = conflict_key_v1(claim)
        groups.setdefault(key, []).append(claim)

    stable_prov = stable_world_provenance_v1()
    facts = []
    conflict_set_ids: list[str] = []
    conflict_artifacts: list[str] = []
    outputs: list[WorldObjectRef] = []

    for conflict_key in sorted(groups):
        group_claims = groups[conflict_key]
        if len(group_claims) < 2:
            continue
        member_ids = sorted({claim.claim_id for claim in group_claims})
        conflict_set = ConflictSet(
            conflict_set_id=conflict_set_id_from_key(conflict_key=conflict_key),
            conflict_key=conflict_key,
            conflict_kind=_conflict_kind_for_group(group_claims, tolerance=opts.tolerance),
            member_claim_ids=member_ids,
            resolution=None,
            props={
                "key_algorithm": opts.key_algorithm_version,
                "compare_algorithm": opts.compare_algorithm_version,
            },
        )
        conflict_ref = persist_conflict_set(cas, conflict_set)
        conflict_artifact_id = str(conflict_ref.artifact_id)
        conflict_set_ids.append(conflict_set.conflict_set_id)
        conflict_artifacts.append(conflict_artifact_id)

        facts.extend(
            emit_world_node_facts(
                node_id=conflict_set.conflict_set_id,
                kind=NodeKind.CONFLICT_SET,
                label=conflict_set.conflict_kind.value,
                artifact_id=conflict_artifact_id,
                props_ref=None,
                provenance=stable_prov,
            )
        )
        for claim_id in member_ids:
            facts.append(
                emit_edge_fact(
                    src_id=claim_id,
                    edge_kind=EdgeKind.CLAIM_IN_CONFLICT_SET,
                    dst_id=conflict_set.conflict_set_id,
                    provenance=stable_prov,
                )
            )
        outputs.append(WorldObjectRef(world_id=conflict_set.conflict_set_id))
        outputs.append(WorldObjectRef(artifact_id=conflict_artifact_id))

    inputs: list[WorldObjectRef] = [
        WorldObjectRef(world_id=claim_id) for claim_id in selected_claim_ids
    ]
    for artifact_id in sorted(set(claim_set_artifact_ids or [])):
        ArtifactID.model_validate(artifact_id)
        inputs.append(WorldObjectRef(artifact_id=artifact_id))

    event = build_claims_world_event(
        event_kind=EventKind.DETECT_CONFLICTS,
        activity_type=ProvActivityType.DETECT_CONFLICTS,
        activity_id=opts.activity_id,
        activity_label="Detect claim conflicts",
        agent_id=opts.agent_id,
        inputs=inputs,
        outputs=outputs,
    )
    event_id = event.event_id
    event_artifact_id = persist_claims_world_event(cas=cas, event=event, facts=facts)

    manifest = write_claims_world_segment(
        facts=facts,
        fact_log_root=fact_log_root,
        segment_name=segment_name or "claims_detect_conflicts",
    )

    return ConflictDetectResult(
        conflict_set_ids=sorted(conflict_set_ids),
        conflict_set_artifact_ids=sorted(set(conflict_artifacts)),
        claim_ids=selected_claim_ids,
        claim_artifact_ids_by_id={
            claim_id: refs_by_claim[claim_id] for claim_id in selected_claim_ids
        },
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
    "detect_conflicts",
]
