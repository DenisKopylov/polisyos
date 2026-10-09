"""Compositional uncertainty contracts shared across IR analytics outputs."""

from __future__ import annotations

import inspect
import math
import re
from dataclasses import dataclass
from enum import Enum
from statistics import NormalDist
from typing import TYPE_CHECKING, Annotated, Any, ClassVar, Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from polisyos.common import serialization
from polisyos.ir.artifacts import (
    ArtifactID,
    ArtifactStore,
    InputRef,
    get_json_artifact,
    normalize_artifact_ref,
    put_json_artifact,
)
from polisyos.ir.artifacts.contracts import (
    _is_string_root_model,
    _normalize_scalar_artifact_id,
)
from polisyos.ir.model_layer.canon import CanonSpec, content_hash, to_canonical_bytes
from polisyos.ir.registry.refs import ArtifactRefModel, UncertaintyEnvelopeRef

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

    from polisyos.ir.kernel.trust import TrustPolicySpec


class UncertaintyCompatibilityError(ValueError):
    """Raised when envelopes with incompatible interval semantics are combined."""


class UncertaintyType(str, Enum):
    """Typed uncertainty categories shared by analytical failure contracts."""

    STATISTICAL = "statistical"
    STRUCTURAL = "structural"
    TRANSPORT = "transport"
    MEASUREMENT = "measurement"
    MODEL = "model"
    OPTIMIZATION = "optimization"


class FailureSeverity(str, Enum):
    """Severity of a typed analytical failure."""

    BLOCKER = "blocker"
    WARNING = "warning"
    INFO = "info"


class TypedFailureCard(BaseModel):
    """Structured failure record shared by analytical producers and consumers."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    judge_name: str = Field(min_length=1)
    failure_type: str = Field(min_length=1)
    severity: FailureSeverity
    description: str = Field(min_length=1)
    uncertainty_type: UncertaintyType | None = None
    remediation_hint: str | None = None
    evidence_ref: ArtifactRefModel | None = None
    metric_name: str | None = None
    observed_value: float | None = None
    threshold_value: float | None = None
    threshold_direction: Literal["max", "min"] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def is_blocker(self) -> bool:
        """Return whether this failure blocks the evaluated operation."""

        return self.severity is FailureSeverity.BLOCKER


class OutputContractCapability(str, Enum):
    """Typed semantic capabilities owned by native analytical output contracts."""

    VALUE_UNCERTAINTY_PROJECTION = "value_uncertainty_projection"


class ValueUncertaintyProjectionKind(str, Enum):
    """Native interval semantics owned by an analytical output contract."""

    POSTERIOR = "posterior"
    ECONOMETRIC = "econometric"
    FORECASTING = "forecasting"
    DISTRIBUTIONAL = "distributional"
    PARTIAL_IDENTIFICATION = "partial_identification"
    TRANSPORT = "transport"


@dataclass(frozen=True, slots=True)
class OutputContractDeclaration:
    """Bind a native contract identifier to its owner-declared capabilities."""

    contract_id: str
    capabilities: frozenset[OutputContractCapability] = frozenset()
    value_uncertainty_projection_kind: ValueUncertaintyProjectionKind | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.contract_id, str) or not self.contract_id.strip():
            raise ValueError("output_contract_declaration_contract_id_invalid")
        normalized = frozenset(self.capabilities)
        if not all(isinstance(item, OutputContractCapability) for item in normalized):
            raise TypeError("output_contract_declaration_capability_invalid")
        owns_value_projection = OutputContractCapability.VALUE_UNCERTAINTY_PROJECTION in normalized
        if owns_value_projection != isinstance(
            self.value_uncertainty_projection_kind,
            ValueUncertaintyProjectionKind,
        ):
            raise ValueError("output_contract_projection_kind_capability_mismatch")
        object.__setattr__(self, "capabilities", normalized)


class NativeValueEstimandBinding(BaseModel):
    """Bind one contract-only projection probe to a complete value estimand.

    This request is intentionally caller-constructible and therefore carries
    no production or promotion authority.  A future production lane must bind
    a separate owner-resolved method-run receipt; this object only proves that
    a native output contract can project its own interval semantics.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["polisyos.ir.native_value_estimand_binding.v1"] = (
        "polisyos.ir.native_value_estimand_binding.v1"
    )
    authority_scope: Literal["contract_only_nonproduction"] = "contract_only_nonproduction"
    production_value_eligible: Literal[False] = False
    binding_kind: Literal["contract_projection_request"] = "contract_projection_request"
    native_contract_id: str = Field(min_length=1)
    producer_method_fqn: str = Field(min_length=1)
    projection_input_content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    query_id: str = Field(min_length=1)
    estimand_id: str = Field(min_length=1)
    outcome: str = Field(min_length=1)
    treatment_or_exposure: str | None = None
    covariates_or_conditioning: tuple[str, ...] = ()
    adjustment_set: tuple[str, ...] | None = None
    population: str = Field(min_length=1)
    sample_filter: str | None = None
    time_horizon: str | None = None
    prediction_origin: str | None = None
    unit: str = Field(min_length=1)
    scale: str = Field(min_length=1)
    transform: str | None = None
    target_role: str = Field(min_length=1)
    loss_or_utility_id: str | None = None
    content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _verify_content_hash(self) -> NativeValueEstimandBinding:
        payload = serialization.artifact_self_identity_projection(self)
        if self.content_hash != _native_value_estimand_binding_hash(payload):
            raise ValueError("native_value_estimand_binding_content_hash_mismatch")
        return self

    @classmethod
    def from_estimand(
        cls,
        *,
        estimand: object,
        native_contract_id: str,
        producer_method_fqn: str,
        projection_input_content_hash: str,
    ) -> NativeValueEstimandBinding:
        """Build a binding from an owner-resolved method input estimand."""

        payload = {
            "schema_version": "polisyos.ir.native_value_estimand_binding.v1",
            "authority_scope": "contract_only_nonproduction",
            "production_value_eligible": False,
            "binding_kind": "contract_projection_request",
            "native_contract_id": native_contract_id,
            "producer_method_fqn": producer_method_fqn,
            "projection_input_content_hash": projection_input_content_hash,
            "query_id": str(getattr(estimand, "query_id", "") or ""),
            "estimand_id": str(getattr(estimand, "estimand_id", "") or ""),
            "outcome": str(getattr(estimand, "outcome", "") or ""),
            "treatment_or_exposure": _optional_estimand_text(
                getattr(estimand, "treatment_or_exposure", None)
            ),
            "covariates_or_conditioning": tuple(
                str(item) for item in getattr(estimand, "covariates_or_conditioning", ())
            ),
            "adjustment_set": _optional_estimand_tuple(getattr(estimand, "adjustment_set", None)),
            "population": str(getattr(estimand, "population", "") or ""),
            "sample_filter": _optional_estimand_text(getattr(estimand, "sample_filter", None)),
            "time_horizon": _optional_estimand_text(getattr(estimand, "time_horizon", None)),
            "prediction_origin": _optional_estimand_text(
                getattr(estimand, "prediction_origin", None)
            ),
            "unit": str(getattr(estimand, "unit", "") or ""),
            "scale": str(getattr(estimand, "scale", "") or ""),
            "transform": _optional_estimand_text(getattr(estimand, "transform", None)),
            "target_role": str(getattr(estimand, "target_role", "") or ""),
            "loss_or_utility_id": _optional_estimand_text(
                getattr(estimand, "loss_or_utility_id", None)
            ),
        }
        return cls.model_validate(
            {**payload, "content_hash": _native_value_estimand_binding_hash(payload)}
        )

    def matches(self, estimand: object) -> bool:
        """Return whether all authority-bearing estimand fields match exactly."""

        expected = type(self).from_estimand(
            estimand=estimand,
            native_contract_id=self.native_contract_id,
            producer_method_fqn=self.producer_method_fqn,
            projection_input_content_hash=self.projection_input_content_hash,
        )
        return self == expected


def _native_value_estimand_binding_hash(payload: object) -> str:
    return content_hash(
        to_canonical_bytes(payload, CanonSpec(forbid_floats=True)),
        prefix=True,
    )


def _optional_estimand_text(value: object) -> str | None:
    if value is None:
        return None
    normalized = str(value)
    return normalized or None


def _optional_estimand_tuple(value: object) -> tuple[str, ...] | None:
    if value is None:
        return None
    return tuple(str(item) for item in value)  # type: ignore[union-attr]


def value_uncertainty_output_contract(
    contract_id: str,
    *,
    projection_kind: ValueUncertaintyProjectionKind,
) -> OutputContractDeclaration:
    """Declare that a native output owns estimand-aware value uncertainty projection."""

    return OutputContractDeclaration(
        contract_id=contract_id,
        capabilities=frozenset({OutputContractCapability.VALUE_UNCERTAINTY_PROJECTION}),
        value_uncertainty_projection_kind=projection_kind,
    )


def supports_value_uncertainty_projection_contract(owner: type[object]) -> bool:
    """Return whether an output owner exposes the complete projection interface."""

    projector = getattr(owner, "to_value_uncertainty", None)
    if not callable(projector):
        return False
    try:
        parameters = inspect.signature(projector).parameters
    except (TypeError, ValueError):
        return False
    return all(
        name in parameters and parameters[name].kind is inspect.Parameter.KEYWORD_ONLY
        for name in ("estimand", "projection_binding")
    )


class PullBackNotRepresentableError(ValueError):
    """Raised when a pull-back needs extra structure that the caller did not supply."""


class UncertaintySource(str, Enum):
    """Origin of the uncertainty interval carried in the IR."""

    CALIBRATION = "calibration"
    TRUST = "trust"
    CONFLICT_RESOLUTION = "conflict_resolution"
    CAUSAL = "causal"
    BOOTSTRAP = "bootstrap"
    ENSEMBLE = "ensemble"
    MANUAL = "manual"


class DistributionFamily(str, Enum):
    """Declare the assumed sampling/posterior family behind an interval estimate."""

    NORMAL = "normal"
    BOOTSTRAP = "bootstrap"
    BAYESIAN = "bayesian"
    UNIFORM = "uniform"
    TRIANGULAR = "triangular"
    UNKNOWN = "unknown"


class PropagationMethod(str, Enum):
    """Declare how uncertainty was propagated before the interval reached the IR."""

    DELTA_METHOD = "delta_method"
    MONTE_CARLO = "monte_carlo"
    ANALYTICAL = "analytical"
    NONE = "none"


class IntervalSemantics(str, Enum):
    """Tell governance/reporting whether an interval is statistical or heuristic."""

    CONFIDENCE_INTERVAL = "confidence_interval"
    CREDIBLE_INTERVAL = "credible_interval"
    DETERMINISTIC_BOUNDS = "deterministic_bounds"
    HEURISTIC_RANGE = "heuristic_range"


class NumericToleranceMode(str, Enum):
    """How float payloads are canonicalized before persistence and composition."""

    DECIMAL_EXACT = "decimal_exact"
    FLOAT_ROUND_12 = "float_round_12"
    HYBRID = "hybrid"


class EnvelopeCombinationMethod(str, Enum):
    """Supported combination semantics for compatible uncertainty envelopes."""

    INTERSECTION = "intersection"
    CONSERVATIVE_UNION = "conservative_union"
    PRECISION_WEIGHTED = "precision_weighted"


class ComposedFlavour(str, Enum):
    """Declare the native and composed family used to transport uncertainty."""

    ANALYTICAL = "analytical"
    MONTE_CARLO = "monte_carlo"
    DELTA = "delta"
    QUASI_MONTE_CARLO = "quasi_monte_carlo"
    MIXED = "mixed"


class ExactnessKind(str, Enum):
    """Disclose whether an envelope is exact, approximated, or only a constraint hull."""

    EXACT = "exact"
    OUTER_BOUND = "outer_bound"
    APPROXIMATION = "approximation"
    CONSTRAINT_ONLY = "constraint_only"


