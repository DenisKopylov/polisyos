"""Public fabric ingestion module API."""

from __future__ import annotations

import importlib
import json
import math
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from polisyos.common.async_tools import run_coro_sync
from polisyos.common.logger import get_logger
from polisyos.core.canon import content_hash
from polisyos.core.observability import get_metrics, get_tracer
from polisyos.fabric.connectors.cache.policy import (
    PolicyRegistry,
    SmartExpiryPolicy,
    StaticDataPolicy,
    TTLPolicy,
    VolatileDataPolicy,
)
from polisyos.fabric.connectors.cache.store import ConnectorCacheStore
from polisyos.fabric.connectors.registry import ConnectorRegistry
from polisyos.fabric.data_plane.quarantine import (
    QuarantineRecord,
    persist_quarantine_record,
)
from polisyos.fabric.evidence import (
    build_evidence_bundle,
    persist_evidence_bundle,
    persist_provenance_graph,
)
from polisyos.fabric.ingestion.providers import (
    ArtifactStoreFactory,
    IngestionDependencies,
    resolve_ingestion_dependencies,
)
from polisyos.fabric.observability import FABRIC_TRACE_NAMES
from polisyos.fabric.provenance.core import (
    ActivityType,
    AgentType,
    EntityType,
    ProvenanceActivity,
    ProvenanceAgent,
    ProvenanceCoreGraph,
    ProvenanceEntity,
)
from polisyos.fabric.provenance.lineage import FabricLineageTracker
from polisyos.fabric.tabular import payload_to_dataframe
from polisyos.fabric.temporal import parse_datetime_utc, utc_now
from polisyos.ir.connectors import FetchRequest, FetchResult

if TYPE_CHECKING:
    from collections.abc import Mapping

    from polisyos.core.artifacts.manifest import ArtifactRef
    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.core.contracts.fabric import EvidenceBundleRef
    from polisyos.core.observability import MetricsRegistry, PolicyOSTracer

logger = get_logger(__name__)
TransformPipelineFactory = Callable[[], Any]
_TRANSFORM_PIPELINE_REGISTRY: dict[str, TransformPipelineFactory] = {}


def _require_text(raw: Mapping[str, object], field: str) -> str:
    value = raw.get(field)
    if isinstance(value, str):
        normalized = value.strip()
        if normalized:
            return normalized
    raise ValueError(f"connector manifest field {field!r} must be a non-empty string")


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        normalized = value.strip()
        return normalized or None
    return str(value).strip() or None


def _optional_bool(value: object) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    raise ValueError(f"Expected bool-compatible value, got {value!r}")


def _bool_with_default(value: object, *, default: bool) -> bool:
    parsed = _optional_bool(value)
    return default if parsed is None else parsed


def _coerce_filter_map(value: object) -> dict[str, list[str]]:
    if not isinstance(value, dict):
        return {}
    normalized: dict[str, list[str]] = {}
    for key, raw_values in value.items():
        if not isinstance(key, str):
            continue
        if isinstance(raw_values, list):
            normalized[key] = [str(item) for item in raw_values]
        elif raw_values is not None:
            normalized[key] = [str(raw_values)]
    return normalized


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError(f"Expected integer-compatible value, got {value!r}")
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str):
        normalized = value.strip()
        if normalized:
            return int(normalized)
    raise ValueError(f"Expected integer-compatible value, got {value!r}")


def _load_yaml_document(text: str) -> object:
    yaml_module = importlib.import_module("yaml")
    safe_load = getattr(yaml_module, "safe_load", None)
    if not callable(safe_load):  # pragma: no cover - defensive import contract
        raise RuntimeError("PyYAML safe_load is unavailable")
    return safe_load(text)


def _is_dataframe_like(value: object) -> bool:
    return hasattr(value, "to_dict") and hasattr(value, "columns")


