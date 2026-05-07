"""Eurostat connector implementation for REST JSON, SDMX, and async bulk workflows."""

from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any, ClassVar

import pandas as pd
from defusedxml import ElementTree as ET

from polisyos.core.canon import content_hash as compute_content_hash
from polisyos.fabric.connectors.base import (
    AsyncFetchLease,
    ConnectionHandle,
    DatasetCapabilitySnapshot,
    FetchRequest,
    FetchResult,
    HealthStatus,
)
from polisyos.fabric.connectors.sources._contracts.eurostat_contracts import EUROSTAT_GENERIC_SCHEMA
from polisyos.fabric.connectors.sources.http_base import HTTPConnectorBase, HTTPResilienceProfile
from polisyos.fabric.connectors.sources.http_common import (
    frame_completeness,
    retry_after_seconds,
    safe_float,
    safe_int,
)
from polisyos.fabric.connectors.types import DatasetDescriptor, FetchError, RateLimitError
from polisyos.fabric.quality.safety import safe_path_segment
from polisyos.ir.connectors import (
    ConnectorCapability,
    ConnectorMetadataSpec,
    QualityTier,
    TrustLevel,
    capabilities_from_flags,
)


class EurostatConnector(HTTPConnectorBase[pd.DataFrame]):
    """Connector for Eurostat public statistics via REST JSON and SDMX.

    Supports synchronous JSON fetches for core queries and profile-driven bulk
    or async retrieval for larger Eurostat workloads.

    Data source:
        https://ec.europa.eu/eurostat
    Protocol:
        REST JSON, SDMX 2.1, bulk export
    Auth:
        None
    Async support:
        Yes, including ``fetch_async()`` and dataset description helpers
    Profile:
        ``eurostat_public``
    """

    namespace: ClassVar[str] = "eurostat"
    short_id: ClassVar[str] = "data"
    connector_id: ClassVar[str] = f"{namespace}.{short_id}"
    _BASE_URL: ClassVar[str] = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data"
    _SDMX_BASE_URL: ClassVar[str] = "https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1"
    _ASYNC_BASE_URL: ClassVar[str] = "https://ec.europa.eu/eurostat/api/dissemination/1.0/async"
    resilience_profile: ClassVar[HTTPResilienceProfile] = HTTPResilienceProfile(
        base_delay=1.5,
        max_response_bytes=50 * 1024 * 1024,
        max_json_bytes=20 * 1024 * 1024,
        max_decompressed_bytes=200 * 1024 * 1024,
        max_rows=500_000,
    )

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
        dataset = safe_path_segment(
            handle.config.headers.get("X-EUROSTAT-HEALTH-DATASET", "nama_10_gdp"),
            what="Eurostat dataset id",
        )
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
        dataset_segment = safe_path_segment(dataset_id, what="Eurostat dataset id")
        url = f"{base_url}/{dataset_segment}"
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
        now = datetime.now(UTC)
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

    async def describe_dataset(
        self,
        handle: ConnectionHandle,
        dataset_id: str,
    ) -> DatasetCapabilitySnapshot:
        session = await self._get_session(handle)
        base = handle.config.headers.get("X-EUROSTAT-SDMX-BASE-URL", self._SDMX_BASE_URL).rstrip(
            "/"
        )
        dataset_segment = safe_path_segment(dataset_id, what="Eurostat dataset id")
        url = f"{base}/structure/dataflow/ESTAT/{dataset_segment}"
        params = {"references": "descendants", "detail": "referencepartial"}
        body, _headers, raw = await self._request_json(
            session,
            url,
            params=params,
            connector_id=self.connector_id,
            headers={"Accept": "application/vnd.sdmx.structure+json;version=1.0"},
        )
        dimension_order = tuple(self._extract_structure_dimension_order(body))
        allowed_positions = self._extract_constraint_positions(body)
        constraint_hash = compute_content_hash(raw, prefix=True)
        return DatasetCapabilitySnapshot(
            source=self.namespace,
            dataset_id=dataset_id,
            resolved_dataset_id=dataset_id,
            preferred_transport="dual",
            dimension_order=dimension_order,
            allowed_positions=allowed_positions,
            availability_hash=constraint_hash,
            constraint_hash=constraint_hash,
            estimated_cardinality=self._estimate_constraint_cardinality(allowed_positions),
            version_hint=self._extract_dataflow_version(body, dataset_id),
            last_checked_at=datetime.now(UTC),
        )

    async def fetch_async(
        self,
        handle: ConnectionHandle,
        request: FetchRequest,
    ) -> AsyncFetchLease:
        session = await self._get_session(handle)
        snapshot = await self.describe_dataset(handle, request.dataset_id)
        url, params = self._build_async_request(handle, request, snapshot=snapshot)
        raw, headers = await self._request_raw(
            session,
            url,
            params=params,
            connector_id=self.connector_id,
        )
        lease = self._parse_async_submission_response(
            raw,
            dataset_id=request.dataset_id,
            request_key=self._request_key(request),
            async_base=self._async_base_url(handle),
        )
        if lease is None:
            raise FetchError(
                message="Expected asynchronous Eurostat extraction response",
                connector_id=self.connector_id,
                dataset_id=request.dataset_id,
                request_params={"url": url, "headers": headers},
            )
        return lease

    async def poll_async_fetch(
        self,
        handle: ConnectionHandle,
        lease: AsyncFetchLease,
    ) -> AsyncFetchLease | FetchResult[pd.DataFrame]:
        session = await self._get_session(handle)
        raw, _headers = await self._request_raw(
            session,
            lease.status_url or f"{self._async_base_url(handle)}/status/{lease.lease_id}",
            params={},
            connector_id=self.connector_id,
        )
        status = self._parse_async_status_response(raw)
        if status is None:
            fault = self._parse_async_fault(raw)
            if fault:
                raise FetchError(
                    message=fault,
                    connector_id=self.connector_id,
                    dataset_id=lease.dataset_id,
                    request_params={"lease_id": lease.lease_id},
                )
            raise FetchError(
                message="Unexpected Eurostat async status response",
                connector_id=self.connector_id,
                dataset_id=lease.dataset_id,
                request_params={"lease_id": lease.lease_id},
            )

        key, current_status = status
        normalized = current_status.lower()
        if normalized in {"submitted", "processing"}:
            return lease.model_copy(
                update={
                    "lease_id": key or lease.lease_id,
                    "status": normalized,
                    "poll_after_seconds": max(float(lease.poll_after_seconds or 5.0), 5.0),
                }
            )
        if normalized in {"expired", "unknown_request", "error"}:
            raise FetchError(
                message=f"Eurostat async request {normalized}",
                connector_id=self.connector_id,
                dataset_id=lease.dataset_id,
                request_params={"lease_id": key or lease.lease_id},
            )

        data_raw, data_headers = await self._request_raw(
            session,
            lease.download_url or f"{self._async_base_url(handle)}/data/{lease.lease_id}",
            params={},
            connector_id=self.connector_id,
        )
        fault = self._parse_async_fault(data_raw)
        if fault:
            if "DATA_NOT_YET_AVAILABLE" in fault:
                return lease.model_copy(update={"status": "processing"})
            if "NO_RESULTS" in fault:
                frame = pd.DataFrame(columns=EUROSTAT_GENERIC_SCHEMA.field_names())
                now = datetime.now(UTC)
                return self._build_fetch_result(
                    data=frame,
                    row_count=0,
                    schema_id=EUROSTAT_GENERIC_SCHEMA.schema_id,
                    schema_version=str(EUROSTAT_GENERIC_SCHEMA.version),
                    quality_tier=QualityTier.GOLD,
                    bytes_transferred=len(data_raw),
                    completeness=1.0,
                    fetched_at=now,
                    fetch_duration_ms=0.0,
                    content_hash=compute_content_hash(data_raw, prefix=True),
                    etag=data_headers.get("ETag"),
                    last_modified=data_headers.get("Last-Modified"),
                )
            raise FetchError(
                message=fault,
                connector_id=self.connector_id,
                dataset_id=lease.dataset_id,
                request_params={"lease_id": lease.lease_id},
            )

        try:
            body = json.loads(data_raw)
        except json.JSONDecodeError as exc:
            raise FetchError(
                message=f"Invalid Eurostat async JSON payload: {exc}",
                connector_id=self.connector_id,
                dataset_id=lease.dataset_id,
                request_params={"lease_id": lease.lease_id},
            ) from exc
        if not isinstance(body, dict):
            raise FetchError(
                message="Unexpected Eurostat async payload type",
                connector_id=self.connector_id,
                dataset_id=lease.dataset_id,
                request_params={"lease_id": lease.lease_id},
            )
        frame = self._parse_jsonstat(body, lease.dataset_id)
        now = datetime.now(UTC)
        return self._build_fetch_result(
            data=frame,
            row_count=len(frame),
            schema_id=EUROSTAT_GENERIC_SCHEMA.schema_id,
            schema_version=str(EUROSTAT_GENERIC_SCHEMA.version),
            quality_tier=QualityTier.GOLD,
            bytes_transferred=len(data_raw),
            completeness=frame_completeness(frame),
            fetched_at=now,
            fetch_duration_ms=0.0,
            content_hash=compute_content_hash(data_raw, prefix=True),
            etag=data_headers.get("ETag"),
            last_modified=data_headers.get("Last-Modified"),
        )

    @staticmethod
    def _build_params(request: FetchRequest) -> dict[str, str]:
        params: dict[str, str] = {"format": "JSON", "lang": "en"}
        for key, values in request.filters:
            if values:
                params[key] = ",".join(values)
        if (
            request.date_start is not None
            and "time" not in params
            and "sinceTimePeriod" not in params
        ):
            params["sinceTimePeriod"] = str(request.date_start.year)
        if (
            request.date_end is not None
            and "time" not in params
            and "untilTimePeriod" not in params
        ):
            params["untilTimePeriod"] = str(request.date_end.year)
        return params

    @staticmethod
    def _request_key(request: FetchRequest) -> str:
        payload = {
            "dataset_id": request.dataset_id,
            "filters": list(request.filters),
            "date_start": request.date_start.isoformat() if request.date_start is not None else "",
            "date_end": request.date_end.isoformat() if request.date_end is not None else "",
        }
        return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    def _async_base_url(self, handle: ConnectionHandle) -> str:
        return handle.config.headers.get("X-EUROSTAT-ASYNC-BASE-URL", self._ASYNC_BASE_URL).rstrip(
            "/"
        )

    def _sdmx_base_url(self, handle: ConnectionHandle) -> str:
        return handle.config.headers.get("X-EUROSTAT-SDMX-BASE-URL", self._SDMX_BASE_URL).rstrip(
            "/"
        )

    def _build_async_request(
        self,
        handle: ConnectionHandle,
        request: FetchRequest,
        *,
        snapshot: DatasetCapabilitySnapshot,
    ) -> tuple[str, dict[str, str]]:
        key = self._build_sdmx_key(request, snapshot=snapshot)
        base = self._sdmx_base_url(handle)
        dataset_segment = safe_path_segment(request.dataset_id, what="Eurostat dataset id")
        url = f"{base}/data/{dataset_segment}"
        if key:
            url = f"{url}/{key}"
        params = {"format": "JSON"}
        if request.date_start is not None and "time" not in dict(request.filters):
            params["startPeriod"] = request.date_start.strftime("%Y-%m-%d")
        if request.date_end is not None and "time" not in dict(request.filters):
            params["endPeriod"] = request.date_end.strftime("%Y-%m-%d")
        return url, params

    @staticmethod
    def _build_sdmx_key(
        request: FetchRequest,
        *,
        snapshot: DatasetCapabilitySnapshot,
    ) -> str:
        filter_map = {
            str(key): tuple(str(value) for value in values if str(value).strip())
            for key, values in request.filters
        }
        dimension_order = tuple(snapshot.dimension_order or tuple(filter_map.keys()))
        segments: list[str] = []
        for dimension in dimension_order:
            values = (
                filter_map.get(dimension)
                or filter_map.get(dimension.lower())
                or filter_map.get(dimension.upper())
            )
            segments.append(
                "+".join(
                    safe_path_segment(value, what=f"Eurostat dimension '{dimension}'")
                    for value in values
                )
                if values
                else ""
            )
        while segments and segments[-1] == "":
            segments.pop()
        return ".".join(segments)

    async def _request_raw(
        self,
        session: Any,
        url: str,
        *,
        params: dict[str, str],
        connector_id: str,
        headers: dict[str, str] | None = None,
    ) -> tuple[bytes, dict[str, str]]:
        async with session.get(url, params=params, headers=headers) as response:
            response_headers = dict(response.headers)
            if response.status == 429:
                retry_after = retry_after_seconds(response_headers)
                raise RateLimitError(
                    connector_id=connector_id,
                    retry_after=int(retry_after) if retry_after is not None else None,
                    limit_remaining=safe_int(response_headers.get("X-RateLimit-Remaining")) or 0,
                )
            if response.status >= 400:
                error = FetchError(
                    message=f"HTTP {response.status}",
                    connector_id=connector_id,
                    request_params={"url": url, "status": response.status},
                )
                error.status_code = response.status  # type: ignore[attr-defined]
                raise error
            raw = await self._read_response_body(
                response,
                connector_id=connector_id,
                url=url,
                max_response_bytes=self.resilience_profile.max_response_bytes,
                max_decompressed_bytes=self.resilience_profile.max_decompressed_bytes,
            )
            return raw, response_headers

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

    @staticmethod
    def _extract_dataflow_version(body: dict[str, Any], dataset_id: str) -> str | None:
        structure = body.get("structure", body)
        dataflows = structure.get("dataflows") or structure.get("dataflow") or []
        if isinstance(dataflows, dict):
            dataflows = [dataflows]
        for entry in dataflows if isinstance(dataflows, list) else []:
            if not isinstance(entry, dict):
                continue
            if str(entry.get("id") or "") == dataset_id:
                version = str(entry.get("version") or "").strip()
                return version or None
        return None

    @staticmethod
    def _extract_structure_dimension_order(body: dict[str, Any]) -> list[str]:
        structure = body.get("structure", body)
        data_structures = structure.get("dataStructures") or structure.get("dataStructure") or []
        if isinstance(data_structures, dict):
            data_structures = [data_structures]
        for entry in data_structures if isinstance(data_structures, list) else []:
            if not isinstance(entry, dict):
                continue
            components = (
                entry.get("dataStructureComponents")
                or entry.get("dataStructureDefinition")
                or entry.get("components")
                or {}
            )
            dimensions = components.get("dimensionList") or components.get("dimensions") or {}
            values = dimensions.get("dimensions") or dimensions.get("dimension") or dimensions
            if isinstance(values, list):
                names = [
                    str(dim.get("id") or "").strip() for dim in values if isinstance(dim, dict)
                ]
                names = [name for name in names if name]
                if names:
                    return names
        return []

    @staticmethod
    def _extract_constraint_positions(body: dict[str, Any]) -> dict[str, list[str]]:
        structure = body.get("structure", body)
        constraints = structure.get("contentConstraints") or structure.get("constraints") or []
        if isinstance(constraints, dict):
            constraints = [constraints]
        allowed: dict[str, set[str]] = {}
        for entry in constraints if isinstance(constraints, list) else []:
            if not isinstance(entry, dict):
                continue
            cube_regions = entry.get("cubeRegions") or entry.get("cubeRegion") or []
            if isinstance(cube_regions, dict):
                cube_regions = [cube_regions]
            for region in cube_regions:
                if not isinstance(region, dict):
                    continue
                key_values = region.get("keyValues") or {}
                for dim_name, payload in key_values.items():
                    if not isinstance(payload, dict):
                        continue
                    values = payload.get("values") or payload.get("value") or []
                    if isinstance(values, dict):
                        values = [values]
                    bucket = allowed.setdefault(str(dim_name), set())
                    for value in values:
                        if isinstance(value, dict):
                            token = str(value.get("id") or value.get("value") or "").strip()
                        else:
                            token = str(value).strip()
                        if token:
                            bucket.add(token)
        return {key: sorted(values) for key, values in allowed.items() if values}

    @staticmethod
    def _estimate_constraint_cardinality(allowed_positions: dict[str, list[str]]) -> int:
        if not allowed_positions:
            return 0
        cardinality = 1
        for values in allowed_positions.values():
            size = len(values)
            if size <= 0:
                continue
            cardinality *= size
        return cardinality

    @staticmethod
    def _xml_local_name(tag: str) -> str:
        if "}" in tag:
            tag = tag.rsplit("}", 1)[-1]
        if ":" in tag:
            tag = tag.rsplit(":", 1)[-1]
        return tag

    @classmethod
    def _parse_async_submission_response(
        cls,
        raw: bytes,
        *,
        dataset_id: str,
        request_key: str,
        async_base: str,
    ) -> AsyncFetchLease | None:
        try:
            root = ET.fromstring(raw)
        except ET.ParseError:
            return None
        lease_id = ""
        status = ""
        for element in root.iter():
            name = cls._xml_local_name(str(element.tag)).lower()
            text = (element.text or "").strip()
            if name == "id" and text:
                lease_id = text
            elif name == "status" and text:
                status = text
        if not lease_id or not status:
            return None
        return AsyncFetchLease(
            lease_id=lease_id,
            connector_id=cls.connector_id,
            dataset_id=dataset_id,
            request_key=request_key,
            status=status.lower(),
            poll_after_seconds=5.0,
            status_url=f"{async_base}/status/{lease_id}",
            download_url=f"{async_base}/data/{lease_id}",
        )

    @classmethod
    def _parse_async_status_response(cls, raw: bytes) -> tuple[str, str] | None:
        try:
            root = ET.fromstring(raw)
        except ET.ParseError:
            return None
        key = ""
        status = ""
        for element in root.iter():
            name = cls._xml_local_name(str(element.tag)).lower()
            text = (element.text or "").strip()
            if name == "key" and text:
                key = text
            elif name == "status" and text:
                status = text
        if not status:
            return None
        return key, status

    @classmethod
    def _parse_async_fault(cls, raw: bytes) -> str | None:
        try:
            root = ET.fromstring(raw)
        except ET.ParseError:
            return None
        for element in root.iter():
            if cls._xml_local_name(str(element.tag)).lower() == "faultstring":
                text = (element.text or "").strip()
                if text:
                    return text
        return None


def _dimension_codes(info: dict[str, Any]) -> list[str]:
    category = info.get("category", {})
    if not isinstance(category, dict):
        return []
    index = category.get("index", {})

    if isinstance(index, dict):
        ordered_keys = [key for key, _ in sorted(index.items(), key=lambda item: int(item[1]))]
    elif isinstance(index, list):
        ordered_keys = [str(value) for value in index]
    else:
        ordered_keys = []

    if not ordered_keys:
        labels = category.get("label", {})
        if isinstance(labels, dict):
            ordered_keys = sorted(str(key) for key in labels)

    # Keep the stable category codes from the Eurostat payload rather than
    # swapping them for human-readable labels. Downstream filters, bulk
    # equivalence, and checkpoint signatures all operate on codes.
    return [str(key) for key in ordered_keys]


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
