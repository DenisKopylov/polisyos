from __future__ import annotations

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.artifacts import get_json_artifact
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
    LatentDiscoveryBundle,
    LatentTrustLevel,
    load_causal_discovery_report,
    persist_causal_discovery_report,
)
from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, EdgeMark, GraphType
from polisyos.ir.refs import CausalDiscoveryReportRef


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
                        description="Observed environment changes are not downstream of the policy.",
                        evidence_basis=["domain_note:env_a_vs_env_b"],
                        falsification_hook="check pre-policy covariate drift",
                    )
                ],
                no_promotion_reasons=["latent_discovery_proof_only"],
                metadata={"review_label": "not_for_decision_support"},
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
