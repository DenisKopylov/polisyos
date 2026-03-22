"""Comparator stack helpers shared by benchmark entrypoints."""

from __future__ import annotations

from collections import OrderedDict
from typing import Any

from benchmarks.runtime import module_available


REQUIRED_ACCEPTANCE_COMPARATORS: "OrderedDict[str, str]" = OrderedDict(
    [
        ("econml", "econml"),
        ("zepid", "zepid"),
        ("stochtree", "stochtree"),
        ("dowhy", "dowhy"),
        ("y0", "y0"),
        ("lightgbm", "lightgbm"),
    ]
)

OPTIONAL_LEGACY_COMPARATORS: "OrderedDict[str, str]" = OrderedDict(
    [
        ("bartpy", "bartpy"),
        ("pymc_bart", "pymc-bart"),
    ]
)


def comparator_distribution_names() -> dict[str, str]:
    """Return distribution names for the canonical acceptance comparators."""
    return dict(REQUIRED_ACCEPTANCE_COMPARATORS)


def comparator_required_modules() -> dict[str, bool]:
    """Return module availability flags for the canonical acceptance comparators."""
    return {label: module_available(module_name) for label, module_name in REQUIRED_ACCEPTANCE_COMPARATORS.items()}


def build_research_acceptance_comparator_status() -> dict[str, str]:
    """Build a status map suitable for `preflight.comparator_status`."""
    return {
        label: ("available" if module_available(module_name) else "missing")
        for label, module_name in REQUIRED_ACCEPTANCE_COMPARATORS.items()
    }


def comparator_degraded_reasons(status: dict[str, Any]) -> list[str]:
    """Render human-readable degraded reasons from a comparator status map."""
    reasons: list[str] = []
    for label, value in status.items():
        if str(value) != "available":
            reasons.append(f"{label} comparator unavailable")
    return reasons

