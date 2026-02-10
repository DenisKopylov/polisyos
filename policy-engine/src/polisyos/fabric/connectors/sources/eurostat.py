from __future__ import annotations

from datetime import datetime, timezone
import json
import time
from typing import Any, AsyncIterator, ClassVar

import pandas as pd

from polisyos.core.canon import content_hash as compute_content_hash
from polisyos.fabric.connectors.base import ConnectionHandle, FetchRequest, FetchResult, HealthStatus
from polisyos.fabric.connectors.sources._contracts.eurostat_contracts import EUROSTAT_GENERIC_SCHEMA
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


class EurostatConnector(HTTPConnectorBase[pd.DataFrame]):
    """Connector for Eurostat JSON Statistics API."""

    namespace: ClassVar[str] = "eurostat"
    short_id: ClassVar[str] = "data"
    connector_id: ClassVar[str] = f"{namespace}.{short_id}"
    _BASE_URL: ClassVar[str] = (
        "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data"
    )
    resilience_profile: ClassVar[HTTPResilienceProfile] = HTTPResilienceProfile(base_delay=1.5)

    capabilities: ClassVar[ConnectorCapability] = (
        ConnectorCapability.FULL_FETCH
        | ConnectorCapability.DATE_RANGE_FILTER
        | ConnectorCapability.DIMENSION_FILTER
        | ConnectorCapability.CATALOG_BROWSE
        | ConnectorCapability.SCHEMA_INTROSPECTION
        | ConnectorCapability.RATE_LIMIT_AWARE
    )

    metadata: ClassVar[ConnectorMetadataSpec] = ConnectorMetadataSpec(
        connector_id=short_id,
        version="1.0.0",
        namespace=namespace,
        source_name="Eurostat Statistics Database",
        source_organization="European Commission - Eurostat",
        source_url="https://ec.europa.eu/eurostat/",
        trust_level=TrustLevel.AUTHORITATIVE,
        quality_tier=QualityTier.GOLD,
        capabilities=capabilities_from_flags(
            ConnectorCapability.FULL_FETCH,
            ConnectorCapability.DATE_RANGE_FILTER,
            ConnectorCapability.DIMENSION_FILTER,
            ConnectorCapability.CATALOG_BROWSE,
            ConnectorCapability.SCHEMA_INTROSPECTION,
            ConnectorCapability.RATE_LIMIT_AWARE,
        ),
    )

    async def health_check(self, handle: ConnectionHandle) -> HealthStatus:
        base_url = self._base_url(handle)
        dataset = handle.config.headers.get("X-EUROSTAT-HEALTH-DATASET", "nama_10_gdp")
        url = f"{base_url}/{dataset}"
        params = {"format": "JSON", "lang": "en"}
        started = time.monotonic()
        try:
            _body, headers, _raw = await self._resilient_request_json(
                handle,
                url,
                params=params,
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
        configured = handle.config.headers.get("X-EUROSTAT-DATASETS", "")
        for raw in configured.split(","):
            dataset_id = raw.strip()
            if not dataset_id:
                continue
            yield DatasetDescriptor(
                dataset_id=dataset_id,
                name=dataset_id,
                description="Configured Eurostat dataset",
                tags=("eurostat", "configured"),
            )

    async def fetch(
        self,
        handle: ConnectionHandle,
        request: FetchRequest,
    ) -> FetchResult[pd.DataFrame]:
        base_url = self._base_url(handle)
        dataset_id = request.dataset_id
        url = f"{base_url}/{dataset_id}"
        params = self._build_params(request)
        started = time.monotonic()

        body, headers, raw = await self._resilient_request_json(
            handle,
            url,
            params=params,
        )
        if not isinstance(body, dict):
            raise FetchError(
                message="Unexpected payload type (expected object)",
                connector_id=self.connector_id,
                request_params={"url": url},
            )

        frame = self._parse_jsonstat(body, dataset_id)
        now = datetime.now(timezone.utc)
        return self._build_fetch_result(
            data=frame,
            row_count=len(frame),
            schema_id=EUROSTAT_GENERIC_SCHEMA.schema_id,
            schema_version=str(EUROSTAT_GENERIC_SCHEMA.version),
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
        return EUROSTAT_GENERIC_SCHEMA.model_dump(mode="python")

    @staticmethod
    def _build_params(request: FetchRequest) -> dict[str, str]:
        params: dict[str, str] = {"format": "JSON", "lang": "en"}
        for key, values in request.filters:
            if values:
                params[key] = ",".join(values)
        if request.date_start is not None and request.date_end is not None and "time" not in params:
            years = [str(year) for year in range(request.date_start.year, request.date_end.year + 1)]
            params["time"] = ",".join(years)
        return params

    @staticmethod
    def _parse_jsonstat(body: dict[str, Any], dataset_id: str) -> pd.DataFrame:
        dim_ids = body.get("id", [])
        dim_sizes = body.get("size", [])
        dimensions = body.get("dimension", {})
        values_any = body.get("value", {})

        if not isinstance(dim_ids, list) or not isinstance(dim_sizes, list):
            return pd.DataFrame(columns=EUROSTAT_GENERIC_SCHEMA.field_names())

        dimension_codes: dict[str, list[str]] = {}
        for dim_id in dim_ids:
            info = dimensions.get(dim_id, {})
            if not isinstance(info, dict):
                info = {}
            dimension_codes[str(dim_id)] = _dimension_codes(info)

        observations: list[tuple[int, Any]] = []
        if isinstance(values_any, dict):
            for key, value in values_any.items():
                try:
                    idx = int(key)
                except (TypeError, ValueError):
                    continue
                observations.append((idx, value))
        elif isinstance(values_any, list):
            observations = list(enumerate(values_any))
        else:
            observations = []

        rows: list[dict[str, Any]] = []
        for idx, raw_value in observations:
            coords = _decode_index(idx, dim_sizes)
            dim_values: dict[str, str] = {}
            for dim_pos, dim_id in enumerate(dim_ids):
                codes = dimension_codes.get(str(dim_id), [])
                coord = coords[dim_pos] if dim_pos < len(coords) else 0
                if 0 <= coord < len(codes):
                    dim_values[str(dim_id)] = codes[coord]
                else:
                    dim_values[str(dim_id)] = str(coord)

            rows.append(
                {
                    "dataset_id": dataset_id,
                    "observation_index": idx,
                    "time_period": dim_values.get("time") or dim_values.get("TIME_PERIOD"),
                    "unit": dim_values.get("unit"),
                    "value": safe_float(raw_value),
                    "dimensions_json": json.dumps(
                        dim_values,
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                }
            )

        if not rows:
            return pd.DataFrame(columns=EUROSTAT_GENERIC_SCHEMA.field_names())
        return pd.DataFrame(rows, columns=EUROSTAT_GENERIC_SCHEMA.field_names())


def _dimension_codes(info: dict[str, Any]) -> list[str]:
    category = info.get("category", {})
    if not isinstance(category, dict):
        return []
    index = category.get("index", {})
    labels = category.get("label", {})

    if isinstance(index, dict):
        ordered_keys = [key for key, _ in sorted(index.items(), key=lambda item: int(item[1]))]
    elif isinstance(index, list):
        ordered_keys = [str(value) for value in index]
    else:
        ordered_keys = []

    if not ordered_keys and isinstance(labels, dict):
        ordered_keys = sorted(str(key) for key in labels)

    resolved: list[str] = []
    for key in ordered_keys:
        if isinstance(labels, dict) and key in labels:
            resolved.append(str(labels[key]))
        else:
            resolved.append(str(key))
    return resolved


def _decode_index(index: int, sizes: list[Any]) -> list[int]:
    if not sizes:
        return []
    coords = [0] * len(sizes)
    remaining = int(index)
    for pos in range(len(sizes) - 1, -1, -1):
        try:
            size = int(sizes[pos])
        except (TypeError, ValueError):
            size = 1
        size = max(size, 1)
        coords[pos] = remaining % size
        remaining //= size
    return coords


__all__ = ["EurostatConnector"]
