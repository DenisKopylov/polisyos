"""Public analytics sensitivity module API."""

from __future__ import annotations

import math
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.ir.artifacts import ArtifactStore, InputRef, get_json_artifact, put_json_artifact
from polisyos.ir.model_layer.canon import CanonSpec
from polisyos.ir.registry.refs import CausalSensitivityResultRef, SensitivityAnalysisBundleRef


class BenchmarkResult(BaseModel):
    """Cinelli-Hazlett benchmarking result relative to a named observed covariate.

    Quantifies how much confounding would be needed (relative to this covariate's
    association strength) to explain away the estimated effect.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    covariate_name: str
    r2yd_x: float | None = None
    """Partial R² of this covariate on outcome (controlling for treatment + other covariates)."""
    r2td_x: float | None = None
    """Partial R² of this covariate on treatment (controlling for other covariates)."""
    bias_scale: float | None = None
    """How many times this covariate's confounding would be needed to explain away the effect.
    Computed as r2td_x / partial_r2_treatment. Values > 1 indicate the effect is more robust
    than a confounder with the same strength as this covariate."""
    rv_benchmarked: float | None = None
    """Robustness Value benchmarked relative to this covariate's partial R². Provided by
    sensemakr when available."""
    interpretation: str = ""
    """Human-readable summary of this benchmark."""

    @model_validator(mode="after")
    def _validate(self) -> BenchmarkResult:
        for field in ("r2yd_x", "r2td_x"):
            val = getattr(self, field)
            if val is not None:
                if not math.isfinite(val):
                    raise ValueError(f"{field} must be finite")
                if not (0.0 <= val <= 1.0):
                    raise ValueError(f"{field} must be in [0, 1]")
        return self


class EValueResult(BaseModel):
    """E value result data model."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    raw_effect: float
    rr_equivalent: float = Field(gt=0.0)
    method: str = Field(min_length=1)
    ci_rr: tuple[float, float] | None = None
    ci_crosses_null: bool = False
    details: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate(self) -> EValueResult:
        if not math.isfinite(self.raw_effect):
            raise ValueError("raw_effect must be finite")
        if not math.isfinite(self.rr_equivalent):
            raise ValueError("rr_equivalent must be finite")
        if self.ci_rr is not None:
            lo, hi = self.ci_rr
            if not math.isfinite(lo) or not math.isfinite(hi):
                raise ValueError("ci_rr bounds must be finite")
            if lo <= 0 or hi <= 0:
                raise ValueError("ci_rr bounds must be > 0")
            if lo > hi:
                raise ValueError("ci_rr lower bound cannot exceed upper bound")
        return self


class SensitivityResult(BaseModel):
    """Sensitivity result data model."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")

    e_value: float | None = None
    e_value_ci_lower: float | None = None
    conversion_method: str | None = None
    e_value_result: EValueResult | None = None

    robustness_value: float | None = None
    partial_r2_treatment: float | None = None

    rosenbaum_gamma: float | None = None
    rosenbaum_p_value: float | None = None

    interpretation: str = ""
    is_robust: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)

    benchmark_results: list[BenchmarkResult] = Field(default_factory=list)
    """Cinelli-Hazlett benchmarks relative to named observed covariates."""
    benchmark_covariates: list[str] = Field(default_factory=list)
    """Names of covariates used for benchmarking."""

    @model_validator(mode="after")
    def _validate(self) -> SensitivityResult:
        for field in (
            "e_value",
            "e_value_ci_lower",
            "robustness_value",
            "partial_r2_treatment",
            "rosenbaum_gamma",
            "rosenbaum_p_value",
        ):
            value = getattr(self, field)
            if value is None:
                continue
            if not math.isfinite(value):
                raise ValueError(f"{field} must be finite")

        if self.e_value is not None and self.e_value < 1.0:
            raise ValueError("E-value must be >= 1.0")
        if self.e_value_ci_lower is not None and self.e_value_ci_lower < 1.0:
            raise ValueError("E-value CI lower must be >= 1.0")
        if self.partial_r2_treatment is not None and not (0.0 <= self.partial_r2_treatment <= 1.0):
            raise ValueError("partial_r2_treatment must be in [0,1]")
        if self.rosenbaum_p_value is not None and not (0.0 <= self.rosenbaum_p_value <= 1.0):
            raise ValueError("rosenbaum_p_value must be in [0,1]")
        return self


class SensitivityAnalysisIndex(BaseModel):
    """Canonical Phase-5 sensitivity index with required uncertainty evidence."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    parameter: str | None = None
    estimate: float | None = None
    standard_error: float | None = None
    ci: tuple[float, float] | None = None
    blocking_reason: str | None = None
    source: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_uncertainty_evidence(self) -> SensitivityAnalysisIndex:
        if self.standard_error is None and self.ci is None and not self.blocking_reason:
            raise ValueError(
                "sensitivity index requires standard_error, ci, or explicit blocking_reason"
            )
        if self.ci is not None and self.ci[0] > self.ci[1]:
            raise ValueError("ci lower bound cannot exceed upper bound")
        return self


