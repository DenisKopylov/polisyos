from __future__ import annotations

import pandas as pd

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.analytics.fairness_audit_report import (
    load_fairness_audit_report,
    persist_fairness_audit_report,
)
from polisyos.ir.governance.validation import ValidationReport
from polisyos.scientist.validation.fairness_audit import (
    CausalFairnessSpec,
    FairnessAuditConfig,
    FairnessAuditRunner,
    FairnessThreshold,
    IntersectionalConfig,
    ProtectedAttributeConfig,
    StatisticalTestsConfig,
    fairness_gate_response,
    predict_with_fairness_gate,
)


def _config(*, causal_required: bool = False) -> FairnessAuditConfig:
    thresholds = {
        "demographic_parity_gap": FairnessThreshold(
            max_abs_gap=0.05,
            min_ratio=0.80,
            blocking=True,
        ),
        "selection_rate": FairnessThreshold(max_abs_gap=0.05, min_ratio=0.80, blocking=True),
        "equalized_odds_gap": FairnessThreshold(max_abs_gap=0.50, blocking=False),
        "false_negative_rate": FairnessThreshold(max_abs_gap=0.50, blocking=False),
        "true_positive_rate": FairnessThreshold(max_abs_gap=0.50, blocking=False),
        "false_positive_rate": FairnessThreshold(max_abs_gap=0.50, blocking=False),
        "positive_predictive_value": FairnessThreshold(max_abs_gap=0.50, blocking=False),
        "calibration_error_by_group": FairnessThreshold(max_abs_gap=0.50, blocking=False),
        "counterfactual_fairness": FairnessThreshold(
            mean_abs_score_delta_max=0.02,
            p95_abs_score_delta_max=0.05,
            flip_rate_max=0.01,
            blocking=True,
        ),
        "path_specific_fairness": FairnessThreshold(
            max_forbidden_path_effect=0.02,
            blocking=True,
        ),
    }
    return FairnessAuditConfig(
        model_id="candidate",
        dataset_id="holdout",
        protected_attributes=[
            ProtectedAttributeConfig(
                name="gender",
                reference="configured",
                reference_value="man",
                required=True,
            )
        ],
        thresholds=thresholds,
        statistical_tests=StatisticalTestsConfig(
            bootstrap_resamples=100,
            random_seed=7,
            multiple_comparison_correction="holm",
        ),
        min_group_n=20,
        min_effective_n=20,
        causal_spec_required=causal_required,
        high_impact=True,
        require_pass_to_deploy=True,
    )


def test_fairness_audit_refuses_large_group_selection_gap() -> None:
    protected = pd.DataFrame({"gender": ["woman"] * 120 + ["man"] * 120})
    y_pred = [1] * 72 + [0] * 48 + [1] * 36 + [0] * 84
    y_true = [1, 0] * 120
    y_score = [0.8 if pred else 0.2 for pred in y_pred]

    result = FairnessAuditRunner(_config()).run(
        y_true=y_true,
        y_pred=y_pred,
        y_score=y_score,
        protected=protected,
    )
    audit = result.to_validation_report()

    assert audit["status"] == "REFUSE"
    assert audit["deployable"] is False
    assert audit["auto_decision_allowed"] is False
    selection_test = next(
        test
        for test in audit["parity_tests"]
        if test["test_id"] == "gender.selection_rate.woman_vs_man"
    )
    assert selection_test["status"] == "FAIL"
    assert selection_test["decision"] == "fail"
    assert selection_test["alpha"] == 0.05
    assert selection_test["correction"] == "holm"
    assert selection_test["abs_estimate"] == 0.3
    dp_gap = next(test for test in audit["parity_tests"] if test["metric"] == "demographic_parity_gap")
    assert dp_gap["status"] == "FAIL"
    woman_metrics = next(
        entry for entry in audit["group_metrics"] if entry["attribute"] == "gender" and entry["group"] == "woman"
    )
    assert woman_metrics["metrics"]["selection_rate"]["estimate"] == 0.6


