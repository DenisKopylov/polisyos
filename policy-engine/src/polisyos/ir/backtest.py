from __future__ import annotations

import math
from enum import Enum
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.core.canon import CanonSpec, from_canonical_bytes

if TYPE_CHECKING:
    from polisyos.core.artifacts.manifest import InputRef
    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.core.contracts.backtest import BacktestReportRef


class BiasDirection(str, Enum):
    OPTIMISTIC = "optimistic"
    PESSIMISTIC = "pessimistic"
    NEUTRAL = "neutral"
    MIXED = "mixed"


class OutcomeComparison(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metric_name: str = Field(min_length=1)
    y_pred: float
    y_true: float
    absolute_error: float = Field(ge=0.0)
    relative_error: float | None = Field(default=None, ge=0.0)
    within_ci: bool = False
    ci_lower: float | None = None
    ci_upper: float | None = None

    @model_validator(mode="after")
    def _validate_numerics(self) -> "OutcomeComparison":
        if not math.isfinite(self.y_pred):
            raise ValueError("y_pred must be finite")
        if not math.isfinite(self.y_true):
            raise ValueError("y_true must be finite")
        if self.ci_lower is not None and not math.isfinite(self.ci_lower):
            raise ValueError("ci_lower must be finite when present")
        if self.ci_upper is not None and not math.isfinite(self.ci_upper):
            raise ValueError("ci_upper must be finite when present")
        if (
            self.ci_lower is not None
            and self.ci_upper is not None
            and self.ci_lower > self.ci_upper
        ):
            raise ValueError("ci_lower must be <= ci_upper")
        return self


class SystematicBias(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bias_type: str = Field(min_length=1)
    direction: BiasDirection
    magnitude: float = Field(ge=0.0)
    affected_metrics: list[str] = Field(default_factory=list)
    description: str = ""
    statistical_test: str = ""
    p_value: float | None = Field(default=None, ge=0.0, le=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_magnitude(self) -> "SystematicBias":
        if not math.isfinite(self.magnitude):
            raise ValueError("magnitude must be finite")
        return self


class BacktestScenario(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario_id: str = Field(min_length=1)
    scenario_label: str = Field(min_length=1)
    jurisdiction: str = ""
    intervention_date: str = ""
    data_source: str = ""

    outcome_comparisons: list[OutcomeComparison] = Field(default_factory=list)
    rmse: float | None = Field(default=None, ge=0.0)
    mae: float | None = Field(default=None, ge=0.0)
    mape: float | None = Field(default=None, ge=0.0)
    coverage_probability: float | None = Field(default=None, ge=0.0, le=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_metrics(self) -> "BacktestScenario":
        for value, name in (
            (self.rmse, "rmse"),
            (self.mae, "mae"),
            (self.mape, "mape"),
            (self.coverage_probability, "coverage_probability"),
        ):
            if value is not None and not math.isfinite(value):
                raise ValueError(f"{name} must be finite")
        return self


class BacktestReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    report_id: str = Field(min_length=1)

    model_spec_ref: str | None = None
    policy_spec_ref: str | None = None
    historical_data_ref: str | None = None
    backtest_config_ref: str | None = None

    scenarios: list[BacktestScenario] = Field(default_factory=list)

    overall_rmse: float | None = Field(default=None, ge=0.0)
    overall_mae: float | None = Field(default=None, ge=0.0)
    overall_mape: float | None = Field(default=None, ge=0.0)
    overall_coverage_probability: float | None = Field(default=None, ge=0.0, le=1.0)
    overall_r_squared: float | None = None
    n_scenarios: int = Field(default=0, ge=0)
    n_metrics_evaluated: int = Field(default=0, ge=0)

    detected_biases: list[SystematicBias] = Field(default_factory=list)
    overall_bias_direction: BiasDirection = BiasDirection.NEUTRAL

    trust_score: float | None = Field(default=None, ge=0.0, le=1.0)
    trust_grade: str | None = None

    cas_artifact_id: str | None = None
    decision_packet_ref: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_counts(self) -> "BacktestReport":
        if self.n_scenarios == 0 and self.scenarios:
            self.n_scenarios = len(self.scenarios)
        if self.n_scenarios != len(self.scenarios):
            raise ValueError("n_scenarios must match scenarios length")
        for value, name in (
            (self.overall_rmse, "overall_rmse"),
            (self.overall_mae, "overall_mae"),
            (self.overall_mape, "overall_mape"),
            (self.overall_coverage_probability, "overall_coverage_probability"),
            (self.overall_r_squared, "overall_r_squared"),
        ):
            if value is not None and not math.isfinite(value):
                raise ValueError(f"{name} must be finite")
        return self


def persist_backtest_report(
    store: "FileSystemCAS",
    report: BacktestReport,
    *,
    inputs: list["InputRef"] | None = None,
    schema_name: str = "ir.backtest_report",
    schema_version: str = "1.0",
) -> "BacktestReportRef":
    from polisyos.core.artifacts.manifest import SchemaInfo
    from polisyos.core.artifacts.store import PutOptions
    from polisyos.core.contracts.backtest import BacktestReportRef

    ref = store.put_json(
        report.model_dump(mode="json"),
        opts=PutOptions(
            kind="ir.backtest_report",
            media_type="application/json",
            schema=SchemaInfo(name=schema_name, version=schema_version),
            inputs=inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return BacktestReportRef.model_validate(ref.model_dump())


def load_backtest_report(store: "FileSystemCAS", ref: "BacktestReportRef") -> BacktestReport:
    payload = from_canonical_bytes(store.get_bytes(ref.artifact_id))
    return BacktestReport.model_validate(payload)


__all__ = [
    "BiasDirection",
    "OutcomeComparison",
    "SystematicBias",
    "BacktestScenario",
    "BacktestReport",
    "persist_backtest_report",
    "load_backtest_report",
]
