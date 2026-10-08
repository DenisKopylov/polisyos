"""Separate conditional mean-estimator error from sampled outcome dispersion."""

from __future__ import annotations

from fractions import Fraction
from pathlib import Path

import pytest

from polisyos.core.artifacts.ir_adapter import build_ir_artifact_store
from polisyos.foundry.uncertainty.config import AdaptiveStoppingConfig, PropagationConfig
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


def _normal_law() -> UncertaintyEnvelope:
    return UncertaintyEnvelope(
        point_estimate=0.0,
        confidence_interval=(-2.0, 2.0),
        distribution_family=DistributionFamily.NORMAL,
        source=UncertaintySource.CALIBRATION,
        propagation_method=PropagationMethod.NONE,
        interval_semantics=IntervalSemantics.CONFIDENCE_INTERVAL,
        distribution_payload=ParametricFitCarrier(
            family=DistributionFamily.NORMAL,
            parameters={"mean": 0.0, "std": 1.0},
        ),
        gate_eligible=False,
    )


def _propagate(config: PropagationConfig, env: UncertaintyEnvelope | None = None):
    return MonteCarloPropagator(config).propagate(
        lambda x=0.0: {"y": -1.0 if x < 0 else 1.0},
        {"x": 0.0},
        {"x": _normal_law() if env is None else env},
        ["y"],
    )[0]


def _fraction_sem_squared(samples: tuple[float, ...]) -> Fraction:
    vals = [Fraction.from_float(x) for x in samples]
    mean = sum(vals) / len(vals)
    return sum((x - mean) ** 2 for x in vals) / (len(vals) * (len(vals) - 1))


def test_actual_iid_mean_error_matches_independent_fraction_after_fresh_cas_reader(
    tmp_path: Path,
) -> None:
    result = _propagate(PropagationConfig(mc_n_samples=100, mc_seed=27))
    store = build_ir_artifact_store(tmp_path / "cas")
    ref = persist_uncertainty_envelope(store, result.envelope)
    fresh = load_uncertainty_envelope(build_ir_artifact_store(tmp_path / "cas"), ref)
    assert isinstance(fresh.distribution_payload, PosteriorSamplesCarrier)
    samples = fresh.distribution_payload.samples
    expected = float(_fraction_sem_squared(samples)) ** 0.5
    diagnostic = fresh.metadata["mean_estimator_error"]
    assert diagnostic == result.diagnostics["mean_estimator_error"]
    assert diagnostic["status"] == "conditional_estimate"
    assert diagnostic["standard_error"] == pytest.approx(expected, rel=1e-12)
    assert diagnostic["requested_draw_count"] == diagnostic["attempted_draw_count"] == 100
    assert diagnostic["finite_output_count"] == 100
    assert diagnostic["target"] == "implemented_push_forward_mean"
    assert diagnostic["assumptions_verified"] is False
    assert diagnostic["gate_eligible"] is False
    assert fresh.gate_eligible is False
    assert diagnostic["standard_error"] < fresh.metadata["mc_std"] / 5
    assert fresh.confidence_interval == (-1.0, 1.0)
    assert diagnostic["seed"] == 27
    assert diagnostic["input_envelope_sha256"]["x"]


@pytest.mark.parametrize("method,scrambled,replicas", [("sobol", False, 1), ("sobol", True, 2)])
def test_qmc_rows_do_not_become_iid_mean_error(method, scrambled, replicas) -> None:
    result = _propagate(
        PropagationConfig(
            mc_n_samples=100,
            mc_sampling_method=method,
            mc_qmc_scramble=scrambled,
            mc_qmc_replicates=replicas,
        )
    )
    diagnostic = result.envelope.metadata["mean_estimator_error"]
    assert diagnostic["status"] == "unavailable"
    assert diagnostic["standard_error"] is None
    assert diagnostic["reason"] == "qmc_replica_means_not_retained"
    assert result.diagnostics["n_samples"] == 100


def test_legacy_inferred_normal_law_does_not_claim_regular_iid_support() -> None:
    env = _normal_law().model_copy(update={"distribution_payload": None})
    result = _propagate(PropagationConfig(mc_n_samples=100), env)
    assert result.envelope.metadata["mean_estimator_error"]["reason"] == (
        "unsupported_input_sampling_law"
    )
    assert result.envelope.metadata["mean_estimator_error"]["standard_error"] is None


def test_weighted_empirical_draw_axis_and_iid_marker_do_not_launder_profile() -> None:
    env = _normal_law().model_copy(
        update={
            "distribution_family": DistributionFamily.BOOTSTRAP,
            "distribution_payload": PosteriorSamplesCarrier(
                samples=(-1.0, 1.0),
                weights=(0.9, 0.1),
                sample_axis="draw",
            ),
            "metadata": {"iid": True, "sampling_law": "independent_normal"},
        }
    )
    result = _propagate(PropagationConfig(mc_n_samples=100), env)
    diagnostic = result.envelope.metadata["mean_estimator_error"]
    assert diagnostic["status"] == "unavailable"
    assert diagnostic["standard_error"] is None
    assert diagnostic["reason"] == "unsupported_input_sampling_law"


