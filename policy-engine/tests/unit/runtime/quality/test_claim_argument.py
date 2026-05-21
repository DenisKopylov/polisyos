from __future__ import annotations

# ruff: noqa: S101
import polisyos.runtime.quality as runtime_quality
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.runtime.quality.claim_argument import (
    CLAIM_ARGUMENT_MAPPING_SCHEMA_VERSION,
    build_pre_publication_challenge_node,
    build_pre_publication_challenge_node_from_scientist_outputs,
    export_claim_argument_case_mapping,
    validate_claim_argument_case_surfaces,
)
from polisyos.scientist.methods.doe.designs import AdversarialPlan, ParameterSpec
from polisyos.scientist.methods.doe.stress_report import StressTestReport
from polisyos.scientist.policy_design.adversary import (
    AdversarialScenarioBundle,
    AdversaryExecutionResult,
)
from polisyos.scientist.policy_design.critic import ConstraintCritique
from polisyos.scientist.policy_design.objectives import PolicyEvaluationVector
from polisyos.scientist.policy_design.search import (
    HierarchicalSearchResult,
    HierarchicalSearchState,
)
from tests._helpers.hds_quality import sha


def test_claim_argument_export_maps_major_claim_surfaces_to_sacm_cae_gsn() -> None:
    case = _claim_argument_case()

    exported = export_claim_argument_case_mapping(case)

    assert exported["schema_version"] == CLAIM_ARGUMENT_MAPPING_SCHEMA_VERSION
    assert exported["standards"] == ["SACM", "CAE", "GSN"]
    assert exported["summary"]["major_claim_count"] == 1
    assert exported["summary"]["issue_count"] == 0

    major_claim = exported["major_claims"][0]
    assert major_claim["claim_id"] == "rec_1"
    assert major_claim["sacm"]["claim"] == "claim-node-rec-1"
    assert major_claim["cae"]["warrant"] == ["warrant-rec-1"]
    assert major_claim["cae"]["counter_evidence"] == ["counter-evidence-rec-1"]
    assert major_claim["gsn"]["strategy"] == ["arg-rec-1"]
    assert major_claim["gsn"]["justification"] == ["warrant-rec-1"]


def test_claim_argument_validation_projects_deficits_as_semantic_limitations() -> None:
    result = validate_claim_argument_case_surfaces(_claim_argument_case())

    assert result.status == "pass"
    assert result.major_claims[0]["limitation_refs"] == ["deficit-assessment-rec-1"]
    assert result.as_dict()["major_claims"][0]["semantic_binding_refs"][
        "limitation_refs"
    ] == ["deficit-assessment-rec-1"]


def test_claim_argument_missing_surfaces_export_semantic_closure_codes() -> None:
    case = _claim_argument_case()
    case["arguments"] = []
    case["warrants"] = []
    case["rebuttals"] = []
    case["counter_evidence"] = []
    case["assurance_deficits"] = []

    payload = validate_claim_argument_case_surfaces(case).as_dict()

    semantic_codes = {
        issue["semantic_binding_issue_code"]
        for issue in payload["semantic_binding_issues"]
    }
    assert {
        "semantic_major_claim_argument_refs_missing",
        "semantic_major_claim_warrant_refs_missing",
        "semantic_major_claim_rebuttal_refs_missing",
        "semantic_major_claim_counter_evidence_refs_missing",
        "semantic_major_claim_limitation_refs_missing",
    } <= semantic_codes


def test_claim_argument_surfaces_are_public_runtime_quality_api() -> None:
    assert runtime_quality.validate_claim_argument_case_surfaces is (
        validate_claim_argument_case_surfaces
    )
    assert runtime_quality.export_claim_argument_case_mapping is (
        export_claim_argument_case_mapping
    )
    assert runtime_quality.build_pre_publication_challenge_node is (
        build_pre_publication_challenge_node
    )
    assert runtime_quality.build_pre_publication_challenge_node_from_scientist_outputs is (
        build_pre_publication_challenge_node_from_scientist_outputs
    )


def test_pre_publication_challenge_builder_wires_scientist_outputs() -> None:
    challenge = build_pre_publication_challenge_node(
        challenge_id="requester-capture-rec-1",
        claim_id="rec_1",
        requester_preferred_conclusion="expand credit support",
        independent_analysis_conclusion="targeted credit support is conditionally justified",
        independent_alternative_analyses=[
            {
                "alternative_id": "baseline-no-action",
                "conclusion": "no action has lower fiscal risk but worse survival impact",
                "evidence_refs": [sha("1")],
            },
            {
                "alternative_id": "untargeted-subsidy",
                "conclusion": "untargeted subsidy is rejected on distributional grounds",
                "evidence_refs": [sha("2")],
            },
        ],
        policy_design_adversary_refs=[sha("3")],
        policy_design_critic_refs=[sha("4")],
        policy_design_objective_refs=[sha("5")],
        policy_design_search_refs=[sha("6")],
        backtesting_adversarial_refs=[sha("7")],
        evidence_ref=sha("8"),
        runtime_event_ref=sha("9"),
    )

    assert challenge["node_type"] == "requester_capture_challenge"
    assert challenge["node_family"] == "pre_publication_challenge"
    assert challenge["challenge_result"] == "passed"
    assert challenge["scientist_output_refs"] == {
        "policy_design_adversary_refs": [sha("3")],
        "policy_design_critic_refs": [sha("4")],
        "policy_design_objective_refs": [sha("5")],
        "policy_design_search_refs": [sha("6")],
        "backtesting_adversarial_refs": [sha("7")],
    }
    assert challenge["adversarial_output_refs"] == [
        sha("3"),
        sha("4"),
        sha("5"),
        sha("6"),
        sha("7"),
    ]


