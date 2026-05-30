from __future__ import annotations

# ruff: noqa: S101
from copy import deepcopy
from typing import Any

import pytest

from polisyos.runtime.quality.case_maturity import build_case_maturity_profile
from polisyos.runtime.quality.policy_design_case import (
    POLICY_DESIGN_CASE_GOVERNANCE_RECORD_FAMILY_REQUIREMENTS,
    POLICY_DESIGN_CASE_MINIMUM_RECORD_FAMILIES,
)
from tests._helpers.hds_quality import (
    blocking_codes,
    complete_quality_evidence,
    policy_design_phase28_5_records,
    policy_design_phase29_1_records,
    policy_design_phase29_2_records,
    scorecard_for,
    sha,
)


def test_serious_scorecard_blocks_when_policy_design_case_is_missing() -> None:
    evidence = complete_quality_evidence()
    evidence.pop("policy_design_case", None)

    scorecard = scorecard_for(quality_evidence=evidence)

    assert "policy_design_case_missing" in blocking_codes(scorecard)


def test_policy_design_case_requires_intent_envelope_and_capability_ledger() -> None:
    case = _policy_design_case()
    case.pop("intent_envelope")
    case.pop("capability_ledger")

    codes = _scorecard_blocking_codes_for_case(case)

    assert {
        "policy_design_intent_envelope_missing",
        "policy_design_capability_ledger_missing",
    } <= codes


def test_scorecard_blocks_legal_shaped_payload_without_lex_retrieval_trace() -> None:
    evidence = complete_quality_evidence()
    report = deepcopy(evidence["normative_evidence"])
    assert isinstance(report, dict)
    for field in (
        "retrieval_status",
        "legal_corpus_snapshot",
        "query_terms",
        "legal_query_terms",
        "legal_snapshot_refs",
        "snapshot_refs",
    ):
        report.pop(field, None)
    evidence["normative_evidence"] = report

    scorecard = scorecard_for(quality_evidence=evidence)

    assert "legal_retrieval_trace_missing" in blocking_codes(scorecard)


def test_scorecard_blocks_wrong_jurisdiction_selected_norm_false_pass() -> None:
    evidence = complete_quality_evidence()
    report = deepcopy(evidence["normative_evidence"])
    assert isinstance(report, dict)
    wrong_norm = {
        "norm_id": "norm.de.credit_eligibility",
        "jurisdiction": "DE",
        "policy_domain": "wartime_msme_support",
        "effective_from": "2024-01-01",
        "source_authority": "Bundestag",
        "authority_level": "statute",
    }
    report["candidate_norms"] = [wrong_norm]
    report["selected_norms"] = [wrong_norm]
    report["applied_norms"] = [wrong_norm]
    report["recommendation_coverage"] = [
        {
            "claim_id": "rec_1",
            "major": True,
            "norm_refs": ["norm.de.credit_eligibility"],
        }
    ]
    evidence["normative_evidence"] = report

    scorecard = scorecard_for(quality_evidence=evidence)

    assert "wrong_jurisdiction" in blocking_codes(scorecard)


def test_final_recommendation_requires_baseline_no_action_option() -> None:
    case = _policy_design_case()
    options = deepcopy(case["options_objectives_tradeoffs"])
    options.pop("baseline_option")
    case["options_objectives_tradeoffs"] = options

    codes = _scorecard_blocking_codes_for_case(case)

    assert "policy_design_options_baseline_missing" in codes


def test_final_recommendation_requires_rejected_options() -> None:
    case = _policy_design_case()
    options = deepcopy(case["options_objectives_tradeoffs"])
    options["rejected_options"] = []
    case["options_objectives_tradeoffs"] = options

    codes = _scorecard_blocking_codes_for_case(case)

    assert "policy_design_rejected_options_missing" in codes


def test_final_recommendation_requires_objective_tradeoff_refs() -> None:
    case = _policy_design_case()
    claim = deepcopy(case["final_major_claims"][0])
    claim["objective_tradeoff_refs"] = []
    case["final_major_claims"] = [claim]

    codes = _scorecard_blocking_codes_for_case(case)

    assert "policy_design_final_recommendation_objective_tradeoff_refs_missing" in codes


@pytest.mark.parametrize(
    ("producer_patch", "expected_code"),
    [
        (
            {"provenance_kind": "static_inventory", "source_surface": "architecture.inventory"},
            "policy_design_producer_static_inventory_not_authority",
        ),
        (
            {"cas_ref": None, "evidence_ref": "/var/lib/policyos/fabric/source.json"},
            "policy_design_producer_local_path_not_authority",
        ),
        (
            {
                "cas_ref": None,
                "runtime_event_ref": None,
                "evidence_ref": "OECD 2024 says this policy works.",
                "source_surface": "narrative_citation",
            },
            "policy_design_producer_narrative_citation_not_authority",
        ),
    ],
)
def test_policy_design_case_rejects_non_runtime_producer_evidence(
    producer_patch: dict[str, Any],
    expected_code: str,
) -> None:
    case = _policy_design_case()
    producer = deepcopy(case["producer_evidence"][0])
    producer.update(producer_patch)
    case["producer_evidence"] = [producer]

    codes = _scorecard_blocking_codes_for_case(case)

    assert expected_code in codes


def test_policy_design_case_requires_wave12_producers_or_runtime_blockers() -> None:
    case = _policy_design_case()
    case["producer_evidence"] = [
        producer
        for producer in case["producer_evidence"]
        if producer.get("producer") != "data_forge"
    ]

    codes = _scorecard_blocking_codes_for_case(case)

    assert "policy_design_producer_runtime_evidence_missing" in codes


def test_policy_design_case_allows_wave12_runtime_blocker_for_required_producer() -> None:
    case = _policy_design_case()
    case["producer_evidence"] = [
        producer
        for producer in case["producer_evidence"]
        if producer.get("producer") != "data_forge"
    ]
    case["producer_evidence"].append(
        _runtime_producer_evidence(
            evidence_id="data-forge-blocked",
            producer="data_forge",
            ref_char="1",
            provenance_kind="runtime_blocker",
            status="blocked",
            blockers=[
                {
                    "code": "data_forge_snapshot_store_unavailable",
                    "message": "Data Forge snapshot store unavailable.",
                    "evidence_ref": sha("1"),
                    "runtime_event_ref": sha("2"),
                }
            ],
        )
    )

    codes = _scorecard_blocking_codes_for_case(case)

    assert "policy_design_producer_runtime_evidence_missing" not in codes
    assert "policy_design_producer_blocker_missing" not in codes


def test_policy_design_case_forbids_wave12_producer_peer_dependencies() -> None:
    case = _policy_design_case()
    producer = deepcopy(case["producer_evidence"][0])
    producer["consumed_producer_refs"] = ["scholar-lit-1"]
    case["producer_evidence"] = [producer, *case["producer_evidence"][1:]]

    codes = _scorecard_blocking_codes_for_case(case)

    assert "policy_design_wave12_producer_dependency_forbidden" in codes


def test_final_claim_data_refs_require_fabric_producer_runtime_refs() -> None:
    case = _policy_design_case()
    case["producer_evidence"] = [
        producer for producer in case["producer_evidence"] if producer.get("producer") != "fabric"
    ]

    codes = _scorecard_blocking_codes_for_case(case)

    assert "policy_design_final_claim_producer_ref_missing" in codes


def test_claim_compiler_rejects_major_claim_without_assurance_node() -> None:
    case = _policy_design_case()
    claim = deepcopy(case["final_major_claims"][0])
    claim.pop("assurance_node_id", None)
    claim.pop("claim_ref", None)
    case["final_major_claims"] = [claim]

    codes = _scorecard_blocking_codes_for_case(case)

    assert "policy_design_major_claim_assurance_node_missing" in codes


def test_claim_compiler_rejects_prose_backfill_for_missing_producer_refs() -> None:
    case = _policy_design_case()
    claim = deepcopy(case["final_major_claims"][0])
    claim["source_data_refs"] = []
    claim["data_refs"] = []
    claim["support_summary"] = (
        "The production MSME panel and selected legal evidence support this claim."
    )
    claim["selected_producer_refs"] = {
        **claim.get("selected_producer_refs", {}),
        "data_forge": [],
        "fabric": [],
    }
    case["final_major_claims"] = [claim]

    codes = _scorecard_blocking_codes_for_case(case)

    assert "policy_design_major_claim_source_data_refs_missing" in codes
    assert "policy_design_major_claim_prose_backfill_not_authority" in codes


@pytest.mark.parametrize(
    ("field", "expected_code"),
    [
        ("selected_candidate_refs", "policy_design_producer_selected_candidates_missing"),
        ("rejected_candidate_refs", "policy_design_producer_rejected_candidates_missing"),
        ("source_rights_refs", "policy_design_producer_source_rights_missing"),
        ("freshness_refs", "policy_design_producer_freshness_missing"),
        ("quality_refs", "policy_design_producer_quality_missing"),
        ("snapshot_refs", "policy_design_producer_snapshot_identity_missing"),
        ("blocker_refs", "policy_design_producer_blocker_missing"),
    ],
)
def test_final_claim_data_refs_require_complete_fabric_producer_contract(
    field: str,
    expected_code: str,
) -> None:
    case = _policy_design_case()
    producer = next(
        producer for producer in case["producer_evidence"] if producer.get("producer") == "fabric"
    )
    producer.pop(field, None)

    codes = _scorecard_blocking_codes_for_case(case)

    assert expected_code in codes


def test_policy_design_case_rejects_static_only_producer_ref_map() -> None:
    case = _policy_design_case()
    case["producer_evidence"] = []
    case["producer_runtime_ref_map"] = {
        "fabric": {
            "provenance_kind": "static_inventory",
            "source_surface": "architecture.inventory",
            "evidence_ref": "repo://architecture/baselines/production_quality/evidence_inventory.json",
            "selected_candidate_refs": ["production-msme-panel"],
            "rejected_candidate_refs": ["fixture-source"],
            "source_rights_refs": ["rights:production-msme-panel"],
            "freshness_refs": ["freshness:production-msme-panel"],
            "quality_refs": ["quality:production-msme-panel"],
            "snapshot_refs": [sha("4")],
            "blocker_refs": [],
        }
    }

    codes = _scorecard_blocking_codes_for_case(case)

    assert "policy_design_producer_static_inventory_not_authority" in codes


def test_options_objectives_tradeoffs_requires_runtime_authority() -> None:
    case = _policy_design_case()
    options = deepcopy(case["options_objectives_tradeoffs"])
    for field in ("provenance_kind", "cas_ref", "evidence_ref", "runtime_event_ref"):
        options.pop(field, None)
    case["options_objectives_tradeoffs"] = options

    codes = _scorecard_blocking_codes_for_case(case)

    assert "policy_design_options_runtime_authority_missing" in codes


def test_policy_design_case_requires_portfolio_or_accepted_deficit_for_major_claim() -> None:
    case = _policy_design_case()
    claim = deepcopy(case["final_major_claims"][0])
    claim["portfolio_refs"] = []
    claim["accepted_deficit_refs"] = []
    case["final_major_claims"] = [claim]
    case["evidence_portfolios"] = []

    codes = _scorecard_blocking_codes_for_case(case)

    assert "policy_design_major_claim_portfolio_missing" in codes


def test_policy_design_case_requires_complete_predeclared_portfolio_design() -> None:
    case = _policy_design_case()
    portfolio = deepcopy(case["evidence_portfolios"][0])
    portfolio.pop("strands")
    case["evidence_portfolios"] = [portfolio]

    codes = _scorecard_blocking_codes_for_case(case)

    assert "policy_design_portfolio_design_strands_missing" in codes


def test_policy_design_case_rejects_post_hoc_portfolio_design_without_exception() -> None:
    case = _policy_design_case()
    portfolio = deepcopy(case["evidence_portfolios"][0])
    portfolio["declared_at"] = "2026-05-17T10:00:00+00:00"
    case["evidence_portfolios"] = [portfolio]

    codes = _scorecard_blocking_codes_for_case(case)

    assert "policy_design_portfolio_design_post_hoc" in codes


def test_policy_design_case_rejects_evidence_line_missing_source_lineage() -> None:
    case = _policy_design_case()
    line = _evidence_line()
    line.pop("source_lineage")
    case["evidence_lines"] = [line]

    codes = _scorecard_blocking_codes_for_case(case)

    assert "policy_design_evidence_line_source_lineage_missing" in codes


def test_policy_design_case_rejects_raw_count_without_effective_independent_count() -> None:
    case = _policy_design_case()
    case["independence_maps"] = [
        {
            "schema_version": "policyos.runtime.policy_design_case.independence_map.v1",
            "map_id": "independence-map-rec-1",
            "portfolio_id": "portfolio-rec-1",
            "claim_id": "rec_1",
            "raw_evidence_line_count": 400,
            "collapse_clusters": [],
        }
    ]

    codes = _scorecard_blocking_codes_for_case(case)

    assert "policy_design_independence_effective_count_missing" in codes


def test_policy_design_case_rejects_unaccepted_single_line_major_claim() -> None:
    case = _policy_design_case()

    codes = _scorecard_blocking_codes_for_case(case)

    assert "policy_design_single_line_evidence_unaccepted" in codes


