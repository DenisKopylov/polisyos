from __future__ import annotations

import math

import pytest
from pydantic import ValidationError

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.analytics.uncertainty import (
    CertificateKind,
    ComposedFlavour,
    ExactnessKind,
    DistributionFamily,
    EnvelopeCombinationMethod,
    IntervalSemantics,
    MixtureComponent,
    MixtureDistributionCarrier,
    NumericPolicySpec,
    NumericToleranceMode,
    ParametricFitCarrier,
    PosteriorSamplesCarrier,
    PropagationMethod,
    PullBackNotRepresentableError,
    QuantileSummaryCarrier,
    UncertaintyCompatibilityError,
    UncertaintyEnvelope,
    UncertaintySource,
    compress_envelope,
    combine_envelopes,
    envelope_meets_trust_policy,
    join_envelopes,
    load_uncertainty_envelope,
    persist_uncertainty_envelope,
    pull_back_envelope,
    push_forward_envelope,
)
from polisyos.ir.kernel.trust import TrustPolicySpec


def test_uncertainty_envelope_basic_creation() -> None:
    env = UncertaintyEnvelope(
        point_estimate=2.35,
        confidence_interval=(1.92, 2.78),
        source=UncertaintySource.CALIBRATION,
        distribution_family=DistributionFamily.NORMAL,
        propagation_method=PropagationMethod.DELTA_METHOD,
    )
    assert env.schema_version == "1.1"
    assert env.confidence_level == 0.95
    assert env.interval_semantics == IntervalSemantics.CONFIDENCE_INTERVAL
    assert env.ci_width == pytest.approx(0.86)


def test_uncertainty_envelope_rejects_invalid_ci() -> None:
    with pytest.raises(ValidationError):
        UncertaintyEnvelope(
            point_estimate=2.0,
            confidence_interval=(3.0, 1.0),
            source=UncertaintySource.TRUST,
            confidence_level=None,
            interval_semantics=IntervalSemantics.DETERMINISTIC_BOUNDS,
        )


def test_uncertainty_envelope_requires_confidence_level_for_statistical_interval() -> None:
    with pytest.raises(ValidationError):
        UncertaintyEnvelope(
            point_estimate=0.4,
            confidence_interval=(0.2, 0.6),
            source=UncertaintySource.CALIBRATION,
            confidence_level=None,
            interval_semantics=IntervalSemantics.CONFIDENCE_INTERVAL,
        )


def test_uncertainty_envelope_heuristic_gate_constraints() -> None:
    with pytest.raises(ValidationError):
        UncertaintyEnvelope(
            point_estimate=0.7,
            confidence_interval=(0.6, 0.8),
            source=UncertaintySource.CONFLICT_RESOLUTION,
            confidence_level=None,
            interval_semantics=IntervalSemantics.HEURISTIC_RANGE,
            is_heuristic_ci=True,
            gate_eligible=True,
        )


def test_uncertainty_envelope_relative_uncertainty_near_zero() -> None:
    env = UncertaintyEnvelope(
        point_estimate=1e-16,
        confidence_interval=(-0.1, 0.1),
        source=UncertaintySource.MANUAL,
        confidence_level=None,
        interval_semantics=IntervalSemantics.DETERMINISTIC_BOUNDS,
    )
    assert env.relative_uncertainty is None


