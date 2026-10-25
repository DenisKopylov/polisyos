from __future__ import annotations

# ruff: noqa: S101
import builtins
from datetime import UTC, datetime

from polisyos.berl import persist_explanation_bundle
from polisyos.berl.contracts.explanation_bundle import ExplanationBundle
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.runtime.quality.claim_argument import validate_claim_argument_case_surfaces
from polisyos.runtime.quality.explanation_reliability import (
    evaluate_warrant_berl_reliability,
)


def _selected_bundle_case(tmp_path):
    store = FileSystemCAS(tmp_path / "selected-explanation-cas")
    bundle = ExplanationBundle.model_validate(
        {
            "bundle_id": "bundle-claim-a",
            "created_at": datetime(2026, 10, 22, tzinfo=UTC).isoformat(),
            "model": {
                "model_id": "policy-model",
                "model_hash": "sha256:model",
                "model_class": "linear",
            },
            "prediction": {
                "prediction_id": "prediction-claim-a",
                "row_id": "row-claim-a",
                "output_name": "claim_acceptance",
                "output_scale": "probability",
                "raw_score": 0.72,
            },
            "feature_context": {
                "feature_values_ref": "sha256:features",
                "feature_schema_version": "features-v1",
            },
            "assumptions": {
                "perturbation_distribution": {"name": "empirical"},
                "feature_dependence_policy": {"primary": "marginal"},
            },
            "methods": [
                {
                    "method_id": "kernel_shap",
                    "params": {"seed": 7},
                    "assumptions": {"feature_removal": "marginal"},
                    "infidelity": {
                        "point_estimate": 0.01,
                        "upper_bound": 0.02,
                        "confidence": 0.95,
                        "n_eval_perturbations": 64,
                        "residual_cap": 1.0,
                        "bound_type": "empirical_bernstein_heldout",
                    },
                }
            ],
            "audit": {"code_version": "test"},
        }
    )
    bundle_ref = persist_explanation_bundle(store, bundle)
    reliability = {
        "reliability_id": "reliability-claim-a",
        "claim_id": "claim-a",
        "warrant_id": "warrant-a",
        "evidence_ref": "sha256:" + "1" * 64,
        "explanation_bundle_ref": bundle_ref.model_dump_json(),
        "validation_thresholds": {"max_p95_infidelity_upper_bound": 0.1},
    }
    warrant = {
        "warrant_id": "warrant-a",
        "claim_id": "claim-a",
        "warrant_text": "The explanation is locally faithful under the measured perturbation.",
        "assumptions": ["Declared perturbation support applies."],
        "applicability_limits": ["Local explanation only."],
        "explanation_trust_affects_acceptance": True,
        "berl_reliability_refs": ["reliability-claim-a"],
    }
    case = {
        "effective_execution_profile": "production",
        "final_major_claims": [
            {
                "claim_id": "claim-a",
                "major": True,
                "warrant_refs": ["warrant-a"],
            }
        ],
        "warrants": [warrant],
        "warrant_reliability_records": [reliability],
    }
    return store, case, warrant


def test_passing_explanation_metrics_do_not_fill_missing_claim_argument_surfaces(tmp_path) -> None:
    store, case, warrant = _selected_bundle_case(tmp_path)

    evaluation = evaluate_warrant_berl_reliability(
        case,
        warrant,
        claim_id="claim-a",
        artifact_store=store,
    )
    validation = validate_claim_argument_case_surfaces(case, artifact_store=store)

    assert len(evaluation.records) == 1
    normalized = evaluation.records[0]
    assert normalized["candidate_diagnostics"]["source"] == "selected_cas_bundle"
    assert normalized["candidate_diagnostics"]["threshold_decision"]["status"] == "pass"
    assert normalized["threshold_decision"]["status"] == "fail"
    assert {
        "policy_design_warrant_berl_subject_context_not_established",
    } <= {issue.code for issue in evaluation.issues}
    assert validation.status == "fail"
    assert {
        "policy_design_major_claim_argument_missing",
        "policy_design_major_claim_rebuttal_missing",
        "policy_design_major_claim_counter_evidence_missing",
    } <= {issue.code for issue in validation.issues}


def test_selected_bundle_import_failure_fails_closed(tmp_path, monkeypatch) -> None:
    store, case, warrant = _selected_bundle_case(tmp_path)
    actual_import = builtins.__import__

    def fail_berl_import(name, *args, **kwargs):
        if name == "polisyos.berl":
            raise ImportError("simulated BERL package import failure")
        return actual_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fail_berl_import)

    evaluation = evaluate_warrant_berl_reliability(
        case,
        warrant,
        claim_id="claim-a",
        artifact_store=store,
    )

    assert len(evaluation.records) == 1
    assert evaluation.records[0]["threshold_decision"]["status"] == "fail"
    assert {
        "policy_design_warrant_berl_bundle_store_read_unavailable",
    } <= {issue.code for issue in evaluation.issues}
