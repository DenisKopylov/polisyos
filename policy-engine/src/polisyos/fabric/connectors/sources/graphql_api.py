"""Generic GraphQL API connector."""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Any, ClassVar

from polisyos.core.canon import content_hash
from polisyos.fabric.connectors.base import (
    BaseConnector,
    ConnectionConfig,
    ConnectionHandle,
    FetchRequest,
    FetchResult,
    HealthStatus,
)
from polisyos.fabric.connectors.contracts import infer_schema
from polisyos.fabric.connectors.types import ValidationIssue, ValidationResult, ValidationSeverity
from polisyos.fabric.safety import extract_bounded_data_path, validate_data_path
from polisyos.fabric.tabular import payload_to_dataframe
from polisyos.ir.connectors import (
    ConnectorCapability,
    ConnectorMetadataSpec,
    DataVersion,
    QualityTier,
    TrustLevel,
    VersionStrategy,
    capabilities_from_flags,
)


class GraphQLConnector(BaseConnector[Any]):
    """Execute GraphQL documents over HTTP and normalize responses into tabular rows."""

    namespace: ClassVar[str] = "graphql"
    short_id: ClassVar[str] = "api"
    connector_id: ClassVar[str] = f"{namespace}.{short_id}"
    capabilities: ClassVar[ConnectorCapability] = (
        ConnectorCapability.FULL_FETCH
        | ConnectorCapability.CUSTOM_QUERY
        | ConnectorCapability.SCHEMA_INTROSPECTION
        | ConnectorCapability.PROVENANCE_METADATA
    )
    metadata: ClassVar[ConnectorMetadataSpec] = ConnectorMetadataSpec(
        connector_id=short_id,
        version="1.0.0",
        namespace=namespace,
        source_name="GraphQL API",
        source_organization="PolicyOS Fabric",
        source_url="https://polisyos.io/fabric/connectors/graphql",
        trust_level=TrustLevel.MEDIUM,
        quality_tier=QualityTier.SILVER,
        capabilities=capabilities_from_flags(
            ConnectorCapability.FULL_FETCH,
            ConnectorCapability.CUSTOM_QUERY,
            ConnectorCapability.SCHEMA_INTROSPECTION,
            ConnectorCapability.PROVENANCE_METADATA,
        ),
        description="Generic GraphQL API connector with configurable query documents.",
    )
    _STATE_KEY: ClassVar[str] = "graphql_api"

    def _query_document(self, config: ConnectionConfig) -> str:
        query = str(config.headers.get("X-GraphQL-Query", "")).strip()
        if not query:
            raise ValueError("X-GraphQL-Query is required for graphql.api")
        return query

    def _data_path(self, config: ConnectionConfig) -> str:
        return validate_data_path(str(config.headers.get("X-GraphQL-DataPath", "data")).strip())

    def _transport_headers(self, config: ConnectionConfig) -> dict[str, str]:
        headers = {k: v for k, v in config.headers.items() if not k.startswith("X-GraphQL-")}
        headers.setdefault("Content-Type", "application/json")
        if config.auth_method == "bearer":
            token = config.auth_credentials.get("token", "")
            headers["Authorization"] = f"Bearer {token}"
        return headers

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
            await self._post_graphql(handle, query="query { __typename }", variables={})
            return HealthStatus(
                healthy=True,
                message="graphql endpoint reachable",
                latency_ms=round((time.monotonic() - started) * 1000, 2),
            )
        except Exception as exc:
            return HealthStatus(healthy=False, message=str(exc))

    async def _post_graphql(
        self,
        handle: ConnectionHandle,
        *,
        query: str,
        variables: dict[str, Any],
    ) -> tuple[Any, bytes]:
        import aiohttp

        payload = {"query": query, "variables": variables}
        raw = json.dumps(payload, sort_keys=True).encode("utf-8")
        timeout = aiohttp.ClientTimeout(total=handle.config.timeout_seconds)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                handle.config.url,
                headers=self._transport_headers(handle.config),
                data=raw,
            ) as response:
                response.raise_for_status()
                body = await response.read()
        parsed = json.loads(body.decode("utf-8"))
        if parsed.get("errors"):
            raise ValueError(f"graphql errors: {parsed['errors']}")
        return parsed, body

    async def fetch(self, handle: ConnectionHandle, request: FetchRequest) -> FetchResult[Any]:
        import pandas as pd

        started = time.monotonic()
        variables: dict[str, Any] = {key: list(values) if len(values) > 1 else values[0] for key, values in request.filters}
        if request.date_start is not None:
            variables.setdefault("date_start", request.date_start.isoformat())
        if request.date_end is not None:
            variables.setdefault("date_end", request.date_end.isoformat())
        if request.incremental_since is not None:
            variables.setdefault("since", request.incremental_since.value)

        envelope, raw_body = await self._post_graphql(
            handle,
            query=self._query_document(handle.config),
            variables=variables,
        )
        extracted = extract_bounded_data_path(envelope, self._data_path(handle.config))
        if isinstance(extracted, dict):
            rows: list[dict[str, Any]] = [dict(extracted)]
        elif isinstance(extracted, list):
            rows = [dict(item) if isinstance(item, dict) else {"value": item} for item in extracted]
        else:
            rows = [{"value": extracted}]

        frame = payload_to_dataframe(rows)
        if frame is None:
            frame = pd.DataFrame(rows)
        fetched_at = datetime.now(timezone.utc)
        schema_id = f"{self.connector_id}.{request.dataset_id or 'query'}"
        schema = infer_schema(frame, schema_id=schema_id)
        state = handle.get_state(self._STATE_KEY) or {}
        schema_by_dataset = dict(state.get("schema_by_dataset", {}))
        schema_by_dataset[request.dataset_id or "query"] = {
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
            "endpoint": handle.config.url,
            "query_document": self._query_document(handle.config),
            "variables": variables,
        }
        handle.set_state(self._STATE_KEY, {"schema_by_dataset": schema_by_dataset})

        payload_hash = "sha256:" + content_hash(raw_body)
        return FetchResult(
            data=frame,
            row_count=len(rows),
            schema_id=schema_id,
            schema_version="1.0.0",
            version=DataVersion(
                strategy=VersionStrategy.CONTENT_HASH,
                value=payload_hash,
                timestamp=fetched_at,
                content_hash=payload_hash,
            ),
            fetched_at=fetched_at,
            completeness=1.0 if rows else 0.0,
            quality_tier=QualityTier.SILVER,
            quality_flags=frozenset({"graphql"}),
            fetch_duration_ms=round((time.monotonic() - started) * 1000, 2),
            bytes_transferred=len(raw_body),
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
        query = str(config.headers.get("X-GraphQL-Query", "")).strip()
        if not query:
            issues.append(
                ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    field="headers",
                    message="X-GraphQL-Query header is required",
                )
            )
        try:
            validate_data_path(str(config.headers.get("X-GraphQL-DataPath", "data")))
        except Exception as exc:
            issues.append(
                ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    field="headers",
                    message=str(exc),
                )
            )
        return ValidationResult(valid=not issues, issues=tuple(issues))


__all__ = ["GraphQLConnector"]