def test_adaptive_sampling_does_not_use_fixed_iid_formula() -> None:
    result = _propagate(
        PropagationConfig(
            adaptive_stopping=AdaptiveStoppingConfig(
                enabled=True,
                min_samples=100,
                max_samples=200,
                check_interval=100,
                ci_half_width_target=10.0,
            )
        )
    )
    assert result.envelope.metadata["mean_estimator_error"]["reason"] == "adaptive_sampling"
    assert result.envelope.metadata["mean_estimator_error"]["standard_error"] is None


def test_actual_one_success_out_of_full_attempts_has_unavailable_error_after_cas(
    tmp_path: Path,
) -> None:
    calls = 0

    def one_success(x=0.0):
        nonlocal calls
        calls += 1
        # First call is nominal replay; the next is the sole successful sampled output.
        return {"y": 1.0 if calls <= 2 else float("nan")}

    result = MonteCarloPropagator(PropagationConfig(mc_n_samples=100)).propagate(
        one_success, {"x": 0.0}, {"x": _normal_law()}, ["y"]
    )[0]
    ref = persist_uncertainty_envelope(build_ir_artifact_store(tmp_path / "cas"), result.envelope)
    fresh = load_uncertainty_envelope(build_ir_artifact_store(tmp_path / "cas"), ref)
    diagnostic = fresh.metadata["mean_estimator_error"]
    assert diagnostic["finite_output_count"] == 1
    assert diagnostic["requested_draw_count"] == diagnostic["attempted_draw_count"] == 100
    assert diagnostic["status"] == "unavailable"
    assert diagnostic["reason"] == "insufficient_independent_draws"
    assert diagnostic["standard_error"] is None
    assert fresh.gate_eligible is False
    assert result.diagnostics["n_failed"] == 99


def test_incomplete_outputs_never_renormalize_to_complete_iid_sample() -> None:
    def partial(x=0.0):
        return {"y": x if x >= 0 else float("nan")}

    result = MonteCarloPropagator(PropagationConfig(mc_n_samples=100)).propagate(
        partial, {"x": 0.0}, {"x": _normal_law()}, ["y"]
    )[0]
    diagnostic = result.envelope.metadata["mean_estimator_error"]
    assert 2 <= diagnostic["finite_output_count"] < diagnostic["attempted_draw_count"]
    assert diagnostic["reason"] == "incomplete_draw_denominator"
    assert diagnostic["standard_error"] is None
    assert result.envelope.gate_eligible is False


def test_unknown_dependency_refuses_before_draws_and_withholds_mean_error() -> None:
    env = _normal_law().model_copy(update={"metadata": {"dependence": "unknown"}})
    result = _propagate(PropagationConfig(mc_n_samples=100), env)
    diagnostic = result.envelope.metadata["mean_estimator_error"]
    assert diagnostic["status"] == "unavailable"
    assert diagnostic["reason"] == "unknown_dependency"
    assert diagnostic["standard_error"] is None
    assert diagnostic["attempted_draw_count"] == 0
    assert result.envelope.gate_eligible is False


def test_fake_mean_error_metadata_does_not_replace_actual_output_arithmetic() -> None:
    env = _normal_law().model_copy(
        update={
            "metadata": {"mean_estimator_error": {"standard_error": 999.0, "status": "admitted"}}
        }
    )
    result = _propagate(PropagationConfig(mc_n_samples=100), env)
    diagnostic = result.envelope.metadata["mean_estimator_error"]
    samples = result.envelope.distribution_payload.samples
    assert diagnostic["standard_error"] == pytest.approx(
        float(_fraction_sem_squared(samples)) ** 0.5
    )
    assert diagnostic["status"] == "conditional_estimate"
    assert diagnostic["assumptions_verified"] is False
    assert diagnostic["gate_eligible"] is False


def test_fixed_constant_response_has_zero_conditional_error_without_authority() -> None:
    result = MonteCarloPropagator(PropagationConfig(mc_n_samples=100)).propagate(
        lambda x=0.0: {"y": 7.0}, {"x": 0.0}, {"x": _normal_law()}, ["y"]
    )[0]
    diagnostic = result.envelope.metadata["mean_estimator_error"]
    assert diagnostic["standard_error"] == 0.0
    assert diagnostic["status"] == "conditional_estimate"
    assert diagnostic["assumptions_verified"] is False
    assert diagnostic["gate_eligible"] is False
    assert result.envelope.gate_eligible is False
