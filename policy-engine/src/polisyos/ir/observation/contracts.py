"""Define raw observation records and homogeneous panels.

This module is the lowest observation layer: it describes raw normalized
measurements and panel containers before family-level governance policy,
measurement trust normalization, or causal-readiness manifests are applied.
Use :class:`ObservationRecord` for atomic evidence rows and
:class:`ObservationPanel` for compiler-ready homogeneous collections.
"""
from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Any

from pydantic import Field, model_validator

from polisyos.ir._validation import ensure_finite_numeric, ensure_interval_monotonicity
from polisyos.ir.kernel.base import ID_PATTERN, KernelModel
from polisyos.ir.types import TimeFrequency

SCHEMA_VERSION_PATTERN = r"^\d+\.\d+$"


class ObservationFamily(str, Enum):
    """Classify raw evidence into stable observation families for routing.

    Families partition raw evidence into domains such as budget flows, firm
    fundamentals, or household distribution so measurement rules, governance
    defaults, and contract compilers can branch on a stable domain label.
    """

    BUDGET_FLOWS = "budget_flows"
    PROCUREMENT_FLOWS = "procurement_flows"
    MACRO_STATE = "macro_state"
    FIRM_FUNDAMENTALS = "firm_fundamentals"
    TRADE_EXPOSURE = "trade_exposure"
    LABOR_MARKET = "labor_market"
    HOUSEHOLD_DISTRIBUTION = "household_distribution"
    DISTRESS_ENFORCEMENT = "distress_enforcement"
    SPATIAL_RASTER_EXOGENOUS = "spatial_raster_exogenous"
    PUBLIC_SERVICE_DOMAIN_FLOWS = "public_service_domain_flows"
    EDUCATION_HUMAN_CAPITAL_SUPPLY = "education_human_capital_supply"
    CONSTRUCTION_CAPITAL_FORMATION = "construction_capital_formation"
    LOGISTICS_FRICTION = "logistics_friction"


class EntityScope(str, Enum):
    """Granularity at which an observation is measured.

    The scope determines which locator fields must be present on an
    :class:`ObservationRecord` and which downstream contracts can consume the
    resulting panel.
    """

    GLOBAL = "global"
    AGENT = "agent"
    FIRM = "firm"
    HOUSEHOLD = "household"
    CELL = "cell"
    HOUSEHOLD_CELL = "household_cell"
    REGION = "region"
    SECTOR = "sector"


class IdentificationMode(str, Enum):
    """Declare the causal identification contract assumed by records and bundles.

    These modes distinguish point-identified data from partially identified,
    proxy-based, interference-aware, or sequential settings so downstream
    components can enforce the right guardrails. The value is read by
    :class:`polisyos.ir.observation.measurement.IdentificationModeRouter`,
    observation contract compilers, and causal-readiness checks to select
    fallback paths or block unsafe execution.
    """

    POINT_IDENTIFIED = "point_identified"
    PARTIALLY_IDENTIFIED = "partially_identified"
    BOUNDS_ONLY = "bounds_only"
    PROXY_IDENTIFIED = "proxy_identified"
    INTERFERENCE_AWARE = "interference_aware"
    SEQUENTIAL = "sequential"


class SourceConfidenceTier(str, Enum):
    """Declare the raw provenance tier consumed by measurement trust normalization.

    :class:`polisyos.ir.observation.measurement.MeasurementRegistry` maps this
    source-side tier and coverage metadata into a ``MeasurementTrustTier`` used
    by calibration losses and readiness routing.
    """

    CORE = "core"
    VALIDATED = "validated"
    EXPLORATORY = "exploratory"


class MultiplexGraphLayerId(str, Enum):
    """Select the graph layer consumed by network compilers and interference checks."""

    BUDGET = "budget"
    PROCUREMENT = "procurement"
    TRADE = "trade"
    DISTRESS = "distress"
    PUBLIC_SERVICE = "public_service"


class StrategicResponseChannel(str, Enum):
    """Identify the adaptation channel that should trigger strategic-response checks.

    ``PolicySpec`` and readiness bundles use this enum to route interventions to
    strategic-response hooks and to document which behavioral channel may break
    naive policy assumptions.
    """

    BUDGET_CHANNEL = "budget_channel"
    PROCUREMENT_CHANNEL = "procurement_channel"
    LABOR_CHANNEL = "labor_channel"
    TRADE_CHANNEL = "trade_channel"
    HOUSEHOLD_INCOME_CHANNEL = "household_income_channel"
    COMPLIANCE_CHANNEL = "compliance_channel"


