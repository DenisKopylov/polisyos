"""Connector for object-storage hosted tabular data."""

from __future__ import annotations

from typing import Any, ClassVar
from urllib.parse import urlparse

from polisyos.fabric.connectors.base import ConnectionConfig
from polisyos.fabric.connectors.sources._file_common import parse_file_config
from polisyos.fabric.connectors.sources.file_tabular import FileTabularConnector
from polisyos.fabric.connectors.types import ValidationIssue, ValidationResult, ValidationSeverity
from polisyos.ir.connectors import (
    ConnectorCapability,
    ConnectorMetadataSpec,
    QualityTier,
    TrustLevel,
    capabilities_from_flags,
)


class ObjectStorageConnector(FileTabularConnector):
    """Read tabular objects from S3/GCS/Azure style URIs using the shared file contract."""

    namespace: ClassVar[str] = "object_storage"
    short_id: ClassVar[str] = "blob"
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
        source_name="Cloud Object Storage",
        source_organization="PolicyOS Fabric",
        source_url="https://polisyos.io/fabric/connectors/object-storage",
        trust_level=TrustLevel.MEDIUM,
        quality_tier=QualityTier.SILVER,
        capabilities=capabilities_from_flags(
            ConnectorCapability.FULL_FETCH,
            ConnectorCapability.CATALOG_BROWSE,
            ConnectorCapability.SCHEMA_INTROSPECTION,
            ConnectorCapability.FRESHNESS_CHECK,
            ConnectorCapability.PROVENANCE_METADATA,
        ),
        description="Generic connector for S3, GCS, and Azure Blob style objects.",
    )
    _SUPPORTED_SCHEMES: ClassVar[frozenset[str]] = frozenset(
        {"file", "http", "https", "s3", "gs", "gcs", "az", "azure", "abfs", "adl"}
    )
    _HEADER_PREFIXES: ClassVar[tuple[str, ...]] = ("X-File-", "X-Object-")

    def _object_metadata(self, url: str) -> dict[str, str]:
        parsed = urlparse(str(url))
        provider = parsed.scheme.lower() or "file"
        bucket = parsed.netloc or ""
        object_key = parsed.path.lstrip("/")
        return {
            "provider": provider,
            "bucket": bucket,
            "object_key": object_key,
        }

    def _lineage_metadata(
        self,
        *,
        handle,
        version,
        format_name: str,
    ) -> dict[str, Any]:
        metadata = super()._lineage_metadata(
            handle=handle,
            version=version,
            format_name=format_name,
        )
        metadata.update(self._object_metadata(handle.config.url))
        if getattr(version, "strategy", None) is not None and version.strategy.value == "etag":
            metadata["etag"] = version.value
        return metadata

    def _schema_extras(
        self,
        *,
        handle,
        version,
        format_name: str,
    ) -> dict[str, Any]:
        extras = self._lineage_metadata(
            handle=handle,
            version=version,
            format_name=format_name,
        )
        extras.pop("content_hash", None)
        return extras

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
            return ValidationResult.failure(*issues)

        scheme = urlparse(str(config.url)).scheme.lower()
        if scheme not in cls._SUPPORTED_SCHEMES:
            issues.append(
                ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    field="url",
                    message=f"unsupported object storage scheme {scheme or '<local>'}",
                )
            )
        try:
            parse_file_config(config)
        except Exception as exc:
            issues.append(
                ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    field="headers",
                    message=str(exc),
                )
            )
        return ValidationResult(valid=not issues, issues=tuple(issues))


__all__ = ["ObjectStorageConnector"]
