"""Combine multiple uncertainty envelopes into one downstream-facing summary envelope."""

from __future__ import annotations

import hashlib
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from statistics import NormalDist
from typing import Any, Literal

from polisyos.core.artifacts import artifact_manifest_profile_sha256
from polisyos.ir.analytics.uncertainty import (
    CertificateKind,
    ComposedFlavour,
    DistributionFamily,
    ExactnessKind,
    IntervalSemantics,
    NumericPolicySpec,
    PropagationMethod,
    UncertaintyEnvelope,
    UncertaintySource,
    build_composition_provenance,
    load_uncertainty_envelope,
    persist_uncertainty_envelope,
)
from polisyos.ir.artifacts import ArtifactStore, InputRef, normalize_input_sequence
from polisyos.ir.registry.refs import UncertaintyEnvelopeRef

from .covariance import extract_std


class AggregationStrategy(str, Enum):
    """Choose how competing uncertainty envelopes should be merged for downstream use."""

    WIDEST = "widest"
    PRECISION_WEIGHTED = "precision_weighted"
    BAYESIAN_COMBINATION = "bayesian_combination"


@dataclass(frozen=True, slots=True)
class _AggregationContext:
    """Facts about the supplied inputs that formulas must not infer numerically."""

    source_count: int
    effective_information_count: int | None
    effective_information_count_status: str
    duplicate_source_count: int
    dependency_unknown: bool
    numeric_policy: NumericPolicySpec


_UNVERIFIED_IDENTITY_AND_RELATION_KEYS = frozenset(
    {
        "envelope_id",
        "artifact_id",
        "ref_id",
        "origin_id",
        "independence",
        "dependency",
        "relation_status",
        "common_estimand_status",
        "common_subject_status",
        "unit_binding_status",
        "combination_status",
        "effective_information_count",
        "effective_information_count_status",
    }
)


def _without_unverified_identity_claims(envelope: UncertaintyEnvelope) -> UncertaintyEnvelope:
    """Drop caller-asserted identity/relation labels before composing multiple inputs."""
    metadata = {
        key: value
        for key, value in envelope.metadata.items()
        if key not in _UNVERIFIED_IDENTITY_AND_RELATION_KEYS
    }
    provenance = envelope.composition_provenance
    if provenance is not None:
        provenance = provenance.model_copy(update={"origin_envelope_ids": ()})
    return envelope.model_copy(update={"metadata": metadata, "composition_provenance": provenance})


def _has_unknown_dependency(envelopes: Sequence[UncertaintyEnvelope]) -> bool:
    """Treat distinct inputs as dependent until a source-bound relation is resolved.

    The current envelope carrier has no relation resolver, so caller metadata labels such as
    ``True`` or ``"independent"`` cannot authorize a precision-style formula. A caller that has
    already resolved an exact selected CAS view may collapse it before calling this function.
    """

    return len(envelopes) > 1