class CertificateKind(str, Enum):
    """Machine-readable approximation/error certificate attached to a composition chain."""

    EXACT = "exact"
    KOLMOGOROV = "kolmogorov"
    WASSERSTEIN_1 = "wasserstein_1"
    TAYLOR_REMAINDER = "taylor_remainder"
    QMC_VARIATION = "qmc_variation"
    RQMC_REPLICATES = "rqmc_replicates"


class RobustSetFamily(str, Enum):
    """Supported geometric families for robust optimization uncertainty sets."""

    BOX = "box"
    ELLIPSOID = "ellipsoid"
    BUDGET = "budget"
    WASSERSTEIN = "wasserstein"


class RobustSetCalibrationMethod(str, Enum):
    """How the size parameter of a robust uncertainty set was calibrated."""

    GAUSSIAN_PARAMETRIC = "gaussian_parametric"
    BOOTSTRAP = "bootstrap"
    CONFORMAL = "conformal"
    HYPOTHESIS_TEST = "hypothesis_test"


class RobustSetCalibrationStatus(str, Enum):
    """Outcome of the set-size selection workflow."""

    OK = "ok"
    INFEASIBLE_TARGET_PAIR = "infeasible_target_pair"
    INSUFFICIENT_DATA = "insufficient_data"


class RobustSetAdequacyStatus(str, Enum):
    """Governance-facing summary of whether a robust set is well calibrated."""

    CALIBRATED = "calibrated"
    UNDERCOVERAGE = "undercoverage"
    OVERCONSERVATIVE = "overconservative"
    INFEASIBLE_TARGET_PAIR = "infeasible_target_pair"
    INSUFFICIENT_DATA = "insufficient_data"
    UNKNOWN = "unknown"


class RobustSetFrontierPoint(BaseModel):
    """One empirical point on the coverage-vs-inflation frontier."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    rho: float = Field(ge=0.0)
    coverage_emp: float = Field(ge=0.0, le=1.0)
    coverage_lcb: float = Field(ge=0.0, le=1.0)
    inflation_mean: float
    inflation_ucb: float
    worst_case_premium: float | None = None
    cvar05: float | None = None

    @model_validator(mode="after")
    def _validate_frontier_point(self) -> RobustSetFrontierPoint:
        for label, value in (
            ("rho", self.rho),
            ("coverage_emp", self.coverage_emp),
            ("coverage_lcb", self.coverage_lcb),
            ("inflation_mean", self.inflation_mean),
            ("inflation_ucb", self.inflation_ucb),
        ):
            if not math.isfinite(value):
                raise ValueError(f"{label} must be finite")
        if self.coverage_lcb > self.coverage_emp + 1e-12:
            raise ValueError("coverage_lcb cannot exceed coverage_emp")
        if self.inflation_ucb < self.inflation_mean - 1e-12:
            raise ValueError("inflation_ucb cannot be below inflation_mean")
        if self.worst_case_premium is not None and not math.isfinite(self.worst_case_premium):
            raise ValueError("worst_case_premium must be finite when provided")
        if self.cvar05 is not None and not math.isfinite(self.cvar05):
            raise ValueError("cvar05 must be finite when provided")
        return self


class RobustSetSpec(BaseModel):
    """Typed robust-set specification shared across calibration and optimization layers."""

    contract_id: ClassVar[str] = "ir.robust_set_spec.v1"

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    family: RobustSetFamily
    size_parameter: float = Field(ge=0.0)
    center: tuple[float, ...]
    scale_diag: tuple[float, ...] | None = None
    covariance: tuple[tuple[float, ...], ...] | None = None
    coverage_target: float | None = Field(default=None, ge=0.0, le=1.0)
    calibration_method: RobustSetCalibrationMethod = RobustSetCalibrationMethod.CONFORMAL
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_spec(self) -> RobustSetSpec:
        if not self.center:
            raise ValueError("center must be non-empty")
        if any(not math.isfinite(value) for value in self.center):
            raise ValueError("center must contain only finite values")

        dimension = len(self.center)
        if self.scale_diag is not None:
            if len(self.scale_diag) != dimension:
                raise ValueError("scale_diag must match center dimension")
            if any((not math.isfinite(value)) or value <= 0.0 for value in self.scale_diag):
                raise ValueError("scale_diag must contain only positive finite values")

        if self.covariance is not None:
            if len(self.covariance) != dimension:
                raise ValueError("covariance must match center dimension")
            for row in self.covariance:
                if len(row) != dimension:
                    raise ValueError("covariance must be square")
                if any(not math.isfinite(value) for value in row):
                    raise ValueError("covariance must contain only finite values")
            cov = np.asarray(self.covariance, dtype=float)
            if not np.allclose(cov, cov.T, atol=1e-8):
                raise ValueError("covariance must be symmetric")
            if np.min(np.linalg.eigvalsh(cov)) < -1e-8:
                raise ValueError("covariance must be positive semidefinite")

        if self.family is RobustSetFamily.BOX and self.scale_diag is None:
            raise ValueError("box robust sets require scale_diag")
        if self.family is RobustSetFamily.ELLIPSOID and self.covariance is None:
            raise ValueError("ellipsoid robust sets require covariance")
        return self

    @property
    def dimension(self) -> int:
        return len(self.center)


class RobustSetCalibrationReport(BaseModel):
    """Calibration artifact linking coverage targets to decision-level conservatism."""

    contract_id: ClassVar[str] = "foundry.calibration.robust_set_report.v1"

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    family: RobustSetFamily
    selected_size: float | None = Field(default=None, ge=0.0)
    target_coverage: float = Field(ge=0.0, le=1.0)
    target_inflation: float | None = Field(default=None, ge=0.0)
    empirical_frontier: tuple[RobustSetFrontierPoint, ...] = ()
    status: RobustSetCalibrationStatus
    adequacy_status: RobustSetAdequacyStatus = RobustSetAdequacyStatus.UNKNOWN
    assumptions: tuple[str, ...] = ()
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_report(self) -> RobustSetCalibrationReport:
        if self.status is RobustSetCalibrationStatus.OK and self.selected_size is None:
            raise ValueError("successful calibration reports require selected_size")
        if self.status is not RobustSetCalibrationStatus.OK and self.selected_size is not None:
            raise ValueError("selected_size must be None unless status is ok")
        if (
            self.adequacy_status is RobustSetAdequacyStatus.CALIBRATED
            and self.status is not RobustSetCalibrationStatus.OK
        ):
            raise ValueError("adequacy_status=calibrated requires status=ok")
        return self


class NumericPolicySpec(BaseModel):
    """Explicit numeric policy for envelope canonicalization."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    policy_id: str = "bounded_float_v1"
    mode: NumericToleranceMode = NumericToleranceMode.FLOAT_ROUND_12
    decimal_places: int = Field(default=12, ge=0, le=15)
    absolute_tolerance: float = Field(default=1e-12, ge=0.0)

    def canonicalize(self, value: float | None) -> float | None:
        if value is None:
            return None
        if not math.isfinite(value):
            return value
        if self.mode is NumericToleranceMode.DECIMAL_EXACT:
            return value
        rounded = round(value, self.decimal_places)
        if self.mode is NumericToleranceMode.HYBRID and abs(rounded) <= self.absolute_tolerance:
            return 0.0
        return rounded


class PosteriorSamplesCarrier(BaseModel):
    """Carry posterior/bootstrap draws when an interval alone is not expressive enough."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    carrier_type: Literal["posterior_samples"] = "posterior_samples"
    samples: tuple[float, ...]
    sample_axis: str = "draw"
    weights: tuple[float, ...] | None = None

    @model_validator(mode="after")
    def _validate_payload(self) -> PosteriorSamplesCarrier:
        if not self.samples:
            raise ValueError("posterior_samples carrier requires at least one sample")
        if self.weights is not None and len(self.weights) != len(self.samples):
            raise ValueError("posterior sample weights must match sample count")
        for value in self.samples:
            if not math.isfinite(value):
                raise ValueError("posterior samples must be finite")
        if self.weights is not None:
            for weight in self.weights:
                if not math.isfinite(weight) or weight < 0.0:
                    raise ValueError("posterior sample weights must be finite and non-negative")
        return self


class QuantileSummaryCarrier(BaseModel):
    """Carry quantile summaries for calibrated posteriors."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    carrier_type: Literal["quantile_summary"] = "quantile_summary"
    quantiles: dict[str, float]

    @model_validator(mode="after")
    def _validate_payload(self) -> QuantileSummaryCarrier:
        if not self.quantiles:
            raise ValueError("quantile summary carrier requires at least one quantile")
        for key, value in self.quantiles.items():
            try:
                level = float(key)
            except ValueError as exc:
                raise ValueError(f"quantile key '{key}' must be parseable as float") from exc
            if not 0.0 <= level <= 1.0:
                raise ValueError("quantile levels must be within [0, 1]")
            if not math.isfinite(value):
                raise ValueError("quantile values must be finite")
        return self


class ParametricFitCarrier(BaseModel):
    """Carry the parameters of a parametric fit used to derive the interval."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    carrier_type: Literal["parametric_fit"] = "parametric_fit"
    family: DistributionFamily
    parameters: dict[str, float]
    support: tuple[float, float] | None = None

    @model_validator(mode="after")
    def _validate_payload(self) -> ParametricFitCarrier:
        if not self.parameters:
            raise ValueError("parametric fit carrier requires at least one parameter")
        for value in self.parameters.values():
            if not math.isfinite(value):
                raise ValueError("parametric fit parameters must be finite")
        if self.support is not None and self.support[0] > self.support[1]:
            raise ValueError("parametric fit support must be ordered")
        return self


class MixtureComponent(BaseModel):
    """One component of a mixture distribution carrier."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    weight: float = Field(gt=0.0)
    family: DistributionFamily
    parameters: dict[str, float]

    @model_validator(mode="after")
    def _validate_payload(self) -> MixtureComponent:
        if not math.isfinite(self.weight):
            raise ValueError("mixture weights must be finite")
        for value in self.parameters.values():
            if not math.isfinite(value):
                raise ValueError("mixture component parameters must be finite")
        return self


class MixtureDistributionCarrier(BaseModel):
    """Carry a finite mixture approximation of the posterior distribution."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    carrier_type: Literal["mixture_distribution"] = "mixture_distribution"
    components: tuple[MixtureComponent, ...]

    @model_validator(mode="after")
    def _validate_payload(self) -> MixtureDistributionCarrier:
        if not self.components:
            raise ValueError("mixture distribution carrier requires at least one component")
        total_weight = sum(component.weight for component in self.components)
        if not math.isfinite(total_weight) or total_weight <= 0.0:
            raise ValueError("mixture distribution total weight must be positive")
        return self


DistributionCarrier = Annotated[
    PosteriorSamplesCarrier
    | QuantileSummaryCarrier
    | ParametricFitCarrier
    | MixtureDistributionCarrier,
    Field(discriminator="carrier_type"),
]


class CompositionStep(BaseModel):
    """One explicit transformation applied during uncertainty composition."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    op: Literal["join", "push_forward", "pull_back", "compress", "resample"]
    stage_name: str = Field(min_length=1)
    input_flavours: tuple[ComposedFlavour, ...]
    output_flavour: ComposedFlavour
    map_name: str | None = None
    lipschitz_bound: float | None = None
    bias_bound: float | None = None
    variance_bound: float | None = None
    sample_size: int | None = Field(default=None, ge=1)
    replicate_count: int | None = Field(default=None, ge=1)
    qmc_method: str | None = None
    scrambled: bool | None = None
    assumptions: tuple[str, ...] = ()
    notes: dict[str, Any] = Field(default_factory=dict)


