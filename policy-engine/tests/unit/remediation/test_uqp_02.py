"""UQP-02 witnesses for covariance axes, joint laws, and empirical carriers."""

from __future__ import annotations

from collections import Counter

import numpy as np
import numpy.testing as npt
import pytest

from polisyos.core.artifacts import FileSystemCAS, ensure_ir_artifact_store
from polisyos.foundry.uncertainty.analytical import AnalyticalPropagator
from polisyos.foundry.uncertainty.config import PropagationConfig
from polisyos.foundry.uncertainty.covariance import build_covariance_matrix
from polisyos.foundry.uncertainty.delta import DeltaMethodPropagator
from polisyos.foundry.uncertainty.dispatcher import PropagationDispatcher
from polisyos.foundry.uncertainty.monte_carlo import MonteCarloPropagator
from polisyos.ir.analytics.uncertainty import (
    DistributionFamily,
    IntervalSemantics,
    ParametricFitCarrier,
    PosteriorSamplesCarrier,
    PropagationMethod,
    UncertaintyEnvelope,
    UncertaintySource,
    load_uncertainty_envelope,
    persist_uncertainty_envelope,
)
from polisyos.ir.artifacts import InputRef
from polisyos.ir.model_layer.canon import CanonViolation

pytestmark = pytest.mark.unit


def _normal_env(
    point: float,
    std: float,
    *,
    metadata: dict[str, object] | None = None,
) -> UncertaintyEnvelope:
    """Build a normal input with an independently specified standard deviation."""
    return UncertaintyEnvelope(
        point_estimate=point,
        confidence_interval=(point - 1.96 * std, point + 1.96 * std),
        confidence_level=0.95,
        distribution_family=DistributionFamily.NORMAL,
        source=UncertaintySource.CALIBRATION,
        propagation_method=PropagationMethod.NONE,
        interval_semantics=IntervalSemantics.CONFIDENCE_INTERVAL,
        gate_eligible=True,
        metadata=metadata or {},
    )


def _empirical_env(
    samples: tuple[float, ...],
    *,
    sample_axis: str = "row",
    weights: tuple[float, ...] | None = None,
    joint_id: str | None = "uqp-test-shared-rows",
    metadata: dict[str, object] | None = None,
) -> UncertaintyEnvelope:
    """Build a small empirical carrier whose row axis is part of the contract."""
    envelope_metadata = dict(metadata or {})
    if joint_id is not None:
        envelope_metadata.setdefault("joint_sample_id", joint_id)
    return UncertaintyEnvelope(
        point_estimate=float(np.mean(samples)),
        confidence_interval=(float(min(samples)), float(max(samples))),
        confidence_level=0.95,
        distribution_family=DistributionFamily.BOOTSTRAP,
        source=UncertaintySource.BOOTSTRAP,
        propagation_method=PropagationMethod.MONTE_CARLO,
        interval_semantics=IntervalSemantics.CONFIDENCE_INTERVAL,
        distribution_payload=PosteriorSamplesCarrier(
            samples=samples,
            sample_axis=sample_axis,
            weights=weights,
        ),
        sample_size=len(samples),
        gate_eligible=True,
        metadata=envelope_metadata,
    )


def _parametric_normal_env(
    *,
    envelope_point: float = 0.0,
    envelope_std: float = 1.0,
    fit_mean: float = 42.0,
    fit_std: float = 0.25,
) -> UncertaintyEnvelope:
    """Build a normal envelope whose typed fit intentionally differs from its interval."""
    return UncertaintyEnvelope(
        point_estimate=envelope_point,
        confidence_interval=(
            envelope_point - 1.96 * envelope_std,
            envelope_point + 1.96 * envelope_std,
        ),
        confidence_level=0.95,
        distribution_family=DistributionFamily.NORMAL,
        source=UncertaintySource.CALIBRATION,
        propagation_method=PropagationMethod.NONE,
        interval_semantics=IntervalSemantics.CONFIDENCE_INTERVAL,
        distribution_payload=ParametricFitCarrier(
            family=DistributionFamily.NORMAL,
            parameters={"mean": fit_mean, "std": fit_std},
        ),
        gate_eligible=True,
        metadata={},
    )


def _heuristic_normal_env() -> UncertaintyEnvelope:
    """Build a calibration-style normal approximation that cannot gate."""
    return UncertaintyEnvelope(
        point_estimate=0.0,
        confidence_interval=(-1.96, 1.96),
        confidence_level=None,
        distribution_family=DistributionFamily.NORMAL,
        source=UncertaintySource.CALIBRATION,
        propagation_method=PropagationMethod.NONE,
        interval_semantics=IntervalSemantics.HEURISTIC_RANGE,
        is_heuristic_ci=True,
        gate_eligible=False,
        metadata={"interval_basis": "local_gaussian_hessian_approximation"},
    )


def test_covariance_reorders_columns_without_reordering_owner_rows() -> None:
    """A [b, a] column declaration must retain a's row and b's row ownership."""
    envelopes = {
        "a": _normal_env(
            0.0,
            1.0,
            metadata={"covariance_row": [0.0, 1.0], "covariance_params": ["b", "a"]},
        ),
        "b": _normal_env(
            0.0,
            3.0,
            metadata={"covariance_row": [9.0, 0.0], "covariance_params": ["b", "a"]},
        ),
    }

    covariance = build_covariance_matrix(
        ["a", "b"],
        envelopes,
        use_full_covariance=True,
        jitter=0.0,
    )

    npt.assert_allclose(np.asarray(covariance), np.diag([1.0, 9.0]), atol=1e-5)


