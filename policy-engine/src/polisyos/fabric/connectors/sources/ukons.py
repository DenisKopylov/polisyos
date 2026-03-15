from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Any, AsyncIterator, ClassVar, Iterable

import pandas as pd

from polisyos.core.canon import content_hash as compute_content_hash
from polisyos.fabric.connectors.base import (
    ConnectionHandle,
    FetchRequest,
    FetchResult,
    HealthStatus,
)
from polisyos.fabric.connectors.sources._contracts.ukons_contracts import UKONS_GENERIC_SCHEMA
from polisyos.fabric.connectors.sources.http_base import HTTPConnectorBase, HTTPResilienceProfile
from polisyos.fabric.connectors.sources.http_common import frame_completeness, safe_float, safe_int
from polisyos.fabric.connectors.types import DatasetDescriptor, FetchError
from polisyos.ir.connectors import (
    ConnectorCapability,
    ConnectorMetadataSpec,
    QualityTier,
    TrustLevel,
    capabilities_from_flags,
)


class UKONSConnector(HTTPConnectorBase[pd.DataFrame]):
    """Connector for UK ONS API v1."""

    namespace: ClassVar[str] = "ukons"
    short_id: ClassVar[str] = "datasets"
    connector_id: ClassVar[str] = f"{namespace}.{short_id}"
    _BASE_URL: ClassVar[str] = "https://api.ons.gov.uk"
    resilience_profile: ClassVar[HTTPResilienceProfile] = HTTPResilienceProfile(base_delay=1.5)

    capabilities: ClassVar[ConnectorCapability] = (
        ConnectorCapability.FULL_FETCH
        | ConnectorCapability.CATALOG_BROWSE
        | ConnectorCapability.SCHEMA_INTROSPECTION
        | ConnectorCapability.RATE_LIMIT_AWARE
    )

    metadata: ClassVar[ConnectorMetadataSpec] = ConnectorMetadataSpec(
        connector_id=short_id,
        version="1.0.0",
        namespace=namespace,
        source_name="UK Office for National Statistics API",
        source_organization="Office for National Statistics",
        source_url=_BASE_URL,
        trust_level=TrustLevel.AUTHORITATIVE,
        quality_tier=QualityTier.GOLD,
        capabilities=capabilities_from_flags(
            ConnectorCapability.FULL_FETCH,
            ConnectorCapability.CATALOG_BROWSE,
            ConnectorCapability.SCHEMA_INTROSPECTION,
            ConnectorCapability.RATE_LIMIT_AWARE,
        ),
    )

    async def health_check(self, handle: ConnectionHandle) -> HealthStatus:
        base_url = self._base_url(handle)
        url = f"{base_url}/dataset"
        started = time.monotonic()
        try:
            _body, headers, _raw = await self._resilient_request_json(
                handle,
                url,
                params={"limit": "1"},
            )
            return HealthStatus(
                healthy=True,
                message="HTTP 200",
                latency_ms=self._elapsed_ms(started),
                rate_limit_remaining=safe_int(headers.get("X-RateLimit-Remaining")),
            )
        except Exception as exc:
            status_code = getattr(exc, "status_code", None)
            message = f"HTTP {status_code}" if status_code is not None else str(exc)
            return HealthStatus(
                healthy=False,
                message=message,
                latency_ms=self._elapsed_ms(started),
            )

    async def list_datasets(
        self,
        handle: ConnectionHandle,
    ) -> AsyncIterator[DatasetDescriptor]:
        base_url = self._base_url(handle)
        url = f"{base_url}/dataset"
        payload, _headers, _raw = await self._resilient_request_json(
            handle,
            url,
            params={"limit": "50"},
        )
        if not isinstance(payload, dict):
            raise FetchError(
                message="Unexpected payload type (expected object)",
                connector_id=self.connector_id,
                request_params={"url": url},
            )
        for row in _extract_dataset_rows(payload):
            dataset_id = row.get("id")
            if not isinstance(dataset_id, str):
                continue
            yield DatasetDescriptor(
                dataset_id=dataset_id,
                name=str(row.get("title") or dataset_id),
                description=str(row.get("description") or ""),
                tags=("ukons", "ons"),
                metadata={
                    "release": row.get("release"),
                    "links": row.get("links"),
                },
            )

    async def fetch(
        self,
        handle: ConnectionHandle,
        request: FetchRequest,
    ) -> FetchResult[pd.DataFrame]:
        base_url = self._base_url(handle)
        dataset_id = request.dataset_id
        url = f"{base_url}/dataset/{dataset_id}/observations"
        params = self._build_params(request)
        started = time.monotonic()

        payload, headers, raw = await self._resilient_request_json(
            handle,
            url,
            params=params,
        )
        if not isinstance(payload, dict):
            raise FetchError(
                message="Unexpected payload type (expected object)",
                connector_id=self.connector_id,
                request_params={"url": url},
            )
        frame = self._parse_observations(payload, dataset_id)
        now = datetime.now(timezone.utc)
        return self._build_fetch_result(
            data=frame,
            row_count=len(frame),
            schema_id=UKONS_GENERIC_SCHEMA.schema_id,
            schema_version=str(UKONS_GENERIC_SCHEMA.version),
            quality_tier=QualityTier.GOLD,
            bytes_transferred=len(raw),
            completeness=frame_completeness(frame),
            fetched_at=now,
            fetch_duration_ms=self._elapsed_ms(started),
            content_hash=compute_content_hash(raw, prefix=True),
            etag=headers.get("ETag"),
            last_modified=headers.get("Last-Modified"),
        )

    async def get_dataset_schema(
        self,
        handle: ConnectionHandle,
        dataset_id: str,
    ) -> dict[str, Any]:
        del handle, dataset_id
        return UKONS_GENERIC_SCHEMA.model_dump(mode="python")

    @staticmethod
    def _build_params(request: FetchRequest) -> dict[str, str]:
        params: dict[str, str] = {}
        for key, values in request.filters:
            if values:
                params[key] = ",".join(values)
        if request.date_start is not None and request.date_end is not None and "time" not in params:
            params["time"] = f"{request.date_start.date()}/{request.date_end.date()}"
        return params

    @staticmethod
    def _parse_observations(payload: dict[str, Any], dataset_id: str) -> pd.DataFrame:
        rows: list[dict[str, Any]] = []
        observations = payload.get("observations", [])
        iterable: Iterable[Any]
        if isinstance(observations, dict):
            iterable = observations.values()
        elif isinstance(observations, list):
            iterable = observations
        else:
            iterable = ()

        for row in iterable:
            if not isinstance(row, dict):
                continue
            dimensions = _extract_dimensions(row.get("dimensions"))
            rows.append(
                {
                    "dataset_id": dataset_id,
                    "observation": safe_float(row.get("observation")),
                    "time_period": dimensions.get("time") or dimensions.get("Time"),
                    "geography": dimensions.get("geography") or dimensions.get("Geography"),
                    "dimensions_json": json.dumps(
                        dimensions,
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                }
            )

        if not rows:
            return pd.DataFrame(columns=UKONS_GENERIC_SCHEMA.field_names())
        return pd.DataFrame(rows, columns=UKONS_GENERIC_SCHEMA.field_names())


def _extract_dataset_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("items", "datasets", "links"):
        value = payload.get(key)
        if isinstance(value, list):
            return [row for row in value if isinstance(row, dict)]
    return []


def _extract_dimensions(value: Any) -> dict[str, str]:
    if isinstance(value, dict):
        return {str(key): str(raw) for key, raw in value.items() if raw is not None}
    if isinstance(value, list):
        result: dict[str, str] = {}
        for row in value:
            if not isinstance(row, dict):
                continue
            key = row.get("dimension_id") or row.get("id") or row.get("name")
            raw_value = row.get("option_id") or row.get("value") or row.get("label")
            if key is None or raw_value is None:
                continue
            result[str(key)] = str(raw_value)
        return result
    return {}


__all__ = ["UKONSConnector"]
