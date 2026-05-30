from __future__ import annotations

# ruff: noqa: S101
from polisyos.legal_requirement import LegalAuthorityRequirementSpec
from polisyos.lex.normpack.legal_authority import build_legal_authority_report


def _claim(**overrides: object) -> dict[str, object]:
    claim: dict[str, object] = {
        "claim_id": "rec_local_credit",
        "claim_ref": "claim:rec_local_credit",
        "major": True,
        "text": "Authorize a local wartime credit guarantee for eligible MSMEs.",
        "legal_authority_required": True,
        "jurisdiction": "UA-30-KYIV",
        "required_authority_types": ["implementing"],
        "policy_instrument": "credit_guarantee",
        "competent_actor_ref": "kyiv_city_council",
        "implementation_authority_required": True,
        "implementation_authority_ref": "kyiv_city_program_office",
        "implementation_period": {"start": "2026-01-01", "end": "2026-12-31"},
    }
    claim.update(overrides)
    return claim


def _requirement(**overrides: object) -> LegalAuthorityRequirementSpec:
    payload: dict[str, object] = {
        "requirement_id": "legal-requirement:run-w7b:rec_local_credit",
        "claim_ref": "claim:rec_local_credit",
        "claim_id": "rec_local_credit",
        "mandatory": True,
        "required_hierarchy_depth": 2,
        "temporal_competence_window": {
            "start": "2026-01-01",
            "end": "2026-12-31",
            "time_role": "implementation_period",
        },
        "authority_types": ["implementing"],
        "required_instrument_classes": ["credit_guarantee"],
        "required_actor_refs": ["kyiv_city_council"],
        "implementation_authority_required": True,
        "fiscal_authority_required": False,
        "scope_predicates": {
            "population": ["eligible_msmes"],
            "geography": ["UA-30-KYIV"],
            "time": ["2026"],
        },
        "fallback_policy": {
            "mode": "governed_config_required",
            "config_ref": "jurisdiction-fallback:ua-local-v1",
        },
        "jurisdiction": "UA-30-KYIV",
        "authority_profile_ref": "production",
        "rule_version_ref": "legal-requirement-compiler:v1",
    }
    payload.update(overrides)
    return LegalAuthorityRequirementSpec.model_validate(payload)


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
        "hierarchy_depth": 2,
        "authority_basis": "statutory_delegation",
        "authority_types": ["implementing"],
        "competent_actor_ref": "kyiv_city_council",
        "instrument_types": ["credit_guarantee"],
        "implementation_authority_ref": "kyiv_city_program_office",
        "hierarchy_position": "local",
        "legal_as_of": "2026-05-23",
        "legal_effective_window": {"start": "2025-01-01", "end": None},
        "rule_version_ref": "lex-legal-authority:v2",
        "provenance_kind": "deterministic_producer",
    }
    norm.update(overrides)
    return norm


def _report(
    *,
    requirement: LegalAuthorityRequirementSpec,
    norms: list[dict[str, object]],
    claim: dict[str, object] | None = None,
    fallback_config: dict[str, object] | None = None,
) -> dict[str, object]:
    return build_legal_authority_report(
        target_context={
            "jurisdiction": "UA-30-KYIV",
            "policy_domain": "wartime_msme_support",
            "as_of": "2026-05-23",
            "authority_profile": "production",
        },
        candidate_norms=norms,
        recommendation_claims=[claim or _claim()],
        legal_requirement_specs=[requirement],
        jurisdiction_fallback_config=fallback_config,
    )


def test_generic_ukrainian_topic_match_is_context_only_against_requirement_spec() -> None:
    report = _report(
        requirement=_requirement(),
        norms=[
            _norm(
                norm_id="norm.ua.generic_credit_context",
                jurisdiction="UA",
                source_authority="Verkhovna Rada",
                authority_level="national",
                hierarchy_depth=1,
                authority_types=[],
                competent_actor_ref="",
                instrument_types=[],
                implementation_authority_ref="",
                relevance_rationale="Broad Ukrainian credit-program context.",
            )
        ],
    )

    anchor = report["claim_legal_anchors"][0]  # type: ignore[index]
    record = report["legal_authority_records"][0]  # type: ignore[index]

    assert report["status"] == "fail"
    assert report["legal_requirement_specs"][0]["requirement_id"] == (  # type: ignore[index]
        "legal-requirement:run-w7b:rec_local_credit"
    )
    assert anchor["legal_admissibility_grade"] == "context_only"
    assert anchor["admissibility_grade"] == "blocked_no_authority"
    assert anchor["selected_norm_refs"] == []
    assert anchor["context_only_norm_refs"] == ["norm.ua.generic_credit_context"]
    assert anchor["no_anchor_refs"]
    assert record["legal_admissibility_grade"] == "context_only"
    assert record["admissibility_grade"] == "context_only"
    assert "legal_authority_missing_claim_level_facets" in report["issue_codes"]