def test_fairness_audit_records_causal_estimands_and_refuses_forbidden_path() -> None:
    protected = pd.DataFrame({"gender": ["woman"] * 80 + ["man"] * 80})
    y_pred = [1, 0] * 80
    y_true = [1, 0] * 80
    y_score = [0.7 if pred else 0.3 for pred in y_pred]
    woman_scores = [score + 0.005 for score in y_score[:80]]
    causal_spec = CausalFairnessSpec(
        protected_attribute="gender",
        counterfactual_pairs=[("woman", "man")],
        counterfactual_scores={"gender:woman->man": woman_scores},
        counterfactual_predictions={"gender:woman->man": y_pred[:80]},
        assumptions=["SCM supplied by validation owner"],
        forbidden_paths=[["gender", "historical_manager_rating", "automated_decision"]],
        path_effects=[
            {
                "path": ["gender", "historical_manager_rating", "automated_decision"],
                "estimate": 0.031,
                "ci_low": 0.025,
                "ci_high": 0.044,
                "p_value": 0.006,
                "p_value_adjusted": 0.018,
                "blocking": True,
            }
        ],
    )

    result = FairnessAuditRunner(_config(causal_required=True)).run(
        y_true=y_true,
        y_pred=y_pred,
        y_score=y_score,
        protected=protected,
        causal_spec=causal_spec,
    )
    audit = result.to_validation_report()

    assert audit["status"] == "REFUSE"
    assert audit["causal_audits"]["counterfactual_fairness"]["status"] == "PASS"
    assert audit["causal_audits"]["path_specific_fairness"]["status"] == "FAIL"
    assert "FORBIDDEN_PATH_EFFECT_EXCEEDS_THRESHOLD" in audit["refusal_policy"]["reason_codes"]


def test_score_only_audit_marks_error_metrics_not_computable_without_labels() -> None:
    protected = pd.DataFrame({"gender": ["woman"] * 2500 + ["man"] * 2500})
    y_pred = [1, 0] * 2500
    y_score = [0.7 if pred else 0.3 for pred in y_pred]

    result = FairnessAuditRunner(_config()).run(
        y_true=None,
        y_pred=y_pred,
        y_score=y_score,
        protected=protected,
    )
    audit = result.to_validation_report()

    assert audit["status"] == "PASS"
    woman_metrics = next(
        entry
        for entry in audit["group_metrics"]
        if entry["attribute"] == "gender" and entry["group"] == "woman"
    )
    assert woman_metrics["metrics"]["selection_rate"]["status"] == "PASS"
    assert woman_metrics["metrics"]["false_positive_rate"]["status"] == "NOT_COMPUTABLE"


def test_intersectional_sparsity_refuses_high_impact_automation() -> None:
    protected = pd.DataFrame(
        {
            "gender": ["woman"] * 30 + ["man"] * 30,
            "race_ethnicity": ["a"] * 15 + ["b"] * 15 + ["a"] * 15 + ["b"] * 15,
        }
    )
    config = _config().model_copy(
        update={
            "protected_attributes": [
                ProtectedAttributeConfig(name="gender", reference_value="man", required=True),
                ProtectedAttributeConfig(name="race_ethnicity", required=True),
            ],
            "min_group_n": 20,
            "intersectional": IntersectionalConfig(enabled=True, max_order=2, min_group_n=20),
        }
    )

    result = FairnessAuditRunner(config).run(
        y_true=[1, 0] * 30,
        y_pred=[1, 0] * 30,
        y_score=[0.8, 0.2] * 30,
        protected=protected,
    )
    audit = result.to_validation_report()

    assert audit["status"] == "REFUSE"
    assert any(group["attribute"] == "gender x race_ethnicity" for group in audit["input_summary"]["groups"])
    assert "FAIRNESS_AUDIT_UNDERPOWERED" in audit["refusal_policy"]["reason_codes"]


