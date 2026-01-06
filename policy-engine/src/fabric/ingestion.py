import hashlib
import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, Tuple, Type

import pandas as pd
from pydantic import BaseModel, ValidationError

from src.fabric.config import (
    DEFAULT_RECONCILIATION_TOLERANCE,
    NORMALIZATION_RULES,
    RECONCILIATION_RULES,
)
from src.fabric.manifest import CoverageMetrics, DatasetManifest, QualityMetrics, ReconciliationReport
from src.fabric.schema import AgentRow, InteractionRow, MacroRow
from src.io.db import SimulationDB
from src.io.graph_store import GraphStore


def _file_hash(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _validate_rows(
    df: pd.DataFrame, model: Type[BaseModel]
) -> Tuple[pd.DataFrame, list[dict[str, Any]]]:
    valid_rows = []
    rejects = []
    for idx, row in df.iterrows():
        data = row.to_dict()
        try:
            valid = model(**data).model_dump()
            valid_rows.append(valid)
        except ValidationError as exc:
            rejects.append({"row_index": int(idx), "errors": exc.errors(), "raw": data})
    return pd.DataFrame(valid_rows), rejects


def _write_rejects(rejects: Iterable[dict[str, Any]], path: Path) -> None:
    if not rejects:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for item in rejects:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")


def _quality_metrics(df: pd.DataFrame, dedup_key: list[str]) -> QualityMetrics:
    missing_rate = float(df.isna().sum().sum() / max(len(df) * len(df.columns), 1))
    duplicate_rate = 0.0
    if dedup_key:
        duplicate_rate = float(df.duplicated(subset=dedup_key).mean())
    return QualityMetrics(
        missing_rate=missing_rate,
        duplicate_rate=duplicate_rate,
        outlier_rate=0.0,
        coverage=CoverageMetrics(),
    )


def _normalize_id(raw_id: str) -> str:
    value = raw_id.strip().lower()
    for rule in NORMALIZATION_RULES:
        value = re.sub(rule["pattern"], rule["repl"], value)
    value = value.strip("_")
    return value or "unknown"


def _build_entity_resolution(df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, str]]:
    mapping: Dict[str, str] = {}
    rows = []
    for raw_id in df["agent_id"].astype(str).tolist():
        canonical = _normalize_id(raw_id)
        mapping[raw_id] = canonical
        confidence = 1.0 if raw_id == canonical else 0.9
        rows.append(
            {
                "raw_id": raw_id,
                "canonical_id": canonical,
                "match_confidence": confidence,
                "match_method": "exact" if confidence == 1.0 else "ruleset_v1",
            }
        )
    return pd.DataFrame(rows), mapping


def _reconcile_interactions(
    df: pd.DataFrame, tolerance: float, rules: Dict[str, Dict[str, str]]
) -> ReconciliationReport:
    unknown_types = sorted(set(df["type"]) - set(rules.keys()))
    if unknown_types:
        raise ValueError(f"Unknown interaction types for reconciliation: {unknown_types}")

    total_outflow = 0.0
    total_inflow = 0.0
    per_type: Dict[str, Dict[str, float]] = {}
    for event_type, rule in rules.items():
        df_type = df[df["type"] == event_type]
        if df_type.empty:
            continue
        debit_col = rule.get("debit")
        credit_col = rule.get("credit")
        if debit_col not in df.columns or credit_col not in df.columns:
            raise ValueError(
                f"Reconciliation rule for '{event_type}' requires columns "
                f"'{debit_col}' and '{credit_col}'"
            )
        debit_sum = float(df_type["amount"].sum())
        credit_sum = float(df_type["amount"].sum())
        diff = abs(debit_sum - credit_sum)
        if diff > tolerance:
            raise ValueError(
                f"Reconciliation failed for type '{event_type}': diff {diff} > {tolerance}"
            )
        per_type[event_type] = {
            "total_debit": debit_sum,
            "total_credit": credit_sum,
            "diff": diff,
        }
        total_outflow += debit_sum
        total_inflow += credit_sum

    diff_total = abs(total_outflow - total_inflow)
    status = "pass" if diff_total <= tolerance else "fail"
    if status == "fail":
        raise ValueError(
            f"Reconciliation failed: diff {diff_total} > tolerance {tolerance}"
        )
    return ReconciliationReport(
        status=status,
        tolerance=tolerance,
        total_outflow=total_outflow,
        total_inflow=total_inflow,
        diff=diff_total,
        per_type=per_type,
    )


