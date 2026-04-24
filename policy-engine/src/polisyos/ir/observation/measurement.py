"""Normalize source trust, regime boundaries, and identification routing.

This module bridges raw observation metadata and compiler-ready routing
decisions. ``MeasurementRegistry`` converts source confidence and coverage into
measurement trust tiers, schema/regime calendars mark unsafe boundary windows,
and ``IdentificationModeRouter`` chooses the effective causal identification
mode for a family or record before readiness checks are assembled.
"""

from __future__ import annotations

import math
from datetime import date, timedelta
from enum import Enum

from pydantic import Field, model_validator

from polisyos.ir.kernel.base import ID_PATTERN, KernelModel
from polisyos.ir.observation.contracts import (
    IdentificationMode,
    ObservationFamily,
    ObservationRecord,
    SourceConfidenceTier,
)
from polisyos.ir.observation.governance import (
    DEFAULT_OBSERVATION_FAMILY_POLICY_REGISTRY,
    ObservationFamilyPolicyRegistry,
)
from polisyos.ir.types import TimeFrequency

SCHEMA_VERSION_PATTERN = r"^\d+\.\d+$"

_FREQUENCY_BUFFER_DAYS = {
    TimeFrequency.MONTH: 31,
    TimeFrequency.QUARTER: 92,
    TimeFrequency.YEAR: 366,
}


class MeasurementTrustTier(str, Enum):
    """Represent the normalized trust bucket consumed by calibration and routing.

    ``MeasurementRegistry.tier_for_record`` derives this enum from raw
    observation metadata. Calibration losses and readiness manifests use the
    resulting tier to downweight proxies, cap weak anchors, or preserve
    authoritative high-coverage sources.
    """

    AUTHORITATIVE_HIGH_COVERAGE = "authoritative_high_coverage"
    AUTHORITATIVE_PARTIAL_COVERAGE = "authoritative_partial_coverage"
    ADMINISTRATIVE_NOISY = "administrative_noisy"
    DERIVED_PROXY = "derived_proxy"
    WEAK_ANCHOR = "weak_anchor"


class MeasurementTierRule(KernelModel):
    """Parameterize trust-weight normalization for one ``MeasurementTrustTier``."""

    tier: MeasurementTrustTier
    trust_cap: float = Field(..., ge=0.0)
    trust_multiplier: float = Field(default=1.0, ge=0.0)
    min_coverage: float = Field(default=0.0, ge=0.0, le=1.0)
    max_coverage: float = Field(default=1.0, ge=0.0, le=1.0)
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_rule(self) -> MeasurementTierRule:
        if self.max_coverage < self.min_coverage:
            raise ValueError("max_coverage must be >= min_coverage")
        return self


class ProxyMappingRule(KernelModel):
    """Declare the default proxy source/metric for one latent family pathway."""

    family: ObservationFamily
    proxy_source_id: str = Field(..., min_length=1, max_length=120)
    proxy_metric_id: str | None = Field(None, min_length=1, max_length=120)
    notes: list[str] = Field(default_factory=list)


class SchemaChangepoint(KernelModel):
    """Mark a schema or publication-regime boundary that should trigger holdouts.

    Calibration split planning and schema-regime boundary checks consult these
    changepoints to avoid leakage around discontinuities.
    """

    changepoint_id: str = Field(..., pattern=ID_PATTERN)
    effective_date: date
    source_id: str | None = Field(None, min_length=1, max_length=120)
    source_version: str | None = Field(None, min_length=1, max_length=120)
    from_schema_regime_id: str | None = Field(None, min_length=1, max_length=120)
    to_schema_regime_id: str | None = Field(None, min_length=1, max_length=120)
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_changepoint(self) -> SchemaChangepoint:
        if self.from_schema_regime_id is None and self.to_schema_regime_id is None:
            raise ValueError(
                "SchemaChangepoint must reference from_schema_regime_id or to_schema_regime_id"
            )
        return self


class SchemaRegimeSpec(KernelModel):
    """Describe the validity window and boundary buffer for one schema regime."""

    schema_regime_id: str = Field(..., min_length=1, max_length=120)
    source_id: str | None = Field(None, min_length=1, max_length=120)
    source_version: str = Field(..., min_length=1, max_length=120)
    effective_start: date
    effective_end: date | None = None
    regime_id: str | None = Field(None, min_length=1, max_length=120)
    publication_regime_notes: list[str] = Field(default_factory=list)
    boundary_buffer_periods: int = Field(default=1, ge=0)

    @model_validator(mode="after")
    def validate_regime(self) -> SchemaRegimeSpec:
        if self.effective_end is not None and self.effective_end < self.effective_start:
            raise ValueError("effective_end must be >= effective_start")
        return self

    def contains(self, period_start: date, period_end: date) -> bool:
        if period_end < self.effective_start:
            return False
        if self.effective_end is None:
            return True
        return period_start <= self.effective_end


