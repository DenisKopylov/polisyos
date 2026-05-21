from __future__ import annotations

# ruff: noqa: S101
from datetime import UTC, datetime

import pytest

from polisyos.runtime.quality.claim_argument import validate_claim_argument_case_surfaces
from polisyos.runtime.quality.explanation_reliability import (
    build_berl_warrant_reliability_record,
)
from tests._helpers.hds_quality import sha


@pytest.mark.parametrize(
    "reliability_flag",
    [
        "explanation_reliability_affects_reviewer_trust",
        "explanation_trust_affects_acceptance",
        "explanation_reliability_affects_user_facing_confidence",
    ],
)
def test_warrant_requires_berl_refs_when_reliability_affects_trust_surface(
    reliability_flag: str,
) -> None:
    case = _claim_argument_case()
    warrant = dict(case["warrants"][0])
    warrant[reliability_flag] = True
    warrant["berl_reliability_refs"] = []
    case["warrants"] = [warrant]

    result = validate_claim_argument_case_surfaces(case)

    assert result.status == "fail"
    assert {
        issue.code for issue in result.issues
    } >= {"policy_design_warrant_berl_refs_missing"}


def test_warrant_reliability_record_blocks_failed_berl_thresholds() -> None:
    case = _claim_argument_case()
    warrant = dict(case["warrants"][0])
    warrant["explanation_trust_affects_acceptance"] = True
    warrant["berl_reliability_refs"] = ["berl-reliability-rec-1"]
    case["warrants"] = [warrant]
    case["warrant_reliability_records"] = [
        {
            "reliability_id": "berl-reliability-rec-1",
            "claim_id": "rec_1",
            "warrant_id": "warrant-rec-1",
            "evidence_ref": sha("9"),
            "explanation_bundle_ref": sha("a"),
            "validation_thresholds": {"max_p95_infidelity_upper_bound": 0.02},
            "explanation_bundle": _berl_bundle(upper_bound=0.08),
        }
    ]

    result = validate_claim_argument_case_surfaces(case)

    assert result.status == "fail"
    assert {
        issue.code for issue in result.issues
    } >= {"policy_design_warrant_berl_threshold_failed"}


def test_warrant_reliability_ref_must_resolve_to_a_record() -> None:
    case = _claim_argument_case()
    warrant = dict(case["warrants"][0])
    warrant["explanation_trust_affects_acceptance"] = True
    warrant["berl_reliability_refs"] = ["missing-berl-reliability-rec"]
    case["warrants"] = [warrant]

    result = validate_claim_argument_case_surfaces(case)

    assert result.status == "fail"
    assert {
        issue.code for issue in result.issues
    } >= {"policy_design_warrant_berl_reliability_record_missing"}


def test_warrant_reliability_record_must_carry_bundle_thresholds_bounds_and_infidelity() -> None:
    case = _claim_argument_case()
    warrant = dict(case["warrants"][0])
    warrant["explanation_trust_affects_acceptance"] = True
    warrant["berl_reliability_refs"] = ["berl-reliability-empty"]
    case["warrants"] = [warrant]
    case["warrant_reliability_records"] = [
        {
            "reliability_id": "berl-reliability-empty",
            "claim_id": "rec_1",
            "warrant_id": "warrant-rec-1",
        }
    ]

    result = validate_claim_argument_case_surfaces(case)

    assert result.status == "fail"
    assert {
        issue.code for issue in result.issues
    } >= {
        "policy_design_warrant_berl_bundle_ref_missing",
        "policy_design_warrant_berl_threshold_decision_missing",
        "policy_design_warrant_berl_empirical_bounds_missing",
        "policy_design_warrant_berl_local_infidelity_missing",
    }


def test_berl_warrant_reliability_record_can_be_built_without_argument_refs() -> None:
    record = build_berl_warrant_reliability_record(
        reliability_id="berl-reliability-rec-1",
        claim_id="rec_1",
        explanation_bundle_ref=sha("bundle"),
        evidence_ref=sha("evidence"),
        validation_thresholds={"max_p95_infidelity_upper_bound": 0.1},
        explanation_bundle=_berl_bundle(upper_bound=0.03),
    )

    assert record["reliability_id"] == "berl-reliability-rec-1"
    assert record["claim_id"] == "rec_1"
    assert "warrant_id" not in record
    assert record["threshold_decision"]["status"] == "pass"
    assert record["empirical_bounds"]
    assert record["local_infidelity_diagnostics"]


