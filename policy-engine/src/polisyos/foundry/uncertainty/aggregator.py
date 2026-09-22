"""Combine multiple uncertainty envelopes into one downstream-facing summary envelope."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum
from statistics import NormalDist

from polisyos.ir.analytics.uncertainty import (
    CertificateKind,
    ComposedFlavour,
    DistributionFamily,
    ExactnessKind,
    IntervalSemantics,
    PropagationMethod,
    UncertaintyCompatibilityError,
    UncertaintyEnvelope,
    UncertaintySource,
    build_composition_provenance,
)

from .covariance import extract_std


class AggregationStrategy(str, Enum):
    """Choose how competing uncertainty envelopes should be merged for downstream use."""

    WIDEST = "widest"
    PRECISION_WEIGHTED = "precision_weighted"
    BAYESIAN_COMBINATION = "bayesian_combination"


_ESTABLISHED_INDEPENDENCE_VALUES = frozenset({"independent"})


@dataclass(frozen=True, slots=True)
class _AggregationContext:
    """Facts about the supplied inputs that formulas must not infer numerically."""

    source_count: int
    effective_information_count: int | None
    effective_information_count_status: str
    duplicate_source_count: int
    dependency_unknown: bool


def _origin_key(envelope: UncertaintyEnvelope) -> tuple[str, ...] | str | None:
    """Return a content-bound provenance key, excluding numeric fallback IDs."""
    provenance = envelope.composition_provenance
    if provenance is not None and provenance.origin_envelope_ids:
        origin_ids = tuple(provenance.origin_envelope_ids)
        if all(_is_content_bound_origin_id(origin_id) for origin_id in origin_ids):
            return ("composition", *origin_ids)
    for field in ("envelope_id", "artifact_id", "ref_id", "origin_id"):
        value = envelope.metadata.get(field)
        if _is_content_bound_origin_id(value):
            return value
    return None


def _is_content_bound_origin_id(value: object) -> bool:
    """Reject IR's numeric-derived inline identity surrogate at this boundary."""
    if not isinstance(value, str):
        return False
    normalized = value.strip().lower()
    return bool(normalized) and not normalized.startswith("inline:")


def _is_established_independence_value(value: object) -> bool:
    """Accept only explicit canonical independence evidence."""
    if value is True:
        return True
    return (
        isinstance(value, str)
        and value.strip().lower().replace("-", "_")
        in _ESTABLISHED_INDEPENDENCE_VALUES
    )


def _has_unknown_dependency(envelopes: Sequence[UncertaintyEnvelope]) -> bool:
    """Return whether independence is absent, conflicting, or unrecognized."""
    for envelope in envelopes:
        dependency_values = [
            envelope.metadata[key]
            for key in ("dependency", "dependence")
            if key in envelope.metadata
        ]
        independence = envelope.metadata.get("independence")
        if independence is False:
            return True
        if dependency_values:
            if not all(_is_established_independence_value(value) for value in dependency_values):
                return True
            if independence is not None and not _is_established_independence_value(independence):
                return True
            continue
        if not _is_established_independence_value(independence):
            return True
    return False


def _prepare_inputs(
    envelopes: Sequence[UncertaintyEnvelope],
) -> tuple[tuple[UncertaintyEnvelope, ...], _AggregationContext]:
    """Collapse exact repeated origins while rejecting conflicting same-origin values."""
    unique: list[UncertaintyEnvelope] = []
    by_origin: dict[tuple[str, ...] | str, UncertaintyEnvelope] = {}
    all_origins_bound = True
    for envelope in envelopes:
        origin = _origin_key(envelope)
        if origin is None:
            all_origins_bound = False
            unique.append(envelope)
            continue
        previous = by_origin.get(origin)
        if previous is None:
            by_origin[origin] = envelope
            unique.append(envelope)
            continue
        if previous != envelope:
            raise UncertaintyCompatibilityError(
                f"conflicting envelopes for origin {origin!r}"
            )

    normalized = tuple(unique)
    dependency_unknown = _has_unknown_dependency(normalized)
    effective_information_count = (
        len(normalized)
        if all_origins_bound and not dependency_unknown
        else None
    )
    context = _AggregationContext(
        source_count=len(envelopes),
        effective_information_count=effective_information_count,
        effective_information_count_status=(
            "recomputed" if effective_information_count is not None else "not_established"
        ),
        duplicate_source_count=len(envelopes) - len(normalized),
        dependency_unknown=dependency_unknown,
    )
    return normalized, context