def test_covariance_rejects_mixed_column_declarations() -> None:
    """A partial column-order declaration cannot be applied to every row."""
    envelopes = {
        "a": _normal_env(
            0.0,
            1.0,
            metadata={"covariance_row": [1.0, 0.0], "covariance_params": ["a", "b"]},
        ),
        "b": _normal_env(0.0, 1.0, metadata={"covariance_row": [0.0, 1.0]}),
    }

    with pytest.raises(ValueError, match="declared for every covariance row"):
        build_covariance_matrix(
            ["a", "b"],
            envelopes,
            use_full_covariance=True,
            jitter=0.0,
        )


def test_covariance_rejects_marginally_incompatible_matrix() -> None:
    """Spectral repair must not conceal a matrix with the wrong marginal scale."""
    envelopes = {
        "a": _normal_env(
            0.0,
            1.0,
            metadata={"covariance_row": [4.0, 0.0], "covariance_params": ["a", "b"]},
        ),
        "b": _normal_env(
            0.0,
            1.0,
            metadata={"covariance_row": [0.0, 1.0], "covariance_params": ["a", "b"]},
        ),
    }

    with pytest.raises(ValueError, match="diagonal"):
        build_covariance_matrix(
            ["a", "b"],
            envelopes,
            use_full_covariance=True,
            jitter=0.0,
        )


def test_analytical_uses_joint_covariance_for_shared_difference_and_independent_control() -> None:
    """The analytical variance is w.T @ Sigma @ w, not a sum of marginal variances."""
    shared_metadata = {
        "covariance_row": [1.0, 1.0],
        "covariance_params": ["a", "b"],
    }
    shared = {
        "a": _normal_env(0.0, 1.0, metadata=shared_metadata),
        "b": _normal_env(0.0, 1.0, metadata=shared_metadata),
    }
    config = PropagationConfig(
        preferred_method="analytical",
        delta_covariance_jitter=0.0,
    )

    shared_result = PropagationDispatcher(config).propagate(
        lambda **params: {"y": params["a"] - params["b"]},
        {"a": 0.0, "b": 0.0},
        shared,
        ["y"],
        weights={"a": 1.0, "b": -1.0},
    )[0]
    independent_result = PropagationDispatcher(config).propagate(
        lambda **params: {"y": params["a"] - params["b"]},
        {"a": 0.0, "b": 0.0},
        {"a": _normal_env(0.0, 1.0), "b": _normal_env(0.0, 1.0)},
        ["y"],
        weights={"a": 1.0, "b": -1.0},
    )[0]

    assert shared_result.method_used is PropagationMethod.ANALYTICAL
    assert shared_result.diagnostics["output_variance"] == pytest.approx(0.0, abs=1e-8)
    # JAX's float32 covariance round-trip contributes a few e-5 here.
    assert independent_result.diagnostics["output_variance"] == pytest.approx(2.0, abs=1e-3)


def test_delta_uses_joint_covariance_for_shared_difference() -> None:
    """Delta propagation must retain the same joint Gaussian law as analytical mode."""
    metadata = {"covariance_row": [1.0, 1.0], "covariance_params": ["a", "b"]}
    result = DeltaMethodPropagator(
        PropagationConfig(delta_use_full_covariance=True, delta_covariance_jitter=0.0)
    ).propagate(
        lambda **params: {"y": params["a"] - params["b"]},
        {"a": 0.0, "b": 0.0},
        {
            "a": _normal_env(0.0, 1.0, metadata=metadata),
            "b": _normal_env(0.0, 1.0, metadata=metadata),
        },
        ["y"],
    )[0]

    assert result.diagnostics["output_variance"] == pytest.approx(0.0, abs=1e-8)


def test_random_mc_preserves_shared_empirical_rows_and_axis() -> None:
    """Aligned empirical rows must be sampled jointly, preserving a=b exactly."""
    weights = (1.0, 2.0, 2.0, 1.0)
    envelopes = {
        "a": _empirical_env((-1.0, 0.0, 0.0, 1.0), weights=weights),
        "b": _empirical_env((-1.0, 0.0, 0.0, 1.0), weights=weights),
    }
    result = MonteCarloPropagator(
        PropagationConfig(
            mc_n_samples=128,
            mc_batch_size=128,
            mc_min_valid_samples=20,
            mc_seed=11,
            mc_sampling_method="random",
        )
    ).propagate(
        lambda **params: {"y": params["a"] - params["b"]},
        {"a": 0.0, "b": 0.0},
        envelopes,
        ["y"],
    )[0]

    payload = result.envelope.distribution_payload
    assert isinstance(payload, PosteriorSamplesCarrier)
    assert payload.sample_axis == "row"
    assert set(payload.samples) == {0.0}
    assert result.envelope.gate_eligible is False
    assert result.envelope.metadata["empirical_joint_id"] == "uqp-test-shared-rows"
    assert result.envelope.metadata["empirical_joint_identity_status"] == (
        "declared_non_authoritative"
    )
    assert result.diagnostics["n_failed"] == 0


