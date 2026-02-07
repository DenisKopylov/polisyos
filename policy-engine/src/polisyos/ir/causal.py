from __future__ import annotations

import math
from enum import Enum
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.ir.uncertainty import (
    DistributionFamily,
    IntervalSemantics,
    PropagationMethod,
    UncertaintyEnvelope,
    UncertaintySource,
)

if TYPE_CHECKING:
    from polisyos.core.artifacts.manifest import InputRef
    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.core.contracts.causal import CausalEffectReportRef


class CausalMethod(str, Enum):
    SYNTHETIC_CONTROL = "synthetic_control"
    DIFFERENCE_IN_DIFFERENCES = "difference_in_differences"
    REGRESSION_DISCONTINUITY = "regression_discontinuity"
    STRUCTURAL_TIME_SERIES = "structural_time_series"


class EstimationStatus(str, Enum):
    SUCCESS = "success"
    INPUT_INVALID = "input_invalid"
    ASSUMPTION_FAILED = "assumption_failed"
    NUMERICAL_FAILURE = "numerical_failure"


class PlaceboResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    unit_id: str | int
    effect_estimate: float
    rmspe_pre: float | None = None
    rmspe_post: float | None = None
    rmspe_ratio: float | None = None


class DiagnosticTest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    test_name: str
    statistic: float | None = None
    p_value: float | None = Field(default=None, ge=0.0, le=1.0)
    passed: bool
    details: dict[str, Any] = Field(default_factory=dict)


class CausalEffectReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")

    method: CausalMethod
    status: EstimationStatus = EstimationStatus.SUCCESS
    status_reason: str | None = None

    estimand: str
    point_estimate: float | None = None
    standard_error: float | None = Field(default=None, ge=0.0)
    confidence_interval: tuple[float, float] | None = None
    confidence_level: float | None = Field(default=0.95, gt=0.0, lt=1.0)
    p_value: float | None = Field(default=None, ge=0.0, le=1.0)

    inference_method: str
    n_bootstrap_samples: int | None = Field(default=None, ge=1)
    effect_size_cohen_d: float | None = None

    pre_treatment_fit: dict[str, float] = Field(default_factory=dict)
    diagnostics: list[DiagnosticTest] = Field(default_factory=list)
    placebo_results: list[PlaceboResult] = Field(default_factory=list)
    placebo_p_value: float | None = Field(default=None, ge=0.0, le=1.0)
    time_effects: dict[str, list[float]] = Field(default_factory=dict)

    method_params: dict[str, Any] = Field(default_factory=dict)
    assumptions: dict[str, str] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    sample_size: int = Field(ge=0)
    n_treated: int = Field(ge=0)
    n_control: int = Field(ge=0)
    pre_periods: int = Field(ge=0)
    post_periods: int = Field(ge=0)

    @model_validator(mode="after")
    def _validate_numbers(self) -> "CausalEffectReport":
        if self.status is EstimationStatus.SUCCESS:
            if self.point_estimate is None:
                raise ValueError("point_estimate is required for successful estimates")
            if self.confidence_interval is None:
                raise ValueError("confidence_interval is required for successful estimates")

        if self.confidence_interval is not None:
            lo, hi = self.confidence_interval
            if not math.isfinite(lo) or not math.isfinite(hi):
                raise ValueError("confidence_interval bounds must be finite")
            if lo > hi:
                raise ValueError("confidence_interval lower bound cannot exceed upper bound")
            if self.point_estimate is not None and not (lo <= self.point_estimate <= hi):
                raise ValueError("point_estimate must lie inside confidence_interval")

        if self.point_estimate is not None and not math.isfinite(self.point_estimate):
            raise ValueError("point_estimate must be finite")
        if self.standard_error is not None and not math.isfinite(self.standard_error):
            raise ValueError("standard_error must be finite")
        if self.effect_size_cohen_d is not None and not math.isfinite(self.effect_size_cohen_d):
            raise ValueError("effect_size_cohen_d must be finite")
        return self

    def to_uncertainty_envelope(self) -> UncertaintyEnvelope | None:
        if self.status is not EstimationStatus.SUCCESS:
            sentinel = 1.0e12
            point = 0.0 if self.point_estimate is None else float(self.point_estimate)
            point = max(-sentinel, min(sentinel, point))
            # Failure-mode envelope keeps governance visibility while remaining non-gate-eligible.
            return UncertaintyEnvelope(
                point_estimate=point,
                confidence_interval=(-sentinel, sentinel),
                confidence_level=None,
                distribution_family=DistributionFamily.UNKNOWN,
                source=UncertaintySource.CAUSAL,
                propagation_method=PropagationMethod.NONE,
                interval_semantics=IntervalSemantics.HEURISTIC_RANGE,
                sample_size=self.sample_size if self.sample_size > 0 else None,
                is_heuristic_ci=True,
                gate_eligible=False,
                metadata={
                    "causal_method": self.method.value,
                    "estimand": self.estimand,
                    "inference_method": self.inference_method,
                    "status": self.status.value,
                    "status_reason": self.status_reason,
                    "failure_envelope": True,
                    "assumptions": dict(self.assumptions),
                },
            )
        if self.point_estimate is None or self.confidence_interval is None:
            return None

        family_map = {
            "placebo_permutation": DistributionFamily.BOOTSTRAP,
            "bootstrap": DistributionFamily.BOOTSTRAP,
            "asymptotic": DistributionFamily.NORMAL,
            "state_space_simulation": DistributionFamily.UNKNOWN,
            "bayesian_posterior": DistributionFamily.BAYESIAN,
        }
        family = family_map.get(self.inference_method, DistributionFamily.UNKNOWN)
        interval_semantics = (
            IntervalSemantics.CREDIBLE_INTERVAL
            if self.inference_method == "bayesian_posterior"
            else IntervalSemantics.CONFIDENCE_INTERVAL
        )

        return UncertaintyEnvelope(
            point_estimate=self.point_estimate,
            confidence_interval=self.confidence_interval,
            confidence_level=self.confidence_level,
            distribution_family=family,
            source=UncertaintySource.CAUSAL,
            propagation_method=PropagationMethod.NONE,
            interval_semantics=interval_semantics,
            sample_size=self.sample_size if self.sample_size > 0 else None,
            is_heuristic_ci=False,
            gate_eligible=True,
            metadata={
                "causal_method": self.method.value,
                "estimand": self.estimand,
                "inference_method": self.inference_method,
                "status": self.status.value,
                "status_reason": self.status_reason,
                "p_value": self.p_value,
                "placebo_p_value": self.placebo_p_value,
                "assumptions": dict(self.assumptions),
            },
        )


def persist_causal_effect_report(
    store: "FileSystemCAS",
    report: CausalEffectReport,
    *,
    inputs: list["InputRef"] | None = None,
    schema_name: str = "ir.causal_effect_report",
    schema_version: str = "1.0",
) -> "CausalEffectReportRef":
    from polisyos.core.artifacts.manifest import SchemaInfo
    from polisyos.core.artifacts.store import PutOptions
    from polisyos.core.contracts.causal import CausalEffectReportRef

    ref = store.put_json(
        report.model_dump(mode="json"),
        opts=PutOptions(
            kind="ir.causal_effect_report",
            media_type="application/json",
            schema=SchemaInfo(name=schema_name, version=schema_version),
            inputs=inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return CausalEffectReportRef.model_validate(ref.model_dump())


def load_causal_effect_report(
    store: "FileSystemCAS",
    ref: "CausalEffectReportRef",
) -> CausalEffectReport:
    payload = from_canonical_bytes(store.get_bytes(ref.artifact_id))
    return CausalEffectReport.model_validate(payload)


__all__ = [
    "CausalMethod",
    "EstimationStatus",
    "PlaceboResult",
    "DiagnosticTest",
    "CausalEffectReport",
    "persist_causal_effect_report",
    "load_causal_effect_report",
]