def _aggregation_metadata(
    envelopes: Sequence[UncertaintyEnvelope],
    context: _AggregationContext,
    *,
    method: str,
    **extra: object,
) -> dict[str, object]:
    """Build a compact metadata view without confusing sources and information units."""
    metadata: dict[str, object] = {
        "aggregation_method": method,
        "n_sources": context.source_count,
        "source_count": context.source_count,
        "effective_information_count": context.effective_information_count,
        "effective_information_count_status": context.effective_information_count_status,
        "duplicate_source_count": context.duplicate_source_count,
        "sources": [env.source.value for env in envelopes],
    }
    metadata.update(extra)
    return metadata


def _passthrough_with_context(
    envelope: UncertaintyEnvelope,
    context: _AggregationContext,
) -> UncertaintyEnvelope:
    """Retain a singleton's declared semantics while exposing aggregation accounting."""
    metadata = {
        **envelope.metadata,
        **_aggregation_metadata((envelope,), context, method="passthrough"),
    }
    return envelope.model_copy(
        update={
            "metadata": metadata,
            "sample_size": context.effective_information_count or envelope.sample_size,
            "gate_eligible": envelope.gate_eligible and not context.dependency_unknown,
        }
    )


def _summary_output_flavour(
    envelopes: Sequence[UncertaintyEnvelope],
) -> ComposedFlavour:
    flavours = {
        (
            env.composition_provenance.composed_flavour
            if env.composition_provenance is not None
            else (
                ComposedFlavour.QUASI_MONTE_CARLO
                if str(env.metadata.get("mc_sampling_method", "")).lower() in {"sobol", "halton"}
                else (
                    ComposedFlavour.MONTE_CARLO
                    if env.propagation_method is PropagationMethod.MONTE_CARLO
                    else (
                        ComposedFlavour.DELTA
                        if env.propagation_method is PropagationMethod.DELTA_METHOD
                        else ComposedFlavour.ANALYTICAL
                    )
                )
            )
        )
        for env in envelopes
    }
    return next(iter(flavours)) if len(flavours) == 1 else ComposedFlavour.MIXED


def aggregate_envelopes(
    envelopes: Sequence[UncertaintyEnvelope],
    *,
    method: str = "widest",
    confidence_level: float = 0.95,
) -> UncertaintyEnvelope:
    """Merge several envelopes into one summary interval for reports or gates."""
    if not envelopes:
        raise ValueError("Cannot aggregate empty envelope list")
    normalized, context = _prepare_inputs(envelopes)
    if len(envelopes) == 1:
        return envelopes[0]
    if len(normalized) == 1:
        return _passthrough_with_context(normalized[0], context)

    if method == AggregationStrategy.PRECISION_WEIGHTED:
        return _precision_weighted(normalized, confidence_level, context=context)
    if method == AggregationStrategy.BAYESIAN_COMBINATION:
        return _bayesian_combination(normalized, confidence_level, context=context)
    if method == AggregationStrategy.WIDEST or method == "widest":
        return _widest(normalized, confidence_level, context=context)

    raise ValueError(f"Unknown aggregation method: {method}")


# ------------------------------------------------------------------
# Widest (original implementation)
# ------------------------------------------------------------------


