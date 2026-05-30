from __future__ import annotations

# ruff: noqa: S101
from copy import deepcopy

from polisyos.corpus import (
    EXPERT_ADJUDICATION_SCHEMA_VERSION,
    build_expert_adjudication_useful_design_gate,
    evaluate_expert_adjudication_manifest,
    expert_adjudication_json_schema,
)


def _base_manifest() -> dict[str, object]:
    return {
        "schema_version": EXPERT_ADJUDICATION_SCHEMA_VERSION,
        "manifest_id": "w11c-deep-pilot-housing-001",
        "phase_id": "W11.C",
        "case_id": "housing-rent-stabilization-001",
        "case_ref": (
            "repo://docs/research/universal-policy-design/outcome-corpus/"
            "cases/housing-rent-stabilization-001.md"
        ),
        "decomposition_ref": (
            "repo://docs/research/universal-policy-design/outcome-corpus/"
            "annotations/housing-rent-stabilization-001.json"
        ),
        "authority_level": "governed",
        "domain_id": "housing",
        "research_refs": ["E1", "E22", "E24", "C30"],
        "pattern_ids": ["P05", "P10", "P15"],
        "expected_claim_ids": ["claim-rent-burden", "claim-legal-competence"],
        "reviewer_topology": {
            "corpus_slice": "deep_pilot",
            "topology_mode": "deep_pilot_overlap",
            "annotation_guide_ref": (
                "repo://docs/research/universal-policy-design/outcome-corpus/"
                "adjudications/README.md#annotation-guide"
            ),
            "calibration_round_id": "deep-pilot-round-1",
            "reviewers": [
                {
                    "reviewer_id": "reviewer-policy-generalist-001",
                    "role": "policy_generalist",
                    "expertise_basis": ["housing policy evaluation"],
                    "conflict_disclosures": ["none_declared"],
                },
                {
                    "reviewer_id": "reviewer-legal-governance-001",
                    "role": "legal_governance_reviewer",
                    "expertise_basis": ["municipal housing competence"],
                    "conflict_disclosures": ["none_declared"],
                },
            ],
        },
        "adjudications": [
            {
                "adjudication_id": "adj-case-housing-001",
                "scope": "case",
                "claim_id": None,
                "dimension_id": "public_truthfulness",
                "label": "limitation_required",
                "structural_pass_claimed": True,
                "structural_validator_refs": ["structural-pdc-v1"],
                "evidence_refs": ["evidence://housing/rent-burden/admin-panel"],
                "context_refs": ["context://housing/municipal-competence"],
                "reviewer_votes": [
                    {
                        "reviewer_id": "reviewer-policy-generalist-001",
                        "label": "limitation_required",
                        "rationale": (
                            "The policy design is usable only with an explicit legal-scope "
                            "limit."
                        ),
                        "disagreement_category": "none",
                    },
                    {
                        "reviewer_id": "reviewer-legal-governance-001",
                        "label": "limitation_required",
                        "rationale": (
                            "Municipal competence is narrower than the public surface "
                            "implies."
                        ),
                        "disagreement_category": "none",
                    },
                ],
                "gold_card": {
                    "claim_id": "case",
                    "dimension_id": "public_truthfulness",
                    "evidence_ref": "evidence://housing/rent-burden/admin-panel",
                    "context_ref": "context://housing/municipal-competence",
                    "failure_mode": "scope_overclaim",
                    "why_structural_checks_missed_it": (
                        "Structural checks saw a legal anchor but not the municipal "
                        "competence limit."
                    ),
                    "status_should_have_been": "publish_with_limitation",
                    "required_surface_change": (
                        "Project the recommendation as limited to covered municipalities."
                    ),
                },
            },
            {
                "adjudication_id": "adj-claim-rent-burden",
                "scope": "claim",
                "claim_id": "claim-rent-burden",
                "dimension_id": "causal_support",
                "label": "semantic_pass",
                "structural_pass_claimed": True,
                "structural_validator_refs": ["claim-registry-v2"],
                "evidence_refs": ["evidence://housing/rent-burden/admin-panel"],
                "context_refs": ["context://housing/2025-market"],
                "reviewer_votes": [
                    {
                        "reviewer_id": "reviewer-policy-generalist-001",
                        "label": "semantic_pass",
                        "rationale": "Evidence supports the bounded rent-burden claim.",
                        "disagreement_category": "none",
                    },
                    {
                        "reviewer_id": "reviewer-legal-governance-001",
                        "label": "semantic_pass",
                        "rationale": (
                            "No legal-competence issue applies to this bounded empirical "
                            "claim."
                        ),
                        "disagreement_category": "none",
                    },
                ],
                "gold_card": None,
            },
            {
                "adjudication_id": "adj-claim-legal-competence",
                "scope": "claim",
                "claim_id": "claim-legal-competence",
                "dimension_id": "legal_competence",
                "label": "false_pass",
                "structural_pass_claimed": True,
                "structural_validator_refs": ["lex-authority-anchor-v1"],
                "evidence_refs": ["legal://housing/statute/municipal-powers"],
                "context_refs": ["context://housing/covered-municipalities"],
                "reviewer_votes": [
                    {
                        "reviewer_id": "reviewer-policy-generalist-001",
                        "label": "limitation_required",
                        "rationale": "The overclaim is remediable through surface narrowing.",
                        "disagreement_category": "scope",
                    },
                    {
                        "reviewer_id": "reviewer-legal-governance-001",
                        "label": "false_pass",
                        "rationale": (
                            "The structural pass used an authentic source outside "
                            "competence scope."
                        ),
                        "disagreement_category": "legal_competence",
                    },
                ],
                "gold_card": {
                    "claim_id": "claim-legal-competence",
                    "dimension_id": "legal_competence",
                    "evidence_ref": "legal://housing/statute/municipal-powers",
                    "context_ref": "context://housing/covered-municipalities",
                    "failure_mode": "authentic_source_legally_incompetent",
                    "why_structural_checks_missed_it": (
                        "The source was authentic, but competence did not cover the proposed scope."
                    ),
                    "status_should_have_been": "blocked",
                    "required_surface_change": "Block publication until legal scope is narrowed.",
                },
            },
        ],
    }


