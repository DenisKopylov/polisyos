from __future__ import annotations

import numpy as np
import pytest

from polisyos.foundry.coupling.estimation import (
    calibrate_coupled_smm,
    estimate_queue_mle,
    filter_queue_counts,
    paired_monte_carlo_effect,
    summary_distance,
)


def test_estimate_queue_mle_recovers_event_log_rates() -> None:
    estimate = estimate_queue_mle(
        [
            {"time": 0.0, "kind": "arrival", "entity_id": "agent-0", "route": "standard"},
            {"time": 1.0, "kind": "service_start", "entity_id": "agent-0", "route": "standard"},
            {"time": 3.0, "kind": "service_complete", "entity_id": "agent-0", "route": "standard"},
            {"time": 4.0, "kind": "abandon", "entity_id": "agent-1", "route": "manual"},
        ]
    )

    assert estimate.n_arrivals == 1
    assert estimate.n_service_completions == 1
    assert estimate.service_rate == 0.5
    assert estimate.abandonment_rate == 0.25
    assert estimate.routing_probabilities["standard"] == 0.75


def test_calibrate_coupled_smm_selects_best_summary_match() -> None:
    observed = {"final_queue_length": 1.0, "completed_count": 2.0}

    def runner(params: dict[str, float], seed: int | None) -> dict[str, float]:
        del seed
        return {
            "final_queue_length": params["service_rate"],
            "completed_count": params["benefit_amount"] / 10.0,
        }

    result = calibrate_coupled_smm(
        {
            "service_rate": [0.5, 1.0],
            "benefit_amount": [10.0, 20.0],
        },
        runner,
        observed,
        seeds=(0, 1),
    )

    assert result.best_params == {"service_rate": 1.0, "benefit_amount": 20.0}
    assert result.best_loss == 0.0
    assert summary_distance(result.fitted_summary, observed) == 0.0


def test_particle_filter_and_paired_monte_carlo_return_stable_shapes() -> None:
    filtered = filter_queue_counts(
        [0.0, 1.0, 2.0],
        arrival_rate=1.0,
        service_rate=0.5,
        n_particles=64,
        seed=7,
    )

    assert len(filtered.filtered_mean) == 3
    assert np.isfinite(filtered.log_likelihood)

    paired = paired_monte_carlo_effect(
        lambda seed: {"welfare": float(seed)},
        lambda seed: {"welfare": float(seed + 2)},
        seeds=[1, 2, 3],
        metric_names=["welfare"],
    )

    assert paired.mean_effects["welfare"] == 2.0
    assert paired.standard_errors["welfare"] == 0.0
    assert paired.standard_error_status["welfare"] == "estimated"


def test_explicit_empty_required_moment_set_is_not_replaced_by_observed_keys() -> None:
    with pytest.raises(ValueError, match="required_moment_names must not be empty"):
        summary_distance(
            {"welfare": 0.0},
            {"welfare": 0.0},
            required_moment_names=(),
        )


def test_smm_optional_means_keep_their_repeat_denominators_and_do_not_rank() -> None:
    """B25: returned optional diagnostics retain each metric's actual sample count."""

    def runner(params: dict[str, float], seed: int | None) -> dict[str, float]:
        assert seed is not None
        required = 0.0 if params["candidate"] == 0.0 else 10.0
        summary = {"required": required}
        if params["candidate"] == 1.0 or seed == 11:
            summary["optional_signal"] = 1.0
        if seed == 13:
            summary["emergent_optional_13"] = 9.0
        return summary

    kwargs = {
        "parameter_grid": {"candidate": (0.0, 1.0)},
        "runner": runner,
        "observed_summary": {"required": 0.0},
        "required_moment_names": ("required",),
        "seeds": (11, 13, 17),
    }
    result = calibrate_coupled_smm(**kwargs)
    reversed_result = calibrate_coupled_smm(**{**kwargs, "seeds": (17, 13, 11)})
    sparse, dense = result.evaluated
    reversed_sparse, reversed_dense = reversed_result.evaluated

    assert sparse["summary"]["optional_signal"] == dense["summary"]["optional_signal"] == 1.0
    assert sparse["moment_counts"]["optional_signal"] == 1
    assert dense["moment_counts"]["optional_signal"] == 3
    assert sparse["moment_counts"]["emergent_optional_13"] == 1
    assert dense["moment_counts"]["emergent_optional_13"] == 1
    assert sparse["diagnostic_only_moments"] == ("emergent_optional_13", "optional_signal")
    assert sparse["optional_moment_status"] == "diagnostic_only"
    assert sparse["comparison_basis"] == "required_moments_only"
    assert sparse["summary"] == reversed_sparse["summary"]
    assert sparse["moment_counts"] == reversed_sparse["moment_counts"]
    assert dense["summary"] == reversed_dense["summary"]
    assert dense["moment_counts"] == reversed_dense["moment_counts"]

    # Optional coverage is descriptive; the required moment alone still selects the fit.
    assert result.best_params == {"candidate": 0.0}
    assert result.fitted_summary == sparse["summary"]
    assert result.fitted_moment_counts == sparse["moment_counts"]
    assert result.fitted_repeat_denominator == 3
    assert result.required_moments == ("required",)
    assert result.comparison_basis == "required_moments_only"
    assert result.optional_moment_status == "diagnostic_only"