@dataclass(frozen=True, slots=True)
class DatasetFetchSpec:
    """Dataset fetch spec data model."""

    connector_id: str
    dataset_id: str
    filters: dict[str, list[str]] = field(default_factory=dict)
    date_start: str | None = None
    date_end: str | None = None
    retryable: bool | None = None
    page_size: int | None = None

    @classmethod
    def from_mapping(cls, raw: Mapping[str, object]) -> DatasetFetchSpec:
        return cls(
            connector_id=_require_text(raw, "connector_id"),
            dataset_id=_require_text(raw, "dataset_id"),
            filters=_coerce_filter_map(raw.get("filters")),
            date_start=_optional_text(raw.get("date_start")),
            date_end=_optional_text(raw.get("date_end")),
            retryable=_optional_bool(raw.get("retryable")),
            page_size=_optional_int(raw.get("page_size")),
        )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "connector_id": self.connector_id,
            "dataset_id": self.dataset_id,
            "filters": self.filters,
        }
        if self.date_start is not None:
            payload["date_start"] = self.date_start
        if self.date_end is not None:
            payload["date_end"] = self.date_end
        if self.retryable is not None:
            payload["retryable"] = self.retryable
        if self.page_size is not None:
            payload["page_size"] = self.page_size
        return payload


@dataclass(frozen=True, slots=True)
class ConnectorManifestSpec:
    """Connector manifest spec data model."""

    datasets: list[DatasetFetchSpec] = field(default_factory=list)
    transform_dag: str | None = None
    allow_local_transform_dag: bool = False
    cache_policy: str | None = None
    retry_policy: dict[str, Any] | None = None

    @classmethod
    def from_mapping(cls, raw: Mapping[str, object]) -> ConnectorManifestSpec:
        raw_datasets = raw.get("datasets")
        if raw_datasets is None:
            datasets: list[DatasetFetchSpec] = []
        elif isinstance(raw_datasets, list):
            datasets = [
                DatasetFetchSpec.from_mapping(dataset)
                for dataset in raw_datasets
                if isinstance(dataset, dict)
            ]
        else:
            raise ValueError("connector manifest 'datasets' must be a list of mappings")

        retry_policy = raw.get("retry_policy")
        normalized_retry_policy = dict(retry_policy) if isinstance(retry_policy, dict) else None
        return cls(
            datasets=datasets,
            transform_dag=_optional_text(raw.get("transform_dag")),
            allow_local_transform_dag=_bool_with_default(
                raw.get("allow_local_transform_dag"),
                default=False,
            ),
            cache_policy=_optional_text(raw.get("cache_policy")),
            retry_policy=normalized_retry_policy,
        )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "datasets": [dataset.to_dict() for dataset in self.datasets],
            "allow_local_transform_dag": self.allow_local_transform_dag,
        }
        if self.transform_dag is not None:
            payload["transform_dag"] = self.transform_dag
        if self.cache_policy is not None:
            payload["cache_policy"] = self.cache_policy
        if self.retry_policy is not None:
            payload["retry_policy"] = dict(self.retry_policy)
        return payload


def _canon_scalar(value: Any) -> Any:
    """Convert non-canonical scalars (e.g. float) to canonical-friendly values."""
    if isinstance(value, float):
        return str(value)
    return value


def _load_manifest_file(path: Path) -> dict[str, Any]:
    suffix = path.suffix.lower()
    text = path.read_text(encoding="utf-8")
    data = _load_yaml_document(text) if suffix in {".yml", ".yaml"} else json.loads(text)
    if not isinstance(data, dict):
        raise ValueError(f"Connector manifest file must map to a dict: {path}")
    return cast("dict[str, Any]", data)


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
        raise TypeError("connector_manifest must be a dict, Path, str, or ConnectorManifestSpec")

    return ConnectorManifestSpec.from_mapping(raw)


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


def register_transform_pipeline(name: str, builder: TransformPipelineFactory) -> None:
    """Register an allowlisted ingestion transform pipeline."""
    key = str(name or "").strip().lower()
    if not key:
        raise ValueError("transform pipeline name must not be empty")
    _TRANSFORM_PIPELINE_REGISTRY[key] = builder


def _validate_transform_pipeline_instance(pipeline: Any) -> Any:
    from polisyos.fabric.connectors.transform.pipeline import TransformPipeline

    if not isinstance(pipeline, TransformPipeline):
        raise TypeError("transform_dag must produce a TransformPipeline instance")
    return pipeline


def _load_local_transform_pipeline(transform_dag: str) -> Any:
    import importlib.util

    path = Path(transform_dag)
    if not path.exists():
        raise FileNotFoundError(f"transform_dag not found: {transform_dag}")

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
    return _validate_transform_pipeline_instance(pipeline)


