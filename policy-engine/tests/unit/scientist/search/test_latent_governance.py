from __future__ import annotations

import numpy as np
from polisyos.ir.analytics.causal_discovery import (
    LatentAssumptionCard,
    LatentBlockEvidence,
    LatentBlockProposal,
    LatentBlockStatus,
    LatentCardinalityIdentificationSpec,
    LatentCausalRole,
    LatentDiscoveryBundle,
    LatentGraphStatus,
    LatentIdentifiabilityStatus,
    LatentPromotionEvidence,
    LatentTrustLevel,
)
from polisyos.ir.refs import ArtifactRefModel
from polisyos.scientist.methods.search.latent_governance import assess_latent_governance


def _cardinality_spec() -> LatentCardinalityIdentificationSpec:
    return LatentCardinalityIdentificationSpec(
        identifiability_status=LatentIdentifiabilityStatus.FULL,
        latent_blocks=[
            LatentBlockProposal(
                latent_id="U_01",
                block_size=1,
                role=LatentCausalRole.CONFOUNDER,
                status=LatentBlockStatus.IDENTIFIED,
                graph_status=LatentGraphStatus.IDENTIFIED,
                anchor_variables=["x_income_1", "x_income_2", "x_income_3"],
                informative_environment_contrasts=["region_a_vs_region_b"],
                evidence=LatentBlockEvidence(
                    gin_supported=True,
                    atomic_structure_supported=True,
                    shift_localized=True,
                    minimal_decomposition_supported=True,
                    role_rule_supported=True,
                    pure_child_count=3,
                    neighbor_count=3,
                    rank=1,
                ),
            )
        ],
        ambiguity_notes=["ordering_within_same_latent_set_unidentifiable"],
    )


def _bundle_from_spec(spec: LatentCardinalityIdentificationSpec) -> LatentDiscoveryBundle:
    return spec.to_bundle(
        inducing_environments=["region_a", "region_b"],
        falsification_tests=["negative_control_outcome", "environment_holdout"],
        trust_level=LatentTrustLevel.RESEARCH,
        assumption_cards=[
            LatentAssumptionCard(
                assumption_id="me_linglah_s_conditions",
                title="ME-LiNGLaH-S identification envelope",
                description=(
                    "Latent block cardinality uses GIN, pure children, and localized "
                    "environment shifts."
                ),
            )
        ],
        no_promotion_reasons=["latent_discovery_proof_only"],
        metadata=spec.bundle_metadata(),
    )


