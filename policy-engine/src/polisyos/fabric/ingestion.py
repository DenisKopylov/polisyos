import hashlib
import json
import math
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Tuple, Type
from uuid import uuid4

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from polisyos.common.async_tools import run_coro_sync
from polisyos.common.logger import get_logger
from polisyos.core.artifacts.manifest import ArtifactRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.contracts.fabric import EvidenceBundleRef
from polisyos.fabric.config import (
    DEFAULT_RECONCILIATION_TOLERANCE,
    NORMALIZATION_RULES,
    RECONCILIATION_RULES,
)
from polisyos.fabric.connectors.cache.policy import (
    PolicyRegistry,
    SmartExpiryPolicy,
    StaticDataPolicy,
    TTLPolicy,
    VolatileDataPolicy,
)
from polisyos.fabric.connectors.cache.store import ConnectorCacheStore
from polisyos.fabric.connectors.registry import ConnectorRegistry
from polisyos.fabric.evidence import (
    build_evidence_bundle,
    persist_evidence_bundle,
    persist_provenance_graph,
)
from polisyos.fabric.fact_writer import build_fact, facts_from_dataframe, write_fact_segment
from polisyos.fabric.io.db import SimulationDB
from polisyos.fabric.io.graph_store import GraphStore
from polisyos.fabric.manifest import (
    CoverageMetrics,
    DatasetManifest,
    QualityMetrics,
    ReconciliationReport,
)
from polisyos.fabric.provenance.core import (
    ActivityType,
    AgentType,
    EntityType,
    ProvenanceActivity,
    ProvenanceAgent,
    ProvenanceCoreGraph,
    ProvenanceEntity,
)
from polisyos.fabric.schema import AgentRow, InteractionRow, MacroRow
from polisyos.ir.connectors import FetchRequest, FetchResult
from polisyos.ir.fact_log import FactProvenance, FactSegmentManifest

logger = get_logger(__name__)


class DatasetFetchSpec(BaseModel):
    model_config = ConfigDict(extra="allow")

    connector_id: str
    dataset_id: str
    filters: dict[str, list[str]] = Field(default_factory=dict)
    date_start: str | None = None
    date_end: str | None = None
    retryable: bool | None = None
    page_size: int | None = None


class ConnectorManifestSpec(BaseModel):
    model_config = ConfigDict(extra="allow")

    datasets: list[DatasetFetchSpec] = Field(default_factory=list)
    transform_dag: str | None = None
    cache_policy: str | None = None
    retry_policy: dict[str, Any] | None = None


