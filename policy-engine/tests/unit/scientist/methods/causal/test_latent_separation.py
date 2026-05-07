from __future__ import annotations

import numpy as np
from polisyos.ir.analytics.causal_discovery import LatentTrustLevel
from polisyos.scientist.methods.causal.latent_separation import (
    SEPARATION_DIAGNOSTIC_INPUTS_KEY,
    SEPARATION_DIAGNOSTICS_KEY,
    LatentSeparationDiagnosticInputs,
    LatentSeparationEnvironmentInput,
    LatentSeparationMeasurementInput,
    LatentSeparationProxyInput,
    certified_latent_separation_pairs,
    certify_latent_separation_trust,
    compute_latent_separation_diagnostics,
    compute_latent_separation_diagnostics_from_inputs,
    latent_separation_assumption_surfaces,
    latent_separation_falsification_surfaces,
    merge_latent_separation_diagnostics_payloads,
    metadata_with_computed_latent_separation,
)


def _diagnostics(**overrides):
    payload = {
        "resolution_label": "latent_confounding",
        "design": {
            "n_env": 3,
            "proxy_blocks": ["W", "Z"],
            "repeated_indicator_blocks": ["R"],
        },
        "measurement_block": {
            "status": "passed",
            "tetrad_test": "single_signal_tetrad_passed",
            "invariance_test": "measurement_invariance_passed",
        },
        "proxy_block": {
            "status": "passed",
            "bridge_test": "proximal_bridge_solved",
            "bridge_stability": "cross_environment_stable",
        },
        "environment_block": {
            "status": "passed",
            "residual_invariance": "post_calibration_residual_invariance_failed",
            "post_calibration_shift": "not_restored",
        },
        "separated_pairs": ["measurement_vs_confounding"],
        "support_scope": ["multi-environment", "proximal-complete"],
    }
    payload.update(overrides)
    return payload


