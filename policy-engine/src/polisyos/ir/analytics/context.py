"""Public analytics context module API."""
from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ContextProfileInferenceLevel(str, Enum):
    """Context profile inference level public type."""
    INFERRED_BASIC = "inferred_basic"
    ENRICHED = "enriched"
    MANUAL = "manual"


class IncomeLevel(str, Enum):
    """Income level public type."""
    LOW = "low"
    LOWER_MIDDLE = "lower_middle"
    UPPER_MIDDLE = "upper_middle"
    HIGH = "high"
    NON_HIGH = "non_high"
    UNKNOWN = "unknown"


class ContextProfile(BaseModel):
    """Context profile for transport-aware literature reuse."""

    model_config = ConfigDict(extra="forbid")

    context_id: str = ""
    context_label: str = ""
    countries: list[str] = Field(default_factory=list)
    income_level: IncomeLevel = IncomeLevel.UNKNOWN
    publication_year: int | None = None
    time_period: str = ""
    institutional_quality: float | None = None
    corruption_level: float | None = None
    state_capacity: float | None = None
    social_trust: float | None = None
    cultural_cluster: str | None = None
    gdp_per_capita: float | None = None
    economic_openness: float | None = None
    post_communist: bool = False
    post_conflict: bool = False
    inference_level: ContextProfileInferenceLevel = ContextProfileInferenceLevel.INFERRED_BASIC
    data_sources: list[str] = Field(default_factory=list)

    def distance_to(self, other: "ContextProfile") -> float:
        """
        Context distance in [0,1] for transportability scoring.

        The score is a weighted blend of structural country traits, socioeconomic deltas
        and temporal mismatch.
        """
        weighted_distance = 0.0
        total_weight = 0.0

        def _add(weight: float, dist: float) -> None:
            nonlocal weighted_distance, total_weight
            weighted_distance += max(0.0, min(1.0, float(dist))) * weight
            total_weight += weight

        if self.context_id and other.context_id:
            _add(0.35, 0.0 if self.context_id == other.context_id else 1.0)

        income_left = _income_level_score(self.income_level)
        income_right = _income_level_score(other.income_level)
        if income_left is not None and income_right is not None:
            _add(1.0, abs(income_left - income_right))

        for field_name, weight in (
            ("institutional_quality", 1.5),
            ("corruption_level", 1.0),
            ("state_capacity", 1.0),
            ("social_trust", 1.0),
            ("economic_openness", 0.75),
        ):
            lhs = getattr(self, field_name)
            rhs = getattr(other, field_name)
            if lhs is None or rhs is None:
                continue
            _add(weight, abs(float(lhs) - float(rhs)))

        if self.gdp_per_capita is not None and other.gdp_per_capita is not None:
            denom = max(abs(float(self.gdp_per_capita)), abs(float(other.gdp_per_capita)), 1.0)
            _add(0.75, abs(float(self.gdp_per_capita) - float(other.gdp_per_capita)) / denom)

        left_year = self.publication_year or _extract_year_from_period(self.time_period)
        right_year = other.publication_year or _extract_year_from_period(other.time_period)
        if left_year is not None and right_year is not None:
            _add(0.5, min(abs(left_year - right_year) / 30.0, 1.0))

        _add(2.0, 1.0 if self.post_communist != other.post_communist else 0.0)
        _add(1.5, 1.0 if self.post_conflict != other.post_conflict else 0.0)

        if total_weight <= 0.0:
            return 0.0
        return max(0.0, min(1.0, weighted_distance / total_weight))

    def enrich_from_datasources(
        self,
        wgi: Any,
        wvs: Any,
        wdi: Any,
        year: int | None = None,
    ) -> "ContextProfile":
        """
        Best-effort enrichment of inferred context using optional datasource clients.

        Clients are intentionally duck-typed to keep this IR package dependency-light.
        """
        resolved_year = (
            year
            or self.publication_year
            or _extract_year_from_period(self.time_period)
            or 2020
        )
        wgi_data = _safe_get_indicators(wgi, self.context_id, resolved_year)
        wdi_data = _safe_get_indicators(wdi, self.context_id, resolved_year)
        wvs_data = _safe_get_wvs_indicators(wvs, self.context_id, resolved_year)

        update = {
            "inference_level": ContextProfileInferenceLevel.ENRICHED,
            "data_sources": sorted(
                set(self.data_sources)
                | {"wgi" if wgi_data else ""}
                | {"wvs" if wvs_data else ""}
                | {"wdi" if wdi_data else ""}
                - {""}
            ),
            "institutional_quality": _coalesce_numeric(
                wgi_data.get("institutional_quality") if wgi_data else None,
                self.institutional_quality,
            ),
            "corruption_level": _coalesce_numeric(
                wgi_data.get("corruption_level") if wgi_data else None,
                self.corruption_level,
            ),
            "state_capacity": _coalesce_numeric(
                wgi_data.get("state_capacity") if wgi_data else None,
                self.state_capacity,
            ),
            "social_trust": _coalesce_numeric(
                wvs_data.get("social_trust") if wvs_data else None,
                self.social_trust,
            ),
            "cultural_cluster": (
                str(wvs_data.get("cultural_cluster"))
                if wvs_data and wvs_data.get("cultural_cluster") is not None
                else self.cultural_cluster
            ),
            "gdp_per_capita": _coalesce_numeric(
                wdi_data.get("gdp_per_capita") if wdi_data else None,
                self.gdp_per_capita,
            ),
            "economic_openness": _coalesce_numeric(
                wdi_data.get("economic_openness") if wdi_data else None,
                self.economic_openness,
            ),
        }
        return self.model_copy(update=update)