def test_qmc_preserves_shared_empirical_rows_and_axis() -> None:
    """QMC inverse-CDF transforms must use one uniform row coordinate for a shared carrier."""
    samples = (-1.0, 0.0, 0.0, 1.0)
    envelopes = {
        "a": _empirical_env(samples),
        "b": _empirical_env(samples),
    }
    result = MonteCarloPropagator(
        PropagationConfig(
            mc_n_samples=128,
            mc_batch_size=128,
            mc_min_valid_samples=20,
            mc_seed=11,
            mc_sampling_method="sobol",
            mc_qmc_scramble=False,
            mc_qmc_replicates=1,
        )
    ).propagate(
        lambda **params: {"y": params["a"] - params["b"]},
        {"a": 0.0, "b": 0.0},
        envelopes,
        ["y"],
    )[0]

    payload = result.envelope.distribution_payload
    assert isinstance(payload, PosteriorSamplesCarrier)
    assert payload.sample_axis == "row"
    assert set(payload.samples) == {0.0}
    assert result.envelope.gate_eligible is False


@pytest.mark.parametrize(
    ("samples", "weights"),
    [((-1.0, 0.0, 0.0, 1.0), None), ((-1.0, 1.0), (9.0, 1.0))],
    ids=["repeated-atoms", "weighted-nine-to-one"],
)
def test_fresh_joint_results_repropagate_the_same_executed_rows(
    tmp_path, samples: tuple[float, ...], weights: tuple[float, ...] | None
) -> None:
    """A native joint pushforward can be persisted, read, and pushed forward again."""
    store = FileSystemCAS(tmp_path)
    writer = ensure_ir_artifact_store(store)
    sources = {
        "a": _empirical_env(samples, weights=weights, metadata={"param_name": "a"}),
        "b": _empirical_env(
            tuple(-sample for sample in samples), weights=weights, metadata={"param_name": "b"}
        ),
    }
    source_refs = {name: persist_uncertainty_envelope(writer, env) for name, env in sources.items()}
    assert all(ref.manifest_profile_sha256 is not None for ref in source_refs.values())
    fresh = ensure_ir_artifact_store(FileSystemCAS(tmp_path))
    admitted = {name: load_uncertainty_envelope(fresh, ref) for name, ref in source_refs.items()}
    for name, envelope in admitted.items():
        carrier = envelope.distribution_payload
        assert isinstance(carrier, PosteriorSamplesCarrier)
        assert carrier.samples == sources[name].distribution_payload.samples
        assert carrier.weights == weights
        assert carrier.sample_axis == "row"

    config = PropagationConfig(
        mc_n_samples=128,
        mc_batch_size=128,
        mc_min_valid_samples=20,
        mc_seed=11,
        mc_sampling_method="random",
        compute_sensitivity=False,
    )
    propagator = MonteCarloPropagator(config)
    attempted: list[tuple[float, float]] = []

    def project(a: float, b: float) -> dict[str, float]:
        attempted.append((float(a), float(b)))
        return {"left": a, "right": -b}

    wrong_b = admitted["b"].model_copy(
        update={
            "distribution_payload": admitted["b"].distribution_payload.model_copy(
                update={"sample_axis": "different-rows"}
            )
        }
    )
    refused = propagator.propagate(
        project, {"a": 0.0, "b": 0.0}, {"a": admitted["a"], "b": wrong_b}, ["left"]
    )[0]
    assert refused.envelope.metadata["failure"] == "incompatible_joint_law"
    assert refused.envelope.gate_eligible is False
    assert attempted == []

    first = propagator.propagate(project, {"a": 0.0, "b": 0.0}, admitted, ["left", "right"])
    assert len(first) == 2
    lineage = [
        InputRef(
            artifact_id=ref.artifact_id,
            role=f"input_envelope.{name}",
            manifest_profile_sha256=ref.manifest_profile_sha256,
        )
        for name, ref in source_refs.items()
    ]
    output_refs = {
        result.metric_id: persist_uncertainty_envelope(writer, result.envelope, inputs=lineage)
        for result in first
    }
    fresh_outputs = {
        name: load_uncertainty_envelope(fresh, ref) for name, ref in output_refs.items()
    }
    for name, envelope in fresh_outputs.items():
        carrier = envelope.distribution_payload
        assert isinstance(carrier, PosteriorSamplesCarrier)
        assert carrier.sample_axis == "row"
        assert carrier.weights is None  # Draw rows are already resampled, not reweighted again.
        assert set(carrier.samples) <= set(samples)
        assert envelope.gate_eligible is False
        assert envelope.metadata["empirical_joint_identity_status"] == "declared_non_authoritative"
        manifest = FileSystemCAS(tmp_path).get_manifest(output_refs[name])
        assert {
            (edge.role, str(edge.artifact_id), edge.manifest_profile_sha256)
            for edge in manifest.inputs
        } == {(edge.role, str(edge.artifact_id), edge.manifest_profile_sha256) for edge in lineage}
    left = fresh_outputs["left"].distribution_payload
    right = fresh_outputs["right"].distribution_payload
    assert isinstance(left, PosteriorSamplesCarrier)
    assert isinstance(right, PosteriorSamplesCarrier)
    assert left.samples == right.samples
    output_id = fresh_outputs["left"].metadata.get("joint_sample_id")
    assert isinstance(output_id, str) and output_id
    assert output_id != "uqp-test-shared-rows"
    assert fresh_outputs["right"].metadata.get("joint_sample_id") == output_id
    assert all(result.envelope.metadata.get("joint_sample_id") == output_id for result in first)
    if weights is not None:
        assert left.samples.count(-1.0) > 0.75 * len(left.samples)

    selected = output_refs["left"]
    wrong_profile = selected.model_copy(update={"manifest_profile_sha256": "sha256:" + "0" * 64})
    with pytest.raises(CanonViolation, match="ir_owned_artifact_read_refused"):
        load_uncertainty_envelope(fresh, wrong_profile)

    second = MonteCarloPropagator(
        PropagationConfig(
            mc_n_samples=128,
            mc_batch_size=128,
            mc_min_valid_samples=20,
            mc_seed=11,
            mc_sampling_method="sobol",
            mc_qmc_scramble=False,
            mc_qmc_replicates=1,
            compute_sensitivity=False,
        )
    ).propagate(
        lambda left, right: {"copy": left, "difference": left - right},
        {"left": 0.0, "right": 0.0},
        fresh_outputs,
        ["copy", "difference"],
    )
    copy, second = second
    assert second.envelope.distribution_family is DistributionFamily.BOOTSTRAP, (
        second.envelope.metadata
    )
    second_rows = second.envelope.distribution_payload
    copied_rows = copy.envelope.distribution_payload
    assert isinstance(second_rows, PosteriorSamplesCarrier)
    assert isinstance(copied_rows, PosteriorSamplesCarrier)
    assert Counter(copied_rows.samples) == Counter(left.samples)
    assert set(second_rows.samples) == {0.0}
    assert second_rows.sample_axis == "row"
    assert second.envelope.gate_eligible is False
    assert second.envelope.metadata.get("effective_information_count") is None


