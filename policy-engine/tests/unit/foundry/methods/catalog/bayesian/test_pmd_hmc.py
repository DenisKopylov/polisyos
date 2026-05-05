from __future__ import annotations

import numpy as np
from polisyos.foundry.methods.catalog.bayesian.pmd_hmc import (
    PmdHmcBenchmarkCase,
    assess_pmd_hmc_multimodality,
    build_pmd_hmc_benchmark_suite,
    run_pmd_hmc_benchmark,
)
from polisyos.foundry.methods.catalog.bayesian.protocols import (
    MultimodalityState,
    PolicyRelevanceClassification,
    PosteriorReadiness,
)


def _passing_sampler_summary() -> tuple[dict[str, float], dict[str, bool]]:
    return (
        {
            "num_monitored_chains": 4.0,
            "max_rhat": 1.0,
            "min_bulk_ess": 640.0,
            "min_tail_ess": 640.0,
            "min_bfmi": 0.70,
            "divergences": 0.0,
            "max_treedepth_hits": 0.0,
        },
        {
            "minimum_chains": True,
            "rhat": True,
            "bulk_ess": True,
            "tail_ess": True,
            "bfmi": True,
            "divergences": True,
            "max_treedepth_hits": True,
        },
    )


def test_pmd_hmc_detects_separated_modes_in_visited_support() -> None:
    rng = np.random.default_rng(5101)
    chains, draws = 4, 160
    samples = np.empty((chains, draws, 2), dtype=float)
    for chain_idx in range(chains):
        left = rng.normal(loc=(-3.0, 0.0), scale=0.20, size=(draws // 2, 2))
        right = rng.normal(loc=(3.0, 0.0), scale=0.20, size=(draws // 2, 2))
        samples[chain_idx] = np.vstack([left, right])
        rng.shuffle(samples[chain_idx], axis=0)

    diagnostics_summary, diagnostic_gates = _passing_sampler_summary()
    status, modes = assess_pmd_hmc_multimodality(
        {"theta": samples},
        num_chains=chains,
        num_samples=draws,
        diagnostics={"num_chains": float(chains), "num_samples": float(draws)},
        diagnostics_summary=diagnostics_summary,
        diagnostic_gates=diagnostic_gates,
        seed=5102,
        view_count=48,
        n_bootstrap=32,
        alpha_detect=0.05,
        w_min=0.10,
    )

    assert status.state is MultimodalityState.MULTIMODALITY_DETECTED
    assert status.test.p_global is not None
    assert status.test.p_global <= 0.05
    assert status.modes.n_detected_lower_bound == 2
    assert status.modes.assignments_available is True
    assert status.downgrade.posterior_readiness is PosteriorReadiness.CAUTION
    assert status.downgrade.mode_conditional_reporting_required is True
    assert len(modes) == 2
    assert {mode.mode_id for mode in modes} == {"M1", "M2"}
    assert sum(mode.draw_count for mode in modes) == chains * draws


def test_pmd_hmc_sampler_geometry_failure_is_inconclusive_not_not_detected() -> None:
    rng = np.random.default_rng(5201)
    samples = rng.normal(size=(2, 120, 3))

    status, modes = assess_pmd_hmc_multimodality(
        {"theta": samples},
        num_chains=2,
        num_samples=120,
        diagnostics={"num_chains": 2.0, "num_samples": 120.0, "divergences": 1.0},
        diagnostics_summary={
            "num_monitored_chains": 2.0,
            "max_rhat": 1.02,
            "min_bulk_ess": 80.0,
            "min_tail_ess": 60.0,
            "min_bfmi": 0.20,
            "divergences": 1.0,
        },
        diagnostic_gates={
            "minimum_chains": False,
            "rhat": False,
            "bulk_ess": False,
            "tail_ess": False,
            "bfmi": False,
            "divergences": False,
            "max_treedepth_hits": True,
        },
        seed=5202,
        view_count=24,
        n_bootstrap=8,
    )

    assert status.state is MultimodalityState.INCONCLUSIVE_SAMPLING_GEOMETRY
    assert status.sampler_adequacy.passed is False
    assert status.downgrade.posterior_readiness is PosteriorReadiness.NOT_READY
    assert status.downgrade.ordinary_mean_summary_allowed is False
    assert modes == ()


def test_pmd_hmc_detects_policy_relevant_multimodality() -> None:
    rng = np.random.default_rng(5301)
    chains, draws = 4, 140
    samples = np.empty((chains, draws, 1), dtype=float)
    for chain_idx in range(chains):
        left = rng.normal(loc=-3.0, scale=0.18, size=(draws // 2, 1))
        right = rng.normal(loc=3.0, scale=0.18, size=(draws // 2, 1))
        samples[chain_idx] = np.vstack([left, right])
        rng.shuffle(samples[chain_idx], axis=0)
    utilities = {
        "action_left": -np.square(samples + 3.0),
        "action_right": -np.square(samples - 3.0),
    }

    diagnostics_summary, diagnostic_gates = _passing_sampler_summary()
    status, modes = assess_pmd_hmc_multimodality(
        {"theta": samples},
        num_chains=chains,
        num_samples=draws,
        diagnostics={"num_chains": float(chains), "num_samples": float(draws)},
        diagnostics_summary=diagnostics_summary,
        diagnostic_gates=diagnostic_gates,
        utility_by_action=utilities,
        seed=5302,
        view_count=48,
        n_bootstrap=32,
        alpha_detect=0.05,
        w_min=0.10,
    )

    assert status.state is MultimodalityState.MULTIMODALITY_DETECTED_POLICY_RELEVANT
    assert status.policy_relevance.classification is PolicyRelevanceClassification.POLICY_SENSITIVE
    assert status.downgrade.posterior_readiness is PosteriorReadiness.REFUSE_SINGLE_POLICY
    assert {mode.policy_summaries["recommended_action"] for mode in modes} == {
        "action_left",
        "action_right",
    }


def test_pmd_hmc_allows_conditional_policy_when_modes_agree() -> None:
    rng = np.random.default_rng(5401)
    chains, draws = 4, 140
    samples = np.empty((chains, draws, 1), dtype=float)
    for chain_idx in range(chains):
        left = rng.normal(loc=-3.0, scale=0.18, size=(draws // 2, 1))
        right = rng.normal(loc=3.0, scale=0.18, size=(draws // 2, 1))
        samples[chain_idx] = np.vstack([left, right])
        rng.shuffle(samples[chain_idx], axis=0)
    utilities = {
        "action_a": np.ones_like(samples),
        "action_b": np.zeros_like(samples),
    }

    diagnostics_summary, diagnostic_gates = _passing_sampler_summary()
    status, modes = assess_pmd_hmc_multimodality(
        {"theta": samples},
        num_chains=chains,
        num_samples=draws,
        diagnostics={"num_chains": float(chains), "num_samples": float(draws)},
        diagnostics_summary=diagnostics_summary,
        diagnostic_gates=diagnostic_gates,
        utility_by_action=utilities,
        seed=5402,
        view_count=48,
        n_bootstrap=32,
        alpha_detect=0.05,
        w_min=0.10,
        policy_margin=0.25,
    )

    assert status.state is MultimodalityState.MULTIMODALITY_DETECTED_POLICY_INVARIANT
    assert status.policy_relevance.classification is PolicyRelevanceClassification.POLICY_INVARIANT
    assert status.policy_relevance.single_recommendation_allowed is True
    assert status.downgrade.posterior_readiness is PosteriorReadiness.CONDITIONAL
    assert {mode.policy_summaries["recommended_action"] for mode in modes} == {"action_a"}


def test_pmd_hmc_benchmark_runner_reports_power_rows() -> None:
    report = run_pmd_hmc_benchmark(
        [
            PmdHmcBenchmarkCase(
                case_id="null_5d",
                target_family="spherical_gaussian",
                dimension=5,
                chains=4,
                draws_per_chain=80,
                seed=5501,
            ),
            PmdHmcBenchmarkCase(
                case_id="mix_5d",
                target_family="two_component_gaussian_mixture",
                dimension=5,
                chains=4,
                draws_per_chain=80,
                separation=5.0,
                min_mode_weight=0.5,
                seed=5502,
            ),
        ],
        view_count=32,
        n_bootstrap=16,
        alpha_detect=0.10,
        w_min=0.10,
    )

    assert report["test_name"] == "PMD-HMC"
    assert len(report["rows"]) == 2
    assert report["power"] is not None


def test_pmd_hmc_default_benchmark_suite_covers_nulls_and_alternatives() -> None:
    cases = build_pmd_hmc_benchmark_suite(
        dimensions=(5,),
        chains_options=(4,),
        draws_per_chain_options=(500,),
        separations=(2.5,),
        min_mode_weights=(0.10,),
        covariance_ratios=(1.0,),
        seed=5601,
    )

    assert {case.target_family for case in cases} == {
        "spherical_gaussian",
        "student_t",
        "two_component_gaussian_mixture",
    }
    assert all(case.dimension == 5 for case in cases)