def ingest_macro(
    raw_path: Path,
    staging_dir: Path,
    curated_dir: Path,
    db: SimulationDB,
    manifest_source: str,
    manifest_license: str,
    schema_version: str = "1.0",
) -> Path:
    df_raw = pd.read_csv(raw_path)
    df_valid, rejects = _validate_rows(df_raw, MacroRow)

    staging_path = staging_dir / "macro.parquet"
    curated_path = curated_dir / "macro.parquet"
    staging_dir.mkdir(parents=True, exist_ok=True)
    curated_dir.mkdir(parents=True, exist_ok=True)

    df_valid.to_parquet(staging_path, index=False)
    df_valid.to_parquet(curated_path, index=False)

    _write_rejects(rejects, staging_dir / "rejects" / "macro_rejects.jsonl")

    # Load into DuckDB
    if not df_valid.empty:
        db.conn.execute("""
            INSERT INTO macro_history (run_id, step, gdp, unemployment_rate, inflation_rate, avg_price, avg_income, government_balance)
            SELECT run_id, step, gdp, unemployment_rate, inflation_rate, avg_price, avg_income, government_balance
            FROM df_valid
        """)

    manifest = DatasetManifest(
        dataset_name="macro",
        source=manifest_source,
        license=manifest_license,
        raw_hash=_file_hash(raw_path),
        schema_version=schema_version,
        row_count=int(len(df_valid)),
        pii_flags={},
        quality=_quality_metrics(df_valid, ["run_id", "step"]),
    )
    manifest_path = curated_dir / "macro_manifest.json"
    manifest_path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
    return curated_path


def ingest_agents(
    raw_path: Path,
    staging_dir: Path,
    curated_dir: Path,
    db: SimulationDB,
    graph: GraphStore,
    manifest_source: str,
    manifest_license: str,
    schema_version: str = "1.0",
) -> Tuple[Path, Dict[str, str], Path]:
    df_raw = pd.read_csv(raw_path)
    df_valid, rejects = _validate_rows(df_raw, AgentRow)
    resolution_df, entity_map = _build_entity_resolution(df_valid)
    df_valid["canonical_id"] = df_valid["agent_id"].map(entity_map)

    staging_path = staging_dir / "agents.parquet"
    curated_path = curated_dir / "agents.parquet"
    staging_dir.mkdir(parents=True, exist_ok=True)
    curated_dir.mkdir(parents=True, exist_ok=True)

    df_valid.to_parquet(staging_path, index=False)
    df_valid.to_parquet(curated_path, index=False)
    resolution_path = curated_dir / "entity_resolution.parquet"
    resolution_df.to_parquet(resolution_path, index=False)

    _write_rejects(rejects, staging_dir / "rejects" / "agents_rejects.jsonl")

    # Load into DuckDB (agents_snapshot)
    if not df_valid.empty:
        df_db = df_valid.copy()
        df_db["run_id"] = "demo_run"
        df_db["step"] = 0
        df_db["agent_id"] = df_db["canonical_id"]
        df_db = df_db[
            ["run_id", "step", "agent_id", "age", "income", "savings", "is_employed"]
        ]
        db.conn.execute("""
            INSERT INTO agents_snapshot (run_id, step, agent_id, age, income, savings, is_employed)
            SELECT run_id, step, agent_id, age, income, savings, is_employed
            FROM df_db
        """)
        if not resolution_df.empty:
            db.conn.execute(
                """
                INSERT INTO entity_resolution (raw_id, canonical_id, match_confidence, match_method)
                SELECT raw_id, canonical_id, match_confidence, match_method
                FROM resolution_df
            """
            )

    # Load into Kùzu
    for _, row in df_valid.iterrows():
        graph.add_agent(str(row["canonical_id"]), str(row["agent_type"]))

    manifest = DatasetManifest(
        dataset_name="agents",
        source=manifest_source,
        license=manifest_license,
        raw_hash=_file_hash(raw_path),
        schema_version=schema_version,
        row_count=int(len(df_valid)),
        pii_flags={"agent_id": True},
        quality=_quality_metrics(df_valid, ["agent_id"]),
    )
    manifest_path = curated_dir / "agents_manifest.json"
    manifest_path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
    resolution_manifest = DatasetManifest(
        dataset_name="entity_resolution",
        source=manifest_source,
        license=manifest_license,
        raw_hash=_file_hash(raw_path),
        schema_version=schema_version,
        row_count=int(len(resolution_df)),
        pii_flags={},
        quality=_quality_metrics(resolution_df, ["raw_id", "canonical_id"]),
    )
    resolution_manifest_path = curated_dir / "entity_resolution_manifest.json"
    resolution_manifest_path.write_text(
        resolution_manifest.model_dump_json(indent=2), encoding="utf-8"
    )
    return curated_path, entity_map, resolution_path