class CompositionProvenance(BaseModel):
    """Persist the history, exactness, and certificates behind a composed envelope."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    native_flavour: ComposedFlavour
    composed_flavour: ComposedFlavour
    exactness: ExactnessKind
    certificate_kind: CertificateKind
    certificate_radius: float | dict[str, float] | None = None
    confidence_level: float | None = Field(default=None, gt=0.0, lt=1.0)
    scope: tuple[str, ...] = ()
    origin_envelope_ids: tuple[str, ...] = ()
    operator_history: tuple[CompositionStep, ...] = ()


def _canonicalize_distribution_payload(
    payload: dict[str, Any] | BaseModel | None,
    policy: NumericPolicySpec,
) -> dict[str, Any] | None:
    if payload is None:
        return None
    if isinstance(payload, BaseModel):
        payload = payload.model_dump(mode="python", round_trip=True)
    carrier_type = payload.get("carrier_type")
    normalized = dict(payload)
    if carrier_type == "posterior_samples":
        normalized["samples"] = [
            policy.canonicalize(float(sample)) for sample in normalized.get("samples", ())
        ]
        if normalized.get("weights") is not None:
            normalized["weights"] = [
                policy.canonicalize(float(weight)) for weight in normalized["weights"]
            ]
    elif carrier_type == "quantile_summary":
        normalized["quantiles"] = {
            str(key): policy.canonicalize(float(value))
            for key, value in sorted(
                normalized.get("quantiles", {}).items(),
                key=lambda entry: float(entry[0]),
            )
        }
    elif carrier_type == "parametric_fit":
        normalized["parameters"] = {
            str(key): policy.canonicalize(float(value))
            for key, value in sorted(normalized.get("parameters", {}).items())
        }
        if normalized.get("support") is not None:
            lo, hi = normalized["support"]
            normalized["support"] = (
                policy.canonicalize(float(lo)),
                policy.canonicalize(float(hi)),
            )
    elif carrier_type == "mixture_distribution":
        components = []
        for component in normalized.get("components", ()):
            components.append(
                {
                    **component,
                    "weight": policy.canonicalize(float(component["weight"])),
                    "parameters": {
                        str(key): policy.canonicalize(float(value))
                        for key, value in sorted(component.get("parameters", {}).items())
                    },
                }
            )
        normalized["components"] = components
    return normalized


def _canonicalize_nested_numbers(value: Any, policy: NumericPolicySpec) -> Any:
    if isinstance(value, float):
        return policy.canonicalize(value)
    if isinstance(value, list):
        return [_canonicalize_nested_numbers(item, policy) for item in value]
    if isinstance(value, tuple):
        return tuple(_canonicalize_nested_numbers(item, policy) for item in value)
    if isinstance(value, dict):
        return {key: _canonicalize_nested_numbers(item, policy) for key, item in value.items()}
    if isinstance(value, BaseModel):
        return _canonicalize_nested_numbers(
            value.model_dump(mode="python", round_trip=True),
            policy,
        )
    return value


def _canonicalize_composition_provenance(
    payload: dict[str, Any] | BaseModel | None,
    policy: NumericPolicySpec,
) -> dict[str, Any] | None:
    if payload is None:
        return None
    return _canonicalize_nested_numbers(payload, policy)


def _origin_id_for_envelope(envelope: UncertaintyEnvelope, *, idx: int) -> str:
    for key in ("envelope_id", "artifact_id", "ref_id"):
        raw = envelope.metadata.get(key)
        if isinstance(raw, str) and raw:
            return raw
    return (
        f"inline:{idx}:{envelope.source.value}:"
        f"{envelope.point_estimate}:{envelope.ci_lower}:{envelope.ci_upper}"
    )


def _scope_for_envelope(envelope: UncertaintyEnvelope) -> tuple[str, ...]:
    scope: list[str] = []
    if envelope.interval_semantics in {
        IntervalSemantics.CONFIDENCE_INTERVAL,
        IntervalSemantics.CREDIBLE_INTERVAL,
    }:
        scope.extend(["interval", "quantile"])
    if envelope.interval_semantics in {
        IntervalSemantics.DETERMINISTIC_BOUNDS,
        IntervalSemantics.HEURISTIC_RANGE,
    }:
        scope.append("bounds")
    if envelope.distribution_payload is not None:
        scope.append("cdf")
    if "expectation" not in scope:
        scope.append("expectation")
    return tuple(dict.fromkeys(scope))


def _infer_native_flavour(envelope: UncertaintyEnvelope) -> ComposedFlavour:
    if envelope.composition_provenance is not None:
        return envelope.composition_provenance.composed_flavour

    sampling_method = str(envelope.metadata.get("mc_sampling_method", "")).lower()
    if sampling_method in {"sobol", "halton"}:
        return ComposedFlavour.QUASI_MONTE_CARLO
    if envelope.propagation_method is PropagationMethod.MONTE_CARLO:
        return ComposedFlavour.MONTE_CARLO
    if envelope.propagation_method is PropagationMethod.DELTA_METHOD:
        return ComposedFlavour.DELTA
    if isinstance(envelope.distribution_payload, PosteriorSamplesCarrier):
        return ComposedFlavour.MONTE_CARLO
    return ComposedFlavour.ANALYTICAL


def _infer_exactness(envelope: UncertaintyEnvelope) -> ExactnessKind:
    if envelope.composition_provenance is not None:
        return envelope.composition_provenance.exactness
    if envelope.is_heuristic_ci:
        return ExactnessKind.APPROXIMATION
    if envelope.interval_semantics is IntervalSemantics.DETERMINISTIC_BOUNDS:
        return ExactnessKind.OUTER_BOUND
    if envelope.propagation_method in {
        PropagationMethod.DELTA_METHOD,
        PropagationMethod.MONTE_CARLO,
    }:
        return ExactnessKind.APPROXIMATION
    if envelope.propagation_method is PropagationMethod.ANALYTICAL:
        return ExactnessKind.EXACT
    return ExactnessKind.APPROXIMATION


def _infer_certificate_kind(envelope: UncertaintyEnvelope) -> CertificateKind:
    if envelope.composition_provenance is not None:
        return envelope.composition_provenance.certificate_kind
    sampling_method = str(envelope.metadata.get("mc_sampling_method", "")).lower()
    if sampling_method in {"sobol", "halton"}:
        return CertificateKind.QMC_VARIATION
    if envelope.propagation_method is PropagationMethod.MONTE_CARLO:
        return CertificateKind.KOLMOGOROV
    if envelope.propagation_method is PropagationMethod.DELTA_METHOD:
        return CertificateKind.TAYLOR_REMAINDER
    return CertificateKind.EXACT


def _dkw_radius(sample_size: int, confidence_level: float) -> float:
    alpha = min(max(1.0 - confidence_level, 1e-12), 1.0 - 1e-12)
    return math.sqrt(math.log(2.0 / alpha) / (2.0 * sample_size))


def _infer_certificate_radius(
    envelope: UncertaintyEnvelope,
) -> float | dict[str, float] | None:
    if envelope.composition_provenance is not None:
        return envelope.composition_provenance.certificate_radius
    sampling_method = str(envelope.metadata.get("mc_sampling_method", "")).lower()
    if sampling_method in {"sobol", "halton"} and envelope.sample_size is not None:
        return {
            "sample_size": float(envelope.sample_size),
            "replicate_count": float(envelope.metadata.get("qmc_replicates", 1)),
        }
    if (
        envelope.propagation_method is PropagationMethod.MONTE_CARLO
        and envelope.sample_size is not None
        and envelope.confidence_level is not None
    ):
        return _dkw_radius(envelope.sample_size, envelope.confidence_level)
    if envelope.propagation_method is PropagationMethod.DELTA_METHOD:
        remainder = envelope.metadata.get("taylor_remainder")
        if isinstance(remainder, (int, float)) and math.isfinite(float(remainder)):
            return float(remainder)
        std = envelope.metadata.get("output_std")
        if isinstance(std, (int, float)) and math.isfinite(float(std)):
            return float(std)
    if envelope.interval_semantics is IntervalSemantics.DETERMINISTIC_BOUNDS:
        return 0.0
    return None


def _base_provenance(
    envelope: UncertaintyEnvelope,
    *,
    idx: int = 0,
) -> CompositionProvenance:
    if envelope.composition_provenance is not None:
        return envelope.composition_provenance
    flavour = _infer_native_flavour(envelope)
    return CompositionProvenance(
        native_flavour=flavour,
        composed_flavour=flavour,
        exactness=_infer_exactness(envelope),
        certificate_kind=_infer_certificate_kind(envelope),
        certificate_radius=_infer_certificate_radius(envelope),
        confidence_level=envelope.confidence_level,
        scope=_scope_for_envelope(envelope),
        origin_envelope_ids=(_origin_id_for_envelope(envelope, idx=idx),),
        operator_history=(),
    )


def _merge_certificate_radii(
    envelopes: Iterable[UncertaintyEnvelope],
) -> float | dict[str, float] | None:
    radii = [_base_provenance(envelope).certificate_radius for envelope in envelopes]
    filtered = [radius for radius in radii if radius is not None]
    if not filtered:
        return None
    if all(isinstance(radius, (int, float)) for radius in filtered):
        return max(float(radius) for radius in filtered)
    merged: dict[str, float] = {}
    for radius in filtered:
        if isinstance(radius, (int, float)):
            merged["radius"] = max(merged.get("radius", 0.0), float(radius))
        else:
            for key, value in radius.items():
                merged[key] = max(merged.get(key, 0.0), float(value))
    return merged


def _worst_exactness(
    envelopes: Iterable[UncertaintyEnvelope],
) -> ExactnessKind:
    order = {
        ExactnessKind.EXACT: 0,
        ExactnessKind.OUTER_BOUND: 1,
        ExactnessKind.APPROXIMATION: 2,
        ExactnessKind.CONSTRAINT_ONLY: 3,
    }
    exactnesses = [_base_provenance(envelope).exactness for envelope in envelopes]
    return max(exactnesses, key=lambda item: order[item])


def _merge_certificate_kind(
    envelopes: Iterable[UncertaintyEnvelope],
    *,
    fallback: CertificateKind = CertificateKind.WASSERSTEIN_1,
) -> CertificateKind:
    kinds = {_base_provenance(envelope).certificate_kind for envelope in envelopes}
    if len(kinds) == 1:
        return next(iter(kinds))
    return fallback


def _propagate_certificate_radius(
    radius: float | dict[str, float] | None,
    *,
    lipschitz_bound: float | None = None,
    bias_bound: float | None = None,
) -> float | dict[str, float] | None:
    if radius is None:
        if bias_bound is None:
            return None
        return float(bias_bound)
    if isinstance(radius, (int, float)):
        scale = abs(float(lipschitz_bound)) if lipschitz_bound is not None else 1.0
        return scale * float(radius) + float(bias_bound or 0.0)
    propagated = {key: float(value) for key, value in radius.items()}
    if lipschitz_bound is not None:
        propagated["lipschitz_bound"] = abs(float(lipschitz_bound))
    if bias_bound is not None:
        propagated["bias_bound"] = float(bias_bound)
    return propagated


def _compose_flavour_for_operation(
    *,
    op: Literal["join", "push_forward", "pull_back", "compress", "resample"],
    input_flavours: tuple[ComposedFlavour, ...],
    output_flavour: ComposedFlavour,
) -> ComposedFlavour:
    unique = set(input_flavours)
    if not unique:
        return output_flavour
    if ComposedFlavour.MIXED in unique or len(unique) > 1:
        return ComposedFlavour.MIXED
    inherited = next(iter(unique))
    if op == "join":
        return inherited
    if output_flavour is ComposedFlavour.ANALYTICAL:
        return inherited
    return output_flavour


def _build_composition_provenance(
    *,
    input_envelopes: Iterable[UncertaintyEnvelope],
    op: Literal["join", "push_forward", "pull_back", "compress", "resample"],
    stage_name: str,
    output_flavour: ComposedFlavour,
    exactness: ExactnessKind,
    certificate_kind: CertificateKind,
    certificate_radius: float | dict[str, float] | None,
    confidence_level: float | None,
    scope: tuple[str, ...],
    map_name: str | None = None,
    lipschitz_bound: float | None = None,
    bias_bound: float | None = None,
    variance_bound: float | None = None,
    sample_size: int | None = None,
    replicate_count: int | None = None,
    qmc_method: str | None = None,
    scrambled: bool | None = None,
    assumptions: tuple[str, ...] = (),
    notes: dict[str, Any] | None = None,
) -> CompositionProvenance:
    normalized = tuple(input_envelopes)
    base = tuple(_base_provenance(envelope, idx=idx) for idx, envelope in enumerate(normalized))
    input_flavours = tuple(provenance.composed_flavour for provenance in base)
    native_flavours = {provenance.native_flavour for provenance in base}
    native_flavour = (
        next(iter(native_flavours)) if len(native_flavours) == 1 else ComposedFlavour.MIXED
    )
    operator_history: list[CompositionStep] = []
    origin_ids: list[str] = []
    for provenance in base:
        operator_history.extend(provenance.operator_history)
        for origin_id in provenance.origin_envelope_ids:
            if origin_id not in origin_ids:
                origin_ids.append(origin_id)
    operator_history.append(
        CompositionStep(
            op=op,
            stage_name=stage_name,
            input_flavours=input_flavours,
            output_flavour=_compose_flavour_for_operation(
                op=op,
                input_flavours=input_flavours,
                output_flavour=output_flavour,
            ),
            map_name=map_name,
            lipschitz_bound=lipschitz_bound,
            bias_bound=bias_bound,
            variance_bound=variance_bound,
            sample_size=sample_size,
            replicate_count=replicate_count,
            qmc_method=qmc_method,
            scrambled=scrambled,
            assumptions=assumptions,
            notes=dict(notes or {}),
        )
    )
    return CompositionProvenance(
        native_flavour=native_flavour,
        composed_flavour=operator_history[-1].output_flavour,
        exactness=exactness,
        certificate_kind=certificate_kind,
        certificate_radius=certificate_radius,
        confidence_level=confidence_level,
        scope=tuple(dict.fromkeys(scope)),
        origin_envelope_ids=tuple(origin_ids),
        operator_history=tuple(operator_history),
    )


def build_composition_provenance(
    *,
    input_envelopes: Iterable[UncertaintyEnvelope],
    op: Literal["join", "push_forward", "pull_back", "compress", "resample"],
    stage_name: str,
    output_flavour: ComposedFlavour,
    exactness: ExactnessKind,
    certificate_kind: CertificateKind,
    certificate_radius: float | dict[str, float] | None,
    confidence_level: float | None,
    scope: tuple[str, ...],
    map_name: str | None = None,
    lipschitz_bound: float | None = None,
    bias_bound: float | None = None,
    variance_bound: float | None = None,
    sample_size: int | None = None,
    replicate_count: int | None = None,
    qmc_method: str | None = None,
    scrambled: bool | None = None,
    assumptions: tuple[str, ...] = (),
    notes: dict[str, Any] | None = None,
) -> CompositionProvenance:
    """Public helper for modules that need to attach a composition step."""

    return _build_composition_provenance(
        input_envelopes=input_envelopes,
        op=op,
        stage_name=stage_name,
        output_flavour=output_flavour,
        exactness=exactness,
        certificate_kind=certificate_kind,
        certificate_radius=certificate_radius,
        confidence_level=confidence_level,
        scope=scope,
        map_name=map_name,
        lipschitz_bound=lipschitz_bound,
        bias_bound=bias_bound,
        variance_bound=variance_bound,
        sample_size=sample_size,
        replicate_count=replicate_count,
        qmc_method=qmc_method,
        scrambled=scrambled,
        assumptions=assumptions,
        notes=notes,
    )


def _std_from_envelope(envelope: UncertaintyEnvelope) -> float:
    if isinstance(envelope.distribution_payload, ParametricFitCarrier):
        for key in ("std", "sigma", "scale"):
            raw = envelope.distribution_payload.parameters.get(key)
            if raw is not None and math.isfinite(float(raw)):
                return max(float(raw), envelope.numeric_policy.absolute_tolerance)
    if envelope.confidence_level is not None:
        z = NormalDist().inv_cdf((1.0 + envelope.confidence_level) / 2.0)
        if z > 0.0:
            return max(
                envelope.ci_width / (2.0 * z),
                envelope.numeric_policy.absolute_tolerance,
            )
    return max(envelope.ci_width / 4.0, envelope.numeric_policy.absolute_tolerance)


def _weighted_mean(values: np.ndarray, weights: np.ndarray | None) -> float:
    if weights is None:
        return float(np.mean(values))
    total = float(np.sum(weights))
    if total <= 0.0:
        return float(np.mean(values))
    return float(np.sum(values * weights) / total)


def _weighted_quantile(
    values: np.ndarray,
    quantile: float,
    weights: np.ndarray | None = None,
) -> float:
    q = min(max(float(quantile), 0.0), 1.0)
    if weights is None:
        return float(np.quantile(values, q))
    order = np.argsort(values)
    sorted_values = values[order]
    sorted_weights = weights[order]
    total = float(np.sum(sorted_weights))
    if total <= 0.0:
        return float(np.quantile(sorted_values, q))
    cumulative = np.cumsum(sorted_weights)
    target = q * total
    return float(np.interp(target, cumulative, sorted_values))


def _normal_quantile_grid(mean: float, std: float, size: int) -> np.ndarray:
    normal = NormalDist(mu=mean, sigma=max(std, 1e-12))
    grid = np.linspace(0.5 / size, 1.0 - 0.5 / size, size)
    return np.asarray([normal.inv_cdf(float(level)) for level in grid], dtype=float)


def _triangular_quantile_grid(lo: float, mode: float, hi: float, size: int) -> np.ndarray:
    if hi <= lo:
        return np.full((size,), mode, dtype=float)
    c = (mode - lo) / (hi - lo)
    grid = np.linspace(0.5 / size, 1.0 - 0.5 / size, size)
    out = np.empty((size,), dtype=float)
    for idx, u in enumerate(grid):
        if u < c:
            out[idx] = lo + math.sqrt(u * (hi - lo) * (mode - lo))
        else:
            out[idx] = hi - math.sqrt((1.0 - u) * (hi - lo) * (hi - mode))
    return out


def _particles_from_parametric_fit(payload: ParametricFitCarrier, size: int) -> np.ndarray:
    family = payload.family
    if family is DistributionFamily.NORMAL:
        mean = float(payload.parameters.get("mean", payload.parameters.get("mu", 0.0)))
        std = float(payload.parameters.get("std", payload.parameters.get("sigma", 1.0)))
        return _normal_quantile_grid(mean, std, size)
    if family is DistributionFamily.UNIFORM:
        if payload.support is not None:
            lo, hi = payload.support
        else:
            lo = float(payload.parameters.get("low", 0.0))
            hi = float(payload.parameters.get("high", 1.0))
        return np.linspace(float(lo), float(hi), size)
    if family is DistributionFamily.TRIANGULAR:
        if payload.support is not None:
            lo, hi = payload.support
        else:
            lo = float(payload.parameters.get("low", 0.0))
            hi = float(payload.parameters.get("high", 1.0))
        mode = float(
            payload.parameters.get("mode", payload.parameters.get("mean", (lo + hi) / 2.0))
        )
        return _triangular_quantile_grid(float(lo), float(mode), float(hi), size)
    lo, hi = payload.support if payload.support is not None else (0.0, 1.0)
    return np.linspace(float(lo), float(hi), size)


def _particles_from_distribution_payload(
    envelope: UncertaintyEnvelope,
    *,
    size: int,
) -> tuple[np.ndarray, np.ndarray | None]:
    payload = envelope.distribution_payload
    if isinstance(payload, PosteriorSamplesCarrier):
        samples = np.asarray(payload.samples, dtype=float)
        weights = None if payload.weights is None else np.asarray(payload.weights, dtype=float)
        return samples, weights
    if isinstance(payload, ParametricFitCarrier):
        return _particles_from_parametric_fit(payload, size), None
    if isinstance(payload, MixtureDistributionCarrier):
        component_sizes = _split_component_sizes(size, len(payload.components))
        parts: list[np.ndarray] = []
        weights: list[np.ndarray] = []
        for component, component_size in zip(payload.components, component_sizes, strict=True):
            component_payload = ParametricFitCarrier(
                family=component.family,
                parameters=component.parameters,
            )
            component_samples = _particles_from_parametric_fit(component_payload, component_size)
            parts.append(component_samples)
            weights.append(np.full((component_size,), float(component.weight), dtype=float))
        return np.concatenate(parts), np.concatenate(weights)
    if payload is None and envelope.distribution_family is DistributionFamily.NORMAL:
        return _normal_quantile_grid(
            float(envelope.point_estimate), _std_from_envelope(envelope), size
        ), None
    raise ValueError("compress_envelope(target='particles') requires a representable law payload")


def _split_component_sizes(total: int, parts: int) -> list[int]:
    total = max(int(total), 1)
    parts = max(int(parts), 1)
    base = total // parts
    remainder = total % parts
    return [base + (1 if idx < remainder else 0) for idx in range(parts)]


def _samples_from_payload(
    payload: DistributionCarrier | None,
) -> tuple[np.ndarray, np.ndarray | None] | None:
    if isinstance(payload, PosteriorSamplesCarrier):
        samples = np.asarray(payload.samples, dtype=float)
        weights = None if payload.weights is None else np.asarray(payload.weights, dtype=float)
        return samples, weights
    return None


def _join_distribution_payloads(
    envelopes: tuple[UncertaintyEnvelope, ...],
) -> DistributionCarrier | None:
    payloads = [envelope.distribution_payload for envelope in envelopes]
    if any(payload is None for payload in payloads):
        return None
    if all(isinstance(payload, PosteriorSamplesCarrier) for payload in payloads):
        samples: list[float] = []
        weights: list[float] = []
        saw_weights = False
        for payload in payloads:
            if not isinstance(payload, PosteriorSamplesCarrier):
                raise TypeError(
                    "posterior payload grouping must contain PosteriorSamplesCarrier only"
                )
            samples.extend(float(sample) for sample in payload.samples)
            if payload.weights is None:
                weights.extend(1.0 for _ in payload.samples)
            else:
                saw_weights = True
                weights.extend(float(weight) for weight in payload.weights)
        return PosteriorSamplesCarrier(
            samples=tuple(samples),
            weights=tuple(weights) if saw_weights else None,
        )
    if all(isinstance(payload, MixtureDistributionCarrier) for payload in payloads):
        components: list[MixtureComponent] = []
        for payload in payloads:
            if not isinstance(payload, MixtureDistributionCarrier):
                raise TypeError(
                    "mixture payload grouping must contain MixtureDistributionCarrier only"
                )
            components.extend(payload.components)
        return MixtureDistributionCarrier(components=tuple(components))
    if all(isinstance(payload, ParametricFitCarrier) for payload in payloads):
        n_payloads = float(len(payloads))
        return MixtureDistributionCarrier(
            components=tuple(
                MixtureComponent(
                    weight=1.0 / n_payloads,
                    family=payload.family,
                    parameters=payload.parameters,
                )
                for payload in payloads
                if isinstance(payload, ParametricFitCarrier)
            )
        )
    return None


def _resolve_join_semantics(
    envelopes: tuple[UncertaintyEnvelope, ...],
) -> tuple[IntervalSemantics, float | None, bool]:
    semantics = {envelope.interval_semantics for envelope in envelopes}
    levels = {envelope.confidence_level for envelope in envelopes}
    if len(semantics) == 1 and len(levels) == 1:
        representative = envelopes[0]
        return (
            representative.interval_semantics,
            representative.confidence_level,
            all(envelope.gate_eligible for envelope in envelopes),
        )
    if any(envelope.is_heuristic_ci for envelope in envelopes):
        return IntervalSemantics.HEURISTIC_RANGE, None, False
    return (
        IntervalSemantics.DETERMINISTIC_BOUNDS,
        None,
        all(envelope.gate_eligible for envelope in envelopes),
    )


def _scope_from_shape(
    *,
    interval_semantics: IntervalSemantics,
    distribution_payload: DistributionCarrier | None,
) -> tuple[str, ...]:
    scope: list[str] = ["expectation"]
    if interval_semantics in {
        IntervalSemantics.CONFIDENCE_INTERVAL,
        IntervalSemantics.CREDIBLE_INTERVAL,
    }:
        scope.extend(["interval", "quantile"])
    if interval_semantics in {
        IntervalSemantics.DETERMINISTIC_BOUNDS,
        IntervalSemantics.HEURISTIC_RANGE,
    }:
        scope.append("bounds")
    if distribution_payload is not None:
        scope.append("cdf")
    return tuple(dict.fromkeys(scope))


class UncertaintyEnvelope(BaseModel):
    """Unified uncertainty contract shared across PolicyOS IR artifacts."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        json_schema_extra={
            "title": "UncertaintyEnvelope",
            "description": "Unified uncertainty contract for Policy OS IR layer.",
        },
    )

    schema_version: str = Field("1.1", pattern=r"^\d+\.\d+$")
    numeric_policy: NumericPolicySpec = Field(default_factory=NumericPolicySpec)

    point_estimate: float
    confidence_interval: tuple[float, float]
    confidence_level: float | None = Field(default=0.95, gt=0.0, lt=1.0)

    distribution_family: DistributionFamily = DistributionFamily.UNKNOWN
    source: UncertaintySource
    propagation_method: PropagationMethod = PropagationMethod.NONE
    interval_semantics: IntervalSemantics = IntervalSemantics.CONFIDENCE_INTERVAL
    distribution_payload: DistributionCarrier | None = None
    composition_provenance: CompositionProvenance | None = None

    sample_size: int | None = Field(default=None, ge=1)

    is_heuristic_ci: bool = False
    gate_eligible: bool = True

    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _canonicalize_numeric_payload(cls, value: Any) -> Any:
        if isinstance(value, UncertaintyEnvelope):
            return value
        if not isinstance(value, dict):
            return value
        payload = dict(value)
        policy = NumericPolicySpec.model_validate(payload.get("numeric_policy", {}))
        payload["numeric_policy"] = policy.model_dump(mode="python")
        if "point_estimate" in payload:
            payload["point_estimate"] = policy.canonicalize(float(payload["point_estimate"]))
        if "confidence_interval" in payload:
            lo, hi = payload["confidence_interval"]
            payload["confidence_interval"] = (
                policy.canonicalize(float(lo)),
                policy.canonicalize(float(hi)),
            )
        if payload.get("confidence_level") is not None:
            payload["confidence_level"] = policy.canonicalize(float(payload["confidence_level"]))
        payload["distribution_payload"] = _canonicalize_distribution_payload(
            payload.get("distribution_payload"),
            policy,
        )
        payload["composition_provenance"] = _canonicalize_composition_provenance(
            payload.get("composition_provenance"),
            policy,
        )
        return payload

    @model_validator(mode="after")
    def _validate_fields(self) -> UncertaintyEnvelope:
        lo, hi = self.confidence_interval

        for value, label in (
            (self.point_estimate, "point_estimate"),
            (lo, "confidence_interval[0]"),
            (hi, "confidence_interval[1]"),
        ):
            if not math.isfinite(value):
                raise ValueError(f"{label} must be finite")

        if self.confidence_level is not None and not math.isfinite(self.confidence_level):
            raise ValueError("confidence_level must be finite")

        if lo > hi:
            raise ValueError(f"confidence_interval lower ({lo}) > upper ({hi})")

        if not (lo <= self.point_estimate <= hi):
            raise ValueError(
                f"point_estimate ({self.point_estimate}) must lie within "
                f"confidence_interval [{lo}, {hi}]"
            )

        statistical = {
            IntervalSemantics.CONFIDENCE_INTERVAL,
            IntervalSemantics.CREDIBLE_INTERVAL,
        }
        if self.interval_semantics in statistical and self.confidence_level is None:
            raise ValueError("confidence_level is required for statistical intervals")

        non_statistical = {
            IntervalSemantics.DETERMINISTIC_BOUNDS,
            IntervalSemantics.HEURISTIC_RANGE,
        }
        if self.interval_semantics in non_statistical and self.confidence_level is not None:
            raise ValueError("confidence_level must be None for non-statistical interval semantics")

        if (
            self.interval_semantics == IntervalSemantics.HEURISTIC_RANGE
            and not self.is_heuristic_ci
        ):
            raise ValueError("interval_semantics=heuristic_range requires is_heuristic_ci=True")

        if self.is_heuristic_ci and self.gate_eligible:
            raise ValueError("heuristic intervals must set gate_eligible=False")

        return self

    @property
    def ci_lower(self) -> float:
        return self.confidence_interval[0]

    @property
    def ci_upper(self) -> float:
        return self.confidence_interval[1]

    @property
    def ci_width(self) -> float:
        return self.ci_upper - self.ci_lower

    @property
    def relative_uncertainty(self) -> float | None:
        if abs(self.point_estimate) < max(self.numeric_policy.absolute_tolerance, 1e-15):
            return None
        return self.ci_width / abs(self.point_estimate)


