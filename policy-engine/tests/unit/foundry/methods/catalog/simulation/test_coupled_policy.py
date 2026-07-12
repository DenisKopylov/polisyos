from __future__ import annotations

import json

import numpy as np

from polisyos.ir.analytics.phase4_dynamics import verify_strangle_receipt


def test_coupled_policy_simulation_is_registered(isolated_registry) -> None:
    method = isolated_registry.get("simulation.coupled_policy.des_abm@1.0.0")

    assert method is not None
    assert isolated_registry.get("simulation.coupled_policy.queue_mle@1.0.0") is not None
    assert isolated_registry.get("simulation.coupled_policy.smm@1.0.0") is not None
    assert isolated_registry.get("simulation.coupled_policy.particle_filter@1.0.0") is not None
    assert isolated_registry.get("simulation.coupled_policy.paired_mc@1.0.0") is not None


def test_coupled_policy_simulation_runs_des_abm_feedback(isolated_registry) -> None:
    method = isolated_registry.get("simulation.coupled_policy.des_abm@1.0.0")
    state = {
        "initial_income": np.asarray([0.0, 0.0]),
        "initial_savings": np.asarray([0.0, 0.0]),
        "is_employed": np.asarray([0.0, 0.0]),
        "risk_aversion": np.asarray([0.1, 0.9]),
    }

    result = method.pure_step(
        state,
        {
            "n_steps": 2,
            "service_rate": 1.0,
            "capacity": 10,
            "benefit_amount": 50.0,
            "seed": 0,
        },
    )["result"]

    assert result["final_queue_length"] == 1.0
    assert result["completed_count"] == 1
    assert result["final_savings"] == [0.0, 50.0]
    assert result["summary"]["final_mean_savings"] == 25.0
    assert result["abm_result"]["identifiability_certificate"]["status"] == (
        "diagnostic_attached"
    )
    assert result["abm_result"]["bifurcation_report"]["status"] == "not_available"
    assert "phase4_abm_result_stub" not in json.dumps(result["abm_result"])
    receipt_note = next(
        note
        for note in result["abm_result"]["notes"]
        if note.startswith("strangle_receipt:")
    )
    payload = dict(result)
    payload.pop("abm_result")
    diagnostics = {
        "method_id": "simulation.coupled_policy.des_abm",
        "horizon": 2,
        "diagnostic_source": "CoupledPolicySimulationEstimator.pure_step",
        "summary_keys": sorted(str(key) for key in result["summary"]),
    }
    verify_strangle_receipt(
        receipt_note.removeprefix("strangle_receipt:"),
        method_id="simulation.coupled_policy.des_abm",
        horizon=2,
        payload=payload,
        diagnostics=diagnostics,
    )


def test_coupled_queue_mle_method_estimates_local_rates(isolated_registry) -> None:
    method = isolated_registry.get("simulation.coupled_policy.queue_mle@1.0.0")

    result = method.pure_step(
        {
            "event_times": np.asarray([0.0, 1.0, 3.0, 4.0]),
            "event_kind_codes": np.asarray([1, 2, 3, 4]),
            "event_entity_codes": np.asarray([0, 0, 0, 1]),
        },
        {},
    )["result"]

    assert result["n_arrivals"] == 1
    assert result["n_service_completions"] == 1
    assert result["service_rate"] == 0.5


def test_coupled_smm_method_selects_best_grid_point(isolated_registry) -> None:
    method = isolated_registry.get("simulation.coupled_policy.smm@1.0.0")
    state = {
        "initial_income": np.asarray([0.0, 0.0]),
        "initial_savings": np.asarray([0.0, 0.0]),
        "is_employed": np.asarray([0.0, 0.0]),
        "risk_aversion": np.asarray([0.1, 0.9]),
        "observed_moments": np.asarray([1.0, 1.0]),
    }

    result = method.pure_step(
        state,
        {
            "moment_names": ("completed_count", "final_queue_length"),
            "service_rate_grid": (0.5, 1.0),
            "benefit_amount_grid": (0.0,),
            "n_steps": 2,
            "capacity": 10,
            "seeds": (0,),
        },
    )["result"]

    assert result["best_params"]["service_rate"] == 1.0
    assert result["best_loss"] == 0.0


def test_particle_filter_and_paired_mc_methods_run(isolated_registry) -> None:
    particle = isolated_registry.get("simulation.coupled_policy.particle_filter@1.0.0")
    filtered = particle.pure_step(
        {"observed_queue_lengths": np.asarray([0.0, 1.0, 1.0])},
        {"arrival_rate": 1.0, "service_rate": 0.5, "n_particles": 32, "seed": 3},
    )["result"]

    assert len(filtered["filtered_mean"]) == 3
    assert np.isfinite(filtered["log_likelihood"])

    paired = isolated_registry.get("simulation.coupled_policy.paired_mc@1.0.0")
    result = paired.pure_step(
        {
            "initial_income": np.asarray([0.0, 0.0]),
            "initial_savings": np.asarray([0.0, 0.0]),
            "is_employed": np.asarray([0.0, 0.0]),
            "risk_aversion": np.asarray([0.1, 0.9]),
        },
        {
            "metric_names": ("final_mean_savings",),
            "n_replications": 3,
            "n_steps": 2,
            "capacity": 10,
            "baseline_benefit_amount": 0.0,
            "policy_benefit_amount": 50.0,
        },
    )["result"]

    assert result["mean_effects"]["final_mean_savings"] == 25.0
    assert result["standard_errors"]["final_mean_savings"] == 0.0
