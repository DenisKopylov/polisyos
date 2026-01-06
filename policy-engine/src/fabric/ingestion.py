import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Tuple, Type

import pandas as pd
from pydantic import BaseModel, ValidationError

from src.fabric.manifest import CoverageMetrics, DatasetManifest, QualityMetrics
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
        db.conn.execute("INSERT INTO macro_history SELECT * FROM df_valid")

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
) -> Path:
    df_raw = pd.read_csv(raw_path)
    df_valid, rejects = _validate_rows(df_raw, AgentRow)

    staging_path = staging_dir / "agents.parquet"
    curated_path = curated_dir / "agents.parquet"
    staging_dir.mkdir(parents=True, exist_ok=True)
    curated_dir.mkdir(parents=True, exist_ok=True)

    df_valid.to_parquet(staging_path, index=False)
    df_valid.to_parquet(curated_path, index=False)

    _write_rejects(rejects, staging_dir / "rejects" / "agents_rejects.jsonl")

    # Load into DuckDB (agents_snapshot)
    if not df_valid.empty:
        df_db = df_valid.copy()
        df_db["run_id"] = "demo_run"
        df_db["step"] = 0
        df_db = df_db[
            ["run_id", "step", "agent_id", "age", "income", "savings", "is_employed"]
        ]
        db.conn.execute("INSERT INTO agents_snapshot SELECT * FROM df_db")

    # Load into Kùzu
    for _, row in df_valid.iterrows():
        graph.add_agent(str(row["agent_id"]), str(row["agent_type"]))

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
    return curated_path


def ingest_interactions(
    raw_path: Path,
    staging_dir: Path,
    curated_dir: Path,
    graph: GraphStore,
    manifest_source: str,
    manifest_license: str,
    schema_version: str = "1.0",
) -> Path:
    df_raw = pd.read_csv(raw_path)
    df_valid, rejects = _validate_rows(df_raw, InteractionRow)

    staging_path = staging_dir / "interactions.parquet"
    curated_path = curated_dir / "interactions.parquet"
    staging_dir.mkdir(parents=True, exist_ok=True)
    curated_dir.mkdir(parents=True, exist_ok=True)

    df_valid.to_parquet(staging_path, index=False)
    df_valid.to_parquet(curated_path, index=False)

    _write_rejects(rejects, staging_dir / "rejects" / "interactions_rejects.jsonl")

    # Load into Kùzu
    for _, row in df_valid.iterrows():
        graph.add_agent(str(row["from_id"]), "agent")
        graph.add_agent(str(row["to_id"]), "agent")
        graph.add_interaction(
            from_id=str(row["from_id"]),
            to_id=str(row["to_id"]),
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
) -> None:
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
    ingest_agents(
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
        manifest_source=source,
        manifest_license=license_name,
    )

    db.close()
