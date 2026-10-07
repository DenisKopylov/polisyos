"""Explicit posterior functionals carried by an unchanged v1.1 envelope.

The finite corpus is an input law, not a certificate of posterior quality.  An
unprofiled historical envelope retains its original generic point meaning.
"""

from __future__ import annotations

import math
import numbers
from typing import Any, Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, StrictFloat, model_validator

from polisyos.ir.artifacts import ArtifactStore, get_json_artifact
from polisyos.ir.model_layer.canon import CanonSpec, content_hash, to_canonical_bytes
from polisyos.ir.registry.refs import ArtifactRefModel, UncertaintyEnvelopeRef

from .uncertainty import (
    IntervalSemantics,
    NumericToleranceMode,
    PosteriorSamplesCarrier,
    UncertaintyEnvelope,
)

PROFILE_KEY = "posterior_summary_profile"
PROFILE_ID = "urn:policyos:ir:bayesian-posterior-summary-profile:1"


def _profile_declared(metadata: dict[str, Any]) -> bool:
    """Recognize new functional declarations without changing legacy joint laws."""
    return (
        PROFILE_KEY in metadata
        or "posterior_summary_profile_required" in metadata
        or metadata.get("point_functional") == "median"
        or metadata.get("mean_functional") == "weighted_arithmetic_mean"
        or metadata.get("interval_functional") == "equal_tail_inverse_cdf"
    )


class PosteriorParameterBinding(BaseModel):
    """Producer-declared identity; missing external lineage stays unknown."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    estimand_id: str = Field(min_length=1)
    unit: str = Field(min_length=1)
    scale: str = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_binding(self) -> PosteriorParameterBinding:
        if any(not value.strip() for value in (self.estimand_id, self.unit, self.scale)):
            raise ValueError("posterior estimand/unit/scale binding cannot be blank")
        return self


class PosteriorSummaryContext(BaseModel):
    """Preserve supplied identity without assigning source or gate authority."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    parameters: dict[str, PosteriorParameterBinding] = Field(default_factory=dict)
    lineage_refs: dict[str, ArtifactRefModel] = Field(default_factory=dict)
    time_roles: dict[str, str] = Field(default_factory=dict)
    purpose: str | None = None

    @property
    def content_hash(self) -> str:
        """Bind the supplied identity and lineage through the existing IR canon."""
        return content_hash(
            to_canonical_bytes(self.model_dump(mode="python"), CanonSpec(forbid_floats=False)),
            prefix=True,
        )


class PosteriorSummaryProfile(BaseModel):
    """Named, independently readable functionals of an exact finite corpus."""

    model_config = ConfigDict(extra="forbid", frozen=True, json_schema_extra={"$id": PROFILE_ID})
    profile_id: Literal["urn:policyos:ir:bayesian-posterior-summary-profile:1"] = PROFILE_ID
    profile_version: Literal["1.0"] = "1.0"
    point_functional: Literal["median"] = "median"
    mean_functional: Literal["weighted_arithmetic_mean"] = "weighted_arithmetic_mean"
    interval_functional: Literal["equal_tail_inverse_cdf"] = "equal_tail_inverse_cdf"
    numeric_representation: Literal["finite_float64"] = "finite_float64"
    compression: Literal["none"] = "none"
    thinning: Literal["none"] = "none"
    gate_eligible: Literal[False] = False
    parameter_name: str = Field(min_length=1)
    parameter_order: tuple[str, ...] = Field(min_length=1)
    draw_ids: tuple[str, ...] = Field(min_length=1)
    row_identity_basis: Literal["producer_input_order", "producer_supplied_ids"]
    sample_axis: str = Field(min_length=1)
    probabilities: tuple[StrictFloat, ...] = Field(min_length=1)
    posterior_mean: StrictFloat
    credible_mass: StrictFloat = Field(gt=0, lt=1)
    carrier_content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    joint_law_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    binding: PosteriorParameterBinding | None = None
    context: PosteriorSummaryContext = Field(default_factory=PosteriorSummaryContext)
    context_content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _validate_profile(self) -> PosteriorSummaryProfile:
        if (
            self.parameter_order != tuple(sorted(set(self.parameter_order)))
            or self.parameter_name not in self.parameter_order
            or len(set(self.draw_ids)) != len(self.draw_ids)
            or any(not item.strip() for item in (*self.parameter_order, *self.draw_ids))
            or not self.sample_axis.strip()
            or len(self.draw_ids) != len(self.probabilities)
            or not math.isfinite(self.posterior_mean)
            or any(not math.isfinite(p) or p < 0 for p in self.probabilities)
            or not math.isclose(math.fsum(self.probabilities), 1.0, rel_tol=0, abs_tol=2e-15)
            or self.binding != self.context.parameters.get(self.parameter_name)
            or set(self.context.parameters) - set(self.parameter_order)
            or self.context.content_hash != self.context_content_hash
        ):
            raise ValueError("posterior summary profile identity/probabilities are invalid")
        return self