def _income_level_score(value: IncomeLevel | str | None) -> float | None:
    order: dict[str, float] = {
        IncomeLevel.LOW.value: 0.0,
        IncomeLevel.LOWER_MIDDLE.value: 0.33,
        IncomeLevel.UPPER_MIDDLE.value: 0.67,
        IncomeLevel.HIGH.value: 1.0,
        IncomeLevel.NON_HIGH.value: 0.5,
        IncomeLevel.UNKNOWN.value: 0.5,
    }
    if value is None:
        return None
    return order.get(str(value), 0.5)


def _extract_year_from_period(value: str) -> int | None:
    token = (value or "").strip()
    if not token:
        return None
    for chunk in token.replace("/", "-").split("-"):
        chunk = chunk.strip()
        if len(chunk) == 4 and chunk.isdigit():
            try:
                return int(chunk)
            except ValueError:
                return None
    return None


def _safe_get_indicators(client: Any, context_id: str, year: int) -> dict[str, Any]:
    if client is None:
        return {}
    getter = getattr(client, "get_indicators", None)
    if not callable(getter):
        return {}
    try:
        payload = getter(context_id, year)
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _safe_get_wvs_indicators(client: Any, context_id: str, year: int) -> dict[str, Any]:
    if client is None:
        return {}
    finder = getattr(client, "find_closest_in_wave", None)
    getter = getattr(client, "get_indicators", None)
    if not callable(getter):
        return {}
    survey_year = year
    if callable(finder):
        try:
            result = finder(context_id, year, max_distance_years=3)
            if isinstance(result, tuple) and result:
                candidate = result[0]
                if isinstance(candidate, int):
                    survey_year = candidate
        except Exception:
            survey_year = year
    try:
        payload = getter(context_id, survey_year=survey_year)
    except TypeError:
        try:
            payload = getter(context_id, survey_year)
        except Exception:
            return {}
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _coalesce_numeric(candidate: Any, fallback: float | None) -> float | None:
    if candidate is None:
        return fallback
    try:
        return float(candidate)
    except (TypeError, ValueError):
        return fallback


__all__ = ["ContextProfile", "ContextProfileInferenceLevel", "IncomeLevel"]