def test_governed_jurisdiction_fallback_emits_proxy_with_limitation() -> None:
    report = _report(
        requirement=_requirement(),
        norms=[
            _norm(
                jurisdiction="UA",
                source_authority="Verkhovna Rada",
                authority_level="national",
                hierarchy_depth=2,
            )
        ],
        fallback_config={
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

    anchor = report["claim_legal_anchors"][0]  # type: ignore[index]
    record = report["legal_authority_records"][0]  # type: ignore[index]

    assert report["status"] == "pass"
    assert anchor["legal_admissibility_grade"] == "proxy_with_limitation"
    assert anchor["admissibility_grade"] == "limited_authority"
    assert anchor["selected_norm_refs"] == ["norm.ua.local_credit"]
    assert record["legal_admissibility_grade"] == "proxy_with_limitation"
    assert record["admissibility_grade"] == "limited_authority"
    assert record["fallback_disposition"] == "configured"
    assert record["fallback_path"] == ["UA-30-KYIV", "UA"]
    assert record["limitation_ref"]


def test_single_norm_can_satisfy_multiple_independent_authority_types() -> None:
    requirement = _requirement(
        authority_types=["implementing", "funding"],
        fiscal_authority_required=True,
    )
    report = _report(
        requirement=requirement,
        claim=_claim(
            required_authority_types=["implementing", "funding"],
            fiscal_authority_required=True,
            fiscal_authority_ref="kyiv_city_budget",
        ),
        norms=[
            _norm(
                authority_types=["implementing", "funding", "oversight"],
                fiscal_authority_ref="kyiv_city_budget",
            )
        ],
    )

    anchor = report["claim_legal_anchors"][0]  # type: ignore[index]
    records = report["legal_authority_records"]  # type: ignore[assignment]

    assert report["status"] == "pass"
    assert anchor["legal_admissibility_grade"] == "admissible"
    assert anchor["selected_authority_types"] == ["implementing", "funding"]
    assert anchor["selected_norm_refs"] == ["norm.ua.local_credit"]
    assert [record["legal_admissibility_grade"] for record in records] == [
        "admissible",
        "admissible",
    ]


def test_competence_window_split_blocks_only_unresolved_segment() -> None:
    report = _report(
        requirement=_requirement(),
        norms=[
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
    )

    anchor = report["claim_legal_anchors"][0]  # type: ignore[index]
    segments = report["claim_window_splits"]  # type: ignore[assignment]

    assert report["status"] == "fail"
    assert anchor["legal_admissibility_grade"] == "blocked"
    assert [segment["legal_window_start"] for segment in segments] == [
        "2026-01-01",
        "2026-07-01",
    ]
    assert [segment["segment_disposition"] for segment in segments] == [
        "selected_authority",
        "blocked_no_authority",
    ]
    assert [segment["legal_segment_disposition"] for segment in segments] == [
        "admissible",
        "blocked",
    ]
    assert anchor["selected_norm_refs"] == ["norm.ua.local_credit"]
    assert anchor["blocked_segment_refs"] == [
        "legal-authority-segment:rec_local_credit:implementing:2026-07-01:2026-12-31"
    ]


def test_out_of_scope_requirement_cannot_emit_selected_authority() -> None:
    report = _report(
        requirement=_requirement(
            mandatory=False,
            out_of_scope=True,
            authority_types=[],
            fallback_policy={"mode": "not_applicable"},
        ),
        claim=_claim(
            legal_authority_required=False,
            required_authority_types=[],
            authority_types=[],
            no_legal_authority_rationale="Operational context only.",
        ),
        norms=[_norm()],
    )

    anchor = report["claim_legal_anchors"][0]  # type: ignore[index]

    assert report["status"] == "pass"
    assert anchor["legal_admissibility_grade"] == "out_of_scope"
    assert anchor["admissibility_grade"] == "context_only"
    assert anchor["selected_norm_refs"] == []
    assert anchor["candidate_norm_refs"] == ["norm.ua.local_credit"]
