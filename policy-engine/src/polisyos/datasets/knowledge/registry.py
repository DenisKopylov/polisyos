"""Dataset registry API for canonical variable lookup and P*(Z) computation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import duckdb

from polisyos.datasets.knowledge.types import DatasetMatch, PStarZResult


class DatasetRegistry:
    """DuckDB-backed registry for transportability-oriented dataset resolution."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    def find_datasets_for_variable(
        self,
        canonical_var: str,
        country_code: str,
        year_range: tuple[int, int] | None = None,
    ) -> list[DatasetMatch]:
        """Find matching datasets for a canonical variable in a country/time context."""
        with duckdb.connect(str(self._db_path), read_only=True) as con:
            rows = con.execute(
                "SELECT a.dataset_id, a.raw_variable, a.canonical_var, a.confidence, "
                "a.is_proxy, a.proxy_penalty, d.coverage_json, d.update_freq "
                "FROM ds_variable_alignments a "
                "LEFT JOIN ds_registry_datasets d ON d.dataset_id = a.dataset_id "
                "WHERE a.canonical_var = ?",
                [canonical_var],
            ).fetchall()

            out: list[DatasetMatch] = []
            cc = (country_code or "").strip().upper()
            for row in rows:
                dataset_id = str(row[0] or "")
                raw_var = str(row[1] or "")
                canonical = str(row[2] or "")
                mapping_conf = float(row[3] or 0.0)
                is_proxy = bool(row[4])
                proxy_penalty = float(row[5] or 0.0)
                coverage = _load_json_object(row[6])
                update_freq = str(row[7] or "")

                coverage_match = _coverage_match(
                    coverage=coverage,
                    country_code=cc,
                    year_range=year_range,
                )
                temporal_match, actual_survey_year, temporal_distance = self._temporal_match(
                    con=con,
                    dataset_id=dataset_id,
                    raw_variable=raw_var,
                    country_code=cc,
                    year_range=year_range,
                    update_freq=update_freq,
                )
                out.append(
                    DatasetMatch(
                        dataset_id=dataset_id,
                        raw_variable=raw_var,
                        canonical_variable=canonical,
                        is_proxy=is_proxy,
                        proxy_penalty=proxy_penalty,
                        mapping_confidence=mapping_conf,
                        coverage_match=coverage_match,
                        temporal_match=temporal_match,
                        actual_survey_year=actual_survey_year,
                        temporal_distance_years=temporal_distance,
                    )
                )

            out.sort(
                key=lambda m: (
                    1 if m.is_proxy else 0,
                    _coverage_rank(m.coverage_match),
                    _temporal_rank(m.temporal_match),
                    -m.mapping_confidence,
                    m.proxy_penalty,
                )
            )
            return out

    def compute_p_star_z(
        self,
        canonical_var: str,
        country_code: str,
        year: int,
        *,
        condition_on: dict[str, float] | None = None,
    ) -> PStarZResult:
        """Compute point estimate P*(Z) or conditional P*(Z|X=x) from cached observations."""
        matches = self.find_datasets_for_variable(
            canonical_var=canonical_var,
            country_code=country_code,
            year_range=(year, year),
        )
        is_conditional = bool(condition_on)
        requested_conditions = condition_on or {}
        conditional_failure_reason: str | None = None

        with duckdb.connect(str(self._db_path), read_only=True) as con:
            for match in matches:
                if match.coverage_match == "none":
                    continue

                if is_conditional:
                    if not self._conditions_present(
                        con=con,
                        dataset_id=match.dataset_id,
                        country_code=country_code,
                        target_year=match.actual_survey_year or year,
                        condition_vars=tuple(requested_conditions.keys()),
                    ):
                        conditional_failure_reason = "condition_variables_missing"
                        continue

                    values = self._read_conditional_values_for_match(
                        con=con,
                        match=match,
                        country_code=country_code,
                        target_year=year,
                        condition_on=requested_conditions,
                    )
                    if not values:
                        conditional_failure_reason = "conditional_filter_unavailable"
                        continue
                else:
                    values = self._read_values_for_match(
                        con=con,
                        match=match,
                        country_code=country_code,
                        target_year=year,
                    )
                    if not values:
                        continue

                value = float(sum(values) / len(values))
                penalties: dict[str, float] = {}
                confidence = match.mapping_confidence if match.mapping_confidence > 0 else 1.0
                if match.is_proxy and match.proxy_penalty > 0:
                    penalties["proxy"] = match.proxy_penalty
                    confidence -= match.proxy_penalty
                if match.temporal_distance_years > 0:
                    temporal_penalty = min(0.3, 0.05 * match.temporal_distance_years)
                    penalties["temporal"] = temporal_penalty
                    confidence -= temporal_penalty
                if is_conditional:
                    penalties["conditional"] = 0.05
                    confidence -= 0.05
                confidence = max(0.0, min(1.0, confidence))

                return PStarZResult(
                    canonical_variable=canonical_var,
                    value=value,
                    dataset_id=match.dataset_id,
                    raw_variable=match.raw_variable,
                    is_proxy=match.is_proxy,
                    proxy_chain=(
                        [f"{match.raw_variable} -> {canonical_var}"] if match.is_proxy else []
                    ),
                    confidence=confidence,
                    penalty_breakdown=penalties,
                    is_conditional=is_conditional,
                    condition_on=requested_conditions,
                    distribution=values if len(values) > 1 else None,
                    distribution_type=("empirical" if len(values) > 1 else "point"),
                )

        penalties: dict[str, float]
        if is_conditional:
            penalties = {
                (conditional_failure_reason or "conditional_estimation_unavailable"): 1.0,
            }
        else:
            penalties = {"missing_data": 1.0}

        return PStarZResult(
            canonical_variable=canonical_var,
            value=None,
            dataset_id=None,
            raw_variable=None,
            is_proxy=False,
            proxy_chain=[],
            confidence=0.0,
            penalty_breakdown=penalties,
            is_conditional=is_conditional,
            condition_on=requested_conditions,
            distribution=None,
            distribution_type="point",
        )

    def _temporal_match(
        self,
        *,
        con: duckdb.DuckDBPyConnection,
        dataset_id: str,
        raw_variable: str,
        country_code: str,
        year_range: tuple[int, int] | None,
        update_freq: str,
    ) -> tuple[str, int | None, int]:
        if year_range is None:
            return "exact", None, 0
        target_year = int(year_range[1])
        if update_freq.lower() == "wave":
            row = con.execute(
                "SELECT survey_year, year "
                "FROM ds_observations "
                "WHERE dataset_id = ? AND raw_variable = ? AND country_code = ? "
                "AND (survey_year IS NOT NULL OR year IS NOT NULL) "
                "ORDER BY ABS(COALESCE(survey_year, year) - ?) ASC "
                "LIMIT 1",
                [dataset_id, raw_variable, country_code, target_year],
            ).fetchone()
            if row is None:
                return "none", None, 0
            survey_year = int(row[0] or row[1])
            distance = abs(target_year - survey_year)
            if distance == 0:
                return "exact", survey_year, 0
            if distance <= 3:
                return "wave_closest", survey_year, distance
            return "extrapolation", survey_year, distance

        coverage_row = con.execute(
            "SELECT MIN(year), MAX(year) "
            "FROM ds_observations "
            "WHERE dataset_id = ? AND raw_variable = ? AND country_code = ? AND year IS NOT NULL",
            [dataset_id, raw_variable, country_code],
        ).fetchone()
        if coverage_row is None or coverage_row[0] is None or coverage_row[1] is None:
            return "none", None, 0
        start_year = int(coverage_row[0])
        end_year = int(coverage_row[1])
        if start_year <= target_year <= end_year:
            return ("exact" if start_year == end_year == target_year else "overlap"), None, 0
        distance = min(abs(target_year - start_year), abs(target_year - end_year))
        return "extrapolation", None, distance

    @staticmethod
    def _read_values_for_match(
        *,
        con: duckdb.DuckDBPyConnection,
        match: DatasetMatch,
        country_code: str,
        target_year: int,
    ) -> list[float]:
        if match.actual_survey_year is not None:
            rows = con.execute(
                "SELECT value FROM ds_observations "
                "WHERE dataset_id = ? AND raw_variable = ? AND country_code = ? "
                "AND survey_year = ? AND value IS NOT NULL",
                [match.dataset_id, match.raw_variable, country_code, match.actual_survey_year],
            ).fetchall()
        else:
            rows = con.execute(
                "SELECT value FROM ds_observations "
                "WHERE dataset_id = ? AND raw_variable = ? AND country_code = ? "
                "AND year = ? AND value IS NOT NULL",
                [match.dataset_id, match.raw_variable, country_code, target_year],
            ).fetchall()
        return [float(row[0]) for row in rows if row and row[0] is not None]

    @staticmethod
    def _read_conditional_values_for_match(
        *,
        con: duckdb.DuckDBPyConnection,
        match: DatasetMatch,
        country_code: str,
        target_year: int,
        condition_on: dict[str, float],
    ) -> list[float]:
        if match.actual_survey_year is not None:
            rows = con.execute(
                "SELECT value, condition_json FROM ds_observations "
                "WHERE dataset_id = ? AND raw_variable = ? AND country_code = ? "
                "AND survey_year = ? AND value IS NOT NULL",
                [match.dataset_id, match.raw_variable, country_code, match.actual_survey_year],
            ).fetchall()
        else:
            rows = con.execute(
                "SELECT value, condition_json FROM ds_observations "
                "WHERE dataset_id = ? AND raw_variable = ? AND country_code = ? "
                "AND year = ? AND value IS NOT NULL",
                [match.dataset_id, match.raw_variable, country_code, target_year],
            ).fetchall()

        filtered: list[float] = []
        for row in rows:
            if not row:
                continue
            value = row[0]
            if value is None:
                continue
            condition_payload = _load_json_object(row[1])
            if not DatasetRegistry._conditions_match(condition_payload, condition_on):
                continue
            filtered.append(float(value))
        return filtered

    @staticmethod
    def _conditions_match(observed: dict[str, Any], requested: dict[str, float]) -> bool:
        if not requested:
            return True
        for name, required_value in requested.items():
            if name not in observed:
                return False
            observed_value = observed.get(name)
            try:
                if abs(float(observed_value) - float(required_value)) > 1e-6:
                    return False
            except (TypeError, ValueError):
                if str(observed_value) != str(required_value):
                    return False
        return True

    @staticmethod
    def _conditions_present(
        *,
        con: duckdb.DuckDBPyConnection,
        dataset_id: str,
        country_code: str,
        target_year: int,
        condition_vars: tuple[str, ...],
    ) -> bool:
        for condition_var in condition_vars:
            row = con.execute(
                "SELECT 1 FROM ds_observations "
                "WHERE dataset_id = ? AND canonical_var = ? AND country_code = ? "
                "AND (year = ? OR survey_year = ?) "
                "AND value IS NOT NULL LIMIT 1",
                [dataset_id, condition_var, country_code, target_year, target_year],
            ).fetchone()
            if row is None:
                return False
        return True


