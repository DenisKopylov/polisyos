from __future__ import annotations

import numpy as np
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