def test_policy_design_case_allows_single_line_major_claim_with_accepted_deficit() -> None:
    case = _policy_design_case()
    case["accepted_deficits"] = [
        {
            "deficit_kind": "single_line_evidence_deficit",
            "status": "accepted",
            "claim_id": "rec_1",
            "accepted_profiles": ["production"],
            "evidence_ref": sha("1"),
            "runtime_event_ref": sha("2"),
        }
    ]

    codes = _scorecard_blocking_codes_for_case(case)

    assert "policy_design_single_line_evidence_unaccepted" not in codes


def test_policy_design_case_blocks_research_deficit_promoted_to_production() -> None:
    case = _policy_design_case(effective_execution_profile="production")
    case["accepted_deficits"] = [
        {
            "deficit_id": "deficit-research-only-single-line",
            "deficit_kind": "single_line_evidence_deficit",
            "status": "accepted",
            "claim_id": "rec_1",
            "accepted_profiles": ["research"],
            "source_authority_profile": "research",
            "evidence_ref": sha("1"),
            "runtime_event_ref": sha("2"),
        }
    ]

    codes = _scorecard_blocking_codes_for_case(case)

    assert "policy_design_research_deficit_promoted_to_authority" in codes


def test_policy_design_case_research_profile_emits_domain_evidence_and_honest_deficit() -> None:
    case = _policy_design_case(effective_execution_profile="research")
    case["accepted_deficits"] = [
        {
            "deficit_id": "deficit-research-single-line",
            "deficit_kind": "single_line_evidence_deficit",
            "status": "accepted",
            "claim_id": "rec_1",
            "accepted_profiles": ["research"],
            "source_authority_profile": "research",
            "evidence_ref": sha("1"),
            "runtime_event_ref": sha("2"),
        }
    ]

    codes = _scorecard_blocking_codes_for_case(case, canary_kind="research")

    assert "policy_design_research_deficit_promoted_to_authority" not in codes
    assert "policy_design_single_line_evidence_unaccepted" not in codes
    assert case["producer_evidence"]
    assert case["accepted_deficits"][0]["deficit_kind"] == "single_line_evidence_deficit"


def test_policy_design_case_rejects_cherry_picked_agreeing_multiverse_specs() -> None:
    case = _policy_design_case()
    case["multiverse_specification_curves"] = [
        {
            "schema_version": (
                "policyos.runtime.policy_design_case.multiverse_specification_curve.v1"
            ),
            "curve_id": "multiverse-rec-1",
            "claim_ids": ["rec_1"],
            "portfolio_id": "portfolio-rec-1",
            "source_kind_counts": {
                "scientist_doe": 1,
                "scientist_discovery": 1,
                "foundry_sensitivity": 1,
                "backtesting": 1,
            },
            "specification_records": [
                {
                    "specification_id": "twfe-baseline",
                    "claim_ids": ["rec_1"],
                    "source_kind": "scientist_doe",
                    "decision": "defensible",
                    "estimate": 0.04,
                    "standard_error": 0.01,
                    "sign": "positive",
                    "significant": True,
                    "drivers": {"model_family": "two_way_fixed_effects"},
                },
                {
                    "specification_id": "event-study",
                    "claim_ids": ["rec_1"],
                    "source_kind": "scientist_discovery",
                    "decision": "defensible",
                    "estimate": 0.03,
                    "standard_error": 0.01,
                    "sign": "positive",
                    "significant": True,
                    "drivers": {"model_family": "event_study"},
                },
                {
                    "specification_id": "matched-did",
                    "claim_ids": ["rec_1"],
                    "source_kind": "foundry_sensitivity",
                    "decision": "defensible",
                    "estimate": 0.02,
                    "standard_error": 0.01,
                    "sign": "positive",
                    "significant": False,
                    "drivers": {"model_family": "matched_did"},
                },
                {
                    "specification_id": "placebo-pretrend",
                    "claim_ids": ["rec_1"],
                    "source_kind": "backtesting",
                    "decision": "rejected",
                    "estimate": -0.03,
                    "standard_error": 0.01,
                    "sign": "negative",
                    "significant": True,
                    "rejection_reason": "Historical pre-period placebo failed.",
                    "drivers": {"model_family": "placebo_backtest"},
                },
            ],
            "defensible_specifications": [
                {"specification_id": "twfe-baseline"},
                {"specification_id": "event-study"},
                {"specification_id": "matched-did"},
            ],
            "rejected_specifications": [
                {
                    "specification_id": "placebo-pretrend",
                    "rejection_reason": "Historical pre-period placebo failed.",
                }
            ],
            "result_distribution": {
                "n_specifications": 4,
                "defensible_count": 3,
                "rejected_count": 1,
                "sign_counts": {"positive": 3, "negative": 1, "zero": 0},
                "estimate_min": -0.03,
                "estimate_max": 0.04,
                "estimate_median": 0.025,
                "share_significant": 0.75,
            },
            "drivers_of_divergence": [{"axis": "model_family", "values": ["placebo_backtest"]}],
            "claim_markers": [
                {
                    "claim_id": "rec_1",
                    "marker": "robust",
                    "reason_codes": ["defensible_specifications_agree"],
                }
            ],
            "evidence_ref": sha("2"),
            "runtime_event_ref": sha("2"),
            "previous_wave_refs": _previous_wave_refs(),
        }
    ]

    codes = _scorecard_blocking_codes_for_case(case)

    assert "policy_design_multiverse_cherry_picked_agreement" in codes


def test_policy_design_case_rejects_post_hoc_selection_hiding_disagreement() -> None:
    case = _policy_design_case()
    disagreeing_line = _evidence_line()
    disagreeing_line.update(
        {
            "line_id": "line-disagreeing",
            "stance": "disagreeing",
            "claim_direction": "negative",
            "evidence_ref": sha("d"),
            "runtime_event_ref": sha("e"),
        }
    )
    case["evidence_lines"] = [_evidence_line(), disagreeing_line]
    case["portfolio_selection_audits"] = [
        {
            "audit_id": "selection-audit-rec-1",
            "claim_id": "rec_1",
            "portfolio_id": "portfolio-rec-1",
            "selection_timing": "post_hoc",
            "selected_line_ids": ["line-data"],
            "excluded_line_ids": ["line-disagreeing"],
            "exclusion_rationales": [
                {
                    "line_id": "line-disagreeing",
                    "reason_code": "opposite_direction_disagreement",
                }
            ],
            "evidence_ref": sha("1"),
            "runtime_event_ref": sha("2"),
        }
    ]

    codes = _scorecard_blocking_codes_for_case(case)

    assert "policy_design_post_hoc_selection_hides_disagreement" in codes


def test_policy_design_case_requires_multiverse_curve_for_major_claim() -> None:
    case = _policy_design_case()
    case["multiverse_specification_curves"] = []
    portfolio = deepcopy(case["evidence_portfolios"][0])
    portfolio.pop("multiverse_report_ref", None)
    case["evidence_portfolios"] = [portfolio]

    codes = _scorecard_blocking_codes_for_case(case)

    assert "policy_design_multiverse_specification_curve_missing" in codes


def test_policy_design_case_rejects_unbound_multiverse_curve() -> None:
    case = _policy_design_case()
    curve = deepcopy(case["multiverse_specification_curves"][0])
    curve["portfolio_id"] = "other-portfolio"
    case["multiverse_specification_curves"] = [curve]

    codes = _scorecard_blocking_codes_for_case(case)

    assert "policy_design_multiverse_specification_curve_missing" in codes


def test_policy_design_case_rejects_multiverse_curve_for_other_claim() -> None:
    case = _policy_design_case()
    curve = deepcopy(case["multiverse_specification_curves"][0])
    curve["claim_ids"] = ["other_claim"]
    for record in curve["specification_records"]:
        record["claim_ids"] = ["other_claim"]
    curve["claim_markers"] = [
        {
            "claim_id": "other_claim",
            "marker": "robust",
            "reason_codes": ["defensible_specifications_agree"],
        }
    ]
    case["multiverse_specification_curves"] = [curve]

    codes = _scorecard_blocking_codes_for_case(case)

    assert "policy_design_multiverse_specification_curve_missing" in codes


def test_policy_design_case_rejects_static_multiverse_refs() -> None:
    case = _policy_design_case()
    portfolio = deepcopy(case["evidence_portfolios"][0])
    portfolio["multiverse_report_ref"] = "repo://architecture/static_multiverse.json"
    case["evidence_portfolios"] = [portfolio]
    curve = deepcopy(case["multiverse_specification_curves"][0])
    curve["evidence_ref"] = "repo://architecture/static_multiverse.json"
    case["multiverse_specification_curves"] = [curve]

    codes = _scorecard_blocking_codes_for_case(case)

    assert "policy_design_multiverse_evidence_ref_invalid" in codes


def test_policy_design_case_requires_synthesis_report_for_major_claim() -> None:
    case = _policy_design_case()
    case["synthesis_reports"] = []
    portfolio = deepcopy(case["evidence_portfolios"][0])
    portfolio.pop("synthesis_report_ref", None)
    case["evidence_portfolios"] = [portfolio]

    codes = _scorecard_blocking_codes_for_case(case)

    assert "policy_design_synthesis_report_missing" in codes


def test_policy_design_case_rejects_hidden_synthesis_direction_change() -> None:
    case = _policy_design_case()
    synthesis_report = deepcopy(case["synthesis_reports"][0])
    synthesis_report["sensitivity_to_synthesis_rules"] = [
        {
            "rule_id": "equal_weight_with_severe_backtests",
            "weighting": "equal",
            "included_decisions": ["defensible", "rejected"],
            "reasonable": True,
            "estimate": -0.015,
            "direction": "negative",
            "direction_changed": True,
            "included_specification_ids": [
                "backtest-placebo",
                "event-study",
                "matched-did",
                "twfe-baseline",
            ],
        }
    ]
    synthesis_report["divergence_assessment"] = {
        "status": "convergent",
        "reason_codes": ["claimed_robust_without_surface"],
    }
    synthesis_report["divergence_evidence"] = []
    case["synthesis_reports"] = [synthesis_report]

    codes = _scorecard_blocking_codes_for_case(case)

    assert "policy_design_synthesis_divergence_evidence_missing" in codes


def test_policy_design_case_allows_authority_profile_portfolio_blocker() -> None:
    case = _policy_design_case()
    claim = deepcopy(case["final_major_claims"][0])
    claim["portfolio_refs"] = []
    claim["accepted_deficit_refs"] = []
    case["final_major_claims"] = [claim]
    case["evidence_portfolios"] = []
    case["evidence_lines"] = []
    case["independence_maps"] = []
    case["multiverse_specification_curves"] = []
    case["disconfirming_evidence_ledgers"] = []
    case["evidence_portfolio_design_blockers"] = [
        {
            "claim_ids": ["rec_1"],
            "authority_profile": "production",
            "status": "blocked",
            "code": "policy_design_portfolio_authority_profile_blocked",
            "message": "Authority profile blocked portfolio design until data access is granted.",
            "evidence_ref": sha("1"),
            "runtime_event_ref": sha("2"),
        }
    ]

    codes = _scorecard_blocking_codes_for_case(case)

    assert "policy_design_major_claim_portfolio_missing" not in codes


def test_policy_design_case_rejects_friendly_only_portfolio_without_disconfirming_deficit() -> None:
    case = _policy_design_case()
    portfolio = deepcopy(case["evidence_portfolios"][0])
    friendly_line = {
        "line_id": "positive-estimate-only",
        "stance": "supporting",
        "evidence_family": "confirmatory_estimate",
    }
    portfolio["disconfirming_lines"] = [friendly_line]
    strand = deepcopy(portfolio["strands"][0])
    strand["disconfirming_lines"] = [friendly_line]
    portfolio["strands"] = [strand]
    case["evidence_portfolios"] = [portfolio]
    case["disconfirming_evidence_ledgers"] = []

    codes = _scorecard_blocking_codes_for_case(case)

    assert "policy_design_disconfirming_lines_missing" in codes


def test_policy_design_case_rejects_missing_severe_test_rationale() -> None:
    case = _policy_design_case()
    ledger = _disconfirming_ledger()
    ledger["severe_tests"][0].pop("rationale")
    case["disconfirming_evidence_ledgers"] = [ledger]

    codes = _scorecard_blocking_codes_for_case(case)

    assert "policy_design_severe_test_rationale_missing" in codes


def test_policy_design_case_claim_refs_do_not_replace_argument_contracts() -> None:
    case = _policy_design_case()
    claim = deepcopy(case["final_major_claims"][0])
    claim["data_refs"] = ["production-msme-panel"]
    claim["method_refs"] = ["causal.difference_in_differences"]
    claim["norm_refs"] = ["norm.ua.credit_eligibility"]
    claim["argument_refs"] = []
    claim["warrant_refs"] = []
    claim["rebuttal_refs"] = []
    claim["accepted_deficit_refs"] = []
    claim["assurance_deficit_refs"] = []
    case["final_major_claims"] = [claim]
    case["arguments"] = []
    case["warrants"] = []
    case["rebuttals"] = []
    case["counter_evidence"] = []
    case["assurance_deficits"] = []

    codes = _scorecard_blocking_codes_for_case(case)

    assert {
        "policy_design_major_claim_argument_missing",
        "policy_design_major_claim_warrant_missing",
        "policy_design_major_claim_rebuttal_missing",
        "policy_design_major_claim_deficit_missing",
    } <= codes