class RegimeCalendarEntry(KernelModel):
    """Inclusive time window for a real-world policy or publication regime."""

    regime_id: str = Field(..., min_length=1, max_length=120)
    start_date: date
    end_date: date
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_entry(self) -> RegimeCalendarEntry:
        if self.end_date < self.start_date:
            raise ValueError("end_date must be >= start_date")
        return self


class ShockCalendarEntry(KernelModel):
    """Inclusive time window for an exogenous shock that can trigger fallback logic."""

    shock_id: str = Field(..., min_length=1, max_length=120)
    start_date: date
    end_date: date
    affected_regime_ids: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_entry(self) -> ShockCalendarEntry:
        if self.end_date < self.start_date:
            raise ValueError("end_date must be >= start_date")
        return self


def _buffer_days(time_grain: TimeFrequency, periods: int) -> int:
    return _FREQUENCY_BUFFER_DAYS[time_grain] * periods


class RegimeCalendar(KernelModel):
    """Calendar of policy or reporting regimes relevant to observations.

    The calendar is consulted during calibration splitting to hold out boundary
    periods where regime transitions make train/validation leakage likely.
    """

    schema_version: str = Field("1.0", pattern=SCHEMA_VERSION_PATTERN)
    entries: list[RegimeCalendarEntry] = Field(default_factory=list)
    boundary_buffer_periods: int = Field(default=1, ge=0)

    def contains(self, *, regime_id: str | None, period_start: date, period_end: date) -> bool:
        for entry in self.entries:
            if regime_id is not None and entry.regime_id != regime_id:
                continue
            if period_start <= entry.end_date and period_end >= entry.start_date:
                return True
        return False

    def is_boundary(
        self,
        *,
        regime_id: str | None,
        period_start: date,
        period_end: date,
        time_grain: TimeFrequency,
    ) -> bool:
        if self.boundary_buffer_periods == 0:
            return False
        window = timedelta(days=_buffer_days(time_grain, self.boundary_buffer_periods))
        for entry in self.entries:
            if regime_id is not None and entry.regime_id != regime_id:
                continue
            start_boundary_end = entry.start_date + window
            end_boundary_start = entry.end_date - window
            if period_start <= start_boundary_end and period_end >= entry.start_date:
                return True
            if period_start <= entry.end_date and period_end >= end_boundary_start:
                return True
        return False


class ShockCalendar(KernelModel):
    """Track exogenous shock windows that can force fallback identification modes.

    ``IdentificationModeRouter`` and calibration splitting logic can use shock
    masks derived from this calendar to activate bounds/proxy fallbacks or to
    exclude unsafe periods near shock boundaries.
    """

    schema_version: str = Field("1.0", pattern=SCHEMA_VERSION_PATTERN)
    entries: list[ShockCalendarEntry] = Field(default_factory=list)
    boundary_buffer_periods: int = Field(default=1, ge=0)

    def contains(
        self, *, period_start: date, period_end: date, regime_id: str | None = None
    ) -> bool:
        for entry in self.entries:
            if (
                regime_id is not None
                and entry.affected_regime_ids
                and regime_id not in entry.affected_regime_ids
            ):
                continue
            if period_start <= entry.end_date and period_end >= entry.start_date:
                return True
        return False

    def is_boundary(
        self,
        *,
        period_start: date,
        period_end: date,
        time_grain: TimeFrequency,
        regime_id: str | None = None,
    ) -> bool:
        if self.boundary_buffer_periods == 0:
            return False
        window = timedelta(days=_buffer_days(time_grain, self.boundary_buffer_periods))
        for entry in self.entries:
            if (
                regime_id is not None
                and entry.affected_regime_ids
                and regime_id not in entry.affected_regime_ids
            ):
                continue
            start_boundary_end = entry.start_date + window
            end_boundary_start = entry.end_date - window
            if period_start <= start_boundary_end and period_end >= entry.start_date:
                return True
            if period_start <= entry.end_date and period_end >= end_boundary_start:
                return True
        return False