def test_distinct_equal_length_output_masks_do_not_form_joint_rows() -> None:
    """Identical row counts do not align successful outputs from different draws."""
    sources = {
        "a": _empirical_env((-1.0, 1.0)),
        "b": _empirical_env((1.0, -1.0)),
    }
    calls = 0

    def different_masks(a: float, b: float) -> dict[str, float | None]:
        nonlocal calls
        calls += 1
        if calls % 2:
            return {"left": a, "right": None}
        return {"left": None, "right": -b}

    propagator = MonteCarloPropagator(
        PropagationConfig(
            mc_n_samples=128,
            mc_batch_size=128,
            mc_min_valid_samples=20,
            mc_seed=11,
            compute_sensitivity=False,
        )
    )
    first = propagator.propagate(different_masks, {"a": 0.0, "b": 0.0}, sources, ["left", "right"])
    assert len(first) == 2
    envelopes = {result.metric_id: result.envelope for result in first}
    assert envelopes["left"].sample_size == envelopes["right"].sample_size == 64
    assert all(envelope.gate_eligible is False for envelope in envelopes.values())
    assert (
        envelopes["left"].metadata["joint_sample_id"]
        != (envelopes["right"].metadata["joint_sample_id"])
    )

    evaluated: list[bool] = []

    def forbidden(left: float, right: float) -> dict[str, float]:
        evaluated.append(True)
        return {"difference": left - right}

    refusal = propagator.propagate(
        forbidden, {"left": 0.0, "right": 0.0}, envelopes, ["difference"]
    )[0]
    assert refusal.envelope.metadata["failure"] == "incompatible_joint_law"
    assert refusal.envelope.gate_eligible is False
    assert evaluated == []


def test_float32_overflow_uses_the_actual_emitted_row_mask() -> None:
    """Finite float64 values may overflow at different emitted float32 positions."""
    sources = {"x": _empirical_env((-1.0, 1.0), joint_id=None)}
    calls = 0

    def overflow_different_rows(x: float) -> dict[str, float]:
        nonlocal calls
        calls += 1
        if calls % 2:
            return {"left": x, "right": 1e40}
        return {"left": 1e40, "right": x}

    propagator = MonteCarloPropagator(
        PropagationConfig(
            mc_n_samples=128,
            mc_batch_size=128,
            mc_min_valid_samples=20,
            mc_seed=11,
            compute_sensitivity=False,
        )
    )
    first = propagator.propagate(overflow_different_rows, {"x": 0.0}, sources, ["left", "right"])
    envelopes = {result.metric_id: result.envelope for result in first}
    assert envelopes["left"].sample_size == envelopes["right"].sample_size == 64
    assert (
        envelopes["left"].metadata["joint_sample_id"]
        != (envelopes["right"].metadata["joint_sample_id"])
    )
    called: list[bool] = []

    def forbidden(left: float, right: float) -> dict[str, float]:
        called.append(True)
        return {"difference": left - right}

    refusal = propagator.propagate(
        forbidden, {"left": 0.0, "right": 0.0}, envelopes, ["difference"]
    )[0]
    assert refusal.envelope.metadata["failure"] == "incompatible_joint_law"
    assert refusal.envelope.gate_eligible is False
    assert called == []
    # Float32 projection loss must remain a failed draw, not a gate-eligible success.
    assert all(result.envelope.gate_eligible is False for result in first)
    assert all(result.diagnostics["output_coverage_complete"] is False for result in first)
    ledger = first[0].diagnostics["draw_outcome_provenance"]
    assert ledger["schema_version"] == "1.2"
    assert ledger["output_numeric_profile"] == "float32_finite_support_v1"
    assert ledger["successful_draw_count"] == 0
    assert len(ledger["failure_records"]) == 128
    outcomes = [
        entry for record in ledger["failure_records"] for entry in record["output_outcomes"]
    ]
    assert len(outcomes) == 128
    assert {entry["outcome_code"] for entry in outcomes} == {"non_finite_output"}
    assert {entry["error_type"] for entry in outcomes} == {"float32_projection_overflow"}