def test_policy_design_case_blocks_hidden_counter_evidence() -> None:
    case = _policy_design_case()
    hidden = deepcopy(case["counter_evidence"][0])
    hidden["counter_evidence_id"] = "counter-hidden-rec-1"
    hidden["visibility"] = "hidden"
    hidden["hidden"] = True
    hidden["status"] = "excluded_from_reviewer_surface"
    hidden["evidence_ref"] = sha("1")
    case["counter_evidence"] = [*case["counter_evidence"], hidden]

    codes = _scorecard_blocking_codes_for_case(case)

    assert "policy_design_hidden_counter_evidence" in codes


def test_policy_design_case_blocks_nominal_approval_without_effective_oversight() -> None:
    case = _policy_design_case()
    case["human_oversight"] = {
        "schema_version": "policyos.runtime.policy_design_case.human_oversight.v1",
        "status": "pass",
        "review_count": 2,
        "reviewer_count": 1,
        "reviewer_independence_rate": 0.0,
        "separation_of_duty_attestation_rate": 0.0,
        "approve_without_change_rate": 1.0,
        "rubber_stamp_risk": "high",
        "effective_oversight": False,
        "oversight_ref": sha("6"),
        "runtime_event_ref": sha("e"),
    }

    codes = _scorecard_blocking_codes_for_case(case)

    assert "policy_design_human_oversight_ineffective" in codes


def test_policy_design_case_blocks_expert_judgement_masquerading_as_observed_data() -> None:
    case = _policy_design_case()
    claim = deepcopy(case["final_major_claims"][0])
    claim["source_data_refs"] = [
        *claim["source_data_refs"],
        "expert-judgement-rec-1",
    ]
    claim["expert_judgement_refs"] = ["expert-judgement-rec-1"]
    case["final_major_claims"] = [claim]
    case["structured_expert_judgements"] = [
        {
            "schema_version": (
                "policyos.runtime.policy_design_case.structured_expert_judgement.v1"
            ),
            "judgement_id": "expert-judgement-rec-1",
            "claim_ids": ["rec_1"],
            "elicitation_method": "delphi",
            "expert_provenance": {
                "expert_id": "expert-1",
                "field": "wartime MSME finance",
                "credential_ref": sha("1"),
            },
            "conflicts": [],
            "uncertainty": {"interval": [0.1, 0.4], "confidence": 0.8},
            "classification": "observed_data",
            "evidence_ref": sha("2"),
            "runtime_event_ref": sha("e"),
        }
    ]

    codes = _scorecard_blocking_codes_for_case(case)

    assert "policy_design_expert_judgement_masquerades_as_observed_data" in codes


def test_policy_design_case_blocks_stakeholder_objections_hidden_from_final_claims() -> None:
    case = _policy_design_case()
    case["consultations"] = [
        {
            "schema_version": ("policyos.runtime.policy_design_case.consultation_record.v1"),
            "consultation_id": "consultation-rec-1",
            "stakeholder_map": {
                "stakeholders": [
                    {"stakeholder_id": "msme", "name": "MSMEs"},
                    {"stakeholder_id": "bank", "name": "Participating banks"},
                ]
            },
            "consultation_plan": {
                "plan_id": "consultation-plan-1",
                "comment_period": "2026-05-01/2026-05-14",
            },
            "public_comments": [
                {
                    "comment_id": "comment-1",
                    "stakeholder_id": "bank",
                    "summary": "Implementation burden is not addressed.",
                }
            ],
            "objection_records": [
                {
                    "objection_id": "objection-1",
                    "claim_id": "rec_1",
                    "severity": "high",
                    "status": "unresolved",
                    "visibility": "hidden",
                    "comment_id": "comment-1",
                }
            ],
            "response_to_comment_reasoning": [],
            "evidence_ref": sha("3"),
            "runtime_event_ref": sha("e"),
        }
    ]

    codes = _scorecard_blocking_codes_for_case(case)

    assert "policy_design_unresolved_objection_hidden_from_final_claim" in codes


def test_policy_design_case_blocks_missing_structured_judgement_and_consultation_records() -> None:
    case = _policy_design_case()
    case.pop("structured_expert_judgements", None)
    case.pop("consultations", None)

    codes = _scorecard_blocking_codes_for_case(case)

    assert "policy_design_structured_judgement_missing" in codes
    assert "policy_design_consultation_record_missing" in codes


def test_policy_design_case_blocks_incomplete_human_oversight_shape() -> None:
    case = _policy_design_case()
    case["human_oversight"] = {
        "schema_version": "policyos.runtime.policy_design_case.human_oversight.v1",
        "status": "pass",
        "rubber_stamp_risk": "low",
        "effective_oversight": True,
    }

    codes = _scorecard_blocking_codes_for_case(case)

    assert "policy_design_human_oversight_required_field_missing" in codes


def test_policy_design_case_blocks_missing_external_audit_archive_record() -> None:
    case = _policy_design_case()
    case.pop("external_audit_record", None)
    case.pop("public_audit_archive", None)

    codes = _scorecard_blocking_codes_for_case(case)

    assert "policy_design_external_audit_record_missing" in codes


def test_policy_design_case_blocks_invalid_external_audit_archive_record() -> None:
    case = _policy_design_case()
    audit_record = deepcopy(case["external_audit_record"])
    audit_record["core_audit"].pop("prov_json")
    case["external_audit_record"] = audit_record

    codes = _scorecard_blocking_codes_for_case(case)

    assert "external_audit_prov_missing" in codes


def test_policy_design_case_blocks_missing_config_release_hardening_record() -> None:
    case = _policy_design_case()
    case.pop("config_release_deployment_migration_hardening", None)

    codes = _scorecard_blocking_codes_for_case(case)

    assert "policy_design_config_release_hardening_record_missing" in codes


def test_policy_design_case_blocks_missing_substrate_residual_verification_record() -> None:
    case = _policy_design_case()
    case.pop("substrate_residual_verification", None)

    codes = _scorecard_blocking_codes_for_case(case)

    assert "policy_design_substrate_residual_verification_record_missing" in codes


def test_policy_design_case_blocks_missing_non_adversarial_self_fmea_record() -> None:
    case = _policy_design_case()
    case.pop("non_adversarial_self_fmea", None)

    codes = _scorecard_blocking_codes_for_case(case)

    assert "policy_design_self_fmea_record_missing" in codes


def test_policy_design_case_blocks_malformed_non_adversarial_self_fmea_record() -> None:
    case = _policy_design_case()
    record = deepcopy(case["non_adversarial_self_fmea"])
    record["schema_version"] = "bad.schema"
    record.pop("job_id", None)
    record.pop("tenant_id", None)
    case["non_adversarial_self_fmea"] = record

    codes = _scorecard_blocking_codes_for_case(case)

    assert "policy_design_self_fmea_schema_invalid" in codes
    assert "policy_design_self_fmea_identity_missing" in codes


def test_policy_design_case_blocks_partial_state_authority_contradiction() -> None:
    case = _policy_design_case()
    case["partial_state_consistency"] = {
        "schema_version": "policyos.runtime.policy_design_case.partial_state_consistency.v1",
        "record_id": "partial-state-consistency-rec-1",
        "record_family": "integrity_self_fmea_and_maturity.v1",
        "case_id": "pdc-R_hds_red_control",
        "run_id": "R_hds_red_control",
        "status": "pass",
        "authoritative_records": [
            {
                "record_id": "lifecycle-authority-published",
                "record_family": "lifecycle_ex_post_and_calibration.v1",
                "field": "case_lifecycle.current_state",
                "value": "published",
                "authority_role": "authoritative",
                "evidence_ref": sha("1"),
                "runtime_event_ref": "event://policy-design-case/lifecycle/published",
            },
            {
                "record_id": "lifecycle-authority-withdrawn",
                "record_family": "lifecycle_ex_post_and_calibration.v1",
                "field": "case_lifecycle.current_state",
                "value": "withdrawn",
                "authority_role": "authoritative",
                "evidence_ref": sha("2"),
                "runtime_event_ref": "event://policy-design-case/lifecycle/withdrawn",
            },
        ],
        "evidence_ref": sha("3"),
        "runtime_event_ref": "event://policy-design-case/partial-state/1",
    }

    codes = _scorecard_blocking_codes_for_case(case)

    assert "policy_design_partial_state_authority_contradiction" in codes


def test_policy_design_case_blocks_malformed_partial_state_consistency_record() -> None:
    case = _policy_design_case()
    record = deepcopy(case["partial_state_consistency"])
    record["schema_version"] = "bad.schema"
    for field in ("case_id", "run_id", "job_id", "tenant_id"):
        record.pop(field, None)
    case["partial_state_consistency"] = record

    codes = _scorecard_blocking_codes_for_case(case)

    assert "policy_design_partial_state_schema_invalid" in codes
    assert "policy_design_partial_state_identity_missing" in codes


def test_policy_design_case_blocks_config_release_hardening_without_case_identity() -> None:
    case = _policy_design_case()
    hardening = deepcopy(case["config_release_deployment_migration_hardening"])
    for field in ("record_id", "contract_id", "run_id"):
        hardening.pop(field, None)
    case["config_release_deployment_migration_hardening"] = hardening

    codes = _scorecard_blocking_codes_for_case(case)

    assert "policy_design_config_release_hardening_identity_missing" in codes


def test_policy_design_case_blocks_deployment_parity_without_required_service_matrix() -> None:
    case = _policy_design_case()
    hardening = deepcopy(case["config_release_deployment_migration_hardening"])
    hardening["deployment_parity"]["required_service_matrix"] = [
        {
            "service": "state_store",
            "local": "real",
            "staging": "real",
            "production": "real",
        }
    ]
    case["config_release_deployment_migration_hardening"] = hardening

    codes = _scorecard_blocking_codes_for_case(case)

    assert "policy_design_deployment_parity_service_missing" in codes


def test_policy_design_case_blocks_release_supply_chain_dirty_tree() -> None:
    case = _policy_design_case()
    hardening = deepcopy(case["config_release_deployment_migration_hardening"])
    hardening["release_supply_chain"]["dirty_tree_clean"] = False
    case["config_release_deployment_migration_hardening"] = hardening

    codes = _scorecard_blocking_codes_for_case(case)

    assert "policy_design_release_provenance_dirty_tree" in codes


def test_policy_design_case_blocks_persisted_state_migration_failure() -> None:
    case = _policy_design_case()
    hardening = deepcopy(case["config_release_deployment_migration_hardening"])
    hardening["persisted_state_migration"]["historical_decision_checks"][0]["replay_status"] = (
        "fail"
    )
    case["config_release_deployment_migration_hardening"] = hardening

    codes = _scorecard_blocking_codes_for_case(case)

    assert "policy_design_persisted_state_migration_check_failed" in codes


def test_policy_design_case_blocks_expired_quarantine_or_shim_usage() -> None:
    case = _policy_design_case()
    hardening = deepcopy(case["config_release_deployment_migration_hardening"])
    hardening["quarantine_shim_lifecycle"]["expired_usage_ids"] = ["legacy-client-shim"]
    case["config_release_deployment_migration_hardening"] = hardening

    codes = _scorecard_blocking_codes_for_case(case)

    assert "policy_design_quarantine_shim_expired" in codes


def test_policy_design_case_blocks_generated_surface_drift() -> None:
    case = _policy_design_case()
    hardening = deepcopy(case["config_release_deployment_migration_hardening"])
    hardening["generated_surface_drift"]["runtime_to_generated_diff"]["status"] = "drift"
    case["config_release_deployment_migration_hardening"] = hardening

    codes = _scorecard_blocking_codes_for_case(case)

    assert "policy_design_generated_surface_drift" in codes


def test_policy_design_case_blocks_stale_manual_runbook_gate() -> None:
    case = _policy_design_case()
    hardening = deepcopy(case["config_release_deployment_migration_hardening"])
    hardening["runbook_automation"]["manual_gates"][0]["status"] = "stale"
    hardening["runbook_automation"]["manual_gates"][0].pop("signed_review_ref", None)
    case["config_release_deployment_migration_hardening"] = hardening

    codes = _scorecard_blocking_codes_for_case(case)

    assert "policy_design_manual_gate_stale" in codes


def test_policy_design_case_blocks_retention_deletion_replay_conflict() -> None:
    case = _policy_design_case()
    hardening = deepcopy(case["config_release_deployment_migration_hardening"])
    hardening["retention_deletion_replay"]["jurisdiction_blockers"] = [
        {
            "blocker_id": "ua-retention-conflict",
            "status": "open",
            "evidence_ref": sha("7"),
        }
    ]
    case["config_release_deployment_migration_hardening"] = hardening

    codes = _scorecard_blocking_codes_for_case(case)

    assert "policy_design_retention_deletion_replay_conflict" in codes


def test_policy_design_case_blocks_non_authority_continuous_governance_report_refs() -> None:
    case = _policy_design_case()
    lifecycle = deepcopy(case["case_lifecycle"])
    lifecycle["continuous_governance_reports"] = {
        "reissue": "not-a-runtime-ref",
        "supersede": "not-a-runtime-ref",
        "withdraw": "not-a-runtime-ref",
        "validity": "not-a-runtime-ref",
    }
    case["case_lifecycle"] = lifecycle

    codes = _scorecard_blocking_codes_for_case(case)

    assert "policy_design_continuous_governance_report_ref_invalid" in codes


