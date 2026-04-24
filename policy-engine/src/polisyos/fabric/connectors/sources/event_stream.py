"""Connector for newline-delimited event streams."""

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
    DataChunk,
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


class EventStreamConnector(BaseConnector[Any]):
    """Read newline-delimited JSON messages as a deterministic event stream."""

    namespace: ClassVar[str] = "stream"
    short_id: ClassVar[str] = "jsonl"
    connector_id: ClassVar[str] = f"{namespace}.{short_id}"
    capabilities: ClassVar[ConnectorCapability] = (
        ConnectorCapability.FULL_FETCH
        | ConnectorCapability.STREAMING
        | ConnectorCapability.SCHEMA_INTROSPECTION
        | ConnectorCapability.PROVENANCE_METADATA
    )
    metadata: ClassVar[ConnectorMetadataSpec] = ConnectorMetadataSpec(
        connector_id=short_id,
        version="1.0.0",
        namespace=namespace,
        source_name="JSONL Event Stream",
        source_organization="PolicyOS Fabric",
        source_url="https://polisyos.io/fabric/connectors/stream",
        trust_level=TrustLevel.MEDIUM,
        quality_tier=QualityTier.SILVER,
        capabilities=capabilities_from_flags(
            ConnectorCapability.FULL_FETCH,
            ConnectorCapability.STREAMING,
            ConnectorCapability.SCHEMA_INTROSPECTION,
            ConnectorCapability.PROVENANCE_METADATA,
        ),
        description="Generic connector for newline-delimited event streams and replay logs.",
    )
    _STATE_KEY: ClassVar[str] = "event_stream"

    def _chunk_size(self, config: ConnectionConfig) -> int:
        raw = str(config.headers.get("X-Stream-ChunkSize", "100")).strip() or "100"
        return max(1, int(raw))

    def _topic(self, config: ConnectionConfig) -> str:
        return str(config.headers.get("X-Stream-Topic", "events")).strip() or "events"

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
            await read_location_bytes(handle.config, prefixes=("X-Stream-",))
            return HealthStatus(
                healthy=True,
                message="stream readable",
                latency_ms=round((time.monotonic() - started) * 1000, 2),
            )
        except Exception as exc:
            return HealthStatus(healthy=False, message=str(exc))

    async def list_datasets(self, handle: ConnectionHandle) -> AsyncIterator[DatasetDescriptor]:
        yield DatasetDescriptor(
            dataset_id=self._topic(handle.config),
            name=self._topic(handle.config),
            description=f"Event stream at {handle.config.url}",
            tags=("stream",),
            metadata={"stream_url": handle.config.url},
        )

    async def fetch_stream(
        self,
        handle: ConnectionHandle,
        request: FetchRequest,
    ) -> AsyncIterator[DataChunk[Any]]:
        payload, _headers = await read_location_bytes(handle.config, prefixes=("X-Stream-",))
        chunk_size = self._chunk_size(handle.config)
        messages: list[dict[str, Any]] = []
        for index, line in enumerate(payload.decode("utf-8").splitlines()):
            raw = line.strip()
            if not raw:
                continue
            message = json.loads(raw)
            if not isinstance(message, dict):
                message = {"value": message}
            message.setdefault(
                "_message_id", f"{request.dataset_id or self._topic(handle.config)}:{index}"
            )
            messages.append(message)

        for chunk_index in range(0, len(messages), chunk_size):
            chunk = messages[chunk_index : chunk_index + chunk_size]
            yield DataChunk(
                data=chunk,
                chunk_index=chunk_index // chunk_size,
                row_count=len(chunk),
                bytes_size=len(json.dumps(chunk, sort_keys=True).encode("utf-8")),
                is_first=chunk_index == 0,
                is_last=(chunk_index + chunk_size) >= len(messages),
            )

    async def fetch(self, handle: ConnectionHandle, request: FetchRequest) -> FetchResult[Any]:
        import pandas as pd

        started = time.monotonic()
        payload, headers = await read_location_bytes(handle.config, prefixes=("X-Stream-",))
        messages: list[dict[str, Any]] = []
        async for chunk in self.fetch_stream(handle, request):
            messages.extend(chunk.data)

        schema_token = str(request.dataset_id or self._topic(handle.config)).replace("-", "_")
        schema_id = f"{self.connector_id}.{schema_token}"
        frame = pd.DataFrame(messages)
        inferred = infer_schema(frame, schema_id=schema_id)
        state = handle.get_state(self._STATE_KEY) or {}
        schema_by_dataset = dict(state.get("schema_by_dataset", {}))
        schema_by_dataset[request.dataset_id or self._topic(handle.config)] = {
            "schema_id": inferred.schema_id,
            "version": str(inferred.version),
            "fields": [
                {
                    "name": field.name,
                    "data_type": field.data_type.value,
                    "nullable": field.nullable,
                }
                for field in inferred.fields
            ],
            "stream_url": handle.config.url,
            "subject_or_topic": self._topic(handle.config),
            "message_ids": [msg["_message_id"] for msg in messages[:10]],
        }
        handle.set_state(self._STATE_KEY, {"schema_by_dataset": schema_by_dataset})

        version = content_version(
            data=payload,
            etag=headers.get("ETag"),
            last_modified=headers.get("Last-Modified"),
        )
        return FetchResult(
            data=messages,
            row_count=len(messages),
            schema_id=schema_id,
            schema_version="1.0.0",
            version=version,
            fetched_at=datetime.now(UTC),
            completeness=1.0 if messages else 0.0,
            quality_tier=QualityTier.SILVER,
            quality_flags=frozenset({"stream_source"}),
            fetch_duration_ms=round((time.monotonic() - started) * 1000, 2),
            bytes_transferred=len(payload),
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
        if not str(config.url).lower().endswith((".jsonl", ".ndjson")):
            issues.append(
                ValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    field="url",
                    message="stream connector works best with .jsonl or .ndjson inputs",
                )
            )
        raw_chunk_size = str(config.headers.get("X-Stream-ChunkSize", "100")).strip() or "100"
        if not raw_chunk_size.isdigit():
            issues.append(
                ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    field="headers",
                    message="X-Stream-ChunkSize must be an integer",
                )
            )
        return ValidationResult(
            valid=not any(i.severity == ValidationSeverity.ERROR for i in issues),
            issues=tuple(issues),
        )


__all__ = ["EventStreamConnector"]