def _require_compatible_envelopes(envelopes: tuple[UncertaintyEnvelope, ...]) -> None:
    semantics = {envelope.interval_semantics for envelope in envelopes}
    if len(semantics) != 1:
        raise UncertaintyCompatibilityError(
            "cannot combine envelopes with different interval semantics"
        )
    confidence_levels = {
        envelope.confidence_level
        for envelope in envelopes
        if envelope.interval_semantics
        in {IntervalSemantics.CONFIDENCE_INTERVAL, IntervalSemantics.CREDIBLE_INTERVAL}
    }
    if len(confidence_levels) > 1:
        raise UncertaintyCompatibilityError(
            "cannot combine envelopes with different confidence levels"
        )


def join_envelopes(
    envelopes: Iterable[UncertaintyEnvelope],
    *,
    representation: str = "best_available_outer_hull",
    source: UncertaintySource = UncertaintySource.ENSEMBLE,
) -> UncertaintyEnvelope:
    """Build the smallest representable outer hull over several envelopes."""

    normalized = tuple(envelopes)
    if not normalized:
        raise ValueError("join_envelopes requires at least one envelope")
    if len(normalized) == 1:
        return normalized[0]

    lows = [envelope.ci_lower for envelope in normalized]
    highs = [envelope.ci_upper for envelope in normalized]
    lower = min(lows)
    upper = max(highs)
    point_estimate = sum(envelope.point_estimate for envelope in normalized) / len(normalized)
    point_estimate = min(max(point_estimate, lower), upper)

    representative = normalized[0]
    interval_semantics, confidence_level, gate_eligible = _resolve_join_semantics(normalized)
    distribution_payload = _join_distribution_payloads(normalized)
    distribution_family = (
        representative.distribution_family
        if len({envelope.distribution_family for envelope in normalized}) == 1
        else DistributionFamily.UNKNOWN
    )
    exactness = (
        ExactnessKind.EXACT
        if (
            distribution_payload is not None
            and all(
                _base_provenance(envelope).exactness is ExactnessKind.EXACT
                for envelope in normalized
            )
        )
        else ExactnessKind.OUTER_BOUND
    )
    base_certificate_kinds = {
        _base_provenance(envelope).certificate_kind for envelope in normalized
    }
    certificate_kind = (
        next(iter(base_certificate_kinds))
        if len(base_certificate_kinds) == 1
        else CertificateKind.WASSERSTEIN_1
    )
    if exactness is ExactnessKind.EXACT:
        certificate_kind = CertificateKind.EXACT

    output_flavour = (
        _base_provenance(representative).composed_flavour
        if len({_base_provenance(envelope).composed_flavour for envelope in normalized}) == 1
        else ComposedFlavour.MIXED
    )
    scope = _scope_from_shape(
        interval_semantics=interval_semantics,
        distribution_payload=distribution_payload,
    )
    provenance = _build_composition_provenance(
        input_envelopes=normalized,
        op="join",
        stage_name="join_envelopes",
        output_flavour=output_flavour,
        exactness=exactness,
        certificate_kind=certificate_kind,
        certificate_radius=_merge_certificate_radii(normalized),
        confidence_level=confidence_level,
        scope=scope,
        assumptions=("outer_hull",),
        notes={"representation": representation},
    )

    return UncertaintyEnvelope(
        numeric_policy=representative.numeric_policy,
        point_estimate=float(point_estimate),
        confidence_interval=(float(lower), float(upper)),
        confidence_level=confidence_level,
        distribution_family=distribution_family,
        source=source,
        propagation_method=representative.propagation_method,
        interval_semantics=interval_semantics,
        distribution_payload=distribution_payload,
        composition_provenance=provenance,
        sample_size=sum(
            envelope.sample_size for envelope in normalized if envelope.sample_size is not None
        )
        or None,
        is_heuristic_ci=interval_semantics is IntervalSemantics.HEURISTIC_RANGE,
        gate_eligible=gate_eligible and interval_semantics is not IntervalSemantics.HEURISTIC_RANGE,
        metadata={
            "join_representation": representation,
            "joined_from": len(normalized),
        },
    )