def _load_json_object(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _parse_time_range(range_value: str) -> tuple[int | None, int | None]:
    if not range_value:
        return None, None
    if "-" not in range_value:
        try:
            year = int(range_value)
        except (TypeError, ValueError):
            return None, None
        return year, year
    left, right = range_value.split("-", 1)
    try:
        return int(left), int(right)
    except (TypeError, ValueError):
        return None, None


def _coverage_match(
    *,
    coverage: dict[str, Any],
    country_code: str,
    year_range: tuple[int, int] | None,
) -> str:
    countries = coverage.get("countries")
    if isinstance(countries, list) and countries:
        normalized = {str(value).upper() for value in countries}
        if country_code and country_code not in normalized:
            return "none"

    if year_range is not None:
        target_start, target_end = year_range
        cov_start, cov_end = _parse_time_range(str(coverage.get("time_range", "")))
        if cov_start is not None and cov_end is not None:
            if target_end < cov_start or target_start > cov_end:
                return "none"
            if target_start >= cov_start and target_end <= cov_end:
                return "full"
            return "partial"
        return "partial"

    return "full"


def _coverage_rank(value: str) -> int:
    ranks = {"full": 0, "partial": 1, "none": 2}
    return ranks.get(value, 3)


def _temporal_rank(value: str) -> int:
    ranks = {"exact": 0, "wave_closest": 1, "overlap": 2, "extrapolation": 3, "none": 4}
    return ranks.get(value, 5)


__all__ = ["DatasetRegistry"]