class SchemaRegimeRegistry(KernelModel):
    """Index schema regimes and changepoints for boundary-aware observation checks."""

    schema_version: str = Field("1.0", pattern=SCHEMA_VERSION_PATTERN)
    regimes: dict[str, SchemaRegimeSpec] = Field(default_factory=dict)
    changepoints: list[SchemaChangepoint] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_registry(self) -> SchemaRegimeRegistry:
        for key, spec in self.regimes.items():
            if key != spec.schema_regime_id:
                raise ValueError(
                    f"schema regime key mismatch: '{key}' != '{spec.schema_regime_id}'"
                )
        return self

    def resolve(self, schema_regime_id: str) -> SchemaRegimeSpec | None:
        return self.regimes.get(schema_regime_id)

    def changepoints_for(self, schema_regime_id: str) -> list[SchemaChangepoint]:
        return [
            point
            for point in self.changepoints
            if point.from_schema_regime_id == schema_regime_id
            or point.to_schema_regime_id == schema_regime_id
        ]

    def is_boundary(
        self,
        *,
        schema_regime_id: str,
        period_start: date,
        period_end: date,
        time_grain: TimeFrequency,
    ) -> bool:
        spec = self.resolve(schema_regime_id)
        if spec is None or spec.boundary_buffer_periods == 0:
            return False
        window = timedelta(days=_buffer_days(time_grain, spec.boundary_buffer_periods))
        if period_start <= spec.effective_start + window and period_end >= spec.effective_start:
            return True
        if spec.effective_end is not None:
            if period_start <= spec.effective_end and period_end >= spec.effective_end - window:
                return True
        for point in self.changepoints_for(schema_regime_id):
            if (
                period_start <= point.effective_date + window
                and period_end >= point.effective_date - window
            ):
                return True
        return False

    @classmethod
    def default(cls) -> SchemaRegimeRegistry:
        return cls(
            regimes={
                "default_schema_v1": SchemaRegimeSpec(
                    schema_regime_id="default_schema_v1",
                    source_version="1.0",
                    effective_start=date(2020, 1, 1),
                    publication_regime_notes=[
                        "Synthetic default schema regime for calibration fixtures."
                    ],
                )
            }
        )