def test_expert_adjudication_schema_is_strict_and_c30_labelled() -> None:
    schema = expert_adjudication_json_schema()

    assert schema["title"] == "ExpertAdjudicationManifest"
    assert schema["properties"]["schema_version"]["const"] == EXPERT_ADJUDICATION_SCHEMA_VERSION
    assert schema["additionalProperties"] is False
    assert {
        "semantic_pass",
        "limitation_required",
        "contested",
        "unsupported",
        "false_pass",
        "fabricated_unverifiable",
        "reviewer_disagreement",
    } <= set(schema["$defs"]["ExpertAdjudicationRecord"]["properties"]["label"]["enum"])


def test_deep_pilot_adjudication_preserves_overlap_and_rejected_gold_card() -> None:
    result = evaluate_expert_adjudication_manifest(_base_manifest())

    assert result["status"] == "pass", result["issues"]
    assert result["case_id"] == "housing-rent-stabilization-001"
    assert result["topology_mode"] == "deep_pilot_overlap"
    assert result["claim_coverage_status"] == "complete"
    assert result["rejected_structural_pass_count"] == 2
    assert result["gold_card_count"] == 2
    assert result["substantive_disagreement_preserved"] is True


def test_rejected_structural_pass_requires_full_gold_card_fields() -> None:
    manifest = deepcopy(_base_manifest())
    adjudication = manifest["adjudications"][2]
    assert isinstance(adjudication, dict)
    adjudication["gold_card"] = None

    result = evaluate_expert_adjudication_manifest(manifest)

    assert result["status"] == "fail"
    assert "expert_adjudication_gold_card_missing" in _issue_codes(result)


def test_reviewer_disagreement_cannot_collapse_to_hidden_gold_label() -> None:
    manifest = deepcopy(_base_manifest())
    adjudication = manifest["adjudications"][2]
    assert isinstance(adjudication, dict)
    adjudication["label"] = "reviewer_disagreement"
    adjudication["resolved_gold_label"] = "false_pass"

    result = evaluate_expert_adjudication_manifest(manifest)

    assert result["status"] == "fail"
    assert "expert_adjudication_schema_invalid" in _issue_codes(result)


def test_structurally_complete_case_without_adjudication_cannot_count_useful_design() -> None:
    gate = build_expert_adjudication_useful_design_gate(
        case_id="housing-rent-stabilization-001",
        structural_complete=True,
        adjudication_result=None,
    )

    assert gate["status"] == "blocked"
    assert gate["counts_toward_useful_design"] is False
    assert gate["blocker_code"] == "expert_adjudication_missing"


def test_semantic_pass_manifest_can_count_toward_useful_design() -> None:
    manifest = deepcopy(_base_manifest())
    for adjudication in manifest["adjudications"]:
        assert isinstance(adjudication, dict)
        adjudication["label"] = "semantic_pass"
        adjudication["gold_card"] = None
        for vote in adjudication["reviewer_votes"]:
            assert isinstance(vote, dict)
            vote["label"] = "semantic_pass"
            vote["disagreement_category"] = "none"
    result = evaluate_expert_adjudication_manifest(manifest)
    gate = build_expert_adjudication_useful_design_gate(
        case_id="housing-rent-stabilization-001",
        structural_complete=True,
        adjudication_result=result,
    )

    assert result["status"] == "pass", result["issues"]
    assert gate["status"] == "eligible"
    assert gate["counts_toward_useful_design"] is True
    assert gate["adjudication_labels"] == ["semantic_pass"]


def _issue_codes(result: dict[str, object]) -> set[str]:
    return {
        str(issue["code"])
        for issue in result["issues"]  # type: ignore[index]
    }