@pytest.mark.parametrize(("small", "lost"), [(1e-50, True), (0.0, False)])
def test_nonzero_output_underflow_does_not_become_an_authoritative_zero(
    small: float, lost: bool
) -> None:
    """Keep exact zero valid, and withhold a lost nonzero without hiding its sibling."""
    source = _empirical_env((-1.0, 1.0), joint_id=None)
    result = MonteCarloPropagator(
        PropagationConfig(
            mc_n_samples=128,
            mc_batch_size=128,
            mc_min_valid_samples=20,
            mc_seed=11,
            compute_sensitivity=False,
        )
    ).propagate(
        lambda x: {"value": small if x < 0.0 else 1.0, "sibling": 2.0},
        {"x": 0.0},
        {"x": source},
        ["value", "sibling"],
    )
    value, sibling = result
    carrier = value.envelope.distribution_payload
    assert isinstance(carrier, PosteriorSamplesCarrier)
    ledger = value.diagnostics["draw_outcome_provenance"]
    if lost:
        assert 20 <= value.envelope.sample_size < 128
        assert set(carrier.samples) == {1.0}
        assert value.envelope.gate_eligible is False
        assert value.diagnostics["output_coverage_complete"] is False
        assert ledger["schema_version"] == "1.2"
        assert ledger["output_numeric_profile"] == "float32_finite_support_v1"
        assert ledger["successful_draw_count"] == value.envelope.sample_size
        assert {
            outcome["error_type"]
            for record in ledger["failure_records"]
            for outcome in record["output_outcomes"]
        } == {"float32_projection_underflow"}
    else:
        assert value.envelope.sample_size == 128
        assert set(carrier.samples) == {0.0, 1.0}
        assert value.envelope.gate_eligible is True
        assert ledger["schema_version"] == "1.0"
        assert ledger["failure_records"] == []
    assert sibling.envelope.sample_size == 128
    assert sibling.envelope.gate_eligible is True


@pytest.mark.parametrize("small", [1e-14, 1e-40])
def test_representable_small_output_is_not_erased_by_envelope_rounding(small: float) -> None:
    """An admitted nonzero float32 atom remains visible in the output carrier."""
    result = MonteCarloPropagator(
        PropagationConfig(
            mc_n_samples=128,
            mc_batch_size=128,
            mc_min_valid_samples=20,
            mc_seed=11,
            compute_sensitivity=False,
        )
    ).propagate(
        lambda x: {"value": small if x < 0.0 else 1.0},
        {"x": 0.0},
        {"x": _empirical_env((-1.0, 1.0), joint_id=None)},
        ["value"],
    )[0]
    carrier = result.envelope.distribution_payload
    assert isinstance(carrier, PosteriorSamplesCarrier)
    assert float(np.float32(small)) in carrier.samples


@pytest.mark.parametrize("small", [1e-14, 1e-40])
def test_representable_constant_output_keeps_nonzero_summary(small: float) -> None:
    """Output summary and persisted rows describe the same finite point mass."""
    result = MonteCarloPropagator(
        PropagationConfig(
            mc_n_samples=128,
            mc_batch_size=128,
            mc_min_valid_samples=20,
            mc_seed=11,
            compute_sensitivity=False,
        )
    ).propagate(
        lambda x: {"value": small},
        {"x": 0.0},
        {"x": _empirical_env((-1.0, 1.0), joint_id=None)},
        ["value"],
    )[0]
    carrier = result.envelope.distribution_payload
    assert isinstance(carrier, PosteriorSamplesCarrier)
    expected = float(np.float32(small))
    assert result.envelope.point_estimate == expected
    assert result.envelope.confidence_interval == (expected, expected)
    assert set(carrier.samples) == {expected}


def test_adjacent_float32_atoms_do_not_collapse_during_envelope_creation() -> None:
    """The default decimal profile must not merge distinct represented atoms."""
    lower = float(np.float32(2e-6))
    upper = float(np.nextafter(np.float32(2e-6), np.float32(np.inf)))
    assert lower != upper and round(lower, 12) == round(upper, 12)
    result = MonteCarloPropagator(
        PropagationConfig(
            mc_n_samples=128,
            mc_batch_size=128,
            mc_min_valid_samples=20,
            mc_seed=11,
            compute_sensitivity=False,
        )
    ).propagate(
        lambda x: {"value": lower if x < 0.0 else upper},
        {"x": 0.0},
        {"x": _empirical_env((-1.0, 1.0), joint_id=None)},
        ["value"],
    )[0]
    carrier = result.envelope.distribution_payload
    assert isinstance(carrier, PosteriorSamplesCarrier)
    assert set(carrier.samples) == {lower, upper}
    assert result.envelope.numeric_policy.mode.value == "decimal_exact"


@pytest.mark.parametrize("magnitude", [1e-20, 1e20])
def test_representable_float32_rows_keep_a_finite_nonzero_scale(magnitude: float) -> None:
    """A float32 reduction must not erase or overflow a representable scale."""
    result = MonteCarloPropagator(
        PropagationConfig(
            mc_n_samples=128,
            mc_batch_size=128,
            mc_min_valid_samples=20,
            mc_seed=11,
            compute_sensitivity=False,
        )
    ).propagate(
        lambda x: {"value": magnitude * x},
        {"x": 0.0},
        {"x": _empirical_env((-1.0, 1.0), joint_id=None)},
        ["value"],
    )[0]
    carrier = result.envelope.distribution_payload
    assert isinstance(carrier, PosteriorSamplesCarrier)
    reference = float(np.std(np.asarray(carrier.samples, dtype=np.float64)))
    assert reference > 0.0
    assert result.envelope.metadata["mc_std"] == pytest.approx(reference, rel=1e-6, abs=0)


