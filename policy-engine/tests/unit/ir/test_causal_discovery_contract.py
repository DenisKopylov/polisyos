from __future__ import annotations

import pytest
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.analytics.causal_discovery import (
    AlgebraicCalibrationMode,
    AlgebraicConstraintFamily,
    AlgebraicConstraintReport,
    AlgebraicFalsificationScope,
    AlgebraicNullDistribution,
    AlgebraicRegularityStatus,
    AlgebraicReproducibilityTier,
    CausalDiscoveryReport,
    ConstraintEvaluationResult,
    ImpliedConstraintSpec,
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
    load_causal_discovery_report,
    persist_causal_discovery_report,
)
from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, EdgeMark, GraphType
from polisyos.ir.artifacts import get_json_artifact
from polisyos.ir.registry.refs import ArtifactRefModel, CausalDiscoveryReportRef


def _minimal_report() -> CausalDiscoveryReport:
    graph = CausalGraphModel(
        graph_type=GraphType.PAG,
        nodes=["X", "Y"],
        edges=[CausalEdge(src="X", dst="Y", mark_src=EdgeMark.CIRCLE, mark_dst=EdgeMark.ARROW)],
        discovery_method="fci",
    )
    resolved_graph = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["X", "Y"],
        edges=[CausalEdge(src="X", dst="Y")],
        discovery_method="fci",
    )
    return CausalDiscoveryReport(
        method="fci",
        graph=graph,
        resolved_graph=resolved_graph,
        bootstrap_stability={"X->Y@lag=1": 0.92},
        n_bootstrap=100,
        significance_level=0.05,
        computation_time_seconds=12.4,
        warnings=[],
    )


def _report_with_algebraic_constraints() -> CausalDiscoveryReport:
    report = _minimal_report()
    return report.model_copy(
        update={
            "algebraic_constraints": AlgebraicConstraintReport(
                severity="warning",
                suggested_repairs=["Revisit the declared measurement block."],
                families_run=[AlgebraicConstraintFamily.CI, AlgebraicConstraintFamily.TETRAD],
                n_implied_constraints=2,
                n_violated_constraints=1,
                tested_by_family={"ci": 1, "tetrad": 1},
                violated_by_family={"ci": 0, "tetrad": 1},
                blocker_conditions_met_by_family={"ci": False, "tetrad": False},
                graph_ranking_penalty=0.35,
                implied_constraints_preview=[
                    ImpliedConstraintSpec(
                        constraint_id="ci:X|Y|_",
                        family=AlgebraicConstraintFamily.CI,
                        statement="X ⟂ Y",
                        variables=("X", "Y"),
                    ),
                    ImpliedConstraintSpec(
                        constraint_id="tetrad:block:ab_cd_vs_ac_bd",
                        family=AlgebraicConstraintFamily.TETRAD,
                        statement="cov(W,X)cov(Y,Z) - cov(W,Y)cov(X,Z) = 0",
                        variables=("W", "X", "Y", "Z"),
                        source_block_id="block",
                    ),
                ],
                violated_constraints_preview=[
                    ConstraintEvaluationResult(
                        constraint_id="tetrad:block:ab_cd_vs_ac_bd",
                        family=AlgebraicConstraintFamily.TETRAD,
                        status="violated",
                        statistic=0.27,
                        p_value=0.01,
                        adjusted_p_value=0.02,
                        severity="warning",
                        regularity_status=AlgebraicRegularityStatus.POTENTIALLY_SINGULAR,
                        null_distribution=AlgebraicNullDistribution.BOOTSTRAP,
                        calibration_mode=AlgebraicCalibrationMode.BOOTSTRAP,
                        scope_of_falsification=AlgebraicFalsificationScope.MEASUREMENT_BLOCK,
                        ranking_weight=0.35,
                        reproducibility_tier=AlgebraicReproducibilityTier.STOCHASTIC_BOOTSTRAP,
                        metadata={"route": "bootstrap_tetrad"},
                    )
                ],
            ),
            "metadata": {
                "algebraic_constraints_summary": {
                    "n_implied_constraints": 2,
                    "n_violated_constraints": 1,
                    "blocker_conditions_met_by_family": {"ci": False, "tetrad": False},
                    "graph_ranking_penalty": 0.35,
                },
                "algebraic_constraint_severity": "warning",
                "algebraic_constraint_families_run": ["ci", "tetrad"],
            },
        }
    )


