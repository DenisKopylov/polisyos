"""Truthfulness tiers, receipts, and reconciliation helpers."""

from __future__ import annotations

from collections.abc import Mapping
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TruthfulnessTier(str, Enum):
    """Normalized epistemic strength of a runtime or catalog truthfulness claim."""

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


def parse_truthfulness_scope(value: str | TruthfulnessScope | None) -> TruthfulnessScope | None:
    """Parse truthfulness scope helper."""
    if value is None:
        return None
    if isinstance(value, TruthfulnessScope):
        return value
    normalized = str(value).strip().lower()
    if not normalized:
        return None
    try:
        return TruthfulnessScope(normalized)
    except ValueError:
        return None


def parse_truthfulness_status(value: str | TruthfulnessStatus | None) -> TruthfulnessStatus | None:
    """Parse truthfulness status helper."""
    if value is None:
        return None
    if isinstance(value, TruthfulnessStatus):
        return value
    normalized = str(value).strip().lower()
    if not normalized:
        return None
    try:
        return TruthfulnessStatus(normalized)
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


def validate_truthfulness_receipt(
    value: TruthfulnessReceipt | Mapping[str, Any] | None,
) -> TruthfulnessReceipt | None:
    """Validate a mapping-or-model as a `TruthfulnessReceipt`."""
    if value is None:
        return None
    if isinstance(value, TruthfulnessReceipt):
        return value
    if isinstance(value, Mapping):
        return TruthfulnessReceipt.model_validate(dict(value))
    raise TypeError("truthfulness receipt must be a mapping or TruthfulnessReceipt")


def extract_truthfulness_receipt(value: Any) -> TruthfulnessReceipt | None:
    """Extract a truthfulness receipt from common result and artifact shapes."""
    if value is None:
        return None
    try:
        if isinstance(value, TruthfulnessReceipt):
            return value
        if isinstance(value, Mapping):
            if "truthfulness_receipt" in value:
                return validate_truthfulness_receipt(value.get("truthfulness_receipt"))
            for nested in value.values():
                receipt = extract_truthfulness_receipt(nested)
                if receipt is not None:
                    return receipt
            return None
        attr = getattr(value, "truthfulness_receipt", None)
        if attr is not None:
            if isinstance(attr, TruthfulnessReceipt):
                return attr
            if isinstance(attr, Mapping):
                return validate_truthfulness_receipt(attr)
        to_receipt = getattr(value, "to_truthfulness_receipt", None)
        if callable(to_receipt):
            candidate = to_receipt()
            if isinstance(candidate, TruthfulnessReceipt):
                return candidate
            if isinstance(candidate, Mapping):
                return validate_truthfulness_receipt(candidate)
    except (TypeError, ValueError):
        return None
    return None


__all__ = [
    "TruthfulnessReceipt",
    "TruthfulnessScope",
    "TruthfulnessStatus",
    "TruthfulnessTier",
    "extract_truthfulness_receipt",
    "parse_truthfulness_scope",
    "parse_truthfulness_status",
    "parse_truthfulness_tier",
    "reconcile_truthfulness_tiers",
    "truthfulness_depth",
    "validate_truthfulness_receipt",
]