class MeasurementRegistry(KernelModel):
    """Normalize raw observation trust, coverage thresholds, and proxy defaults.

    The registry converts raw source metadata into trust tiers, family-specific
    coverage thresholds, and proxy defaults that downstream calibration and
    routing components can apply consistently.
    """

    schema_version: str = Field("1.0", pattern=SCHEMA_VERSION_PATTERN)
    trust_tiers: dict[str, MeasurementTierRule] = Field(default_factory=dict)
    coverage_rules: dict[str, float] = Field(default_factory=dict)
    proxy_mappings: dict[str, ProxyMappingRule] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_registry(self) -> MeasurementRegistry:
        for tier in MeasurementTrustTier:
            if tier.value not in self.trust_tiers:
                raise ValueError(f"missing trust tier rule: {tier.value}")
        for family in ObservationFamily:
            if family.value not in self.coverage_rules:
                raise ValueError(f"missing coverage rule for family: {family.value}")
        for key, rule in self.proxy_mappings.items():
            if key != rule.family.value:
                raise ValueError(f"proxy mapping key mismatch: '{key}' != '{rule.family.value}'")
        return self

    def coverage_threshold_for_family(self, family: ObservationFamily) -> float:
        """Return the minimum trusted coverage required for a family."""
        return float(self.coverage_rules[family.value])

    def proxy_mapping_for_family(self, family: ObservationFamily) -> ProxyMappingRule | None:
        """Return the default proxy mapping for ``family`` if one is registered."""
        return self.proxy_mappings.get(family.value)

    def tier_for_record(self, record: ObservationRecord) -> MeasurementTrustTier:
        """Map raw observation metadata to a normalized trust tier.

        Args:
            record: Raw observation row whose source tier, coverage, bias flags,
                and proxy metadata should be normalized.

        Returns:
            The measurement trust tier used by calibration and readiness routing.
        """
        threshold = self.coverage_threshold_for_family(record.family)
        if (
            record.identification_mode == IdentificationMode.PROXY_IDENTIFIED
            or record.proxy_source_id
        ):
            return MeasurementTrustTier.DERIVED_PROXY
        if record.source_confidence_tier == SourceConfidenceTier.EXPLORATORY:
            return MeasurementTrustTier.WEAK_ANCHOR
        if record.source_confidence_tier == SourceConfidenceTier.CORE:
            if record.coverage_estimate >= threshold and not record.measurement_bias_flag:
                return MeasurementTrustTier.AUTHORITATIVE_HIGH_COVERAGE
            return MeasurementTrustTier.AUTHORITATIVE_PARTIAL_COVERAGE
        return MeasurementTrustTier.ADMINISTRATIVE_NOISY

    def normalize_trust_weight(
        self,
        trust_weight: float,
        *,
        tier: MeasurementTrustTier,
    ) -> float:
        """Apply tier-specific caps and multipliers to a raw trust weight.

        Args:
            trust_weight: Source-provided non-negative trust score.
            tier: Normalized measurement tier controlling cap and multiplier.

        Returns:
            A bounded non-negative trust weight suitable for downstream losses.

        Raises:
            ValueError: If ``trust_weight`` is negative or non-finite.
        """
        if not math.isfinite(trust_weight):
            raise ValueError("trust_weight must be finite")
        if trust_weight < 0.0:
            raise ValueError("trust_weight must be >= 0")
        rule = self.trust_tiers[tier.value]
        normalized = min(trust_weight, rule.trust_cap) * rule.trust_multiplier
        return max(0.0, min(normalized, rule.trust_cap))

    def normalize_record_trust(self, record: ObservationRecord) -> float:
        """Normalize one record's trust weight using its derived measurement tier."""
        return self.normalize_trust_weight(record.trust_weight, tier=self.tier_for_record(record))

    @classmethod
    def default(cls) -> MeasurementRegistry:
        """Build the built-in family coverage, tier, and proxy defaults."""
        trust_tiers = {
            MeasurementTrustTier.AUTHORITATIVE_HIGH_COVERAGE.value: MeasurementTierRule(
                tier=MeasurementTrustTier.AUTHORITATIVE_HIGH_COVERAGE,
                trust_cap=1.0,
                trust_multiplier=1.0,
                min_coverage=0.85,
            ),
            MeasurementTrustTier.AUTHORITATIVE_PARTIAL_COVERAGE.value: MeasurementTierRule(
                tier=MeasurementTrustTier.AUTHORITATIVE_PARTIAL_COVERAGE,
                trust_cap=0.85,
                trust_multiplier=0.95,
                min_coverage=0.5,
            ),
            MeasurementTrustTier.ADMINISTRATIVE_NOISY.value: MeasurementTierRule(
                tier=MeasurementTrustTier.ADMINISTRATIVE_NOISY,
                trust_cap=0.7,
                trust_multiplier=0.85,
            ),
            MeasurementTrustTier.DERIVED_PROXY.value: MeasurementTierRule(
                tier=MeasurementTrustTier.DERIVED_PROXY,
                trust_cap=0.6,
                trust_multiplier=0.8,
            ),
            MeasurementTrustTier.WEAK_ANCHOR.value: MeasurementTierRule(
                tier=MeasurementTrustTier.WEAK_ANCHOR,
                trust_cap=0.25,
                trust_multiplier=0.6,
            ),
        }
        coverage_rules = {
            ObservationFamily.BUDGET_FLOWS.value: 0.85,
            ObservationFamily.PROCUREMENT_FLOWS.value: 0.8,
            ObservationFamily.MACRO_STATE.value: 0.95,
            ObservationFamily.FIRM_FUNDAMENTALS.value: 0.8,
            ObservationFamily.TRADE_EXPOSURE.value: 0.75,
            ObservationFamily.LABOR_MARKET.value: 0.7,
            ObservationFamily.HOUSEHOLD_DISTRIBUTION.value: 0.65,
            ObservationFamily.DISTRESS_ENFORCEMENT.value: 0.6,
            ObservationFamily.SPATIAL_RASTER_EXOGENOUS.value: 0.9,
            ObservationFamily.PUBLIC_SERVICE_DOMAIN_FLOWS.value: 0.75,
            ObservationFamily.EDUCATION_HUMAN_CAPITAL_SUPPLY.value: 0.8,
            ObservationFamily.CONSTRUCTION_CAPITAL_FORMATION.value: 0.75,
            ObservationFamily.LOGISTICS_FRICTION.value: 0.7,
        }
        proxy_mappings = {
            ObservationFamily.LABOR_MARKET.value: ProxyMappingRule(
                family=ObservationFamily.LABOR_MARKET,
                proxy_source_id="administrative_employment",
                proxy_metric_id="registered_employment",
            ),
            ObservationFamily.HOUSEHOLD_DISTRIBUTION.value: ProxyMappingRule(
                family=ObservationFamily.HOUSEHOLD_DISTRIBUTION,
                proxy_source_id="household_survey_proxy",
                proxy_metric_id="consumption_proxy",
            ),
            ObservationFamily.LOGISTICS_FRICTION.value: ProxyMappingRule(
                family=ObservationFamily.LOGISTICS_FRICTION,
                proxy_source_id="border_queue_time",
                proxy_metric_id="queue_delay_proxy",
            ),
        }
        return cls(
            trust_tiers=trust_tiers,
            coverage_rules=coverage_rules,
            proxy_mappings=proxy_mappings,
        )


