from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from polisyos.core.artifacts.manifest import InputRef, SchemaInfo, WarningRecord
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.core.contracts.fabric import (
    DataSnapshot,
    DataSnapshotRef,
    DataViewRequestRef,
    EvidenceBundleRef,
    WarningsBundle,
    WarningsRef,
)
from polisyos.fabric import fabric_get_data
from polisyos.ir.analytics.data_views import DataViewRequest as AnalyticsDataViewRequest
from polisyos.ir.connectors import FetchResult, QualityTier
from polisyos.ir.queries import DataViewRequest as QueryDataViewRequest
from polisyos.scientist.engine.context import FabricPort


class DefaultFabricPort(FabricPort):
    """Concrete FabricPort adapter for DataViewRequest -> DataSnapshot flows."""

    def snapshot(self, store: FileSystemCAS, request_ref: DataViewRequestRef) -> DataSnapshotRef:
        payload = from_canonical_bytes(store.get_bytes(request_ref.artifact_id))
        query_request = _parse_query_request(payload)

        dataset_id = _resolve_dataset_id(query_request)
        constraints = _build_fetch_constraints(query_request)

        fetch_result = fabric_get_data(
            dataset_id=dataset_id,
            constraints=constraints,
        )
        quality_payload = _build_quality_report_payload(
            result=fetch_result,
            dataset_id=dataset_id,
        )

        data_ref = store.put_json(
            _jsonable(fetch_result.data),
            PutOptions(
                kind="fabric.tabular_payload",
                media_type="application/json",
                schema=SchemaInfo(name="polisyos.fabric.TabularPayload", version="1.0"),
                inputs=[
                    InputRef(artifact_id=request_ref.artifact_id, role="data_view_request_ref"),
                ],
            ),
            canon_spec=CanonSpec(forbid_floats=False),
        )
        schema_ref = store.put_json(
            {
                "schema_id": fetch_result.schema_id,
                "schema_version": fetch_result.schema_version,
            },
            PutOptions(
                kind="fabric.data_schema",
                media_type="application/json",
                schema=SchemaInfo(name="polisyos.fabric.DataSchema", version="1.0"),
            ),
        )
        quality_report_ref = store.put_json(
            quality_payload,
            PutOptions(
                kind="fabric.quality_report",
                media_type="application/json",
                schema=SchemaInfo(name="polisyos.fabric.DataQualityReport", version="1.0"),
            ),
            canon_spec=CanonSpec(forbid_floats=False),
        )

        warnings_ref = _persist_warnings(store, fetch_result)
        evidence_ref = _coerce_evidence_ref(fetch_result)
        pii_scan_summary = (
            fetch_result.pii_scan.model_dump(mode="json")
            if fetch_result.pii_scan is not None
            else None
        )

        snapshot_inputs = [
            InputRef(artifact_id=request_ref.artifact_id, role="data_view_request_ref"),
            InputRef(artifact_id=data_ref.artifact_id, role="data_ref"),
            InputRef(artifact_id=schema_ref.artifact_id, role="data_schema_ref"),
            InputRef(artifact_id=quality_report_ref.artifact_id, role="quality_report_ref"),
        ]
        if evidence_ref is not None:
            snapshot_inputs.append(
                InputRef(artifact_id=evidence_ref.artifact_id, role="evidence_ref")
            )
        if warnings_ref is not None:
            snapshot_inputs.append(
                InputRef(artifact_id=warnings_ref.artifact_id, role="warnings_ref")
            )

        snapshot = DataSnapshot(
            data_ref=data_ref,
            data_schema_ref=schema_ref,
            evidence_ref=evidence_ref,
            quality_report_ref=quality_report_ref,
            warnings_ref=warnings_ref,
            pii_scan_summary=pii_scan_summary,
            stats={
                "dataset_id": dataset_id,
                "row_count": int(fetch_result.row_count),
                "bytes_transferred": int(fetch_result.bytes_transferred),
                "quality_tier": fetch_result.quality_tier.name.lower(),
            },
            notes=[
                "scientist.adapter.fabric_bridge",
                "source=fabric_get_data",
            ],
        )
        snapshot_ref = store.put_json(
            snapshot,
            PutOptions(
                kind="fabric.data_snapshot",
                media_type="application/json",
                schema=SchemaInfo(name="polisyos.core.DataSnapshot", version="0.2.0"),
                inputs=snapshot_inputs,
            ),
            canon_spec=CanonSpec(forbid_floats=False),
        )
        return DataSnapshotRef(artifact_id=snapshot_ref.artifact_id)


def _parse_query_request(payload: Any) -> QueryDataViewRequest | AnalyticsDataViewRequest:
    try:
        return QueryDataViewRequest.model_validate(payload)
    except Exception:
        pass
    return AnalyticsDataViewRequest.model_validate(payload)


def _resolve_dataset_id(request: QueryDataViewRequest | AnalyticsDataViewRequest) -> str:
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
    now = datetime.now(timezone.utc)
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


def _persist_warnings(store: FileSystemCAS, result: FetchResult[Any]) -> WarningsRef | None:
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
    if not warnings:
        return None
    warnings_ref = store.put_json(
        WarningsBundle(warnings=warnings),
        PutOptions(
            kind="fabric.warnings",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.WarningsBundle", version="1.0"),
        ),
    )
    return WarningsRef(artifact_id=warnings_ref.artifact_id)


def _coerce_evidence_ref(result: FetchResult[Any]) -> EvidenceBundleRef | None:
    if result.evidence_ref is None:
        return None
    return EvidenceBundleRef.model_validate(result.evidence_ref.model_dump(mode="json"))


def _jsonable(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return value


__all__ = ["DefaultFabricPort"]