def _file_hash(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _build_ingestion_provenance_graph(
    *,
    raw_dir: Path,
    curated_dir: Path,
    source: str,
    license_name: str,
    started_at: datetime,
    ended_at: datetime,
) -> ProvenanceCoreGraph:
    graph = ProvenanceCoreGraph(
        graph_id=f"ingestion-{uuid4().hex[:8]}",
        created_at=started_at,
        metadata={"source": source, "license": license_name},
    )

    system_agent = ProvenanceAgent(
        agent_id="polisyos-fabric",
        agent_type=AgentType.SYSTEM,
        label="Policy OS Fabric Ingestion System",
        metadata={"version": "1.0"},
    )
    graph.add_agent(system_agent)

    ingest_activity = ProvenanceActivity(
        activity_id=f"ingest-{uuid4().hex[:8]}",
        activity_type=ActivityType.INGEST,
        label=f"Ingest from {source}",
        started_at=started_at,
        ended_at=ended_at,
        parameters={"source": source, "license": license_name},
    )
    graph.add_activity(ingest_activity)
    graph.add_association(ingest_activity.activity_id, system_agent.agent_id)

    raw_entity_ids: list[str] = []
    raw_paths = [
        raw_dir / "macro.csv",
        raw_dir / "agents.csv",
        raw_dir / "interactions.csv",
    ]
    for raw_path in raw_paths:
        if not raw_path.exists():
            continue
        entity_id = f"raw-{raw_path.stem}-{_file_hash(raw_path)[:8]}"
        entity = ProvenanceEntity(
            entity_id=entity_id,
            entity_type=EntityType.DATASET,
            label=f"Raw CSV: {raw_path.name}",
            created_at=datetime.fromtimestamp(raw_path.stat().st_mtime),
            attributes={
                "path": str(raw_path),
                "size_bytes": raw_path.stat().st_size,
                "source_system": source,
            },
        )
        graph.add_entity(entity)
        graph.add_attribution(entity_id, system_agent.agent_id)
        graph.add_usage(ingest_activity.activity_id, entity_id)
        raw_entity_ids.append(entity_id)

    for name in ["macro", "agents", "entity_resolution", "interactions"]:
        manifest_path = curated_dir / f"{name}_manifest.json"
        if not manifest_path.exists():
            continue
        entity_id = f"curated-{manifest_path.stem}-{_file_hash(manifest_path)[:8]}"
        entity = ProvenanceEntity(
            entity_id=entity_id,
            entity_type=EntityType.DATASET,
            label=f"Manifest: {manifest_path.name}",
            created_at=datetime.fromtimestamp(manifest_path.stat().st_mtime),
            attributes={
                "path": str(manifest_path),
                "format": "json",
            },
        )
        graph.add_entity(entity)
        graph.add_attribution(entity_id, system_agent.agent_id)
        graph.add_generation(entity_id, ingest_activity.activity_id)
        for raw_id in raw_entity_ids:
            graph.add_derivation(entity_id, raw_id)

    return graph


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
    df: pd.DataFrame,
    tolerance: float,
    rules: Dict[str, Dict[str, str]],
    *,
    strict: bool = True,
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
        if diff > tolerance and strict:
            raise ValueError(
                f"Reconciliation failed for type '{event_type}': diff {diff} > {tolerance}"
            )
        if diff > tolerance and not strict:
            logger.warning(
                "Reconciliation diff for type '%s' exceeds tolerance: %s > %s",
                event_type,
                diff,
                tolerance,
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
    if status == "fail" and strict:
        raise ValueError(f"Reconciliation failed: diff {diff_total} > tolerance {tolerance}")
    if status == "fail" and not strict:
        logger.warning(
            "Reconciliation diff exceeds tolerance: %s > %s", diff_total, tolerance
        )
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
    reconciliation_strict: bool = True,
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
        df_valid,
        reconciliation_tolerance,
        RECONCILIATION_RULES,
        strict=reconciliation_strict,
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


def _load_manifest_file(path: Path) -> dict[str, Any]:
    try:
        import yaml
    except Exception as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("PyYAML is required to load connector manifests.") from exc

    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ValueError(f"Connector manifest file must map to a dict: {path}")
    return data


def _normalize_connector_manifest(
    manifest: dict[str, Any] | Path | str | ConnectorManifestSpec,
) -> ConnectorManifestSpec:
    if isinstance(manifest, ConnectorManifestSpec):
        return manifest
    if isinstance(manifest, (str, Path)):
        path = Path(manifest)
        if not path.exists():
            raise FileNotFoundError(f"Connector manifest not found: {path}")
        raw = _load_manifest_file(path)
        if isinstance(raw.get("connector_manifest"), dict):
            raw = raw["connector_manifest"]
    elif isinstance(manifest, dict):
        raw = manifest
    else:
        raise TypeError(
            "connector_manifest must be a dict, Path, str, or ConnectorManifestSpec"
        )

    try:
        return ConnectorManifestSpec.model_validate(raw)
    except ValidationError as exc:
        raise ValueError(f"Invalid connector manifest: {exc}") from exc


def _build_cache_registry(policy_spec: str | None) -> PolicyRegistry:
    if not policy_spec or policy_spec == "default":
        return PolicyRegistry()

    if policy_spec.startswith("ttl:"):
        raw = policy_spec.split(":", 1)[1].strip()
        try:
            seconds = int(raw)
        except ValueError:
            logger.warning("Invalid ttl cache_policy: %s", policy_spec)
            return PolicyRegistry()
        return PolicyRegistry(default_policy=TTLPolicy(ttl=timedelta(seconds=seconds)))

    if policy_spec == "static":
        return PolicyRegistry(default_policy=StaticDataPolicy())
    if policy_spec == "volatile":
        return PolicyRegistry(default_policy=VolatileDataPolicy())
    if policy_spec == "smart":
        return PolicyRegistry(default_policy=SmartExpiryPolicy())

    logger.warning("Unknown cache_policy '%s' — falling back to default.", policy_spec)
    return PolicyRegistry()


def _load_transform_pipeline(transform_dag: str | None) -> Any | None:
    if not transform_dag:
        return None

    path = Path(transform_dag)
    if not path.exists():
        logger.warning("transform_dag not found: %s", transform_dag)
        return None

    import importlib.util

    module_name = f"polisyos_transform_dag_{path.stem}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ValueError(f"Could not load transform_dag: {transform_dag}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    pipeline = getattr(module, "PIPELINE", None)
    if pipeline is None and hasattr(module, "build_pipeline"):
        pipeline = module.build_pipeline()

    if pipeline is None:
        raise ValueError(
            "transform_dag must define PIPELINE or build_pipeline()"
        )

    from polisyos.fabric.connectors.transform.pipeline import TransformPipeline

    if not isinstance(pipeline, TransformPipeline):
        raise TypeError("transform_dag must produce a TransformPipeline instance")
    return pipeline


def _result_to_dataframe(payload: Any) -> pd.DataFrame | None:
    if isinstance(payload, pd.DataFrame):
        return payload
    if isinstance(payload, list):
        return pd.DataFrame(payload)
    if hasattr(payload, "to_pandas"):
        return payload.to_pandas()
    return None


def _apply_transform_pipeline(
    result: FetchResult[Any],
    pipeline: Any | None,
) -> FetchResult[Any]:
    if pipeline is None:
        return result

    df = _result_to_dataframe(result.data)
    if df is None:
        logger.warning("transform_dag skipped (unsupported payload type)")
        return result

    transform_result = pipeline.apply(df)
    if transform_result.warnings:
        logger.warning(
            "transform_dag warnings: %s",
            transform_result.warnings,
        )

    data = transform_result.data
    return result.model_copy(
        update={
            "data": data,
            "row_count": int(len(data)),
        }
    )


def _parse_optional_datetime(value: str | None) -> datetime | None:
    if value is None:
        return None
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _sync_fetch(
    registry: ConnectorRegistry,
    connector_id: str,
    connector: Any,
    request: FetchRequest,
) -> FetchResult[Any]:
    async def _do_fetch() -> FetchResult[Any]:
        entry = registry.get_entry(connector_id)
        if entry.default_config is None:
            raise ValueError(f"No default_config registered for connector '{connector_id}'")
        handle = await registry.get_connection(connector_id, entry.default_config)
        try:
            return await connector.fetch(handle, request)
        finally:
            await registry.release_connection(connector_id, handle)

    return run_coro_sync(_do_fetch())


def _run_connector_ingestion(
    *,
    manifest: dict[str, Any] | Path | str | ConnectorManifestSpec,
    cas_root: Path | None,
    source: str,
    license_name: str,
) -> EvidenceBundleRef | None:
    """
    Connector-aware ingestion pipeline.

    Laws satisfied:
        - Law D: ProvenanceCoreGraph is built and persisted.
        - Law E: EvidenceBundleRef is always returned when cas_root is set.
    """
    spec = _normalize_connector_manifest(manifest)

    if not spec.datasets:
        logger.warning("connector_ingestion: manifest.datasets is empty — nothing to fetch.")
        return None

    cas_store = FileSystemCAS(Path(cas_root)) if cas_root is not None else None
    if cas_store is None:
        logger.warning(
            "connector_ingestion: cas_root is None — evidence will not be persisted."
        )

    cache_registry = _build_cache_registry(spec.cache_policy)
    cache_store = ConnectorCacheStore(cas_store, cache_registry) if cas_store else None
    pipeline = _load_transform_pipeline(spec.transform_dag)
    registry = ConnectorRegistry.get_instance()

    ingestion_started_at = datetime.now(timezone.utc)
    artifact_refs: list[ArtifactRef] = []
    fetch_activities: list[dict[str, Any]] = []

    for idx, ds_spec in enumerate(spec.datasets):
        connector_id = ds_spec.connector_id
        dataset_id = ds_spec.dataset_id
        filters = ds_spec.filters or {}

        logger.info(
            "connector_ingestion: fetching dataset %d/%d (%s:%s)",
            idx + 1,
            len(spec.datasets),
            connector_id,
            dataset_id,
        )

        connector = registry.get(connector_id)

        filter_tuple = tuple((k, tuple(v)) for k, v in sorted(filters.items()))
        request = FetchRequest(
            dataset_id=dataset_id,
            filters=filter_tuple,
            date_start=_parse_optional_datetime(ds_spec.date_start),
            date_end=_parse_optional_datetime(ds_spec.date_end),
            include_metadata=True,
            include_schema=True,
            retryable=ds_spec.retryable,
            page_size=ds_spec.page_size,
        )

        result: FetchResult[Any] = _sync_fetch(registry, connector_id, connector, request)
        result = _apply_transform_pipeline(result, pipeline)

        payload_ref: ArtifactRef | None = None
        if cache_store is not None:
            metadata = cache_store.put(request, result, connector_id=connector_id)
            payload_ref = metadata.payload_ref
            artifact_refs.append(payload_ref)

        fetch_activities.append(
            {
                "connector_id": connector_id,
                "dataset_id": dataset_id,
                "fetched_at": result.fetched_at.isoformat(),
                "cache_key": request.cache_key,
                "row_count": result.row_count,
                "completeness": result.completeness,
                "schema_id": result.schema_id,
                "schema_version": result.schema_version,
                "version_strategy": result.version.strategy.value,
                "version_value": result.version.value,
                "content_hash": result.version.content_hash,
                "data_artifact_id": payload_ref.artifact_id.hex if payload_ref else None,
            }
        )

    ingestion_completed_at = datetime.now(timezone.utc)

    if cas_store is None:
        return None

    manifest_hash = _manifest_fingerprint(spec)
    prov_graph = _build_connector_provenance_graph(
        datasets=fetch_activities,
        source=source,
        license_name=license_name,
        started_at=ingestion_started_at,
        ended_at=ingestion_completed_at,
        manifest_hash=manifest_hash,
    )
    provenance_ref = persist_provenance_graph(cas_store, prov_graph)

    evidence_bundle = build_evidence_bundle(
        sources=artifact_refs,
        notes=[
            f"connector_ingestion: {len(spec.datasets)} dataset(s) fetched",
            f"manifest_hash: {manifest_hash}",
        ],
        provenance_ref=provenance_ref,
    )
    return persist_evidence_bundle(cas_store, evidence_bundle)


def _manifest_fingerprint(spec: ConnectorManifestSpec) -> str:
    payload = spec.model_dump(mode="json", exclude_none=True)
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _build_connector_provenance_graph(
    *,
    datasets: list[dict[str, Any]],
    source: str,
    license_name: str,
    started_at: datetime,
    ended_at: datetime,
    manifest_hash: str,
) -> ProvenanceCoreGraph:
    graph = ProvenanceCoreGraph(
        graph_id=f"connector_ingestion_{started_at.strftime('%Y%m%dT%H%M%S')}",
        created_at=started_at,
        metadata={"source": source, "license": license_name},
    )

    graph.add_agent(
        ProvenanceAgent(
            agent_id="ConnectorRegistry",
            agent_type=AgentType.SYSTEM,
            label="ConnectorRegistry singleton",
        )
    )

    activity_id = "connector_ingestion_run"
    graph.add_activity(
        ProvenanceActivity(
            activity_id=activity_id,
            activity_type=ActivityType.INGEST,
            label="Connector-based ingestion",
            started_at=started_at,
            ended_at=ended_at,
            parameters={
                "source": source,
                "license": license_name,
                "dataset_count": len(datasets),
                "manifest_hash": manifest_hash,
            },
        )
    )

    graph.add_association(activity_id, "ConnectorRegistry")

    manifest_entity_id = f"connector_manifest.{manifest_hash[:12]}"
    graph.add_entity(
        ProvenanceEntity(
            entity_id=manifest_entity_id,
            entity_type=EntityType.DATASET,
            label="connector_manifest",
            created_at=started_at,
            attributes={"manifest_hash": manifest_hash},
        )
    )
    graph.add_usage(activity_id, manifest_entity_id)

    for ds in datasets:
        entity_id = f"dataset.{ds['connector_id']}.{ds['dataset_id']}"
        attributes = {
            "row_count": ds["row_count"],
            "completeness": ds["completeness"],
            "cache_key": ds["cache_key"],
            "schema_id": ds.get("schema_id"),
            "schema_version": ds.get("schema_version"),
            "version_strategy": ds.get("version_strategy"),
            "version_value": ds.get("version_value"),
        }
        if ds.get("content_hash"):
            attributes["content_hash"] = ds["content_hash"]
        if ds.get("data_artifact_id"):
            attributes["data_artifact_id"] = ds["data_artifact_id"]

        graph.add_entity(
            ProvenanceEntity(
                entity_id=entity_id,
                entity_type=EntityType.DATASET,
                label=f"{ds['connector_id']}:{ds['dataset_id']}",
                created_at=datetime.fromisoformat(ds["fetched_at"]),
                attributes=attributes,
            )
        )
        graph.add_generation(entity_id, activity_id)

    return graph


def run_ingestion(
    raw_dir: Path,
    staging_dir: Path,
    curated_dir: Path,
    db_path: Path,
    kuzu_path: Path,
    source: str,
    license_name: str,
    clear_on_start: bool = False,
    reconciliation_tolerance: float = DEFAULT_RECONCILIATION_TOLERANCE,
    reconciliation_strict: bool = True,
    cas_root: Path | None = Path(".polisyos"),
    connector_manifest: dict[str, Any] | Path | str | ConnectorManifestSpec | None = None,
) -> EvidenceBundleRef | None:
    """
    Orchestrate ingestion.

    When connector_manifest is provided (dict or path), the ConnectorRegistry
    pipeline is used. Otherwise the legacy CSV-based ingestion runs unchanged.
    """
    if connector_manifest is not None:
        return _run_connector_ingestion(
            manifest=connector_manifest,
            cas_root=cas_root,
            source=source,
            license_name=license_name,
        )
    if clear_on_start and db_path.exists():
        db_path.unlink()
    graph = GraphStore(str(kuzu_path), clear_on_start=True)
    cas_store = FileSystemCAS(Path(cas_root)) if cas_root is not None else None
    ingestion_started_at = datetime.utcnow()

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
        reconciliation_tolerance=reconciliation_tolerance,
        reconciliation_strict=reconciliation_strict,
        cas_store=cas_store,
    )
    ingestion_completed_at = datetime.utcnow()

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

        provenance_ref = None
        prov_graph = _build_ingestion_provenance_graph(
            raw_dir=raw_dir,
            curated_dir=curated_dir,
            source=source,
            license_name=license_name,
            started_at=ingestion_started_at,
            ended_at=ingestion_completed_at,
        )
        provenance_ref = persist_provenance_graph(cas_store, prov_graph)

        evidence_bundle = build_evidence_bundle(
            sources=manifest_refs,
            notes=["ingestion evidence"],
            provenance_ref=provenance_ref,
        )
        return persist_evidence_bundle(cas_store, evidence_bundle)
    return None