def _load_transform_pipeline(
    transform_dag: str | None,
    *,
    allow_local_trust: bool = False,
) -> Any | None:
    if not transform_dag:
        return None

    key = str(transform_dag).strip().lower()
    if key in _TRANSFORM_PIPELINE_REGISTRY:
        return _validate_transform_pipeline_instance(_TRANSFORM_PIPELINE_REGISTRY[key]())

    path = Path(transform_dag)
    if path.exists():
        if not allow_local_trust:
            raise ValueError(
                "Local transform_dag Python loading is disabled by default because it "
                "executes arbitrary code. Register an allowlisted transform pipeline "
                "or set allow_local_transform_dag=true only for trusted local manifests."
            )
        logger.warning(
            "Loading trusted local transform_dag from %s. This executes Python and "
            "should only be enabled for local, trusted manifests.",
            transform_dag,
        )
        return _load_local_transform_pipeline(transform_dag)

    raise ValueError(
        f"Unknown transform_dag '{transform_dag}'. Register it in the transform registry "
        "or provide a trusted local file with allow_local_transform_dag=true."
    )


def _build_identity_transform_pipeline() -> Any:
    from polisyos.fabric.connectors.transform.pipeline import TransformPipeline

    return TransformPipeline()


register_transform_pipeline("identity", _build_identity_transform_pipeline)


def _pipeline_supports_row_isolation(pipeline: Any) -> bool:
    if pipeline is None:
        return False
    try:
        compiled = pipeline.compile()
    except Exception:
        return False
    safe_classes = {
        "NormalizationTransform",
        "ValidationTransform",
        "FilterTransform",
        "CodeHarmonizationTransform",
        "ImputationTransform",
    }
    return all(stage.transform.__class__.__name__ in safe_classes for stage in compiled.stages)


def _persist_quarantine_entry(
    *,
    cas_store: FileSystemCAS | None,
    source: str,
    reason: str,
    severity: str,
    raw_payload: Any,
    schema_version: str | None,
    traceback_class: str | None,
    trace_id: str,
    downstream_impacts: tuple[str, ...],
    context: dict[str, Any],
    input_artifact_ids: list[str] | None = None,
) -> str | None:
    if cas_store is None:
        return None
    ref = persist_quarantine_record(
        cas_store,
        record=QuarantineRecord.new(
            reason=reason,
            severity=severity,
            source=source,
            schema_version=schema_version,
            traceback_class=traceback_class,
            trace_id=trace_id,
            downstream_impacts=downstream_impacts,
            context=context,
        ),
        raw_payload=raw_payload,
        input_artifact_ids=input_artifact_ids or [],
    )
    return str(ref.artifact_id)


def _rows_from_payload(payload: Any) -> tuple[list[Any] | None, str | None, list[str] | None]:
    if _is_dataframe_like(payload):
        rows = cast("Any", payload).to_dict(orient="records")
        columns = [str(col) for col in cast("Any", payload).columns]
        if isinstance(rows, list):
            return rows, "dataframe", columns
    if isinstance(payload, list):
        return list(payload), "records", None
    return None, None, None


def _rows_to_payload(kind: str, rows: list[Any], columns: list[str] | None) -> Any:
    if kind == "dataframe":
        pandas_module = importlib.import_module("pandas")
        return cast("Any", pandas_module).DataFrame(rows, columns=columns)
    return rows


def _non_finite_fields(row: dict[str, Any]) -> list[str]:
    fields: list[str] = []
    for key, value in row.items():
        if isinstance(value, bool) or value is None:
            continue
        if not isinstance(value, (int, float)):
            continue
        numeric = float(value)
        if not math.isfinite(numeric):
            fields.append(str(key))
    return fields


