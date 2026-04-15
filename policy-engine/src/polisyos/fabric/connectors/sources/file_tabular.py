"""Connector for local or remote tabular files."""
from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncIterator, ClassVar
from urllib.parse import urlparse

from polisyos.fabric.connectors.base import (
    BaseConnector,
    ConnectionConfig,
    ConnectionHandle,
    FetchRequest,
    FetchResult,
    HealthStatus,
)
from polisyos.fabric.connectors.sources._file_common import (
    content_version,
    dataframe_from_bytes,
    infer_file_format,
    parse_file_config,
    read_location_bytes,
    schema_dict_from_dataframe,
)
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


def _dataset_name(location: str, fallback: str) -> str:
    parsed = urlparse(location)
    path = parsed.path if parsed.scheme else location
    stem = Path(path).stem or fallback
    return stem.replace(".", "_")


class FileTabularConnector(BaseConnector[Any]):
    """Read CSV, JSONL, Parquet, or Excel payloads from local or remote files."""

    namespace: ClassVar[str] = "files"
    short_id: ClassVar[str] = "tabular"
    connector_id: ClassVar[str] = f"{namespace}.{short_id}"
    capabilities: ClassVar[ConnectorCapability] = (
        ConnectorCapability.FULL_FETCH
        | ConnectorCapability.CATALOG_BROWSE
        | ConnectorCapability.SCHEMA_INTROSPECTION
        | ConnectorCapability.FRESHNESS_CHECK
        | ConnectorCapability.PROVENANCE_METADATA
    )
    metadata: ClassVar[ConnectorMetadataSpec] = ConnectorMetadataSpec(
        connector_id=short_id,
        version="1.0.0",
        namespace=namespace,
        source_name="Tabular Files",
        source_organization="PolicyOS Fabric",
        source_url="https://polisyos.io/fabric/connectors/files",
        trust_level=TrustLevel.MEDIUM,
        quality_tier=QualityTier.SILVER,
        capabilities=capabilities_from_flags(
            ConnectorCapability.FULL_FETCH,
            ConnectorCapability.CATALOG_BROWSE,
            ConnectorCapability.SCHEMA_INTROSPECTION,
            ConnectorCapability.FRESHNESS_CHECK,
            ConnectorCapability.PROVENANCE_METADATA,
        ),
        description="Generic connector for local/remote CSV, JSONL, Parquet, and Excel files.",
    )

    _STATE_KEY: ClassVar[str] = "tabular_file"
    _SUPPORTED_SCHEMES: ClassVar[frozenset[str]] = frozenset({"", "file", "http", "https"})
    _HEADER_PREFIXES: ClassVar[tuple[str, ...]] = ("X-File-",)

    def _lineage_metadata(
        self,
        *,
        handle: ConnectionHandle,
        version,
        format_name: str,
    ) -> dict[str, Any]:
        return {
            "source_location": handle.config.url,
            "format": format_name,
            "content_hash": version.content_hash,
        }

    def _schema_extras(
        self,
        *,
        handle: ConnectionHandle,
        version,
        format_name: str,
    ) -> dict[str, Any]:
        return {
            "source_location": handle.config.url,
            "format": format_name,
        }

    async def connect(self, config: ConnectionConfig) -> ConnectionHandle:
        validation = self.validate_config(config)
        if not validation.valid:
            issues = "; ".join(issue.message for issue in validation.issues)
            raise ValueError(f"invalid {self.connector_id} config: {issues}")
        handle = self._create_handle(config)
        handle.set_state(self._STATE_KEY, {"schema_by_dataset": {}, "version_by_dataset": {}})
        return handle

    async def disconnect(self, handle: ConnectionHandle) -> None:
        del handle

    async def health_check(self, handle: ConnectionHandle) -> HealthStatus:
        started = time.monotonic()
        try:
            await read_location_bytes(handle.config, prefixes=self._HEADER_PREFIXES)
            latency_ms = round((time.monotonic() - started) * 1000, 2)
            return HealthStatus(healthy=True, message="location readable", latency_ms=latency_ms)
        except Exception as exc:
            return HealthStatus(healthy=False, message=str(exc))

    async def list_datasets(self, handle: ConnectionHandle) -> AsyncIterator[DatasetDescriptor]:
        dataset_id = _dataset_name(handle.config.url, "dataset")
        yield DatasetDescriptor(
            dataset_id=dataset_id,
            name=dataset_id,
            description=f"Tabular file at {handle.config.url}",
            tags=("files",),
            metadata={"location": handle.config.url},
        )

    async def fetch(self, handle: ConnectionHandle, request: FetchRequest) -> FetchResult[Any]:
        import pandas as pd

        started = time.monotonic()
        file_opts = parse_file_config(handle.config)
        payload, headers = await read_location_bytes(handle.config, prefixes=self._HEADER_PREFIXES)
        dataset_id = request.dataset_id or _dataset_name(handle.config.url, "dataset")
        frame = dataframe_from_bytes(
            payload,
            location=handle.config.url,
            format_name=file_opts["format"],
            encoding=file_opts["encoding"],
            delimiter=file_opts["delimiter"],
            sheet_name=file_opts["sheet_name"],
        )
        total_rows = len(frame)
        has_more = False
        if request.page_size is not None and total_rows > request.page_size:
            frame = frame.head(request.page_size).reset_index(drop=True)
            has_more = True
        format_name = infer_file_format(handle.config.url, file_opts["format"])
        version = content_version(
            data=payload,
            etag=headers.get("ETag"),
            last_modified=headers.get("Last-Modified"),
        )
        frame.attrs["lineage"] = self._lineage_metadata(
            handle=handle,
            version=version,
            format_name=format_name,
        )

        state = handle.get_state(self._STATE_KEY) or {}
        schema_by_dataset = dict(state.get("schema_by_dataset", {}))
        version_by_dataset = dict(state.get("version_by_dataset", {}))
        schema_by_dataset[dataset_id] = schema_dict_from_dataframe(
            frame,
            schema_id=f"{self.connector_id}.{dataset_id}",
            extras=self._schema_extras(
                handle=handle,
                version=version,
                format_name=format_name,
            ),
        )
        version_by_dataset[dataset_id] = version.model_dump(mode="json")
        handle.set_state(
            self._STATE_KEY,
            {
                "schema_by_dataset": schema_by_dataset,
                "version_by_dataset": version_by_dataset,
            },
        )

        return FetchResult(
            data=frame if isinstance(frame, pd.DataFrame) else pd.DataFrame(frame),
            row_count=len(frame),
            schema_id=f"{self.connector_id}.{dataset_id}",
            schema_version="1.0.0",
            version=version,
            fetched_at=datetime.now(timezone.utc),
            completeness=1.0 if total_rows else 0.0,
            quality_tier=QualityTier.SILVER,
            quality_flags=frozenset({f"format:{format_name}"}),
            has_more=has_more,
            total_count=total_rows,
            fetch_duration_ms=round((time.monotonic() - started) * 1000, 2),
            bytes_transferred=len(payload),
        )

    async def get_dataset_schema(
        self,
        handle: ConnectionHandle,
        dataset_id: str,
    ) -> dict[str, Any]:
        state = handle.get_state(self._STATE_KEY) or {}
        schema_by_dataset = dict(state.get("schema_by_dataset", {}))
        schema = schema_by_dataset.get(dataset_id)
        if schema is not None:
            return dict(schema)
        result = await self.fetch(handle, FetchRequest(dataset_id=dataset_id))
        del result
        state = handle.get_state(self._STATE_KEY) or {}
        schema = dict(state.get("schema_by_dataset", {})).get(dataset_id)
        return dict(schema or {"error": f"schema not available for {dataset_id}"})

    async def check_freshness(
        self,
        handle: ConnectionHandle,
        dataset_id: str,
        cached_version,
    ):
        from polisyos.fabric.connectors.types import FreshnessResult, FreshnessStatus

        payload, headers = await read_location_bytes(handle.config, prefixes=self._HEADER_PREFIXES)
        current = content_version(
            data=payload,
            etag=headers.get("ETag"),
            last_modified=headers.get("Last-Modified"),
        )
        if current.is_newer_than(cached_version):
            return FreshnessResult(
                status=FreshnessStatus.STALE,
                message=f"{dataset_id} changed",
                new_version_available=True,
                new_version_hint=current.value,
            )
        return FreshnessResult(status=FreshnessStatus.FRESH, message=f"{dataset_id} unchanged")

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
        else:
            scheme = urlparse(str(config.url)).scheme.lower()
            if scheme not in cls._SUPPORTED_SCHEMES:
                issues.append(
                    ValidationIssue(
                        severity=ValidationSeverity.ERROR,
                        field="url",
                        message=f"unsupported scheme {scheme or '<local>'} for {cls.connector_id}",
                    )
                )
            try:
                infer_file_format(str(config.url), parse_file_config(config)["format"])
            except Exception as exc:
                issues.append(
                    ValidationIssue(
                        severity=ValidationSeverity.ERROR,
                        field="headers",
                        message=str(exc),
                    )
                )
        return ValidationResult(valid=not issues, issues=tuple(issues))


__all__ = ["FileTabularConnector"]