def _report_with_latent_discovery() -> CausalDiscoveryReport:
    report = _minimal_report()
    return report.model_copy(
        update={
            "latent_discovery": LatentDiscoveryBundle(
                proposed_latent_nodes=["U_income_shock"],
                inducing_environments=["city_a", "city_b"],
                identification_conditions=["environmental shift is exogenous"],
                falsification_tests=["negative_control_outcome", "environment_holdout"],
                trust_level=LatentTrustLevel.RESEARCH,
                assumption_cards=[
                    LatentAssumptionCard(
                        assumption_id="latent_shift_exogeneity",
                        title="Shift exogeneity",
                        description=(
                            "Observed environment changes are not downstream of the policy."
                        ),
                        evidence_basis=["domain_note:env_a_vs_env_b"],
                        falsification_hook="check pre-policy covariate drift",
                    )
                ],
                no_promotion_reasons=["latent_discovery_proof_only"],
                metadata={"review_label": "not_for_decision_support"},
            ),
        }
    )


def _promotion_ref(ch: str, *, kind: str) -> ArtifactRefModel:
    seed = ch.lower()
    if seed not in "0123456789abcdef":
        seed = format(sum(ord(symbol) for symbol in seed) % 16, "x")
    return ArtifactRefModel(
        artifact_id=f"sha256:{seed * 64}",
        kind=kind,
        media_type="application/json",
    )


def _report_with_promoted_latent_discovery() -> CausalDiscoveryReport:
    report = _minimal_report()
    return report.model_copy(
        update={
            "latent_discovery": LatentDiscoveryBundle(
                proposed_latent_nodes=["U_income_shock"],
                inducing_environments=["city_a", "city_b"],
                identification_conditions=[
                    "environmental shift is exogenous",
                    "reflective measurement invariance",
                ],
                falsification_tests=[
                    "negative_control_outcome",
                    "environment_holdout",
                ],
                trust_level=LatentTrustLevel.CONDITIONAL,
                assumption_cards=[
                    LatentAssumptionCard(
                        assumption_id="latent_shift_exogeneity",
                        title="Shift exogeneity",
                        description=(
                            "Observed environment changes are not downstream of the policy."
                        ),
                        evidence_basis=["domain_note:env_a_vs_env_b"],
                        falsification_hook="check pre-policy covariate drift",
                    )
                ],
                readiness_cap="bounds_ready",
                human_gate_required=True,
                promotion_allowed=True,
                no_promotion_reasons=[],
                not_for_decision_support=False,
                promotion_evidence=LatentPromotionEvidence(
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
                    external_evidence_refs=[
                        _promotion_ref("e", kind="scientist.latent.external_evidence")
                    ],
                    replication_refs=[_promotion_ref("f", kind="scientist.latent.replication")],
                    hidden_benchmark_ref=_promotion_ref(
                        "g", kind="scientist.latent.hidden_benchmark"
                    ),
                    reviewer_decision_ref=_promotion_ref(
                        "h", kind="scientist.latent.reviewer_decision"
                    ),
                    scope_regime=["linear_nongaussian", "metric_invariant"],
                    invariance_level="metric",
                ),
                metadata={"review_label": "conditional_bounds_ready"},
            ),
        }
    )


def test_causal_discovery_report_contract() -> None:
    report = _minimal_report()
    assert report.method == "fci"
    assert report.graph.graph_type is GraphType.PAG
    assert report.resolved_graph is not None
    assert report.resolved_graph.graph_type is GraphType.DAG
    assert report.n_bootstrap == 100
    assert report.bootstrap_stability["X->Y@lag=1"] == 0.92
    assert report.algebraic_constraints is None


def test_causal_discovery_report_contract_supports_algebraic_constraints() -> None:
    report = _report_with_algebraic_constraints()

    assert report.algebraic_constraints is not None
    assert report.algebraic_constraints.severity == "warning"
    assert report.algebraic_constraints.n_implied_constraints == 2
    assert report.algebraic_constraints.n_violated_constraints == 1
    assert report.algebraic_constraints.graph_ranking_penalty == 0.35
    assert report.algebraic_constraints.blocker_conditions_met_by_family == {
        "ci": False,
        "tetrad": False,
    }


def test_causal_discovery_report_contract_supports_latent_governance_bundle() -> None:
    report = _report_with_latent_discovery()

    assert report.latent_discovery is not None
    assert report.latent_discovery.readiness_cap == "proof_only"
    assert report.latent_discovery.promotion_allowed is False
    assert report.latent_discovery.human_gate_required is True
    assert report.latent_discovery.not_for_decision_support is True


