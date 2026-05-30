from __future__ import annotations

from polisyos.lex.normpack.applicability_report import build_normative_applicability_report

# ruff: noqa: S101
from polisyos.lex.normpack.legal_authority import build_legal_authority_report


def _serious_claim(**overrides: object) -> dict[str, object]:
    claim: dict[str, object] = {
        "claim_id": "rec_local_credit",
        "major": True,
        "text": "Authorize a local wartime credit guarantee for eligible MSMEs.",
        "legal_authority_required": True,
        "jurisdiction": "UA-30-KYIV",
        "required_authority_types": ["implementing"],
        "policy_instrument": "credit_guarantee",
        "competent_actor_ref": "kyiv_city_council",
        "implementation_authority_ref": "kyiv_city_program_office",
        "implementation_period": {"start": "2026-01-01", "end": "2026-12-31"},
    }
    claim.update(overrides)
    return claim


def _norm(**overrides: object) -> dict[str, object]:
    norm: dict[str, object] = {
        "norm_id": "norm.ua.local_credit",
        "norm_version_ref": "norm.ua.local_credit@2026-01-01",
        "source_provenance_ref": "lex-corpus:ua-local-credit",
        "jurisdiction": "UA-30-KYIV",
        "policy_domain": "wartime_msme_support",
        "effective_from": "2025-01-01",
        "source_authority": "Kyiv City Council",
        "authority_level": "local",
        "authority_basis": "statutory_delegation",
        "authority_types": ["implementing"],
        "competent_actor_ref": "kyiv_city_council",
        "instrument_types": ["credit_guarantee"],
        "implementation_authority_ref": "kyiv_city_program_office",
        "hierarchy_position": "local",
        "legal_as_of": "2026-05-22",
        "legal_effective_window": {"start": "2025-01-01", "end": None},
        "rule_version_ref": "lex-legal-authority:v1",
        "provenance_kind": "deterministic_producer",
    }
    norm.update(overrides)
    return norm


def test_generic_ukrainian_topic_match_stays_context_not_authority() -> None:
    report = build_normative_applicability_report(
        target_context={
            "jurisdiction": "UA-30-KYIV",
            "policy_domain": "wartime_msme_support",
            "as_of": "2026-05-22",
            "authority_profile": "production",
        },
        candidate_norms=[
            _norm(
                norm_id="norm.ua.generic_credit_context",
                jurisdiction="UA",
                source_authority="Verkhovna Rada",
                authority_level="statute",
                authority_types=[],
                competent_actor_ref="",
                instrument_types=[],
                implementation_authority_ref="",
                relevance_rationale="Broad Ukrainian credit-program context.",
            )
        ],
        recommendation_claims=[_serious_claim()],
    )

    anchor = report["claim_legal_anchors"][0]

    assert report["status"] == "fail"
    assert report["capability_reality_status"] == "implemented"
    assert (
        "claim_level_legal_admissibility"
        in report["runtime_authority_envelope"]["authoritative_for"]
    )
    assert "recommendation_substance" in report["runtime_authority_envelope"]["may_not_use_for"]
    assert anchor["admissibility_grade"] == "blocked_no_authority"
    assert anchor["selected_norm_refs"] == []
    assert anchor["rejected_norm_refs"] == ["norm.ua.generic_credit_context"]
    assert anchor["context_only_norm_refs"] == ["norm.ua.generic_credit_context"]
    assert "legal_authority_missing_claim_level_facets" in report["issue_codes"]


def test_jurisdiction_fallback_requires_governed_config() -> None:
    claim = _serious_claim(
        jurisdiction="UA-30-KYIV",
        competent_actor_ref="ministry_of_economy",
        implementation_authority_ref="ministry_program_office",
    )
    national_norm = _norm(
        jurisdiction="UA",
        authority_level="national",
        source_authority="Verkhovna Rada",
        competent_actor_ref="ministry_of_economy",
        implementation_authority_ref="ministry_program_office",
    )

    blocked = build_normative_applicability_report(
        target_context={
            "jurisdiction": "UA-30-KYIV",
            "policy_domain": "wartime_msme_support",
            "as_of": "2026-05-22",
            "authority_profile": "production",
        },
        candidate_norms=[national_norm],
        recommendation_claims=[claim],
    )

    assert blocked["claim_legal_anchors"][0]["selected_norm_refs"] == []
    assert "legal_authority_fallback_policy_missing" in blocked["issue_codes"]

    allowed = build_normative_applicability_report(
        target_context={
            "jurisdiction": "UA-30-KYIV",
            "policy_domain": "wartime_msme_support",
            "as_of": "2026-05-22",
            "authority_profile": "production",
        },
        candidate_norms=[national_norm],
        recommendation_claims=[claim],
        jurisdiction_fallback_config={
            "config_ref": "jurisdiction-fallback:ua-local-v1",
            "rules": [
                {
                    "from_jurisdiction": "UA-30-KYIV",
                    "to_jurisdiction": "UA",
                    "authority_types": ["implementing"],
                    "instrument_types": ["credit_guarantee"],
                    "policy_ref": "jurisdiction-fallback:ua-local-national-implementation",
                    "disposition": "allowed",
                }
            ],
        },
    )

    record = allowed["legal_authority_records"][0]

    assert allowed["status"] == "pass"
    assert allowed["claim_legal_anchors"][0]["selected_norm_refs"] == ["norm.ua.local_credit"]
    assert record["jurisdiction_fallback_policy_ref"] == (
        "jurisdiction-fallback:ua-local-national-implementation"
    )
    assert record["fallback_path"] == ["UA-30-KYIV", "UA"]
    assert record["fallback_disposition"] == "configured"