def test_counterfactual_residual_scm_fallback_runs_from_features() -> None:
    protected = pd.DataFrame({"gender": ["woman"] * 80 + ["man"] * 80})
    features = pd.DataFrame({"qualification": [0.2, 0.8] * 80})
    y_score = [0.72 if gender == "woman" else 0.28 for gender in protected["gender"]]
    y_pred = [score >= 0.5 for score in y_score]
    config = _config(causal_required=True).model_copy(
        update={
            "thresholds": {
                **_config(causal_required=True).thresholds,
                "path_specific_fairness": FairnessThreshold(
                    max_forbidden_path_effect=0.02,
                    blocking=False,
                ),
            }
        }
    )
    causal_spec = CausalFairnessSpec(
        protected_attribute="gender",
        estimator="residual_scm",
        counterfactual_pairs=[("woman", "man")],
        covariate_columns=["qualification"],
    )

    result = FairnessAuditRunner(config).run(
        y_true=[1, 0] * 80,
        y_pred=y_pred,
        y_score=y_score,
        protected=protected,
        features=features,
        causal_spec=causal_spec,
    )
    audit = result.to_validation_report()

    cf = audit["causal_audits"]["counterfactual_fairness"]
    assert cf["estimator"] == "residual_scm_linear_bootstrap"
    assert cf["status"] == "FAIL"
    assert audit["status"] == "REFUSE"


def test_path_specific_overlap_diagnostic_blocks_causal_claim() -> None:
    protected = pd.DataFrame({"gender": ["woman"] * 80 + ["man"] * 80})
    causal_spec = CausalFairnessSpec(
        protected_attribute="gender",
        forbidden_paths=[["gender", "automated_decision"]],
        path_effects=[
            {
                "path": ["gender", "automated_decision"],
                "estimate": 0.001,
                "ci_low": 0.0,
                "ci_high": 0.003,
            }
        ],
        diagnostics={"positivity_min": 0.001, "positivity_max": 0.92},
    )

    result = FairnessAuditRunner(_config(causal_required=True)).run(
        y_true=[1, 0] * 80,
        y_pred=[1, 0] * 80,
        y_score=[0.8, 0.2] * 80,
        protected=protected,
        causal_spec=causal_spec,
    )
    audit = result.to_validation_report()

    assert audit["causal_audits"]["path_specific_fairness"]["diagnostics"]["overlap_status"] == "FAIL"
    assert "CAUSAL_OVERLAP_DIAGNOSTIC_FAILED" in audit["refusal_policy"]["reason_codes"]


def test_fairness_audit_report_persists_roundtrip(tmp_path) -> None:
    protected = pd.DataFrame({"gender": ["woman"] * 60 + ["man"] * 60})
    result = FairnessAuditRunner(_config()).run(
        y_true=[1, 0] * 60,
        y_pred=[1, 0] * 60,
        y_score=[0.8, 0.2] * 60,
        protected=protected,
    )
    store = FileSystemCAS(tmp_path)

    ref = persist_fairness_audit_report(store, result.report)
    loaded = load_fairness_audit_report(store, ref)

    assert ref.kind == "scientist.fairness_audit_report"
    assert loaded == result.report


def test_runtime_gate_blocks_all_automation_when_report_refuses() -> None:
    report = {
        "fairness_audit": {
            "status": "REFUSE",
            "auto_decision_allowed": False,
            "audit_id": "validation_report_2026_04_26_001",
            "refusal_policy": {
                "runtime_behavior": {
                    "fallback": "human_review_or_approved_fallback_policy",
                    "message_code": "FAIRNESS_AUDIT_BLOCK",
                }
            },
        }
    }

    blocked = fairness_gate_response(report)

    assert blocked == {
        "decision": None,
        "status": "refused",
        "code": "FAIRNESS_AUDIT_BLOCK",
        "message": (
            "Automated decision is unavailable because the latest fairness audit found a "
            "protected-group or causal-fairness gap above the configured threshold."
        ),
        "fallback": "human_review_or_approved_fallback_policy",
        "report_id": "validation_report_2026_04_26_001",
    }


def test_predict_with_fairness_gate_allows_passing_report() -> None:
    class Model:
        def predict(self, features):
            return {"decision": "approved", "features": features}

    result = predict_with_fairness_gate(
        Model(),
        {"features": {"x": 1}},
        {"fairness_audit": {"status": "PASS", "auto_decision_allowed": True}},
    )

    assert result == {"decision": "approved", "features": {"x": 1}}


def test_validation_report_accepts_embedded_fairness_audit() -> None:
    report = ValidationReport(
        error_summary="No validation issues.",
        issues=[],
        fairness_audit={
            "version": "1.0.0",
            "status": "PASS",
            "deployable": True,
            "auto_decision_allowed": True,
            "audit_id": "fairness_audit_test",
        },
    )

    assert report.fairness_audit["status"] == "PASS"