def _sanitize_fetch_result(
    result: FetchResult[Any],
    *,
    connector_id: str,
    dataset_id: str,
    cas_store: FileSystemCAS | None = None,
) -> tuple[FetchResult[Any], list[str], int]:
    rows, payload_kind, columns = _rows_from_payload(result.data)
    if rows is None or payload_kind is None:
        return result, [], 0

    signature_counts = Counter(
        tuple(sorted(str(key) for key in row)) for row in rows if isinstance(row, dict)
    )
    expected_keys = max(
        signature_counts,
        key=lambda item: (signature_counts[item], -len(item), item),
        default=(),
    )

    valid_rows: list[Any] = []
    warnings: list[str] = []
    quarantined = 0
    for index, row in enumerate(rows):
        reason: str | None = None
        context: dict[str, Any] = {"row_index": index}

        if not isinstance(row, dict):
            reason = "poison_row"
            context["message"] = "payload row is not a JSON object"
        elif expected_keys and tuple(sorted(str(key) for key in row)) != expected_keys:
            reason = "invalid_schema_row"
            context["expected_fields"] = list(expected_keys)
            context["actual_fields"] = sorted(str(key) for key in row)
        else:
            non_finite = _non_finite_fields(row)
            if non_finite:
                reason = "non_finite_metric"
                context["fields"] = non_finite

        if reason is None:
            valid_rows.append(row)
            continue

        quarantined += 1
        warning = f"quarantined {connector_id}:{dataset_id} row {index} because of {reason}"
        warnings.append(warning)
        _persist_quarantine_entry(
            cas_store=cas_store,
            source=f"connector.fetch:{connector_id}:{dataset_id}",
            reason=reason,
            severity="error",
            raw_payload=row,
            schema_version=result.schema_version,
            traceback_class=None,
            trace_id=f"{connector_id}:{dataset_id}:row:{index}",
            downstream_impacts=(
                "connector_ingestion",
                "connector_cache",
                "evidence_bundle",
                "data_snapshot",
            ),
            context=context,
        )

    if quarantined == 0:
        return result, [], 0

    total_rows = max(len(rows), 1)
    cleaned_payload = _rows_to_payload(payload_kind, valid_rows, columns)
    updated_quality_flags = frozenset(set(result.quality_flags).union({"quarantine_applied"}))
    cleaned_result = result.model_copy(
        update={
            "data": cleaned_payload,
            "row_count": len(valid_rows),
            "completeness": min(result.completeness, len(valid_rows) / total_rows),
            "quality_flags": updated_quality_flags,
        }
    )
    return cleaned_result, warnings, quarantined


def _apply_transform_pipeline(
    result: FetchResult[Any],
    pipeline: Any | None,
    *,
    connector_id: str,
    dataset_id: str,
    cas_store: FileSystemCAS | None = None,
) -> tuple[FetchResult[Any], ProvenanceCoreGraph | None, list[str], int]:
    if pipeline is None:
        return result, None, [], 0

    df = payload_to_dataframe(result.data)
    if df is None:
        logger.warning("transform_dag skipped (unsupported payload type)")
        return result, None, [], 0

    context = None
    tracker: FabricLineageTracker | None = None
    try:
        from polisyos.fabric.connectors.transform.pipeline import TransformContext

        tracker = FabricLineageTracker(
            graph_id=(
                f"connector_transform_{connector_id}_{dataset_id}_"
                f"{result.version.value or 'noversion'}"
            ),
            metadata={
                "connector_id": connector_id,
                "dataset_id": dataset_id,
                "schema_id": result.schema_id or "",
                "schema_version": result.schema_version or "",
            },
        )
        tracker.register_source_dataset(
            connector_id=connector_id,
            dataset_id=dataset_id,
            fields=[str(column) for column in df.columns],
            schema_id=result.schema_id,
        )
        context = TransformContext(
            metadata={"lineage_tracker": tracker},
        )
    except Exception:
        context = None

    try:
        transform_result = pipeline.apply(df, context=context)
        if transform_result.warnings:
            logger.warning("transform_dag warnings: %s", transform_result.warnings)
        data = transform_result.data
        return (
            result.model_copy(update={"data": data, "row_count": len(data)}),
            tracker.graph if tracker is not None else None,
            list(transform_result.warnings),
            0,
        )
    except Exception as exc:
        if not _pipeline_supports_row_isolation(pipeline):
            raise

        warnings = [
            (
                f"transform_dag row isolation fallback for {connector_id}:{dataset_id} "
                f"after {type(exc).__name__}"
            )
        ]
        good_frames: list[Any] = []
        quarantined = 0
        for index in range(len(df)):
            row_frame = df.iloc[[index]].copy()
            try:
                row_result = pipeline.apply(row_frame, context=context)
                good_frames.append(row_result.data)
            except Exception as row_exc:
                quarantined += 1
                warnings.append(
                    f"quarantined transform row {index} for {connector_id}:{dataset_id} "
                    f"({type(row_exc).__name__})"
                )
                _persist_quarantine_entry(
                    cas_store=cas_store,
                    source=f"connector.transform:{connector_id}:{dataset_id}",
                    reason="transform_error",
                    severity="error",
                    raw_payload=row_frame.to_dict(orient="records"),
                    schema_version=result.schema_version,
                    traceback_class=type(row_exc).__name__,
                    trace_id=f"{connector_id}:{dataset_id}:transform:{index}",
                    downstream_impacts=(
                        "connector_ingestion",
                        "connector_cache",
                        "evidence_bundle",
                        "data_snapshot",
                    ),
                    context={
                        "row_index": index,
                        "message": str(row_exc),
                        "pipeline_stages": [stage.name for stage in pipeline.compile().stages],
                    },
                )

        data = (
            cast("Any", importlib.import_module("pandas")).concat(
                good_frames,
                ignore_index=True,
            )
            if good_frames
            else df.iloc[0:0].copy()
        )
        return (
            result.model_copy(update={"data": data, "row_count": len(data)}),
            tracker.graph if tracker is not None else None,
            warnings,
            quarantined,
        )


