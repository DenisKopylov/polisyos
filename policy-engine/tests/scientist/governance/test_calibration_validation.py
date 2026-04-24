from __future__ import annotations

import json

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.ir.analytics.distributional import TailRiskDeltaEntry, TailRiskDeltaSummary
from polisyos.ir.analytics.fairness import CausalFairnessReport, FairnessDecomposition
from polisyos.ir.analytics.interference import (
    ExposureMappingType,
    InterferenceCertificate,
    InterferenceEffectDecomposition,
    InterferenceMethod,
    NetworkInterferenceReport,
)
from polisyos.ir.observation.bundles import BacktestPlanBundle, ContractCompatibilityTarget
from polisyos.ir.observation.contract_compilers import SpecificationCurveInput
from polisyos.scientist.backtesting.plan import HistoricalValidationPlan, PredictionSource
from polisyos.scientist.discovery.utility_judge import (
    DownstreamUtilityReport,
    HypothesisUtilityScore,
)
from polisyos.scientist.governance.accountability import GovernanceAccountabilityInput
from polisyos.scientist.governance.backtest_matrix import BacktestKind
from polisyos.scientist.governance.calibration import (
    CalibrationAdversarialResult,
    CalibrationGovernanceReport,
)
from polisyos.scientist.governance.calibration_validation import (
    CalibrationValidationRunner,
    CalibrationValidationRunnerInput,
    load_calibration_validation_bundle,
)
from polisyos.scientist.search.lessons import LessonQuery, LessonRegistry, load_lesson_card


def _artifact_ref(seed: str) -> ArtifactRef:
    return ArtifactRef(
        artifact_id=f"sha256:{seed * 64}",
        kind="scientist.test",
        media_type="application/json",
    )


def _governance_report() -> CalibrationGovernanceReport:
    return CalibrationGovernanceReport(
        verdict="approve",
        adversarial_results=[
            CalibrationAdversarialResult(
                alias="strategic_gaming_adversarial",
                suite_id="strategic_gaming_v1",
                required=True,
                status="passed",
            ),
            CalibrationAdversarialResult(
                alias="multiplicity_disclosure_adversarial",
                suite_id="multiplicity_disclosure_v1",
                required=True,
                status="passed",
            ),
        ],
        metadata={},
    )


def _plan_bundle(tmp_path, kind: BacktestKind) -> BacktestPlanBundle:
    path = tmp_path / f"{kind.value}.json"
    path.write_text(json.dumps({"metric": [1.0, 1.0, 1.0]}), encoding="utf-8")
    return BacktestPlanBundle(
        contract_target=ContractCompatibilityTarget(
            contract_id=f"{kind.value}_bundle",
            contract_fqn="polisyos.tests.BacktestPlanBundle",
        ),
        required_fields=["metric"],
        holdout_windows=["2024-Q4"],
        plans=[
            HistoricalValidationPlan(
                plan_id=f"{kind.value}_plan",
                historical_data_path=str(path),
                ground_truth_outcomes={"metric": [1.0, 1.0]},
                target_metrics=["metric"],
                prediction_source=PredictionSource.PROVIDED,
                predicted_outcomes={"metric": [0.98, 1.02]},
            )
        ],
        historical_payloads={"metric": {"values": [1.0, 1.0, 1.0]}},
    )


def _utility_report() -> DownstreamUtilityReport:
    return DownstreamUtilityReport(
        scores=[
            HypothesisUtilityScore(
                hypothesis_id="h1",
                identification_status="identified",
                identifiability_score=1.0,
                stability_score=0.8,
                transportability_score=0.82,
                composite_score=0.9,
                rank=1,
            )
        ],
        recommended_shortlist=["h1"],
    )


def _interference_report() -> NetworkInterferenceReport:
    return NetworkInterferenceReport(
        method=InterferenceMethod.PARTIAL_IPW,
        status="success",
        effects=InterferenceEffectDecomposition(
            direct_effect=0.1,
            spillover_effect=0.02,
            total_effect=0.12,
            n_units=8,
            n_treated=3,
        ),
        exposure_mapping=ExposureMappingType.FRACTIONAL,
        n_units=8,
        n_treated=3,
    )


