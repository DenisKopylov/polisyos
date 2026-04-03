"""WHO Global Health Observatory connector implementation for indicator and observation APIs."""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Any, AsyncIterator, ClassVar

import pandas as pd

from polisyos.core.canon import streaming_hash
from polisyos.fabric.connectors.base import ConnectionHandle, FetchRequest, FetchResult, HealthStatus
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

_WHO_FIELDS = (
    "indicator_id",
    "country_code",
    "year",
    "value",
    "dimension_1",
    "dimension_2",
    "dimension_3",
    "dimensions_json",
    "updated_at",
)

_WHO_SELECT_FIELDS = (
    "IndicatorCode",
    "SpatialDim",
    "TimeDim",
    "TimeDimensionValue",
    "NumericValue",
    "Value",
    "Dim1Type",
    "Dim1",
    "Dim2Type",
    "Dim2",
    "Dim3Type",
    "Dim3",
    "Date",
)


class WHOConnector(HTTPConnectorBase[pd.DataFrame]):
    """Connector for WHO Global Health Observatory indicator observations.

    Fetches public health indicators and dimensions from the WHO GHO API using
    grouped HTTP requests and Fabric normalization semantics.

    Data source:
        https://www.who.int/data/gho
    Protocol:
        REST JSON / OData-like API
    Auth:
        None
    Async support:
        Standard async HTTP execution only
    Profile:
        ``who_gho``
    """

    namespace: ClassVar[str] = "who"
    short_id: ClassVar[str] = "indicators"
    connector_id: ClassVar[str] = f"{namespace}.{short_id}"
    _BASE_URL: ClassVar[str] = "https://ghoapi.azureedge.net/api"
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
        source_name="WHO Global Health Observatory",
        source_organization="World Health Organization",
        source_url="https://www.who.int/data/gho",
        trust_level=TrustLevel.AUTHORITATIVE,
        quality_tier=QualityTier.SILVER,
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
        url = f"{self._base_url(handle)}/Indicator"
        started = time.monotonic()
        try:
            _body, _headers, _raw = await self._resilient_request_json(
                handle,
                url,
                params={"$top": "1"},
            )
            return HealthStatus(
                healthy=True,
                message="HTTP 200",
                latency_ms=self._elapsed_ms(started),
            )
        except Exception as exc:
            status_code = getattr(exc, "status_code", None)
            message = f"HTTP {status_code}" if status_code is not None else str(exc)
            return HealthStatus(
                healthy=False,
                message=message,
                latency_ms=self._elapsed_ms(started),
            )

    async def list_datasets(self, handle: ConnectionHandle) -> AsyncIterator[DatasetDescriptor]:
        url = f"{self._base_url(handle)}/Indicator"
        limit = max(1, safe_int(handle.config.headers.get("X-WHO-CATALOG-LIMIT")) or 200)
        body, _headers, _raw = await self._resilient_request_json(
            handle,
            url,
            params={"$top": str(limit)},
        )
        records = body.get("value", []) if isinstance(body, dict) else []
        for row in records:
            if not isinstance(row, dict):
                continue
            dataset_id = str(row.get("IndicatorCode") or "").strip()
            if not dataset_id:
                continue
            yield DatasetDescriptor(
                dataset_id=dataset_id,
                name=str(row.get("IndicatorName") or dataset_id),
                description="WHO GHO indicator",
                tags=("who", "gho", "health"),
                metadata={"language": row.get("Language")},
                schema_id="who.indicators.generic",
                supports_filters=("country", "year", "dim1", "dim2", "dim3"),
            )

    async def fetch(
        self,
        handle: ConnectionHandle,
        request: FetchRequest,
    ) -> FetchResult[pd.DataFrame]:
        indicator_id = request.dataset_id
        url = f"{self._base_url(handle)}/{indicator_id}"
        params = self._build_params(request)
        started = time.monotonic()

        body, headers, raw = await self._resilient_request_json(
            handle,
            url,
            params=params,
        )
        if not isinstance(body, dict):
            raise FetchError(
                message="Unexpected WHO payload type",
                connector_id=self.connector_id,
                dataset_id=indicator_id,
            )

        frame = self._normalize_rows(body, indicator_id)
        now = datetime.now(timezone.utc)
        return self._build_fetch_result(
            data=frame,
            row_count=len(frame),
            schema_id="who.indicators.generic",
            schema_version="1.0.0",
            quality_tier=QualityTier.SILVER,
            bytes_transferred=len(raw),
            completeness=frame_completeness(frame),
            fetched_at=now,
            fetch_duration_ms=self._elapsed_ms(started),
            content_hash=streaming_hash((raw,), prefix=True),
            etag=headers.get("ETag"),
            last_modified=headers.get("Last-Modified"),
        )

    async def get_dataset_schema(
        self,
        handle: ConnectionHandle,
        dataset_id: str,
    ) -> dict[str, Any]:
        del handle, dataset_id
        return {
            "schema_id": "who.indicators.generic",
            "version": "1.0.0",
            "fields": list(_WHO_FIELDS),
            "time_dimension": "year",
            "geo_dimension": "country_code",
        }

    @staticmethod
    def _build_params(request: FetchRequest) -> dict[str, str]:
        filter_map = {key: list(values) for key, values in request.filters}
        clauses: list[str] = []

        countries = [
            WHOConnector._to_iso3(value)
            for key in ("country", "geo", "geography", "SpatialDim")
            for value in filter_map.get(key, [])
            if value
        ]
        countries = sorted({value for value in countries if value})
        if countries:
            if len(countries) == 1:
                clauses.append(f"SpatialDim eq '{countries[0]}'")
            else:
                clauses.append("(" + " or ".join(f"SpatialDim eq '{value}'" for value in countries) + ")")

        year_values = [safe_int(value) for value in filter_map.get("year", []) + filter_map.get("TimeDim", [])]
        year_values = [value for value in year_values if value is not None]
        start_year = request.date_start.year if request.date_start is not None else None
        end_year = request.date_end.year if request.date_end is not None else None
        if year_values:
            start_year = min(year_values)
            end_year = max(year_values)
        if start_year is not None:
            clauses.append(f"TimeDim ge {int(start_year)}")
        if end_year is not None:
            clauses.append(f"TimeDim le {int(end_year)}")

        for dim_key, source_key in (("dim1", "Dim1"), ("dim2", "Dim2"), ("dim3", "Dim3")):
            values = [str(value).strip() for value in filter_map.get(dim_key, []) if str(value).strip()]
            if not values:
                continue
            if len(values) == 1:
                clauses.append(f"{source_key} eq '{values[0]}'")
            else:
                clauses.append("(" + " or ".join(f"{source_key} eq '{value}'" for value in values) + ")")

        params: dict[str, str] = {}
        if clauses:
            params["$filter"] = " and ".join(clauses)
        params["$select"] = ",".join(_WHO_SELECT_FIELDS)
        return params

    @staticmethod
    def _normalize_rows(body: dict[str, Any], indicator_id: str) -> pd.DataFrame:
        records = body.get("value", [])
        if not isinstance(records, list):
            return pd.DataFrame(columns=_WHO_FIELDS)

        rows: list[dict[str, Any]] = []
        for row in records:
            if not isinstance(row, dict):
                continue
            dims = {
                key: row.get(key)
                for key in ("Dim1Type", "Dim1", "Dim2Type", "Dim2", "Dim3Type", "Dim3")
                if row.get(key) not in (None, "")
            }
            numeric_value = safe_float(row.get("NumericValue"))
            if numeric_value is None:
                numeric_value = safe_float(row.get("Value"))
            rows.append(
                {
                    "indicator_id": str(row.get("IndicatorCode") or indicator_id),
                    "country_code": str(row.get("SpatialDim") or "").strip().upper(),
                    "year": safe_int(row.get("TimeDim") or row.get("TimeDimensionValue")),
                    "value": numeric_value,
                    "dimension_1": row.get("Dim1"),
                    "dimension_2": row.get("Dim2"),
                    "dimension_3": row.get("Dim3"),
                    "dimensions_json": json.dumps(dims, sort_keys=True, separators=(",", ":")),
                    "updated_at": row.get("Date"),
                }
            )

        if not rows:
            return pd.DataFrame(columns=_WHO_FIELDS)
        return pd.DataFrame(rows, columns=_WHO_FIELDS)

    @staticmethod
    def _to_iso3(value: str) -> str:
        normalized = str(value or "").strip().upper()
        return _ISO2_TO_ISO3.get(normalized, normalized)


