"""Dataset registry API for canonical variable lookup and P*(Z) computation."""

from __future__ import annotations

import json
import math
from typing import TYPE_CHECKING, Any

import duckdb

from polisyos.datasets.knowledge.proxy_penalties import (
    metric_name_from_alignment_evidence,
    resolve_proxy_penalty,
)
from polisyos.datasets.knowledge.types import DatasetMatch, PStarZResult

if TYPE_CHECKING:
    from pathlib import Path

_TEMPORAL_VOLATILITY: dict[str, float] = {
    "institutional_quality": 0.02,
    "rule_of_law": 0.02,
    "population": 0.01,
    "life_expectancy": 0.02,
    "gdp_per_capita": 0.05,
    "unemployment_rate": 0.08,
    "poverty_rate": 0.04,
    "inequality": 0.03,
    "inflation": 0.15,
    "exchange_rate": 0.20,
    "migration": 0.10,
    "interest_rate": 0.12,
    "public_trust": 0.04,
    "social_trust": 0.03,
}
_DEFAULT_VOLATILITY = 0.05


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
                "a.is_proxy, a.proxy_penalty, d.coverage_json, d.update_freq, a.method, a.evidence "
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
                alignment_method = str(row[8] or "")
                alignment_evidence = str(row[9] or "")

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
                        alignment_method=alignment_method,
                        alignment_evidence=alignment_evidence,
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

    def find_datasets_for_variables_bulk(
        self,
        variables: list[str],
        country_code: str,
        year_range: tuple[int, int] | None = None,
    ) -> dict[str, list[DatasetMatch]]:
        out: dict[str, list[DatasetMatch]] = {}
        for variable in variables:
            out[str(variable)] = self.find_datasets_for_variable(
                str(variable),
                country_code,
                year_range,
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
        """Compute bounded P*(Z) or P*(Z|X=x) estimate with provenance."""
        matches = self.find_datasets_for_variable(
            canonical_var=canonical_var,
            country_code=country_code,
            year_range=(year, year),
        )
        if not matches:
            matches = self.find_datasets_for_variable(
                canonical_var=canonical_var,
                country_code=country_code,
                year_range=(max(year - 3, 0), year + 1),
            )
        is_conditional = bool(condition_on)
        requested_conditions = condition_on or {}
        conditional_failure_reason: str | None = None

        with duckdb.connect(str(self._db_path), read_only=True) as con:
            estimates: list[dict[str, Any]] = []
            for match in matches:
                if match.coverage_match == "none":
                    continue
                if match.temporal_distance_years > _max_temporal_lag(canonical_var):
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
                        series = self._read_observation_series_for_match(
                            con=con,
                            match=match,
                            country_code=country_code,
                            conditional=True,
                            condition_on=requested_conditions,
                        )
                        interpolated_value, interp_confidence, support_year, imputation_method = (
                            _interpolate_observation(
                                series,
                                target_year=year,
                                max_lag=_max_temporal_lag(canonical_var),
                            )
                        )
                        if interpolated_value is None:
                            conditional_failure_reason = "conditional_filter_unavailable"
                            continue
                        values = [interpolated_value]
                        uncertainty_sources = ["conditional", "interpolation"]
                        imputation_penalty = _imputation_penalty(imputation_method)
                        support_year_value = support_year
                    else:
                        uncertainty_sources = ["conditional"]
                        imputation_penalty = 0.0
                        support_year_value = match.actual_survey_year or year
                else:
                    values = self._read_values_for_match(
                        con=con,
                        match=match,
                        country_code=country_code,
                        target_year=year,
                    )
                    if not values:
                        series = self._read_observation_series_for_match(
                            con=con,
                            match=match,
                            country_code=country_code,
                            conditional=False,
                            condition_on=None,
                        )
                        interpolated_value, _interp_confidence, support_year, imputation_method = (
                            _interpolate_observation(
                                series,
                                target_year=year,
                                max_lag=_max_temporal_lag(canonical_var),
                            )
                        )
                        if interpolated_value is None:
                            continue
                        values = [interpolated_value]
                        uncertainty_sources = ["interpolation"]
                        imputation_penalty = _imputation_penalty(imputation_method)
                        support_year_value = support_year
                    else:
                        uncertainty_sources = []
                        imputation_penalty = 0.0
                        support_year_value = match.actual_survey_year or year

                value = float(sum(values) / len(values))
                penalties: dict[str, float] = {}
                weight = match.mapping_confidence if match.mapping_confidence > 0 else 1.0
                if match.is_proxy and match.proxy_penalty > 0:
                    effective_proxy_penalty = resolve_proxy_penalty(
                        metric_name=metric_name_from_alignment_evidence(match.alignment_evidence),
                        canonical_var=match.canonical_variable,
                        base_penalty=match.proxy_penalty,
                        country_code=country_code,
                        year=year,
                    )
                    penalties["proxy"] = effective_proxy_penalty
                    uncertainty_sources.append("proxy_penalty")
                    weight *= max(0.0, 1.0 - effective_proxy_penalty)
                temporal_penalty = _temporal_penalty(
                    canonical_var, support_year_value or year, year
                )
                if temporal_penalty > 0:
                    penalties["temporal"] = temporal_penalty
                    uncertainty_sources.append("temporal_distance")
                    weight *= max(0.0, 1.0 - temporal_penalty)
                if imputation_penalty > 0:
                    penalties["imputation"] = imputation_penalty
                    uncertainty_sources.append("imputation")
                    weight *= max(0.0, 1.0 - imputation_penalty)
                if is_conditional:
                    penalties["conditional"] = 0.05
                    weight *= 0.95
                weight = max(0.0, min(1.0, weight))
                if weight <= 0:
                    continue
                estimates.append(
                    {
                        "match": match,
                        "value": value,
                        "values": values,
                        "weight": weight,
                        "penalties": penalties,
                        "uncertainty_sources": sorted(set(uncertainty_sources)),
                        "support_year": support_year_value,
                        "imputation_method": imputation_method
                        if "imputation" in penalties
                        else None,
                        "imputation_penalty": imputation_penalty,
                    }
                )

            if estimates:
                total_weight = sum(float(item["weight"]) for item in estimates) or 1.0
                weighted_mean = (
                    sum(float(item["value"]) * float(item["weight"]) for item in estimates)
                    / total_weight
                )
                distribution = [float(item["value"]) for item in estimates]
                direct_exact = [
                    item
                    for item in estimates
                    if not item["match"].is_proxy
                    and float(item["penalties"].get("proxy", 0.0)) == 0.0
                    and float(item["penalties"].get("temporal", 0.0)) == 0.0
                    and float(item["penalties"].get("imputation", 0.0)) == 0.0
                    and item["match"].temporal_match in {"exact", "overlap", "wave_closest"}
                    and (
                        item.get("support_year") == year or item["match"].actual_survey_year == year
                    )
                ]
                if direct_exact:
                    best_exact = max(direct_exact, key=lambda item: float(item["weight"]))
                    best_match = best_exact["match"]
                    exact_value = float(best_exact["value"])
                    return PStarZResult(
                        canonical_variable=canonical_var,
                        value=exact_value,
                        dataset_id=best_match.dataset_id,
                        raw_variable=best_match.raw_variable,
                        is_proxy=bool(best_match.is_proxy),
                        proxy_chain=(
                            [f"{best_match.raw_variable} -> {canonical_var}"]
                            if best_match.is_proxy
                            else []
                        ),
                        confidence=float(best_exact["weight"]),
                        penalty_breakdown=dict(best_exact["penalties"]),
                        is_conditional=is_conditional,
                        condition_on=requested_conditions,
                        distribution=None,
                        distribution_type="point",
                        std_error=None,
                        ci_low=None,
                        ci_high=None,
                        uncertainty_sources=list(best_exact["uncertainty_sources"]),
                        imputation_method=best_exact.get("imputation_method"),
                        imputation_penalty=float(best_exact.get("imputation_penalty", 0.0) or 0.0),
                        data_support_year=int(best_exact.get("support_year"))
                        if best_exact.get("support_year") is not None
                        else None,
                        data_support_country=country_code,
                    )
                max_weight_item = max(estimates, key=lambda item: float(item["weight"]))
                if len(distribution) > 1:
                    variance = (
                        sum(
                            float(item["weight"]) * ((float(item["value"]) - weighted_mean) ** 2)
                            for item in estimates
                        )
                        / total_weight
                    )
                    std_error = math.sqrt(max(variance, 0.0) / len(distribution))
                    distribution_type = "normal"
                else:
                    std_error = (
                        abs(weighted_mean) * max(0.05, 1.0 - float(max_weight_item["weight"])) * 0.5
                    )
                    distribution_type = "bounded"
                ci_low = weighted_mean - 1.96 * std_error
                ci_high = weighted_mean + 1.96 * std_error
                merged_penalties: dict[str, float] = {}
                uncertainty_sources = sorted(
                    {source for item in estimates for source in item["uncertainty_sources"]}
                )
                for item in estimates:
                    for key, value in dict(item["penalties"]).items():
                        merged_penalties[key] = max(
                            float(value), float(merged_penalties.get(key, 0.0))
                        )
                best_match = max_weight_item["match"]
                return PStarZResult(
                    canonical_variable=canonical_var,
                    value=float(weighted_mean),
                    dataset_id=best_match.dataset_id,
                    raw_variable=best_match.raw_variable,
                    is_proxy=bool(best_match.is_proxy),
                    proxy_chain=(
                        [f"{best_match.raw_variable} -> {canonical_var}"]
                        if best_match.is_proxy
                        else []
                    ),
                    confidence=float(max_weight_item["weight"]),
                    penalty_breakdown=merged_penalties,
                    is_conditional=is_conditional,
                    condition_on=requested_conditions,
                    distribution=(distribution if len(distribution) > 1 else None),
                    distribution_type=distribution_type,
                    std_error=float(std_error),
                    ci_low=float(ci_low),
                    ci_high=float(ci_high),
                    uncertainty_sources=uncertainty_sources,
                    imputation_method=max_weight_item.get("imputation_method"),
                    imputation_penalty=float(max_weight_item.get("imputation_penalty", 0.0) or 0.0),
                    data_support_year=int(max_weight_item.get("support_year"))
                    if max_weight_item.get("support_year") is not None
                    else None,
                    data_support_country=country_code,
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
            std_error=None,
            ci_low=None,
            ci_high=None,
            uncertainty_sources=[],
            imputation_method=None,
            imputation_penalty=0.0,
            data_support_year=None,
            data_support_country=country_code,
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
    def _read_observation_series_for_match(
        *,
        con: duckdb.DuckDBPyConnection,
        match: DatasetMatch,
        country_code: str,
        conditional: bool,
        condition_on: dict[str, float] | None,
    ) -> list[tuple[int, float]]:
        rows = con.execute(
            "SELECT COALESCE(survey_year, year) AS support_year, value, condition_json "
            "FROM ds_observations "
            "WHERE dataset_id = ? AND raw_variable = ? AND country_code = ? "
            "AND value IS NOT NULL "
            "AND (survey_year IS NOT NULL OR year IS NOT NULL)",
            [match.dataset_id, match.raw_variable, country_code],
        ).fetchall()
        out: list[tuple[int, float]] = []
        for row in rows:
            support_year = row[0]
            value = row[1]
            if support_year is None or value is None:
                continue
            if conditional and condition_on:
                if not DatasetRegistry._conditions_match(_load_json_object(row[2]), condition_on):
                    continue
            out.append((int(support_year), float(value)))
        out.sort(key=lambda item: item[0])
        return out

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


def _temporal_penalty(canonical_var: str, data_year: int, target_year: int) -> float:
    volatility = _TEMPORAL_VOLATILITY.get(canonical_var, _DEFAULT_VOLATILITY)
    distance = abs(int(target_year) - int(data_year))
    return min(0.5, float(volatility) * float(distance))


def _max_temporal_lag(canonical_var: str) -> int:
    volatility = _TEMPORAL_VOLATILITY.get(canonical_var, _DEFAULT_VOLATILITY)
    if volatility >= 0.12:
        return 1
    if volatility >= 0.07:
        return 2
    if volatility >= 0.04:
        return 3
    return 6


def _interpolate_observation(
    observations: list[tuple[int, float]],
    *,
    target_year: int,
    max_lag: int,
) -> tuple[float | None, float, int | None, str | None]:
    if not observations:
        return None, 0.0, None, None
    years = [item[0] for item in observations]
    values = [item[1] for item in observations]
    if target_year in years:
        idx = years.index(target_year)
        return float(values[idx]), 1.0, int(target_year), None

    before = [(year, value) for year, value in observations if year < target_year]
    after = [(year, value) for year, value in observations if year > target_year]
    if before and after:
        left_year, left_value = before[-1]
        right_year, right_value = after[0]
        gap = right_year - left_year
        if (
            gap <= 0
            or abs(target_year - left_year) > max_lag
            or abs(right_year - target_year) > max_lag
        ):
            return None, 0.0, None, None
        fraction = (target_year - left_year) / gap
        interpolated = left_value + fraction * (right_value - left_value)
        confidence = max(0.5, 1.0 - 0.05 * gap)
        return float(interpolated), float(confidence), int(target_year), "linear_interpolation"

    nearest_year, nearest_value = min(observations, key=lambda item: abs(item[0] - target_year))
    distance = abs(nearest_year - target_year)
    if distance > max_lag:
        return None, 0.0, None, None
    confidence = max(0.25, 1.0 - 0.12 * distance)
    method = "carry_forward" if nearest_year < target_year else "nearest_observation"
    return float(nearest_value), float(confidence), int(nearest_year), method


def _imputation_penalty(method: str | None) -> float:
    if not method:
        return 0.0
    penalties = {
        "linear_interpolation": 0.08,
        "carry_forward": 0.18,
        "nearest_observation": 0.12,
    }
    return float(penalties.get(method, 0.1))


__all__ = ["DatasetRegistry"]