def _claim_argument_case() -> dict[str, object]:
    return {
        "effective_execution_profile": "production",
        "final_major_claims": [
            {
                "claim_id": "rec_1",
                "assurance_node_id": "claim-node-rec-1",
                "claim_ref": sha("a"),
                "major": True,
                "argument_refs": ["arg-rec-1"],
                "warrant_refs": ["warrant-rec-1"],
                "rebuttal_refs": ["rebuttal-rec-1"],
                "counter_evidence_refs": ["counter-evidence-rec-1"],
                "assurance_deficit_refs": ["deficit-assessment-rec-1"],
                "requester_capture_challenge_refs": ["requester-capture-rec-1"],
                "blocker_refs": [],
            }
        ],
        "arguments": [
            {
                "argument_id": "arg-rec-1",
                "claim_id": "rec_1",
                "strategy": "triangulated_policy_design_case",
                "evidence_refs": [sha("1"), sha("2")],
            }
        ],
        "warrants": [
            {
                "warrant_id": "warrant-rec-1",
                "claim_id": "rec_1",
                "warrant_text": "Runtime evidence supports the claim.",
                "assumptions": ["parallel trends remains plausible"],
                "applicability_limits": ["No extrapolation outside observed support"],
                "requires_explanation_reliability": False,
                "berl_reliability_refs": [],
            }
        ],
        "rebuttals": [
            {
                "rebuttal_id": "rebuttal-rec-1",
                "claim_id": "rec_1",
                "counter_evidence_refs": ["counter-evidence-rec-1"],
                "resolution": "counter-evidence assessed and bounded",
            }
        ],
        "counter_evidence": [
            {
                "counter_evidence_id": "counter-evidence-rec-1",
                "claim_id": "rec_1",
                "visibility": "reviewer_visible",
                "status": "assessed",
                "assessment_result": "bounded",
                "evidence_ref": sha("3"),
                "runtime_event_ref": sha("4"),
            }
        ],
        "assurance_deficits": [
            {
                "deficit_id": "deficit-assessment-rec-1",
                "claim_id": "rec_1",
                "deficit_kind": "no_unresolved_assurance_deficit",
                "status": "none",
                "evidence_ref": sha("5"),
                "runtime_event_ref": sha("6"),
            }
        ],
        "requester_capture_challenges": [
            {
                "challenge_id": "requester-capture-rec-1",
                "claim_id": "rec_1",
                "challenge_result": "passed",
                "requester_preferred_conclusion": "expand credit support",
                "independent_analysis_conclusion": (
                    "targeted credit support is conditionally justified"
                ),
                "independent_alternative_analyses": [
                    {
                        "alternative_id": "baseline-no-action",
                        "conclusion": (
                            "no action has lower fiscal risk but worse survival impact"
                        ),
                        "evidence_refs": [sha("1")],
                    },
                    {
                        "alternative_id": "untargeted-subsidy",
                        "conclusion": (
                            "untargeted subsidy is rejected on distributional grounds"
                        ),
                        "evidence_refs": [sha("2")],
                    },
                ],
                "scientist_output_refs": {
                    "policy_design_adversary_refs": [sha("3")],
                    "policy_design_critic_refs": [sha("4")],
                    "policy_design_objective_refs": [sha("5")],
                    "policy_design_search_refs": [sha("6")],
                    "backtesting_adversarial_refs": [sha("7")],
                },
                "adversarial_output_refs": [
                    sha("3"),
                    sha("4"),
                    sha("5"),
                    sha("6"),
                    sha("7"),
                ],
                "evidence_ref": sha("7"),
                "runtime_event_ref": sha("8"),
            }
        ],
        "nodes": [
            {
                "node_type": "claim",
                "node_id": "claim-node-rec-1",
                "claim_id": "rec_1",
                "claim_ref": sha("a"),
                "cas_ref": sha("a"),
                "runtime_event_ref": sha("e"),
                "runtime_authority_envelope": {
                    "authority_role": "producer_authority",
                    "provenance_kind": "runtime_emitted",
                },
            }
        ],
    }


def _berl_bundle(*, upper_bound: float) -> dict[str, object]:
    return {
        "bundle_id": "berl-bundle-1",
        "created_at": datetime(2026, 5, 18, tzinfo=UTC).isoformat(),
        "faithfulness_claim": "bounded",
        "display_policy": "limited",
        "model": {
            "model_id": "policy_model",
            "model_hash": sha("m"),
            "model_class": "gradient_boosted_trees",
            "training_data_hash": sha("d"),
        },
        "prediction": {
            "prediction_id": "prediction-1",
            "row_id": "case-1",
            "output_name": "claim_acceptance",
            "output_scale": "probability",
            "raw_score": 0.72,
            "display_score": 0.72,
            "decision_threshold": 0.65,
        },
        "feature_context": {
            "feature_values_ref": sha("f"),
            "feature_schema_version": "2026-05",
            "constraints_ref": sha("c"),
        },
        "assumptions": {
            "perturbation_distribution": {
                "name": "conditional_empirical_local",
                "radius": 0.2,
                "categorical_policy": "observed_support_only",
                "continuous_policy": "local_empirical_resampling",
                "support_constraints": sha("c"),
            },
            "feature_dependence_policy": {
                "primary": "conditional_observational",
                "alternatives_tested": ["marginal_interventional"],
                "causal_claim_made": False,
            },
            "background_data": {
                "dataset_ref": sha("b"),
                "n": 120,
                "sampling_policy": "fixed_fixture_sample",
            },
        },
        "redundancy": {"clusters": []},
        "methods": [
            {
                "method_id": "kernel_shap_conditional",
                "library": "berl-fixture",
                "library_version": "1.0.0",
                "params": {"coalition_samples": 64},
                "assumptions": {"feature_removal": "conditional_observational"},
                "attributions": [{"feature": "employment_rate", "value": 0.18}],
                "infidelity": {
                    "point_estimate": 0.01,
                    "upper_bound": upper_bound,
                    "confidence": 0.95,
                    "n_eval_perturbations": 64,
                    "residual_cap": 1.0,
                    "bound_type": "empirical_bernstein_heldout",
                    "evaluation_split": "heldout",
                },
            }
        ],
        "disagreement": {
            "methods_compared": ["kernel_shap_conditional"],
            "top_k": 1,
            "top_k_jaccard_median": 1.0,
            "kendall_tau_median": 1.0,
            "sign_conflict_features": [],
            "flags": [],
        },
        "validity": {
            "support_check": {
                "ood_rate_eval_perturbations": 0.01,
                "constraint_violation_rate": 0.0,
            },
            "use_restrictions": ["Local to declared perturbation support."],
        },
        "audit": {
            "code_version": "berl-fixture@sha256:code",
            "random_seeds": [7],
            "artifact_refs": [sha("r")],
        },
    }