def posterior_summary_functionals(
    samples: tuple[float, ...], probabilities: tuple[float, ...], credible_mass: float
) -> tuple[float, float, tuple[float, float]]:
    """Compute named mean and atom-preserving inverse-CDF quantiles.

    Sampling admission owns normalization and representable-category checks;
    this helper consumes the canonical probabilities and gives them their
    explicitly versioned summary meaning.

    Args:
        samples: Finite observations in the declared sample axis.
        probabilities: Already normalized finite-machine category masses.
        credible_mass: Requested two-sided equal-tail mass in (0, 1).

    Returns:
        Arithmetic mean, inverse-CDF median and equal-tail bounds.

    Raises:
        ValueError: If input or sorted quantile categories cannot be represented.
    """
    if len(samples) != len(probabilities) or not samples or not 0 < credible_mass < 1:
        raise ValueError("posterior summary shape/mass is invalid")
    if any(not math.isfinite(x) for x in (*samples, *probabilities)):
        raise ValueError("posterior summary values must be finite")
    if any(p < 0 for p in probabilities) or not math.isclose(
        math.fsum(probabilities), 1, rel_tol=0, abs_tol=2e-15
    ):
        raise ValueError("posterior summary requires canonical probabilities")
    # Readback admits the finite CDF too: a constructor-valid carrier alone
    # does not establish canonical, representable positive categories.
    _posterior_cdf(np.asarray(probabilities, dtype=np.float64))
    mean = math.fsum(x * p for x, p in zip(samples, probabilities, strict=True))
    if not math.isfinite(mean):
        raise ValueError("posterior mean is outside finite float64 representation")
    order = np.argsort(samples, kind="stable")
    ordered_samples = np.asarray(samples, dtype=np.float64)[order]
    ordered_weights = np.asarray(probabilities, dtype=np.float64)[order]
    positive = ordered_weights > 0
    ordered_samples, ordered_weights = ordered_samples[positive], ordered_weights[positive]
    cumulative = _posterior_cdf(ordered_weights)
    alpha = (1.0 - credible_mass) / 2.0
    indices = np.searchsorted(cumulative, [0.5, alpha, 1.0 - alpha], side="left")
    median, lo, hi = (float(ordered_samples[i]) for i in indices)
    return mean, median, (lo, hi)


def _posterior_cdf(probabilities: np.ndarray) -> np.ndarray:
    """Apply the existing positive-category invariant in quantile sort order."""
    cumulative = np.cumsum(probabilities, dtype=np.float64)
    last_positive = np.flatnonzero(probabilities > 0)[-1]
    cumulative[last_positive:] = 1.0
    masses = np.diff(np.concatenate(([0.0], cumulative)))
    if np.any(masses < 0) or not np.array_equal(masses > 0, probabilities > 0):
        raise ValueError("positive posterior category collapses in the finite CDF")
    return cumulative


