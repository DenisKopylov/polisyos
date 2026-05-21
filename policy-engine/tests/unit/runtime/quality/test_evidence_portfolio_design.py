from __future__ import annotations

# ruff: noqa: S101
import json
from copy import deepcopy
from pathlib import Path

import pytest

from polisyos.runtime.quality.evidence_portfolio import (
    EVIDENCE_PORTFOLIO_DESIGN_SCHEMA_VERSION,
    EvidencePortfolioDesignError,
    portfolio_design_refs_by_claim,
    validate_evidence_portfolio_design_record,
    validate_portfolio_predeclaration_before_evidence_acceptance,
)
from tests._helpers.hds_quality import sha

REPO_ROOT = Path(__file__).resolve().parents[4]
SCHEMA_PATH = (
    REPO_ROOT
    / "schemas/runtime_quality/policy_design_evidence_portfolio_design_v1.schema.json"
)


def _portfolio_design() -> dict[str, object]:
    return {
        "schema_version": EVIDENCE_PORTFOLIO_DESIGN_SCHEMA_VERSION,
        "portfolio_id": "portfolio-rec-1",
        "claim_ids": ["rec_1"],
        "predeclared": True,
        "declared_at": "2026-05-17T08:00:00+00:00",
        "declared_before_producer_execution": True,
        "authority_level": "production",
        "strands": [
            {
                "strand_id": "data-method-literature",
                "claim_id": "rec_1",
                "authority_level": "production",
                "candidate_data_source_families": [
                    "production_msme_panel",
                    "administrative_credit_registry",
                ],
                "candidate_method_families": [
                    "causal_effect_estimation",
                    "quasi_experimental_panel",
                ],
                "defensible_specification_space": {
                    "primary_estimand": "ATT",
                    "allowed_models": ["two_way_fixed_effects", "event_study"],
                    "allowed_covariate_sets": ["baseline", "bank_controls"],
                },
                "inclusion_rules": [
                    "Include production datasets with firm survival and credit exposure.",
                ],
                "exclusion_rules": [
                    "Exclude fixture or survey-only sources without legal use rights.",
                ],
                "disconfirming_lines": [
                    {
                        "line_id": "placebo-pre-period",
                        "required": True,
                        "evidence_family": "negative_control",
                    }
                ],
                "synthesis_rules": {
                    "strategy": "triangulate_independent_lines",
                    "conflict_policy": "surface_and_bound",
                },
                "stopping_rules": {
                    "minimum_effective_independent_evidence_count": 2,
                    "stop_when": "new independent strands no longer change conclusion",
                },
                "cost_proportionality": {
                    "budget_tier": "standard",
                    "proportionality_rationale": (
                        "Production authority major claim warrants at least two "
                        "independent evidence families."
                    ),
                },
            }
        ],
        "candidate_data_source_families": [
            "production_msme_panel",
            "administrative_credit_registry",
        ],
        "candidate_method_families": [
            "causal_effect_estimation",
            "quasi_experimental_panel",
        ],
        "inclusion_rules": ["Prefer production administrative sources."],
        "exclusion_rules": ["Reject local fixture sources."],
        "disconfirming_lines": ["placebo-pre-period"],
        "synthesis_rules": {"strategy": "triangulate_independent_lines"},
        "stopping_rules": {"minimum_effective_independent_evidence_count": 2},
        "cost_proportionality": {"budget_tier": "standard"},
        "cas_ref": sha("1"),
        "runtime_event_ref": sha("2"),
    }


def test_portfolio_design_record_carries_required_strand_contract() -> None:
    validated = validate_evidence_portfolio_design_record(
        _portfolio_design(),
        major_claim_ids=["rec_1"],
        producer_execution_started_at="2026-05-17T09:00:00+00:00",
    )

    assert validated["schema_version"] == EVIDENCE_PORTFOLIO_DESIGN_SCHEMA_VERSION
    assert validated["portfolio_id"] == "portfolio-rec-1"
    assert validated["claim_ids"] == ["rec_1"]
    assert validated["strands"][0]["strand_id"] == "data-method-literature"


def test_portfolio_design_projects_claim_ref_axis_for_compiler() -> None:
    refs_by_claim = portfolio_design_refs_by_claim([_portfolio_design()])

    assert refs_by_claim == {"rec_1": ["portfolio-rec-1"]}


def test_portfolio_design_json_schema_names_required_contract_surfaces() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    assert schema["properties"]["schema_version"]["const"] == (
        EVIDENCE_PORTFOLIO_DESIGN_SCHEMA_VERSION
    )
    assert set(schema["required"]) >= {
        "strands",
        "candidate_data_source_families",
        "candidate_method_families",
        "inclusion_rules",
        "exclusion_rules",
        "disconfirming_lines",
        "synthesis_rules",
        "stopping_rules",
        "cost_proportionality",
    }
    strand_required = set(schema["properties"]["strands"]["items"]["required"])
    assert "defensible_specification_space" in strand_required