def _accountability_input() -> GovernanceAccountabilityInput:
    return GovernanceAccountabilityInput(
        candidate_id="candidate_policy",
        model_name="policy_classifier",
        model_version="2026.04",
        intended_use="promotion_gate",
        evaluation_split="holdout",
        dataset_name="policy_holdout",
        dataset_version="v1",
        data_sources=["holdout_snapshot"],
        predicted_scores=[0.95, 0.80, 0.70, 0.40, 0.65, 0.55, 0.35, 0.10],
        observed_outcomes=[1.0, 1.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0],
        protected_attributes={
            "gender": ["F", "F", "F", "F", "M", "M", "M", "M"],
            "region": ["urban", "urban", "rural", "rural", "urban", "urban", "rural", "rural"],
        },
        causal_fairness_report=CausalFairnessReport(
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
            recommendation="Direct discrimination remains above threshold.",
        ),
        tail_risk_summary=TailRiskDeltaSummary(
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
        ),
    )


def test_calibration_validation_runner_executes_backtest_stress_leaderboard_and_lesson(
    tmp_path,
    cas_store,
) -> None:
    registry = LessonRegistry(root=tmp_path / "registry" / "lessons", store=cas_store)
    runner = CalibrationValidationRunner(cas_store)
    result = runner.run(
        CalibrationValidationRunnerInput(
            run_id="R_c5b_full",
            candidate_ref=_artifact_ref("a"),
            governance_report=_governance_report(),
            calibration_fit_score=0.91,
            backtest_plan_bundles={kind: _plan_bundle(tmp_path, kind) for kind in BacktestKind},
            specification_curve_input=SpecificationCurveInput(
                specification_ids=["s1", "s2", "s3"],
                estimates=[0.3, 0.28, 0.32],
                standard_errors=[0.1, 0.1, 0.1],
            ),
            downstream_utility_report=_utility_report(),
            network_interference_report=_interference_report(),
            interference_certificate=InterferenceCertificate(
                supported_query_family="spillover",
                fallback_mode="pairwise",
                reduction_error_bound=0.05,
            ),
            strategic_summary={
                "fallback_mode": "exact_equilibrium",
                "closure_summary": {"mode": "exact_equilibrium", "equilibrium_count": 1},
                "multiplicity_note": "disclosed",
            },
            baseline_metrics={"policy_value": 100.0, "coverage": 0.9},
            lesson_registry=registry,
            accountability_input=_accountability_input(),
        )
    )

    assert result.bundle_ref.kind == "scientist.calibration_validation_bundle"
    assert result.bundle.status == "completed"
    assert result.bundle.backtest_matrix is not None
    assert result.bundle.stress_scenarios is not None
    assert result.bundle.leaderboard_entry is not None
    assert result.bundle.lesson_card_ref is not None
    assert result.bundle.governance_accountability_ref is not None
    assert result.bundle.governance_accountability_summary["risk_weighted_verdict"] == "human_gate"

    stored = load_calibration_validation_bundle(cas_store, result.bundle_ref)
    assert stored.readout_summary()["composite_score"] is not None
    assert stored.readout_summary()["accountability_ref"] is not None
    assert stored.readout_summary()["requires_human_review"] is True
    assert stored.readout_summary()["escalation_triggers"]
    assert stored.readout_summary()["accountability_summary"]["requires_human_review"] is True

    card = load_lesson_card(cas_store, result.bundle.lesson_card_ref)
    assert card.stage_name == "calibration_validation"
    hits = registry.query(LessonQuery(source_run_id="R_c5b_full", limit=5))
    assert any(hit.lesson_id == card.lesson_id for hit in hits)


def test_calibration_validation_runner_blocks_eligibility_on_missing_transport_and_interference(
    tmp_path,
    cas_store,
) -> None:
    runner = CalibrationValidationRunner(cas_store)
    result = runner.run(
        CalibrationValidationRunnerInput(
            run_id="R_c5b_gaps",
            candidate_ref=_artifact_ref("b"),
            governance_report=_governance_report(),
            calibration_fit_score=0.9,
            backtest_plan_bundles={kind: _plan_bundle(tmp_path, kind) for kind in BacktestKind},
            baseline_metrics={"policy_value": 100.0},
        )
    )

    metrics = result.bundle.leaderboard_entry.metrics
    assert "missing_metric:transportability_score" in metrics.gap_flags
    assert "missing_metric:interference_fit" in metrics.gap_flags
    assert metrics.eligible_for_promotion is False
