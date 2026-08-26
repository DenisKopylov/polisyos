"""Temporal constraint parsing helpers."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta

from polisyos.common.timestamps import parse_iso_date

_MONTHS = {
    "січня": 1,
    "лютого": 2,
    "березня": 3,
    "квітня": 4,
    "травня": 5,
    "червня": 6,
    "липня": 7,
    "серпня": 8,
    "вересня": 9,
    "жовтня": 10,
    "листопада": 11,
    "грудня": 12,
}


@dataclass(frozen=True)
class TemporalConstraint:
    """Temporal constraint public type."""

    constraint_type: str
    effective_from_iso: str | None
    effective_to_iso: str | None
    raw_text_uk: str
    resolved: bool
    resolution_method: str
    confidence: float
    anchor_date_kind: str = ""
    offset_days: int = 0
    offset_months: int = 0
    offset_years: int = 0
    state_hint: str = ""


_DATE_PATTERN = (
    r"(\d{1,2})\s+"
    r"(січня|лютого|березня|квітня|травня|червня|липня|серпня|вересня|жовтня|листопада|грудня)\s+"
    r"(\d{4})\s+року"
)
_DATE_INTERVAL_RE = re.compile(
    rf"(?:з|починаючи\s+з)\s+{_DATE_PATTERN}\s+(?:до|по)\s+{_DATE_PATTERN}",
    re.IGNORECASE,
)
_FIXED_START_RE = re.compile(
    rf"(?:з|починаючи\s+з)\s+{_DATE_PATTERN}",
    re.IGNORECASE,
)
_FIXED_END_RE = re.compile(
    rf"(?:до|по)\s+{_DATE_PATTERN}",
    re.IGNORECASE,
)
_LOSS_OF_FORCE_FIXED_RE = re.compile(
    rf"(?:втрачає|втратив|втрачають)\s+чинність(?:\s+з)?\s+{_DATE_PATTERN}",
    re.IGNORECASE,
)
_ENTRY_PUBLICATION_RE = re.compile(
    r"набирає\s+чинності?\s+з\s+дня\s+(?:його\s+)?(опублікування|прийняття)",
    re.IGNORECASE,
)
_ENTRY_AFTER_OFFSET_RE = re.compile(
    r"набирає\s+чинності?\s+через\s+(\d+)\s+"
    r"(дн(?:ів|і|ень)|місяц(?:ів|і|ь)|рок(?:ів|и|у))\s+"
    r"з\s+дня\s+(опублікування|прийняття)",
    re.IGNORECASE,
)
_RELATIVE_AFTER_OFFSET_RE = re.compile(
    r"через\s+(\d+)\s+"
    r"(дн(?:ів|і|ень)|місяц(?:ів|і|ь)|рок(?:ів|и|у))\s+"
    r"з\s+дня\s+(опублікування|прийняття)",
    re.IGNORECASE,
)
_LOSS_OF_FORCE_PUBLICATION_RE = re.compile(
    r"(?:втрачає|втратив|втрачають)\s+чинність\s+з\s+дня\s+(опублікування|прийняття)",
    re.IGNORECASE,
)
_LOSS_OF_FORCE_AFTER_OFFSET_RE = re.compile(
    r"(?:втрачає|втратив|втрачають)\s+чинність\s+через\s+(\d+)\s+"
    r"(дн(?:ів|і|ень)|місяц(?:ів|і|ь)|рок(?:ів|и|у))\s+"
    r"з\s+дня\s+(опублікування|прийняття)",
    re.IGNORECASE,
)
_SUSPENSION_INTERVAL_RE = re.compile(
    rf"(?:дію(?:\s+\w+){{0,4}}?\s+зупинено|зупиняється\s+дія)"
    rf"(?:\s+з\s+{_DATE_PATTERN})?\s+(?:до|по)\s+{_DATE_PATTERN}",
    re.IGNORECASE,
)
_SUSPENSION_OPEN_RE = re.compile(
    r"(?:дію(?:\s+\w+){0,4}?\s+зупинено|зупиняється\s+дія)",
    re.IGNORECASE,
)


def _iso_from_ua_date(day: str, month_name: str, year: str) -> str:
    month = _MONTHS.get(month_name.lower(), 1)
    return f"{int(year):04d}-{month:02d}-{int(day):02d}"


def _add_months(base_date: date, months: int) -> date:
    month0 = (base_date.month - 1) + months
    year = base_date.year + month0 // 12
    month = month0 % 12 + 1
    if month == 2:
        leap = year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
        max_day = 29 if leap else 28
    elif month in {4, 6, 9, 11}:
        max_day = 30
    else:
        max_day = 31
    return date(year, month, min(base_date.day, max_day))


def _apply_relative_offset(
    *,
    base_iso: str | None,
    days: int = 0,
    months: int = 0,
    years: int = 0,
) -> str | None:
    base_date = parse_iso_date(base_iso)
    if base_date is None:
        return None
    shifted = base_date + timedelta(days=days)
    if months:
        shifted = _add_months(shifted, months)
    if years:
        shifted = _add_months(shifted, years * 12)
    return shifted.isoformat()


def _relative_anchor_iso(
    *,
    anchor_kind: str,
    publication_date_iso: str | None,
    adoption_date_iso: str | None,
) -> str | None:
    if anchor_kind == "publication":
        return publication_date_iso
    if anchor_kind == "adoption":
        return adoption_date_iso
    return None


def _offset_parts(
    amount_text: str,
    unit_text: str,
) -> tuple[int, int, int]:
    amount = int(amount_text)
    unit = unit_text.lower()
    if unit.startswith("дн"):
        return amount, 0, 0
    if unit.startswith("місяц"):
        return 0, amount, 0
    return 0, 0, amount


def _relative_constraint(
    *,
    constraint_type: str,
    raw_text_uk: str,
    anchor_kind: str,
    confidence: float,
    publication_date_iso: str | None,
    adoption_date_iso: str | None,
    offset_days: int = 0,
    offset_months: int = 0,
    offset_years: int = 0,
    state_hint: str = "",
    use_as_effective_to: bool = False,
) -> TemporalConstraint:
    anchor_iso = _relative_anchor_iso(
        anchor_kind=anchor_kind,
        publication_date_iso=publication_date_iso,
        adoption_date_iso=adoption_date_iso,
    )
    resolved_iso = _apply_relative_offset(
        base_iso=anchor_iso,
        days=offset_days,
        months=offset_months,
        years=offset_years,
    )
    return TemporalConstraint(
        constraint_type=constraint_type,
        effective_from_iso=None if use_as_effective_to else resolved_iso,
        effective_to_iso=resolved_iso if use_as_effective_to else None,
        raw_text_uk=raw_text_uk,
        resolved=bool(resolved_iso),
        resolution_method="pattern+anchor" if resolved_iso else "pattern",
        confidence=confidence,
        anchor_date_kind=anchor_kind,
        offset_days=offset_days,
        offset_months=offset_months,
        offset_years=offset_years,
        state_hint=state_hint,
    )


def parse_temporal_constraints(
    text: str,
    *,
    publication_date_iso: str | None = None,
    adoption_date_iso: str | None = None,
) -> list[TemporalConstraint]:
    """Parse temporal constraints helper."""
    constraints: list[TemporalConstraint] = []
    if not text.strip():
        return constraints

    for match in _DATE_INTERVAL_RE.finditer(text):
        start_day, start_month, start_year, end_day, end_month, end_year = match.groups()
        constraints.append(
            TemporalConstraint(
                constraint_type="closed_interval",
                effective_from_iso=_iso_from_ua_date(start_day, start_month, start_year),
                effective_to_iso=_iso_from_ua_date(end_day, end_month, end_year),
                raw_text_uk=match.group(0),
                resolved=True,
                resolution_method="pattern",
                confidence=0.98,
                state_hint="current",
            )
        )

    for match in _LOSS_OF_FORCE_FIXED_RE.finditer(text):
        day, month_name, year = match.groups()
        constraints.append(
            TemporalConstraint(
                constraint_type="loss_of_force",
                effective_from_iso=None,
                effective_to_iso=_iso_from_ua_date(day, month_name, year),
                raw_text_uk=match.group(0),
                resolved=True,
                resolution_method="pattern",
                confidence=0.96,
                state_hint="historical",
            )
        )

    for match in _FIXED_START_RE.finditer(text):
        day, month_name, year = match.groups()
        constraints.append(
            TemporalConstraint(
                constraint_type="fixed_start",
                effective_from_iso=_iso_from_ua_date(day, month_name, year),
                effective_to_iso=None,
                raw_text_uk=match.group(0),
                resolved=True,
                resolution_method="pattern",
                confidence=0.95,
                state_hint="current",
            )
        )

    for match in _FIXED_END_RE.finditer(text):
        day, month_name, year = match.groups()
        constraints.append(
            TemporalConstraint(
                constraint_type="fixed_end",
                effective_from_iso=None,
                effective_to_iso=_iso_from_ua_date(day, month_name, year),
                raw_text_uk=match.group(0),
                resolved=True,
                resolution_method="pattern",
                confidence=0.9,
            )
        )

    for match in _ENTRY_PUBLICATION_RE.finditer(text):
        anchor_kind = "publication" if match.group(1).lower().startswith("опуб") else "adoption"
        constraints.append(
            _relative_constraint(
                constraint_type="relative_to_anchor",
                raw_text_uk=match.group(0),
                anchor_kind=anchor_kind,
                confidence=0.92,
                publication_date_iso=publication_date_iso,
                adoption_date_iso=adoption_date_iso,
                state_hint="future" if anchor_kind == "publication" else "current",
            )
        )

    for match in _ENTRY_AFTER_OFFSET_RE.finditer(text):
        amount_text, unit_text, anchor_text = match.groups()
        offset_days, offset_months, offset_years = _offset_parts(amount_text, unit_text)
        anchor_kind = "publication" if anchor_text.lower().startswith("опуб") else "adoption"
        constraints.append(
            _relative_constraint(
                constraint_type="relative_to_anchor",
                raw_text_uk=match.group(0),
                anchor_kind=anchor_kind,
                confidence=0.9,
                publication_date_iso=publication_date_iso,
                adoption_date_iso=adoption_date_iso,
                offset_days=offset_days,
                offset_months=offset_months,
                offset_years=offset_years,
                state_hint="future",
            )
        )

    for match in _RELATIVE_AFTER_OFFSET_RE.finditer(text):
        amount_text, unit_text, anchor_text = match.groups()
        offset_days, offset_months, offset_years = _offset_parts(amount_text, unit_text)
        anchor_kind = "publication" if anchor_text.lower().startswith("опуб") else "adoption"
        constraints.append(
            _relative_constraint(
                constraint_type="relative_to_anchor",
                raw_text_uk=match.group(0),
                anchor_kind=anchor_kind,
                confidence=0.78,
                publication_date_iso=publication_date_iso,
                adoption_date_iso=adoption_date_iso,
                offset_days=offset_days,
                offset_months=offset_months,
                offset_years=offset_years,
            )
        )

    for match in _LOSS_OF_FORCE_PUBLICATION_RE.finditer(text):
        anchor_kind = "publication" if match.group(1).lower().startswith("опуб") else "adoption"
        constraints.append(
            _relative_constraint(
                constraint_type="loss_of_force",
                raw_text_uk=match.group(0),
                anchor_kind=anchor_kind,
                confidence=0.88,
                publication_date_iso=publication_date_iso,
                adoption_date_iso=adoption_date_iso,
                state_hint="historical",
                use_as_effective_to=True,
            )
        )

    for match in _LOSS_OF_FORCE_AFTER_OFFSET_RE.finditer(text):
        amount_text, unit_text, anchor_text = match.groups()
        offset_days, offset_months, offset_years = _offset_parts(amount_text, unit_text)
        anchor_kind = "publication" if anchor_text.lower().startswith("опуб") else "adoption"
        constraints.append(
            _relative_constraint(
                constraint_type="loss_of_force",
                raw_text_uk=match.group(0),
                anchor_kind=anchor_kind,
                confidence=0.86,
                publication_date_iso=publication_date_iso,
                adoption_date_iso=adoption_date_iso,
                offset_days=offset_days,
                offset_months=offset_months,
                offset_years=offset_years,
                state_hint="historical",
                use_as_effective_to=True,
            )
        )

    for match in _SUSPENSION_INTERVAL_RE.finditer(text):
        groups = match.groups()
        if len(groups) == 6:
            start_day, start_month, start_year, end_day, end_month, end_year = groups
        else:
            start_day = start_month = start_year = ""
            end_day, end_month, end_year = groups[-3:]
        constraints.append(
            TemporalConstraint(
                constraint_type="suspension",
                effective_from_iso=(
                    _iso_from_ua_date(start_day, start_month, start_year)
                    if start_day and start_month and start_year
                    else None
                ),
                effective_to_iso=_iso_from_ua_date(end_day, end_month, end_year),
                raw_text_uk=match.group(0),
                resolved=True,
                resolution_method="pattern",
                confidence=0.9,
                state_hint="suspended",
            )
        )

    for match in _SUSPENSION_OPEN_RE.finditer(text):
        constraints.append(
            TemporalConstraint(
                constraint_type="suspension",
                effective_from_iso=None,
                effective_to_iso=None,
                raw_text_uk=match.group(0),
                resolved=False,
                resolution_method="pattern",
                confidence=0.7,
                state_hint="suspended",
            )
        )

    return constraints


__all__ = ["TemporalConstraint", "parse_temporal_constraints"]
