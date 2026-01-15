from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Iterable

import pandas as pd

from polisyos.common.logger import get_logger
from polisyos.fabric.io.db import SimulationDB
from polisyos.ir.fact_log import FactSegmentManifest

logger = get_logger(__name__)

META_TABLE = "_meta_segments"
MACRO_PREFIX = "macro."
AGENT_PREFIX = "agent."
ENTITY_PREFIX = "entity_resolution."

DEFAULT_AGENT_RUN_ID = "demo_run"
DEFAULT_AGENT_STEP = 0

AUTO_COLUMNS = {"timestamp", "created_at", "applied_at"}
VALID_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

TABLE_TYPE_HINTS = {
    "macro_history": {
        "run_id": "VARCHAR",
        "step": "INTEGER",
        "timestamp": "TIMESTAMP",
    },
    "agents_snapshot": {
        "run_id": "VARCHAR",
        "step": "INTEGER",
        "agent_id": "VARCHAR",
        "age": "INTEGER",
        "is_employed": "BOOLEAN",
    },
}


def load_fact_manifests(fact_dir: Path) -> list[FactSegmentManifest]:
    index_path = fact_dir / "_segments.jsonl"
    if not index_path.exists():
        return []
    manifests: list[FactSegmentManifest] = []
    with index_path.open("r", encoding="utf-8") as f:
        for line in f:
            raw = line.strip()
            if not raw:
                continue
            try:
                manifests.append(FactSegmentManifest.model_validate_json(raw))
            except Exception as exc:
                logger.warning("Skipping invalid fact manifest: %s", exc)
    return manifests


def ensure_materialized(
    db: SimulationDB, fact_manifests: Iterable[FactSegmentManifest]
) -> None:
    manifests = list(fact_manifests)
    if not manifests:
        return
    _ensure_meta_table(db)
    applied = _load_applied_segments(db)
    for manifest in manifests:
        existing = applied.get(manifest.segment_id)
        if existing:
            if existing != manifest.sha256:
                raise ValueError(
                    f"Segment hash mismatch for {manifest.segment_id}: {existing} != {manifest.sha256}"
                )
            continue
        _apply_segment(db, manifest)
        _record_applied_segment(db, manifest)


def materialize_duckdb_from_fact_log(fact_dir: Path, db: SimulationDB) -> None:
    manifests = load_fact_manifests(fact_dir)
    ensure_materialized(db, manifests)


def _ensure_meta_table(db: SimulationDB) -> None:
    db.conn.execute(
        """
        CREATE TABLE IF NOT EXISTS _meta_segments (
            segment_id VARCHAR PRIMARY KEY,
            sha256 VARCHAR,
            row_count INTEGER,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """
    )


def _load_applied_segments(db: SimulationDB) -> dict[str, str]:
    rows = db.conn.execute(f"SELECT segment_id, sha256 FROM {META_TABLE}").fetchall()
    return {row[0]: row[1] for row in rows}


def _record_applied_segment(db: SimulationDB, manifest: FactSegmentManifest) -> None:
    db.conn.execute(
        f"""
        INSERT INTO {META_TABLE} (segment_id, sha256, row_count)
        VALUES (?, ?, ?)
    """,
        [manifest.segment_id, manifest.sha256, manifest.row_count],
    )


def _apply_segment(db: SimulationDB, manifest: FactSegmentManifest) -> None:
    segment_path = Path(manifest.path)
    if not segment_path.exists():
        raise FileNotFoundError(f"Missing fact segment: {segment_path}")
    _verify_segment_hash(segment_path, manifest.sha256)
    df = pd.read_parquet(segment_path)
    if df.empty:
        return
    _apply_macro_facts(db, df)
    _apply_agent_facts(db, df)
    _apply_entity_resolution_facts(db, df)


def _verify_segment_hash(path: Path, expected_sha256: str) -> None:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != expected_sha256:
        raise ValueError(f"Segment hash mismatch for {path}: {digest} != {expected_sha256}")