def compress_envelope(
    envelope: UncertaintyEnvelope,
    *,
    target: Literal["interval", "moments", "particles"] = "interval",
) -> UncertaintyEnvelope:
    """Explicitly compress a law-carrying envelope into a smaller representation."""

    base = _base_provenance(envelope)
    distribution_payload = envelope.distribution_payload
    distribution_family = envelope.distribution_family
    confidence_level = envelope.confidence_level
    exactness = base.exactness
    certificate_kind = base.certificate_kind
    certificate_radius = base.certificate_radius

    if target == "interval":
        if distribution_payload is not None:
            exactness = ExactnessKind.OUTER_BOUND
        distribution_payload = None
    elif target == "moments":
        std = _std_from_envelope(envelope)
        distribution_family = DistributionFamily.NORMAL
        distribution_payload = ParametricFitCarrier(
            family=DistributionFamily.NORMAL,
            parameters={"mean": float(envelope.point_estimate), "std": float(std)},
        )
        exactness = ExactnessKind.APPROXIMATION
        certificate_kind = (
            CertificateKind.TAYLOR_REMAINDER
            if base.composed_flavour is ComposedFlavour.DELTA
            else certificate_kind
        )
    elif target == "particles":
        particle_count = envelope.sample_size or 256
        particle_values, particle_weights = _particles_from_distribution_payload(
            envelope,
            size=particle_count,
        )
        distribution_payload = PosteriorSamplesCarrier(
            samples=tuple(float(value) for value in particle_values),
            weights=(
                None
                if particle_weights is None
                else tuple(float(weight) for weight in particle_weights)
            ),
        )
        distribution_family = DistributionFamily.BOOTSTRAP
        exactness = (
            base.exactness
            if isinstance(envelope.distribution_payload, PosteriorSamplesCarrier)
            else ExactnessKind.APPROXIMATION
        )
        if not isinstance(envelope.distribution_payload, PosteriorSamplesCarrier):
            certificate_kind = (
                CertificateKind.RQMC_REPLICATES
                if base.certificate_kind is CertificateKind.RQMC_REPLICATES
                else CertificateKind.KOLMOGOROV
            )
    else:
        raise ValueError(f"Unknown compression target: {target}")

    scope = _scope_from_shape(
        interval_semantics=envelope.interval_semantics,
        distribution_payload=distribution_payload,
    )
    provenance = _build_composition_provenance(
        input_envelopes=(envelope,),
        op="compress",
        stage_name="compress_envelope",
        output_flavour=base.composed_flavour,
        exactness=exactness,
        certificate_kind=certificate_kind,
        certificate_radius=certificate_radius,
        confidence_level=confidence_level,
        scope=scope,
        notes={"target": target},
    )
    return envelope.model_copy(
        update={
            "distribution_family": distribution_family,
            "distribution_payload": distribution_payload,
            "composition_provenance": provenance,
            "sample_size": (
                len(distribution_payload.samples)
                if isinstance(distribution_payload, PosteriorSamplesCarrier)
                else envelope.sample_size
            ),
            "metadata": {
                **envelope.metadata,
                "compression_target": target,
            },
        }
    )


