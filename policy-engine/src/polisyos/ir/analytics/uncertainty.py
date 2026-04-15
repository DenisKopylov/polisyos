"""Compositional uncertainty contracts shared across IR analytics outputs."""
from __future__ import annotations

import math
from enum import Enum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.ir.artifacts import ArtifactStore, InputRef, get_json_artifact, put_json_artifact
from polisyos.ir.canon import CanonSpec
from polisyos.ir.kernel.trust import TrustPolicySpec
from polisyos.ir.refs import UncertaintyEnvelopeRef


class UncertaintyCompatibilityError(ValueError):
    """Raised when envelopes with incompatible interval semantics are combined."""


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
    def _validate_payload(self) -> "PosteriorSamplesCarrier":
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
    def _validate_payload(self) -> "QuantileSummaryCarrier":
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
    def _validate_payload(self) -> "ParametricFitCarrier":
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
    def _validate_payload(self) -> "MixtureComponent":
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
    def _validate_payload(self) -> "MixtureDistributionCarrier":
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
            policy.canonicalize(float(sample))
            for sample in normalized.get("samples", ())
        ]
        if normalized.get("weights") is not None:
            normalized["weights"] = [
                policy.canonicalize(float(weight))
                for weight in normalized["weights"]
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

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    numeric_policy: NumericPolicySpec = Field(default_factory=NumericPolicySpec)

    point_estimate: float
    confidence_interval: tuple[float, float]
    confidence_level: float | None = Field(default=0.95, gt=0.0, lt=1.0)

    distribution_family: DistributionFamily = DistributionFamily.UNKNOWN
    source: UncertaintySource
    propagation_method: PropagationMethod = PropagationMethod.NONE
    interval_semantics: IntervalSemantics = IntervalSemantics.CONFIDENCE_INTERVAL
    distribution_payload: DistributionCarrier | None = None

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
        return payload

    @model_validator(mode="after")
    def _validate_fields(self) -> "UncertaintyEnvelope":
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
        point_estimate = sum(
            envelope.point_estimate * weight
            for envelope, weight in zip(normalized, weights, strict=True)
        ) / weight_total
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
        envelope.sample_size
        for envelope in normalized
        if envelope.sample_size is not None
    ]
    return UncertaintyEnvelope(
        numeric_policy=representative.numeric_policy,
        point_estimate=point_estimate,
        confidence_interval=combined_interval,
        confidence_level=representative.confidence_level,
        distribution_family=distribution_family,
        source=source,
        propagation_method=propagation_method,
        interval_semantics=representative.interval_semantics,
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
    schema_version: str = "1.0",
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
    payload = get_json_artifact(store, ref.artifact_id)
    return UncertaintyEnvelope.model_validate(payload)


__all__ = [
    "DistributionCarrier",
    "DistributionFamily",
    "EnvelopeCombinationMethod",
    "IntervalSemantics",
    "MixtureComponent",
    "MixtureDistributionCarrier",
    "NumericPolicySpec",
    "NumericToleranceMode",
    "ParametricFitCarrier",
    "PosteriorSamplesCarrier",
    "PropagationMethod",
    "QuantileSummaryCarrier",
    "UncertaintyCompatibilityError",
    "UncertaintyEnvelope",
    "UncertaintySource",
    "combine_envelopes",
    "envelope_meets_trust_policy",
    "persist_uncertainty_envelope",
    "load_uncertainty_envelope",
]
