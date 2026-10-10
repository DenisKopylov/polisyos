from __future__ import annotations

# ruff: noqa: S101
from polisyos.runtime.quality.claim_argument import validate_claim_argument_case_surfaces
from polisyos.runtime.quality.explanation_reliability import (
    evaluate_warrant_berl_reliability,
)


def test_passing_explanation_metrics_do_not_fill_missing_claim_argument_surfaces() -> None:
    reliability = {
        "reliability_id": "reliability-claim-a",
        "claim_id": "claim-a",
        "warrant_id": "warrant-a",
        "evidence_ref": "sha256:" + "1" * 64,
        "explanation_bundle_ref": "sha256:" + "2" * 64,
        "validation_thresholds": {"max_p95_infidelity_upper_bound": 0.1},
        "threshold_decision": {"status": "pass", "violations": []},
        "empirical_bounds": [{"metric": "p95_infidelity", "upper_bound": 0.02}],
        "local_infidelity_diagnostics": [{"feature": "employment", "status": "bounded"}],
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

    evaluation = evaluate_warrant_berl_reliability(case, warrant, claim_id="claim-a")
    validation = validate_claim_argument_case_surfaces(case)

    assert not evaluation.issues
    assert evaluation.records[0]["threshold_decision"]["status"] == "pass"
    assert validation.status == "fail"
    assert {
        "policy_design_major_claim_argument_missing",
        "policy_design_major_claim_rebuttal_missing",
        "policy_design_major_claim_counter_evidence_missing",
    } <= {issue.code for issue in validation.issues}