class ObservationRecord(KernelModel):
    """Store one raw normalized measurement and the metadata needed for routing.

    Represents one metric value for a specific entity scope and time window,
    together with the metadata needed for measurement-aware loss weighting,
    schema-regime boundary handling, and causal readiness routing.

    Attributes:
        observation_id: Stable lineage identifier for the measurement.
        family: Observation domain used by governance and compiler registries.
        entity_scope: Granularity that determines which locator field is required.
        coverage_estimate: Estimated share of the target population covered.
        trust_weight: Raw source confidence weight before registry normalization.
        identification_mode: Assumptions under which the value may be used causally.
    """

    schema_version: str = Field("1.0", pattern=SCHEMA_VERSION_PATTERN)

    observation_id: str = Field(..., pattern=ID_PATTERN)
    family: ObservationFamily
    time_grain: TimeFrequency
    period_start: date
    period_end: date

    entity_scope: EntityScope
    entity_id: str | None = Field(None, max_length=128)
    cell_id: str | None = Field(None, max_length=128)
    region_code: str | None = Field(None, max_length=64)
    sector_id: str | None = Field(None, max_length=64)

    metric_id: str = Field(..., min_length=1, max_length=120)
    observed_value: float
    unit: str = Field(..., min_length=1, max_length=32)
    coverage_estimate: float = Field(..., ge=0.0, le=1.0)
    measurement_bias_flag: bool = False
    censoring_mask: bool = False
    trust_weight: float = Field(..., ge=0.0)
    lag_days_estimate: int = Field(default=0, ge=0)

    source_id: str = Field(..., min_length=1, max_length=120)
    source_version: str = Field(..., min_length=1, max_length=120)
    regime_id: str = Field(..., min_length=1, max_length=120)
    shock_mask: bool = False
    schema_regime_id: str = Field(..., min_length=1, max_length=120)
    identification_mode: IdentificationMode
    source_confidence_tier: SourceConfidenceTier = SourceConfidenceTier.VALIDATED
    proxy_source_id: str | None = Field(None, max_length=120)
    notes_json: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_observation_record(self) -> "ObservationRecord":
        ensure_interval_monotonicity(
            self.period_start,
            self.period_end,
            label="period",
            start_name="period_start",
            end_name="period_end",
        )
        ensure_finite_numeric(self.observed_value, field_name="observed_value")
        ensure_finite_numeric(self.coverage_estimate, field_name="coverage_estimate")
        ensure_finite_numeric(self.trust_weight, field_name="trust_weight")

        if self.identification_mode == IdentificationMode.PROXY_IDENTIFIED and not self.proxy_source_id:
            raise ValueError("proxy_source_id is required for proxy_identified observations")

        if self.entity_scope in {EntityScope.AGENT, EntityScope.FIRM, EntityScope.HOUSEHOLD}:
            if not self.entity_id:
                raise ValueError(f"entity_id is required for scope={self.entity_scope.value}")
        if self.entity_scope in {EntityScope.CELL, EntityScope.HOUSEHOLD_CELL} and not self.cell_id:
            raise ValueError(f"cell_id is required for scope={self.entity_scope.value}")
        if self.entity_scope == EntityScope.REGION and not self.region_code:
            raise ValueError("region_code is required for scope=region")
        if self.entity_scope == EntityScope.SECTOR and not self.sector_id:
            raise ValueError("sector_id is required for scope=sector")
        return self


class ObservationPanel(KernelModel):
    """Group homogeneous raw observations before compiler and readiness stages.

    Panels guarantee a shared observation family and time grain so compiler
    stages can align records onto a single timeline and materialize bundle
    artifacts deterministically.
    """

    schema_version: str = Field("1.0", pattern=SCHEMA_VERSION_PATTERN)
    panel_id: str = Field(..., pattern=ID_PATTERN)
    family: ObservationFamily
    time_grain: TimeFrequency
    records: list[ObservationRecord] = Field(..., min_length=1)
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_panel(self) -> "ObservationPanel":
        for record in self.records:
            if record.family != self.family:
                raise ValueError(
                    f"record family mismatch: expected {self.family.value}, got {record.family.value}"
                )
            if record.time_grain != self.time_grain:
                raise ValueError(
                    "record time_grain mismatch: "
                    f"expected {self.time_grain.value}, got {record.time_grain.value}"
                )
        return self


__all__ = [
    "EntityScope",
    "IdentificationMode",
    "MultiplexGraphLayerId",
    "ObservationFamily",
    "ObservationPanel",
    "ObservationRecord",
    "SourceConfidenceTier",
    "StrategicResponseChannel",
]
