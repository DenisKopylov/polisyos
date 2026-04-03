"""World Values Survey connector implementation for wave-aware survey indicator retrieval."""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, AsyncIterator, ClassVar

import pandas as pd

from polisyos.core.canon import streaming_hash
from polisyos.fabric.connectors.base import (
    ConnectionHandle,
    FetchRequest,
    FetchResult,
    HealthStatus,
)
from polisyos.fabric.connectors.sources._contracts.wvs_contracts import WVS_GENERIC_SCHEMA
from polisyos.fabric.connectors.sources.http_base import (
    HTTPConnectorBase,
    HTTPResilienceProfile,
)
from polisyos.fabric.connectors.sources.http_common import (
    frame_completeness,
    retry_after_seconds,
    safe_float,
    safe_int,
)
from polisyos.fabric.connectors.types import DatasetDescriptor, FetchError
from polisyos.ir.connectors import (
    ConnectorCapability,
    ConnectorMetadataSpec,
    QualityTier,
    TrustLevel,
    capabilities_from_flags,
)


_log = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _load_wvs_registry_indicators() -> dict[str, str]:
    """Load indicator titles from wvs_indicator_registry.yaml (wave 7 only)."""
    try:
        import yaml  # noqa: PLC0415

        registry_path = (
            Path(__file__).resolve().parents[5]
            / "data"
            / "dataset_catalog"
            / "wvs_indicator_registry.yaml"
        )
        if not registry_path.exists():
            return {}
        with open(registry_path) as fh:
            data = yaml.safe_load(fh)
        indicators = data.get("indicators", {})
        result: dict[str, str] = {}
        for code, spec in indicators.items():
            waves = spec.get("waves", [])
            if 7 in waves:
                result[code] = spec.get("title", code)
        _log.debug("WVS registry: loaded %d wave-7 indicators", len(result))
        return result
    except Exception:
        _log.warning("Failed to load WVS indicator registry, using static fallback", exc_info=True)
        return {}