def test_smm_missing_required_moment_cannot_win_with_complete_optional_diagnostics() -> None:
    """Optional coverage cannot compensate for a missing required comparison moment."""

    def runner(params: dict[str, float], seed: int | None) -> dict[str, float]:
        del seed
        if params["candidate"] == 0.0:
            return {"easy": 0.0, "optional": 0.0}
        return {"easy": 0.0, "hard": 99.0, "optional": 0.0}

    result = calibrate_coupled_smm(
        {"candidate": (0.0, 1.0)},
        runner,
        {"easy": 0.0, "hard": 100.0},
        required_moment_names=("easy", "hard"),
        seeds=(11, 13, 17),
    )

    assert result.best_params == {"candidate": 1.0}
    missing = next(item for item in result.evaluated if item["params"] == {"candidate": 0.0})
    assert missing["loss"] == float("inf")
    assert missing["missing_moments"] == ("hard",)
    assert missing["moment_counts"] == {"easy": 3, "hard": 0, "optional": 3}


def test_empty_and_partial_sample_moments_are_absent_but_explicit_zero_is_observed() -> None:
    from jax import numpy as jnp

    from polisyos.foundry.contracts.state import GlobalState, QueueRuntimeState
    from polisyos.foundry.coupling.estimation import extract_coupled_summary
    from polisyos.foundry.coupling.executor import CoupledRuntimeState

    empty_queue = QueueRuntimeState.empty(1)
    empty_runtime = CoupledRuntimeState.initialize(GlobalState.empty(1, 0), queue_state=empty_queue)
    summary = extract_coupled_summary(empty_runtime, [])
    assert "mean_wait" not in summary
    assert "p90_wait" not in summary
    assert "mean_queue_length" not in summary
    assert summary["completed_count"] == 0.0
    assert summary["final_mean_savings"] == 0.0

    partial_summary = extract_coupled_summary(
        empty_runtime,
        [{"queue/queue_length": 0.0}, {}],
    )
    assert "mean_queue_length" not in partial_summary

    zero_wait_queue = empty_queue.replace(
        queued_at=jnp.asarray([0.0]),
        completed_at=jnp.asarray([0.0]),
        completed_count=jnp.asarray(1),
    )
    zero_wait_runtime = CoupledRuntimeState.initialize(
        GlobalState.empty(1, 0), queue_state=zero_wait_queue
    )
    zero_summary = extract_coupled_summary(zero_wait_runtime, [{"queue/queue_length": 0.0}])
    assert zero_summary["mean_wait"] == 0.0
    assert zero_summary["p90_wait"] == 0.0
    assert zero_summary["mean_queue_length"] == 0.0


def test_summary_refuses_present_nonfinite_samples_and_omits_empty_population_means() -> None:
    from polisyos.foundry.contracts.state import GlobalState, QueueRuntimeState
    from polisyos.foundry.coupling.estimation import extract_coupled_summary
    from polisyos.foundry.coupling.executor import CoupledRuntimeState

    runtime = CoupledRuntimeState.initialize(
        GlobalState.empty(1, 0), queue_state=QueueRuntimeState.empty(1)
    )
    with pytest.raises(ValueError, match="finite"):
        extract_coupled_summary(runtime, [{"queue/queue_length": np.nan}])
    with pytest.raises(ValueError, match="finite"):
        extract_coupled_summary(runtime, [{"queue/queue_length": np.nan}, {}])

    empty_population = CoupledRuntimeState.initialize(
        GlobalState.empty(0, 0), queue_state=QueueRuntimeState.empty(0)
    )
    empty_summary = extract_coupled_summary(empty_population, [])
    assert "final_mean_savings" not in empty_summary
    assert "final_mean_income" not in empty_summary


def test_partial_queue_samples_do_not_hide_malformed_present_values() -> None:
    from polisyos.foundry.contracts.state import GlobalState, QueueRuntimeState
    from polisyos.foundry.coupling.estimation import extract_coupled_summary
    from polisyos.foundry.coupling.executor import CoupledRuntimeState

    runtime = CoupledRuntimeState.initialize(
        GlobalState.empty(1, 0), queue_state=QueueRuntimeState.empty(1)
    )
    with pytest.raises(ValueError, match="finite"):
        extract_coupled_summary(runtime, [{"queue/queue_length": np.nan}, {}])
    with pytest.raises(ValueError, match="numeric"):
        extract_coupled_summary(runtime, [{"queue/queue_length": "not-a-number"}, {}])


def test_queue_mle_requires_positive_exposure_and_preserves_observed_zero_arrivals() -> None:
    with pytest.raises(ValueError, match="event_log must not be empty"):
        estimate_queue_mle([])
    with pytest.raises(ValueError, match="positive observation window"):
        estimate_queue_mle([{"time": 1.0, "kind": "service_complete"}])

    estimate = estimate_queue_mle(
        [
            {"time": 0.0, "kind": "service_start", "entity_id": "agent-0"},
            {"time": 1.0, "kind": "service_complete", "entity_id": "agent-0"},
        ]
    )
    assert estimate.observation_window == 1.0
    assert estimate.n_arrivals == 0
    assert estimate.arrival_rate == 0.0


def test_particle_filter_requires_observations_and_preserves_observed_zero() -> None:
    with pytest.raises(ValueError, match="observed_queue_lengths must not be empty"):
        filter_queue_counts([], arrival_rate=0.0, service_rate=0.0)

    filtered = filter_queue_counts(
        [0.0], arrival_rate=0.0, service_rate=0.0, n_particles=32, seed=7
    )
    assert len(filtered.filtered_mean) == 1
    assert np.isfinite(filtered.log_likelihood)
    with pytest.raises(ValueError, match="finite"):
        filter_queue_counts([np.nan], arrival_rate=0.0, service_rate=0.0)