def push_forward_envelope(
    func: Callable[[float], float],
    envelope: UncertaintyEnvelope,
    *,
    map_name: str | None = None,
    cert_policy: str = "auto",
    lipschitz_bound: float | None = None,
    bias_bound: float | None = None,
    grid_size: int = 129,
) -> UncertaintyEnvelope:
    """Propagate one scalar envelope through a downstream map."""

    base = _base_provenance(envelope)
    map_label = map_name or getattr(func, "__name__", "anonymous_map")

    extracted = _samples_from_payload(envelope.distribution_payload)
    if extracted is not None:
        samples, weights = extracted
        pushed = np.asarray([float(func(float(sample))) for sample in samples], dtype=float)
        point_estimate = _weighted_mean(pushed, weights)
        if (
            envelope.interval_semantics
            in {
                IntervalSemantics.CONFIDENCE_INTERVAL,
                IntervalSemantics.CREDIBLE_INTERVAL,
            }
            and envelope.confidence_level is not None
        ):
            alpha = 1.0 - envelope.confidence_level
            lower = _weighted_quantile(pushed, alpha / 2.0, weights)
            upper = _weighted_quantile(pushed, 1.0 - alpha / 2.0, weights)
            interval_semantics = envelope.interval_semantics
            confidence_level = envelope.confidence_level
            gate_eligible = envelope.gate_eligible
        else:
            lower = float(np.min(pushed))
            upper = float(np.max(pushed))
            interval_semantics = IntervalSemantics.DETERMINISTIC_BOUNDS
            confidence_level = None
            gate_eligible = envelope.gate_eligible and not envelope.is_heuristic_ci
        output_payload = PosteriorSamplesCarrier(
            samples=tuple(float(value) for value in pushed),
            weights=(None if weights is None else tuple(float(weight) for weight in weights)),
        )
        output_flavour = base.composed_flavour
        exactness = base.exactness
        certificate_kind = base.certificate_kind
        certificate_radius = base.certificate_radius
        distribution_family = envelope.distribution_family
        sample_size = len(pushed)
        assumptions = ("law_preserving_particles",)
    elif cert_policy in {"auto", "delta"} and (
        envelope.distribution_family is DistributionFamily.NORMAL
        or isinstance(envelope.distribution_payload, ParametricFitCarrier)
    ):
        point = float(envelope.point_estimate)
        std = _std_from_envelope(envelope)
        step = max(abs(point), 1.0) * 1e-4
        fx = float(func(point))
        fp = float(func(point + step))
        fm = float(func(point - step))
        first = (fp - fm) / (2.0 * step)
        second = (fp - 2.0 * fx + fm) / (step * step)
        corrected_point = fx + 0.5 * second * std * std
        propagated_std = max(abs(first) * std, envelope.numeric_policy.absolute_tolerance)
        if envelope.confidence_level is not None:
            z = NormalDist().inv_cdf((1.0 + envelope.confidence_level) / 2.0)
            lower = corrected_point - z * propagated_std
            upper = corrected_point + z * propagated_std
            interval_semantics = envelope.interval_semantics
            confidence_level = envelope.confidence_level
        else:
            lower = corrected_point - 2.0 * propagated_std
            upper = corrected_point + 2.0 * propagated_std
            interval_semantics = IntervalSemantics.DETERMINISTIC_BOUNDS
            confidence_level = None
        output_payload = ParametricFitCarrier(
            family=DistributionFamily.NORMAL,
            parameters={"mean": corrected_point, "std": propagated_std},
        )
        output_flavour = ComposedFlavour.DELTA
        exactness = ExactnessKind.APPROXIMATION
        certificate_kind = CertificateKind.TAYLOR_REMAINDER
        certificate_radius = abs(0.5 * second * std * std) + float(bias_bound or 0.0)
        distribution_family = DistributionFamily.NORMAL
        point_estimate = corrected_point
        gate_eligible = envelope.gate_eligible
        sample_size = envelope.sample_size
        assumptions = ("local_linearization",)
    else:
        lower_in, upper_in = envelope.confidence_interval
        grid = np.linspace(float(lower_in), float(upper_in), max(int(grid_size), 3))
        pushed = np.asarray([float(func(float(value))) for value in grid], dtype=float)
        point_estimate = float(func(float(envelope.point_estimate)))
        lower = float(np.min(pushed))
        upper = float(np.max(pushed))
        interval_semantics = IntervalSemantics.DETERMINISTIC_BOUNDS
        confidence_level = None
        gate_eligible = False
        output_payload = None
        output_flavour = base.composed_flavour
        exactness = ExactnessKind.APPROXIMATION
        certificate_kind = (
            CertificateKind.WASSERSTEIN_1 if lipschitz_bound is not None else base.certificate_kind
        )
        certificate_radius = (
            None
            if base.certificate_radius is None or lipschitz_bound is None
            else (
                float(base.certificate_radius) * float(lipschitz_bound) + float(bias_bound or 0.0)
                if isinstance(base.certificate_radius, (int, float))
                else {
                    key: float(value) * float(lipschitz_bound)
                    for key, value in base.certificate_radius.items()
                }
            )
        )
        distribution_family = DistributionFamily.UNKNOWN
        sample_size = None
        assumptions = ("compressed_interval_input",)

    scope = _scope_from_shape(
        interval_semantics=interval_semantics,
        distribution_payload=output_payload,
    )
    provenance = _build_composition_provenance(
        input_envelopes=(envelope,),
        op="push_forward",
        stage_name="push_forward_envelope",
        output_flavour=output_flavour,
        exactness=exactness,
        certificate_kind=certificate_kind,
        certificate_radius=certificate_radius,
        confidence_level=confidence_level,
        scope=scope,
        map_name=map_label,
        lipschitz_bound=lipschitz_bound,
        bias_bound=bias_bound,
        sample_size=sample_size,
        assumptions=assumptions,
        notes={"cert_policy": cert_policy},
    )
    return UncertaintyEnvelope(
        numeric_policy=envelope.numeric_policy,
        point_estimate=float(point_estimate),
        confidence_interval=(float(min(lower, upper)), float(max(lower, upper))),
        confidence_level=confidence_level,
        distribution_family=distribution_family,
        source=envelope.source,
        propagation_method=(
            PropagationMethod.DELTA_METHOD
            if output_flavour is ComposedFlavour.DELTA
            else envelope.propagation_method
        ),
        interval_semantics=interval_semantics,
        distribution_payload=output_payload,
        composition_provenance=provenance,
        sample_size=sample_size,
        is_heuristic_ci=interval_semantics is IntervalSemantics.HEURISTIC_RANGE,
        gate_eligible=gate_eligible,
        metadata={
            **envelope.metadata,
            "push_forward_map": map_label,
            "push_forward_cert_policy": cert_policy,
        },
    )


def pull_back_envelope(
    func: Callable[[float], float],
    envelope: UncertaintyEnvelope,
    *,
    base_measure: tuple[float, float] | None = None,
    upstream_particles: PosteriorSamplesCarrier | tuple[float, ...] | None = None,
    local_inverse: Callable[[float], float] | None = None,
    map_name: str | None = None,
    grid_size: int = 257,
) -> UncertaintyEnvelope:
    """Lift a downstream admissible set back to an upstream constraint-style envelope."""

    if local_inverse is None and upstream_particles is None and base_measure is None:
        raise PullBackNotRepresentableError(
            "pull_back_envelope requires base_measure, upstream_particles, or local_inverse"
        )

    map_label = map_name or getattr(func, "__name__", "anonymous_map")
    base = _base_provenance(envelope)
    lower_out, upper_out = envelope.confidence_interval

    if upstream_particles is not None:
        if isinstance(upstream_particles, PosteriorSamplesCarrier):
            samples = np.asarray(upstream_particles.samples, dtype=float)
            weights = (
                None
                if upstream_particles.weights is None
                else np.asarray(upstream_particles.weights, dtype=float)
            )
        else:
            samples = np.asarray(tuple(float(value) for value in upstream_particles), dtype=float)
            weights = None
        mask = np.asarray(
            [
                float(lower_out) <= float(func(float(sample))) <= float(upper_out)
                for sample in samples
            ],
            dtype=bool,
        )
        selected = samples[mask]
        selected_weights = None if weights is None else weights[mask]
        if selected.size == 0:
            raise PullBackNotRepresentableError(
                "pull-back rejected every supplied upstream particle"
            )
        point_estimate = _weighted_mean(selected, selected_weights)
        lower = float(np.min(selected))
        upper = float(np.max(selected))
        distribution_payload = PosteriorSamplesCarrier(
            samples=tuple(float(value) for value in selected),
            weights=(
                None
                if selected_weights is None
                else tuple(float(weight) for weight in selected_weights)
            ),
        )
        notes = {"mode": "particle_reweighting"}
        sample_size = int(selected.size)
    elif local_inverse is not None:
        output_grid = np.linspace(float(lower_out), float(upper_out), max(int(grid_size), 3))
        pulled = np.asarray(
            [float(local_inverse(float(value))) for value in output_grid], dtype=float
        )
        point_estimate = float(local_inverse(float(envelope.point_estimate)))
        lower = float(np.min(pulled))
        upper = float(np.max(pulled))
        distribution_payload = None
        notes = {"mode": "local_inverse"}
        sample_size = None
    else:
        base_lower, base_upper = base_measure
        upstream_grid = np.linspace(float(base_lower), float(base_upper), max(int(grid_size), 3))
        mask = np.asarray(
            [
                float(lower_out) <= float(func(float(value))) <= float(upper_out)
                for value in upstream_grid
            ],
            dtype=bool,
        )
        selected = upstream_grid[mask]
        if selected.size == 0:
            raise PullBackNotRepresentableError(
                "pull-back found no admissible points in base_measure"
            )
        point_estimate = float(np.mean(selected))
        lower = float(np.min(selected))
        upper = float(np.max(selected))
        distribution_payload = None
        notes = {"mode": "base_measure_grid"}
        sample_size = int(selected.size)

    interval_semantics = IntervalSemantics.DETERMINISTIC_BOUNDS
    confidence_level = None
    scope = _scope_from_shape(
        interval_semantics=interval_semantics,
        distribution_payload=distribution_payload,
    )
    provenance = _build_composition_provenance(
        input_envelopes=(envelope,),
        op="pull_back",
        stage_name="pull_back_envelope",
        output_flavour=base.composed_flavour,
        exactness=ExactnessKind.CONSTRAINT_ONLY,
        certificate_kind=base.certificate_kind,
        certificate_radius=base.certificate_radius,
        confidence_level=confidence_level,
        scope=scope,
        map_name=map_label,
        sample_size=sample_size,
        assumptions=("inverse_not_identified_without_structure",),
        notes=notes,
    )
    return UncertaintyEnvelope(
        numeric_policy=envelope.numeric_policy,
        point_estimate=float(point_estimate),
        confidence_interval=(float(min(lower, upper)), float(max(lower, upper))),
        confidence_level=None,
        distribution_family=DistributionFamily.UNKNOWN,
        source=envelope.source,
        propagation_method=envelope.propagation_method,
        interval_semantics=interval_semantics,
        distribution_payload=distribution_payload,
        composition_provenance=provenance,
        sample_size=sample_size,
        is_heuristic_ci=False,
        gate_eligible=False,
        metadata={
            **envelope.metadata,
            "pull_back_map": map_label,
        },
    )


