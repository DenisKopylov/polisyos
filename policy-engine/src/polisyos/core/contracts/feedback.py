"""Public contracts feedback module API."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


def _utc_now() -> datetime:
    return datetime.now(UTC)


class MonitoringVerdict(str, Enum):
    """Monitoring verdict public type."""

    PENDING = "pending"
    CONFIRMED = "confirmed"
    REFUTED = "refuted"
    INCONCLUSIVE = "inconclusive"
    INSUFFICIENT_DATA = "insufficient_data"
    DEGRADED = "degraded"


class MonitoringRange(BaseModel):
    """Monitoring range public type."""

    model_config = ConfigDict(extra="forbid")

    lower: float | None = None
    upper: float | None = None


class MonitoringWindow(BaseModel):
    """Monitoring window public type."""

    model_config = ConfigDict(extra="forbid")

    start_offset_days: int = 0
    end_offset_days: int = 30
    grace_days: int = 7


class MonitoredMetric(BaseModel):
    """Monitored metric public type."""

    model_config = ConfigDict(extra="forbid")

    metric_id: str
    source_metric_id: str
    baseline_value: float
    confirm_range: MonitoringRange
    refute_range: MonitoringRange
    window: MonitoringWindow = Field(default_factory=MonitoringWindow)
    min_observations: int = Field(default=1, ge=1)
    weight: float = Field(default=1.0, ge=0.0)
    recalibration_target: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class DecisionMonitoringContract(BaseModel):
    """Decision monitoring contract data model."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(default="1.0", pattern=r"^\d+\.\d+$")
    run_id: str | None = None
    decision_lineage_key: str | None = None
    anchor_at: datetime
    backtest_mode_effective: str | None = None
    backtest_trust_eligible: bool | None = None
    metrics: list[MonitoredMetric] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class MonitoringMetricResult(BaseModel):
    """Monitoring metric result data model."""

    model_config = ConfigDict(extra="forbid")

    metric_id: str
    source_metric_id: str
    baseline_value: float
    actual_value: float | None = None
    observed_count: int = Field(default=0, ge=0)
    verdict: MonitoringVerdict = MonitoringVerdict.PENDING
    reason: str | None = None
    delta: float | None = None
    recalibration_target: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class DecisionMonitoringReport(BaseModel):
    """Decision monitoring report data model."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(default="1.0", pattern=r"^\d+\.\d+$")
    run_id: str
    decision_packet_ref: str | None = None
    monitoring_contract_ref: str | None = None
    anchor_at: datetime | None = None
    evaluated_at: datetime = Field(default_factory=_utc_now)
    overall_verdict: MonitoringVerdict = MonitoringVerdict.PENDING
    metrics: list[MonitoringMetricResult] = Field(default_factory=list)
    refuted_metric_ids: list[str] = Field(default_factory=list)
    degraded_reasons: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class HistoricalSemanticRowDelta(BaseModel):
    """Historical semantic row delta public type."""

    model_config = ConfigDict(extra="forbid")

    row_key: str
    change_type: Literal[
        "schema_only",
        "row_added",
        "row_removed",
        "row_revised",
        "field_semantics_changed",
    ]
    field_deltas: dict[str, dict[str, Any]] = Field(default_factory=dict)
    numeric_deltas: dict[str, float] = Field(default_factory=dict)
    old_row: dict[str, Any] | None = None
    new_row: dict[str, Any] | None = None


class HistoricalSemanticDiffSummary(BaseModel):
    """Historical semantic diff summary data model."""

    model_config = ConfigDict(extra="forbid")

    schema_only: bool = False
    row_added: int = Field(default=0, ge=0)
    row_removed: int = Field(default=0, ge=0)
    row_revised: int = Field(default=0, ge=0)
    field_semantics_changed: int = Field(default=0, ge=0)
    matched_rows: int = Field(default=0, ge=0)
    compared_rows: int = Field(default=0, ge=0)
    coverage_ratio: float | None = Field(default=None, ge=0.0, le=1.0)
    material_revision: bool = False
    manual_review_required: bool = False
    key_fields: list[str] = Field(default_factory=list)
    schema_change_types: list[str] = Field(default_factory=list)
    duplicate_keys_left: int = Field(default=0, ge=0)
    duplicate_keys_right: int = Field(default=0, ge=0)


class HistoricalSemanticDiffReport(BaseModel):
    """Historical semantic diff report data model."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(default="1.0", pattern=r"^\d+\.\d+$")
    left_schema_id: str
    right_schema_id: str
    left_data_ref: str | None = None
    right_data_ref: str | None = None
    key_fields: list[str] = Field(default_factory=list)
    summary: HistoricalSemanticDiffSummary = Field(default_factory=HistoricalSemanticDiffSummary)
    changes: list[HistoricalSemanticRowDelta] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class CompareDeltaSection(BaseModel):
    """Compare delta section public type."""

    model_config = ConfigDict(extra="forbid")

    changed: bool = False
    refs: dict[str, str | None] = Field(default_factory=dict)
    summary: dict[str, Any] = Field(default_factory=dict)
    details: dict[str, Any] = Field(default_factory=dict)


class DecisionCompareReport(BaseModel):
    """Decision compare report data model."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(default="1.0", pattern=r"^\d+\.\d+$")
    left_run_id: str
    right_run_id: str
    left_decision_packet_ref: str | None = None
    right_decision_packet_ref: str | None = None
    deltas: dict[str, CompareDeltaSection] = Field(default_factory=dict)
    root_cause: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class DecisionReissuePlan(BaseModel):
    """Decision reissue plan data model."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(default="1.0", pattern=r"^\d+\.\d+$")
    source_run_id: str
    source_decision_packet_ref: str | None = None
    monitoring_report_ref: str | None = None
    compare_report_ref: str | None = None
    calibration_config_ref: str | None = None
    parameter_override_bundle_ref: str | None = None
    refuted_metric_ids: list[str] = Field(default_factory=list)
    revised_metric_ids: list[str] = Field(default_factory=list)
    publication_mode: Literal["human_gated"] = "human_gated"
    requires_operator_confirmation: bool = True
    recommended_action: str = "reissue_decision_packet"
    notes: list[str] = Field(default_factory=list)


__all__ = [
    "CompareDeltaSection",
    "DecisionCompareReport",
    "DecisionMonitoringContract",
    "DecisionMonitoringReport",
    "DecisionReissuePlan",
    "HistoricalSemanticDiffReport",
    "HistoricalSemanticDiffSummary",
    "HistoricalSemanticRowDelta",
    "MonitoredMetric",
    "MonitoringMetricResult",
    "MonitoringRange",
    "MonitoringVerdict",
    "MonitoringWindow",
]