def _prepare_inputs(
    envelopes: Sequence[UncertaintyEnvelope],
) -> tuple[tuple[UncertaintyEnvelope, ...], _AggregationContext]:
    """Retain every input; only a selected persisted view can establish identity here."""
    numeric_policy = _reconcile_input_context(envelopes)
    normalized = tuple(_without_unverified_identity_claims(envelope) for envelope in envelopes)
    dependency_unknown = _has_unknown_dependency(normalized)
    context = _AggregationContext(
        source_count=len(envelopes),
        effective_information_count=None,
        effective_information_count_status="not_established",
        duplicate_source_count=0,
        dependency_unknown=dependency_unknown,
        numeric_policy=numeric_policy,
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
    if context.source_count > 1:
        metadata.update(
            {
                "relation_status": "not_established",
                "common_estimand_status": "not_established",
                "common_subject_status": "not_established",
                "unit_binding_status": "not_established",
                "effective_information_count_status": "not_established",
                "aggregation_input_context_status": "recomputed_conflict_free_claims",
                "numeric_policy_status": "recomputed_identical_typed_policy",
                "aggregation_context_assumption": (
                    "candidate_only_conditional_hull: input numeric values are provisionally "
                    "treated as a shared coordinate only to construct a non-gating outer hull; "
                    "no common unit, subject, estimand, or dependence basis is established"
                ),
            }
        )
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
    """Combine envelopes conservatively; in-memory labels cannot prove source identity."""
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
        numeric_policy=context.numeric_policy,
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
    if (
        context.effective_information_count is None
        or context.dependency_unknown
        or any(
            env.interval_semantics is not IntervalSemantics.CONFIDENCE_INTERVAL
            or env.is_heuristic_ci
            for env in envelopes
        )
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
        numeric_policy=context.numeric_policy,
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
    if (
        context.effective_information_count is None
        or context.dependency_unknown
        or any(
            env.interval_semantics is not IntervalSemantics.CONFIDENCE_INTERVAL
            or env.is_heuristic_ci
            for env in envelopes
        )
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
        numeric_policy=context.numeric_policy,
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


_UNVERIFIED_OUTPUT_METADATA_KEYS = frozenset(
    {
        "n_sources",
        "source_count",
        "duplicate_source_count",
        "sources",
        "combined_std",
        "posterior_std",
        "effective_information_count",
        "effective_information_count_status",
        "input_envelope_view_count",
        "unique_selected_view_count",
        "repeated_selected_view_count",
        "selected_view_identity_status",
        "relation_status",
        "common_estimand_status",
        "common_subject_status",
        "unit_binding_status",
        "explicit_context_compatibility",
        "aggregation_input_context_status",
        "aggregation_context_assumption",
        "numeric_policy_status",
        "combination_status",
    }
)


def _selected_envelope_view_key(
    ref: UncertaintyEnvelopeRef,
) -> tuple[str, str, str, str | None]:
    """Identify a CAS view by its content, typed kind/media, and selected profile."""
    return (
        str(ref.artifact_id),
        ref.kind,
        ref.media_type,
        ref.manifest_profile_sha256,
    )


def _require_selected_envelope_manifest(
    store: ArtifactStore,
    ref: UncertaintyEnvelopeRef,
) -> Any:
    """Resolve and verify one exact profiled uncertainty-envelope view."""
    if ref.kind != "ir.uncertainty_envelope" or ref.media_type != "application/json":
        raise ValueError("uncertainty_envelope_kind_or_media_mismatch")
    if ref.manifest_profile_sha256 is None:
        raise ValueError("uncertainty_envelope_selected_profile_missing")
    manifest = store.get_manifest(ref)
    schema = manifest.artifact_schema
    if (
        manifest.kind != ref.kind
        or manifest.media_type != ref.media_type
        or schema is None
        or schema.name != "ir.uncertainty_envelope"
        or schema.version != "1.1"
        or artifact_manifest_profile_sha256(manifest) != ref.manifest_profile_sha256
    ):
        raise ValueError("uncertainty_envelope_selected_manifest_mismatch")
    stored_bytes = store.get_bytes(ref.artifact_id)
    if hashlib.sha256(stored_bytes).hexdigest() != ref.artifact_id.hex:
        raise ValueError("uncertainty_envelope_content_address_mismatch")
    return manifest


def _source_envelope_input_ref(ref: UncertaintyEnvelopeRef) -> InputRef:
    """Record an exact selected source view in the output manifest."""
    if ref.manifest_profile_sha256 is None:
        raise ValueError("source_uncertainty_envelope_selected_profile_missing")
    return InputRef(
        artifact_id=ref.artifact_id,
        role="source_uncertainty_envelope",
        manifest_profile_sha256=ref.manifest_profile_sha256,
    )


@dataclass(frozen=True, slots=True)
class _AggregationSemanticContextV1:
    """Typed projection of the legacy context axes recognized by this owner.

    The projection is a consistency check over caller-supplied legacy values. It is not
    source-owned unit, subject, estimand, or relation evidence.
    """

    schema_version: Literal["polisyos.foundry.uncertainty.aggregation_semantic_context.v1"]
    numeric_policy: NumericPolicySpec
    unit: str | None
    currency: str | None
    subject: str | None
    subject_id: str | None
    subject_kind: str | None
    estimand: str | None
    estimand_id: str | None


_SEMANTIC_CONTEXT_AXES = (
    "unit",
    "currency",
    "subject",
    "subject_id",
    "subject_kind",
    "estimand",
    "estimand_id",
)


def _semantic_context_text(value: object) -> str | None:
    """Parse one recognized legacy axis without coercing malformed values to absence."""
    if value is None:
        return None
    if isinstance(value, Enum):
        value = value.value
    if not isinstance(value, str):
        raise ValueError("uncertainty_envelope_explicit_context_malformed")
    if not value.strip():
        return None
    return value


def _project_semantic_context_v1(
    envelope: UncertaintyEnvelope,
) -> _AggregationSemanticContextV1:
    """Project only typed quantity axes; arbitrary producer metadata stays per-source."""
    metadata = envelope.metadata
    raw_nested = metadata.get("context")
    if raw_nested is not None and not isinstance(raw_nested, Mapping):
        raise ValueError("uncertainty_envelope_explicit_context_malformed")
    nested: Mapping[str, Any] = raw_nested if isinstance(raw_nested, Mapping) else {}

    projected: dict[str, str | None] = {}
    for axis in _SEMANTIC_CONTEXT_AXES:
        candidates = [
            _semantic_context_text(source[axis]) for source in (metadata, nested) if axis in source
        ]
        present = {candidate for candidate in candidates if candidate is not None}
        if len(present) > 1:
            raise ValueError("uncertainty_envelope_explicit_context_mismatch")
        projected[axis] = next(iter(present), None)

    return _AggregationSemanticContextV1(
        schema_version="polisyos.foundry.uncertainty.aggregation_semantic_context.v1",
        numeric_policy=envelope.numeric_policy,
        unit=projected["unit"],
        currency=projected["currency"],
        subject=projected["subject"],
        subject_id=projected["subject_id"],
        subject_kind=projected["subject_kind"],
        estimand=projected["estimand"],
        estimand_id=projected["estimand_id"],
    )


def _reconcile_input_context(
    envelopes: Sequence[UncertaintyEnvelope],
) -> NumericPolicySpec:
    """Refuse recognized axis conflicts while leaving producer metadata source-local."""
    if not envelopes:
        raise ValueError("uncertainty_envelope_cohort_empty")
    projections = tuple(_project_semantic_context_v1(envelope) for envelope in envelopes)
    numeric_policy = projections[0].numeric_policy
    if any(item.numeric_policy != numeric_policy for item in projections[1:]):
        raise ValueError("uncertainty_envelope_numeric_policy_mismatch")

    for axis in _SEMANTIC_CONTEXT_AXES:
        present = {getattr(item, axis) for item in projections if getattr(item, axis) is not None}
        if len(present) > 1:
            raise ValueError("uncertainty_envelope_explicit_context_mismatch")
    return numeric_policy


def aggregate_persisted_envelope_views(
    store: ArtifactStore,
    refs: tuple[UncertaintyEnvelopeRef, ...],
    *,
    method: Literal["widest", "precision_weighted", "bayesian_combination"] = "widest",
) -> UncertaintyEnvelope:
    """Aggregate exact selected CAS views, retaining unknown relations as a non-gating hull."""
    if not refs:
        raise ValueError("uncertainty_envelope_cohort_empty")
    selected_envelopes: list[UncertaintyEnvelope] = []
    for ref in refs:
        _require_selected_envelope_manifest(store, ref)
        selected_envelopes.append(load_uncertainty_envelope(store, ref))
    _reconcile_input_context(tuple(selected_envelopes))

    unique: dict[tuple[str, str, str, str | None], UncertaintyEnvelope] = {}
    for ref, envelope in zip(refs, selected_envelopes, strict=True):
        key = _selected_envelope_view_key(ref)
        if key not in unique:
            unique[key] = _without_unverified_identity_claims(envelope)

    envelopes = tuple(unique.values())
    aggregate = aggregate_envelopes(envelopes, method=method)
    metadata = {
        **aggregate.metadata,
        "input_envelope_view_count": len(refs),
        "unique_selected_view_count": len(unique),
        "repeated_selected_view_count": len(refs) - len(unique),
        "selected_view_identity_status": "recomputed",
        "relation_status": "not_established",
        "common_estimand_status": "not_established",
        "common_subject_status": "not_established",
        "unit_binding_status": "not_established",
        "effective_information_count": None,
        "effective_information_count_status": "not_established",
    }
    return aggregate.model_copy(
        update={"metadata": metadata, "gate_eligible": aggregate.gate_eligible and len(unique) == 1}
    )


def persist_aggregated_envelope(
    store: ArtifactStore,
    source_refs: tuple[UncertaintyEnvelopeRef, ...],
    *,
    method: Literal["widest", "precision_weighted", "bayesian_combination"] = "widest",
) -> UncertaintyEnvelopeRef:
    """Persist the existing IR envelope with exact selected source-view edges."""
    aggregate = aggregate_persisted_envelope_views(store, source_refs, method=method)
    return persist_uncertainty_envelope(
        store,
        aggregate,
        inputs=[_source_envelope_input_ref(ref) for ref in source_refs],
        return_selected_profile=True,
    )


def load_aggregated_envelope_fresh(
    store: ArtifactStore,
    aggregate_ref: UncertaintyEnvelopeRef,
    *,
    source_refs: tuple[UncertaintyEnvelopeRef, ...],
    method: Literal["widest", "precision_weighted", "bayesian_combination"] = "widest",
) -> UncertaintyEnvelope:
    """Recompute a persisted aggregate from its exact ordered selected source views."""
    manifest = _require_selected_envelope_manifest(store, aggregate_ref)
    expected_inputs = [_source_envelope_input_ref(ref) for ref in source_refs]
    if normalize_input_sequence(manifest.inputs) != expected_inputs:
        raise ValueError("aggregated_uncertainty_envelope_manifest_source_mismatch")
    stored = load_uncertainty_envelope(store, aggregate_ref)
    expected = aggregate_persisted_envelope_views(store, source_refs, method=method)
    if stored != expected:
        raise ValueError("aggregated_uncertainty_envelope_does_not_recompute")
    return stored
