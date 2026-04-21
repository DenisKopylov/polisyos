"""Define survey-calibration contracts for noisy auxiliary totals and weight outputs."""
from __future__ import annotations

from typing import Any, ClassVar, Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator, model_validator

from polisyos.ir.observation.bundles import ContractCompatibilityTarget
from polisyos.ir.refs import ArtifactRefModel, DependenceStructureRef

SCHEMA_VERSION_PATTERN = r"^\d+\.\d+$"
_PSD_TOL = 1e-10


def _to_numpy(value: Any) -> np.ndarray:
    if isinstance(value, np.ndarray):
        return value
    return np.asarray(value, dtype=float)


def _validate_vector(name: str, value: Any, *, expected_length: int | None = None) -> np.ndarray:
    arr = _to_numpy(value)
    if arr.ndim != 1:
        raise ValueError(f"{name} must be a 1D numpy array")
    if expected_length is not None and arr.shape[0] != expected_length:
        raise ValueError(f"{name} length must equal {expected_length}")
    if not np.all(np.isfinite(arr)):
        raise ValueError(f"{name} must contain only finite values")
    return arr


def _validate_square_matrix(name: str, value: Any, *, expected_size: int | None = None) -> np.ndarray:
    arr = _to_numpy(value)
    if arr.ndim != 2 or arr.shape[0] != arr.shape[1]:
        raise ValueError(f"{name} must be a square 2D numpy array")
    if expected_size is not None and arr.shape != (expected_size, expected_size):
        raise ValueError(f"{name} must have shape {(expected_size, expected_size)}")
    if not np.all(np.isfinite(arr)):
        raise ValueError(f"{name} must contain only finite values")
    return arr


def _validate_symmetric_psd(name: str, value: np.ndarray) -> np.ndarray:
    if not np.allclose(value, value.T, atol=_PSD_TOL):
        raise ValueError(f"{name} must be symmetric")
    eigvals = np.linalg.eigvalsh(0.5 * (value + value.T))
    min_eig = float(np.min(eigvals)) if eigvals.size else 0.0
    if min_eig < -_PSD_TOL:
        raise ValueError(f"{name} must be positive semidefinite")
    return value