def _widest(
    envelopes: Sequence[UncertaintyEnvelope],
    confidence_level: float,
    *,
    context: _AggregationContext,
    force_fail_closed: bool = False,
) -> UncertaintyEnvelope:
    point = sum(env.point_estimate for env in envelopes) / len(envelopes)
    lo = min(env.confidence_interval[0] for env in envelopes)
    hi = max(env.confidence_interval[1] for env in envelopes)

    semantics = {env.interval_semantics for env in envelopes}
    levels = {env.confidence_level for env in envelopes}
    any_heuristic = any(env.is_heuristic_ci for env in envelopes)
    if any_heuristic:
        semantics = IntervalSemantics.HEURISTIC_RANGE
        level = None
        gate_eligible = False
    elif len(semantics) == 1 and len(levels) == 1 and not force_fail_closed:
        semantics = next(iter(semantics))
        level = next(iter(levels))
        gate_eligible = all(env.gate_eligible for env in envelopes)
    elif (
        len(semantics) == 1
        and next(iter(semantics))
        in {IntervalSemantics.DETERMINISTIC_BOUNDS, IntervalSemantics.HEURISTIC_RANGE}
        and not force_fail_closed
    ):
        semantics = next(iter(semantics))
        level = None
        gate_eligible = all(env.gate_eligible for env in envelopes)
    else:
        semantics = IntervalSemantics.DETERMINISTIC_BOUNDS
        level = None
        gate_eligible = False

    if (
        force_fail_closed
        or context.dependency_unknown
        or context.effective_information_count is None
    ):
        semantics = (
            IntervalSemantics.HEURISTIC_RANGE
            if any_heuristic
            else IntervalSemantics.DETERMINISTIC_BOUNDS
        )
        level = None
        gate_eligible = False

    point = min(max(point, lo), hi)

    return UncertaintyEnvelope(
        point_estimate=float(point),
        confidence_interval=(float(lo), float(hi)),
        confidence_level=level,
        distribution_family=DistributionFamily.UNKNOWN,
        source=UncertaintySource.ENSEMBLE,
        propagation_method=PropagationMethod.NONE,
        interval_semantics=semantics,
        sample_size=context.effective_information_count,
        is_heuristic_ci=any_heuristic,
        gate_eligible=gate_eligible,
        composition_provenance=build_composition_provenance(
            input_envelopes=tuple(envelopes),
            op="compress",
            stage_name="foundry.aggregate.widest",
            output_flavour=_summary_output_flavour(envelopes),
            exactness=ExactnessKind.OUTER_BOUND,
            certificate_kind=CertificateKind.WASSERSTEIN_1,
            certificate_radius=None,
            confidence_level=level,
            scope=(
                ("expectation", "bounds")
                if level is None
                else ("expectation", "interval", "quantile")
            ),
            notes={"aggregation_method": "widest"},
        ),
        metadata=_aggregation_metadata(envelopes, context, method="widest"),
    )


# ------------------------------------------------------------------
# Precision-weighted (inverse-variance weighting)
# ------------------------------------------------------------------


