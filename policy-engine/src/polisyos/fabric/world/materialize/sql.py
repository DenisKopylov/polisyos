"""Public materialize sql module API."""
from __future__ import annotations

from polisyos.ir.world.predicates import (
    WORLD_ARTIFACT_ID,
    WORLD_KIND,
    WORLD_LABEL,
    WORLD_PROPS_REF,
)


def sql_load_applied_segments() -> str:
    """Sql load applied segments helper."""
    return "SELECT segment_id, segment_sha256 FROM world._meta_world_segments"


def sql_count_new_world_facts(staging_table: str) -> str:
    """Sql count new world facts helper."""
    return f"""
    SELECT COUNT(*)
    FROM {staging_table} s
    LEFT JOIN world.world_facts w
        ON w.fact_id = s.fact_id
    WHERE w.fact_id IS NULL
    """


def sql_insert_world_facts(staging_table: str) -> str:
    """Sql insert world facts helper."""
    return f"""
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
    )
    SELECT
        s.fact_id,
        s.schema_version,
        s.subject_id,
        s.predicate_id,
        s.object_value,
        s.target_id,
        s.valid_time,
        s.tx_time,
        s.provenance_json,
        s.trust_json,
        s.legal_json,
        s.segment_id
    FROM {staging_table} s
    LEFT JOIN world.world_facts w
        ON w.fact_id = s.fact_id
    WHERE w.fact_id IS NULL
    """


def sql_count_new_edges(staging_table: str) -> str:
    """Sql count new edges helper."""
    return f"""
    SELECT COUNT(*)
    FROM {staging_table} s
    LEFT JOIN world.world_edges w
        ON w.edge_id = s.edge_id
    WHERE w.edge_id IS NULL
    """


def sql_insert_world_edges(staging_table: str) -> str:
    """Sql insert world edges helper."""
    return f"""
    INSERT INTO world.world_edges (
        edge_id,
        src_id,
        predicate_id,
        kind,
        dst_id,
        valid_time,
        tx_time,
        provenance_json,
        trust_json,
        legal_json,
        segment_id
    )
    SELECT
        s.edge_id,
        s.src_id,
        s.predicate_id,
        s.kind,
        s.dst_id,
        s.valid_time,
        s.tx_time,
        s.provenance_json,
        s.trust_json,
        s.legal_json,
        s.segment_id
    FROM {staging_table} s
    LEFT JOIN world.world_edges w
        ON w.edge_id = s.edge_id
    WHERE w.edge_id IS NULL
    """


def sql_insert_missing_nodes(touched_table: str) -> str:
    """Sql insert missing nodes helper."""
    return f"""
    INSERT INTO world.world_nodes (node_id, kind)
    SELECT DISTINCT t.node_id, 'unknown'
    FROM {touched_table} t
    LEFT JOIN world.world_nodes n
        ON n.node_id = t.node_id
    WHERE n.node_id IS NULL
    """


def sql_kind_conflicts(touched_table: str) -> str:
    """Sql kind conflicts helper."""
    return f"""
    SELECT subject_id
    FROM world.world_facts
    WHERE predicate_id = '{WORLD_KIND}'
      AND subject_id IN (SELECT node_id FROM {touched_table})
    GROUP BY subject_id
    HAVING COUNT(DISTINCT object_value) > 1
    """


def _sql_ranked_value(predicate_id: str, alias: str, touched_table: str) -> str:
    return f"""
    {alias} AS (
        SELECT subject_id, object_value AS {alias}_value
        FROM (
            SELECT
                subject_id,
                object_value,
                ROW_NUMBER() OVER (
                    PARTITION BY subject_id
                    ORDER BY (object_value IS NULL), tx_time DESC
                ) AS rn
            FROM world.world_facts
            WHERE predicate_id = '{predicate_id}'
              AND subject_id IN (SELECT node_id FROM {touched_table})
        )
        WHERE rn = 1
    )
    """


def sql_update_world_nodes(touched_table: str) -> str:
    """Sql update world nodes helper."""
    label_cte = _sql_ranked_value(WORLD_LABEL, "label_choice", touched_table)
    artifact_cte = _sql_ranked_value(WORLD_ARTIFACT_ID, "artifact_choice", touched_table)
    props_cte = _sql_ranked_value(WORLD_PROPS_REF, "props_choice", touched_table)
    return f"""
    WITH
    touched AS (SELECT DISTINCT node_id FROM {touched_table}),
    kind_choice AS (
        SELECT subject_id, MAX(object_value) AS kind
        FROM world.world_facts
        WHERE predicate_id = '{WORLD_KIND}'
          AND subject_id IN (SELECT node_id FROM touched)
        GROUP BY subject_id
    ),
    {label_cte},
    {artifact_cte},
    {props_cte}
    UPDATE world.world_nodes AS n
    SET
        kind = COALESCE(
            (SELECT k.kind FROM kind_choice k WHERE k.subject_id = n.node_id),
            n.kind
        ),
        label = (
            SELECT l.label_choice_value
            FROM label_choice l
            WHERE l.subject_id = n.node_id
        ),
        artifact_id = (
            SELECT a.artifact_choice_value
            FROM artifact_choice a
            WHERE a.subject_id = n.node_id
        ),
        props_ref = (
            SELECT p.props_choice_value
            FROM props_choice p
            WHERE p.subject_id = n.node_id
        ),
        updated_at = CURRENT_TIMESTAMP
    WHERE n.node_id IN (SELECT node_id FROM touched)
    """


__all__ = [
    "sql_count_new_edges",
    "sql_count_new_world_facts",
    "sql_insert_missing_nodes",
    "sql_insert_world_edges",
    "sql_insert_world_facts",
    "sql_kind_conflicts",
    "sql_load_applied_segments",
    "sql_update_world_nodes",
]