class IdentificationRoute(KernelModel):
    """Return the effective identification mode selected for one family/record.

    ``fallback_triggered`` tells contract compilers and readiness checks whether
    observed coverage, censoring, bias, or shocks forced a policy fallback away
    from the family primary mode.
    """

    family: ObservationFamily
    selected_mode: IdentificationMode
    primary_mode: IdentificationMode
    fallback_mode: IdentificationMode | None = None
    explicit_mode: IdentificationMode | None = None
    fallback_triggered: bool = False
    reason: str = Field(..., min_length=1, max_length=120)


class IdentificationModeRouter(KernelModel):
    """Router that chooses the effective identification mode for observations.

    The router combines family policy defaults with measurement coverage,
    censoring, bias flags, and shocks to determine whether fallback modes must
    be activated.
    """

    schema_version: str = Field("1.0", pattern=SCHEMA_VERSION_PATTERN)
    measurement_registry: MeasurementRegistry = Field(default_factory=MeasurementRegistry.default)
    family_policy_registry: ObservationFamilyPolicyRegistry = Field(
        default_factory=lambda: DEFAULT_OBSERVATION_FAMILY_POLICY_REGISTRY
    )

    def route_family(
        self,
        family: ObservationFamily,
        *,
        coverage_estimate: float,
        censoring_mask: bool = False,
        measurement_bias_flag: bool = False,
        shock_mask: bool = False,
        explicit_mode: IdentificationMode | None = None,
    ) -> IdentificationRoute:
        """Choose the effective identification mode for one family under observed conditions.

        Args:
            family: Observation family being routed.
            coverage_estimate: Observed population coverage in ``[0, 1]``.
            censoring_mask: Whether censoring is present for the family slice.
            measurement_bias_flag: Whether known measurement bias should trigger
                fallback semantics.
            shock_mask: Whether an exogenous shock window should trigger fallback.
            explicit_mode: Optional mode supplied by a concrete record or caller.

        Returns:
            A resolved route with selected, primary, fallback, and reason fields.
        """
        policy = self.family_policy_registry.for_family(family)
        selected = policy.primary_identification_mode
        reason = "primary_policy"
        allowed = {policy.primary_identification_mode}
        if policy.fallback_identification_mode is not None:
            allowed.add(policy.fallback_identification_mode)

        fallback_triggered = bool(
            policy.fallback_identification_mode is not None
            and (
                coverage_estimate < self.measurement_registry.coverage_threshold_for_family(family)
                or censoring_mask
                or measurement_bias_flag
                or shock_mask
            )
        )

        if explicit_mode is not None and explicit_mode in allowed:
            selected = explicit_mode
            reason = "explicit_mode"
        elif explicit_mode is not None:
            reason = "incompatible_explicit_mode"

        if fallback_triggered and policy.fallback_identification_mode is not None:
            if explicit_mode is None or explicit_mode == policy.primary_identification_mode:
                selected = policy.fallback_identification_mode
                reason = "fallback_conditions"

        return IdentificationRoute(
            family=family,
            selected_mode=selected,
            primary_mode=policy.primary_identification_mode,
            fallback_mode=policy.fallback_identification_mode,
            explicit_mode=explicit_mode,
            fallback_triggered=fallback_triggered,
            reason=reason,
        )

    def route_record(self, record: ObservationRecord) -> IdentificationRoute:
        """Route one concrete observation record using its metadata and explicit mode."""
        return self.route_family(
            record.family,
            coverage_estimate=record.coverage_estimate,
            censoring_mask=record.censoring_mask,
            measurement_bias_flag=record.measurement_bias_flag,
            shock_mask=record.shock_mask,
            explicit_mode=record.identification_mode,
        )


__all__ = [
    "IdentificationModeRouter",
    "IdentificationRoute",
    "MeasurementRegistry",
    "MeasurementTierRule",
    "MeasurementTrustTier",
    "ProxyMappingRule",
    "RegimeCalendar",
    "RegimeCalendarEntry",
    "SchemaChangepoint",
    "SchemaRegimeRegistry",
    "SchemaRegimeSpec",
    "ShockCalendar",
    "ShockCalendarEntry",
]