def _precision_weighted(
    envelopes: Sequence[UncertaintyEnvelope],
    confidence_level: float,
    *,
    context: _AggregationContext,
) -> UncertaintyEnvelope:
    if context.effective_information_count is None or context.dependency_unknown or any(
        env.interval_semantics is not IntervalSemantics.CONFIDENCE_INTERVAL
        or env.is_heuristic_ci
        for env in envelopes
    ):
        return _widest(
            envelopes,
            confidence_level,
            context=context,
            force_fail_closed=True,
        )

    stds = [extract_std(env) for env in envelopes]
    if any(s < 1e-30 for s in stds):
        # Degenerate — fallback to widest
        return _widest(envelopes, confidence_level, context=context)

    precisions = [1.0 / (s * s) for s in stds]
    total_precision = sum(precisions)

    point = (
        sum(p * float(env.point_estimate) for p, env in zip(precisions, envelopes))
        / total_precision
    )
    combined_var = 1.0 / total_precision
    combined_std = math.sqrt(combined_var)

    z = NormalDist().inv_cdf((1.0 + confidence_level) / 2.0)
    lo = point - z * combined_std
    hi = point + z * combined_std

    return UncertaintyEnvelope(
        point_estimate=float(point),
        confidence_interval=(float(lo), float(hi)),
        confidence_level=confidence_level,
        distribution_family=DistributionFamily.NORMAL,
        source=UncertaintySource.ENSEMBLE,
        propagation_method=PropagationMethod.NONE,
        interval_semantics=IntervalSemantics.CONFIDENCE_INTERVAL,
        sample_size=context.effective_information_count,
        is_heuristic_ci=False,
        gate_eligible=(
            all(env.gate_eligible for env in envelopes)
            and context.effective_information_count is not None
        ),
        composition_provenance=build_composition_provenance(
            input_envelopes=tuple(envelopes),
            op="compress",
            stage_name="foundry.aggregate.precision_weighted",
            output_flavour=_summary_output_flavour(envelopes),
            exactness=ExactnessKind.APPROXIMATION,
            certificate_kind=CertificateKind.WASSERSTEIN_1,
            certificate_radius=float(combined_std),
            confidence_level=confidence_level,
            scope=("expectation", "interval", "quantile"),
            notes={"aggregation_method": "precision_weighted"},
        ),
        metadata=_aggregation_metadata(
            envelopes,
            context,
            method="precision_weighted",
            combined_std=float(combined_std),
        ),
    )


# ------------------------------------------------------------------
# Bayesian combination (Gaussian conjugate update)
# ------------------------------------------------------------------


def _bayesian_combination(
    envelopes: Sequence[UncertaintyEnvelope],
    confidence_level: float,
    *,
    context: _AggregationContext,
) -> UncertaintyEnvelope:
    if context.effective_information_count is None or context.dependency_unknown or any(
        env.interval_semantics is not IntervalSemantics.CONFIDENCE_INTERVAL
        or env.is_heuristic_ci
        for env in envelopes
    ):
        return _widest(
            envelopes,
            confidence_level,
            context=context,
            force_fail_closed=True,
        )

    stds = [extract_std(env) for env in envelopes]
    if any(s < 1e-30 for s in stds):
        return _widest(envelopes, confidence_level, context=context)

    # Sequential Bayesian update: prior = first envelope
    mu = float(envelopes[0].point_estimate)
    var = stds[0] ** 2

    for env, s in zip(envelopes[1:], stds[1:]):
        data_var = s * s
        new_var = 1.0 / (1.0 / var + 1.0 / data_var)
        mu = new_var * (mu / var + float(env.point_estimate) / data_var)
        var = new_var

    combined_std = math.sqrt(var)
    z = NormalDist().inv_cdf((1.0 + confidence_level) / 2.0)
    lo = mu - z * combined_std
    hi = mu + z * combined_std

    return UncertaintyEnvelope(
        point_estimate=float(mu),
        confidence_interval=(float(lo), float(hi)),
        confidence_level=confidence_level,
        distribution_family=DistributionFamily.NORMAL,
        source=UncertaintySource.ENSEMBLE,
        propagation_method=PropagationMethod.NONE,
        interval_semantics=IntervalSemantics.CREDIBLE_INTERVAL,
        sample_size=context.effective_information_count,
        is_heuristic_ci=False,
        gate_eligible=(
            all(env.gate_eligible for env in envelopes)
            and context.effective_information_count is not None
        ),
        composition_provenance=build_composition_provenance(
            input_envelopes=tuple(envelopes),
            op="compress",
            stage_name="foundry.aggregate.bayesian_combination",
            output_flavour=_summary_output_flavour(envelopes),
            exactness=ExactnessKind.APPROXIMATION,
            certificate_kind=CertificateKind.WASSERSTEIN_1,
            certificate_radius=float(combined_std),
            confidence_level=confidence_level,
            scope=("expectation", "interval", "quantile"),
            notes={"aggregation_method": "bayesian_combination"},
        ),
        metadata=_aggregation_metadata(
            envelopes,
            context,
            method="bayesian_combination",
            posterior_std=float(combined_std),
        ),
    )