def test_policy_design_case_blocks_requester_prior_confirmation_without_alternatives() -> None:
    case = _policy_design_case()
    challenge = deepcopy(case["requester_capture_challenges"][0])
    challenge.update(
        {
            "challenge_result": "passed",
            "requester_preferred_conclusion": "expand credit support",
            "independent_analysis_conclusion": "expand credit support",
            "independent_alternative_analyses": [],
            "scientist_output_refs": {},
            "adversarial_output_refs": [],
        }
    )
    case["requester_capture_challenges"] = [challenge]

    codes = _scorecard_blocking_codes_for_case(case)

    assert "policy_design_requester_capture_independent_alternatives_missing" in codes
    assert "policy_design_challenge_policy_adversary_ref_missing" in codes
    assert "policy_design_challenge_backtesting_adversarial_ref_missing" in codes


def test_policy_design_case_warrant_requires_berl_refs_for_reliability() -> None:
    case = _policy_design_case()
    warrant = deepcopy(case["warrants"][0])
    warrant["requires_explanation_reliability"] = True
    warrant["explanation_trust_affects_acceptance"] = True
    warrant["berl_reliability_refs"] = []
    case["warrants"] = [warrant]

    codes = _scorecard_blocking_codes_for_case(case)

    assert "policy_design_warrant_berl_refs_missing" in codes


def test_policy_design_case_blocks_high_cost_low_impact_without_proportionality() -> None:
    case = _policy_design_case(effective_execution_profile="research")
    ledger = deepcopy(case["run_cost_proportionality_ledgers"][0])
    ledger["authority_level"] = "research"
    ledger["public_impact"] = "low"
    ledger["total_actual_cost_usd"] = 650.0
    ledger["proportionality_evidence"] = {}
    depth = ledger["evidence_depth_budget"]
    assert isinstance(depth, dict)
    depth["authority_level"] = "research"
    depth["public_impact"] = "low"
    depth["effective_independent_evidence_count"] = 1
    depth["minimum_effective_independent_evidence_count"] = 1
    case["run_cost_proportionality_ledgers"] = [ledger]

    codes = _scorecard_blocking_codes_for_case(case, canary_kind="research")

    assert (
        "policy_design_run_cost_high_cost_low_impact_without_proportionality"
        in codes
    )


def test_policy_design_case_accepts_typed_run_cost_blocker_as_exit_fence() -> None:
    case = _policy_design_case()
    case["run_cost_proportionality_ledgers"] = []
    case["run_cost_proportionality_blockers"] = [
        {
            "status": "blocked",
            "code": "policy_design_run_cost_proportionality_source_unavailable",
            "message": "Provider cost export was unavailable for this run.",
            "evidence_ref": sha("9"),
            "runtime_event_ref": "event://runtime/run-cost/blocker/R_hds_red_control",
            "blocked_record_family": "run_cost_proportionality_ledger.v1",
        }
    ]

    codes = _scorecard_blocking_codes_for_case(case)

    assert "policy_design_run_cost_proportionality_ledger_missing" not in codes
    assert "policy_design_run_cost_proportionality_source_unavailable" in codes


def test_policy_design_case_projects_run_cost_ledger_from_runtime_context() -> None:
    evidence = complete_quality_evidence()
    case = evidence["policy_design_case"]
    assert isinstance(case, dict)
    case.pop("run_cost_proportionality_ledgers", None)

    scorecard = scorecard_for(quality_evidence=evidence)
    codes = blocking_codes(scorecard)

    assert "policy_design_run_cost_proportionality_ledger_missing" not in codes
    assert "policy_design_run_cost_source_run_id_missing" not in codes


def _scorecard_blocking_codes_for_case(
    case: dict[str, Any],
    *,
    canary_kind: str = "production",
) -> set[str]:
    evidence = complete_quality_evidence()
    evidence["policy_design_case"] = case
    scorecard = scorecard_for(canary_kind=canary_kind, quality_evidence=evidence)
    return blocking_codes(scorecard)


def _valid_external_audit_record() -> dict[str, Any]:
    return {
        "schema_version": "policyos.policy_design_case.external_audit_record.v1",
        "record_family": "publication_trust_and_external_governance.v1",
        "record_id": "external-audit-R_hds_red_control",
        "run_id": "R_hds_red_control",
        "status": "pass",
        "public_archive": {
            "path": "audit/R_hds_red_control.polisyos-audit.tar.gz",
            "sha256": sha("a"),
            "size_bytes": 2048,
            "verifiable_without_private_operator_context": True,
        },
        "core_audit": {
            "package_format": "polisyos-audit-v1",
            "prov_json": {
                "path": "provenance/prov.json",
                "status": "pass",
                "entity_count": 3,
                "activity_count": 2,
                "agent_count": 1,
            },
            "slsa": {
                "attestation_path": "slsa/attestation.json",
                "signature_path": "slsa/signature.json",
                "transparency_path": "slsa/transparency_entry.json",
                "status": "pass",
            },
            "verifier": {
                "module": "polisyos.core.audit.verifier.AuditPackageVerifier",
                "status": "pass",
            },
            "standalone_verifier": {
                "path": "verification/verify.py",
                "template": "polisyos.core.audit.standalone_verifier_template",
                "command": (
                    "python verification/verify.py audit/R_hds_red_control.polisyos-audit.tar.gz"
                ),
            },
            "safe_archive_tool": "polisyos.core.audit.safe_tar.safe_extract_tar",
        },
        "verification": {
            "overall_status": "PASS",
            "package_path": "audit/R_hds_red_control.polisyos-audit.tar.gz",
            "run_id": "R_hds_red_control",
            "failures": [],
            "warnings": [],
        },
        "exported_refs": {
            "policy_design_case": {
                "ref": "public://audit/R_hds_red_control/policy_design_case.json",
                "sha256": sha("b"),
            }
        },
        "public_private_boundary": {
            "private_operator_context_required": False,
            "public_ref_count": 1,
            "redacted_or_access_controlled": [],
        },
    }


def _pass1b_tenant_cas_approval_governance_record() -> dict[str, Any]:
    from polisyos.runtime.quality.pass1b_hardening import (
        build_pass1b_tenant_cas_approval_governance_record,
    )

    case_bindings = {
        "tenant_identity": {
            "record_ref": sha("a"),
            "tenant_id": "tenant-prod",
            "cell_id": "cell-a",
            "status": "pass",
            "runtime_event_ref": "event://tenant/identity/1",
        },
        "cas_ownership": {
            "record_ref": sha("b"),
            "owner_index_ref": sha("c"),
            "tenant_id": "tenant-prod",
            "read_scope_enforced": True,
            "status": "pass",
            "runtime_event_ref": "event://cas/ownership/1",
        },
        "artifact_tenant_mapping": {
            "record_ref": sha("d"),
            "descendant_map_ref": sha("e"),
            "api_decision_ref": sha("f"),
            "status": "pass",
            "runtime_event_ref": "event://artifacts/tenant-map/1",
        },
        "cas_manifest_governance": {
            "record_ref": sha("1"),
            "producer_metadata_ref": sha("2"),
            "governance_metadata_ref": sha("3"),
            "retention_class": "governed",
            "encryption_metadata_ref": sha("4"),
            "status": "pass",
            "runtime_event_ref": "event://cas/manifest-governance/1",
        },
        "approval_authority": {
            "record_ref": sha("5"),
            "approval_packet_ref": sha("6"),
            "scorecard_digest_ref": sha("7"),
            "projection_policy": "immutable_packet_projection",
            "status": "pass",
            "runtime_event_ref": "event://approval/authority/1",
        },
        "override_signature": {
            "record_ref": sha("8"),
            "override_packet_ref": sha("9"),
            "reviewer_identity_ref": sha("a"),
            "signature_ref": "signature://reviewer-alpha",
            "signature_class": "internal_reviewer_attestation",
            "non_overridable_blockers_enforced": True,
            "status": "pass",
            "runtime_event_ref": "event://approval/override/1",
        },
        "decision_lifecycle": {
            "record_ref": sha("b"),
            "decision_packet_ref": sha("c"),
            "published_artifact_ref": sha("d"),
            "validity_lifecycle_ref": sha("e"),
            "continuous_governance_ref": sha("f"),
            "status": "pass",
            "runtime_event_ref": "event://decision/lifecycle/1",
        },
        "privacy_security_authority": {
            "record_ref": sha("0"),
            "privacy_compliance_report_ref": sha("1"),
            "security_assurance_report_ref": sha("2"),
            "runtime_enforcement_log_refs": [sha("3")],
            "canonical_metadata_ref": sha("4"),
            "status": "pass",
            "runtime_event_ref": "event://privacy-security/authority/1",
        },
        "human_review_authority": {
            "record_ref": sha("5"),
            "human_oversight_ref": sha("6"),
            "reviewer_identity_refs": [sha("7")],
            "separation_of_duty_ref": sha("8"),
            "rubber_stamp_risk": "low",
            "effective_oversight": True,
            "status": "pass",
            "runtime_event_ref": "event://human-review/authority/1",
        },
        "privileged_action_authority": {
            "record_ref": sha("9"),
            "privileged_action_ledger_ref": sha("a"),
            "dual_control_ref": sha("b"),
            "before_after_hash_refs": [sha("c")],
            "tamper_evident_attribution_ref": sha("d"),
            "status": "pass",
            "runtime_event_ref": "event://privileged-action/authority/1",
        },
        "signing_public_trust": {
            "record_ref": sha("e"),
            "signing_authority_matrix_ref": sha("f"),
            "key_lifecycle_refs": [sha("0")],
            "release_attestation_ref": sha("1"),
            "public_packet_signature_ref": "signature://public-packet",
            "trust_status": "valid",
            "status": "pass",
            "runtime_event_ref": "event://signing/public-trust/1",
        },
        "recall_retraction": {
            "record_ref": sha("2"),
            "recall_authority_ref": sha("3"),
            "retraction_authority_ref": sha("4"),
            "contestability_hook_ref": sha("5"),
            "status": "pass",
            "runtime_event_ref": "event://governance/recall-retraction/1",
        },
        "public_trust": {
            "record_ref": sha("6"),
            "public_export_ref": sha("7"),
            "external_audit_archive_ref": sha("8"),
            "standalone_verifier_ref": sha("9"),
            "public_contestability_ref": sha("a"),
            "status": "pass",
            "runtime_event_ref": "event://public-trust/1",
        },
    }
    pdd_bindings = [
        _pass1b_pdd("PDD-022", "tenant_identity"),
        _pass1b_pdd("PDD-023", "cas_ownership"),
        _pass1b_pdd("PDD-024", "artifact_tenant_mapping"),
        _pass1b_pdd("PDD-025", "cas_manifest_governance"),
        _pass1b_pdd("PDD-028", "approval_authority"),
        _pass1b_pdd("PDD-029", "override_signature"),
        _pass1b_pdd("PDD-030", ["decision_lifecycle", "recall_retraction"]),
        _pass1b_pdd("PDD-033", "privacy_security_authority"),
        _pass1b_pdd("PDD-058", ["human_review_authority", "override_signature"]),
        _pass1b_pdd("PDD-095", "privileged_action_authority"),
        _pass1b_pdd("PDD-096", ["signing_public_trust", "public_trust"]),
    ]
    return build_pass1b_tenant_cas_approval_governance_record(
        record_id="pass1b-hardening-rec-1",
        case_id="pdc-R_hds_red_control",
        run_id="R_hds_red_control",
        job_id="job-hds-red-control",
        tenant_id="tenant-prod",
        cell_id="cell-a",
        case_bindings=case_bindings,
        pdd_bindings=pdd_bindings,
        evidence_ref=sha("1"),
        runtime_event_ref="event://policy-design-case/pass1b-hardening/1",
    )


def _pass1b_pdd(pdd_id: str, surfaces: str | list[str]) -> dict[str, Any]:
    surface_list = [surfaces] if isinstance(surfaces, str) else surfaces
    return {
        "pdd_id": pdd_id,
        "surface": surface_list[0],
        "surfaces": surface_list,
        "record_ref": f"policy_design_case.pass1b.{pdd_id.lower()}",
        "evidence_ref": sha("f"),
        "runtime_event_ref": f"event://policy-design-case/pass1b/{pdd_id}",
        "owner": "team-quality-closeout",
        "status": "implemented",
    }


