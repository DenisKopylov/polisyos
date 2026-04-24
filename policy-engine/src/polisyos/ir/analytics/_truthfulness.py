"""IR-local truthfulness receipt types used by analytics contracts.

These contracts mirror the runtime truthfulness surface without importing
`polisyos.core`, which keeps the `common -> ir -> core` dependency order clean.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TruthfulnessTier(str, Enum):
    """Normalized epistemic strength of a runtime truthfulness claim."""

    UNVERIFIED = "unverified"
    APPROXIMATE_CALIBRATED = "approximate_calibrated"
    ASYMPTOTIC = "asymptotic"
    EXACT = "exact"


class TruthfulnessScope(str, Enum):
    """Scope under which a truthfulness tier is asserted."""

    POSTERIOR = "posterior"
    MARGINAL_COVERAGE = "marginal_coverage"
    CONDITIONAL_COVERAGE = "conditional_coverage"
    PREDICTIVE_CALIBRATION = "predictive_calibration"
    DECISION_REGRET = "decision_regret"


class TruthfulnessStatus(str, Enum):
    """Reconciliation status between declared and runtime truthfulness."""

    MISSING_BOTH = "missing_both"
    CATALOG_ONLY = "catalog_only"
    RUNTIME_ONLY = "runtime_only"
    RUNTIME_DOWNGRADED = "runtime_downgraded"
    RUNTIME_CONSISTENT = "runtime_consistent"
    CATALOG_UNDERCLAIMS = "catalog_underclaims"


_TRUTHFULNESS_DEPTH = {
    TruthfulnessTier.UNVERIFIED: 0,
    TruthfulnessTier.APPROXIMATE_CALIBRATED: 1,
    TruthfulnessTier.ASYMPTOTIC: 2,
    TruthfulnessTier.EXACT: 3,
}


def parse_truthfulness_tier(value: str | TruthfulnessTier | None) -> TruthfulnessTier | None:
    """Parse truthfulness tier helper."""

    if value is None:
        return None
    if isinstance(value, TruthfulnessTier):
        return value
    normalized = str(value).strip().lower()
    if not normalized:
        return None
    try:
        return TruthfulnessTier(normalized)
    except ValueError:
        return None


def truthfulness_depth(value: str | TruthfulnessTier | None) -> int:
    """Return numeric rank depth for a truthfulness tier."""

    tier = parse_truthfulness_tier(value)
    if tier is None:
        return 0
    return _TRUTHFULNESS_DEPTH[tier]


def reconcile_truthfulness_tiers(
    declared: str | TruthfulnessTier | None,
    runtime: str | TruthfulnessTier | None,
) -> tuple[TruthfulnessTier, TruthfulnessStatus]:
    """Conservatively reconcile catalog and runtime truthfulness signals."""

    declared_tier = parse_truthfulness_tier(declared)
    runtime_tier = parse_truthfulness_tier(runtime)
    if declared_tier is None and runtime_tier is None:
        return TruthfulnessTier.UNVERIFIED, TruthfulnessStatus.MISSING_BOTH
    if runtime_tier is None:
        return declared_tier or TruthfulnessTier.UNVERIFIED, TruthfulnessStatus.CATALOG_ONLY
    if declared_tier is None:
        return runtime_tier, TruthfulnessStatus.RUNTIME_ONLY
    if truthfulness_depth(runtime_tier) < truthfulness_depth(declared_tier):
        return runtime_tier, TruthfulnessStatus.RUNTIME_DOWNGRADED
    if truthfulness_depth(runtime_tier) == truthfulness_depth(declared_tier):
        return runtime_tier, TruthfulnessStatus.RUNTIME_CONSISTENT
    return declared_tier, TruthfulnessStatus.CATALOG_UNDERCLAIMS


class TruthfulnessReceipt(BaseModel):
    """Canonical runtime receipt describing truthfulness certification evidence."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    declared_truthfulness_tier: TruthfulnessTier | None = None
    runtime_truthfulness_tier: TruthfulnessTier | None = None
    effective_truthfulness_tier: TruthfulnessTier | None = None
    truthfulness_scope: TruthfulnessScope | None = None
    status: TruthfulnessStatus | None = None
    diagnostics: dict[str, Any] = Field(default_factory=dict)
    degradation_reasons: tuple[str, ...] = Field(default_factory=tuple)
    evidence_ref: str | None = None
    certificate_version: str = "1.0"

    @model_validator(mode="after")
    def _reconcile_defaults(self) -> TruthfulnessReceipt:
        if self.effective_truthfulness_tier is None or self.status is None:
            effective, status = reconcile_truthfulness_tiers(
                self.declared_truthfulness_tier,
                self.runtime_truthfulness_tier,
            )
            if self.effective_truthfulness_tier is None:
                object.__setattr__(self, "effective_truthfulness_tier", effective)
            if self.status is None:
                object.__setattr__(self, "status", status)
        return self


__all__ = [
    "TruthfulnessReceipt",
    "TruthfulnessScope",
    "TruthfulnessStatus",
    "TruthfulnessTier",
    "reconcile_truthfulness_tiers",
    "truthfulness_depth",
]