class AuxiliaryTotalUncertainty(BaseModel):
    """Describe uncertainty attached to auxiliary population totals used by GREG."""

    contract_id: ClassVar[str] = "foundry.survey.auxiliary_total_uncertainty.v1"
    contract_fqn: ClassVar[str] = (
        "polisyos.foundry.methods.catalog.survey.protocols.AuxiliaryTotalUncertainty"
    )
    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    schema_version: str = Field("1.0", pattern=SCHEMA_VERSION_PATTERN)
    source_kind: Literal[
        "exact",
        "estimated_external",
        "estimated_internal",
        "two_phase",
        "model_based",
        "time_series_benchmark",
        "multiple_imputation",
    ]
    target_names: list[str] = Field(..., min_length=1)
    units: list[str] | None = None
    variance: Any | None = None
    standard_error: Any | None = None
    covariance_matrix: Any | None = None
    correlation_matrix: Any | None = None
    degrees_of_freedom: int | None = Field(default=None, ge=1)
    replicate_totals: Any | None = None
    estimation_method: str | None = None
    source_dataset: str | None = None
    reference_period: str | None = None
    notes: list[str] = Field(default_factory=list)

    @field_validator(
        "variance",
        "standard_error",
        "covariance_matrix",
        "correlation_matrix",
        "replicate_totals",
        mode="before",
    )
    @classmethod
    def _coerce_numpy(cls, value: Any) -> Any:
        if value is None:
            return None
        return _to_numpy(value)

    @field_serializer(
        "variance",
        "standard_error",
        "covariance_matrix",
        "correlation_matrix",
        "replicate_totals",
        mode="plain",
        when_used="json",
    )
    def _serialize_numpy(self, value: Any) -> Any:
        if isinstance(value, np.ndarray):
            return value.tolist()
        return value

    @model_validator(mode="after")
    def _validate_structure(self) -> "AuxiliaryTotalUncertainty":
        n_targets = len(self.target_names)
        if len(set(self.target_names)) != n_targets:
            raise ValueError("target_names must be unique")
        if self.units is not None and len(self.units) != n_targets:
            raise ValueError("units length must match target_names")

        has_cov = self.covariance_matrix is not None
        has_var = self.variance is not None
        has_se = self.standard_error is not None
        has_corr = self.correlation_matrix is not None
        has_replicates = self.replicate_totals is not None

        if has_corr and not has_se:
            raise ValueError("correlation_matrix requires standard_error")

        representation_count = int(has_cov) + int(has_var) + int(has_replicates) + int(has_se)
        if self.source_kind == "exact":
            if has_replicates:
                raise ValueError("exact uncertainty cannot include replicate_totals")
            if representation_count == 0:
                return self
            covariance = self.to_covariance()
            if not np.allclose(covariance, 0.0, atol=_PSD_TOL):
                raise ValueError("exact uncertainty must omit variance-like fields or set them to zero")
            return self

        if representation_count != 1:
            raise ValueError(
                "provide exactly one of covariance_matrix, variance, standard_error, or replicate_totals"
            )

        if has_var:
            variance = _validate_vector("variance", self.variance, expected_length=n_targets)
            if np.any(variance < 0.0):
                raise ValueError("variance must be non-negative")

        if has_se:
            standard_error = _validate_vector(
                "standard_error",
                self.standard_error,
                expected_length=n_targets,
            )
            if np.any(standard_error < 0.0):
                raise ValueError("standard_error must be non-negative")
            if has_corr:
                corr = _validate_square_matrix(
                    "correlation_matrix",
                    self.correlation_matrix,
                    expected_size=n_targets,
                )
                _validate_symmetric_psd("correlation_matrix", corr)
                if not np.allclose(np.diag(corr), 1.0, atol=1e-8):
                    raise ValueError("correlation_matrix diagonal must equal 1")
                if np.any(np.abs(corr) > 1.0 + 1e-8):
                    raise ValueError("correlation_matrix entries must lie in [-1, 1]")

        if has_cov:
            covariance = _validate_square_matrix(
                "covariance_matrix",
                self.covariance_matrix,
                expected_size=n_targets,
            )
            _validate_symmetric_psd("covariance_matrix", covariance)

        if has_replicates:
            replicates = _to_numpy(self.replicate_totals)
            if replicates.ndim != 2 or replicates.shape[1] != n_targets:
                raise ValueError("replicate_totals must be a 2D array with one column per target")
            if replicates.shape[0] < 2:
                raise ValueError("replicate_totals require at least two replicates")
            if not np.all(np.isfinite(replicates)):
                raise ValueError("replicate_totals must contain only finite values")

        return self

    @property
    def n_targets(self) -> int:
        return len(self.target_names)

    def to_covariance(self, *, reference_totals: Any | None = None) -> np.ndarray:
        """Materialize the covariance matrix used to relax calibration constraints."""
        p = self.n_targets
        if self.covariance_matrix is not None:
            return np.asarray(self.covariance_matrix, dtype=float)
        if self.variance is not None:
            variance = np.asarray(self.variance, dtype=float)
            return np.diag(variance)
        if self.standard_error is not None:
            standard_error = np.asarray(self.standard_error, dtype=float)
            if self.correlation_matrix is None:
                return np.diag(standard_error**2)
            correlation = np.asarray(self.correlation_matrix, dtype=float)
            return np.diag(standard_error) @ correlation @ np.diag(standard_error)
        if self.replicate_totals is not None:
            replicates = np.asarray(self.replicate_totals, dtype=float)
            if reference_totals is None:
                center = np.mean(replicates, axis=0)
            else:
                center = _validate_vector("reference_totals", reference_totals, expected_length=p)
            centered = replicates - center
            divisor = max(replicates.shape[0] - 1, 1)
            covariance = (centered.T @ centered) / float(divisor)
            return 0.5 * (covariance + covariance.T)
        return np.zeros((p, p), dtype=float)


