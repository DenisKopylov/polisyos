"""Fabric-owned transactional write waist for retained world snapshots."""

from __future__ import annotations

import importlib.util as _importlib_util
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.fabric.world.store.errors import WorldValidationError

if TYPE_CHECKING:
    from polisyos.fabric.world.store.snapshots import WorldSnapshotRecord


class _WorldSnapshotWriteModel(BaseModel):
    """Strict immutable base for world snapshot write contracts."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        revalidate_instances="always",
    )


class WorldSnapshotNodeWrite(_WorldSnapshotWriteModel):
    """One canonical world node to replace within a snapshot write."""

    node_id: str = Field(..., min_length=1)
    kind: str = Field(..., min_length=1)
    label: str | None
    artifact_id: str | None
    props_ref: str | None


class WorldSnapshotFactWrite(_WorldSnapshotWriteModel):
    """One canonical world fact to replace within a snapshot write."""

    fact_id: str = Field(..., min_length=1)
    schema_version: str = Field(..., min_length=1)
    subject_id: str = Field(..., min_length=1)
    predicate_id: str = Field(..., min_length=1)
    object_value: str | None
    target_id: str | None
    valid_time: str | None
    tx_time: str = Field(..., min_length=1)
    provenance_json: dict[str, Any]
    trust_json: dict[str, Any] | None
    legal_json: dict[str, Any] | None
    segment_id: str | None


class WorldSnapshotWriteRequest(_WorldSnapshotWriteModel):
    """Complete, identity-bound request for one retained world snapshot."""

    snapshot_root: Path
    snapshot_id: str = Field(..., min_length=1)
    branch_name: str = Field(..., min_length=1)
    as_of_valid_time: str = Field(..., min_length=1)
    as_of_tx_time: str = Field(..., min_length=1)
    provenance: dict[str, Any]
    nodes: tuple[WorldSnapshotNodeWrite, ...] = Field(..., min_length=1)
    facts: tuple[WorldSnapshotFactWrite, ...] = Field(..., min_length=1)

    @model_validator(mode="after")
    def _validate_identity_graph(self) -> WorldSnapshotWriteRequest:
        node_ids = tuple(node.node_id for node in self.nodes)
        fact_ids = tuple(fact.fact_id for fact in self.facts)
        if len(set(node_ids)) != len(node_ids):
            raise ValueError("world_snapshot_node_ids_not_unique")
        if len(set(fact_ids)) != len(fact_ids):
            raise ValueError("world_snapshot_fact_ids_not_unique")

        declared_nodes = set(node_ids)
        unresolved_subjects = {
            fact.subject_id for fact in self.facts if fact.subject_id not in declared_nodes
        }
        unresolved_targets = {
            fact.target_id
            for fact in self.facts
            if fact.target_id is not None and fact.target_id not in declared_nodes
        }
        if unresolved_subjects or unresolved_targets:
            raise ValueError(
                "world_snapshot_fact_node_unresolved: "
                f"subjects={sorted(unresolved_subjects)!r}, targets={sorted(unresolved_targets)!r}"
            )

        referenced_nodes = {
            reference
            for fact in self.facts
            for reference in (fact.subject_id, fact.target_id)
            if reference is not None
        }
        nodes_without_facts = declared_nodes - referenced_nodes
        if nodes_without_facts:
            raise ValueError(
                f"world_snapshot_nodes_without_facts: {sorted(nodes_without_facts)!r}"
            )
        return self


class WorldSnapshotBackendUnavailable(RuntimeError):
    """Raised when the exact DuckDB backend required by the write waist is absent."""


def _json_value(value: dict[str, Any] | None) -> str | None:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def write_world_snapshot(
    db_path: Path,
    request: WorldSnapshotWriteRequest,
) -> WorldSnapshotRecord:
    """Replace named world rows transactionally, then retain the proven snapshot.

    Args:
        db_path: File-backed DuckDB database owned by the caller's workspace.
        request: Strict node, fact, temporal, and provenance snapshot request.

    Returns:
        The retained Fabric world snapshot record.

    Raises:
        WorldSnapshotBackendUnavailable: The exact DuckDB backend is not installed.
        WorldValidationError: Written rows or referential postconditions do not match.
        ValidationError: The supplied request was constructed without satisfying its contract.
    """

    validated = WorldSnapshotWriteRequest.model_validate(request.model_dump(mode="python"))
    provenance = _json_value(validated.provenance)
    node_rows = tuple(
        (node.node_id, node.kind, node.label, node.artifact_id, node.props_ref)
        for node in validated.nodes
    )
    fact_rows = tuple(
        (
            fact.fact_id,
            fact.schema_version,
            fact.subject_id,
            fact.predicate_id,
            fact.object_value,
            fact.target_id,
            fact.valid_time,
            fact.tx_time,
            _json_value(fact.provenance_json),
            _json_value(fact.trust_json),
            _json_value(fact.legal_json),
            fact.segment_id,
        )
        for fact in validated.facts
    )

    if _importlib_util.find_spec("duckdb") is None:
        raise WorldSnapshotBackendUnavailable(
            "write_world_snapshot requires the optional 'duckdb' backend"
        )

    import duckdb as _duckdb_backend

    from polisyos.fabric.io.db import SimulationDB
    from polisyos.fabric.world.materialize import ensure_world_schema
    from polisyos.fabric.world.store.snapshots import create_world_snapshot

    del _duckdb_backend

    managed_fact_ids = tuple(fact.fact_id for fact in validated.facts)
    managed_node_ids = tuple(node.node_id for node in validated.nodes)

    with SimulationDB(db_path=str(db_path)) as db:
        ensure_world_schema(db)
        db.conn.execute("BEGIN")
        try:
            db.conn.execute(
                """
                DELETE FROM world.world_facts
                WHERE fact_id IN (SELECT unnest(?))
                """,
                [list(managed_fact_ids)],
            )
            db.conn.execute(
                """
                DELETE FROM world.world_nodes
                WHERE node_id IN (SELECT unnest(?))
                """,
                [list(managed_node_ids)],
            )
            db.conn.executemany(
                """
                INSERT INTO world.world_nodes (
                    node_id, kind, label, artifact_id, props_ref
                ) VALUES (?, ?, ?, ?, ?)
                """,
                node_rows,
            )
            db.conn.executemany(
                """
                INSERT INTO world.world_facts (
                    fact_id,
                    schema_version,
                    subject_id,
                    predicate_id,
                    object_value,
                    target_id,
                    valid_time,
                    tx_time,
                    provenance_json,
                    trust_json,
                    legal_json,
                    segment_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                fact_rows,
            )

            fetched_nodes = db.conn.execute(
                """
                SELECT node_id, kind, label, artifact_id, props_ref
                FROM world.world_nodes
                WHERE node_id IN (SELECT unnest(?))
                ORDER BY node_id
                """,
                [list(managed_node_ids)],
            ).fetchall()
            if fetched_nodes != sorted(node_rows):
                raise WorldValidationError("world_snapshot_node_write_mismatch")

            fetched_facts = db.conn.execute(
                """
                SELECT
                    fact_id,
                    schema_version,
                    subject_id,
                    predicate_id,
                    object_value,
                    target_id,
                    valid_time,
                    tx_time,
                    provenance_json,
                    trust_json,
                    legal_json,
                    segment_id
                FROM world.world_facts
                WHERE fact_id IN (SELECT unnest(?))
                ORDER BY fact_id
                """,
                [list(managed_fact_ids)],
            ).fetchall()
            if fetched_facts != sorted(fact_rows):
                raise WorldValidationError("world_snapshot_fact_write_mismatch")

            orphan_facts = db.conn.execute(
                """
                SELECT f.fact_id AS orphan_fact_id
                FROM world.world_facts AS f
                LEFT JOIN world.world_nodes AS subject_node
                    ON subject_node.node_id = f.subject_id
                LEFT JOIN world.world_nodes AS target_node
                    ON target_node.node_id = f.target_id
                WHERE (
                      subject_node.node_id IS NULL
                      OR (f.target_id IS NOT NULL AND target_node.node_id IS NULL)
                  )
                ORDER BY f.fact_id
                """
            ).fetchall()
            if orphan_facts:
                raise WorldValidationError(
                    f"world_snapshot_orphan_facts: {[row[0] for row in orphan_facts]!r}"
                )

            orphan_nodes = db.conn.execute(
                """
                SELECT n.node_id AS orphan_node_id
                FROM world.world_nodes AS n
                LEFT JOIN world.world_facts AS f
                    ON f.subject_id = n.node_id OR f.target_id = n.node_id
                WHERE n.node_id IN (SELECT unnest(?))
                GROUP BY n.node_id
                HAVING count(f.fact_id) = 0
                ORDER BY n.node_id
                """,
                [list(managed_node_ids)],
            ).fetchall()
            if orphan_nodes:
                raise WorldValidationError(
                    f"world_snapshot_orphan_nodes: {[row[0] for row in orphan_nodes]!r}"
                )
            db.conn.execute("COMMIT")
        except BaseException:
            db.conn.execute("ROLLBACK")
            raise

        return create_world_snapshot(
            db,
            snapshot_root=validated.snapshot_root,
            snapshot_id=validated.snapshot_id,
            branch_name=validated.branch_name,
            as_of_valid_time=validated.as_of_valid_time,
            as_of_tx_time=validated.as_of_tx_time,
            provenance=json.loads(provenance or "{}"),
        )


__all__ = [
    "WorldSnapshotBackendUnavailable",
    "WorldSnapshotFactWrite",
    "WorldSnapshotNodeWrite",
    "WorldSnapshotWriteRequest",
    "write_world_snapshot",
]