def test_large_representable_constant_does_not_overflow_its_mean() -> None:
    """A finite constant point mass cannot become infinite during reduction."""
    value = float(np.float32(3e38))
    result = MonteCarloPropagator(
        PropagationConfig(
            mc_n_samples=128,
            mc_batch_size=128,
            mc_min_valid_samples=20,
            mc_seed=11,
            compute_sensitivity=False,
        )
    ).propagate(
        lambda x: {"value": value},
        {"x": 0.0},
        {"x": _empirical_env((-1.0, 1.0), joint_id=None)},
        ["value"],
    )[0]
    carrier = result.envelope.distribution_payload
    assert isinstance(carrier, PosteriorSamplesCarrier)
    assert result.envelope.point_estimate == value
    assert set(carrier.samples) == {value}
    assert result.envelope.metadata["mc_std"] == 0.0


def test_outputs_from_different_sampled_corpora_do_not_share_joint_rows() -> None:
    """Same axes and draw counts cannot join outputs from different executions."""
    sources = {
        "a": _empirical_env((-1.0, 0.0, 0.0, 1.0)),
        "b": _empirical_env((1.0, 0.0, 0.0, -1.0)),
    }

    def run(seed: int):
        return MonteCarloPropagator(
            PropagationConfig(
                mc_n_samples=128,
                mc_batch_size=128,
                mc_min_valid_samples=20,
                mc_seed=seed,
                compute_sensitivity=False,
            )
        ).propagate(
            lambda a, b: {"left": a, "right": -b},
            {"a": 0.0, "b": 0.0},
            sources,
            ["left", "right"],
        )

    first, second = run(11), run(12)
    left, right = first[0].envelope, second[1].envelope
    left_rows, right_rows = left.distribution_payload, right.distribution_payload
    assert isinstance(left_rows, PosteriorSamplesCarrier)
    assert isinstance(right_rows, PosteriorSamplesCarrier)
    assert left_rows.sample_axis == right_rows.sample_axis == "row"
    assert len(left_rows.samples) == len(right_rows.samples) == 128
    assert left_rows.samples != right_rows.samples
    assert left.metadata["joint_sample_id"] != right.metadata["joint_sample_id"]

    evaluated: list[bool] = []

    def forbidden(left: float, right: float) -> dict[str, float]:
        evaluated.append(True)
        return {"difference": left - right}

    refusal = MonteCarloPropagator(
        PropagationConfig(mc_n_samples=128, mc_batch_size=128, mc_min_valid_samples=20)
    ).propagate(
        forbidden, {"left": 0.0, "right": 0.0}, {"left": left, "right": right}, ["difference"]
    )[0]
    assert refusal.envelope.metadata["failure"] == "incompatible_joint_law"
    assert refusal.envelope.gate_eligible is False
    assert evaluated == []


def test_same_inputs_and_seed_but_different_emitted_rows_do_not_join() -> None:
    """An unbound callback cannot turn a matching sampling recipe into row identity."""
    sources = {"x": _empirical_env((-1.0, 0.0, 1.0), joint_id=None)}
    propagator = MonteCarloPropagator(
        PropagationConfig(
            mc_n_samples=128,
            mc_batch_size=128,
            mc_min_valid_samples=20,
            mc_seed=11,
            compute_sensitivity=False,
        )
    )
    same = propagator.propagate(
        lambda x: {"left": x, "right": x}, {"x": 0.0}, sources, ["left", "right"]
    )
    changed = propagator.propagate(
        lambda x: {"left": x, "right": -x}, {"x": 0.0}, sources, ["left", "right"]
    )
    left, right = same[0].envelope, changed[1].envelope
    assert left.metadata["joint_sample_id"] != right.metadata["joint_sample_id"]
    calls: list[bool] = []

    def forbidden(left: float, right: float) -> dict[str, float]:
        calls.append(True)
        return {"difference": left - right}

    refusal = propagator.propagate(
        forbidden, {"left": 0.0, "right": 0.0}, {"left": left, "right": right}, ["difference"]
    )[0]
    assert refusal.envelope.metadata["failure"] == "incompatible_joint_law"
    assert refusal.envelope.gate_eligible is False
    assert calls == []


def test_matching_conditional_masks_remain_candidate_only_on_repropagation() -> None:
    """Matching surviving rows can be reused without promoting conditional results."""
    sources = {"x": _empirical_env((-1.0, 1.0), joint_id=None)}
    propagator = MonteCarloPropagator(
        PropagationConfig(
            mc_n_samples=128,
            mc_batch_size=128,
            mc_min_valid_samples=20,
            mc_seed=11,
            compute_sensitivity=False,
        )
    )
    calls = 0

    def conditional(x: float) -> dict[str, float | None]:
        nonlocal calls
        calls += 1
        if calls % 2:
            return {"left": x, "right": x}
        return {"left": None, "right": None}

    first = propagator.propagate(conditional, {"x": 0.0}, sources, ["left", "right"])
    envelopes = {result.metric_id: result.envelope for result in first}
    assert all(envelope.sample_size == 64 for envelope in envelopes.values())
    assert all(envelope.gate_eligible is False for envelope in envelopes.values())
    assert all(
        envelope.metadata["distribution_sample_semantics"]
        == "successful_draws_only_conditional_on_execution"
        for envelope in envelopes.values()
    )
    assert (
        envelopes["left"].metadata["joint_sample_id"]
        == (envelopes["right"].metadata["joint_sample_id"])
    )
    second = propagator.propagate(
        lambda left, right: {"difference": left - right},
        {"left": 0.0, "right": 0.0},
        envelopes,
        ["difference"],
    )[0]
    assert second.envelope.distribution_family is DistributionFamily.BOOTSTRAP
    assert second.envelope.gate_eligible is False
    second_rows = second.envelope.distribution_payload
    assert isinstance(second_rows, PosteriorSamplesCarrier)
    assert set(second_rows.samples) == {0.0}