def _computed_latent_inputs() -> dict[str, object]:
    rng = np.random.default_rng(2)
    n_obs = 160
    env = np.repeat(["region_a", "region_b"], n_obs // 2)
    env_effect = (env == "region_b").astype(float)
    latent = rng.normal(size=n_obs)
    treatment = (0.5 * latent + 0.4 * rng.normal(size=n_obs) > 0.0).astype(float)
    r1 = latent + rng.normal(scale=0.05, size=n_obs)
    r2 = 0.9 * latent + rng.normal(scale=0.05, size=n_obs)
    r3 = 1.1 * latent + rng.normal(scale=0.05, size=n_obs)
    w_proxy = 0.7 * latent + 0.5 * rng.normal(size=n_obs)
    z_proxy = 0.4 * latent + 0.6 * rng.normal(size=n_obs)
    outcome = (
        treatment
        + 0.8 * w_proxy
        + 0.2 * latent
        + 0.2 * env_effect
        + rng.normal(scale=0.2, size=n_obs)
    )
    return {
        "data": {
            "outcome": outcome,
            "treatment": treatment,
            "environment": env,
            "r1": r1,
            "r2": r2,
            "r3": r3,
            "W": w_proxy,
            "Z": z_proxy,
        },
        "design": {
            "repeated_indicator_blocks": ["r1", "r2", "r3"],
            "proxy_blocks": ["W", "Z"],
        },
    }


def _promotion_ref(ch: str, *, kind: str) -> ArtifactRefModel:
    seed = ch.lower()
    if seed not in "0123456789abcdef":
        seed = format(sum(ord(symbol) for symbol in seed) % 16, "x")
    return ArtifactRefModel(
        artifact_id=f"sha256:{seed * 64}",
        kind=kind,
        media_type="application/json",
    )


def _conditional_promotion_evidence() -> LatentPromotionEvidence:
    return LatentPromotionEvidence(
        observable_implication_refs=[
            _promotion_ref("a", kind="scientist.latent.observable_implication")
        ],
        local_misspecification_test_refs=[
            _promotion_ref("b", kind="scientist.latent.local_misspecification")
        ],
        environment_stability_ref=_promotion_ref(
            "c", kind="scientist.latent.environment_stability"
        ),
        rival_explanation_audit_ref=_promotion_ref(
            "d", kind="scientist.latent.rival_explanation_audit"
        ),
        external_evidence_refs=[_promotion_ref("e", kind="scientist.latent.external_evidence")],
        replication_refs=[_promotion_ref("f", kind="scientist.latent.replication")],
        hidden_benchmark_ref=_promotion_ref("g", kind="scientist.latent.hidden_benchmark"),
        reviewer_decision_ref=_promotion_ref("h", kind="scientist.latent.reviewer_decision"),
        scope_regime=["linear_nongaussian", "metric_invariant"],
        invariance_level="metric",
    )


def _validated_measurement_promotion_evidence() -> LatentPromotionEvidence:
    return _conditional_promotion_evidence().model_copy(
        update={
            "replication_refs": [
                _promotion_ref("f", kind="scientist.latent.replication"),
                _promotion_ref("i", kind="scientist.latent.replication"),
            ],
            "exclusion_test_refs": [_promotion_ref("j", kind="scientist.latent.exclusion_test")],
            "external_anchor_refs": [_promotion_ref("k", kind="scientist.latent.external_anchor")],
            "cross_model_robustness_refs": [
                _promotion_ref("l", kind="scientist.latent.cross_model_robustness")
            ],
            "scope_regime": [
                "linear_nongaussian",
                "scalar_invariant",
                "reflective_measurement",
            ],
            "invariance_level": "scalar",
            "measurement_scope": True,
        }
    )


def test_latent_governance_accepts_cardinality_identification_conditions() -> None:
    bundle = _bundle_from_spec(_cardinality_spec())

    assessment = assess_latent_governance(bundle)

    assert assessment is not None
    assert assessment.valid is True
    assert assessment.metadata["model_class"] == "ME-LiNGLaH-S"
    assert assessment.metadata["identifiability_status"] == "full"
    assert assessment.metadata["latent_blocks"][0]["latent_id"] == "U_01"
    assert (
        "latent_cardinality_ambiguity:ordering_within_same_latent_set_unidentifiable"
        in assessment.surfaced_assumptions
    )
    assert assessment.promotion_allowed is False
    assert assessment.not_for_decision_support is True


def test_latent_cardinality_spec_roundtrips_via_bundle_helper() -> None:
    spec = _cardinality_spec()
    bundle = _bundle_from_spec(spec)

    recovered = bundle.latent_cardinality_spec()

    assert recovered == spec


def test_latent_governance_rejects_cardinality_claim_without_localized_shift() -> None:
    spec = _cardinality_spec()
    bundle = _bundle_from_spec(spec)
    weakened_conditions = [
        condition
        for condition in bundle.identification_conditions
        if not condition.startswith("env_shift:U_01:")
    ]
    bundle = bundle.model_copy(update={"identification_conditions": weakened_conditions})

    assessment = assess_latent_governance(bundle)

    assert assessment is not None
    assert assessment.valid is False
    assert "latent_cardinality_localized_shift_missing:U_01" in assessment.missing_requirements
    assert (
        "latent_cardinality_condition_failed:"
        "latent_cardinality_localized_shift_missing:U_01" in assessment.no_promotion_reasons
    )
    assert assessment.metadata["cardinality_gate_failures"] == [
        "latent_cardinality_localized_shift_missing:U_01"
    ]


def test_latent_governance_accepts_stage_9_2_falsification_family_without_manual_list() -> None:
    bundle = LatentDiscoveryBundle(
        proposed_latent_nodes=["U_labor_market"],
        inducing_environments=["region_a", "region_b"],
        identification_conditions=["proximal bridge completeness"],
        falsification_tests=[],
        trust_level=LatentTrustLevel.RESEARCH,
        assumption_cards=[
            LatentAssumptionCard(
                assumption_id="latent_shift_exogeneity",
                title="Shift exogeneity",
                description="Regional shift is not downstream of the proposed policy.",
            )
        ],
        no_promotion_reasons=["latent_discovery_proof_only"],
        metadata={
            "separation_diagnostics": {
                "resolution_label": "latent_confounding",
                "design": {
                    "n_env": 2,
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
            }
        },
    )

    assessment = assess_latent_governance(bundle)

    assert assessment is not None
    assert assessment.valid is True
    assert "falsification_tests_missing" not in assessment.missing_requirements
    assert assessment.metadata["trust_level"] == "conditional"
    assert assessment.metadata["certified_pairs"] in (
        ["measurement_vs_confounding"],
        ["proxy_vs_confounding"],
    )


def test_latent_governance_consumes_computed_separation_diagnostics_without_promotion() -> None:
    bundle = LatentDiscoveryBundle(
        proposed_latent_nodes=["U_labor_market"],
        inducing_environments=["region_a", "region_b"],
        identification_conditions=["proximal bridge completeness"],
        falsification_tests=[],
        trust_level=LatentTrustLevel.RESEARCH,
        assumption_cards=[
            LatentAssumptionCard(
                assumption_id="latent_shift_exogeneity",
                title="Shift exogeneity",
                description="Regional shift is not downstream of the proposed policy.",
            )
        ],
        no_promotion_reasons=["latent_discovery_proof_only"],
        metadata={"separation_diagnostic_inputs": _computed_latent_inputs()},
    )

    assessment = assess_latent_governance(bundle)

    assert assessment is not None
    assert assessment.valid is True
    assert assessment.metadata["trust_level"] == "conditional"
    assert assessment.metadata["resolution_label"] in {
        "latent_confounding",
        "proxy_mismatch",
    }
    assert assessment.metadata["certified_pairs"] in (
        ["measurement_vs_confounding"],
        ["proxy_vs_confounding"],
    )
    assert assessment.promotion_allowed is False
    assert assessment.metadata["readiness_cap"] == "proof_only"


def test_latent_governance_allows_conditional_bounds_ready_bundle() -> None:
    bundle = LatentDiscoveryBundle(
        proposed_latent_nodes=["U_labor_market"],
        inducing_environments=["region_a", "region_b"],
        identification_conditions=["proximal bridge completeness"],
        falsification_tests=["negative_control_outcome"],
        trust_level=LatentTrustLevel.CONDITIONAL,
        assumption_cards=[
            LatentAssumptionCard(
                assumption_id="latent_shift_exogeneity",
                title="Shift exogeneity",
                description="Regional shift is not downstream of the proposed policy.",
            )
        ],
        readiness_cap="bounds_ready",
        promotion_allowed=True,
        no_promotion_reasons=[],
        not_for_decision_support=False,
        promotion_evidence=_conditional_promotion_evidence(),
    )

    assessment = assess_latent_governance(bundle)

    assert assessment is not None
    assert assessment.valid is True
    assert assessment.claim_mode == "bounded_latent"
    assert assessment.degradation_mode == "bounds_only"
    assert assessment.readiness_cap == "bounds_ready"
    assert assessment.promotion_allowed is True
    assert assessment.not_for_decision_support is False
    assert assessment.promotion_verdict is not None
    assert assessment.promotion_verdict.derived_trust_level is LatentTrustLevel.CONDITIONAL


def test_latent_governance_allows_validated_measurement_estimation_ready_bundle() -> None:
    bundle = LatentDiscoveryBundle(
        proposed_latent_nodes=["U_labor_market"],
        inducing_environments=["region_a", "region_b", "region_c"],
        identification_conditions=["reflective measurement invariance"],
        falsification_tests=["negative_control_outcome", "environment_holdout"],
        trust_level=LatentTrustLevel.VALIDATED,
        assumption_cards=[
            LatentAssumptionCard(
                assumption_id="measurement_scope",
                title="Reflective measurement scope",
                description="Latent enters downstream use only as a reflective measurement layer.",
            )
        ],
        readiness_cap="estimation_ready",
        promotion_allowed=True,
        no_promotion_reasons=[],
        not_for_decision_support=False,
        promotion_evidence=_validated_measurement_promotion_evidence(),
    )

    assessment = assess_latent_governance(bundle)

    assert assessment is not None
    assert assessment.valid is True
    assert assessment.claim_mode == "validated_measurement_latent"
    assert assessment.degradation_mode == "measurement_ready"
    assert assessment.readiness_cap == "estimation_ready"
    assert assessment.promotion_allowed is True
    assert assessment.not_for_decision_support is False
    assert assessment.promotion_verdict is not None
    assert assessment.promotion_verdict.derived_trust_level is LatentTrustLevel.VALIDATED
