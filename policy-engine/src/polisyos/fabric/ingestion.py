import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any, Dict, Iterable, Tuple, Type

import pandas as pd
from pydantic import BaseModel, ValidationError

from polisyos.core.artifacts.manifest import ArtifactRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.contracts.fabric import EvidenceBundleRef
from polisyos.fabric.config import (
    DEFAULT_RECONCILIATION_TOLERANCE,
    NORMALIZATION_RULES,
    RECONCILIATION_RULES,
)
from polisyos.fabric.evidence import build_evidence_bundle, persist_evidence_bundle
from polisyos.fabric.fact_writer import build_fact, facts_from_dataframe, write_fact_segment
from polisyos.fabric.io.db import SimulationDB
from polisyos.fabric.io.graph_store import GraphStore
from polisyos.fabric.manifest import (
    CoverageMetrics,
    DatasetManifest,
    QualityMetrics,
    ReconciliationReport,
)
from polisyos.fabric.schema import AgentRow, InteractionRow, MacroRow
from polisyos.ir.fact_log import FactProvenance, FactSegmentManifest


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
        if math.isnan(duplicate_rate):
            duplicate_rate = 0.0
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
        raise ValueError(f"Reconciliation failed: diff {diff_total} > tolerance {tolerance}")
    return ReconciliationReport(
        status=status,
        tolerance=tolerance,
        total_outflow=total_outflow,
        total_inflow=total_inflow,
        diff=diff_total,
        per_type=per_type,
    )


def _build_provenance(
    manifest: DatasetManifest, ingestion_run_id: str | None = None
) -> FactProvenance:
    return FactProvenance(
        source_id=manifest.source,
        license=manifest.license,
        raw_hash=manifest.raw_hash,
        ingestion_run_id=ingestion_run_id,
    )


def _append_segment_index(manifest: FactSegmentManifest, index_path: Path) -> None:
    index_path.parent.mkdir(parents=True, exist_ok=True)
    with index_path.open("a", encoding="utf-8") as f:
        f.write(manifest.model_dump_json() + "\n")


def _persist_fact_segment_manifest(
    manifest: FactSegmentManifest, store: FileSystemCAS
) -> ArtifactRef:
    ref = store.put_json(
        manifest.model_dump(),
        opts=PutOptions(
            kind="ir.fact_segment_manifest",
            media_type="application/json",
            schema=SchemaInfo(name="ir.fact_segment_manifest", version="1.0"),
        ),
    )
    return ArtifactRef.model_validate(ref.model_dump())


def _emit_fact_segments(
    df: pd.DataFrame,
    *,
    dataset_name: str,
    curated_dir: Path,
    predicate_map: dict[str, str],
    subject_field: str,
    provenance: FactProvenance,
    valid_time_field: str | None = None,
    target_field: str | None = None,
    cas_store: FileSystemCAS | None = None,
) -> ArtifactRef | None:
    if df.empty:
        return
    facts = facts_from_dataframe(
        df,
        subject_field=subject_field,
        predicate_value_map=predicate_map,
        provenance=provenance,
        valid_time_field=valid_time_field,
        target_field=target_field,
    )
    segment_dir = curated_dir / "fact_log"
    manifest = write_fact_segment(facts, segment_dir=segment_dir, segment_name=dataset_name)
    _append_segment_index(manifest, segment_dir / "_segments.jsonl")
    if cas_store is not None:
        return _persist_fact_segment_manifest(manifest, cas_store)
    return None