def test_random_mc_uses_weighted_empirical_atoms_instead_of_ci_normal() -> None:
    """Random sampling must consume source particle masses and preserve atoms."""
    result = MonteCarloPropagator(
        PropagationConfig(
            mc_n_samples=256,
            mc_batch_size=256,
            mc_min_valid_samples=20,
            mc_seed=11,
            mc_sampling_method="random",
        )
    ).propagate(
        lambda **params: {"y": params["a"]},
        {"a": 0.0},
        {"a": _empirical_env((-1.0, 1.0), weights=(9.0, 1.0))},
        ["y"],
    )[0]

    payload = result.envelope.distribution_payload
    assert isinstance(payload, PosteriorSamplesCarrier)
    assert set(payload.samples) <= {-1.0, 1.0}
    assert payload.samples.count(-1.0) > 0.75 * len(payload.samples)


def test_qmc_uses_weighted_empirical_atoms_instead_of_ci_normal() -> None:
    """QMC must apply the weighted inverse CDF to empirical source atoms."""
    result = MonteCarloPropagator(
        PropagationConfig(
            mc_n_samples=128,
            mc_batch_size=128,
            mc_min_valid_samples=20,
            mc_seed=11,
            mc_sampling_method="sobol",
            mc_qmc_scramble=False,
            mc_qmc_replicates=1,
        )
    ).propagate(
        lambda **params: {"y": params["a"]},
        {"a": 0.0},
        {"a": _empirical_env((-1.0, 1.0), weights=(9.0, 1.0))},
        ["y"],
    )[0]

    payload = result.envelope.distribution_payload
    assert isinstance(payload, PosteriorSamplesCarrier)
    assert set(payload.samples) <= {-1.0, 1.0}
    assert payload.samples.count(-1.0) > 0.75 * len(payload.samples)


def test_incompatible_empirical_axes_are_not_sampled_as_independent() -> None:
    """Mismatched empirical axes must become a typed limitation, not a fake joint law."""
    envelopes = {
        "a": _empirical_env((-1.0, 0.0, 0.0, 1.0), sample_axis="row-a"),
        "b": _empirical_env((-1.0, 0.0, 0.0, 1.0), sample_axis="row-b"),
    }
    result = (
        MonteCarloPropagator(
            PropagationConfig(mc_n_samples=128, mc_batch_size=128, mc_min_valid_samples=20)
        )
        .propagate(
            lambda **params: {"y": params["a"] - params["b"]},
            {"a": 0.0, "b": 0.0},
            envelopes,
            ["y"],
        )[0]
        .envelope
    )

    assert result.distribution_family is DistributionFamily.UNKNOWN
    assert result.gate_eligible is False
    assert result.metadata["failure"] == "incompatible_joint_law"


def test_same_empirical_axis_with_different_weights_is_not_a_joint_law() -> None:
    """Equal labels do not establish a shared law when source masses differ."""
    envelopes = {
        "a": _empirical_env((-1.0, 0.0, 0.0, 1.0), weights=(1.0, 1.0, 1.0, 1.0)),
        "b": _empirical_env((-1.0, 0.0, 0.0, 1.0), weights=(1.0, 2.0, 1.0, 1.0)),
    }
    result = (
        MonteCarloPropagator(
            PropagationConfig(mc_n_samples=128, mc_batch_size=128, mc_min_valid_samples=20)
        )
        .propagate(
            lambda **params: {"y": params["a"] - params["b"]},
            {"a": 0.0, "b": 0.0},
            envelopes,
            ["y"],
        )[0]
        .envelope
    )

    assert result.distribution_family is DistributionFamily.UNKNOWN
    assert result.gate_eligible is False
    assert result.metadata["failure"] == "incompatible_joint_law"


def test_same_empirical_axis_with_different_lengths_is_not_a_joint_law() -> None:
    """Equal labels do not establish row alignment when lengths differ."""
    envelopes = {
        "a": _empirical_env((-1.0, 0.0, 0.0, 1.0)),
        "b": _empirical_env((-1.0, 0.0)),
    }
    result = (
        MonteCarloPropagator(
            PropagationConfig(mc_n_samples=128, mc_batch_size=128, mc_min_valid_samples=20)
        )
        .propagate(
            lambda **params: {"y": params["a"] - params["b"]},
            {"a": 0.0, "b": 0.0},
            envelopes,
            ["y"],
        )[0]
        .envelope
    )

    assert result.distribution_family is DistributionFamily.UNKNOWN
    assert result.gate_eligible is False
    assert result.metadata["failure"] == "incompatible_joint_law"