def _apply_macro_facts(db: SimulationDB, facts: pd.DataFrame) -> None:
    macro = _select_prefix(facts, MACRO_PREFIX)
    if macro.empty:
        return
    macro = macro[["subject_id", "valid_time", "predicate_id", "object_value"]].copy()
    macro = macro[macro["valid_time"].notna()]
    if macro.empty:
        return
    macro["metric"] = macro["predicate_id"].str[len(MACRO_PREFIX) :]
    pivot = (
        macro.pivot_table(
            index=["subject_id", "valid_time"],
            columns="metric",
            values="object_value",
            aggfunc="first",
        )
        .reset_index()
        .rename(columns={"subject_id": "run_id", "valid_time": "step"})
    )
    metrics = [col for col in pivot.columns if col not in {"run_id", "step"}]
    _ensure_columns(pivot, metrics)
    for col in metrics:
        pivot[col] = pd.to_numeric(pivot[col], errors="coerce")
    pivot["step"] = pd.to_numeric(pivot["step"], errors="coerce").astype("Int64")
    _ensure_columns_from_udf_schema(db, "macro_history")
    _ensure_table_columns(db, "macro_history", pivot)
    table_cols = _table_columns(db, "macro_history")
    insert_cols = [col for col in ["run_id", "step", *metrics] if col in table_cols]
    _ensure_columns(pivot, insert_cols)
    pivot = pivot[insert_cols]
    if pivot.empty:
        return
    cols_sql = ", ".join(insert_cols)
    db.conn.execute(
        f"""
        INSERT INTO macro_history ({cols_sql})
        SELECT {cols_sql}
        FROM pivot
    """
    )


def _apply_agent_facts(db: SimulationDB, facts: pd.DataFrame) -> None:
    agents = _select_prefix(facts, AGENT_PREFIX)
    if agents.empty:
        return
    agents = agents[["subject_id", "predicate_id", "object_value"]].copy()
    agents["metric"] = agents["predicate_id"].str[len(AGENT_PREFIX) :]
    pivot = (
        agents.pivot_table(
            index=["subject_id"], columns="metric", values="object_value", aggfunc="first"
        )
        .reset_index()
        .rename(columns={"subject_id": "agent_id", "employment": "is_employed"})
    )
    _ensure_columns(pivot, ["age", "income", "savings", "is_employed"])
    pivot["age"] = pd.to_numeric(pivot["age"], errors="coerce").astype("Int64")
    pivot["income"] = pd.to_numeric(pivot["income"], errors="coerce")
    pivot["savings"] = pd.to_numeric(pivot["savings"], errors="coerce")
    pivot["is_employed"] = pivot["is_employed"].map(_coerce_bool)
    pivot["run_id"] = DEFAULT_AGENT_RUN_ID
    pivot["step"] = DEFAULT_AGENT_STEP
    _ensure_columns_from_udf_schema(db, "agents_snapshot")
    _ensure_table_columns(db, "agents_snapshot", pivot)
    table_cols = _table_columns(db, "agents_snapshot")
    base_cols = ["run_id", "step", "agent_id"]
    metric_cols = [col for col in pivot.columns if col not in base_cols]
    insert_cols = [col for col in [*base_cols, *metric_cols] if col in table_cols]
    _ensure_columns(pivot, insert_cols)
    pivot = pivot[insert_cols]
    if pivot.empty:
        return
    cols_sql = ", ".join(insert_cols)
    db.conn.execute(
        f"""
        INSERT INTO agents_snapshot ({cols_sql})
        SELECT {cols_sql}
        FROM pivot
    """
    )


