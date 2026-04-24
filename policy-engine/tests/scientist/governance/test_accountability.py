from __future__ import annotations

from polisyos.calibration import evaluate_binary
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.analytics.distributional import TailRiskDeltaEntry, TailRiskDeltaSummary
from polisyos.ir.analytics.fairness import CausalFairnessReport, FairnessDecomposition
from polisyos.scientist.governance.accountability import (
    GovernanceAccountabilityInput,
    build_governance_accountability_artifact,
    load_governance_accountability_artifact,
    persist_governance_accountability_artifact,
)


def _candidate_ref(seed: str) -> ArtifactRef:
    return ArtifactRef(
        artifact_id=f"sha256:{seed * 64}",
        kind="scientist.test",
        media_type="application/json",
    )


def _fairness_report() -> CausalFairnessReport:
    return CausalFairnessReport(
        decomposition=FairnessDecomposition(
            tv=0.16,
            direct_effect=0.08,
            indirect_effect=0.03,
            spurious_effect=0.05,
            decomposition_residual=0.0,
            n_obs=8,
            protected_attribute="gender",
            outcome="approval",
            mediators=("income_proxy",),
            estimation_method="counterfactual",
        ),
        counterfactual_fairness_satisfied=False,
        path_specific_fairness={"A->Y": False},
        direct_discrimination=0.08,
        indirect_discrimination=0.03,
        primary_unfair_pathway="A->Y",
        recommendation="Direct discrimination remains above the default-path threshold.",
    )


def _tail_risk_summary() -> TailRiskDeltaSummary:
    return TailRiskDeltaSummary(
        outcome_name="loss",
        entries=[
            TailRiskDeltaEntry(
                baseline_quantile=0.95,
                threshold_value=0.8,
                baseline_exceedance_probability=0.05,
                counterfactual_exceedance_probability=0.13,
                exceedance_probability_delta=0.08,
                baseline_expected_shortfall=0.22,
                counterfactual_expected_shortfall=0.34,
                expected_shortfall_delta=0.12,
            )
        ],
    )


def test_governance_accountability_artifact_builds_thresholds_frontier_and_escalation(
    tmp_path,
) -> None:
    store = FileSystemCAS(tmp_path)
    artifact = build_governance_accountability_artifact(
        run_id="R_accountability",
        candidate_ref=_candidate_ref("a"),
        governance_verdict="approve",
        governance_issues=[],
        adversarial_results=[],
        composite_score=0.82,
        eligible_for_promotion=True,
        stress_summary={"worst_scenario": "trade_disruption", "critical_count": 1, "high_count": 2},
        accountability_input=GovernanceAccountabilityInput(
            candidate_id="candidate_policy",
            model_name="policy_classifier",
            model_version="2026.04",
            intended_use="promotion_gate",
            evaluation_split="holdout",
            dataset_name="policy_holdout",
            dataset_version="v1",
            data_sources=["holdout_snapshot"],
            known_limitations=["small protected-group slices"],
            predicted_scores=[0.95, 0.80, 0.70, 0.40, 0.65, 0.55, 0.35, 0.10],
            observed_outcomes=[1.0, 1.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0],
            protected_attributes={
                "gender": ["F", "F", "F", "F", "M", "M", "M", "M"],
                "region": ["urban", "urban", "rural", "rural", "urban", "urban", "rural", "rural"],
            },
            causal_fairness_report=_fairness_report(),
            tail_risk_summary=_tail_risk_summary(),
        ),
    )

    assert artifact.calibration is not None
    assert artifact.calibration.brier_score is not None
    assert len(artifact.calibration.reliability_diagram) == 10
    assert artifact.fairness is not None
    assert artifact.fairness.equalized_odds_gap is not None
    assert artifact.fairness.group_calibration
    assert artifact.adaptive_threshold is not None
    assert artifact.adaptive_threshold.frontier
    assert artifact.risk is not None
    assert artifact.risk.cvar_delta == 0.12
    assert artifact.risk_weighted_verdict == "human_gate"
    assert artifact.escalation_policy.requires_human_review is True

    counterfactual_threshold = next(
        entry
        for entry in artifact.threshold_registry
        if entry.threshold_id == "fairness.counterfactual_direct_discrimination_max"
    )
    assert counterfactual_threshold.passed is False
    assert counterfactual_threshold.rationale

    ref = persist_governance_accountability_artifact(store, artifact)
    loaded = load_governance_accountability_artifact(store, ref)

    summary = loaded.compact_summary()
    assert summary["risk_weighted_verdict"] == "human_gate"
    assert summary["requires_human_review"] is True
    assert (
        "threshold_violation:fairness.counterfactual_direct_discrimination_max"
        in summary["escalation_triggers"]
    )
    assert summary["fairness"]["counterfactual_fairness_satisfied"] is False


def test_governance_accountability_prefers_external_calibration_diagnostics(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    external = evaluate_binary(
        y_true=[1.0, 1.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0],
        y_prob=[0.80, 0.75, 0.20, 0.15, 0.70, 0.25, 0.30, 0.10],
        curves={"binning": ["quantile"], "n_bins": [4]},
    )
    artifact = build_governance_accountability_artifact(
        run_id="R_accountability_external_diag",
        candidate_ref=_candidate_ref("b"),
        governance_verdict="approve",
        accountability_input=GovernanceAccountabilityInput(
            predicted_scores=[0.99, 0.99, 0.99, 0.99, 0.01, 0.01, 0.01, 0.01],
            observed_outcomes=[1.0, 1.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0],
            calibration_diagnostics=external,
        ),
    )

    assert artifact.calibration is not None
    assert artifact.calibration.ece == external.metrics.ece
    assert len(artifact.calibration.reliability_diagram) == 4
    ref = persist_governance_accountability_artifact(store, artifact)
    loaded = load_governance_accountability_artifact(store, ref)
    assert loaded.calibration is not None
    assert loaded.calibration.ece == external.metrics.ece