class CalibrationWeights(BaseModel):
    """Carry calibrated weights plus diagnostics for exact or relaxed survey calibration."""

    contract_id: ClassVar[str] = "foundry.survey.calibration_weights.v1"
    contract_fqn: ClassVar[str] = "polisyos.foundry.methods.catalog.survey.protocols.CalibrationWeights"
    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    calibrated_weights: Any
    lambda_: Any
    achieved_totals: Any
    control_residual: Any
    uncertainty_covariance_used: Any
    constraint_mode: Literal["exact", "relaxed"]
    solver_status: Literal["ok", "regularized", "fallback_pinv", "failed"]
    design_weights: Any | None = None
    x_sample: Any | None = None
    known_totals: Any | None = None
    q_weights: Any | None = None
    auxiliary_total_uncertainty: AuxiliaryTotalUncertainty | None = None
    bounds: tuple[float, float] | None = None
    sample_aux_error_cov: Any | None = None
    diagnostics: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "calibrated_weights",
        "lambda_",
        "achieved_totals",
        "control_residual",
        "uncertainty_covariance_used",
        "design_weights",
        "x_sample",
        "known_totals",
        "q_weights",
        "sample_aux_error_cov",
        mode="before",
    )
    @classmethod
    def _coerce_arrays(cls, value: Any) -> Any:
        if value is None:
            return None
        return _to_numpy(value)

    @field_serializer(
        "calibrated_weights",
        "lambda_",
        "achieved_totals",
        "control_residual",
        "uncertainty_covariance_used",
        "design_weights",
        "x_sample",
        "known_totals",
        "q_weights",
        "sample_aux_error_cov",
        mode="plain",
        when_used="json",
    )
    def _serialize_arrays(self, value: Any) -> Any:
        if isinstance(value, np.ndarray):
            return value.tolist()
        return value

    @model_validator(mode="after")
    def _validate_shapes(self) -> "CalibrationWeights":
        calibrated_weights = _validate_vector("calibrated_weights", self.calibrated_weights)
        design_weights = (
            _validate_vector("design_weights", self.design_weights, expected_length=calibrated_weights.shape[0])
            if self.design_weights is not None
            else None
        )
        q_weights = (
            _validate_vector("q_weights", self.q_weights, expected_length=calibrated_weights.shape[0])
            if self.q_weights is not None
            else None
        )
        lambda_ = _validate_vector("lambda_", self.lambda_)
        achieved_totals = _validate_vector(
            "achieved_totals",
            self.achieved_totals,
            expected_length=lambda_.shape[0],
        )
        _validate_vector(
            "control_residual",
            self.control_residual,
            expected_length=lambda_.shape[0],
        )
        covariance = _validate_square_matrix(
            "uncertainty_covariance_used",
            self.uncertainty_covariance_used,
            expected_size=lambda_.shape[0],
        )
        _validate_symmetric_psd("uncertainty_covariance_used", covariance)

        if self.known_totals is not None:
            _validate_vector("known_totals", self.known_totals, expected_length=lambda_.shape[0])
        if self.x_sample is not None:
            x_sample = np.asarray(self.x_sample, dtype=float)
            if x_sample.ndim != 2:
                raise ValueError("x_sample must be a 2D numpy array")
            if x_sample.shape != (calibrated_weights.shape[0], lambda_.shape[0]):
                raise ValueError("x_sample shape must match calibrated_weights x lambda_ dimensions")
        if self.sample_aux_error_cov is not None:
            sample_aux = _validate_square_matrix(
                "sample_aux_error_cov",
                self.sample_aux_error_cov,
                expected_size=lambda_.shape[0],
            )
            if not np.allclose(sample_aux, sample_aux.T, atol=_PSD_TOL):
                raise ValueError("sample_aux_error_cov must be symmetric")
        if design_weights is not None and np.any(design_weights <= 0.0):
            raise ValueError("design_weights must be strictly positive")
        if q_weights is not None and np.any(q_weights <= 0.0):
            raise ValueError("q_weights must be strictly positive")
        if self.bounds is not None:
            lower, upper = map(float, self.bounds)
            if not np.isfinite(lower) or not np.isfinite(upper):
                raise ValueError("bounds must be finite")
            if lower >= upper:
                raise ValueError("bounds must satisfy lower < upper")
        return self


AUXILIARY_TOTAL_UNCERTAINTY_TARGET = ContractCompatibilityTarget(
    contract_id=AuxiliaryTotalUncertainty.contract_id,
    contract_fqn=AuxiliaryTotalUncertainty.contract_fqn,
)
CALIBRATION_WEIGHTS_TARGET = ContractCompatibilityTarget(
    contract_id=CalibrationWeights.contract_id,
    contract_fqn=CalibrationWeights.contract_fqn,
)


class SAEResult(BaseModel):
    """Typed small-area estimation result with shared Phase 1 dependence hook."""

    contract_id: ClassVar[str] = "foundry.survey.sae_result.v1"
    model_config = ConfigDict(extra="forbid", frozen=True)

    method_name: str
    statistics: dict[str, Any] = Field(default_factory=dict)
    dependence_ref: DependenceStructureRef | None = None
    quality_certificate_ref: ArtifactRefModel | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


__all__ = [
    "AUXILIARY_TOTAL_UNCERTAINTY_TARGET",
    "SAEResult",
    "AuxiliaryTotalUncertainty",
    "CALIBRATION_WEIGHTS_TARGET",
    "CalibrationWeights",
]