def combine_envelopes(
    envelopes: list[UncertaintyEnvelope] | tuple[UncertaintyEnvelope, ...],
    *,
    method: EnvelopeCombinationMethod = EnvelopeCombinationMethod.CONSERVATIVE_UNION,
    source: UncertaintySource = UncertaintySource.ENSEMBLE,
) -> UncertaintyEnvelope:
    """Combine compatible envelopes through one shared contract layer."""
    normalized = tuple(envelopes)
    if not normalized:
        raise ValueError("combine_envelopes requires at least one envelope")
    _require_compatible_envelopes(normalized)
    if len(normalized) == 1:
        return normalized[0]

    lows = [envelope.ci_lower for envelope in normalized]
    highs = [envelope.ci_upper for envelope in normalized]
    if method is EnvelopeCombinationMethod.INTERSECTION:
        combined_interval = (max(lows), min(highs))
        if combined_interval[0] > combined_interval[1]:
            raise UncertaintyCompatibilityError("envelope intersection is empty")
        point_estimate = sum(envelope.point_estimate for envelope in normalized) / len(normalized)
    elif method is EnvelopeCombinationMethod.PRECISION_WEIGHTED:
        weights = [
            1.0 / max(envelope.ci_width, envelope.numeric_policy.absolute_tolerance or 1e-12)
            for envelope in normalized
        ]
        weight_total = sum(weights)
        point_estimate = (
            sum(
                envelope.point_estimate * weight
                for envelope, weight in zip(normalized, weights, strict=True)
            )
            / weight_total
        )
        combined_interval = (min(lows), max(highs))
    else:
        point_estimate = sum(envelope.point_estimate for envelope in normalized) / len(normalized)
        combined_interval = (min(lows), max(highs))

    representative = normalized[0]
    distribution_family = (
        representative.distribution_family
        if len({envelope.distribution_family for envelope in normalized}) == 1
        else DistributionFamily.UNKNOWN
    )
    propagation_method = (
        representative.propagation_method
        if len({envelope.propagation_method for envelope in normalized}) == 1
        else PropagationMethod.NONE
    )
    sample_sizes = [
        envelope.sample_size for envelope in normalized if envelope.sample_size is not None
    ]
    scope = _scope_from_shape(
        interval_semantics=representative.interval_semantics,
        distribution_payload=None,
    )
    provenance = _build_composition_provenance(
        input_envelopes=normalized,
        op="compress",
        stage_name="combine_envelopes",
        output_flavour=(
            _base_provenance(representative).composed_flavour
            if len({_base_provenance(envelope).composed_flavour for envelope in normalized}) == 1
            else ComposedFlavour.MIXED
        ),
        exactness=(
            ExactnessKind.OUTER_BOUND
            if method is EnvelopeCombinationMethod.CONSERVATIVE_UNION
            else ExactnessKind.APPROXIMATION
        ),
        certificate_kind=(
            CertificateKind.EXACT
            if method is EnvelopeCombinationMethod.INTERSECTION
            else CertificateKind.WASSERSTEIN_1
        ),
        certificate_radius=_merge_certificate_radii(normalized),
        confidence_level=representative.confidence_level,
        scope=scope,
        notes={"summary_combination_method": method.value},
    )
    return UncertaintyEnvelope(
        numeric_policy=representative.numeric_policy,
        point_estimate=point_estimate,
        confidence_interval=combined_interval,
        confidence_level=representative.confidence_level,
        distribution_family=distribution_family,
        source=source,
        propagation_method=propagation_method,
        interval_semantics=representative.interval_semantics,
        composition_provenance=provenance,
        sample_size=sum(sample_sizes) if sample_sizes else None,
        is_heuristic_ci=any(envelope.is_heuristic_ci for envelope in normalized),
        gate_eligible=all(envelope.gate_eligible for envelope in normalized),
        metadata={
            "combined_from": len(normalized),
            "combination_method": method.value,
        },
    )


def envelope_meets_trust_policy(
    envelope: UncertaintyEnvelope,
    policy: TrustPolicySpec,
) -> bool:
    """Align envelope semantics with kernel trust policy fields."""
    if not envelope.gate_eligible:
        return False
    if policy.min_confidence is None:
        return True
    if envelope.confidence_level is None:
        return False
    return envelope.confidence_level >= policy.min_confidence


