"""Regime-aware forecasting uncertainty contracts for structural breaks."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, ClassVar

from pydantic import ConfigDict, Field, model_validator

from polisyos.ir.analytics.forecasting_uncertainty import ForecastingUncertaintyBundle
from polisyos.ir.analytics.uncertainty import (
    OutputContractDeclaration,
    value_uncertainty_output_contract,
)
from polisyos.ir.artifacts import ArtifactStore, InputRef, get_json_artifact, put_json_artifact
from polisyos.ir.model_layer.canon import CanonSpec
from polisyos.ir.registry.refs import ArtifactRefModel, RegimeShiftForecastBundleRef


class RegimeModelFamily(StrEnum):
    """Forecasting model family used to represent regime uncertainty."""

    MARKOV_SWITCHING = "markov_switching"
    HIDDEN_SEMI_MARKOV = "hidden_semi_markov"
    CHANGEPOINT = "changepoint"
    HYBRID = "hybrid"


class RegimeIdentifiabilityStatus(StrEnum):
    """Machine-readable result of the regime identifiability gates."""

    IDENTIFIED = "identified"
    WEAKLY_IDENTIFIED = "weakly_identified"
    NOT_IDENTIFIED = "not_identified"


class RegimeForecastCalibrationStatus(StrEnum):
    """Production gate status for regime-aware forecast horizons."""

    CALIBRATED = "calibrated"
    WEAKLY_CALIBRATED = "weakly_calibrated"
    UNKNOWN = "unknown"
    DRIFTING = "drifting"


class ForecastShiftTypeAssessment(StrEnum):
    """Shared forecast/causal vocabulary for the type of observed shift."""

    STRUCTURAL = "structural"
    SELECTION = "selection"
    LATENT_CONFOUNDED = "latent_confounded"
    MIXED = "mixed"
    UNKNOWN = "unknown"


class RegimeBenchmarkStatus(StrEnum):
    """Traffic-light acceptance result from the regime calibration benchmark."""

    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"


def _validate_artifact_ref(ref: ArtifactRefModel | None, *, field_name: str) -> None:
    if ref is None:
        return
    if not str(ref.kind).strip():
        raise ValueError(f"{field_name}.kind must be non-empty")
    if not str(ref.media_type).strip():
        raise ValueError(f"{field_name}.media_type must be non-empty")


class RegimeShiftForecastBundle(ForecastingUncertaintyBundle):
    """Forecasting bundle carrying latent regime and break-date uncertainty."""

    contract_id: ClassVar[str] = "ir.regime_shift_forecast_bundle.v1"
    output_contract_declaration: ClassVar[OutputContractDeclaration] = (
        value_uncertainty_output_contract(contract_id)
    )
    model_config = ConfigDict(extra="forbid", frozen=True)

    regime_model_family: RegimeModelFamily
    identifiability_status: RegimeIdentifiabilityStatus
    regime_status: RegimeForecastCalibrationStatus = RegimeForecastCalibrationStatus.UNKNOWN

    regime_count_posterior_ref: ArtifactRefModel
    break_count_posterior_ref: ArtifactRefModel | None = None
    assignment_posterior_ref: ArtifactRefModel
    break_posterior_ref: ArtifactRefModel | None = None
    run_length_posterior_ref: ArtifactRefModel | None = None

    permutation_invariant_regime_map_ref: ArtifactRefModel
    regime_parameter_summary_ref: ArtifactRefModel
    duration_summary_ref: ArtifactRefModel | None = None
    transition_summary_ref: ArtifactRefModel | None = None

    predictive_mixture_ref: ArtifactRefModel
    regime_conditional_forecasts_ref: ArtifactRefModel
    calibration_slice_ref: ArtifactRefModel
    break_recovery_curve_ref: ArtifactRefModel
    shift_type_assessment: ForecastShiftTypeAssessment
    shift_type_assessment_ref: ArtifactRefModel | None = None

    identifiability_diagnostics_ref: ArtifactRefModel
    benchmark_status: RegimeBenchmarkStatus

    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_regime_contract(self) -> RegimeShiftForecastBundle:
        for field_name in (
            "regime_count_posterior_ref",
            "break_count_posterior_ref",
            "assignment_posterior_ref",
            "break_posterior_ref",
            "run_length_posterior_ref",
            "permutation_invariant_regime_map_ref",
            "regime_parameter_summary_ref",
            "duration_summary_ref",
            "transition_summary_ref",
            "predictive_mixture_ref",
            "regime_conditional_forecasts_ref",
            "calibration_slice_ref",
            "break_recovery_curve_ref",
            "shift_type_assessment_ref",
            "identifiability_diagnostics_ref",
        ):
            _validate_artifact_ref(getattr(self, field_name), field_name=field_name)

        if self.regime_model_family in {
            RegimeModelFamily.CHANGEPOINT,
            RegimeModelFamily.HYBRID,
        }:
            if self.break_count_posterior_ref is None:
                raise ValueError("changepoint and hybrid bundles require break_count_posterior_ref")
            if self.break_posterior_ref is None and self.run_length_posterior_ref is None:
                raise ValueError(
                    "changepoint and hybrid bundles require break_posterior_ref "
                    "or run_length_posterior_ref"
                )

        if (
            self.regime_model_family is RegimeModelFamily.HIDDEN_SEMI_MARKOV
            and self.duration_summary_ref is None
        ):
            raise ValueError("hidden semi-Markov bundles require duration_summary_ref")

        if (
            self.benchmark_status is RegimeBenchmarkStatus.GREEN
            and self.identifiability_status is not RegimeIdentifiabilityStatus.IDENTIFIED
        ):
            raise ValueError("green benchmark status requires identified regimes")

        if self.regime_status is RegimeForecastCalibrationStatus.CALIBRATED:
            if self.identifiability_status is not RegimeIdentifiabilityStatus.IDENTIFIED:
                raise ValueError("calibrated regime status requires identified regimes")
            if self.benchmark_status is not RegimeBenchmarkStatus.GREEN:
                raise ValueError("calibrated regime status requires a green benchmark")

        if self._max_declared_horizon() > 12:
            if self.regime_status is not RegimeForecastCalibrationStatus.CALIBRATED:
                raise ValueError(
                    "forecasts beyond horizon 12 require calibrated regime status"
                )

        return self

    def _max_declared_horizon(self) -> int:
        horizons = [interval.horizon for interval in self.prediction_interval]
        horizons.extend(entry.horizon for entry in self.fan_chart.horizons)
        return max(horizons, default=0)


def persist_regime_shift_forecast_bundle(
    store: ArtifactStore,
    bundle: RegimeShiftForecastBundle,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = "ir.regime_shift_forecast_bundle",
    schema_version: str = "1.0",
) -> RegimeShiftForecastBundleRef:
    """Persist a regime-shift forecast bundle as a typed JSON artifact."""

    ref = put_json_artifact(
        store,
        bundle.model_dump(mode="json", round_trip=True),
        kind="ir.regime_shift_forecast_bundle",
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return RegimeShiftForecastBundleRef.model_validate(ref)


def load_regime_shift_forecast_bundle(
    store: ArtifactStore,
    ref: RegimeShiftForecastBundleRef,
) -> RegimeShiftForecastBundle:
    """Load a regime-shift forecast bundle from artifact storage."""

    payload = get_json_artifact(store, ref.artifact_id)
    return RegimeShiftForecastBundle.model_validate(payload)


__all__ = [
    "ForecastShiftTypeAssessment",
    "RegimeBenchmarkStatus",
    "RegimeForecastCalibrationStatus",
    "RegimeIdentifiabilityStatus",
    "RegimeModelFamily",
    "RegimeShiftForecastBundle",
    "load_regime_shift_forecast_bundle",
    "persist_regime_shift_forecast_bundle",
]