class WVSConnector(HTTPConnectorBase[pd.DataFrame]):
    """Connector for World Values Survey wave and time-series data.

    Normalizes WVS wave lookups and temporal matching so survey observations
    can be joined into Fabric world snapshots.

    Data source:
        https://www.worldvaluessurvey.org
    Protocol:
        REST JSON plus local bulk-file profile support
    Auth:
        None
    Async support:
        Standard async HTTP execution only
    Profile:
        ``wvs_wave7``
    """

    namespace: ClassVar[str] = "wvs"
    short_id: ClassVar[str] = "wave7"
    connector_id: ClassVar[str] = f"{namespace}.{short_id}"
    _BASE_URL: ClassVar[str] = "https://api.worldvaluessurvey.org/v1"
    resilience_profile: ClassVar[HTTPResilienceProfile] = HTTPResilienceProfile(base_delay=1.2)

    WAVE_RANGES: ClassVar[dict[int, tuple[int, int]]] = {
        5: (2005, 2009),
        6: (2010, 2014),
        7: (2017, 2022),
    }
    _DEFAULT_SURVEY_YEAR_BY_COUNTRY: ClassVar[dict[str, int]] = {
        # Core blocking countries (Wave 7)
        "DE": 2018,
        "UA": 2020,
        "RO": 2018,
        "PL": 2018,
        # Regional extended
        "RU": 2017,
        "CZ": 2017,
        "HU": 2018,
        "LT": 2018,
        "LV": 2018,
        "EE": 2018,
        "GE": 2019,
        "AM": 2018,
        "AZ": 2018,
        "KZ": 2018,
        "KG": 2020,
        # Common partners
        "US": 2022,
        "GB": 2022,
        "AU": 2018,
        "JP": 2019,
        "CN": 2018,
        "BR": 2018,
        "MX": 2018,
        "TR": 2018,
        "NG": 2018,
        "EG": 2018,
        "ET": 2020,
        "ID": 2018,
        "PH": 2019,
        "TH": 2018,
        "VN": 2020,
        "CO": 2018,
        "PE": 2018,
        "CL": 2018,
        "AR": 2017,
        "NZ": 2020,
    }
    _WAVE7_INDICATORS: ClassVar[dict[str, str]] = {
        "A009": "State of health (subjective)",
        "A165": "Most people can be trusted (social trust)",
        "A170": "Satisfaction with your life",
        "A173": "How much freedom of choice and control",
        "D059": "Men make better political leaders than women do",
        "E023": "Interest in politics",
        "E025": "Political action: Signing a petition",
        "E035": "Income equality",
        "E069_07": "Confidence: Parliament",
        "E069_11": "Confidence: The Government",
        "E069_17": "Confidence: Justice System/Courts",
        "E117": "Political system: Having a democratic political system",
        "E233": "Democracy: Women have the same rights as men",
        "E286": "Social activism: Donating to a group or campaign",
        "Y022": "Welzel equality sub-index",
    }

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
        source_name="World Values Survey (Wave 7)",
        source_organization="World Values Survey Association",
        source_url="https://www.worldvaluessurvey.org",
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

    def __init__(self) -> None:
        super().__init__()
        self._survey_year_by_country = dict(self._DEFAULT_SURVEY_YEAR_BY_COUNTRY)

    def find_closest_in_wave(
        self,
        country_code: str,
        target_year: int,
        max_distance_years: int = 3,
    ) -> tuple[int | None, int | None]:
        """Find nearest survey year within the same wave when possible."""
        cc = (country_code or "").strip().upper()
        if not cc:
            return None, None

        candidate_year = self._survey_year_by_country.get(cc)
        if candidate_year is None:
            return None, None

        target_wave = self._year_to_wave(target_year)
        candidate_wave = self._year_to_wave(candidate_year)
        if target_wave is not None and candidate_wave is not None and target_wave != candidate_wave:
            return None, None
        if abs(target_year - candidate_year) > max_distance_years:
            return None, None
        return candidate_year, candidate_wave

    async def health_check(self, handle: ConnectionHandle) -> HealthStatus:
        url = self._build_url(handle, "/observations")
        params = {"indicator": "A165", "country": "US", "survey_year": "2022", "limit": "1"}
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
        del handle
        merged = {**self._WAVE7_INDICATORS, **_load_wvs_registry_indicators()}
        for indicator_code, label in sorted(merged.items()):
            yield DatasetDescriptor(
                dataset_id=indicator_code,
                name=label,
                description="World Values Survey Wave 7 indicator",
                tags=("wvs", "wave7", "survey"),
                metadata={"wave": 7},
            )

    async def fetch(
        self,
        handle: ConnectionHandle,
        request: FetchRequest,
    ) -> FetchResult[pd.DataFrame]:
        indicator_id = request.dataset_id
        countries = self._parse_countries(request)
        target_year = self._parse_target_year(request)
        started = time.monotonic()

        payload_chunks: list[bytes] = []
        rows: list[dict[str, Any]] = []
        bytes_transferred = 0
        etag: str | None = None
        last_modified: str | None = None
        etag_conflict = False
        last_modified_conflict = False

        url = self._build_url(handle, "/observations")
        params = self._build_fetch_params(
            indicator_id=indicator_id,
            countries=countries,
            survey_year=target_year,
        )
        body, headers, raw = await self._resilient_request_json(handle, url, params=params)
        payload_chunks.append(raw)
        bytes_transferred += len(raw)
        etag, etag_conflict = _update_header_consensus(
            current=etag,
            conflicted=etag_conflict,
            candidate=headers.get("ETag"),
        )
        last_modified, last_modified_conflict = _update_header_consensus(
            current=last_modified,
            conflicted=last_modified_conflict,
            candidate=headers.get("Last-Modified"),
        )
        rows.extend(self._extract_rows(body, indicator_id=indicator_id))

        if not rows and target_year is not None and countries:
            for country in countries:
                survey_year, wave = self.find_closest_in_wave(country, target_year)
                if survey_year is None:
                    continue
                retry_params = self._build_fetch_params(
                    indicator_id=indicator_id,
                    countries=[country],
                    survey_year=survey_year,
                )
                body_retry, headers_retry, raw_retry = await self._resilient_request_json(
                    handle,
                    url,
                    params=retry_params,
                )
                payload_chunks.append(raw_retry)
                bytes_transferred += len(raw_retry)
                etag, etag_conflict = _update_header_consensus(
                    current=etag,
                    conflicted=etag_conflict,
                    candidate=headers_retry.get("ETag"),
                )
                last_modified, last_modified_conflict = _update_header_consensus(
                    current=last_modified,
                    conflicted=last_modified_conflict,
                    candidate=headers_retry.get("Last-Modified"),
                )
                recovered = self._extract_rows(
                    body_retry,
                    indicator_id=indicator_id,
                    fallback_country=country,
                    fallback_survey_year=survey_year,
                    fallback_wave=wave,
                )
                rows.extend(recovered)

        frame = self._normalize_rows(rows, indicator_id=indicator_id)
        now = datetime.now(timezone.utc)
        return self._build_fetch_result(
            data=frame,
            row_count=len(frame),
            schema_id=WVS_GENERIC_SCHEMA.schema_id,
            schema_version=str(WVS_GENERIC_SCHEMA.version),
            quality_tier=QualityTier.SILVER,
            bytes_transferred=bytes_transferred,
            completeness=frame_completeness(frame),
            fetched_at=now,
            fetch_duration_ms=self._elapsed_ms(started),
            content_hash=streaming_hash(payload_chunks, prefix=True),
            etag=etag if not etag_conflict else None,
            last_modified=last_modified if not last_modified_conflict else None,
        )

    async def get_dataset_schema(
        self,
        handle: ConnectionHandle,
        dataset_id: str,
    ) -> dict[str, Any]:
        del handle, dataset_id
        return WVS_GENERIC_SCHEMA.model_dump(mode="python")

    def _build_url(self, handle: ConnectionHandle, path: str) -> str:
        base = self._base_url(handle).rstrip("/")
        suffix = path if path.startswith("/") else f"/{path}"
        return f"{base}{suffix}"

    @classmethod
    def _year_to_wave(cls, year: int) -> int | None:
        for wave, (start, end) in cls.WAVE_RANGES.items():
            if start <= year <= end:
                return wave
        return None

    @staticmethod
    def _parse_countries(request: FetchRequest) -> list[str]:
        filters = {key: list(values) for key, values in request.filters}
        raw = filters.get("country") or filters.get("country_code") or []
        return sorted({value.strip().upper() for value in raw if value and value.strip()})

    @staticmethod
    def _parse_target_year(request: FetchRequest) -> int | None:
        if request.date_end is not None:
            return int(request.date_end.year)
        if request.date_start is not None:
            return int(request.date_start.year)
        filters = {key: list(values) for key, values in request.filters}
        year_values = filters.get("survey_year") or filters.get("year") or []
        if not year_values:
            return None
        try:
            return int(year_values[0])
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _build_fetch_params(
        *,
        indicator_id: str,
        countries: list[str],
        survey_year: int | None,
    ) -> dict[str, str]:
        params: dict[str, str] = {"indicator": indicator_id}
        if countries:
            params["country"] = ",".join(countries)
        if survey_year is not None:
            params["survey_year"] = str(survey_year)
        return params

    @staticmethod
    def _extract_rows(
        payload: Any,
        *,
        indicator_id: str,
        fallback_country: str | None = None,
        fallback_survey_year: int | None = None,
        fallback_wave: int | None = None,
    ) -> list[dict[str, Any]]:
        if isinstance(payload, list):
            base_rows = [row for row in payload if isinstance(row, dict)]
        elif isinstance(payload, dict):
            if isinstance(payload.get("data"), list):
                base_rows = [row for row in payload["data"] if isinstance(row, dict)]
            elif isinstance(payload.get("items"), list):
                base_rows = [row for row in payload["items"] if isinstance(row, dict)]
            elif isinstance(payload.get("results"), list):
                base_rows = [row for row in payload["results"] if isinstance(row, dict)]
            else:
                base_rows = [payload]
        else:
            raise FetchError(
                message="Unexpected WVS payload type",
                connector_id=WVSConnector.connector_id,
                dataset_id=indicator_id,
            )

        out: list[dict[str, Any]] = []
        for row in base_rows:
            country = (
                row.get("country_code")
                or row.get("country")
                or row.get("country_iso3")
                or fallback_country
            )
            survey_year = (
                safe_int(row.get("survey_year"))
                or safe_int(row.get("year"))
                or fallback_survey_year
            )
            wave = safe_int(row.get("wave")) or safe_int(row.get("wave_number")) or fallback_wave
            if country is None or survey_year is None:
                continue
            out.append(
                {
                    "country_code": str(country).upper(),
                    "country_name": row.get("country_name") or row.get("country_label"),
                    "survey_year": int(survey_year),
                    "wave": int(wave) if wave is not None else 7,
                    "indicator_code": (
                        row.get("indicator_code")
                        or row.get("indicator_id")
                        or row.get("question_code")
                        or indicator_id
                    ),
                    "indicator_label": (
                        row.get("indicator_label")
                        or row.get("indicator_name")
                        or row.get("question_text")
                    ),
                    "value": safe_float(row.get("value")),
                    "sample_size": safe_int(row.get("sample_size")) or safe_int(row.get("n")),
                }
            )
        return out

    def _normalize_rows(
        self,
        rows: list[dict[str, Any]],
        *,
        indicator_id: str,
    ) -> pd.DataFrame:
        if not rows:
            return pd.DataFrame(columns=WVS_GENERIC_SCHEMA.field_names())
        frame = pd.DataFrame(rows, columns=WVS_GENERIC_SCHEMA.field_names())
        if frame.empty:
            return pd.DataFrame(columns=WVS_GENERIC_SCHEMA.field_names())

        frame["indicator_code"] = frame["indicator_code"].fillna(indicator_id)
        frame["wave"] = frame["wave"].fillna(7).astype("int64")
        frame["survey_year"] = frame["survey_year"].astype("int64")
        frame["country_code"] = frame["country_code"].astype(str)

        for _, row in frame.iterrows():
            cc = str(row.get("country_code") or "").upper()
            sy = safe_int(row.get("survey_year"))
            if cc and sy is not None:
                self._survey_year_by_country[cc] = int(sy)
        return frame


def _update_header_consensus(
    *,
    current: str | None,
    conflicted: bool,
    candidate: str | None,
) -> tuple[str | None, bool]:
    if conflicted:
        return None, True
    if candidate is None:
        return current, False
    if current is None:
        return candidate, False
    if current == candidate:
        return current, False
    return None, True


_retry_after_seconds = retry_after_seconds

__all__ = ["WVSConnector", "_retry_after_seconds"]