def test_mixed_empirical_and_parametric_inputs_are_not_assumed_independent() -> None:
    """A carrier plus a non-carrier needs an explicit joint-law producer."""
    envelopes = {
        "a": _empirical_env((-1.0, 0.0, 1.0)),
        "b": _normal_env(0.0, 1.0),
    }
    result = (
        MonteCarloPropagator(
            PropagationConfig(mc_n_samples=128, mc_batch_size=128, mc_min_valid_samples=20)
        )
        .propagate(
            lambda **params: {"y": params["a"] - params["b"]},
            {"a": 0.0, "b": 0.0},
            envelopes,
            ["y"],
        )[0]
        .envelope
    )

    assert result.distribution_family is DistributionFamily.UNKNOWN
    assert result.gate_eligible is False
    assert result.metadata["failure"] == "incompatible_joint_law"


def test_default_empirical_draws_without_shared_identity_are_not_coupled() -> None:
    """Matching free-form axes cannot establish a shared row identity by themselves."""
    envelopes = {
        "a": _empirical_env((-1.0, 0.0, 1.0), joint_id=None),
        "b": _empirical_env((-1.0, 0.0, 1.0), joint_id=None),
    }
    result = (
        MonteCarloPropagator(
            PropagationConfig(mc_n_samples=128, mc_batch_size=128, mc_min_valid_samples=20)
        )
        .propagate(
            lambda **params: {"y": params["a"] - params["b"]},
            {"a": 0.0, "b": 0.0},
            envelopes,
            ["y"],
        )[0]
        .envelope
    )

    assert result.distribution_family is DistributionFamily.UNKNOWN
    assert result.gate_eligible is False
    assert result.metadata["failure"] == "unestablished_joint_law"


def test_unknown_dependency_does_not_fall_back_to_independent_normal() -> None:
    """An explicit unknown dependency must fail closed in every backend."""
    envelopes = {
        "a": _normal_env(0.0, 1.0, metadata={"dependency": "unknown"}),
        "b": _normal_env(0.0, 1.0, metadata={"dependency": "unknown"}),
    }
    calls: list[dict[str, float]] = []

    def simulation(**params: float) -> dict[str, float]:
        calls.append(params)
        return {"y": params["a"] - params["b"]}

    result = (
        PropagationDispatcher(PropagationConfig(preferred_method="analytical"))
        .propagate(
            simulation,
            {"a": 0.0, "b": 0.0},
            envelopes,
            ["y"],
            weights={"a": 1.0, "b": -1.0},
        )[0]
        .envelope
    )

    assert result.distribution_family is DistributionFamily.UNKNOWN
    assert result.gate_eligible is False
    assert result.metadata["failure"] == "unknown_dependency"
    assert calls == []


def test_random_mc_uses_normal_parametric_fit_payload() -> None:
    """Random sampling must consume a typed normal fit, not reconstruct CI moments."""
    result = MonteCarloPropagator(
        PropagationConfig(
            mc_n_samples=128,
            mc_batch_size=128,
            mc_min_valid_samples=20,
            mc_seed=11,
            mc_sampling_method="random",
        )
    ).propagate(
        lambda **params: {"y": params["a"]},
        {"a": 0.0},
        {"a": _parametric_normal_env()},
        ["y"],
    )[0]

    payload = result.envelope.distribution_payload
    assert isinstance(payload, PosteriorSamplesCarrier)
    assert result.envelope.point_estimate == pytest.approx(42.0, abs=0.2)
    assert all(40.0 < sample < 44.0 for sample in payload.samples)
    assert result.envelope.metadata["parametric_fit_payload_used"] is True


def test_qmc_uses_normal_parametric_fit_payload() -> None:
    """QMC inverse CDF must consume typed fit parameters instead of the envelope CI."""
    result = MonteCarloPropagator(
        PropagationConfig(
            mc_n_samples=128,
            mc_batch_size=128,
            mc_min_valid_samples=20,
            mc_seed=11,
            mc_sampling_method="sobol",
            mc_qmc_scramble=False,
            mc_qmc_replicates=1,
        )
    ).propagate(
        lambda **params: {"y": params["a"]},
        {"a": 0.0},
        {"a": _parametric_normal_env()},
        ["y"],
    )[0]

    payload = result.envelope.distribution_payload
    assert isinstance(payload, PosteriorSamplesCarrier)
    assert result.envelope.point_estimate == pytest.approx(42.0, abs=0.2)
    assert all(40.0 < sample < 44.0 for sample in payload.samples)
    assert result.envelope.metadata["parametric_fit_payload_used"] is True


def test_non_gate_input_stays_non_gate_through_all_propagators() -> None:
    """Propagation cannot promote a heuristic calibration input into a gate."""
    input_envelopes = {"a": _heuristic_normal_env()}

    def simulation(**params: float) -> dict[str, float]:
        return {"y": params["a"]}

    analytical = AnalyticalPropagator.propagate_linear_combination(
        weights={"a": 1.0},
        input_envelopes=input_envelopes,
        output_metric_id="y",
    )
    delta = DeltaMethodPropagator(PropagationConfig(delta_use_full_covariance=True)).propagate(
        simulation,
        {"a": 0.0},
        input_envelopes,
        ["y"],
    )[0]
    monte_carlo = MonteCarloPropagator(
        PropagationConfig(
            mc_n_samples=100,
            mc_batch_size=10,
            mc_min_valid_samples=10,
            mc_seed=11,
        )
    ).propagate(
        simulation,
        {"a": 0.0},
        input_envelopes,
        ["y"],
    )[0]

    assert analytical.envelope.gate_eligible is False
    assert delta.envelope.gate_eligible is False
    assert monte_carlo.envelope.gate_eligible is False