def persist_uncertainty_envelope(
    store: ArtifactStore,
    envelope: UncertaintyEnvelope,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = "ir.uncertainty_envelope",
    schema_version: str = "1.1",
) -> UncertaintyEnvelopeRef:
    """Persist an uncertainty envelope as a typed JSON artifact reference."""
    ref = put_json_artifact(
        store,
        envelope.model_dump(mode="python", round_trip=True),
        kind="ir.uncertainty_envelope",
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return UncertaintyEnvelopeRef.model_validate(ref)


def load_uncertainty_envelope(
    store: ArtifactStore,
    ref: UncertaintyEnvelopeRef,
) -> UncertaintyEnvelope:
    """Load an uncertainty envelope from artifact storage."""
    payload = get_json_artifact(store, ref)
    return UncertaintyEnvelope.model_validate(payload)


@dataclass(frozen=True, slots=True)
class PersistedUncertaintyAdmission:
    """Carry a resolved persisted envelope only when its evidence is admitted."""

    envelope: UncertaintyEnvelope | None
    limitation_codes: tuple[str, ...] = ()

    @property
    def admitted(self) -> bool:
        """Return whether the persisted envelope has an admitted evidence chain."""
        return self.envelope is not None and not self.limitation_codes


_SIMULATION_UNCERTAINTY_READ_ERRORS = (
    AttributeError,
    KeyError,
    OSError,
    RuntimeError,
    TypeError,
    ValidationError,
    ValueError,
)
_SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")
_PROPAGATION_COMPONENT = "scientist.node_propagate_uncertainty@1.0.0"


def load_simulation_result_uncertainty_admission(
    store: ArtifactStore,
    simulation_result_ref: Any,
    metric_id: str,
) -> PersistedUncertaintyAdmission:
    """Resolve and conservatively admit one propagated metric envelope.

    The reader binds the selected metric to the persisted simulation-result
    map, its per-metric propagation diagnostic, and the CAS content identities.
    It recomputes the available draw-count/sample consistency checks. The
    current propagation producer does not persist successful draw-to-input
    identity rows or a linked trusted verifier receipt, so even a complete
    producer-declared denominator remains limited and is never returned as an
    admitted numeric envelope.

    Args:
        store: Artifact store holding the persisted simulation artifacts.
        simulation_result_ref: Content-addressed ref for the SimulationResult.
        metric_id: Exact metric subject requested by the consumer.

    Returns:
        PersistedUncertaintyAdmission: An admitted envelope or typed limits
        explaining why the reader cannot use the result.
    """
    limitations: list[str] = []
    try:
        simulation_reference = _normalized_artifact_reference(store, simulation_result_ref)
        if simulation_reference.get("kind") != "foundry.simulation_result":
            return PersistedUncertaintyAdmission(None, ("simulation_result_kind_mismatch",))
        simulation_manifest = store.get_manifest(simulation_reference)
        _check_persisted_artifact_identity(
            simulation_manifest,
            simulation_reference,
            expected_kind="foundry.simulation_result",
            expected_schema="polisyos.core.SimulationResult",
            expected_version=None,
            prefix="simulation_result",
            limitations=limitations,
        )
        simulation_payload = get_json_artifact(
            store,
            simulation_reference,
        )
        if not isinstance(simulation_payload, dict):
            return PersistedUncertaintyAdmission(None, ("simulation_result_payload_invalid",))
        payload_version = simulation_payload.get("schema_version")
        schema = getattr(simulation_manifest, "artifact_schema", None)
        if (
            not isinstance(payload_version, str)
            or getattr(schema, "version", None) != payload_version
        ):
            limitations.append("simulation_result_schema_version_mismatch")
        _check_producer_identity(
            simulation_manifest,
            prefix="simulation_result",
            limitations=limitations,
        )

        envelopes = simulation_payload.get("uncertainty_envelopes")
        if not isinstance(envelopes, dict):
            return PersistedUncertaintyAdmission(
                None,
                tuple(dict.fromkeys([*limitations, "simulation_uncertainty_map_missing"])),
            )
        envelope_raw = envelopes.get(metric_id)
        if not isinstance(envelope_raw, dict):
            return PersistedUncertaintyAdmission(
                None,
                tuple(dict.fromkeys([*limitations, "metric_envelope_ref_missing"])),
            )
        envelope_reference = normalize_artifact_ref(envelope_raw)
        if envelope_reference.get("kind") != "ir.uncertainty_envelope":
            limitations.append("metric_envelope_kind_mismatch")
        envelope_manifest = store.get_manifest(envelope_reference)
        _check_persisted_artifact_identity(
            envelope_manifest,
            envelope_reference,
            expected_kind="ir.uncertainty_envelope",
            expected_schema="ir.uncertainty_envelope",
            expected_version="1.1",
            prefix="metric_envelope",
            limitations=limitations,
        )
        _check_producer_identity(
            envelope_manifest,
            prefix="metric_envelope",
            limitations=limitations,
        )
        envelope = UncertaintyEnvelope.model_validate(
            get_json_artifact(
                store,
                envelope_reference,
            )
        )

        report_raw = simulation_payload.get("propagation_report_ref")
        if not isinstance(report_raw, dict):
            return PersistedUncertaintyAdmission(
                None,
                tuple(dict.fromkeys([*limitations, "propagation_report_ref_missing"])),
            )
        report_reference = normalize_artifact_ref(report_raw)
        if report_reference.get("kind") != "foundry.propagation_report":
            limitations.append("propagation_report_kind_mismatch")
        report_manifest = store.get_manifest(report_reference)
        _check_persisted_artifact_identity(
            report_manifest,
            report_reference,
            expected_kind="foundry.propagation_report",
            expected_schema="polisyos.foundry.PropagationReport",
            expected_version="1.1",
            prefix="propagation_report",
            limitations=limitations,
        )
        _check_producer_identity(
            report_manifest,
            prefix="propagation_report",
            limitations=limitations,
        )
        _check_simulation_result_lineage(
            simulation_manifest,
            metric_id=metric_id,
            envelope_reference=envelope_reference,
            report_reference=report_reference,
            limitations=limitations,
        )
        _check_report_lineage(
            report_manifest,
            metric_id=metric_id,
            envelope_reference=envelope_reference,
            limitations=limitations,
        )
        _check_metric_envelope_subject(
            envelope,
            metric_id=metric_id,
            limitations=limitations,
        )
        report_payload = get_json_artifact(
            store,
            report_reference,
        )
        if not isinstance(report_payload, dict):
            return PersistedUncertaintyAdmission(
                None,
                tuple(dict.fromkeys([*limitations, "propagation_report_payload_invalid"])),
            )
        _check_propagation_report(
            report_payload,
            envelope,
            metric_id=metric_id,
            limitations=limitations,
        )
    except _SIMULATION_UNCERTAINTY_READ_ERRORS as exc:
        limitations.append(f"persisted_uncertainty_read_failed:{type(exc).__name__}")

    # Producer counts and labels can be internally consistent without proving
    # successful draw identities. There is no current persisted verifier
    # receipt linked to this envelope/report chain, so this consumer has no
    # admitted route to a finite normative value.
    limitations.append("draw_success_ledger_missing")
    limitations.append("draw_basis_verifier_missing")
    return PersistedUncertaintyAdmission(
        None,
        tuple(dict.fromkeys(limitations)),
    )


def _normalized_artifact_reference(store: ArtifactStore, ref: Any) -> dict[str, str]:
    """Normalize a typed ref or resolve an ID through its stored manifest."""
    if isinstance(ref, (str, ArtifactID)) or _is_string_root_model(ref):
        artifact_id = _normalize_scalar_artifact_id(ref)
        manifest = store.get_manifest(artifact_id)
        return {
            "artifact_id": str(artifact_id),
            "kind": str(getattr(manifest, "kind", "")),
            "media_type": str(getattr(manifest, "media_type", "")),
        }
    return normalize_artifact_ref(ref)


def _check_persisted_artifact_identity(
    manifest: Any,
    reference: dict[str, str],
    *,
    expected_kind: str,
    expected_schema: str,
    expected_version: str | None,
    prefix: str,
    limitations: list[str],
) -> None:
    """Reconcile a ref, CAS manifest, and pinned schema identity."""
    manifest_id = str(getattr(manifest, "artifact_id", ""))
    manifest_kind = str(getattr(manifest, "kind", ""))
    manifest_media = str(getattr(manifest, "media_type", ""))
    if manifest_id != reference.get("artifact_id"):
        limitations.append(f"{prefix}_content_binding_mismatch")
    if (
        manifest_kind != expected_kind
        or reference.get("kind") != manifest_kind
        or reference.get("media_type") != manifest_media
        or manifest_media != "application/json"
    ):
        limitations.append(f"{prefix}_manifest_identity_mismatch")
    artifact_schema = getattr(manifest, "artifact_schema", None)
    if getattr(artifact_schema, "name", None) != expected_schema:
        limitations.append(f"{prefix}_schema_name_mismatch")
    if (
        expected_version is not None
        and getattr(artifact_schema, "version", None) != expected_version
    ):
        limitations.append(f"{prefix}_schema_version_mismatch")


def _check_producer_identity(manifest: Any, *, prefix: str, limitations: list[str]) -> None:
    """Record producer identity gaps without treating labels as verification."""
    producer = getattr(manifest, "producer", None)
    if producer is None:
        limitations.append(f"{prefix}_producer_provenance_missing")
        return
    component = str(getattr(producer, "component", ""))
    version = str(getattr(producer, "version", ""))
    if component != _PROPAGATION_COMPONENT or version != "1.0.0":
        limitations.append(f"{prefix}_producer_provenance_mismatch")


def _manifest_inputs(manifest: Any) -> list[tuple[str, str, str | None]]:
    """Return persisted input role/content/view identities from one CAS manifest."""
    inputs = getattr(manifest, "inputs", ())
    if not isinstance(inputs, (list, tuple)):
        return []
    result: list[tuple[str, str, str | None]] = []
    for item in inputs:
        role = getattr(item, "role", None)
        artifact_id = getattr(item, "artifact_id", None)
        profile = getattr(item, "manifest_profile_sha256", None)
        if isinstance(role, str) and artifact_id is not None:
            result.append((role, str(artifact_id), profile))
    return result


def _artifact_reference_identity(reference: dict[str, str]) -> tuple[str, str | None]:
    """Return artifact ID and selected manifest profile from a normalized ref."""
    return reference["artifact_id"], reference.get("manifest_profile_sha256")


def _check_simulation_result_lineage(
    manifest: Any,
    *,
    metric_id: str,
    envelope_reference: dict[str, str],
    report_reference: dict[str, str],
    limitations: list[str],
) -> None:
    inputs = _manifest_inputs(manifest)
    expected = {
        f"metric_envelope.{metric_id}": _artifact_reference_identity(envelope_reference),
        "propagation_report": _artifact_reference_identity(report_reference),
    }
    for role, selected_identity in expected.items():
        matching = [
            (artifact_id, profile)
            for selected_role, artifact_id, profile in inputs
            if selected_role == role
        ]
        if matching != [selected_identity]:
            limitations.append(f"simulation_result_lineage_mismatch:{role}")
    if len([role for role, _, _ in inputs if role == "base_simulation_result"]) != 1:
        limitations.append("simulation_result_base_lineage_missing")
    if len([role for role, _, _ in inputs if role == "propagation_config"]) != 1:
        limitations.append("simulation_result_config_lineage_missing")


def _check_report_lineage(
    manifest: Any,
    *,
    metric_id: str,
    envelope_reference: dict[str, str],
    limitations: list[str],
) -> None:
    inputs = _manifest_inputs(manifest)
    role = f"metric_envelope.{metric_id}"
    if [
        (artifact_id, profile) for input_role, artifact_id, profile in inputs if input_role == role
    ] != [_artifact_reference_identity(envelope_reference)]:
        limitations.append("propagation_report_envelope_lineage_missing")
    if not any(input_role.startswith("input_envelope.") for input_role, _, _ in inputs):
        limitations.append("propagation_report_input_envelope_lineage_missing")


def _check_metric_envelope_subject(
    envelope: UncertaintyEnvelope,
    *,
    metric_id: str,
    limitations: list[str],
) -> None:
    provenance = envelope.composition_provenance
    history = () if provenance is None else provenance.operator_history
    if not history or history[-1].map_name != metric_id:
        limitations.append("uncertainty_metric_subject_unbound")
    if not envelope.gate_eligible:
        limitations.append("uncertainty_envelope_not_gate_eligible")
    if (
        envelope.is_heuristic_ci
        or envelope.interval_semantics is not IntervalSemantics.CONFIDENCE_INTERVAL
    ):
        limitations.append("uncertainty_interval_not_confidence_interval")
    if envelope.confidence_level is None:
        limitations.append("uncertainty_confidence_level_missing")
    if envelope.metadata.get("candidate_only") is True:
        limitations.append("uncertainty_envelope_candidate_only")


def _check_propagation_report(
    report: dict[str, Any],
    envelope: UncertaintyEnvelope,
    *,
    metric_id: str,
    limitations: list[str],
) -> None:
    if report.get("schema_version") != "1.1":
        limitations.append("propagation_report_payload_version_mismatch")
    diagnostics = report.get("diagnostics")
    if not isinstance(diagnostics, list):
        limitations.append("propagation_report_diagnostics_missing")
        return
    matching = [
        item
        for item in diagnostics
        if isinstance(item, dict) and item.get("metric_id") == metric_id
    ]
    if len(matching) != 1:
        limitations.append("propagation_metric_diagnostic_unbound")
        return
    metric_diagnostic = matching[0].get("diagnostics")
    if not isinstance(metric_diagnostic, dict):
        limitations.append("propagation_metric_diagnostic_invalid")
        return
    if metric_id in (report.get("missing_output_metric_ids") or []):
        limitations.append("propagation_metric_output_missing")
    if metric_id in (report.get("incomplete_output_metric_ids") or []):
        limitations.append("propagation_metric_output_incomplete")
    if metric_diagnostic.get("output_coverage_complete") is not True:
        limitations.append("propagation_metric_output_coverage_incomplete")

    provenance = report.get("draw_outcome_provenance")
    if not isinstance(provenance, dict) or provenance.get("schema_version") != "1.0":
        limitations.append("propagation_draw_ledger_missing_or_malformed")
        return
    requested = _nonnegative_int(provenance.get("requested_draw_count"))
    attempted = _nonnegative_int(provenance.get("attempted_draw_count"))
    successful = _nonnegative_int(provenance.get("successful_draw_count"))
    unattempted = _nonnegative_int(provenance.get("unattempted_draw_count"))
    failure_records = provenance.get("failure_records")
    if (
        requested is None
        or attempted is None
        or successful is None
        or unattempted is None
        or not isinstance(failure_records, list)
    ):
        limitations.append("propagation_draw_ledger_malformed")
        return

    failure_indexes: set[int] = set()
    metric_failure_indexes: set[int] = set()
    for record in failure_records:
        if not isinstance(record, dict):
            limitations.append("propagation_draw_failure_record_malformed")
            continue
        draw_index = _nonnegative_int(record.get("draw_index"))
        digest = record.get("sampled_input_sha256")
        outcomes = record.get("output_outcomes")
        if (
            draw_index is None
            or draw_index >= attempted
            or not isinstance(digest, str)
            or _SHA256_HEX.fullmatch(digest) is None
            or not isinstance(outcomes, list)
            or draw_index in failure_indexes
        ):
            limitations.append("propagation_draw_failure_record_malformed")
            continue
        failure_indexes.add(draw_index)
        for output in outcomes:
            if isinstance(output, dict) and output.get("output_metric_id") == metric_id:
                metric_failure_indexes.add(draw_index)
    recomputed_global_successes = attempted - len(failure_indexes)
    recomputed_metric_successes = attempted - len(metric_failure_indexes)
    if (
        requested <= 0
        or attempted > requested
        or unattempted != requested - attempted
        or successful != recomputed_global_successes
    ):
        limitations.append("propagation_draw_denominator_mismatch")
    if provenance.get("outcome_denominator_complete") is not (attempted == requested):
        limitations.append("propagation_draw_denominator_status_mismatch")

    metric_samples = _posterior_samples(envelope)
    sample_count = None if metric_samples is None else len(metric_samples)
    diagnostic_attempted = _nonnegative_int(metric_diagnostic.get("n_samples"))
    diagnostic_valid = _nonnegative_int(metric_diagnostic.get("n_valid"))
    diagnostic_failed = _nonnegative_int(metric_diagnostic.get("n_failed"))
    if (
        diagnostic_attempted != attempted
        or diagnostic_valid != recomputed_metric_successes
        or diagnostic_failed != len(metric_failure_indexes)
        or sample_count != diagnostic_valid
        or envelope.sample_size != diagnostic_valid
    ):
        limitations.append("propagation_draw_to_envelope_count_mismatch")
    if metric_failure_indexes:
        limitations.append("propagation_metric_has_failed_draws")
    if metric_samples is None:
        limitations.append("propagation_successful_draw_values_missing")
    elif diagnostic_valid is not None and diagnostic_valid > 0:
        point = float(np.mean(np.asarray(metric_samples, dtype=np.float64)))
        if not math.isclose(point, envelope.point_estimate, rel_tol=1e-6, abs_tol=1e-8):
            limitations.append("propagation_draw_point_summary_mismatch")
        if envelope.confidence_level is not None:
            alpha = 1.0 - envelope.confidence_level
            bounds = np.percentile(
                np.asarray(metric_samples, dtype=np.float64),
                [100.0 * alpha / 2.0, 100.0 * (1.0 - alpha / 2.0)],
            )
            if not (
                math.isclose(
                    float(bounds[0]), envelope.confidence_interval[0], rel_tol=1e-6, abs_tol=1e-8
                )
                and math.isclose(
                    float(bounds[1]), envelope.confidence_interval[1], rel_tol=1e-6, abs_tol=1e-8
                )
            ):
                limitations.append("propagation_draw_interval_summary_mismatch")

    recipe = provenance.get("sampling_recipe")
    if not isinstance(recipe, dict):
        limitations.append("propagation_sampling_recipe_missing")
        return
    input_names = recipe.get("input_param_names")
    input_digests = recipe.get("input_envelope_sha256")
    if (
        not isinstance(input_names, list)
        or not all(isinstance(name, str) for name in input_names)
        or not isinstance(input_digests, dict)
        or set(input_names) != set(input_digests)
        or not all(
            isinstance(digest, str) and _SHA256_HEX.fullmatch(digest) is not None
            for digest in input_digests.values()
        )
    ):
        limitations.append("propagation_sampling_input_identity_malformed")
    else:
        limitations.append("propagation_sampling_input_content_not_recomputed")
    if recipe.get("sample_axis") != "draw":
        limitations.append("propagation_draw_axis_unresolved")
    if provenance.get("implementation_identity_status") != "verified":
        limitations.append("propagation_implementation_identity_not_established")


def _nonnegative_int(value: Any) -> int | None:
    if type(value) is not int or value < 0:
        return None
    return value


def _posterior_samples(envelope: UncertaintyEnvelope) -> tuple[float, ...] | None:
    payload = envelope.distribution_payload
    if isinstance(payload, PosteriorSamplesCarrier) and payload.sample_axis == "draw":
        return payload.samples
    return None


__all__ = [
    "CertificateKind",
    "ComposedFlavour",
    "CompositionProvenance",
    "CompositionStep",
    "DistributionCarrier",
    "DistributionFamily",
    "EnvelopeCombinationMethod",
    "ExactnessKind",
    "FailureSeverity",
    "IntervalSemantics",
    "MixtureComponent",
    "MixtureDistributionCarrier",
    "NativeValueEstimandBinding",
    "NumericPolicySpec",
    "NumericToleranceMode",
    "OutputContractCapability",
    "OutputContractDeclaration",
    "ParametricFitCarrier",
    "PersistedUncertaintyAdmission",
    "PosteriorSamplesCarrier",
    "PropagationMethod",
    "PullBackNotRepresentableError",
    "QuantileSummaryCarrier",
    "RobustSetAdequacyStatus",
    "RobustSetCalibrationMethod",
    "RobustSetCalibrationReport",
    "RobustSetCalibrationStatus",
    "RobustSetFamily",
    "RobustSetFrontierPoint",
    "RobustSetSpec",
    "TypedFailureCard",
    "UncertaintyCompatibilityError",
    "UncertaintyEnvelope",
    "UncertaintySource",
    "UncertaintyType",
    "ValueUncertaintyProjectionKind",
    "build_composition_provenance",
    "combine_envelopes",
    "compress_envelope",
    "envelope_meets_trust_policy",
    "join_envelopes",
    "load_simulation_result_uncertainty_admission",
    "load_uncertainty_envelope",
    "persist_uncertainty_envelope",
    "pull_back_envelope",
    "push_forward_envelope",
    "supports_value_uncertainty_projection_contract",
    "value_uncertainty_output_contract",
]