def posterior_carrier_content_hash(carrier: PosteriorSamplesCarrier) -> str:
    """Reuse the IR canonical content identity for the stored carrier.

    Args:
        carrier: Exact stored finite corpus, weights and sample axis.

    Returns:
        The prefixed canonical SHA-256 identity.
    """
    return content_hash(
        to_canonical_bytes(carrier.model_dump(mode="python"), CanonSpec(forbid_floats=False)),
        prefix=True,
    )


def read_posterior_summary_profile(
    envelope: UncertaintyEnvelope,
) -> PosteriorSummaryProfile | None:
    """Recompute a declared profile; refuse malformed named computations.

    Args:
        envelope: Compatible v1.1 envelope read through configured storage.

    Returns:
        Reconciled profile, or None for a historical unprofiled envelope.

    Raises:
        ValueError: If a declared profile, corpus or functional is inconsistent.
    """
    if PROFILE_KEY not in envelope.metadata:
        if _profile_declared(envelope.metadata):
            raise ValueError("posterior summary profile is missing")
        return None
    profile = PosteriorSummaryProfile.model_validate(envelope.metadata[PROFILE_KEY])
    carrier = envelope.distribution_payload
    if not isinstance(carrier, PosteriorSamplesCarrier):
        raise ValueError("posterior summary exact carrier is missing")
    if (
        envelope.schema_version != "1.1"
        or envelope.metadata.get("posterior_summary_profile_required") is not True
        or envelope.gate_eligible
        or envelope.numeric_policy.mode is not NumericToleranceMode.DECIMAL_EXACT
        or envelope.interval_semantics is not IntervalSemantics.CREDIBLE_INTERVAL
        or envelope.confidence_level != profile.credible_mass
        or carrier.weights != profile.probabilities
        or carrier.sample_axis != profile.sample_axis
        or len(carrier.samples) != len(profile.draw_ids)
        or posterior_carrier_content_hash(carrier) != profile.carrier_content_hash
        or envelope.metadata.get("param_name") != profile.parameter_name
        or envelope.metadata.get("joint_parameter_order") != list(profile.parameter_order)
        or envelope.metadata.get("joint_draw_ids") != list(profile.draw_ids)
        or envelope.metadata.get("joint_law_sha256") != profile.joint_law_sha256
        or envelope.metadata.get("joint_sample_id") != profile.joint_law_sha256
    ):
        raise ValueError("posterior summary profile/carrier binding is invalid")
    mean, median, interval = posterior_summary_functionals(
        carrier.samples, profile.probabilities, profile.credible_mass
    )
    if (
        mean != profile.posterior_mean
        or median != envelope.point_estimate
        or interval != envelope.confidence_interval
        or envelope.metadata.get("point_functional") != "median"
        or envelope.metadata.get("interval_functional") != "equal_tail_inverse_cdf"
    ):
        raise ValueError("posterior summary named functionals do not reconcile")
    return profile


def posterior_nominal_mean(
    envelope: UncertaintyEnvelope,
    *,
    parameter_name: str | None = None,
    binding: PosteriorParameterBinding | None = None,
) -> float:
    """Use the admitted posterior mean, or the unchanged legacy point.

    Args:
        envelope: Exact input envelope whose profile is recomputed.
        parameter_name: Consumer mapping coordinate, when declared.
        binding: Expected estimand/unit/scale supplied by the consumer.

    Returns:
        Explicit posterior mean, or historical generic point for legacy input.

    Raises:
        ValueError: If a declared profile or its consumer join is invalid.
    """
    profile = read_posterior_summary_profile(envelope)
    if profile is not None and (
        (parameter_name is not None and profile.parameter_name != parameter_name)
        or (binding is not None and profile.binding != binding)
    ):
        raise ValueError("posterior summary parameter/estimand/unit binding does not match")
    return envelope.point_estimate if profile is None else profile.posterior_mean