def ingest_interactions(
    raw_path: Path,
    staging_dir: Path,
    curated_dir: Path,
    graph: GraphStore,
    entity_map: Dict[str, str],
    manifest_source: str,
    manifest_license: str,
    schema_version: str = "1.0",
    reconciliation_tolerance: float = DEFAULT_RECONCILIATION_TOLERANCE,
) -> Path:
    df_raw = pd.read_csv(raw_path)
    df_valid, rejects = _validate_rows(df_raw, InteractionRow)

    staging_path = staging_dir / "interactions.parquet"
    curated_path = curated_dir / "interactions.parquet"
    staging_dir.mkdir(parents=True, exist_ok=True)
    curated_dir.mkdir(parents=True, exist_ok=True)

    def _map_id(raw_id: str) -> str:
        if raw_id not in entity_map:
            raise ValueError(f"Missing canonical_id for raw_id '{raw_id}'")
        return entity_map[raw_id]

    df_valid["from_canonical_id"] = df_valid["from_id"].map(_map_id)
    df_valid["to_canonical_id"] = df_valid["to_id"].map(_map_id)

    df_valid.to_parquet(staging_path, index=False)
    df_valid.to_parquet(curated_path, index=False)

    _write_rejects(rejects, staging_dir / "rejects" / "interactions_rejects.jsonl")

    reconciliation = _reconcile_interactions(
        df_valid, reconciliation_tolerance, RECONCILIATION_RULES
    )

    # Load into Kùzu
    for _, row in df_valid.iterrows():
        graph.add_agent(str(row["from_canonical_id"]), "agent")
        graph.add_agent(str(row["to_canonical_id"]), "agent")
        graph.add_interaction(
            from_id=str(row["from_canonical_id"]),
            to_id=str(row["to_canonical_id"]),
            step=int(row["step"]),
            amount=float(row["amount"]),
            type_=str(row["type"]),
        )

    manifest = DatasetManifest(
        dataset_name="interactions",
        source=manifest_source,
        license=manifest_license,
        raw_hash=_file_hash(raw_path),
        schema_version=schema_version,
        row_count=int(len(df_valid)),
        pii_flags={},
        quality=_quality_metrics(df_valid, ["from_id", "to_id", "step", "type"]),
        reconciliation=reconciliation,
    )
    manifest_path = curated_dir / "interactions_manifest.json"
    manifest_path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
    return curated_path


def run_ingestion(
    raw_dir: Path,
    staging_dir: Path,
    curated_dir: Path,
    db_path: Path,
    kuzu_path: Path,
    source: str,
    license_name: str,
    clear_on_start: bool = False,
) -> None:
    if clear_on_start and db_path.exists():
        db_path.unlink()
    db = SimulationDB(str(db_path))
    graph = GraphStore(str(kuzu_path), clear_on_start=True)

    ingest_macro(
        raw_path=raw_dir / "macro.csv",
        staging_dir=staging_dir,
        curated_dir=curated_dir,
        db=db,
        manifest_source=source,
        manifest_license=license_name,
    )
    _, entity_map, _ = ingest_agents(
        raw_path=raw_dir / "agents.csv",
        staging_dir=staging_dir,
        curated_dir=curated_dir,
        db=db,
        graph=graph,
        manifest_source=source,
        manifest_license=license_name,
    )
    ingest_interactions(
        raw_path=raw_dir / "interactions.csv",
        staging_dir=staging_dir,
        curated_dir=curated_dir,
        graph=graph,
        entity_map=entity_map,
        manifest_source=source,
        manifest_license=license_name,
    )

    db.close()
