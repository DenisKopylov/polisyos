"""Connector for GeoJSON feature collections."""

from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any, ClassVar

from polisyos.fabric.connectors.base import (
    BaseConnector,
    ConnectionConfig,
    ConnectionHandle,
    FetchRequest,
    FetchResult,
    HealthStatus,
)
from polisyos.fabric.connectors.contracts import infer_schema
from polisyos.fabric.connectors.sources._file_common import content_version, read_location_bytes
from polisyos.fabric.connectors.types import (
    DatasetDescriptor,
    ValidationIssue,
    ValidationResult,
    ValidationSeverity,
)
from polisyos.ir.connectors import (
    ConnectorCapability,
    ConnectorMetadataSpec,
    QualityTier,
    TrustLevel,
    capabilities_from_flags,
)


def _extract_crs(payload: dict[str, Any]) -> str:
    crs = payload.get("crs")
    if isinstance(crs, dict):
        properties = crs.get("properties")
        if isinstance(properties, dict) and properties.get("name"):
            return str(properties["name"])
    return "EPSG:4326"


class GeoJSONConnector(BaseConnector[Any]):
    """Preserve feature properties plus CRS and geometry lineage from GeoJSON files."""

    namespace: ClassVar[str] = "geojson"
    short_id: ClassVar[str] = "features"
    connector_id: ClassVar[str] = f"{namespace}.{short_id}"
    capabilities: ClassVar[ConnectorCapability] = (
        ConnectorCapability.FULL_FETCH
        | ConnectorCapability.CATALOG_BROWSE
        | ConnectorCapability.SCHEMA_INTROSPECTION
        | ConnectorCapability.PROVENANCE_METADATA
    )
    metadata: ClassVar[ConnectorMetadataSpec] = ConnectorMetadataSpec(
        connector_id=short_id,
        version="1.0.0",
        namespace=namespace,
        source_name="GeoJSON Features",
        source_organization="PolicyOS Fabric",
        source_url="https://polisyos.io/fabric/connectors/geojson",
        trust_level=TrustLevel.MEDIUM,
        quality_tier=QualityTier.SILVER,
        capabilities=capabilities_from_flags(
            ConnectorCapability.FULL_FETCH,
            ConnectorCapability.CATALOG_BROWSE,
            ConnectorCapability.SCHEMA_INTROSPECTION,
            ConnectorCapability.PROVENANCE_METADATA,
        ),
        description="GeoJSON feature connector preserving CRS and geometry metadata.",
    )
    _STATE_KEY: ClassVar[str] = "geojson"

    async def connect(self, config: ConnectionConfig) -> ConnectionHandle:
        validation = self.validate_config(config)
        if not validation.valid:
            issues = "; ".join(issue.message for issue in validation.issues)
            raise ValueError(f"invalid {self.connector_id} config: {issues}")
        handle = self._create_handle(config)
        handle.set_state(self._STATE_KEY, {"schema_by_dataset": {}})
        return handle

    async def disconnect(self, handle: ConnectionHandle) -> None:
        del handle

    async def health_check(self, handle: ConnectionHandle) -> HealthStatus:
        started = time.monotonic()
        try:
            await read_location_bytes(handle.config, prefixes=("X-GeoJSON-",))
            return HealthStatus(
                healthy=True,
                message="geojson readable",
                latency_ms=round((time.monotonic() - started) * 1000, 2),
            )
        except Exception as exc:
            return HealthStatus(healthy=False, message=str(exc))

    async def list_datasets(self, handle: ConnectionHandle) -> AsyncIterator[DatasetDescriptor]:
        yield DatasetDescriptor(
            dataset_id="feature_collection",
            name="feature_collection",
            description=f"GeoJSON data at {handle.config.url}",
            tags=("geojson",),
            metadata={"location": handle.config.url},
        )

    async def fetch(self, handle: ConnectionHandle, request: FetchRequest) -> FetchResult[Any]:
        import pandas as pd

        started = time.monotonic()
        payload_bytes, headers = await read_location_bytes(handle.config, prefixes=("X-GeoJSON-",))
        payload = json.loads(payload_bytes.decode("utf-8"))
        features = list(payload.get("features", []))
        geometry_types: set[str] = set()
        rows: list[dict[str, Any]] = []
        for index, feature in enumerate(features):
            properties = dict(feature.get("properties") or {})
            geometry = dict(feature.get("geometry") or {})
            geometry_type = str(geometry.get("type") or "Unknown")
            geometry_types.add(geometry_type)
            rows.append(
                {
                    "feature_id": feature.get("id", index),
                    **properties,
                    "geometry_type": geometry_type,
                    "geometry": json.dumps(geometry, sort_keys=True),
                }
            )
        frame = pd.DataFrame(rows)
        version = content_version(
            data=payload_bytes,
            etag=headers.get("ETag"),
            last_modified=headers.get("Last-Modified"),
        )
        spatial_metadata = {
            "crs": _extract_crs(payload),
            "geometry_types": tuple(sorted(geometry_types)),
            "feature_count": len(rows),
            "source_location": handle.config.url,
            "content_hash": version.content_hash,
        }
        frame.attrs["spatial_metadata"] = spatial_metadata
        frame.attrs["lineage"] = {
            "source_location": handle.config.url,
            "content_hash": version.content_hash,
        }

        schema_id = f"{self.connector_id}.{request.dataset_id or 'feature_collection'}"
        schema = infer_schema(frame, schema_id=schema_id)
        state = handle.get_state(self._STATE_KEY) or {}
        schema_by_dataset = dict(state.get("schema_by_dataset", {}))
        schema_by_dataset[request.dataset_id or "feature_collection"] = {
            "schema_id": schema.schema_id,
            "version": str(schema.version),
            "fields": [
                {
                    "name": field.name,
                    "data_type": field.data_type.value,
                    "nullable": field.nullable,
                }
                for field in schema.fields
            ],
            "spatial_metadata": {
                "crs": spatial_metadata["crs"],
                "geometry_types": list(spatial_metadata["geometry_types"]),
                "feature_count": spatial_metadata["feature_count"],
            },
            "lineage": {
                "source_location": handle.config.url,
                "content_hash": version.content_hash,
            },
        }
        handle.set_state(self._STATE_KEY, {"schema_by_dataset": schema_by_dataset})

        return FetchResult(
            data=frame,
            row_count=len(frame),
            schema_id=schema_id,
            schema_version="1.0.0",
            version=version,
            fetched_at=datetime.now(UTC),
            completeness=1.0 if rows else 0.0,
            quality_tier=QualityTier.SILVER,
            quality_flags=frozenset({"spatial_metadata_present"}),
            fetch_duration_ms=round((time.monotonic() - started) * 1000, 2),
            bytes_transferred=len(payload_bytes),
        )

    async def get_dataset_schema(
        self,
        handle: ConnectionHandle,
        dataset_id: str,
    ) -> dict[str, Any]:
        state = handle.get_state(self._STATE_KEY) or {}
        schema = dict(state.get("schema_by_dataset", {})).get(dataset_id)
        if schema is not None:
            return dict(schema)
        await self.fetch(handle, FetchRequest(dataset_id=dataset_id))
        state = handle.get_state(self._STATE_KEY) or {}
        schema = dict(state.get("schema_by_dataset", {})).get(dataset_id)
        return dict(schema or {"error": f"schema not available for {dataset_id}"})

    @classmethod
    def validate_config(cls, config: ConnectionConfig) -> ValidationResult:
        issues: list[ValidationIssue] = []
        if not str(config.url).strip():
            issues.append(
                ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    field="url",
                    message="url is required",
                )
            )
        elif not str(config.url).lower().endswith((".geojson", ".json")):
            issues.append(
                ValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    field="url",
                    message="GeoJSON URLs usually end with .geojson or .json",
                )
            )
        return ValidationResult(
            valid=not any(i.severity == ValidationSeverity.ERROR for i in issues),
            issues=tuple(issues),
        )


__all__ = ["GeoJSONConnector"]