def _apply_entity_resolution_facts(db: SimulationDB, facts: pd.DataFrame) -> None:
    entities = _select_prefix(facts, ENTITY_PREFIX)
    if entities.empty:
        return
    entities = entities[["subject_id", "predicate_id", "object_value"]].copy()
    entities["metric"] = entities["predicate_id"].str[len(ENTITY_PREFIX) :]
    pivot = (
        entities.pivot_table(
            index=["subject_id"], columns="metric", values="object_value", aggfunc="first"
        )
        .reset_index()
        .rename(columns={"subject_id": "raw_id"})
    )
    _ensure_columns(pivot, ["canonical_id", "match_confidence", "match_method"])
    pivot["match_confidence"] = pd.to_numeric(pivot["match_confidence"], errors="coerce")
    pivot = pivot[["raw_id", "canonical_id", "match_confidence", "match_method"]]
    if pivot.empty:
        return
    db.conn.execute(
        """
        INSERT INTO entity_resolution (
            raw_id, canonical_id, match_confidence, match_method
        )
        SELECT raw_id, canonical_id, match_confidence, match_method
        FROM pivot
    """
    )


def _select_prefix(df: pd.DataFrame, prefix: str) -> pd.DataFrame:
    if "predicate_id" not in df.columns:
        return pd.DataFrame()
    predicates = df["predicate_id"].astype(str)
    return df[predicates.str.startswith(prefix)].copy()


def _ensure_columns(df: pd.DataFrame, columns: list[str]) -> None:
    for col in columns:
        if col not in df.columns:
            df[col] = None


def _table_columns(db: SimulationDB, table: str) -> list[str]:
    rows = db.conn.execute(f"PRAGMA table_info('{table}')").fetchall()
    return [row[1] for row in rows]


def _duckdb_type_for_series(series: pd.Series) -> str:
    if pd.api.types.is_bool_dtype(series.dtype):
        return "BOOLEAN"
    if pd.api.types.is_integer_dtype(series.dtype):
        return "INTEGER"
    if pd.api.types.is_float_dtype(series.dtype):
        return "DOUBLE"
    if pd.api.types.is_datetime64_any_dtype(series.dtype):
        return "TIMESTAMP"
    return "VARCHAR"


def _ensure_table_columns(db: SimulationDB, table: str, df: pd.DataFrame) -> None:
    existing = set(_table_columns(db, table))
    for col in df.columns:
        if col in existing or col in AUTO_COLUMNS:
            continue
        if not VALID_IDENTIFIER.match(col):
            logger.warning("Skipping unsafe column name in materializer: %s", col)
            continue
        dtype = _duckdb_type_for_series(df[col])
        db.conn.execute(f'ALTER TABLE {table} ADD COLUMN "{col}" {dtype}')
        existing.add(col)


def _default_type_for_column(table: str, column: str) -> str:
    table_hints = TABLE_TYPE_HINTS.get(table, {})
    if column in table_hints:
        return table_hints[column]
    if table == "macro_history":
        return "DOUBLE"
    if table == "agents_snapshot":
        return "DOUBLE"
    return "VARCHAR"


def _ensure_columns_from_udf_schema(db: SimulationDB, table: str) -> None:
    try:
        from polisyos.fabric.udf.config import load_udf_schema
    except Exception as exc:
        logger.warning("Skipping UDF schema precreate: %s", exc)
        return
    schema = load_udf_schema()
    allowed = schema.allowed_columns.get(table, set())
    if not allowed:
        return
    existing = set(_table_columns(db, table))
    for col in sorted(allowed):
        if col in existing or col in AUTO_COLUMNS:
            continue
        if not VALID_IDENTIFIER.match(col):
            logger.warning("Skipping unsafe UDF schema column: %s", col)
            continue
        dtype = _default_type_for_column(table, col)
        db.conn.execute(f'ALTER TABLE {table} ADD COLUMN "{col}" {dtype}')
        existing.add(col)


def _coerce_bool(value: object) -> bool | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"true", "t", "1", "yes"}:
        return True
    if text in {"false", "f", "0", "no"}:
        return False
    return None