@pytest.mark.parametrize(
    ("field", "expected_code"),
    [
        ("strands", "policy_design_portfolio_design_strands_missing"),
        ("candidate_data_source_families", "policy_design_portfolio_candidate_data_missing"),
        ("candidate_method_families", "policy_design_portfolio_candidate_methods_missing"),
        ("inclusion_rules", "policy_design_portfolio_inclusion_rules_missing"),
        ("exclusion_rules", "policy_design_portfolio_exclusion_rules_missing"),
        ("disconfirming_lines", "policy_design_portfolio_disconfirming_lines_missing"),
        ("synthesis_rules", "policy_design_portfolio_synthesis_rules_missing"),
        ("stopping_rules", "policy_design_portfolio_stopping_rules_missing"),
        ("cost_proportionality", "policy_design_portfolio_cost_proportionality_missing"),
    ],
)
def test_portfolio_design_record_rejects_missing_required_surface(
    field: str,
    expected_code: str,
) -> None:
    design = _portfolio_design()
    design.pop(field)

    with pytest.raises(EvidencePortfolioDesignError, match=expected_code):
        validate_evidence_portfolio_design_record(
            design,
            major_claim_ids=["rec_1"],
            producer_execution_started_at="2026-05-17T09:00:00+00:00",
        )


def test_portfolio_design_record_rejects_post_hoc_design_without_exception() -> None:
    design = _portfolio_design()
    design["declared_at"] = "2026-05-17T10:00:00+00:00"

    with pytest.raises(
        EvidencePortfolioDesignError,
        match="policy_design_portfolio_design_post_hoc",
    ):
        validate_evidence_portfolio_design_record(
            design,
            major_claim_ids=["rec_1"],
            producer_execution_started_at="2026-05-17T09:00:00+00:00",
        )


def test_portfolio_design_record_accepts_post_hoc_design_with_accepted_exception() -> None:
    design = _portfolio_design()
    design["declared_at"] = "2026-05-17T10:00:00+00:00"
    design["accepted_exception"] = {
        "status": "accepted",
        "exception_ref": sha("3"),
        "reason": "Producer execution was restarted from an invalid predeclared design.",
        "approved_by": "team-runtime-quality",
    }

    validated = validate_evidence_portfolio_design_record(
        design,
        major_claim_ids=["rec_1"],
        producer_execution_started_at="2026-05-17T09:00:00+00:00",
    )

    assert validated["accepted_exception"]["status"] == "accepted"


def test_portfolio_design_record_requires_each_strand_to_bind_major_claim() -> None:
    design = _portfolio_design()
    mutated_strand = deepcopy(design["strands"][0])  # type: ignore[index]
    assert isinstance(mutated_strand, dict)
    mutated_strand["claim_id"] = "other_claim"
    design["strands"] = [mutated_strand]

    with pytest.raises(
        EvidencePortfolioDesignError,
        match="policy_design_portfolio_strand_claim_ref_missing",
    ):
        validate_evidence_portfolio_design_record(
            design,
            major_claim_ids=["rec_1"],
            producer_execution_started_at="2026-05-17T09:00:00+00:00",
        )


def test_producer_acceptance_guard_requires_predeclared_portfolio_design() -> None:
    with pytest.raises(
        EvidencePortfolioDesignError,
        match="policy_design_major_claim_portfolio_missing",
    ):
        validate_portfolio_predeclaration_before_evidence_acceptance(
            portfolio_designs=[],
            major_claim_ids=["rec_1"],
            producer_execution_started_at="2026-05-17T09:00:00+00:00",
        )


def test_producer_acceptance_guard_rejects_invalid_design_rows() -> None:
    with pytest.raises(
        EvidencePortfolioDesignError,
        match="policy_design_portfolio_design_invalid",
    ):
        validate_portfolio_predeclaration_before_evidence_acceptance(
            portfolio_designs=[object()],  # type: ignore[list-item]
            major_claim_ids=["rec_1"],
            producer_execution_started_at="2026-05-17T09:00:00+00:00",
        )


def test_producer_acceptance_guard_accepts_design_declared_before_execution() -> None:
    result = validate_portfolio_predeclaration_before_evidence_acceptance(
        portfolio_designs=[_portfolio_design()],
        major_claim_ids=["rec_1"],
        producer_execution_started_at="2026-05-17T09:00:00+00:00",
    )

    assert result["status"] == "pass"
    assert result["accepted_claim_ids"] == ["rec_1"]
    assert result["portfolio_design_ids"] == ["portfolio-rec-1"]


def test_producer_acceptance_guard_rejects_post_hoc_design_without_exception() -> None:
    design = _portfolio_design()
    design["declared_at"] = "2026-05-17T10:00:00+00:00"

    with pytest.raises(
        EvidencePortfolioDesignError,
        match="policy_design_portfolio_design_post_hoc",
    ):
        validate_portfolio_predeclaration_before_evidence_acceptance(
            portfolio_designs=[design],
            major_claim_ids=["rec_1"],
            producer_execution_started_at="2026-05-17T09:00:00+00:00",
        )


def test_producer_acceptance_guard_allows_authority_profile_blocker() -> None:
    result = validate_portfolio_predeclaration_before_evidence_acceptance(
        portfolio_designs=[],
        major_claim_ids=["rec_1"],
        producer_execution_started_at="2026-05-17T09:00:00+00:00",
        effective_authority_profile="exploratory",
        authority_profile_blockers=[
            {
                "claim_ids": ["rec_1"],
                "authority_profile": "exploratory",
                "status": "blocked",
                "code": "policy_design_portfolio_blocked_by_exploratory_profile",
                "message": "Exploratory authority profile cannot accept portfolio designs.",
                "evidence_ref": sha("4"),
                "runtime_event_ref": sha("5"),
            }
        ],
    )

    assert result["status"] == "blocked"
    assert result["accepted_claim_ids"] == []
    assert result["blocked_claim_ids"] == ["rec_1"]