def _valid_config_release_hardening_record() -> dict[str, Any]:
    return {
        "schema_version": (
            "policyos.runtime.policy_design_case.config_release_deployment_migration_hardening.v1"
        ),
        "contract_id": ("policy_design_case.config_release_deployment_migration_hardening.v1"),
        "record_family": "publication_trust_and_external_governance.v1",
        "record_id": "config-release-hardening-R_hds_red_control",
        "run_id": "R_hds_red_control",
        "status": "pass",
        "pdd_ids": [
            "PDD-072",
            "PDD-075",
            "PDD-076",
            "PDD-079",
            "PDD-080",
            "PDD-081",
            "PDD-082",
        ],
        "deployment_parity": {
            "deployment_unit_refs": [sha("1")],
            "required_service_matrix": [
                _service_matrix_row("authz_opa"),
                _service_matrix_row("state_store"),
                _service_matrix_row("generated_clients"),
                _service_matrix_row("resource_quotas"),
                _service_matrix_row("release_gates"),
            ],
            "parity_diff": {"status": "match", "diff_ref": sha("2")},
            "topology_ref": sha("3"),
            "promotion_gate_refs": [sha("4")],
        },
        "release_supply_chain": {
            "release_provenance_ref": sha("5"),
            "lockfile_fingerprints": {"uv.lock": sha("6")},
            "generated_artifact_fingerprints": {"runtime_api_client": sha("7")},
            "sbom_ref": sha("8"),
            "attestation_ref": sha("9"),
            "signing_ref": sha("a"),
            "promotion_gate_refs": [sha("b")],
            "dirty_tree_clean": True,
            "untracked_artifact_count": 0,
        },
        "persisted_state_migration": {
            "migration_exercise_refs": [sha("c")],
            "compatibility_fixture_refs": [sha("d")],
            "historical_decision_checks": [
                {
                    "artifact_family": "policy_design_case",
                    "read_status": "pass",
                    "replay_status": "pass",
                    "migrate_status": "pass",
                    "reissue_status": "pass",
                    "withdraw_status": "pass",
                    "evidence_ref": sha("e"),
                }
            ],
            "typed_incompatibility_explanations": [],
        },
        "quarantine_shim_lifecycle": {
            "ledger_ref": sha("f"),
            "active_usage_ids": [],
            "expired_usage_ids": [],
            "approved_exception_refs": [],
            "serious_run_usage_scan_ref": sha("0"),
        },
        "generated_surface_drift": {
            "fingerprints": {
                "openapi": sha("1"),
                "generated_client": sha("2"),
                "dashboard_validator": sha("3"),
                "cli": sha("4"),
                "docs": sha("5"),
                "release_snapshot": sha("6"),
            },
            "runtime_to_generated_diff": {"status": "match", "diff_ref": sha("7")},
            "negative_consumer_test_refs": [sha("8")],
        },
        "runbook_automation": {
            "manual_gate_inventory_ref": sha("9"),
            "manual_gates": [
                {
                    "gate_id": "publication-approval",
                    "owner": "team-quality-closeout",
                    "reviewer_role": "policy_reviewer",
                    "status": "pass",
                    "signed_review_ref": sha("a"),
                    "evidence_ref": sha("b"),
                }
            ],
            "automation_candidate_classification_ref": sha("c"),
            "stale_manual_gate_ids": [],
        },
        "retention_deletion_replay": {
            "retention_replay_matrix_ref": sha("d"),
            "deletion_minimization_scenario_refs": [sha("e")],
            "public_private_auditability_ref": sha("f"),
            "replay_evidence_ref": sha("0"),
            "jurisdiction_blockers": [],
        },
        "evidence_ref": sha("1"),
        "runtime_event_ref": "event://policy-design-case/config-release-hardening/1",
    }


def _service_matrix_row(service: str) -> dict[str, str]:
    return {
        "service": service,
        "local": "real",
        "staging": "real",
        "production": "real",
    }


