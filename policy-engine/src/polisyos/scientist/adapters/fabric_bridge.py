"""Default Fabric port implementation that resolves data-view requests into CAS snapshots."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Protocol, cast, runtime_checkable

from polisyos.common import serialization as common_serialization
from polisyos.common.logger import get_logger
from polisyos.core.artifacts import profile_bound_ref
from polisyos.core.artifacts.manifest import (
    ArtifactRef,
    SchemaInfo,
    WarningRecord,
    input_ref_from_artifact_ref,
)
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.core.canon import CanonSpec
from polisyos.core.contracts.fabric import (
    DataSnapshotOwnerBound,
    DataSnapshotRef,
    DataViewRequestRef,
    EvidenceBundleRef,
    FabricBridgeDataSnapshotLineage,
    WarningsBundle,
    WarningsRef,
)
from polisyos.fabric import fabric_get_data
from polisyos.ir.analytics.data_views import DataViewRequest as AnalyticsDataViewRequest
from polisyos.ir.connectors import FetchResult, QualityTier
from polisyos.ir.model_layer.queries import DataViewRequest as QueryDataViewRequest

if TYPE_CHECKING:
    from collections.abc import Iterable

    from polisyos.core.artifacts.protocol import ArtifactStore
    from polisyos.fabric.api import ConnectorRegistryLike, FederationFetchRequest
    from polisyos.fabric.connectors.sources.sql_query import SQLQueryExecution

logger = get_logger(__name__)


class ExecutionTierViolationError(RuntimeError):
    """Signal that the requested dataset is catalog-only and cannot be auto-executed."""


ExecutionTierViolation = ExecutionTierViolationError


# Minimum tier required for runtime execution.  Datasets below this
# tier are discoverable in the catalog but must not be auto-executed.
_MIN_RUNTIME_EXECUTION_TIER = "fetchable"

_TIER_RANK: dict[str, int] = {
    "transport_ready": 0,
    "fetchable": 1,
    "catalog": 2,
}


class FabricFetchDataFn(Protocol):
    """Call signature used by the Scientist-to-Fabric adapter."""

    def __call__(
        self,
        *,
        dataset_id: str,
        connector_id: str | None = None,
        constraints: dict[str, Any] | None = None,
        registry: ConnectorRegistryLike | None = None,
    ) -> FetchResult[Any]: ...


class _FederatedFabricFetchDataFn(FabricFetchDataFn, Protocol):
    """Optional extended callback; legacy callback protocol stays compatible."""

    def __call__(
        self,
        *,
        dataset_id: str,
        connector_id: str | None = None,
        constraints: dict[str, Any] | None = None,
        registry: ConnectorRegistryLike | None = None,
        federation: FederationFetchRequest | None = None,
    ) -> FetchResult[Any]: ...


class DatasetCatalogStoreLike(Protocol):
    """Read-only catalog surface required for execution-tier checks."""

    def get_dataset(self, dataset_id: str) -> object | None: ...


@runtime_checkable
class ColumnarPayloadLike(Protocol):
    """Payloads that expose a dataframe-style `columns` collection."""

    @property
    def columns(self) -> Iterable[object]: ...


@runtime_checkable
class ModelDumpLike(Protocol):
    """Objects that can serialize themselves into JSON-compatible data."""

    def model_dump(self, *, mode: str) -> object: ...


class DefaultFabricPort:
    """Fetch a Fabric dataset and persist a normalized `DataSnapshot` artifact tree.

    The adapter accepts either query-layer or analytics-layer `DataViewRequest`
    payloads, enforces minimum runtime execution tier, calls `fabric_get_data()`,
    persists data/schema/quality/warnings/evidence artifacts, and returns a
    `DataSnapshotRef` suitable for `BuildDataSnapshotNode`.
    """

    def __init__(
        self,
        *,
        fetch_data: FabricFetchDataFn = fabric_get_data,
        connector_registry: ConnectorRegistryLike | None = None,
        catalog_store: DatasetCatalogStoreLike | None = None,
        federation: FederationFetchRequest | None = None,
        connector_id: str | None = None,
        require_fresh_registered_sql: bool = False,
    ) -> None:
        self._fetch_data = fetch_data
        self._connector_registry = connector_registry
        self._catalog_store = catalog_store
        self._federation = federation
        self._connector_id = connector_id
        self._require_fresh_registered_sql = require_fresh_registered_sql
        if require_fresh_registered_sql and (connector_id is None or connector_registry is None):
            raise ValueError("fresh registered SQL requires an exact connector and registry")
        if require_fresh_registered_sql and federation is not None:
            raise ValueError("fresh registered SQL and federation are mutually exclusive")

    def snapshot(self, store: ArtifactStore, request_ref: DataViewRequestRef) -> DataSnapshotRef:
        """Resolve a request into the ordinary persisted snapshot reference."""
        snapshot_ref, _ = self._snapshot_with_execution(store, request_ref)
        return snapshot_ref

    def _snapshot_with_execution(
        self,
        store: ArtifactStore,
        request_ref: DataViewRequestRef,
        *,
        expected_config_fingerprint: str | None = None,
        expected_dataset_id: str | None = None,
        expected_page_size: int | None = None,
        expected_query: str | None = None,
    ) -> tuple[DataSnapshotRef, SQLQueryExecution | None]:
        """Resolve a request artifact into a persisted `DataSnapshotRef`.

        Raises:
            ExecutionTierViolation: If the dataset is catalog-only and below the
                minimum runtime execution tier.
            ValueError: If the request does not identify a dataset.
        """
        from polisyos.core.artifacts import load_core_json_artifact

        request_ref = profile_bound_ref(store, request_ref)
        payload = load_core_json_artifact(store, request_ref)
        query_request = _parse_query_request(payload)

        if self._require_fresh_registered_sql:
            # The general request-to-constraints conversion discards unsupported
            # operators/scope. Authority-selected SQL must reject that intent.
            try:
                dataset_id, constraints = _admit_federation_query_request(query_request)
            except ValueError as exc:
                raise ValueError("registered_sql_requested_scope_not_executed") from exc
        elif self._federation is None:
            dataset_id = _resolve_dataset_id(query_request)
            constraints = _build_fetch_constraints(query_request)
        else:
            # The explicit opt-in request is admitted as a whole before any
            # legacy fallback, registry tier check or producer callback.
            dataset_id, constraints = _admit_federation_query_request(query_request)

        _enforce_execution_tier(dataset_id, catalog_store=self._catalog_store)

        federation_audit: dict[str, Any] | None = None
        sql_execution: SQLQueryExecution | None = None
        if self._federation is None:
            if self._require_fresh_registered_sql:
                from polisyos.fabric.api import _execute_registered_sql

                sql_execution = _execute_registered_sql(
                    dataset_id=dataset_id,
                    connector_id=cast("str", self._connector_id),
                    constraints=constraints,
                    registry=cast("Any", self._connector_registry),
                    expected_config_fingerprint=expected_config_fingerprint,
                    expected_dataset_id=expected_dataset_id,
                    expected_page_size=expected_page_size,
                    expected_query=expected_query,
                )
                fetch_result = sql_execution.result
            else:
                fetch_result = self._fetch_data(
                    dataset_id=dataset_id,
                    connector_id=self._connector_id,
                    constraints=constraints,
                    registry=self._connector_registry,
                )
        else:
            from polisyos.fabric import (
                freeze_federation_request,
                prepare_federation_core_payload,
                reopen_federated_fetch_result,
                verify_federation_core_payload,
            )

            expected_context = freeze_federation_request(
                dataset_id=dataset_id,
                federation=self._federation,
                constraints=constraints,
                registry=self._connector_registry,
            )
            expected_root = self._federation.output_root
            fetch_federated = cast("_FederatedFabricFetchDataFn", self._fetch_data)
            fetched = fetch_federated(
                dataset_id=dataset_id,
                constraints=constraints,
                registry=self._connector_registry,
                federation=self._federation,
            )
            # This consumer reopens actual selected bytes; caller data/attrs and
            # audit summaries cannot substitute for this second fresh replay.
            fetch_result = reopen_federated_fetch_result(
                fetched, expected_context=expected_context, expected_root=expected_root
            )
            # Admission uses the exact frozen page bound, not result.row_count
            # or unknown-completeness markers. No rows are silently sliced.
            if len(fetch_result.data) > query_request.pagination.limit:
                raise ValueError("Composed capture exceeds the independent query output bound")
            federation_audit = fetch_result.federation_audit.model_dump(mode="json")
            federation_audit["consumer_request_ref"] = request_ref.model_dump(mode="json")
        quality_payload = _build_quality_report_payload(
            result=fetch_result,
            dataset_id=dataset_id,
        )
        if sql_execution is not None:
            # Driver success proves neither source completeness nor freshness.
            # The existing report schema requires a numeric score; zero is a
            # conservative gate value, and the flag retains the unknown reason.
            quality_payload["score"] = 0.0
            quality_payload["tier"] = "unverified"
            quality_payload["grade"] = "F"
            quality_payload["quality_flags"] = sorted(
                {*quality_payload["quality_flags"], "source_completeness_unknown"}
            )
        if federation_audit is not None or sql_execution is not None:
            quality_payload["freshness_status"] = {
                "is_fresh": False,
                "level": "unknown",
                "data_age_seconds": None,
                "message": "Bounded capture does not establish source currentness",
                "fetched_at": fetch_result.fetched_at.isoformat(),
            }
        evidence_ref = _coerce_evidence_ref(fetch_result)

        schema_payload: dict[str, Any] = {
            "schema_id": fetch_result.schema_id,
            "schema_version": fetch_result.schema_version,
        }
        if sql_execution is not None:
            schema_payload["sql_columns"] = [
                {"name": name, "dtype": dtype}
                for name, dtype in zip(sql_execution.columns, sql_execution.dtypes, strict=True)
            ]
        federation_warnings: dict[str, Any] | None = None
        data_payload = _jsonable(fetch_result.data) if federation_audit is None else None
        if sql_execution is not None:
            from polisyos.fabric.api import _require_registered_sql_execution

            _require_registered_sql_execution(sql_execution)
            if not _registered_sql_rows_match(sql_execution.output_json, data_payload):
                raise ValueError("registered_sql_output_binding_not_established")
        data_spec = CanonSpec(forbid_floats=False)
        if federation_audit is not None:
            # Every FED payload is admitted against the actual Core decoder
            # before the first Core publication. Values/status/hash alone are
            # not a semantic round-trip. Null equivalence is R4's, not ours.
            schema_payload["federation_columns"] = federation_audit["columns"]
            data_payload = prepare_federation_core_payload(None, frame=fetch_result.data)
            schema_payload = cast("dict[str, Any]", prepare_federation_core_payload(schema_payload))
            quality_payload = cast(
                "dict[str, Any]", prepare_federation_core_payload(quality_payload)
            )
            warning_bundle = _build_warnings_bundle(fetch_result, federation_audit=federation_audit)
            federation_warnings = cast(
                "dict[str, Any]", prepare_federation_core_payload(warning_bundle)
            )
            data_spec = CanonSpec(forbid_floats=False, exclude_none=False)

        data_ref = store.put_json(
            data_payload,
            ArtifactWriteOptions(
                kind="fabric.tabular_payload",
                media_type="application/json",
                schema=SchemaInfo(name="polisyos.fabric.TabularPayload", version="1.0"),
                inputs=[input_ref_from_artifact_ref(request_ref, role="data_view_request_ref")],
            ),
            canon_spec=data_spec,
            return_selected_profile=True,
        )
        _require_selected_profile(data_ref, "fabric_bridge_data_profile_unverified")
        if sql_execution is not None and not _registered_sql_rows_match(
            sql_execution.output_json, load_core_json_artifact(store, data_ref)
        ):
            raise ValueError("registered_sql_output_binding_not_established")
        if federation_audit is not None:
            verify_federation_core_payload(
                load_core_json_artifact(store, data_ref), data_payload, frame=fetch_result.data
            )
        schema_options = ArtifactWriteOptions(
            kind="fabric.data_schema",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.fabric.DataSchema",
                version="1.1" if sql_execution is not None else "1.0",
            ),
        )
        if federation_audit is None:
            schema_ref = store.put_json(
                schema_payload, schema_options, return_selected_profile=True
            )
        else:
            schema_ref = store.put_json(
                schema_payload, schema_options, canon_spec=data_spec, return_selected_profile=True
            )
        _require_selected_profile(schema_ref, "fabric_bridge_schema_profile_unverified")
        if (
            sql_execution is not None
            and load_core_json_artifact(store, schema_ref) != schema_payload
        ):
            raise ValueError("registered_sql_schema_binding_not_established")
        quality_report_ref = store.put_json(
            quality_payload,
            ArtifactWriteOptions(
                kind="fabric.quality_report",
                media_type="application/json",
                schema=SchemaInfo(
                    name="polisyos.fabric.DataQualityReport",
                    version="1.1" if sql_execution is not None else "1.0",
                ),
            ),
            canon_spec=data_spec,
            return_selected_profile=True,
        )
        _require_selected_profile(
            quality_report_ref,
            "fabric_bridge_quality_report_profile_unverified",
        )

        warnings_ref = _persist_warnings(
            store,
            fetch_result,
            federation_audit=federation_audit,
            prepared_federation_payload=federation_warnings,
        )
        if federation_audit is not None:
            verify_federation_core_payload(
                load_core_json_artifact(store, schema_ref), schema_payload
            )
            verify_federation_core_payload(
                load_core_json_artifact(store, quality_report_ref), quality_payload
            )
            if warnings_ref is None:
                raise ValueError("Federation acquisition audit was not persisted")
            verify_federation_core_payload(
                load_core_json_artifact(store, warnings_ref), federation_warnings
            )
        pii_scan_summary = (
            fetch_result.pii_scan.model_dump(mode="json")
            if fetch_result.pii_scan is not None
            else None
        )

        snapshot_inputs = [
            input_ref_from_artifact_ref(request_ref, role="data_view_request_ref"),
            input_ref_from_artifact_ref(data_ref, role="data_ref"),
            input_ref_from_artifact_ref(schema_ref, role="data_schema_ref"),
            input_ref_from_artifact_ref(quality_report_ref, role="quality_report_ref"),
        ]
        if evidence_ref is not None:
            snapshot_inputs.append(input_ref_from_artifact_ref(evidence_ref, role="evidence_ref"))
        if warnings_ref is not None:
            snapshot_inputs.append(input_ref_from_artifact_ref(warnings_ref, role="warnings_ref"))

        snapshot_stats: dict[str, int | str] = {
            "dataset_id": dataset_id,
            "row_count": int(fetch_result.row_count),
            "bytes_transferred": int(fetch_result.bytes_transferred),
            "quality_tier": fetch_result.quality_tier.name.lower(),
        }
        snapshot_notes = [
            "scientist.adapter.fabric_bridge",
            "source=fabric_get_data",
        ]
        if federation_audit is not None:
            snapshot_notes.remove("source=fabric_get_data")
            snapshot_notes.append("source=federation_receipt_consumer_asserted")
            snapshot_stats["federation_manifest_sha256"] = str(federation_audit["manifest_sha256"])
            snapshot_notes.extend(
                [
                    "federation.assurance=software_derivation_candidate",
                    "federation.leaf_history=consumer_asserted",
                    "federation.currentness=not_established",
                    "federation.capture_scope=captured_rows_only",
                    "federation.query_fulfillment=not_established",
                    f"federation.parent_history={federation_audit['parent_history']}",
                ]
            )
        if sql_execution is not None:
            snapshot_notes.remove("source=fabric_get_data")
            snapshot_notes.extend(
                [
                    "source=registered_sql_candidate",
                    "registered_sql.shape_and_workflow_basis=not_established",
                ]
            )
            snapshot_stats["registered_sql_data_shape_basis"] = "not_established"
            snapshot_stats["registered_sql_workflow_compatibility_basis"] = "not_established"
        elif federation_audit is None:
            semantic_stats, semantic_notes = _collect_snapshot_semantics(fetch_result.data)
            snapshot_stats.update(semantic_stats)
            snapshot_notes.extend(semantic_notes)
        else:
            # Column names establish schema, not dataset shape or workflow
            # suitability. This route has no independently admitted shape basis.
            snapshot_stats["federation_data_shape_basis"] = "not_established"
            snapshot_stats["federation_workflow_compatibility_basis"] = "not_established"
            snapshot_notes.append("federation.shape_and_workflow_basis=not_established")

        snapshot = DataSnapshotOwnerBound(
            data_ref=data_ref,
            data_schema_ref=schema_ref,
            evidence_ref=evidence_ref,
            quality_report_ref=quality_report_ref,
            warnings_ref=warnings_ref,
            pii_scan_summary=pii_scan_summary,
            source_lineage=FabricBridgeDataSnapshotLineage(
                data_view_request_ref=request_ref,
            ),
            stats=snapshot_stats,
            notes=snapshot_notes,
        )
        snapshot_payload: object = snapshot
        if federation_audit is not None:
            snapshot_payload = prepare_federation_core_payload(snapshot)
        snapshot_ref = store.put_json(
            snapshot_payload,
            ArtifactWriteOptions(
                kind="fabric.data_snapshot",
                media_type="application/json",
                schema=SchemaInfo(name="polisyos.core.DataSnapshot", version="0.3.0"),
                inputs=snapshot_inputs,
            ),
            canon_spec=data_spec,
            return_selected_profile=True,
        )
        if federation_audit is not None:
            verify_federation_core_payload(
                load_core_json_artifact(store, snapshot_ref), snapshot_payload
            )
        _require_selected_profile(snapshot_ref, "fabric_bridge_snapshot_profile_unverified")
        if sql_execution is not None:
            _require_registered_sql_execution(sql_execution)
            if not _registered_sql_rows_match(
                sql_execution.output_json, load_core_json_artifact(store, data_ref)
            ):
                raise ValueError("registered_sql_output_binding_not_established")
        return DataSnapshotRef.model_validate(snapshot_ref.model_dump(mode="python")), sql_execution


def _registered_sql_rows_match(observed_json: bytes, value: object) -> bool:
    """Compare decoded JSON without bool/int or null/omitted-key equivalence."""
    try:
        observed = json.loads(observed_json)
        return json.dumps(
            observed, sort_keys=True, separators=(",", ":"), allow_nan=False
        ) == json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError, UnicodeDecodeError):
        return False


def _parse_query_request(
    payload: object,
) -> QueryDataViewRequest | AnalyticsDataViewRequest:
    try:
        return QueryDataViewRequest.model_validate(payload)
    except Exception as exc:
        logger.debug("Ignored exception: %s", exc)
    return AnalyticsDataViewRequest.model_validate(payload)


def _admit_federation_query_request(
    request: QueryDataViewRequest | AnalyticsDataViewRequest,
) -> tuple[str, dict[str, Any]]:
    """Compile the whole supported opt-in profile without a dataset fallback.

    A request ID identifies a request, never a missing dataset metric. Only the
    actual sole nonblank metric selects the dataset for this bounded route.
    """
    if not isinstance(request, QueryDataViewRequest):
        raise ValueError("Federation capture supports the explicit table-query profile only")
    if len(request.metrics) != 1 or not request.metrics[0].strip():
        raise ValueError("Federation capture requires exactly one nonblank explicit metric")
    if (
        request.schema_version != "1.0"
        or request.view_type != "table"
        or request.filters
        or request.aggregation is not None
        or request.access_tier is not None
        or request.scope.jurisdiction is not None
        or request.scope.valid_time is not None
        or request.scope.as_of is not None
        or request.pagination.cursor is not None
    ):
        raise ValueError("Federation capture does not establish this requested query scope")
    return request.metrics[0].strip(), {"page_size": request.pagination.limit}


def _resolve_dataset_id(
    request: QueryDataViewRequest | AnalyticsDataViewRequest,
) -> str:
    metrics = getattr(request, "metrics", []) or []
    for metric in metrics:
        metric_id = str(metric).strip()
        if metric_id:
            return metric_id
    request_id = str(getattr(request, "request_id", "")).strip()
    if request_id:
        return request_id
    raise ValueError("DataViewRequest must define at least one metric or request_id")


def _build_fetch_constraints(
    request: QueryDataViewRequest | AnalyticsDataViewRequest,
) -> dict[str, Any]:
    constraints: dict[str, Any] = {}

    filters: dict[str, list[str]] = {}
    for item in getattr(request, "filters", []) or []:
        column = str(getattr(item, "column", "")).strip()
        op = str(getattr(item, "op", "==")).strip().lower()
        if not column:
            continue
        if op not in {"==", "in"}:
            continue
        value = getattr(item, "value", None)
        if isinstance(value, list):
            values = [str(entry) for entry in value if entry is not None]
        else:
            values = [str(value)] if value is not None else []
        if values:
            filters[column] = sorted(values)

    if filters:
        constraints["filters"] = filters

    if isinstance(request, QueryDataViewRequest):
        valid_time = request.scope.valid_time if request.scope is not None else None
        if valid_time is not None:
            if valid_time.from_:
                constraints["date_start"] = str(valid_time.from_)
            if valid_time.to:
                constraints["date_end"] = str(valid_time.to)
        constraints["page_size"] = int(request.pagination.limit)
    else:
        if request.step_start is not None:
            constraints["date_start"] = str(request.step_start)
        if request.step_end is not None:
            constraints["date_end"] = str(request.step_end)

    return constraints


def _build_quality_report_payload(*, result: FetchResult[Any], dataset_id: str) -> dict[str, Any]:
    now = datetime.now(UTC)
    data_age_seconds: int | None = None
    if result.source_updated_at is not None:
        data_age_seconds = max(
            0,
            int((result.fetched_at - result.source_updated_at).total_seconds()),
        )

    is_fresh = data_age_seconds is None or data_age_seconds <= 14 * 24 * 3600
    freshness_level = "fresh" if is_fresh else "stale"

    severity = "warning"
    if result.quality_tier in {QualityTier.BRONZE, QualityTier.UNVERIFIED}:
        severity = "error"

    violations = [
        {
            "rule_type": "quality_flag",
            "field_name": None,
            "severity": severity,
            "message": str(flag),
            "expected": "none",
            "actual": str(flag),
        }
        for flag in sorted(result.quality_flags)
    ]

    return {
        "dataset_id": dataset_id,
        "schema_id": result.schema_id,
        "score": float(result.completeness),
        "tier": result.quality_tier.name.lower(),
        "grade": _quality_grade(result.quality_tier),
        "freshness_status": {
            "is_fresh": is_fresh,
            "level": freshness_level,
            "data_age_seconds": data_age_seconds,
            "message": (
                "source freshness within threshold"
                if is_fresh
                else "source freshness exceeds strict threshold"
            ),
            "fetched_at": result.fetched_at.isoformat(),
        },
        "violations": violations,
        "validated_at": now.isoformat(),
        "row_count": int(result.row_count),
        "quality_flags": sorted(result.quality_flags),
    }


def _quality_grade(tier: QualityTier) -> str:
    if tier == QualityTier.PLATINUM:
        return "A"
    if tier == QualityTier.GOLD:
        return "B"
    if tier == QualityTier.SILVER:
        return "C"
    if tier == QualityTier.BRONZE:
        return "D"
    return "F"


def _build_warnings_bundle(
    result: FetchResult[Any],
    *,
    federation_audit: dict[str, Any] | None = None,
) -> WarningsBundle | None:
    warnings: list[WarningRecord] = []
    for flag in sorted(result.quality_flags):
        warnings.append(
            WarningRecord(
                code="fabric.quality_flag",
                msg=str(flag),
            )
        )
    if result.not_modified:
        warnings.append(
            WarningRecord(
                code="fabric.not_modified",
                msg="Source responded with not_modified",
            )
        )
    if federation_audit is not None:
        warnings.append(
            WarningRecord(
                code="fabric.federation.candidate_derivation",
                msg="Selected software replay; source history and currentness remain unknown",
                data=federation_audit,
            )
        )
    if not warnings:
        return None
    return WarningsBundle(warnings=warnings)


def _persist_warnings(
    store: ArtifactStore,
    result: FetchResult[Any],
    *,
    federation_audit: dict[str, Any] | None = None,
    prepared_federation_payload: dict[str, Any] | None = None,
) -> WarningsRef | None:
    payload: object = (
        prepared_federation_payload
        if federation_audit is not None
        else _build_warnings_bundle(result)
    )
    if payload is None:
        return None
    options = ArtifactWriteOptions(
        kind="fabric.warnings",
        media_type="application/json",
        schema=SchemaInfo(name="polisyos.core.WarningsBundle", version="1.0"),
    )
    if federation_audit is None:
        # Preserve the existing default store/canonical profile exactly.
        warnings_ref = store.put_json(payload, options, return_selected_profile=True)
    else:
        # Reported quality/transfer observations include finite numeric fields;
        # use the same supported Core float profile as data and quality writes.
        warnings_ref = store.put_json(
            payload,
            options,
            canon_spec=CanonSpec(forbid_floats=False, exclude_none=False),
            return_selected_profile=True,
        )
    _require_selected_profile(warnings_ref, "fabric_bridge_warnings_profile_unverified")
    return WarningsRef.model_validate(warnings_ref.model_dump(mode="python"))


def _coerce_evidence_ref(result: FetchResult[Any]) -> EvidenceBundleRef | None:
    if result.evidence_ref is None:
        return None
    evidence_ref = EvidenceBundleRef.model_validate(result.evidence_ref.model_dump(mode="json"))
    _require_selected_profile(evidence_ref, "fabric_bridge_evidence_profile_unverified")
    return evidence_ref


def _require_selected_profile(ref: ArtifactRef, error_code: str) -> None:
    if ref.manifest_profile_sha256 is None:
        raise ValueError(error_code)


def _collect_snapshot_semantics(data: object) -> tuple[dict[str, str], list[str]]:
    fields = _payload_field_names(data)
    if not fields:
        return {}, []

    stats: dict[str, str] = {}
    notes: list[str] = []

    survey_year_field = _first_field(fields, "survey_year", "SurveyYear")
    wave_field = _first_field(fields, "wave", "Wave")
    sample_weight_field = _first_field(
        fields,
        "sample_weight",
        "sample_weights",
        "weight",
        "weights",
    )
    inclusion_prob_field = _first_field(
        fields,
        "inclusion_probabilities",
        "inclusion_probability",
        "sampling_probability",
    )

    if survey_year_field or wave_field:
        stats["data_shape"] = "survey_repeated_cross_section"
        notes.append("data_shape=survey_repeated_cross_section")
        notes.append("allowed_workflows=transport,survey,hte,repeated_cross_section")
        notes.append("blocked_workflows=panel_scm,panel_did,panel_econometrics")

    if survey_year_field:
        stats["survey_year_field"] = survey_year_field
    if wave_field:
        stats["wave_field"] = wave_field
    if sample_weight_field:
        stats["sample_weight_field"] = sample_weight_field
    if inclusion_prob_field:
        stats["inclusion_probabilities_field"] = inclusion_prob_field

    return stats, notes


def _payload_field_names(data: object) -> set[str]:
    if data is None:
        return set()
    if isinstance(data, ColumnarPayloadLike):
        try:
            return {str(column) for column in list(data.columns)}
        except Exception:
            logger.debug("Failed to inspect payload columns", exc_info=True)
    if isinstance(data, list):
        fields: set[str] = set()
        for row in data[:5]:
            if isinstance(row, dict):
                fields.update(str(key) for key in row)
        return fields
    if isinstance(data, dict):
        fields = {str(key) for key in data}
        for nested_key in ("value", "data", "items", "results", "records"):
            nested = data.get(nested_key)
            if isinstance(nested, list):
                for row in nested[:5]:
                    if isinstance(row, dict):
                        fields.update(str(key) for key in row)
                break
        return fields
    return set()


def _first_field(fields: set[str], *candidates: str) -> str | None:
    for candidate in candidates:
        if candidate in fields:
            return candidate
    return None


def _columnar_records(value: ColumnarPayloadLike) -> list[dict[str, Any]]:
    """Convert only known table APIs to rows without guessing object semantics."""
    import pandas as pd
    import pyarrow as pa

    if isinstance(value, pd.DataFrame):
        columns = list(value.columns)
        records = value.to_dict(orient="records")
    elif isinstance(value, pa.Table):
        columns = list(value.column_names)
        records = value.to_pylist()
    else:
        raise TypeError("unsupported columnar payload type")

    if any(not isinstance(column, str) for column in columns):
        raise TypeError("columnar payload column names must be strings")
    if len(columns) != len(set(columns)):
        raise ValueError("columnar payload has duplicate column names")
    if not isinstance(records, list):
        raise TypeError("columnar records conversion must return a list")
    for index, row in enumerate(records):
        if not isinstance(row, dict) or list(row) != columns:
            raise ValueError(f"columnar row {index} does not preserve the declared column schema")
    return records


def _jsonable(value: object) -> object:
    if isinstance(value, ModelDumpLike):
        value = value.model_dump(mode="json")
    elif isinstance(value, ColumnarPayloadLike):
        value = _columnar_records(value)
    return common_serialization.to_python_data(value, unsupported="error")


def _enforce_execution_tier(
    dataset_id: str,
    *,
    catalog_store: DatasetCatalogStoreLike | None = None,
) -> None:
    """Check that *dataset_id* meets the minimum execution tier.

    The check is best-effort: if the catalog is unavailable or the dataset
    is not found (e.g. connector-resolved at runtime), execution proceeds
    with a warning rather than a hard block.
    """
    try:
        if catalog_store is None:
            return
        catalog = catalog_store
        if catalog is None:
            return
        dataset = catalog.get_dataset(dataset_id)
        if dataset is None:
            # Dataset resolved via connector, not in catalog — allow.
            return
        tier = str(getattr(dataset, "execution_tier", "catalog") or "catalog")
        min_rank = _TIER_RANK.get(_MIN_RUNTIME_EXECUTION_TIER, 1)
        actual_rank = _TIER_RANK.get(tier, 2)
        if actual_rank > min_rank:
            raise ExecutionTierViolationError(
                f"Dataset '{dataset_id}' has execution_tier='{tier}' which is "
                f"below the minimum runtime tier '{_MIN_RUNTIME_EXECUTION_TIER}'. "
                f"Catalog-only datasets are discoverable but not auto-executable. "
                f"Promote the dataset to '{_MIN_RUNTIME_EXECUTION_TIER}' or higher "
                f"before using it in a workflow."
            )
    except ExecutionTierViolationError:
        raise
    except Exception as exc:
        logger.debug("Execution tier check skipped for '%s': %s", dataset_id, exc)


__all__ = ["DefaultFabricPort", "ExecutionTierViolation"]