def test_authority_types_are_independent_for_funding_claims() -> None:
    report = build_normative_applicability_report(
        target_context={
            "jurisdiction": "UA-30-KYIV",
            "policy_domain": "wartime_msme_support",
            "as_of": "2026-05-22",
            "authority_profile": "production",
        },
        candidate_norms=[
            _norm(
                authority_types=["enabling", "oversight"],
                fiscal_authority_ref="",
            )
        ],
        recommendation_claims=[
            _serious_claim(
                required_authority_types=["enabling", "funding"],
                fiscal_authority_required=True,
                fiscal_authority_ref="kyiv_city_budget",
            )
        ],
    )

    anchor = report["claim_legal_anchors"][0]
    records_by_type = {
        record["authority_type"]: record for record in report["legal_authority_records"]
    }

    assert report["status"] == "fail"
    assert records_by_type["enabling"]["admissibility_grade"] == "selected_authority"
    assert records_by_type["funding"]["admissibility_grade"] == "blocked_no_authority"
    assert anchor["selected_authority_types"] == ["enabling"]
    assert anchor["blocked_authority_types"] == ["funding"]
    assert "legal_authority_type_not_carried_by_norm" in report["issue_codes"]


def test_competence_change_splits_only_the_affected_legal_window() -> None:
    report = build_normative_applicability_report(
        target_context={
            "jurisdiction": "UA-30-KYIV",
            "policy_domain": "wartime_msme_support",
            "as_of": "2026-05-22",
            "authority_profile": "production",
        },
        candidate_norms=[
            _norm(
                competence_windows=[
                    {
                        "start": "2026-01-01",
                        "end": "2026-06-30",
                        "competent_actor_ref": "kyiv_city_council",
                        "implementation_authority_ref": "kyiv_city_program_office",
                        "authority_types": ["implementing"],
                    },
                    {
                        "start": "2026-07-01",
                        "end": "2026-12-31",
                        "competent_actor_ref": "kyiv_recovery_agency",
                        "implementation_authority_ref": "",
                        "authority_types": ["implementing"],
                    },
                ]
            )
        ],
        recommendation_claims=[_serious_claim()],
    )

    segments = report["claim_window_splits"]

    assert report["status"] == "fail"
    assert [segment["legal_window_start"] for segment in segments] == [
        "2026-01-01",
        "2026-07-01",
    ]
    assert [segment["segment_disposition"] for segment in segments] == [
        "selected_authority",
        "blocked_no_authority",
    ]
    assert report["claim_legal_anchors"][0]["selected_norm_refs"] == ["norm.ua.local_credit"]
    assert report["claim_legal_anchors"][0]["blocked_segment_refs"] == [
        "legal-authority-segment:rec_local_credit:implementing:2026-07-01:2026-12-31"
    ]


def test_llm_legal_summary_remains_candidate_until_lex_validates_norm_ref() -> None:
    report = build_normative_applicability_report(
        target_context={
            "jurisdiction": "UA-30-KYIV",
            "policy_domain": "wartime_msme_support",
            "as_of": "2026-05-22",
            "authority_profile": "production",
        },
        candidate_norms=[
            _norm(
                norm_id="llm-summary:credit-law",
                provenance_kind="llm_candidate",
                source_provenance_ref="",
                norm_version_ref="",
            )
        ],
        recommendation_claims=[_serious_claim()],
    )

    anchor = report["claim_legal_anchors"][0]

    assert report["status"] == "fail"
    assert anchor["admissibility_grade"] == "blocked_no_authority"
    assert anchor["selected_norm_refs"] == []
    assert anchor["candidate_norm_refs"] == ["llm-summary:credit-law"]
    assert "legal_authority_llm_candidate_not_authority" in report["issue_codes"]