def _runtime_producer_evidence(
    *,
    evidence_id: str,
    producer: str,
    ref_char: str,
    provenance_kind: str = "runtime_emitted",
    status: str = "accepted",
    blockers: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    ref = sha(ref_char)
    selected_refs, rejected_refs = _producer_contract_candidate_refs(producer)
    payload = {
        "evidence_id": evidence_id,
        "producer": producer,
        "producer_component": f"polisyos.{producer}",
        "producer_owner": "team-domain-producers",
        "provenance_kind": provenance_kind,
        "source_surface": "runtime.producer_output",
        "evidence_ref": ref,
        "cas_ref": ref,
        "runtime_event_ref": sha("e"),
        "execution_started_at": "2026-05-17T09:00:00+00:00",
        "schema_name": f"policyos.policy_design_case.{producer}_producer_evidence.v1",
        "status": status,
        "candidate_refs": [*selected_refs, *rejected_refs],
        "selected_candidate_refs": selected_refs,
        "rejected_candidate_refs": rejected_refs,
        "source_rights_refs": [f"rights:{producer}:runtime"],
        "freshness_refs": [f"freshness:{producer}:2026-05-17"],
        "quality_refs": [f"quality:{producer}:pass"],
        "snapshot_refs": [sha(ref_char)],
        "blocker_refs": [],
    }
    if blockers is not None:
        payload["blockers"] = blockers
    return payload


def _producer_contract_candidate_refs(producer: str) -> tuple[list[str], list[str]]:
    selected_by_producer = {
        "lex": ["norm.ua.credit_eligibility"],
        "fabric": ["production-msme-panel"],
        "data_forge": ["data-forge-snapshot-1"],
        "scholar": ["scholar-lit-1", "literature:msme-survival-review"],
        "foundry": ["causal.difference_in_differences"],
        "options_objectives": ["options-objectives-tradeoffs-rec-1"],
    }
    rejected_by_producer = {
        "lex": ["norm.ua.procurement_fixture"],
        "fabric": ["fixture-source"],
        "data_forge": ["stale-domain-snapshot"],
        "scholar": ["literature:procurement-fixture"],
        "foundry": ["descriptive.summary"],
        "options_objectives": ["option-untargeted-subsidy"],
    }
    return (
        selected_by_producer.get(producer, [f"{producer}:selected"]),
        rejected_by_producer.get(producer, [f"{producer}:rejected"]),
    )


def _evidence_line() -> dict[str, Any]:
    return {
        "schema_version": "policyos.runtime.policy_design_case.evidence_line.v1",
        "line_id": "line-data",
        "portfolio_id": "portfolio-rec-1",
        "portfolio_strand_id": "data-method-literature",
        "claim_id": "rec_1",
        "evidence_strand": "data",
        "source_lineage": {
            "source_id": "production-msme-panel",
            "source_ref": sha("7"),
            "lineage_refs": [sha("8")],
        },
        "method_id": "causal.difference_in_differences",
        "method_assumptions": [
            "parallel trends holds after bank and oblast controls",
        ],
        "specification_id": "did.att.baseline.v1",
        "producer_identity": {
            "component": "polisyos.foundry.methods.causal",
            "version": "2026.05.17+wave16",
            "owner": "team-science-quality",
        },
        "execution_context": {
            "run_id": "run-policy-design-1",
            "job_id": "job-evidence-line-1",
            "tenant_id": "tenant-prod",
            "trace_id": "trace-evidence-line-1",
        },
        "evidence_ref": sha("a"),
        "runtime_event_ref": sha("b"),
    }


def _independence_map() -> dict[str, Any]:
    return {
        "schema_version": "policyos.runtime.policy_design_case.independence_map.v1",
        "map_id": "independence-map-rec-1",
        "portfolio_ids": ["portfolio-rec-1"],
        "claim_ids": ["rec_1"],
        "raw_evidence_line_count": 1,
        "effective_independent_evidence_count": 1,
        "collapse_dimensions_used": ["claim_ids", "evidence_strand"],
        "collapse_clusters": [
            {
                "cluster_id": "independent-cluster-1",
                "line_ids": ["line-data"],
                "raw_line_count": 1,
                "effective_line_count": 1,
                "representative_line_id": "line-data",
                "collapse_reasons": [],
                "collapse_dimensions": {
                    "claim_ids": ["rec_1"],
                    "evidence_strand": "data",
                },
            }
        ],
        "effective_mass_report": {
            "raw_evidence_line_count": 1,
            "effective_independent_evidence_count": 1,
            "raw_support_line_count": 1,
            "raw_counterevidence_line_count": 0,
            "raw_context_line_count": 0,
            "effective_support_mass": 1.0,
            "effective_counterevidence_mass": 0.0,
            "effective_context_mass": 0.0,
            "balance_status": "support_dominant",
            "independence_status": "singular",
            "largest_hard_collapse_cluster": 0,
            "dominant_collapse_reasons": [],
            "support_line_ids": ["line-data"],
            "counterevidence_line_ids": [],
            "context_line_ids": [],
            "limiting_deficits": [],
            "raw_count_display_policy": {
                "raw_count_authority": "diagnostic_only",
                "must_display_with": [
                    "effective_independent_evidence_count",
                    "effective_support_mass",
                    "collapse_reasons",
                ],
            },
        },
        "graded_independence": {
            "enabled": False,
            "feature_flag": "policy_design_case.graded_independence_weights",
            "feature_flag_enabled": False,
            "authority_posture": "strict_hard_collapse_only",
            "governed_config": {"status": "not_configured"},
        },
        "rare_domain_scarcity": {
            "status": "not_rare_domain",
            "support_inflation_allowed": False,
            "effective_support_mass_after_scarcity": 1.0,
            "authority_effect": "none",
        },
        "evidence_ref": sha("1"),
        "runtime_event_ref": sha("2"),
    }


def _previous_wave_refs() -> dict[str, list[str]]:
    return {
        "portfolio_design_refs": ["portfolio-rec-1"],
        "evidence_line_refs": ["line-data"],
        "independence_map_refs": ["independence-map-rec-1"],
    }


def _disconfirming_ledger() -> dict[str, Any]:
    return {
        "schema_version": ("policyos.runtime.policy_design_case.disconfirming_evidence_ledger.v1"),
        "ledger_id": "disconfirming-ledger-rec-1",
        "portfolio_id": "portfolio-rec-1",
        "claim_ids": ["rec_1"],
        "disconfirming_lines": ["placebo-pre-period"],
        "ir_falsification_reports": [
            {
                "tests": [
                    {
                        "test_name": "placebo-pre-period",
                        "test_kind": "placebo_treatment",
                        "passed": True,
                        "p_value": 0.41,
                        "interpretation": (
                            "Placebo effect is statistically indistinguishable from zero."
                        ),
                        "is_critical": True,
                    }
                ],
                "n_passed": 1,
                "n_failed": 0,
                "overall_passed": True,
                "critical_failures": [],
            }
        ],
        "adversarial_plans": [
            {
                "strategy": "grid_extreme",
                "parameter_specs": [
                    {
                        "name": "credit_shock",
                        "lower_bound": -0.35,
                        "upper_bound": 0.35,
                        "baseline": 0.0,
                    }
                ],
                "max_iterations": 50,
                "vulnerability_threshold": -0.05,
                "tail_percentile": 0.05,
                "stop_on_first_vulnerability": False,
                "collect_top_k": 20,
            }
        ],
        "severe_tests": [
            {
                "test_id": "severe-placebo-pre-period",
                "line_id": "placebo-pre-period",
                "claim_id": "rec_1",
                "test_kind": "negative_control",
                "severity": "severe",
                "rationale": (
                    "A pre-period placebo had a high chance to expose anticipatory "
                    "trends that would invalidate the recommended targeting claim."
                ),
                "expected_failure_mode": "pre_policy_trend_violation",
                "result": "passed",
                "evidence_ref": sha("3"),
                "runtime_event_ref": sha("4"),
            }
        ],
        "evidence_ref": sha("5"),
        "runtime_event_ref": sha("6"),
        "previous_wave_refs": _previous_wave_refs(),
    }


def _multiverse_specification_curve() -> dict[str, Any]:
    return {
        "schema_version": ("policyos.runtime.policy_design_case.multiverse_specification_curve.v1"),
        "curve_id": "multiverse-rec-1",
        "claim_ids": ["rec_1"],
        "portfolio_id": "portfolio-rec-1",
        "source_kind_counts": {
            "backtesting": 1,
            "foundry_sensitivity": 1,
            "scientist_discovery": 1,
            "scientist_doe": 1,
        },
        "specification_records": [
            {
                "specification_id": "backtest-placebo",
                "claim_ids": ["rec_1"],
                "source_kind": "backtesting",
                "decision": "rejected",
                "estimate": 0.01,
                "standard_error": 0.02,
                "sign": "positive",
                "significant": False,
                "rejection_reason": "Backtest scenario was underpowered.",
                "drivers": {"model_family": "placebo_backtest"},
            },
            {
                "specification_id": "matched-did",
                "claim_ids": ["rec_1"],
                "source_kind": "foundry_sensitivity",
                "decision": "defensible",
                "estimate": 0.03,
                "standard_error": 0.01,
                "sign": "positive",
                "significant": True,
                "drivers": {"model_family": "matched_did"},
            },
            {
                "specification_id": "event-study",
                "claim_ids": ["rec_1"],
                "source_kind": "scientist_discovery",
                "decision": "defensible",
                "estimate": 0.04,
                "standard_error": 0.01,
                "sign": "positive",
                "significant": True,
                "drivers": {"model_family": "event_study"},
            },
            {
                "specification_id": "twfe-baseline",
                "claim_ids": ["rec_1"],
                "source_kind": "scientist_doe",
                "decision": "defensible",
                "estimate": 0.04,
                "standard_error": 0.01,
                "sign": "positive",
                "significant": True,
                "drivers": {"model_family": "two_way_fixed_effects"},
            },
        ],
        "defensible_specifications": [
            {"specification_id": "event-study"},
            {"specification_id": "matched-did"},
            {"specification_id": "twfe-baseline"},
        ],
        "rejected_specifications": [
            {
                "specification_id": "backtest-placebo",
                "rejection_reason": "Backtest scenario was underpowered.",
            }
        ],
        "result_distribution": {
            "n_specifications": 4,
            "defensible_count": 3,
            "rejected_count": 1,
            "sign_counts": {"positive": 4, "negative": 0, "zero": 0},
            "estimate_min": 0.01,
            "estimate_max": 0.04,
            "estimate_median": 0.035,
            "share_significant": 0.75,
        },
        "drivers_of_divergence": [
            {
                "axis": "model_family",
                "values": [
                    "event_study",
                    "matched_did",
                    "placebo_backtest",
                    "two_way_fixed_effects",
                ],
            }
        ],
        "claim_markers": [
            {
                "claim_id": "rec_1",
                "marker": "robust",
                "reason_codes": ["defensible_specifications_agree"],
            }
        ],
        "evidence_ref": sha("2"),
        "runtime_event_ref": sha("e"),
        "previous_wave_refs": _previous_wave_refs(),
    }


def _synthesis_report() -> dict[str, Any]:
    return {
        "schema_version": ("policyos.runtime.policy_design_case.evidence_synthesis_report.v1"),
        "contract_id": "policy_design_case.evidence_synthesis_report.v1",
        "report_id": "synthesis-rec-1",
        "claim_ids": ["rec_1"],
        "portfolio_id": "portfolio-rec-1",
        "multiverse_curve_refs": ["multiverse-rec-1"],
        "disconfirming_ledger_refs": ["disconfirming-ledger-rec-1"],
        "weighting_model": {
            "strategy": "inverse_variance",
            "rule_id": "ivw_defensible_only",
            "included_decisions": ["defensible"],
        },
        "heterogeneity_model": {
            "model": "random_effects",
            "tau_squared": 0.001,
            "i_squared": 0.18,
            "interpretation": "low",
        },
        "certainty_framework": {
            "framework": "GRADE-like",
            "rating": "moderate",
            "downgrade_reasons": [],
        },
        "publication_bias_treatment": {
            "method": "small_study_shadow_check",
            "status": "assessed",
            "small_study_effect": "not_detected",
        },
        "inclusion_policy": {
            "policy_id": "predeclared-portfolio-inclusion",
            "included_decisions": ["defensible"],
            "rationale": "Use defensible predeclared specifications for primary synthesis.",
        },
        "exclusion_policy": {
            "policy_id": "exclude-invalid-primary-include-sensitivity",
            "excluded_decisions": ["rejected"],
            "rationale": (
                "Rejected specifications remain visible in sensitivity and divergence checks."
            ),
        },
        "synthesis_estimate": {
            "rule_id": "ivw_defensible_only",
            "estimate": 0.0367,
            "direction": "positive",
            "included_specification_ids": [
                "event-study",
                "matched-did",
                "twfe-baseline",
            ],
            "total_weight": 30000.0,
        },
        "claim_direction": "positive",
        "sensitivity_to_synthesis_rules": [
            {
                "rule_id": "equal_weight_with_backtests",
                "weighting": "equal",
                "included_decisions": ["defensible", "rejected"],
                "reasonable": True,
                "estimate": 0.03,
                "direction": "positive",
                "direction_changed": False,
                "included_specification_ids": [
                    "backtest-placebo",
                    "event-study",
                    "matched-did",
                    "twfe-baseline",
                ],
            }
        ],
        "information_saturation": {
            "status": "saturated",
            "effective_independent_evidence_count": 3,
            "minimum_effective_independent_evidence_count": 2,
            "recent_direction_changes": 0,
            "stopping_decision": "stop",
        },
        "effective_evidence_mass": {
            "effective_support_mass": 3.0,
            "effective_counterevidence_mass": 1.0,
            "effective_context_mass": 0.0,
            "collapse_reasons": [],
            "counterevidence_preserved": True,
            "raw_count_display_policy": {
                "raw_count_authority": "diagnostic_only",
                "must_display_with": [
                    "effective_support_mass",
                    "effective_counterevidence_mass",
                    "collapse_reasons",
                ],
            },
        },
        "run_cost_proportionality": {
            "status": "proportional",
            "budget_tier": "standard",
            "estimated_run_cost_usd": 18.25,
            "marginal_cost_usd": 1.5,
            "marginal_information_gain": 0.0,
            "cost_evidence_ref": sha("6"),
            "proportionality_rationale": (
                "Information saturation permits stopping without hiding the "
                "recorded disconfirming backtest."
            ),
        },
        "divergence_assessment": {
            "status": "convergent",
            "reason_codes": ["reasonable_synthesis_rules_preserve_direction"],
        },
        "divergence_evidence": [],
        "blockers": [],
        "evidence_ref": sha("3"),
        "runtime_event_ref": sha("e"),
        "previous_wave_refs": {
            **_previous_wave_refs(),
            "multiverse_curve_refs": ["multiverse-rec-1"],
            "disconfirming_ledger_refs": ["disconfirming-ledger-rec-1"],
        },
    }


def _run_cost_component(cost: float, ref_char: str) -> dict[str, Any]:
    return {
        "budget_usd": cost + 1.0,
        "actual_cost_usd": cost,
        "evidence_ref": sha(ref_char),
    }


def _run_cost_proportionality_ledger() -> dict[str, Any]:
    return {
        "schema_version": (
            "policyos.runtime.policy_design_case.run_cost_proportionality_ledger.v1"
        ),
        "ledger_id": "run-cost-ledger-R_hds_red_control",
        "run_id": "R_hds_red_control",
        "job_id": "job-hds-red-control",
        "authority_level": "production",
        "public_impact": "high",
        "runtime_performance_budget": _run_cost_component(3.0, "1"),
        "foundry_cost_model": _run_cost_component(4.0, "2"),
        "scientist_budget": _run_cost_component(5.0, "3"),
        "doe_search_budget": _run_cost_component(2.5, "4"),
        "provider_cost": _run_cost_component(1.5, "5"),
        "elapsed_time_budget": {
            "budget_seconds": 3600,
            "actual_seconds": 1800,
            "evidence_ref": sha("6"),
        },
        "human_review_burden": {
            "budget_reviewer_hours": 3.0,
            "actual_reviewer_hours": 1.5,
            "evidence_ref": sha("7"),
        },
        "evidence_depth_budget": {
            "authority_level": "production",
            "public_impact": "high",
            "observed_heterogeneity": "moderate",
            "effective_independent_evidence_count": 4,
            "minimum_effective_independent_evidence_count": 4,
            "stopping_rule": "stop after saturation and no recent direction changes",
            "stopping_decision": "stop",
            "stopping_rule_result_ref": sha("8"),
        },
        "proportionality_evidence": {
            "status": "proportional",
            "rationale": "Production authority and high public impact justify Wave 30 spend.",
            "evidence_ref": sha("9"),
        },
        "budget_change_records": [],
        "evidence_ref": sha("a"),
        "runtime_event_ref": "event://runtime/run-cost/R_hds_red_control",
    }


def _policy_design_case(**overrides: object) -> dict[str, Any]:
    case: dict[str, Any] = {
        "schema_version": "policyos.runtime.policy_design_case.v1",
        "profile": "policy_design",
        "case_id": "pdc-R_hds_red_control",
        "run_id": "R_hds_red_control",
        "job_id": "job-hds-red-control",
        "owner": "team-runtime-quality",
        "runtime_authority": {
            "provenance_kind": "runtime_emitted",
            "cas_ref": sha("1"),
            "runtime_event_ref": sha("2"),
            "same_input_closure_ref": sha("3"),
        },
        "intent_envelope": {
            "intent_ref": sha("4"),
            "jurisdiction": "UA",
            "target_population": "wartime MSMEs",
            "policy_time": "2026-05-15",
            "data_time": "2024-2026",
            "desired_outcome": "msme survival",
            "requester_preferred_conclusion": "expand credit support",
            "independent_analysis_required": True,
        },
        "capability_ledger": {
            "ledger_ref": sha("5"),
            "duties": [
                {"capability": "lex", "state": "selected", "evidence_ref": sha("6")},
                {"capability": "fabric", "state": "selected", "evidence_ref": sha("7")},
                {"capability": "scholar", "state": "selected", "evidence_ref": sha("8")},
                {"capability": "foundry", "state": "selected", "evidence_ref": sha("9")},
                {"capability": "scientist", "state": "selected", "evidence_ref": sha("a")},
                {"capability": "claim_compiler", "state": "selected", "evidence_ref": sha("b")},
            ],
        },
        "producer_evidence": [
            _runtime_producer_evidence(
                evidence_id="lex-norm-1",
                producer="lex",
                ref_char="c",
            ),
            _runtime_producer_evidence(
                evidence_id="fabric-source-1",
                producer="fabric",
                ref_char="7",
            ),
            _runtime_producer_evidence(
                evidence_id="data-forge-snapshot-1",
                producer="data_forge",
                ref_char="d",
            ),
            _runtime_producer_evidence(
                evidence_id="scholar-lit-1",
                producer="scholar",
                ref_char="e",
            ),
            _runtime_producer_evidence(
                evidence_id="foundry-method-1",
                producer="foundry",
                ref_char="f",
            ),
            _runtime_producer_evidence(
                evidence_id="options-objectives-1",
                producer="options_objectives",
                ref_char="0",
            ),
        ],
        "evidence_portfolios": [
            {
                "schema_version": (
                    "policyos.runtime.policy_design_case.evidence_portfolio_design.v1"
                ),
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
                            "allowed_models": [
                                "two_way_fixed_effects",
                                "event_study",
                            ],
                            "allowed_covariate_sets": [
                                "baseline",
                                "bank_controls",
                            ],
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
                            "stop_when": ("new independent strands no longer change conclusion"),
                        },
                        "cost_proportionality": {
                            "budget_tier": "standard",
                            "proportionality_rationale": (
                                "Production authority major claim warrants two "
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
                "independence_map_ref": sha("1"),
                "effective_independent_evidence_count": 3,
                "multiverse_report_ref": sha("2"),
                "synthesis_report_ref": sha("3"),
                "disconfirming_line_refs": [sha("4")],
                "stopping_rule_result_ref": sha("5"),
                "cost_proportionality_ref": sha("6"),
            }
        ],
        "evidence_lines": [_evidence_line()],
        "independence_maps": [_independence_map()],
        "multiverse_specification_curves": [_multiverse_specification_curve()],
        "disconfirming_evidence_ledgers": [_disconfirming_ledger()],
        "synthesis_reports": [_synthesis_report()],
        "run_cost_proportionality_ledgers": [_run_cost_proportionality_ledger()],
        "arguments": [
            {
                "argument_id": "arg-rec-1",
                "claim_id": "rec_1",
                "strategy": "policy_design_claim_argument",
                "evidence_refs": [sha("c"), sha("d"), sha("e"), sha("f")],
            }
        ],
        "warrants": [
            {
                "warrant_id": "warrant-rec-1",
                "claim_id": "rec_1",
                "warrant_text": (
                    "Runtime legal, data, method, and literature evidence support the claim."
                ),
                "assumptions": ["Production panel and legal authority refs remain in scope."],
                "applicability_limits": [
                    "No extrapolation outside wartime MSMEs in the observed jurisdiction."
                ],
                "requires_explanation_reliability": False,
                "explanation_trust_affects_acceptance": False,
                "berl_reliability_refs": [sha("7")],
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
                "stance": "counter_evidence",
                "visibility": "reviewer_visible",
                "status": "assessed",
                "assessment_result": "bounded",
                "evidence_ref": sha("8"),
                "runtime_event_ref": sha("e"),
            }
        ],
        "assurance_deficits": [
            {
                "deficit_id": "deficit-assessment-rec-1",
                "claim_id": "rec_1",
                "deficit_kind": "no_unresolved_assurance_deficit",
                "status": "none",
                "evidence_ref": sha("9"),
                "runtime_event_ref": sha("e"),
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
                "independent_analysis_result": "no_capture_detected",
                "independent_alternative_analyses": [
                    {
                        "alternative_id": "baseline-no-action",
                        "conclusion": ("no action has lower fiscal risk but worse survival impact"),
                        "evidence_refs": [sha("1")],
                    },
                    {
                        "alternative_id": "untargeted-subsidy",
                        "conclusion": ("untargeted subsidy is rejected on distributional grounds"),
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
                "evidence_ref": sha("0"),
                "runtime_event_ref": sha("e"),
            }
        ],
        "accepted_deficits": [],
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
        "final_major_claims": [
            {
                "claim_id": "rec_1",
                "assurance_node_id": "claim-node-rec-1",
                "claim_ref": sha("a"),
                "major": True,
                "text": "Target wartime credit support to eligible MSMEs.",
                "concept_refs": ["concept.wartime_msme_credit_support"],
                "legal_norm_refs": ["norm.ua.credit_eligibility"],
                "source_data_refs": ["production-msme-panel", "data-forge-snapshot-1"],
                "data_refs": ["production-msme-panel"],
                "method_refs": ["causal.difference_in_differences"],
                "norm_refs": ["norm.ua.credit_eligibility"],
                "scholar_refs": ["scholar-lit-1"],
                "literature_refs": ["scholar-lit-1"],
                "portfolio_refs": ["portfolio-rec-1"],
                "independence_refs": ["independence-map-rec-1"],
                "specification_curve_refs": ["multiverse-rec-1"],
                "disconfirming_refs": ["disconfirming-ledger-rec-1"],
                "synthesis_refs": ["synthesis-rec-1"],
                "argument_refs": ["arg-rec-1"],
                "warrant_refs": ["warrant-rec-1"],
                "rebuttal_refs": ["rebuttal-rec-1"],
                "counter_evidence_refs": ["counter-evidence-rec-1"],
                "assurance_deficit_refs": ["deficit-assessment-rec-1"],
                "requester_capture_challenge_refs": ["requester-capture-rec-1"],
                "blocker_refs": [],
                "accepted_deficit_refs": [],
                "objective_tradeoff_refs": ["options-objectives-tradeoffs-rec-1"],
                "uncertainty_refs": ["foundry-uncertainty-1"],
                "numerical_semantics_refs": ["ir.numerical_semantics.msme_survival"],
                "monitoring_refs": ["monitoring.plan.rec_1"],
                "prediction_refs": ["prediction-rec-1"],
                "observed_outcome_refs": ["outcome-link-rec-1"],
                "reassessment_refs": ["reassessment-rec-1"],
                "future_prior_refs": ["future-prior-rec-1"],
                "expert_judgement_refs": ["expert-judgement-rec-1"],
                "consultation_objection_refs": ["objection-1"],
                "selected_producer_refs": {
                    "lex": ["norm.ua.credit_eligibility"],
                    "fabric": ["production-msme-panel"],
                    "data_forge": ["data-forge-snapshot-1"],
                    "scholar": ["scholar-lit-1"],
                    "foundry": [
                        "causal.difference_in_differences",
                        "foundry-uncertainty-1",
                    ],
                    "options_objectives": ["options-objectives-tradeoffs-rec-1"],
                },
            }
        ],
        "human_oversight": {
            "schema_version": "policyos.runtime.policy_design_case.human_oversight.v1",
            "status": "pass",
            "authority_profile": "production",
            "review_count": 4,
            "reviewer_count": 4,
            "reviewer_identities": ["reviewer-alpha", "reviewer-beta"],
            "reviewer_roles": ["policy_reviewer", "external_domain_reviewer"],
            "review_scope": {
                "claim_ids": ["rec_1"],
                "surfaces": ["final_major_claims", "evidence_portfolios"],
            },
            "conflicts": [],
            "reviewer_independence_rate": 1.0,
            "producer_independence": {
                "separation_of_duty_attested": True,
                "attestation_ref": sha("6"),
            },
            "separation_of_duty_attestation_rate": 1.0,
            "exposure_order_controls": {
                "policy_claims_blinded_until_evidence_reviewed": True,
                "order_refs": ["exposure-order-rec-1"],
            },
            "time_spent_seconds": 1800,
            "dissent_records": [],
            "change_requests": [
                {
                    "request_id": "change-1",
                    "claim_id": "rec_1",
                    "status": "accepted",
                    "summary": "Narrow eligibility language and surface residual risk.",
                }
            ],
            "override_decisions": [],
            "approve_without_change_rate": 0.25,
            "rubber_stamp_risk": "low",
            "voi_escalation_ref": sha("7"),
            "accepted_deficit_refs": [],
            "effective_oversight": True,
            "oversight_ref": sha("6"),
            "evidence_ref": sha("6"),
            "runtime_event_ref": "event://policy-design-case/human-oversight/1",
        },
        "structured_expert_judgements": [
            {
                "schema_version": (
                    "policyos.runtime.policy_design_case.structured_expert_judgement.v1"
                ),
                "judgement_id": "expert-judgement-rec-1",
                "claim_ids": ["rec_1"],
                "elicitation_method": "delphi",
                "expert_provenance": {
                    "expert_id": "expert-1",
                    "field": "wartime MSME finance",
                    "credential_ref": sha("1"),
                },
                "conflicts": [],
                "uncertainty": {"interval": [0.1, 0.4], "confidence": 0.8},
                "classification": "judgement_not_data",
                "evidence_ref": sha("2"),
                "runtime_event_ref": "event://policy-design-case/expert-judgement/1",
            }
        ],
        "consultations": [
            {
                "schema_version": ("policyos.runtime.policy_design_case.consultation_record.v1"),
                "consultation_id": "consultation-rec-1",
                "stakeholder_map": {
                    "stakeholders": [
                        {"stakeholder_id": "msme", "name": "MSMEs"},
                        {"stakeholder_id": "bank", "name": "Participating banks"},
                    ]
                },
                "consultation_plan": {
                    "plan_id": "consultation-plan-1",
                    "comment_period": "2026-05-01/2026-05-14",
                },
                "public_comments": [
                    {
                        "comment_id": "comment-1",
                        "stakeholder_id": "bank",
                        "summary": "Implementation burden needs monitoring.",
                    }
                ],
                "objection_records": [
                    {
                        "objection_id": "objection-1",
                        "claim_id": "rec_1",
                        "severity": "high",
                        "status": "unresolved",
                        "visibility": "public",
                        "comment_id": "comment-1",
                    }
                ],
                "response_to_comment_reasoning": [
                    {
                        "response_id": "response-1",
                        "objection_id": "objection-1",
                        "reasoning": "Monitoring plan adds bank-burden indicators.",
                    }
                ],
                "evidence_ref": sha("3"),
                "runtime_event_ref": "event://policy-design-case/consultation/1",
            }
        ],
        "external_audit_record": _valid_external_audit_record(),
        **policy_design_phase28_5_records(),
        **policy_design_phase29_1_records(),
        **policy_design_phase29_2_records(),
        "pass1b_tenant_cas_approval_governance": (_pass1b_tenant_cas_approval_governance_record()),
        "config_release_deployment_migration_hardening": (_valid_config_release_hardening_record()),
        "implementation_monitoring_evaluation": {
            "schema_version": (
                "policyos.runtime.policy_design_case.implementation_monitoring_evaluation.v1"
            ),
            "record_id": "implementation-monitoring-rec-1",
            "case_id": "pdc-R_hds_red_control",
            "claim_ids": ["rec_1"],
            "implementation_contract": {
                "contract_id": "implementation-contract-rec-1",
                "intervention_ref": "option-targeted-credit",
                "responsible_owner": "team-policy-implementation",
                "start_date": "2026-06-01",
                "affected_claim_ids": ["rec_1"],
                "assumption_refs": ["assumption-parallel-trends"],
                "evidence_ref": sha("a"),
            },
            "monitoring_plan": {
                "plan_id": "monitoring.plan.rec_1",
                "indicators": [
                    {
                        "indicator_id": "msme_survival_rate",
                        "claim_id": "rec_1",
                        "data_source_refs": ["production-msme-panel"],
                        "thresholds": {"degradation_budget": 0.2},
                    }
                ],
                "observation_windows": [
                    {
                        "window_id": "post-publication-q1",
                        "start": "2026-06-01T00:00:00+00:00",
                        "end": "2026-09-01T00:00:00+00:00",
                    }
                ],
                "review_cadence": "monthly",
                "trigger_thresholds": ["ddm_readiness_R2"],
                "responsible_owners": ["team-ddm", "team-policy-implementation"],
                "evidence_ref": sha("b"),
            },
            "evaluation_design": {
                "design_id": "evaluation-design-rec-1",
                "design_type": "difference_in_differences_reassessment",
                "estimand": "ATT",
                "outcome_metrics": ["msme_survival_rate"],
                "comparison_strategy": "matched eligible non-recipients",
                "observation_windows": ["post-publication-q1"],
                "evidence_ref": sha("c"),
            },
            "publication_order": {
                "publication_authority_ref": sha("p"),
                "created_before_publication_authority": True,
            },
            "ddm_monitoring": {
                "shift_events": [
                    {
                        "event_id": "shift-risk-1",
                        "event_type": "ml.problem_15_7.shift_risk.v1",
                        "affected_claim_ids": ["rec_1"],
                        "affected_evidence_line_refs": ["line-data"],
                        "downstream_status": "publication_review_required",
                        "evidence_ref": sha("d"),
                        "runtime_event_ref": "event://ddm/shift-risk-1",
                    }
                ],
                "degradation_events": [
                    {
                        "event_id": "degradation-1",
                        "event_type": "ml.problem_15_7.degradation.v1",
                        "affected_claim_ids": ["rec_1"],
                        "affected_evidence_line_refs": ["line-data"],
                        "readiness_event_ids": ["readiness-1"],
                        "downstream_status": "publication_review_required",
                        "evidence_ref": sha("e"),
                        "runtime_event_ref": "event://ddm/degradation-1",
                    }
                ],
                "readiness_events": [
                    {
                        "event_id": "readiness-1",
                        "event_type": "ml.problem_15_7.readiness_state.v1",
                        "affected_claim_ids": ["rec_1"],
                        "affected_evidence_line_refs": ["line-data"],
                        "readiness_state": "R2",
                        "downstream_status": "publication_review_required",
                        "evidence_ref": sha("f"),
                        "runtime_event_ref": "event://ddm/readiness-1",
                    }
                ],
                "incident_events": [
                    {
                        "event_id": "incident-1",
                        "event_type": "ml.problem_15_7.incident_payload.v1",
                        "affected_claim_ids": ["rec_1"],
                        "affected_evidence_line_refs": ["line-data"],
                        "root_cause_event_ids": ["root-cause-1"],
                        "downstream_status": "publication_review_required",
                        "evidence_ref": sha("8"),
                        "runtime_event_ref": "event://ddm/incident-1",
                    }
                ],
                "root_cause_events": [
                    {
                        "event_id": "root-cause-1",
                        "event_type": "ml.problem_15_7.root_cause_bundle.v1",
                        "affected_claim_ids": ["rec_1"],
                        "affected_evidence_line_refs": ["line-data"],
                        "downstream_status": "publication_review_required",
                        "evidence_ref": sha("9"),
                        "runtime_event_ref": "event://ddm/root-cause-1",
                    }
                ],
            },
            "evidence_ref": sha("1"),
            "runtime_event_ref": "event://policy-design-case/implementation-monitoring/1",
        },
        "case_lifecycle": {
            "schema_version": "policyos.runtime.policy_design_case.case_lifecycle.v1",
            "ledger_id": "case-lifecycle-rec-1",
            "case_id": "pdc-R_hds_red_control",
            "current_state": "published",
            "events": [
                {
                    "event_id": "lifecycle-published",
                    "event_type": "published",
                    "previous_state": "approved",
                    "new_state": "published",
                    "evidence_refs": [sha("1")],
                    "runtime_event_ref": "event://policy-design-case/lifecycle/published",
                },
                {
                    "event_id": "lifecycle-validity-confirmed",
                    "event_type": "confirmed",
                    "previous_state": "published",
                    "new_state": "confirmed",
                    "evidence_refs": [sha("2")],
                    "runtime_event_ref": "event://policy-design-case/lifecycle/confirmed",
                },
            ],
            "continuous_governance_reports": {
                "reissue": sha("3"),
                "supersede": sha("4"),
                "withdraw": sha("5"),
                "validity": sha("6"),
            },
            "resolution_event_refs": ["lifecycle-validity-confirmed"],
            "evidence_ref": sha("7"),
            "runtime_event_ref": "event://policy-design-case/lifecycle",
        },
        "ex_post_learning": {
            "schema_version": "policyos.runtime.policy_design_case.ex_post_learning.v1",
            "record_id": "ex-post-learning-rec-1",
            "case_id": "pdc-R_hds_red_control",
            "claim_prediction_links": [
                {
                    "link_id": "outcome-link-rec-1",
                    "claim_id": "rec_1",
                    "prediction_ref": "prediction-rec-1",
                    "observed_outcome_ref": "observed-outcome-rec-1",
                    "reassessment_ref": "reassessment-rec-1",
                    "reassessment_status": "confirmed",
                    "future_method_prior_ref": "future-prior-rec-1",
                    "future_uncertainty_prior_ref": "future-prior-rec-1",
                    "evidence_ref": sha("a"),
                    "runtime_event_ref": "event://policy-design-case/ex-post/outcome-link",
                }
            ],
            "calibration": {
                "calibration_report_refs": [sha("b")],
                "backtesting_report_refs": [sha("c")],
                "calibration_leaderboard_ref": sha("d"),
                "track_record_ref": sha("e"),
            },
            "memory_contamination_check": {
                "status": "clean",
                "policy": {
                    "hidden_ref_ids": [],
                    "hidden_suite_ids": [],
                    "canary_tokens": [],
                },
                "findings": [],
                "evidence_ref": sha("f"),
                "runtime_event_ref": "event://policy-design-case/ex-post/memory-clean",
            },
            "learning_records": [
                {
                    "learning_id": "learning-rec-1",
                    "scope": "wartime_msme_support",
                    "applicability": ["UA", "production_msme_panel"],
                    "revocation_conditions": ["new legal regime", "data schema change"],
                    "memory_contamination_controls": ["hidden_eval_scan_clean"],
                    "evidence_ref": sha("0"),
                }
            ],
            "evidence_ref": sha("1"),
            "runtime_event_ref": "event://policy-design-case/ex-post",
        },
        "case_maturity_profile": _case_maturity_profile(),
        "record_families": _record_family_coverage_rows(),
        "records": _runtime_record_family_records(),
        **_phase28_2_records(),
        **_phase28_3_records(),
        "options_objectives_tradeoffs": {
            "schema_version": (
                "policyos.runtime.policy_design_case.options_objectives_tradeoffs.v1"
            ),
            "record_id": "options-objectives-tradeoffs-rec-1",
            "producer_component": "polisyos.scientist.policy_design.objectives",
            "producer_owner": "team-science-quality",
            "provenance_kind": "runtime_emitted",
            "cas_ref": sha("0"),
            "evidence_ref": sha("0"),
            "runtime_event_ref": sha("e"),
            "status": "pass",
            "baseline_option": {
                "option_id": "option-no-action",
                "option_kind": "baseline_no_action",
                "label": "No additional wartime credit support.",
                "evidence_ref": sha("9"),
            },
            "candidate_options": [
                {
                    "option_id": "option-targeted-credit",
                    "label": "Target credit support to eligible MSMEs.",
                    "selected": True,
                    "evidence_ref": sha("a"),
                }
            ],
            "rejected_options": [
                {
                    "option_id": "option-untargeted-subsidy",
                    "reason": "Lower welfare under fiscal exposure and fairness constraints.",
                    "evidence_ref": sha("b"),
                }
            ],
            "objective_function": {
                "objective_id": "objective-msme-survival-fiscal-balance",
                "objective_ref": sha("c"),
                "direction": "maximize",
                "formula": "survival_gain - fiscal_risk_penalty",
            },
            "tradeoff_weights": [
                {
                    "weight_id": "tradeoff-survival-vs-fiscal-risk",
                    "metric": "fiscal_risk_penalty",
                    "weight": 0.35,
                    "source_ref": sha("d"),
                }
            ],
            "social_weights": {
                "weights_ref": sha("e"),
                "source": "foundry.welfare.social_weights",
                "groups": {"micro": 1.2, "small": 1.0, "medium": 0.8},
            },
            "welfare_bounds": {
                "welfare_ref": "ir.welfare_bundle.msme_survival",
                "lower_bound": 0.12,
                "upper_bound": 0.31,
            },
            "distributional_effects": [
                {
                    "effect_id": "distributional-msme-size-band",
                    "distributional_report_ref": "ir.distributional.msme_size_band",
                    "fairness_report_ref": "ir.fairness.msme_credit_access",
                    "mobility_report_ref": "ir.mobility.msme_survival",
                }
            ],
            "qualitative_effects": [
                {
                    "effect_id": "qualitative-bank-burden",
                    "description": "Participating banks face higher verification burden.",
                    "evidence_ref": sha("f"),
                }
            ],
            "risk": {
                "risk_ref": "foundry.policy_risk.msme_credit",
                "implementation_risk": "medium",
                "residual_risk": "bounded",
            },
            "uncertainty": {
                "uncertainty_ref": "foundry.uncertainty.msme_credit",
                "interval_ref": "ir.uncertainty.msme_survival",
                "source": "foundry.uncertainty",
            },
            "source_refs": {
                "foundry_welfare_ref": "ir.welfare_bundle.msme_survival",
                "foundry_uncertainty_ref": "foundry.uncertainty.msme_credit",
                "ir_distributional_ref": "ir.distributional.msme_size_band",
                "ir_fairness_ref": "ir.fairness.msme_credit_access",
                "ir_mobility_ref": "ir.mobility.msme_survival",
            },
        },
    }
    case.update(overrides)
    return case


def _case_maturity_profile() -> dict[str, Any]:
    return build_case_maturity_profile(
        record_id="case-maturity-rec-1",
        case_id="pdc-R_hds_red_control",
        run_id="R_hds_red_control",
        job_id="job-hds-red-control",
        tenant_id="tenant-prod",
        family_maturities={
            family_id: {
                "maturity": "evidence_complete",
                "record_refs": [sha("1")],
                "argument_refs": [sha("2")],
                "evidence_refs": [sha("3")],
            }
            for family_id in POLICY_DESIGN_CASE_MINIMUM_RECORD_FAMILIES
        },
        evidence_ref=sha("1"),
        runtime_event_ref="event://policy-design-case/case-maturity/1",
    )


def _record_family_coverage_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for family_id in POLICY_DESIGN_CASE_MINIMUM_RECORD_FAMILIES:
        slug = family_id.removesuffix(".v1")
        row: dict[str, Any] = {
            "family_id": family_id,
            "status": "present",
            "schema_owner": "team-runtime-quality",
            "producer_owner": "team-runtime-quality",
            "reader_owner": "team-quality-closeout",
            "schema_name": f"policyos.policy_design_case.{family_id}",
            "scorecard_gate": f"policy_design_case.{slug}.present_or_blocked",
            "readiness_gate": "policy_design_case.record_family_coverage",
            "readiness_check": "policy_design_case.record_family_coverage",
            "authority_envelope": {
                "authority_role": "reader_authority",
                "provenance_kind": "runtime_derived",
                "cas_ref": sha("1"),
                "runtime_event_ref": "event://policy-design-case/record-family-coverage",
            },
        }
        governance_surfaces = _governance_surfaces_for_family(family_id)
        if governance_surfaces:
            row["governance_surfaces"] = governance_surfaces
        rows.append(row)
    return rows


def _runtime_record_family_records() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, family_id in enumerate(POLICY_DESIGN_CASE_MINIMUM_RECORD_FAMILIES, start=1):
        slug = family_id.removesuffix(".v1").replace("_", "-")
        event_ref = f"event://policy-design-case/records/{slug}/1"
        rows.append(
            {
                "record_id": f"pdc-{slug}-record-1",
                "family_id": family_id,
                "record_family": family_id,
                "schema_name": f"policyos.policy_design_case.{family_id}",
                "schema_version": f"policyos.policy_design_case.{family_id}",
                "producer_owner": "team-runtime-quality",
                "reader_owner": "team-quality-closeout",
                "readiness_gate": "policy_design_case.record_family_coverage",
                "readiness_check": "policy_design_case.record_family_coverage",
                "evidence_ref": sha(hex(index % 16)[2:]),
                "cas_ref": sha(hex(index % 16)[2:]),
                "runtime_event_ref": event_ref,
                "authority_envelope": {
                    "authority_role": "producer_authority",
                    "provenance_kind": "runtime_emitted",
                    "cas_ref": sha(hex(index % 16)[2:]),
                    "runtime_event_ref": event_ref,
                },
            }
        )
    return rows


def _governance_surfaces_for_family(family_id: str) -> list[str]:
    return [
        surface
        for surface, required_family in (
            POLICY_DESIGN_CASE_GOVERNANCE_RECORD_FAMILY_REQUIREMENTS.items()
        )
        if required_family == family_id
    ]


def _phase28_2_records() -> dict[str, Any]:
    return {
        "substrate_residual_verification": {
            "schema_version": (
                "policyos.runtime.policy_design_case.substrate_residual_verification.v1"
            ),
            "record_family": "substrate_residual_verification.v1",
            "record_id": "substrate-residual-verification-rec-1",
            "case_id": "pdc-R_hds_red_control",
            "run_id": "R_hds_red_control",
            "job_id": "job-hds-red-control",
            "tenant_id": "tenant-prod",
            "status": "pass",
            "pdd_bindings": [
                _substrate_residual_binding(
                    "PDD-019",
                    "capability_mode_and_fallback_selection.v1",
                    ["mode_ledger", "fallback_degradation_ledger"],
                ),
                _substrate_residual_binding(
                    "PDD-031",
                    "publication_trust_and_external_governance.v1",
                    ["deterministic_replay_manifest", "typed_replay_drift"],
                ),
                _substrate_residual_binding(
                    "PDD-032",
                    "implementation_monitoring_and_evaluation.v1",
                    ["resilience_matrix", "observed_vs_modeled_resilience"],
                ),
                _substrate_residual_binding(
                    "PDD-039",
                    "publication_trust_and_external_governance.v1",
                    ["trusted_authority_fields", "authority_spoofing_controls"],
                ),
                _substrate_residual_binding(
                    "PDD-040",
                    "integrity_self_fmea_and_maturity.v1",
                    ["partial_state_consistency", "retry_reconciliation"],
                ),
                _substrate_residual_binding(
                    "PDD-041",
                    "publication_trust_and_external_governance.v1",
                    ["shared_cas_evidence_graph", "tenant_scoped_cas_ownership"],
                ),
                _substrate_residual_binding(
                    "PDD-067",
                    "publication_trust_and_external_governance.v1",
                    ["public_export", "public_export_semantic_preservation"],
                ),
                _substrate_residual_binding(
                    "PDD-071",
                    "capability_mode_and_fallback_selection.v1",
                    ["effective_configuration_ledger", "environment_provenance"],
                ),
                _substrate_residual_binding(
                    "PDD-084",
                    "publication_trust_and_external_governance.v1",
                    ["tool_transcript_authority", "compaction_audit"],
                ),
                _substrate_residual_binding(
                    "PDD-086",
                    "method_selection_and_validity.v1",
                    ["simulation_boundary_ledger", "evidence_mode_ledger"],
                    owner="team-science-quality",
                ),
            ],
            "evidence_ref": sha("2"),
            "runtime_event_ref": "event://policy-design-case/substrate-residual/1",
        }
    }


def _substrate_residual_binding(
    diagnostic_id: str,
    record_family_id: str,
    facets: list[str],
    *,
    owner: str = "team-runtime-quality",
) -> dict[str, Any]:
    return {
        "diagnostic_id": diagnostic_id,
        "record_family_id": record_family_id,
        "record_facets": facets,
        "record_refs": [sha(diagnostic_id[-1].lower())],
        "evidence_ref": sha(diagnostic_id[-1].lower()),
        "runtime_event_ref": f"event://policy-design-case/substrate-residual/{diagnostic_id}",
        "owner": owner,
        "status": "pass",
    }


def _phase28_3_records() -> dict[str, Any]:
    return {
        "dormant_capability_inventory": {
            "schema_version": (
                "policyos.runtime.policy_design_case.dormant_capability_inventory.v1"
            ),
            "record_id": "dormant-capability-inventory-rec-1",
            "record_family": "capability_mode_and_fallback_selection.v1",
            "status": "pass",
            "capabilities": [
                {
                    "capability": "lex_legal_kg",
                    "available": True,
                    "invoked": True,
                    "input_contract": "normative_applicability_request.v1",
                    "output_artifact": "normative_applicability_report",
                    "consumer": "policy_design_case.legal_authority_and_competence",
                    "current_break_point": "none",
                },
                {
                    "capability": "fabric_dataset_catalog_graph",
                    "available": True,
                    "invoked": True,
                    "input_contract": "data_need_contract.v1",
                    "output_artifact": "fabric_source_selection_audit",
                    "consumer": "policy_design_case.data_source_semantic_lineage",
                    "current_break_point": "none",
                },
                {
                    "capability": "foundry_method_catalog_expectations",
                    "available": True,
                    "invoked": True,
                    "input_contract": "method_selection_request.v1",
                    "output_artifact": "foundry_method_report",
                    "consumer": "policy_design_case.method_selection_and_validity",
                    "current_break_point": "none",
                },
                {
                    "capability": "scientist_workflow_nodes",
                    "available": True,
                    "invoked": True,
                    "input_contract": "scientist_workflow_plan.v1",
                    "output_artifact": "scientist_node_events",
                    "consumer": "policy_design_case.claim_argument_evidence_case",
                    "current_break_point": "none",
                },
            ],
            "evidence_ref": sha("1"),
            "runtime_event_ref": ("event://policy-design-case/pdd-017/dormant-capabilities"),
            "next_diagnostic_command": (
                "uv run pytest tests/unit/runtime/quality/"
                "test_policy_design_case_observability_static_audit.py -q"
            ),
        },
        "skip_causality_ledger": {
            "schema_version": ("policyos.runtime.policy_design_case.skip_causality_ledger.v1"),
            "record_id": "skip-causality-ledger-rec-1",
            "record_family": "capability_mode_and_fallback_selection.v1",
            "status": "pass",
            "projection_preserves_reason_fields": True,
            "skipped_nodes": [
                {
                    "node_id": "scientist.legal_conflict_deep_dive",
                    "reason_code": "prerequisite_not_applicable",
                    "missing_input": "legal_conflict_candidate",
                    "prerequisite_status": "no_conflict_detected",
                    "downstream_impact": (
                        "deep-dive node skipped; final claim keeps no-conflict ref"
                    ),
                    "profile_policy": ("production skips require reason and blocker visibility"),
                    "raw_node_outcome_ref": sha("2"),
                    "progress_event_ref": "event://runtime/progress/scientist/skip/1",
                    "node_event_ref": ("event://scientist/node/legal_conflict_deep_dive/skip"),
                }
            ],
            "evidence_ref": sha("2"),
            "runtime_event_ref": "event://policy-design-case/pdd-018/skip-causality",
            "next_diagnostic_command": (
                "uv run pytest tests/unit/runtime/quality/"
                "test_policy_design_case_observability_static_audit.py -q"
            ),
        },
        "freshness_policy_time_semantics": {
            "schema_version": (
                "policyos.runtime.policy_design_case.freshness_policy_time_semantics.v1"
            ),
            "record_id": "freshness-policy-time-rec-1",
            "record_family": "numeric_time_and_geography_semantics.v1",
            "status": "pass",
            "policy_time": "2026-05-15",
            "evidence_time_bindings": [
                _freshness_binding("legal", "2026-05-14", 30, sha("3")),
                _freshness_binding("data", "2026-05-15", 90, sha("4")),
                _freshness_binding("benchmark", "2026-05-10", 180, sha("5")),
                _freshness_binding("decision", "2026-05-17", 30, sha("6")),
            ],
            "continuous_governance_triggers": [
                {
                    "trigger_id": "reissue-when-source-stale",
                    "trigger": "source_freshness_expired",
                    "action": "reissue_or_withdraw",
                }
            ],
            "final_artifact_date_assumptions": [
                {
                    "artifact": "public_policy_brief",
                    "assumption": "Evidence remains current at publication time.",
                    "evidence_ref": sha("7"),
                }
            ],
            "evidence_ref": sha("3"),
            "runtime_event_ref": ("event://policy-design-case/pdd-045/freshness-policy-time"),
            "next_diagnostic_command": (
                "uv run pytest tests/unit/runtime/quality/"
                "test_policy_design_case_observability_static_audit.py -q"
            ),
        },
    }


def _freshness_binding(
    evidence_kind: str,
    evidence_as_of: str,
    acceptable_recency_window_days: int,
    evidence_ref: str,
) -> dict[str, Any]:
    return {
        "evidence_kind": evidence_kind,
        "policy_time": "2026-05-15",
        "evidence_as_of": evidence_as_of,
        "freshness_status": "pass",
        "acceptable_recency_window_days": acceptable_recency_window_days,
        "evidence_ref": evidence_ref,
    }
