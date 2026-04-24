"""Declarative static rule tables for funnel validation.

These tables are consumed by Level 0 (static validator) and Level 1
(cheap heuristics).  Keep them purely declarative — no I/O, no imports
of heavy dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# ---------------------------------------------------------------------------
# Forbidden policy combinations
# ---------------------------------------------------------------------------

# Keys are intervention types; values are sets of conflicting types.
# If a candidate contains BOTH the key AND any member of the value set
# simultaneously, it is flagged.
FORBIDDEN_COMBINATIONS: dict[str, set[str]] = {
    "carbon_tax": {"fossil_subsidy", "fossil_fuel_subsidy"},
    "fossil_subsidy": {"carbon_tax", "emission_cap"},
    "price_cap": {"market_deregulation", "price_liberalization"},
    "market_deregulation": {"price_cap", "price_floor"},
    "import_ban": {"free_trade_agreement"},
    "free_trade_agreement": {"import_ban", "import_quota"},
    "rent_control": {"housing_deregulation"},
    "minimum_wage_increase": {"wage_subsidy_removal"},
}

# ---------------------------------------------------------------------------
# Parameter domain rules
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class DomainRule:
    """Declarative parameter domain constraint."""

    pattern: str  # substring match on parameter name (case-insensitive)
    lower: float | None = None
    upper: float | None = None
    description: str = ""


PARAMETER_DOMAIN_RULES: list[DomainRule] = [
    DomainRule(pattern="rate", lower=0.0, upper=1.0, description="Rates must be in [0, 1]"),
    DomainRule(pattern="tax", lower=0.0, upper=1.0, description="Tax rates must be in [0, 1]"),
    DomainRule(
        pattern="probability", lower=0.0, upper=1.0, description="Probabilities must be in [0, 1]"
    ),
    DomainRule(pattern="share", lower=0.0, upper=1.0, description="Shares must be in [0, 1]"),
    DomainRule(pattern="fraction", lower=0.0, upper=1.0, description="Fractions must be in [0, 1]"),
    DomainRule(
        pattern="percentage", lower=0.0, upper=100.0, description="Percentages must be in [0, 100]"
    ),
    DomainRule(
        pattern="subsidy", lower=0.0, upper=None, description="Subsidies must be non-negative"
    ),
    DomainRule(
        pattern="duration", lower=0.0, upper=None, description="Durations must be non-negative"
    ),
    DomainRule(pattern="count", lower=0.0, upper=None, description="Counts must be non-negative"),
]

# Absolute parameter magnitude cap (anything beyond is suspicious).
EXTREME_VALUE_THRESHOLD: float = 1e6

# ---------------------------------------------------------------------------
# Unit / dimension consistency
# ---------------------------------------------------------------------------

# Maps parameter-name pattern → expected dimension label.
UNIT_CONSISTENCY_MAP: dict[str, str] = {
    "rate": "ratio",
    "tax": "ratio",
    "subsidy": "currency",
    "spending": "currency",
    "budget": "currency",
    "gdp": "currency",
    "population": "count",
    "duration": "time",
    "age": "time",
}

# ---------------------------------------------------------------------------
# Fiscal sanity bounds
# ---------------------------------------------------------------------------

# Upper-bound sanity for fiscal parameters (in abstract units).
# Policy spending greater than MAX_FISCAL_RATIO × declared GDP is rejected.
MAX_FISCAL_RATIO: float = 2.0

# ---------------------------------------------------------------------------
# Legal red-flag patterns
# ---------------------------------------------------------------------------

# Intervention type substrings that require special scrutiny.
LEGAL_RED_FLAGS: list[str] = [
    "forced_",
    "compulsory_",
    "confiscation",
    "expropriation",
    "surveillance",
    "ethnic_",
    "racial_",
    "religious_",
]

# ---------------------------------------------------------------------------
# Policy conflict rules (Level 1 heuristic)
# ---------------------------------------------------------------------------

# Intervention-type pairs that are not *forbidden* but create policy tension.
# Each entry maps an intervention type to a set of conflicting types with a
# tension score in (0, 1].
CONFLICT_RULES: dict[str, dict[str, float]] = {
    "austerity": {"stimulus": 0.9, "spending_increase": 0.8},
    "stimulus": {"austerity": 0.9, "spending_cut": 0.8},
    "trade_liberalization": {"domestic_protection": 0.7},
    "domestic_protection": {"trade_liberalization": 0.7},
    "monetary_tightening": {"fiscal_expansion": 0.6},
    "fiscal_expansion": {"monetary_tightening": 0.6},
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def check_forbidden_combinations(
    intervention_types: list[str],
) -> list[tuple[str, str]]:
    """Return pairs of interventions that violate forbidden-combination rules."""
    type_set = set(intervention_types)
    violations: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for itype in intervention_types:
        forbidden = FORBIDDEN_COMBINATIONS.get(itype, set())
        for conflict in forbidden & type_set:
            pair = tuple(sorted((itype, conflict)))
            if pair not in seen:
                seen.add(pair)
                violations.append(pair)
    return violations


def check_parameter_domains(
    name: str,
    value: Any,
) -> list[str]:
    """Return list of violation messages for a single parameter."""
    if not isinstance(value, (int, float)):
        return []

    issues: list[str] = []

    # NaN / Inf checks
    if value != value:  # NaN
        issues.append(f"{name}: NaN value")
        return issues
    if abs(value) == float("inf"):
        issues.append(f"{name}: infinite value")
        return issues

    # Extreme value check
    if abs(value) > EXTREME_VALUE_THRESHOLD:
        issues.append(f"{name}: extreme value ({value}), exceeds ±{EXTREME_VALUE_THRESHOLD}")

    # Domain rules
    name_lower = name.lower()
    for rule in PARAMETER_DOMAIN_RULES:
        if rule.pattern in name_lower:
            if rule.lower is not None and value < rule.lower:
                issues.append(f"{name}: {value} < {rule.lower} ({rule.description})")
            if rule.upper is not None and value > rule.upper:
                issues.append(f"{name}: {value} > {rule.upper} ({rule.description})")

    return issues


def check_legal_red_flags(intervention_type: str) -> list[str]:
    """Return legal red-flag matches for an intervention type."""
    lower = intervention_type.lower()
    return [flag for flag in LEGAL_RED_FLAGS if flag in lower]


def compute_conflict_score(intervention_types: list[str]) -> float:
    """Return max conflict tension score among all intervention pairs."""
    max_score = 0.0
    type_set = set(intervention_types)
    for itype in intervention_types:
        conflicts = CONFLICT_RULES.get(itype, {})
        for conflict_type, score in conflicts.items():
            if conflict_type in type_set:
                max_score = max(max_score, score)
    return max_score
