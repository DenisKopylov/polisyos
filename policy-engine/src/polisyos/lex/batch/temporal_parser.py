"""Temporal constraint parsing helpers."""

from __future__ import annotations

import re
from dataclasses import dataclass

_MONTHS = {
    "січня": "01",
    "лютого": "02",
    "березня": "03",
    "квітня": "04",
    "травня": "05",
    "червня": "06",
    "липня": "07",
    "серпня": "08",
    "вересня": "09",
    "жовтня": "10",
    "листопада": "11",
    "грудня": "12",
}


@dataclass(frozen=True)
class TemporalConstraint:
    constraint_type: str
    effective_from_iso: str | None
    effective_to_iso: str | None
    raw_text_uk: str
    resolved: bool
    resolution_method: str
    confidence: float


_FIXED_DATE_RE = re.compile(
    r"з\s+(\d{1,2})\s+(січня|лютого|березня|квітня|травня|червня|липня|серпня|вересня|жовтня|листопада|грудня)\s+(\d{4})\s+року",
    re.IGNORECASE,
)
_RELATIVE_PUBLICATION_RE = re.compile(
    r"через\s+(\d+)\s+місяц\w*\s+з\s+дня\s+(опублікування|прийняття)",
    re.IGNORECASE,
)
_ENTRY_PUBLICATION_RE = re.compile(
    r"набирає\s+чинності?\s+з\s+дня\s+(його\s+)?опублікування",
    re.IGNORECASE,
)


def parse_temporal_constraints(text: str) -> list[TemporalConstraint]:
    constraints: list[TemporalConstraint] = []
    for match in _FIXED_DATE_RE.finditer(text):
        day, month_name, year = match.groups()
        month = _MONTHS.get(month_name.lower(), "01")
        constraints.append(
            TemporalConstraint(
                constraint_type="fixed_date",
                effective_from_iso=f"{year}-{month}-{int(day):02d}",
                effective_to_iso=None,
                raw_text_uk=match.group(0),
                resolved=True,
                resolution_method="pattern",
                confidence=0.95,
            )
        )
    for match in _RELATIVE_PUBLICATION_RE.finditer(text):
        constraints.append(
            TemporalConstraint(
                constraint_type="relative_to_publication",
                effective_from_iso=None,
                effective_to_iso=None,
                raw_text_uk=match.group(0),
                resolved=False,
                resolution_method="pattern",
                confidence=0.7,
            )
        )
    for match in _ENTRY_PUBLICATION_RE.finditer(text):
        constraints.append(
            TemporalConstraint(
                constraint_type="relative_to_publication",
                effective_from_iso=None,
                effective_to_iso=None,
                raw_text_uk=match.group(0),
                resolved=False,
                resolution_method="pattern",
                confidence=0.9,
            )
        )
    return constraints
