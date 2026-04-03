"""Public fabric ingestion module API."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from polisyos.common.async_tools import run_coro_sync
from polisyos.common.logger import get_logger
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import content_hash
from polisyos.core.contracts.fabric import EvidenceBundleRef
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
from polisyos.fabric.provenance.core import (
    ActivityType,
    AgentType,
    EntityType,
    ProvenanceActivity,
    ProvenanceAgent,
    ProvenanceCoreGraph,
    ProvenanceEntity,
)
from polisyos.fabric.tabular import payload_to_dataframe
from polisyos.ir.connectors import FetchRequest, FetchResult

logger = get_logger(__name__)


class DatasetFetchSpec(BaseModel):
    """Dataset fetch spec data model."""
    model_config = ConfigDict(extra="allow")

    connector_id: str
    dataset_id: str
    filters: dict[str, list[str]] = Field(default_factory=dict)
    date_start: str | None = None
    date_end: str | None = None
    retryable: bool | None = None
    page_size: int | None = None


class ConnectorManifestSpec(BaseModel):
    """Connector manifest spec data model."""
    model_config = ConfigDict(extra="allow")

    datasets: list[DatasetFetchSpec] = Field(default_factory=list)
    transform_dag: str | None = None
    cache_policy: str | None = None
    retry_policy: dict[str, Any] | None = None


def _canon_scalar(value: Any) -> Any:
    """Convert non-canonical scalars (e.g. float) to canonical-friendly values."""
    if isinstance(value, float):
        return str(value)
    return value


def _load_manifest_file(path: Path) -> dict[str, Any]:
    suffix = path.suffix.lower()
    text = path.read_text(encoding="utf-8")
    if suffix in {".yml", ".yaml"}:
        import yaml

        data = yaml.safe_load(text)
    else:
        data = json.loads(text)
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
        raise ValueError("transform_dag must define PIPELINE or build_pipeline()")

    from polisyos.fabric.connectors.transform.pipeline import TransformPipeline

    if not isinstance(pipeline, TransformPipeline):
        raise TypeError("transform_dag must produce a TransformPipeline instance")
    return pipeline


def _apply_transform_pipeline(
    result: FetchResult[Any],
    pipeline: Any | None,
) -> FetchResult[Any]:
    if pipeline is None:
        return result

    df = payload_to_dataframe(result.data)
    if df is None:
        logger.warning("transform_dag skipped (unsupported payload type)")
        return result

    transform_result = pipeline.apply(df)
    if transform_result.warnings:
        logger.warning("transform_dag warnings: %s", transform_result.warnings)

    data = transform_result.data
    return result.model_copy(update={"data": data, "row_count": int(len(data))})


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
    *,
    connection_config: Any | None = None,
) -> FetchResult[Any]:
    async def _do_fetch() -> FetchResult[Any]:
        config = connection_config
        if config is None:
            entry = registry.get_entry(connector_id)
            if entry.default_config is None:
                raise ValueError(
                    f"No default_config registered for connector '{connector_id}'"
                )
            config = entry.default_config
        handle = await registry.get_connection(connector_id, config)
        try:
            return await connector.fetch(handle, request)
        finally:
            await registry.release_connection(connector_id, handle)

    return run_coro_sync(_do_fetch())


def _manifest_fingerprint(spec: ConnectorManifestSpec) -> str:
    payload = spec.model_dump(mode="json", exclude_none=True)
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return content_hash(canonical)


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
            "source_updated_at": ds.get("source_updated_at"),
            "fetch_duration_ms": ds.get("fetch_duration_ms"),
        }
        if ds.get("content_hash"):
            attributes["content_hash"] = ds["content_hash"]
        if ds.get("quality_flags"):
            attributes["quality_flags"] = ",".join(ds["quality_flags"])
        if ds.get("data_artifact_id"):
            attributes["data_artifact_id"] = ds["data_artifact_id"]
        if ds.get("pii_max_severity"):
            attributes["pii_max_severity"] = ds["pii_max_severity"]
        if ds.get("pii_entities_total") is not None:
            attributes["pii_entities_total"] = int(ds["pii_entities_total"])
        if ds.get("pii_sampled") is not None:
            attributes["pii_sampled"] = bool(ds["pii_sampled"])

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


def run_connectors_ingestion(
    *,
    connector_manifest: dict[str, Any] | Path | str | ConnectorManifestSpec,
    source: str,
    license_name: str,
    cas_root: Path | None = Path(".polisyos"),
    connection_config: Any | None = None,
) -> EvidenceBundleRef | None:
    """Canonical connector ingestion entrypoint."""
    spec = _normalize_connector_manifest(connector_manifest)
    if not spec.datasets:
        logger.warning("connector_ingestion: manifest.datasets is empty — nothing to fetch.")
        return None

    cas_store = FileSystemCAS(Path(cas_root)) if cas_root is not None else None
    if cas_store is None:
        logger.warning("connector_ingestion: cas_root is None — evidence will not be persisted.")

    cache_registry = _build_cache_registry(spec.cache_policy)
    cache_store = ConnectorCacheStore(cas_store, cache_registry) if cas_store else None
    pipeline = _load_transform_pipeline(spec.transform_dag)
    registry = ConnectorRegistry.get_instance()
    pii_stage = None
    try:
        from polisyos.fabric.pii import PIIDetectionStage

        pii_stage = PIIDetectionStage.from_env()
    except Exception as exc:
        logger.warning("connector_ingestion: failed to initialize PII stage: %s", exc)
        pii_stage = None

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

        result: FetchResult[Any] = _sync_fetch(
            registry, connector_id, connector, request,
            connection_config=connection_config,
        )
        result = _apply_transform_pipeline(result, pipeline)
        if pii_stage is not None:
            try:
                result, _ = pii_stage.process_fetch_result(result)
            except Exception as exc:
                logger.warning(
                    "connector_ingestion: PII scan failed for %s:%s: %s",
                    connector_id,
                    dataset_id,
                    exc,
                )

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
                "completeness": _canon_scalar(result.completeness),
                "schema_id": result.schema_id,
                "schema_version": result.schema_version,
                "version_strategy": result.version.strategy.value,
                "version_value": result.version.value,
                "content_hash": result.version.content_hash,
                "source_updated_at": (
                    result.source_updated_at.isoformat()
                    if result.source_updated_at is not None
                    else None
                ),
                "fetch_duration_ms": _canon_scalar(result.fetch_duration_ms),
                "quality_flags": sorted(str(flag) for flag in result.quality_flags),
                "not_modified": result.not_modified,
                "data_artifact_id": payload_ref.artifact_id.hex if payload_ref else None,
                "pii_max_severity": (
                    result.pii_scan.max_severity if result.pii_scan else None
                ),
                "pii_entities_total": (
                    result.pii_scan.total_entities_found if result.pii_scan else None
                ),
                "pii_sampled": result.pii_scan.sampled if result.pii_scan else None,
                "pii_scan": (
                    result.pii_scan.model_dump(mode="json") if result.pii_scan else None
                ),
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

    dataset_notes = [
        (
            f"{activity['connector_id']}:{activity['dataset_id']} "
            f"rows={activity['row_count']} "
            f"version={activity['version_strategy']}:{activity['version_value']}"
        )
        for activity in fetch_activities
    ]
    evidence_bundle = build_evidence_bundle(
        sources=artifact_refs,
        notes=[
            f"connector_ingestion: {len(spec.datasets)} dataset(s) fetched",
            f"manifest_hash: {manifest_hash}",
            *dataset_notes,
        ],
        provenance_ref=provenance_ref,
    )
    return persist_evidence_bundle(cas_store, evidence_bundle)


__all__ = [
    "ConnectorManifestSpec",
    "DatasetFetchSpec",
    "run_connectors_ingestion",
]