def test_latent_cardinality_spec_emits_canonical_bundle_fields() -> None:
    block = LatentBlockProposal(
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
    spec = LatentCardinalityIdentificationSpec(
        identifiability_status=LatentIdentifiabilityStatus.FULL,
        latent_blocks=[block],
        ambiguity_notes=["ordering_within_same_latent_set_unidentifiable"],
    )

    assert spec.proposed_latent_nodes() == ["U_01|block_size=1|role=confounder|status=identified"]
    conditions = spec.canonical_identification_conditions(
        treatment_variable="tax_rate",
        outcome_variable="employment",
    )
    assert "class:multi_env_linear_nongaussian_latent_sem" in conditions
    assert "atomic_block:U_01:p=1:pure_children>=2:neighbors>=3:rank=1" in conditions
    assert "env_shift:U_01:contrast=region_a_vs_region_b:localized=true" in conditions
    role_rule = "role_rule:U_01:ancestor(tax_rate)&ancestor(employment)&!descendant(tax_rate)"
    assert role_rule in conditions

    metadata = spec.bundle_metadata()
    assert metadata["model_class"] == "ME-LiNGLaH-S"
    assert metadata["identifiability_status"] == "full"
    assert metadata["latent_blocks"][0]["block_size"] == 1
    assert metadata["latent_blocks"][0]["evidence"]["shift_localized"] is True


def test_latent_cardinality_spec_requires_suspected_only_blocks_to_use_candidates() -> None:
    with pytest.raises(ValueError, match="latent_candidates"):
        LatentCardinalityIdentificationSpec(
            identifiability_status=LatentIdentifiabilityStatus.SUSPECTED_ONLY,
            latent_blocks=[
                LatentBlockProposal(
                    latent_id="U_99",
                    block_size=1,
                    status=LatentBlockStatus.SUSPECTED_ONLY,
                )
            ],
        )


def test_causal_discovery_report_artifact_roundtrip(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    report = _minimal_report()

    ref = persist_causal_discovery_report(store, report)
    loaded = load_causal_discovery_report(store, ref)

    assert isinstance(ref, CausalDiscoveryReportRef)
    assert ref.kind == "ir.causal_discovery_report"
    assert loaded == report


def test_causal_discovery_report_persists_algebraic_previews_via_refs(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    report = _report_with_algebraic_constraints()

    ref = persist_causal_discovery_report(store, report)
    persisted_payload = get_json_artifact(store, ref.artifact_id)
    loaded = load_causal_discovery_report(store, ref)

    algebraic = persisted_payload["algebraic_constraints"]
    assert algebraic["implied_constraints_ref"]["kind"] == "ir.algebraic_implied_constraints"
    assert algebraic["violated_constraints_ref"]["kind"] == "ir.algebraic_violated_constraints"
    assert algebraic["implied_constraints_preview"] == []
    assert algebraic["violated_constraints_preview"] == []

    assert loaded.algebraic_constraints is not None
    assert len(loaded.algebraic_constraints.implied_constraints_preview) == 2
    assert len(loaded.algebraic_constraints.violated_constraints_preview) == 1
    assert loaded.metadata["algebraic_constraint_severity"] == "warning"


def test_causal_discovery_report_roundtrips_latent_governance_bundle(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    report = _report_with_latent_discovery()

    ref = persist_causal_discovery_report(store, report)
    loaded = load_causal_discovery_report(store, ref)

    assert loaded.latent_discovery is not None
    assert loaded.latent_discovery == report.latent_discovery
    assert loaded.latent_discovery.readiness_cap == "proof_only"
    assert loaded.latent_discovery.promotion_allowed is False
    assert loaded.latent_discovery.human_gate_required is True


def test_causal_discovery_report_roundtrips_promoted_latent_governance_bundle(
    tmp_path,
) -> None:
    store = FileSystemCAS(tmp_path)
    report = _report_with_promoted_latent_discovery()

    ref = persist_causal_discovery_report(store, report)
    loaded = load_causal_discovery_report(store, ref)

    assert loaded.latent_discovery is not None
    assert loaded.latent_discovery == report.latent_discovery
    assert loaded.latent_discovery.trust_level is LatentTrustLevel.CONDITIONAL
    assert loaded.latent_discovery.readiness_cap == "bounds_ready"
    assert loaded.latent_discovery.promotion_allowed is True
    assert loaded.latent_discovery.not_for_decision_support is False
    assert loaded.latent_discovery.promotion_evidence is not None
    assert loaded.latent_discovery.promotion_evidence.invariance_level == "metric"
    assert loaded.latent_discovery.promotion_evidence.scope_regime == [
        "linear_nongaussian",
        "metric_invariant",
    ]