def _parse_optional_datetime(value: str | None) -> datetime | None:
    if value is None:
        return None
    return cast("datetime", parse_datetime_utc(value, what="manifest datetime"))


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
                raise ValueError(f"No default_config registered for connector '{connector_id}'")
            config = entry.default_config
        handle = await registry.get_connection(connector_id, config)
        try:
            return await connector.fetch(handle, request)
        finally:
            await registry.release_connection(connector_id, handle)

    return run_coro_sync(_do_fetch())


def _manifest_fingerprint(spec: ConnectorManifestSpec) -> str:
    payload = spec.to_dict()
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return str(content_hash(canonical))


def _build_connector_provenance_graph(
    *,
    datasets: list[dict[str, Any]],
    source: str,
    license_name: str,
    started_at: datetime,
    ended_at: datetime,
    manifest_hash: str,
    transform_lineage_graphs: list[ProvenanceCoreGraph] | None = None,
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
        if ds.get("quarantined_records_count") is not None:
            attributes["quarantined_records_count"] = int(ds["quarantined_records_count"])
        if ds.get("quarantine_sources"):
            attributes["quarantine_sources"] = ",".join(ds["quarantine_sources"])
        if ds.get("quarantine_downstream_impacts"):
            attributes["quarantine_downstream_impacts"] = ",".join(
                ds["quarantine_downstream_impacts"]
            )

        graph.add_entity(
            ProvenanceEntity(
                entity_id=entity_id,
                entity_type=EntityType.DATASET,
                label=f"{ds['connector_id']}:{ds['dataset_id']}",
                created_at=parse_datetime_utc(ds["fetched_at"], what="fetched_at"),
                attributes=attributes,
            )
        )
        graph.add_generation(entity_id, activity_id)

    for lineage_graph in transform_lineage_graphs or ():
        graph.merge(lineage_graph)

    return graph


def run_connectors_ingestion(
    *,
    connector_manifest: dict[str, Any] | Path | str | ConnectorManifestSpec,
    source: str,
    license_name: str,
    cas_root: Path | None = Path(".polisyos/cas"),
    connection_config: Any | None = None,
    registry: ConnectorRegistry | None = None,
    tracer: PolicyOSTracer | None = None,
    metrics: MetricsRegistry | None = None,
    store_factory: ArtifactStoreFactory | None = None,
    dependencies: IngestionDependencies | None = None,
) -> EvidenceBundleRef | None:
    """Canonical connector ingestion entrypoint."""
    spec = _normalize_connector_manifest(connector_manifest)
    if not spec.datasets:
        logger.warning("connector_ingestion: manifest.datasets is empty — nothing to fetch.")
        return None
    resolved_dependencies = dependencies or resolve_ingestion_dependencies(
        registry=registry,
        tracer=tracer,
        metrics=metrics,
        store_factory=store_factory,
        registry_factory=ConnectorRegistry.get_instance,
        tracer_factory=get_tracer,
        metrics_factory=get_metrics,
    )
    with resolved_dependencies.tracer.start_as_current_span(
        FABRIC_TRACE_NAMES["data_plane_ingest"],
        attributes={
            "ingestion.source": source,
            "ingestion.dataset_count": len(spec.datasets),
            "ingestion.has_transform_pipeline": bool(spec.transform_dag),
        },
    ) as span:
        cas_store = (
            resolved_dependencies.store_factory(Path(cas_root)) if cas_root is not None else None
        )
        if cas_store is None:
            logger.warning(
                "connector_ingestion: cas_root is None — evidence will not be persisted."
            )

        cache_registry = _build_cache_registry(spec.cache_policy)
        cache_store = (
            ConnectorCacheStore(
                cas_store,
                cache_registry,
                metrics=resolved_dependencies.metrics,
                tracer=resolved_dependencies.tracer,
            )
            if cas_store
            else None
        )
        pipeline = _load_transform_pipeline(
            spec.transform_dag,
            allow_local_trust=spec.allow_local_transform_dag,
        )
        pii_stage = None
        try:
            from polisyos.fabric.pii import PIIDetectionStage

            pii_stage = PIIDetectionStage.from_env()
        except Exception as exc:
            logger.warning("connector_ingestion: failed to initialize PII stage: %s", exc)
            pii_stage = None

        ingestion_started_at = utc_now()
        artifact_refs: list[ArtifactRef] = []
        fetch_activities: list[dict[str, Any]] = []
        transform_lineage_graphs: list[ProvenanceCoreGraph] = []

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

            connector = resolved_dependencies.registry.get(connector_id)
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
                resolved_dependencies.registry,
                connector_id,
                connector,
                request,
                connection_config=connection_config,
            )
            result, transform_graph, transform_warnings, transform_quarantined = (
                _apply_transform_pipeline(
                    result,
                    pipeline,
                    connector_id=connector_id,
                    dataset_id=dataset_id,
                    cas_store=cas_store,
                )
            )
            if transform_graph is not None:
                transform_lineage_graphs.append(transform_graph)
            if transform_warnings:
                logger.warning(
                    "transform pipeline warnings for %s:%s: %s",
                    connector_id,
                    dataset_id,
                    transform_warnings,
                )
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
            result, quarantine_warnings, fetch_quarantined = _sanitize_fetch_result(
                result,
                connector_id=connector_id,
                dataset_id=dataset_id,
                cas_store=cas_store,
            )
            if quarantine_warnings:
                logger.warning(
                    "connector_ingestion quarantine warnings for %s:%s: %s",
                    connector_id,
                    dataset_id,
                    quarantine_warnings,
                )

            payload_ref: ArtifactRef | None = None
            if cache_store is not None:
                connector_metadata = getattr(connector, "metadata", None)
                metadata = cache_store.put(
                    request,
                    result,
                    connector_id=connector_id,
                    classification=getattr(connector_metadata, "data_classification", None),
                    column_classification=getattr(
                        connector_metadata, "column_classification", None
                    ),
                )
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
                    "pii_max_severity": (result.pii_scan.max_severity if result.pii_scan else None),
                    "pii_entities_total": (
                        result.pii_scan.total_entities_found if result.pii_scan else None
                    ),
                    "pii_sampled": result.pii_scan.sampled if result.pii_scan else None,
                    "pii_scan": (
                        result.pii_scan.model_dump(mode="json") if result.pii_scan else None
                    ),
                    "quarantined_records_count": int(transform_quarantined + fetch_quarantined),
                    "quarantine_sources": tuple(
                        source_name
                        for source_name, count in (
                            (
                                f"connector.transform:{connector_id}:{dataset_id}",
                                transform_quarantined,
                            ),
                            (f"connector.fetch:{connector_id}:{dataset_id}", fetch_quarantined),
                        )
                        if count > 0
                    ),
                    "quarantine_downstream_impacts": tuple(
                        dict.fromkeys(
                            impact_name
                            for impact_names, count in (
                                (("connector_ingestion",), transform_quarantined),
                                (
                                    (
                                        "connector_cache",
                                        "evidence_bundle",
                                        "data_snapshot",
                                    ),
                                    fetch_quarantined,
                                ),
                            )
                            if count > 0
                            for impact_name in impact_names
                        )
                    ),
                }
            )

        ingestion_completed_at = utc_now()
        span.set_attribute("ingestion.completed_dataset_count", len(fetch_activities))

        if getattr(resolved_dependencies.metrics, "record_fabric_lineage_graph", None):
            for graph in transform_lineage_graphs:
                resolved_dependencies.metrics.record_fabric_lineage_graph(
                    graph_id=graph.graph_id,
                    node_count=len(graph.entities) + len(graph.activities) + len(graph.agents),
                    edge_count=len(graph.edges),
                )

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
            transform_lineage_graphs=transform_lineage_graphs,
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
    "IngestionDependencies",
    "resolve_ingestion_dependencies",
    "run_connectors_ingestion",
]