# Comprehensive ISO-2 → ISO-3 mapping for all country scopes used by the
# pipeline (core_blocking + regional_extended + common partners).  Entries
# that are already ISO-3 map to themselves so passthrough is safe.
_ISO2_TO_ISO3: dict[str, str] = {
    # core_blocking
    "UA": "UKR", "UKR": "UKR",
    "DE": "DEU", "DEU": "DEU",
    "PL": "POL", "POL": "POL",
    "RO": "ROU", "ROU": "ROU",
    "MD": "MDA", "MDA": "MDA",
    # regional_extended
    "CZ": "CZE", "CZE": "CZE",
    "SK": "SVK", "SVK": "SVK",
    "HU": "HUN", "HUN": "HUN",
    "LT": "LTU", "LTU": "LTU",
    "LV": "LVA", "LVA": "LVA",
    "EE": "EST", "EST": "EST",
    "GE": "GEO", "GEO": "GEO",
    "AM": "ARM", "ARM": "ARM",
    "AZ": "AZE", "AZE": "AZE",
    "KZ": "KAZ", "KAZ": "KAZ",
    "UZ": "UZB", "UZB": "UZB",
    # common partners
    "US": "USA", "USA": "USA",
    "GB": "GBR", "GBR": "GBR",
    "FR": "FRA", "FRA": "FRA",
    "IT": "ITA", "ITA": "ITA",
    "ES": "ESP", "ESP": "ESP",
    "AT": "AUT", "AUT": "AUT",
    "BE": "BEL", "BEL": "BEL",
    "NL": "NLD", "NLD": "NLD",
    "SE": "SWE", "SWE": "SWE",
    "DK": "DNK", "DNK": "DNK",
    "FI": "FIN", "FIN": "FIN",
    "NO": "NOR", "NOR": "NOR",
    "CH": "CHE", "CHE": "CHE",
    "PT": "PRT", "PRT": "PRT",
    "IE": "IRL", "IRL": "IRL",
    "BG": "BGR", "BGR": "BGR",
    "HR": "HRV", "HRV": "HRV",
    "SI": "SVN", "SVN": "SVN",
    "RS": "SRB", "SRB": "SRB",
    "BA": "BIH", "BIH": "BIH",
    "ME": "MNE", "MNE": "MNE",
    "AL": "ALB", "ALB": "ALB",
    "MK": "MKD", "MKD": "MKD",
    "BY": "BLR", "BLR": "BLR",
    "RU": "RUS", "RUS": "RUS",
    "TR": "TUR", "TUR": "TUR",
    "CN": "CHN", "CHN": "CHN",
    "IN": "IND", "IND": "IND",
    "JP": "JPN", "JPN": "JPN",
    "KR": "KOR", "KOR": "KOR",
    "BR": "BRA", "BRA": "BRA",
    "MX": "MEX", "MEX": "MEX",
    "ZA": "ZAF", "ZAF": "ZAF",
    "AU": "AUS", "AUS": "AUS",
    "CA": "CAN", "CAN": "CAN",
    "NZ": "NZL", "NZL": "NZL",
}


__all__ = ["WHOConnector"]