def test_lex_consumes_capability_graph_legal_facts_with_effective_time_filtering() -> None:
    report = build_legal_authority_report(
        target_context={
            "jurisdiction": "UA",
            "policy_domain": "wartime_msme_support",
            "as_of": "2022-04-01",
            "authority_profile": "production",
        },
        candidate_norms=[],
        recommendation_claims=[
            _serious_claim(
                jurisdiction="UA",
                competent_actor_ref="ministry_of_economy",
                implementation_authority_ref="wartime_credit_program_office",
                implementation_period={"start": "2022-03-01", "end": "2022-12-31"},
            )
        ],
        legal_requirement_specs=[
            {
                "requirement_id": "legal-requirement:ua-wartime-credit",
                "claim_ref": "rec_local_credit",
                "claim_id": "rec_local_credit",
                "mandatory": True,
                "authority_types": ["implementing"],
                "required_hierarchy_depth": 2,
                "required_instrument_classes": ["credit_guarantee"],
                "required_actor_refs": ["ministry_of_economy"],
                "required_implementation_authority_refs": [
                    "wartime_credit_program_office"
                ],
                "temporal_competence_window": {
                    "start": "2022-03-01",
                    "end": "2022-12-31",
                    "time_role": "implementation_period",
                    "legal_as_of": "2022-04-01",
                },
                "jurisdiction": "UA",
                "concept_spine_refs": ["concept:firm_survival"],
            }
        ],
        capability_bindings=[
            {
                "requirement_id": "legal-requirement:ua-wartime-credit",
                "status": "selected_exact",
                "selected_capability_ref": "capability:lex_prewar_credit_authority",
                "construct_ref": "construct:firm_survival",
                "capability_index_ref": "capability-index:phase5",
                "construct_registry_ref": "construct-registry:v1",
                "authority_composition_rule_ref": "capability-authority-v1.0",
                "modality": ["lex_norm"],
                "evidence_mode": "normative_authority",
                "metadata": {
                    "norm_ref": "norm.ua.prewar_credit",
                    "norm_version_ref": "norm.ua.prewar_credit@2021",
                    "source_provenance_ref": "lex_normative_facts:prewar",
                    "jurisdiction": "UA",
                    "authority_types": ["implementing"],
                    "competent_actor_ref": "ministry_of_economy",
                    "instrument_types": ["credit_guarantee"],
                    "implementation_authority_ref": "wartime_credit_program_office",
                    "hierarchy_position": "statute",
                    "hierarchy_depth": 2,
                    "source_authority": "Verkhovna Rada",
                    "effective_from": "2021-01-01",
                    "effective_to": "2022-02-23",
                    "legal_as_of": "2022-04-01",
                    "lex_normative_fact_refs": ["lex_normative_facts:prewar"],
                    "lex_rule_threshold_refs": ["lex_rule_thresholds:prewar"],
                    "lex_temporal_audit_refs": ["lex_temporal_audit:prewar"],
                },
            },
            {
                "requirement_id": "legal-requirement:ua-wartime-credit",
                "status": "selected_exact",
                "selected_capability_ref": "capability:lex_wartime_credit_authority",
                "construct_ref": "construct:firm_survival",
                "capability_index_ref": "capability-index:phase5",
                "construct_registry_ref": "construct-registry:v1",
                "authority_composition_rule_ref": "capability-authority-v1.0",
                "modality": ["lex_norm"],
                "evidence_mode": "normative_authority",
                "metadata": {
                    "norm_ref": "norm.ua.wartime_credit",
                    "norm_version_ref": "norm.ua.wartime_credit@2022-03-01",
                    "source_provenance_ref": "lex_normative_facts:wartime",
                    "jurisdiction": "UA",
                    "authority_types": ["implementing"],
                    "competent_actor_ref": "ministry_of_economy",
                    "instrument_types": ["credit_guarantee"],
                    "implementation_authority_ref": "wartime_credit_program_office",
                    "hierarchy_position": "statute",
                    "hierarchy_depth": 2,
                    "source_authority": "Cabinet of Ministers wartime resolution",
                    "effective_from": "2022-02-24",
                    "effective_to": None,
                    "legal_as_of": "2022-04-01",
                    "lex_normative_fact_refs": ["lex_normative_facts:wartime"],
                    "lex_rule_threshold_refs": ["lex_rule_thresholds:msme_employee_count"],
                    "lex_amendment_refs": ["lex_amendments:wartime_credit_2022"],
                    "lex_temporal_audit_refs": ["lex_temporal_audit:wartime"],
                    "legal_hierarchy_constraints": ["wartime_resolution_overrides_prewar"],
                },
            },
        ],
    )

    anchor = report["claim_legal_anchors"][0]
    record = report["legal_authority_records"][0]

    assert report["status"] == "pass"
    assert anchor["selected_norm_refs"] == ["norm.ua.wartime_credit"]
    assert anchor["rejected_norm_refs"] == ["norm.ua.prewar_credit"]
    assert record["capability_ref"] == "capability:lex_wartime_credit_authority"
    assert record["construct_ref"] == "construct:firm_survival"
    assert record["capability_index_ref"] == "capability-index:phase5"
    assert record["lex_normative_fact_refs"] == ["lex_normative_facts:wartime"]
    assert record["lex_rule_threshold_refs"] == ["lex_rule_thresholds:msme_employee_count"]
    assert record["lex_amendment_refs"] == ["lex_amendments:wartime_credit_2022"]
    assert record["lex_temporal_audit_refs"] == ["lex_temporal_audit:wartime"]
    assert record["legal_hierarchy_constraints"] == [
        "wartime_resolution_overrides_prewar"
    ]