def test_uncertainty_envelope_cas_roundtrip(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    env = UncertaintyEnvelope(
        point_estimate=42.0,
        confidence_interval=(40.0, 44.0),
        source=UncertaintySource.TRUST,
        confidence_level=None,
        interval_semantics=IntervalSemantics.DETERMINISTIC_BOUNDS,
        metadata={"trust_policy_id": "strict"},
    )

    ref_1 = persist_uncertainty_envelope(store, env)
    ref_2 = persist_uncertainty_envelope(store, env)
    loaded = load_uncertainty_envelope(store, ref_1)

    assert ref_1.kind == "ir.uncertainty_envelope"
    assert ref_1.artifact_id == ref_2.artifact_id
    assert loaded == env


def test_numeric_policy_canonicalizes_bounded_floats() -> None:
    env = UncertaintyEnvelope(
        numeric_policy=NumericPolicySpec(
            mode=NumericToleranceMode.HYBRID,
            decimal_places=6,
            absolute_tolerance=1e-6,
        ),
        point_estimate=1.23456789,
        confidence_interval=(-0.0000001, 2.34567891),
        source=UncertaintySource.CAUSAL,
        confidence_level=None,
        interval_semantics=IntervalSemantics.DETERMINISTIC_BOUNDS,
    )

    assert env.point_estimate == pytest.approx(1.234568)
    assert env.confidence_interval[0] == 0.0
    assert env.confidence_interval[1] == pytest.approx(2.345679)


def test_combine_envelopes_conservative_union() -> None:
    left = UncertaintyEnvelope(
        point_estimate=1.0,
        confidence_interval=(0.8, 1.2),
        source=UncertaintySource.CAUSAL,
    )
    right = UncertaintyEnvelope(
        point_estimate=1.1,
        confidence_interval=(0.9, 1.3),
        source=UncertaintySource.BOOTSTRAP,
    )

    combined = combine_envelopes(
        [left, right],
        method=EnvelopeCombinationMethod.CONSERVATIVE_UNION,
    )

    assert combined.source is UncertaintySource.ENSEMBLE
    assert combined.confidence_interval == (0.8, 1.3)
    assert combined.metadata["combination_method"] == "conservative_union"
    assert combined.composition_provenance is not None
    assert combined.composition_provenance.operator_history[-1].op == "compress"


def test_combine_envelopes_rejects_incompatible_interval_semantics() -> None:
    left = UncertaintyEnvelope(
        point_estimate=1.0,
        confidence_interval=(0.8, 1.2),
        source=UncertaintySource.CAUSAL,
    )
    right = UncertaintyEnvelope(
        point_estimate=1.1,
        confidence_interval=(0.9, 1.3),
        source=UncertaintySource.CAUSAL,
        confidence_level=None,
        interval_semantics=IntervalSemantics.DETERMINISTIC_BOUNDS,
    )

    with pytest.raises(UncertaintyCompatibilityError):
        combine_envelopes([left, right])


def test_distribution_carriers_validate_and_roundtrip(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    env = UncertaintyEnvelope(
        point_estimate=0.4,
        confidence_interval=(0.2, 0.6),
        source=UncertaintySource.BOOTSTRAP,
        distribution_family=DistributionFamily.BOOTSTRAP,
        distribution_payload=PosteriorSamplesCarrier(samples=(0.2, 0.4, 0.6)),
    )
    quantiles = QuantileSummaryCarrier(quantiles={"0.05": 0.1, "0.95": 0.9})
    mixture = MixtureDistributionCarrier(
        components=(
            MixtureComponent(
                weight=0.6,
                family=DistributionFamily.NORMAL,
                parameters={"mu": 0.4, "sigma": 0.1},
            ),
            MixtureComponent(
                weight=0.4,
                family=DistributionFamily.NORMAL,
                parameters={"mu": 0.5, "sigma": 0.2},
            ),
        )
    )

    ref = persist_uncertainty_envelope(store, env)
    loaded = load_uncertainty_envelope(store, ref)

    assert loaded.distribution_payload == env.distribution_payload
    assert quantiles.quantiles["0.95"] == pytest.approx(0.9)
    assert len(mixture.components) == 2


def test_envelope_meets_trust_policy_uses_confidence_level() -> None:
    env = UncertaintyEnvelope(
        point_estimate=1.0,
        confidence_interval=(0.8, 1.2),
        source=UncertaintySource.TRUST,
        confidence_level=0.95,
    )
    strict = TrustPolicySpec(policy_id="strict", min_confidence=0.9)
    too_strict = TrustPolicySpec(policy_id="too_strict", min_confidence=0.99)

    assert envelope_meets_trust_policy(env, strict) is True
    assert envelope_meets_trust_policy(env, too_strict) is False


def test_join_envelopes_builds_outer_hull_with_history() -> None:
    left = UncertaintyEnvelope(
        point_estimate=1.0,
        confidence_interval=(0.8, 1.2),
        source=UncertaintySource.CAUSAL,
        distribution_payload=PosteriorSamplesCarrier(samples=(0.8, 1.0, 1.2)),
    )
    right = UncertaintyEnvelope(
        point_estimate=1.3,
        confidence_interval=(1.1, 1.6),
        source=UncertaintySource.BOOTSTRAP,
        propagation_method=PropagationMethod.MONTE_CARLO,
        distribution_payload=PosteriorSamplesCarrier(samples=(1.1, 1.3, 1.6)),
    )

    joined = join_envelopes((left, right))

    assert joined.confidence_interval == (0.8, 1.6)
    assert isinstance(joined.distribution_payload, PosteriorSamplesCarrier)
    assert joined.composition_provenance is not None
    assert joined.composition_provenance.exactness == ExactnessKind.OUTER_BOUND
    assert joined.composition_provenance.composed_flavour == ComposedFlavour.MONTE_CARLO
    assert joined.composition_provenance.operator_history[-1].op == "join"


def test_push_forward_particles_preserves_law_object() -> None:
    env = UncertaintyEnvelope(
        point_estimate=2.0,
        confidence_interval=(1.0, 3.0),
        source=UncertaintySource.BOOTSTRAP,
        propagation_method=PropagationMethod.MONTE_CARLO,
        distribution_family=DistributionFamily.BOOTSTRAP,
        distribution_payload=PosteriorSamplesCarrier(samples=(1.0, 2.0, 3.0)),
        sample_size=3,
    )

    pushed = push_forward_envelope(lambda value: value * value, env, map_name="square")

    assert isinstance(pushed.distribution_payload, PosteriorSamplesCarrier)
    assert pushed.distribution_payload.samples == (1.0, 4.0, 9.0)
    assert pushed.composition_provenance is not None
    assert pushed.composition_provenance.certificate_kind == CertificateKind.KOLMOGOROV
    assert pushed.composition_provenance.operator_history[-1].op == "push_forward"
    assert pushed.composition_provenance.composed_flavour == ComposedFlavour.MONTE_CARLO


def test_compress_envelope_to_moments_marks_approximation() -> None:
    env = UncertaintyEnvelope(
        point_estimate=0.4,
        confidence_interval=(0.2, 0.6),
        source=UncertaintySource.BOOTSTRAP,
        propagation_method=PropagationMethod.MONTE_CARLO,
        distribution_family=DistributionFamily.BOOTSTRAP,
        distribution_payload=PosteriorSamplesCarrier(samples=(0.2, 0.4, 0.6)),
        sample_size=3,
    )

    compressed = compress_envelope(env, target="moments")

    assert isinstance(compressed.distribution_payload, ParametricFitCarrier)
    assert compressed.distribution_payload.family == DistributionFamily.NORMAL
    assert compressed.composition_provenance is not None
    assert compressed.composition_provenance.exactness == ExactnessKind.APPROXIMATION
    assert compressed.composition_provenance.operator_history[-1].op == "compress"


def test_compress_envelope_to_particles_from_parametric_fit() -> None:
    env = UncertaintyEnvelope(
        point_estimate=0.0,
        confidence_interval=(-1.96, 1.96),
        source=UncertaintySource.CALIBRATION,
        distribution_family=DistributionFamily.NORMAL,
        distribution_payload=ParametricFitCarrier(
            family=DistributionFamily.NORMAL,
            parameters={"mean": 0.0, "std": 1.0},
        ),
        sample_size=16,
    )

    compressed = compress_envelope(env, target="particles")

    assert isinstance(compressed.distribution_payload, PosteriorSamplesCarrier)
    assert compressed.sample_size == 16
    assert len(compressed.distribution_payload.samples) == 16
    assert compressed.composition_provenance is not None
    assert compressed.composition_provenance.operator_history[-1].op == "compress"


def test_pull_back_requires_extra_structure() -> None:
    env = UncertaintyEnvelope(
        point_estimate=4.0,
        confidence_interval=(3.0, 5.0),
        source=UncertaintySource.CAUSAL,
    )

    with pytest.raises(PullBackNotRepresentableError):
        pull_back_envelope(lambda value: value * value, env)


def test_pull_back_with_local_inverse_returns_constraint_envelope() -> None:
    env = UncertaintyEnvelope(
        point_estimate=6.25,
        confidence_interval=(4.0, 9.0),
        source=UncertaintySource.CAUSAL,
        confidence_level=None,
        interval_semantics=IntervalSemantics.DETERMINISTIC_BOUNDS,
    )

    pulled = pull_back_envelope(
        lambda value: value * value,
        env,
        local_inverse=math.sqrt,
        map_name="square",
    )

    assert pulled.interval_semantics == IntervalSemantics.DETERMINISTIC_BOUNDS
    assert pulled.confidence_level is None
    assert pulled.gate_eligible is False
    assert pulled.composition_provenance is not None
    assert pulled.composition_provenance.exactness == ExactnessKind.CONSTRAINT_ONLY
    assert pulled.composition_provenance.operator_history[-1].op == "pull_back"