def _computed_inputs(
    *,
    seed: int = 2,
    n_obs: int = 160,
    env_shift: float = 0.2,
    weak_proxies: bool = False,
    flip_indicator: bool = False,
) -> tuple[dict[str, object], dict[str, object]]:
    rng = np.random.default_rng(seed)
    env = np.repeat(["region_a", "region_b"], n_obs // 2)
    env_effect = (env == "region_b").astype(float)
    latent = rng.normal(size=n_obs)
    treatment = (0.5 * latent + 0.4 * rng.normal(size=n_obs) > 0.0).astype(float)
    r1 = latent + rng.normal(scale=0.05, size=n_obs)
    r2 = 0.9 * latent + rng.normal(scale=0.05, size=n_obs)
    r3 = 1.1 * latent + rng.normal(scale=0.05, size=n_obs)
    if flip_indicator:
        r2[env == "region_b"] *= -1.0
    if weak_proxies:
        w_proxy = rng.normal(size=n_obs)
        z_proxy = rng.normal(size=n_obs)
        outcome = (
            treatment + 0.8 * latent + env_shift * env_effect + rng.normal(scale=0.2, size=n_obs)
        )
    else:
        w_proxy = 0.7 * latent + 0.5 * rng.normal(size=n_obs)
        z_proxy = 0.4 * latent + 0.6 * rng.normal(size=n_obs)
        outcome = (
            treatment
            + 0.8 * w_proxy
            + 0.2 * latent
            + env_shift * env_effect
            + rng.normal(scale=0.2, size=n_obs)
        )
    data = {
        "outcome": outcome,
        "treatment": treatment,
        "environment": env,
        "r1": r1,
        "r2": r2,
        "r3": r3,
        "W": w_proxy,
        "Z": z_proxy,
    }
    design = {
        "repeated_indicator_blocks": ["r1", "r2", "r3"],
        "proxy_blocks": ["W", "Z"],
    }
    return data, design


def test_compute_latent_separation_diagnostics_finds_latent_confounding() -> None:
    data, design = _computed_inputs(env_shift=0.2)

    payload = compute_latent_separation_diagnostics(data, design)

    assert payload["resolution_label"] == "latent_confounding"
    assert payload["measurement_block"]["status"] == "passed"
    assert payload["proxy_block"]["bridge_test"] == "proximal_bridge_solved"
    assert payload["environment_block"]["residual_invariance"] == (
        "post_calibration_residual_invariance_failed"
    )
    assert (
        certify_latent_separation_trust(
            {SEPARATION_DIAGNOSTICS_KEY: payload},
            fallback=LatentTrustLevel.RESEARCH,
        )
        is LatentTrustLevel.CONDITIONAL
    )


def test_compute_latent_separation_diagnostics_finds_measurement_error() -> None:
    data, design = _computed_inputs(
        n_obs=140,
        env_shift=0.0,
        weak_proxies=True,
    )

    payload = compute_latent_separation_diagnostics(data, design)

    assert payload["resolution_label"] == "measurement_error"
    assert payload["proxy_block"]["bridge_test"] == "proximal_bridge_failed"
    assert payload["environment_block"]["residual_invariance"] == (
        "post_calibration_residual_invariance_restored"
    )
    assert (
        certify_latent_separation_trust(
            {SEPARATION_DIAGNOSTICS_KEY: payload},
            fallback=LatentTrustLevel.RESEARCH,
        )
        is LatentTrustLevel.CONDITIONAL
    )


def test_compute_latent_separation_diagnostics_finds_proxy_mismatch() -> None:
    data, design = _computed_inputs(
        n_obs=140,
        env_shift=0.5,
        weak_proxies=True,
    )

    payload = compute_latent_separation_diagnostics(data, design)

    assert payload["resolution_label"] == "proxy_mismatch"
    assert payload["proxy_block"]["bridge_test"] == "proximal_bridge_failed"
    assert payload["environment_block"]["residual_invariance"] == (
        "post_calibration_residual_invariance_failed"
    )


def test_compute_latent_separation_diagnostics_surfaces_mixed_signals() -> None:
    data, design = _computed_inputs(
        env_shift=0.0,
        flip_indicator=True,
    )

    payload = compute_latent_separation_diagnostics(data, design)

    assert payload["resolution_label"] == "mixed"
    assert payload["measurement_block"]["status"] == "failed"
    assert payload["conflicts"] == [
        "latent_separation:measurement_conflicts_with_proxy_or_environment"
    ]


def test_computed_latent_separation_diagnostics_stay_unresolved_when_unsupported() -> None:
    payload = compute_latent_separation_diagnostics(
        {"outcome": [1.0, 2.0], "treatment": [0.0, 1.0]},
        {"repeated_indicator_blocks": [], "proxy_blocks": []},
    )

    assert payload["resolution_label"] == "unresolved"
    assert (
        certify_latent_separation_trust(
            {SEPARATION_DIAGNOSTICS_KEY: payload},
            fallback=LatentTrustLevel.VALIDATED,
        )
        is LatentTrustLevel.RESEARCH
    )


def test_raw_inputs_take_precedence_over_prefilled_separation_metadata() -> None:
    metadata = {
        SEPARATION_DIAGNOSTICS_KEY: _diagnostics(),
        SEPARATION_DIAGNOSTIC_INPUTS_KEY: {
            "data": {"outcome": [1.0, 2.0], "treatment": [0.0, 1.0]},
            "design": {"repeated_indicator_blocks": [], "proxy_blocks": []},
        },
    }

    computed = metadata_with_computed_latent_separation(metadata)

    assert computed[SEPARATION_DIAGNOSTICS_KEY]["resolution_label"] == "unresolved"
    assert (
        certify_latent_separation_trust(
            computed,
            fallback=LatentTrustLevel.VALIDATED,
        )
        is LatentTrustLevel.RESEARCH
    )


def test_latent_separation_certifies_conditional_with_pairwise_separation() -> None:
    assert certified_latent_separation_pairs(_diagnostics()) == ["measurement_vs_confounding"]

    trust = certify_latent_separation_trust(
        {SEPARATION_DIAGNOSTICS_KEY: _diagnostics()},
        fallback=LatentTrustLevel.RESEARCH,
    )

    assert trust is LatentTrustLevel.CONDITIONAL


def test_latent_separation_certifies_validated_with_replication() -> None:
    trust = certify_latent_separation_trust(
        {
            SEPARATION_DIAGNOSTICS_KEY: _diagnostics(
                replication={
                    "status": "passed",
                    "held_out_environments": True,
                    "replicated_resolution_label": "latent_confounding",
                    "replicated_separated_pairs": ["measurement_vs_confounding"],
                }
            )
        },
        fallback=LatentTrustLevel.RESEARCH,
    )

    assert trust is LatentTrustLevel.VALIDATED


def test_latent_separation_keeps_research_when_design_is_incomplete() -> None:
    trust = certify_latent_separation_trust(
        {
            SEPARATION_DIAGNOSTICS_KEY: _diagnostics(
                design={
                    "n_env": 1,
                    "proxy_blocks": ["W"],
                    "repeated_indicator_blocks": [],
                }
            )
        },
        fallback=LatentTrustLevel.VALIDATED,
    )

    assert trust is LatentTrustLevel.RESEARCH


def test_structured_latent_separation_inputs_compute_without_raw_data() -> None:
    payload = compute_latent_separation_diagnostics_from_inputs(
        LatentSeparationDiagnosticInputs(
            candidate_latent_nodes=["U_01"],
            design={
                "environments": ["region_a", "region_b"],
                "proxy_blocks": ["W", "Z"],
                "repeated_indicator_blocks": ["R_block"],
            },
            measurement_block=LatentSeparationMeasurementInput(
                status="passed",
                tetrad_test="single_signal_tetrad_passed",
                invariance_test="measurement_invariance_passed",
                repeated_indicator_blocks=["R_block"],
            ),
            proxy_block=LatentSeparationProxyInput(
                status="passed",
                bridge_test="proximal_bridge_solved",
                bridge_stability="cross_environment_stable",
                proxy_blocks=["W", "Z"],
            ),
            environment_block=LatentSeparationEnvironmentInput(
                status="passed",
                residual_invariance="post_calibration_residual_invariance_failed",
                post_calibration_shift="not_restored",
                environments=["region_a", "region_b"],
                n_env=2,
            ),
        )
    )

    assert payload["source"] == "computed_from_inputs"
    assert payload["resolution_label"] == "latent_confounding"
    assert payload["measurement_block"]["tetrad_test"] == "single_signal_tetrad_passed"
    assert payload["proxy_block"]["bridge_test"] == "proximal_bridge_solved"
    assert payload["environment_block"]["post_calibration_shift"] == "not_restored"


def test_structured_latent_separation_inputs_support_validated_replication() -> None:
    metadata = {
        SEPARATION_DIAGNOSTIC_INPUTS_KEY: LatentSeparationDiagnosticInputs(
            candidate_latent_nodes=["U_01"],
            design={
                "environments": ["region_a", "region_b"],
                "proxy_blocks": ["W", "Z"],
                "repeated_indicator_blocks": ["R_block"],
            },
            measurement_block=LatentSeparationMeasurementInput(
                status="passed",
                tetrad_test="single_signal_tetrad_passed",
                invariance_test="measurement_invariance_passed",
                repeated_indicator_blocks=["R_block"],
            ),
            proxy_block=LatentSeparationProxyInput(
                status="passed",
                bridge_test="proximal_bridge_solved",
                bridge_stability="cross_environment_stable",
                proxy_blocks=["W", "Z"],
            ),
            environment_block=LatentSeparationEnvironmentInput(
                status="passed",
                residual_invariance="post_calibration_residual_invariance_failed",
                post_calibration_shift="not_restored",
                environments=["region_a", "region_b"],
                n_env=2,
            ),
            replication={
                "status": "passed",
                "held_out_environments": True,
                "replicated_resolution_label": "latent_confounding",
                "replicated_separated_pairs": ["measurement_vs_confounding"],
            },
        ).model_dump(mode="json")
    }

    computed = metadata_with_computed_latent_separation(metadata)

    assert computed[SEPARATION_DIAGNOSTICS_KEY]["source"] == "computed_from_inputs"
    assert (
        certify_latent_separation_trust(computed, fallback=LatentTrustLevel.RESEARCH)
        is LatentTrustLevel.VALIDATED
    )


def test_latent_separation_does_not_certify_red_embedding_representation() -> None:
    payload = compute_latent_separation_diagnostics_from_inputs(
        LatentSeparationDiagnosticInputs(
            candidate_latent_nodes=["U_01"],
            design={
                "environments": ["region_a", "region_b"],
                "proxy_blocks": ["W", "Z"],
                "repeated_indicator_blocks": ["R_block"],
            },
            measurement_block=LatentSeparationMeasurementInput(
                status="passed",
                tetrad_test="single_signal_tetrad_passed",
                invariance_test="measurement_invariance_passed",
                repeated_indicator_blocks=["R_block"],
            ),
            proxy_block=LatentSeparationProxyInput(
                status="passed",
                bridge_test="proximal_bridge_solved",
                bridge_stability="cross_environment_stable",
                proxy_blocks=["W", "Z"],
                embedding_family="gcn",
                representation_faithfulness_status="red",
                separator_recoverability={"community_score": 0.41},
                collision_rate=0.34,
                effect_drift_z=2.7,
                representation_recommended_action="require_raw_graph_summaries",
            ),
            environment_block=LatentSeparationEnvironmentInput(
                status="passed",
                residual_invariance="post_calibration_residual_invariance_failed",
                post_calibration_shift="not_restored",
                environments=["region_a", "region_b"],
                n_env=2,
            ),
        )
    )

    assert payload["resolution_label"] == "latent_confounding"
    assert certified_latent_separation_pairs(payload) == []
    assert (
        certify_latent_separation_trust(
            {SEPARATION_DIAGNOSTICS_KEY: payload},
            fallback=LatentTrustLevel.CONDITIONAL,
        )
        is LatentTrustLevel.RESEARCH
    )


def test_latent_separation_keeps_research_when_falsification_payload_is_incomplete() -> None:
    trust = certify_latent_separation_trust(
        {
            SEPARATION_DIAGNOSTICS_KEY: _diagnostics(
                proxy_block={"status": "passed", "bridge_test": "proximal_bridge_solved"}
            )
        },
        fallback=LatentTrustLevel.CONDITIONAL,
    )

    assert trust is LatentTrustLevel.RESEARCH


def test_latent_separation_keeps_research_when_pair_is_declared_but_not_certified() -> None:
    payload = _diagnostics(
        resolution_label="measurement_error",
        environment_block={
            "status": "passed",
            "residual_invariance": "post_calibration_residual_invariance_failed",
            "post_calibration_shift": "not_restored",
        },
        separated_pairs=["measurement_vs_proxy"],
    )

    assert certified_latent_separation_pairs(payload) == []
    assert (
        certify_latent_separation_trust(
            {SEPARATION_DIAGNOSTICS_KEY: payload},
            fallback=LatentTrustLevel.CONDITIONAL,
        )
        is LatentTrustLevel.RESEARCH
    )


def test_latent_separation_certifies_measurement_error_against_proxy_mismatch() -> None:
    payload = _diagnostics(
        resolution_label="measurement_error",
        separated_pairs=["measurement_vs_proxy"],
        proxy_block={
            "status": "passed",
            "bridge_test": "proximal_bridge_failed",
            "bridge_stability": "cross_environment_unstable",
        },
        environment_block={
            "status": "passed",
            "residual_invariance": "post_calibration_residual_invariance_restored",
            "post_calibration_shift": "absorbed",
        },
    )

    assert certified_latent_separation_pairs(payload) == ["measurement_vs_proxy"]
    assert (
        certify_latent_separation_trust(
            {SEPARATION_DIAGNOSTICS_KEY: payload},
            fallback=LatentTrustLevel.RESEARCH,
        )
        is LatentTrustLevel.CONDITIONAL
    )


def test_latent_separation_certifies_proxy_mismatch_against_confounding() -> None:
    payload = _diagnostics(
        resolution_label="proxy_mismatch",
        separated_pairs=["proxy_vs_confounding"],
        measurement_block={
            "status": "passed",
            "tetrad_test": "single_signal_tetrad_passed",
            "invariance_test": "measurement_invariance_passed",
        },
        proxy_block={
            "status": "failed",
            "flagged_proxies": ["W_bad"],
            "bridge_test": "proximal_bridge_failed",
            "bridge_stability": "cross_environment_unstable",
        },
    )

    assert certified_latent_separation_pairs(payload) == ["proxy_vs_confounding"]
    assert (
        certify_latent_separation_trust(
            {SEPARATION_DIAGNOSTICS_KEY: payload},
            fallback=LatentTrustLevel.RESEARCH,
        )
        is LatentTrustLevel.CONDITIONAL
    )


def test_latent_separation_surfaces_assumptions_and_falsification_families() -> None:
    payload = _diagnostics()

    assumptions = latent_separation_assumption_surfaces(payload)
    tests = latent_separation_falsification_surfaces(payload)

    assert "latent_separation_resolution:latent_confounding" in assumptions
    assert "latent_separation_pair:measurement_vs_confounding" in assumptions
    assert "latent_separation_design:multi_environment" in assumptions
    assert "latent_separation:single_signal_tetrad" in tests
    assert "latent_separation:proximal_bridge_overidentification" in tests
    assert "latent_separation:proximal_bridge_solved" in tests


def test_merging_replicated_diagnostics_can_validate_same_resolution() -> None:
    merged = merge_latent_separation_diagnostics_payloads([_diagnostics(), _diagnostics()])

    assert merged is not None
    assert merged["resolution_label"] == "latent_confounding"
    assert merged["replication"]["independent_discovery_hypothesis"] is True
    assert (
        certify_latent_separation_trust(
            {SEPARATION_DIAGNOSTICS_KEY: merged},
            fallback=LatentTrustLevel.RESEARCH,
        )
        is LatentTrustLevel.VALIDATED
    )