def test_pre_publication_challenge_builder_projects_typed_scientist_outputs() -> None:
    adversary_result = AdversaryExecutionResult(
        scenario_bundle=AdversarialScenarioBundle(candidate_id="policy-candidate-1"),
        compiled_plan=AdversarialPlan(
            parameter_specs=[ParameterSpec(name="benefit_rate", lower_bound=0.0, upper_bound=1.0)]
        ),
        stress_test_report=StressTestReport(
            report_id="stress-report-1",
            cas_artifact_id=sha("8"),
        ),
        adversary_bundle_ref=_artifact_ref(sha("3"), kind="scientist.policy_adversary_bundle"),
        stress_test_report_ref=_artifact_ref(sha("7"), kind="scientist.stress_test_report"),
    )
    critic = ConstraintCritique(
        candidate_id="policy-candidate-1",
        passed=True,
        metadata={"artifact_ref": sha("4")},
    )
    objectives = PolicyEvaluationVector(
        candidate_id="policy-candidate-1",
        metadata={"artifact_ref": sha("5")},
    )
    search = HierarchicalSearchResult(
        state=HierarchicalSearchState(),
        shared_frontier=[{"artifact_ref": sha("6")}],
    )

    challenge = build_pre_publication_challenge_node_from_scientist_outputs(
        challenge_id="requester-capture-rec-1",
        claim_id="rec_1",
        requester_preferred_conclusion="expand credit support",
        independent_analysis_conclusion="targeted credit support is conditionally justified",
        independent_alternative_analyses=[
            {
                "alternative_id": "baseline-no-action",
                "conclusion": "no action has lower fiscal risk but worse survival impact",
                "evidence_refs": [sha("1")],
            },
            {
                "alternative_id": "untargeted-subsidy",
                "conclusion": "untargeted subsidy is rejected on distributional grounds",
                "evidence_refs": [sha("2")],
            },
        ],
        policy_design_adversary_output=adversary_result,
        policy_design_critic_output=critic,
        policy_design_objectives_output=objectives,
        policy_design_search_output=search,
        backtesting_adversarial_output=adversary_result,
        evidence_ref=sha("9"),
        runtime_event_ref=sha("0"),
    )

    assert challenge["challenge_result"] == "passed"
    assert challenge["scientist_output_refs"] == {
        "policy_design_adversary_refs": [sha("3")],
        "policy_design_critic_refs": [sha("4")],
        "policy_design_objective_refs": [sha("5")],
        "policy_design_search_refs": [sha("6")],
        "backtesting_adversarial_refs": [sha("7")],
    }
    assert validate_claim_argument_case_surfaces(
        {
            **_claim_argument_case(),
            "requester_capture_challenges": [challenge],
        }
    ).status == "pass"


def test_requester_capture_challenge_rejects_prior_confirmation_without_alternatives() -> None:
    case = _claim_argument_case()
    challenge = dict(case["requester_capture_challenges"][0])
    challenge.update(
        {
            "challenge_result": "passed",
            "requester_preferred_conclusion": "expand credit support",
            "independent_analysis_conclusion": "expand credit support",
            "independent_alternative_analyses": [],
            "scientist_output_refs": {},
        }
    )
    case["requester_capture_challenges"] = [challenge]

    result = validate_claim_argument_case_surfaces(case)

    assert result.status == "fail"
    assert {
        "policy_design_requester_capture_independent_alternatives_missing",
        "policy_design_challenge_policy_adversary_ref_missing",
        "policy_design_challenge_policy_critic_ref_missing",
        "policy_design_challenge_policy_objectives_ref_missing",
        "policy_design_challenge_policy_search_ref_missing",
        "policy_design_challenge_backtesting_adversarial_ref_missing",
    } <= {issue.code for issue in result.issues}


def test_requester_capture_challenge_failed_result_blocks_claim_acceptance() -> None:
    case = _claim_argument_case()
    challenge = dict(case["requester_capture_challenges"][0])
    challenge["challenge_result"] = "failed"
    case["requester_capture_challenges"] = [challenge]

    result = validate_claim_argument_case_surfaces(case)

    assert result.status == "fail"
    assert {
        issue.code for issue in result.issues
    } >= {"policy_design_requester_capture_challenge_failed"}


def test_requester_capture_challenge_rejects_alternatives_that_repeat_requester_prior() -> None:
    case = _claim_argument_case()
    challenge = dict(case["requester_capture_challenges"][0])
    challenge.update(
        {
            "requester_preferred_conclusion": "expand credit support",
            "independent_analysis_conclusion": "expand credit support",
            "independent_alternative_analyses": [
                {
                    "alternative_id": "alt-confirm-1",
                    "conclusion": "expand credit support",
                    "evidence_refs": [sha("11")],
                },
                {
                    "alternative_id": "alt-confirm-2",
                    "conclusion": "expand credit support",
                    "evidence_refs": [sha("12")],
                },
            ],
        }
    )
    case["requester_capture_challenges"] = [challenge]

    result = validate_claim_argument_case_surfaces(case)

    assert result.status == "fail"
    assert {
        issue.code for issue in result.issues
    } >= {
        "policy_design_requester_capture_independent_alternatives_missing",
        "policy_design_requester_capture_independent_analysis_confirms_prior",
    }


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


def _artifact_ref(artifact_id: str, *, kind: str) -> ArtifactRef:
    return ArtifactRef(
        artifact_id=artifact_id,
        kind=kind,
        media_type="application/json",
    )