def validate_raw_posterior_summary_envelope(
    payload: Any, *, parameter_name: str | None = None
) -> None:
    """Admit declared raw profile values before the legacy numeric decoder.

    Args:
        payload: Raw JSON value read by the existing CAS/codec.
        parameter_name: Enclosing consumer/report coordinate, if supplied.

    Raises:
        ValueError: If a declared profile has coerced non-real or mismatched data.
    """
    if not isinstance(payload, dict) or not isinstance(payload.get("metadata"), dict):
        return
    metadata = payload["metadata"]
    if not _profile_declared(metadata):
        return
    if PROFILE_KEY not in metadata:
        raise ValueError("posterior summary profile is missing")
    profile = PosteriorSummaryProfile.model_validate(metadata[PROFILE_KEY])
    if parameter_name is not None and profile.parameter_name != parameter_name:
        raise ValueError("posterior profile coordinate does not match its enclosing mapping")
    carrier = payload.get("distribution_payload")
    if not isinstance(carrier, dict) or carrier.get("carrier_type") != "posterior_samples":
        raise ValueError("posterior summary raw carrier is missing")
    for label in ("samples", "weights"):
        values = carrier.get(label)
        if not isinstance(values, (list, tuple)) or not values:
            raise ValueError("posterior summary raw carrier axes are missing")
        if any(
            isinstance(value, (bool, np.bool_))
            or not isinstance(value, numbers.Real)
            or not math.isfinite(float(value))
            for value in values
        ):
            raise ValueError("posterior summary raw carrier requires finite real non-bool values")
    numeric_values = [payload.get("point_estimate"), payload.get("confidence_level")]
    interval = payload.get("confidence_interval")
    if not isinstance(interval, (list, tuple)) or len(interval) != 2:
        raise ValueError("posterior summary raw interval is malformed")
    numeric_values.extend(interval)
    if any(
        isinstance(value, (bool, np.bool_))
        or not isinstance(value, numbers.Real)
        or not math.isfinite(float(value))
        for value in numeric_values
    ):
        raise ValueError("posterior summary raw functionals require finite real non-bool values")


def load_posterior_summary_envelope(
    store: ArtifactStore, ref: UncertaintyEnvelopeRef
) -> UncertaintyEnvelope:
    """Read a profile-bearing law through a strict inlet and the legacy decoder.

    Args:
        store: Existing configured artifact store.
        ref: Existing typed envelope content reference.

    Returns:
        The unchanged v1.1 model after raw-profile and CAS admission.

    Raises:
        ValueError: If a declared law has an invalid raw carrier or CAS profile.
    """
    raw = get_json_artifact(store, ref.artifact_id)
    validate_raw_posterior_summary_envelope(raw)
    metadata = raw.get("metadata", {}) if isinstance(raw, dict) else {}
    if isinstance(metadata, dict) and PROFILE_KEY in metadata:
        manifest = store.get_manifest(ref.artifact_id)
        schema = manifest.artifact_schema
        if (
            ref.kind != "ir.uncertainty_envelope"
            or ref.media_type != "application/json"
            or manifest.kind != "ir.uncertainty_envelope"
            or manifest.media_type != "application/json"
            or schema is None
            or schema.name != "ir.uncertainty_envelope"
            or schema.version != "1.1"
            or not store.verify(ref.artifact_id).ok
        ):
            raise ValueError("posterior summary CAS kind/schema/content is invalid")
    # Decode the exact raw value admitted above using the existing v1.1 model.
    return UncertaintyEnvelope.model_validate(raw)


__all__ = [
    "PosteriorParameterBinding",
    "PosteriorSummaryContext",
    "PosteriorSummaryProfile",
    "load_posterior_summary_envelope",
    "posterior_carrier_content_hash",
    "posterior_nominal_mean",
    "posterior_summary_functionals",
    "read_posterior_summary_profile",
    "validate_raw_posterior_summary_envelope",
]