class SensitivityAnalysisBundle(BaseModel):
    """Canonical Phase-5 wrapper over causal, dependent, distributional, and DOE indices."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    kind: Literal["scientist.sensitivity_analysis_bundle"] = "scientist.sensitivity_analysis_bundle"
    bundle_id: str
    indices: list[SensitivityAnalysisIndex] = Field(default_factory=list)
    source_refs: list[str] = Field(default_factory=list)
    source_payloads: dict[str, Any] = Field(default_factory=dict)
    diagnostics: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_indices(self) -> SensitivityAnalysisBundle:
        if not self.indices:
            raise ValueError("SensitivityAnalysisBundle requires at least one index")
        return self


def persist_sensitivity_result(
    store: ArtifactStore,
    result: SensitivityResult,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = "ir.sensitivity_result",
    schema_version: str = "1.0",
) -> CausalSensitivityResultRef:
    """Persist sensitivity result helper."""
    ref = put_json_artifact(
        store,
        result.model_dump(mode="json"),
        kind="ir.sensitivity_result",
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return CausalSensitivityResultRef.model_validate(ref)


def load_sensitivity_result(
    store: ArtifactStore,
    ref: CausalSensitivityResultRef,
) -> SensitivityResult:
    """Load sensitivity result."""
    payload = get_json_artifact(store, ref.artifact_id)
    return SensitivityResult.model_validate(payload)


def sensitivity_analysis_bundle_from_result(
    result: SensitivityResult,
    *,
    bundle_id: str = "legacy_sensitivity_result",
    source_ref: str | None = None,
) -> SensitivityAnalysisBundle:
    """Wrap a legacy SensitivityResult in the canonical Phase-5 bundle surface."""

    indices: list[SensitivityAnalysisIndex] = []
    source = "legacy_sensitivity_result"
    if result.e_value is not None:
        indices.append(
            SensitivityAnalysisIndex(
                name="e_value",
                estimate=result.e_value,
                ci=(
                    (result.e_value_ci_lower, result.e_value)
                    if result.e_value_ci_lower is not None
                    else None
                ),
                blocking_reason=(
                    None
                    if result.e_value_ci_lower is not None
                    else "legacy e_value lacks uncertainty evidence"
                ),
                source=source,
            )
        )
    if result.robustness_value is not None:
        indices.append(
            SensitivityAnalysisIndex(
                name="robustness_value",
                estimate=result.robustness_value,
                blocking_reason="legacy robustness_value lacks uncertainty evidence",
                source=source,
            )
        )
    if result.rosenbaum_gamma is not None:
        indices.append(
            SensitivityAnalysisIndex(
                name="rosenbaum_gamma",
                estimate=result.rosenbaum_gamma,
                blocking_reason="legacy rosenbaum_gamma lacks uncertainty evidence",
                source=source,
            )
        )
    if not indices:
        indices.append(
            SensitivityAnalysisIndex(
                name="legacy_sensitivity_result",
                blocking_reason="legacy sensitivity result has no reportable index",
                source=source,
            )
        )
    return SensitivityAnalysisBundle(
        bundle_id=bundle_id,
        indices=indices,
        source_refs=[] if source_ref is None else [source_ref],
        source_payloads={"legacy": result.model_dump(mode="json")},
    )


def persist_sensitivity_analysis_bundle(
    store: ArtifactStore,
    bundle: SensitivityAnalysisBundle,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = "polisyos.scientist.sensitivity_analysis_bundle",
    schema_version: str = "1.0",
) -> SensitivityAnalysisBundleRef:
    """Persist a canonical Phase-5 sensitivity bundle."""

    ref = put_json_artifact(
        store,
        bundle.model_dump(mode="json"),
        kind="scientist.sensitivity_analysis_bundle",
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return SensitivityAnalysisBundleRef.model_validate(ref)


def load_sensitivity_analysis_bundle(
    store: ArtifactStore,
    ref: SensitivityAnalysisBundleRef,
) -> SensitivityAnalysisBundle:
    """Load a canonical Phase-5 sensitivity bundle."""

    payload = get_json_artifact(store, ref.artifact_id)
    return SensitivityAnalysisBundle.model_validate(payload)


__all__ = [
    "BenchmarkResult",
    "EValueResult",
    "SensitivityAnalysisBundle",
    "SensitivityAnalysisIndex",
    "SensitivityResult",
    "load_sensitivity_analysis_bundle",
    "load_sensitivity_result",
    "persist_sensitivity_analysis_bundle",
    "persist_sensitivity_result",
    "sensitivity_analysis_bundle_from_result",
]
