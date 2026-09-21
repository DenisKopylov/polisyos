"""Observation period helpers owned by the Ukraine Data Forge domain.

This module owns the small calendar projection shared by normalized source
builders and household observation consumers.  Invalid or missing period
identifiers remain typed absence at the series boundary; they are never
coerced into a concrete period.
"""

from __future__ import annotations

import calendar
import re
from datetime import date

import pandas as pd

from polisyos.ir.model_layer.types import TimeFrequency


# Kept as a compatibility surface for callers that used the old common.py
# table.  Calendar-aware code below deliberately uses calendar.monthrange so
# leap years cannot inherit the old fixed-February bound.
MONTHLY_END_MONTH = {
    1: 31,
    2: 28,
    3: 31,
    4: 30,
    5: 31,
    6: 30,
    7: 31,
    8: 31,
    9: 30,
    10: 31,
    11: 30,
    12: 31,
}


OBSERVATION_FRAME_COLUMNS = [
    "observation_id",
    "family",
    "time_grain",
    "period_start",
    "period_end",
    "entity_scope",
    "entity_id",
    "cell_id",
    "region_code",
    "sector_id",
    "metric_id",
    "observed_value",
    "unit",
    "coverage_estimate",
    "measurement_bias_flag",
    "censoring_mask",
    "trust_weight",
    "lag_days_estimate",
    "source_id",
    "source_version",
    "regime_id",
    "shock_mask",
    "schema_regime_id",
    "identification_mode",
    "source_confidence_tier",
    "proxy_source_id",
]


_YEAR_PATTERN = re.compile(r"^(?P<year>\d{4})$")
_QUARTER_PATTERN = re.compile(r"^(?P<year>\d{4})[-_/]?Q(?P<quarter>[1-4])$")
_MONTH_PATTERN = re.compile(r"^(?P<year>\d{4})[-_/]?M(?P<month>\d{1,2})$")
_DATE_PATTERN = re.compile(r"^(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2})$")
_NUMERIC_MONTH_PATTERN = re.compile(r"^(?P<year>\d{4})[-_/]?(?P<month>\d{2})$")


def _is_missing_period(value: object) -> bool:
    """Return whether a scalar period value is missing or blank."""
    if value is None or value is pd.NA:
        return True
    try:
        missing = pd.isna(value)
    except (TypeError, ValueError):
        return False
    try:
        return bool(missing)
    except (TypeError, ValueError):
        return False


def _period_to_dates(period_value: object, time_grain: TimeFrequency) -> tuple[date, date]:
    """Convert one declared period identifier into inclusive ISO boundaries.

    Raises:
        ValueError: If the identifier is missing, malformed, or outside the
            calendar range for its declared format.
    """
    if _is_missing_period(period_value):
        raise ValueError("period identifier is missing")

    text = str(period_value).strip()
    normalized = text.upper()
    if not normalized or normalized in {"<NA>", "NAN", "NAT"}:
        raise ValueError("period identifier is empty or missing")

    year: int
    month: int = 1
    quarter_from_text: int | None = None
    day_from_text: int | None = None

    if match := _YEAR_PATTERN.fullmatch(normalized):
        year = int(match.group("year"))
    elif match := _QUARTER_PATTERN.fullmatch(normalized):
        year = int(match.group("year"))
        quarter_from_text = int(match.group("quarter"))
        month = (quarter_from_text - 1) * 3 + 1
    elif match := _MONTH_PATTERN.fullmatch(normalized):
        year = int(match.group("year"))
        month = int(match.group("month"))
    elif match := _DATE_PATTERN.fullmatch(normalized):
        year = int(match.group("year"))
        month = int(match.group("month"))
        day_from_text = int(match.group("day"))
    elif match := _NUMERIC_MONTH_PATTERN.fullmatch(normalized):
        year = int(match.group("year"))
        month = int(match.group("month"))
    else:
        raise ValueError(f"unrecognized period identifier: {text!r}")

    if not 1 <= month <= 12:
        raise ValueError(f"period month is outside 1..12: {month}")
    days_in_month = calendar.monthrange(year, month)[1]
    if day_from_text is not None and not 1 <= day_from_text <= days_in_month:
        raise ValueError(f"period day is outside the calendar month: {text!r}")

    if time_grain == TimeFrequency.YEAR:
        return date(year, 1, 1), date(year, 12, 31)
    if time_grain == TimeFrequency.QUARTER:
        quarter = quarter_from_text or ((month - 1) // 3 + 1)
        start_month = (quarter - 1) * 3 + 1
        end_month = start_month + 2
        return date(year, start_month, 1), date(
            year,
            end_month,
            calendar.monthrange(year, end_month)[1],
        )
    if time_grain != TimeFrequency.MONTH:
        raise ValueError(f"unsupported time grain: {time_grain!r}")
    return date(year, month, 1), date(year, month, days_in_month)


def _period_cache_key(value: object) -> str | None:
    """Return a stable cache key for a scalar period, or ``None`` if absent."""
    if _is_missing_period(value):
        return None
    text = str(value).strip()
    if not text or text.upper() in {"<NA>", "NAN", "NAT"}:
        return None
    return text.upper()


def _period_series_to_iso_bounds(
    values: pd.Series,
    *,
    time_grain: TimeFrequency,
) -> tuple[pd.Series, pd.Series]:
    """Project period identifiers to aligned ISO-bound series.

    Periods are parsed once per unique non-missing key.  Invalid or missing
    keys remain ``pd.NA`` at their original positions, allowing a caller to
    quarantine the row or preserve typed absence without inventing a date.
    """
    raw = values.copy() if isinstance(values, pd.Series) else pd.Series(values)
    starts = pd.Series(pd.NA, index=raw.index, dtype="string")
    ends = pd.Series(pd.NA, index=raw.index, dtype="string")
    mapping: dict[str, tuple[date, date] | None] = {}

    for value in raw.tolist():
        key = _period_cache_key(value)
        if key is None or key in mapping:
            continue
        try:
            mapping[key] = _period_to_dates(value, time_grain)
        except (TypeError, ValueError):
            mapping[key] = None

    for index, value in raw.items():
        key = _period_cache_key(value)
        bounds = mapping.get(key) if key is not None else None
        if bounds is None:
            continue
        starts.at[index] = bounds[0].isoformat()
        ends.at[index] = bounds[1].isoformat()
    return starts, ends


__all__ = ("MONTHLY_END_MONTH", "OBSERVATION_FRAME_COLUMNS")