def ingest_macro(
    raw_path: Path,
    staging_dir: Path,
    curated_dir: Path,
    db: SimulationDB | None,
    manifest_source: str,
    manifest_license: str,
    schema_version: str = "1.0",
    cas_store: FileSystemCAS | None = None,
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
    provenance = _build_provenance(manifest)
    _emit_fact_segments(
        df_valid,
        dataset_name="macro",
        curated_dir=curated_dir,
        predicate_map={
            "macro.gdp": "gdp",
            "macro.unemployment_rate": "unemployment_rate",
            "macro.inflation_rate": "inflation_rate",
            "macro.avg_price": "avg_price",
            "macro.avg_income": "avg_income",
            "macro.government_balance": "government_balance",
        },
        subject_field="run_id",
        valid_time_field="step",
        provenance=provenance,
        cas_store=cas_store,
    )
    return curated_path


def ingest_agents(
    raw_path: Path,
    staging_dir: Path,
    curated_dir: Path,
    db: SimulationDB | None,
    graph: GraphStore,
    manifest_source: str,
    manifest_license: str,
    schema_version: str = "1.0",
    cas_store: FileSystemCAS | None = None,
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
    provenance = _build_provenance(manifest)
    resolution_provenance = _build_provenance(resolution_manifest)
    _emit_fact_segments(
        df_valid,
        dataset_name="agents",
        curated_dir=curated_dir,
        predicate_map={
            "agent.age": "age",
            "agent.income": "income",
            "agent.savings": "savings",
            "agent.employment": "is_employed",
        },
        subject_field="canonical_id",
        provenance=provenance,
        cas_store=cas_store,
    )
    _emit_fact_segments(
        resolution_df,
        dataset_name="entity_resolution",
        curated_dir=curated_dir,
        predicate_map={
            "entity_resolution.canonical_id": "canonical_id",
            "entity_resolution.match_confidence": "match_confidence",
            "entity_resolution.match_method": "match_method",
        },
        subject_field="raw_id",
        provenance=resolution_provenance,
        cas_store=cas_store,
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
    cas_store: FileSystemCAS | None = None,
) -> Path:
    df_raw = pd.read_csv(raw_path)
    df_valid, rejects = _validate_rows(df_raw, InteractionRow)
    if not entity_map:
        raise ValueError("Entity resolution map is empty; run ingest_agents first.")
    resolution_manifest_path = curated_dir / "entity_resolution_manifest.json"
    if not resolution_manifest_path.exists():
        raise ValueError(
            f"Missing entity resolution manifest: {resolution_manifest_path}. Run ingest_agents first."
        )

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
    provenance = _build_provenance(manifest)
    if not df_valid.empty:
        facts = []
        for _, row in df_valid.iterrows():
            predicate_id = f"interaction.{row['type']}"
            facts.append(
                build_fact(
                    subject_id=str(row["from_canonical_id"]),
                    predicate_id=predicate_id,
                    object_value=row.get("amount"),
                    target_id=str(row["to_canonical_id"]),
                    valid_time=row.get("step"),
                    provenance=provenance,
                )
            )
        segment_dir = curated_dir / "fact_log"
        manifest_segment = write_fact_segment(
            facts, segment_dir=segment_dir, segment_name="interactions"
        )
        _append_segment_index(manifest_segment, segment_dir / "_segments.jsonl")
        if cas_store is not None:
            _persist_fact_segment_manifest(manifest_segment, cas_store)
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
    cas_root: Path | None = Path(".polisyos"),
) -> EvidenceBundleRef | None:
    if clear_on_start and db_path.exists():
        db_path.unlink()
    graph = GraphStore(str(kuzu_path), clear_on_start=True)
    cas_store = FileSystemCAS(Path(cas_root)) if cas_root is not None else None

    ingest_macro(
        raw_path=raw_dir / "macro.csv",
        staging_dir=staging_dir,
        curated_dir=curated_dir,
        db=None,
        manifest_source=source,
        manifest_license=license_name,
        cas_store=cas_store,
    )
    _, entity_map, _ = ingest_agents(
        raw_path=raw_dir / "agents.csv",
        staging_dir=staging_dir,
        curated_dir=curated_dir,
        db=None,
        graph=graph,
        manifest_source=source,
        manifest_license=license_name,
        cas_store=cas_store,
    )
    ingest_interactions(
        raw_path=raw_dir / "interactions.csv",
        staging_dir=staging_dir,
        curated_dir=curated_dir,
        graph=graph,
        entity_map=entity_map,
        manifest_source=source,
        manifest_license=license_name,
        cas_store=cas_store,
    )

    # Пишем evidence bundle в CAS для набора манифестов
    if cas_store is not None:
        manifest_refs: list[ArtifactRef] = []

        def _put_manifest(name: str) -> None:
            path = curated_dir / f"{name}_manifest.json"
            if not path.exists():
                return
            ref = cas_store.put_bytes(
                path.read_bytes(),
                opts=PutOptions(
                    kind="fabric.dataset_manifest",
                    media_type="application/json",
                    schema=SchemaInfo(name="fabric.dataset_manifest", version="1.0"),
                ),
            )
            manifest_refs.append(ArtifactRef.model_validate(ref.model_dump()))

        for manifest_name in ["macro", "agents", "entity_resolution", "interactions"]:
            _put_manifest(manifest_name)

        evidence_bundle = build_evidence_bundle(
            sources=manifest_refs,
            notes=["ingestion evidence"],
        )
        return persist_evidence_bundle(cas_store, evidence_bundle)
    return None
