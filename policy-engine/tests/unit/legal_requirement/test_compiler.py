from __future__ import annotations

# ruff: noqa: S101
import json

from polisyos.legal_requirement import (
    LegalAuthorityRequirementCompiler,
    LegalAuthorityRequirementSpec,
    LegalAuthorityType,
    compile_legal_authority_requirement_artifact,
    compile_legal_authority_requirements,
    legal_authority_requirement_audit_surface,
    write_legal_authority_requirement_artifact,
)


def _claim(**overrides: object) -> dict[str, object]:
    claim: dict[str, object] = {
        "claim_id": "rec_local_credit",
        "claim_ref": "claim:rec_local_credit",
        "major": True,
        "text": "Authorize a local wartime credit guarantee for eligible MSMEs.",
        "legal_authority_required": True,
        "jurisdiction": "UA-30-KYIV",
        "required_authority_types": ["implementing", "funding"],
        "policy_instrument": "credit_guarantee",
        "competent_actor_ref": "kyiv_city_council",
        "implementation_authority_required": True,
        "implementation_authority_ref": "kyiv_city_program_office",
        "fiscal_authority_required": True,
        "fiscal_authority_ref": "kyiv_city_budget",
        "implementation_period": {"start": "2026-01-01", "end": "2026-12-31"},
        "population_predicate": "eligible_msmes",
    }
    claim.update(overrides)
    return claim


def test_compiler_emits_claim_level_legal_authority_requirement_spec() -> None:
    specs = compile_legal_authority_requirements(
        run_id="run-w7b",
        target_context={
            "jurisdiction": "UA-30-KYIV",
            "authority_profile": "production",
            "as_of": "2026-05-23",
        },
        claims=[_claim()],
        facets=[
            {
                "facet_id": "facet:geo",
                "facet_type": "geography_predicate",
                "value": "UA-30-KYIV",
                "concept_ref": "concept://ua/kyiv",
                "scope": "kyiv:msme",
                "authority_profile": "production",
                "temporal_window": "2026",
            },
            {
                "facet_id": "facet:time",
                "facet_type": "time_predicate",
                "value": "2026",
                "concept_ref": "concept://time/2026",
                "scope": "kyiv:msme",
                "authority_profile": "production",
                "temporal_window": "2026",
            },
        ],
        obligations=[
            {
                "obligation_id": "obligation:legal-competence",
                "family": "legal",
                "description": "Prove municipal legal competence.",
                "metadata": {"required_hierarchy_depth": 2},
            }
        ],
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

    assert len(specs) == 1
    spec = specs[0]

    assert isinstance(spec, LegalAuthorityRequirementSpec)
    assert spec.requirement_id == "legal-requirement:run-w7b:rec_local_credit"
    assert spec.claim_ref == "claim:rec_local_credit"
    assert spec.required_hierarchy_depth == 2
    assert spec.temporal_competence_window.start == "2026-01-01"
    assert spec.temporal_competence_window.end == "2026-12-31"
    assert spec.authority_types == (
        LegalAuthorityType.IMPLEMENTING,
        LegalAuthorityType.FUNDING,
    )
    assert spec.required_instrument_classes == ("credit_guarantee",)
    assert spec.required_actor_refs == ("kyiv_city_council",)
    assert spec.implementation_authority_required is True
    assert spec.fiscal_authority_required is True
    assert spec.scope_predicates.geography == ("UA-30-KYIV",)
    assert spec.scope_predicates.population == ("eligible_msmes",)
    assert spec.fallback_policy.config_ref == "jurisdiction-fallback:ua-local-v1"
    assert spec.fallback_policy.mode == "governed_config_required"
    assert spec.authority_profile_ref == "production"
    assert spec.pattern_refs == ("P01", "P05", "P08", "P12")


def test_compiler_marks_non_legal_claim_out_of_scope_without_minting_authority() -> None:
    specs = LegalAuthorityRequirementCompiler().compile(
        run_id="run-w7b",
        target_context={"jurisdiction": "UA", "authority_profile": "research"},
        claims=[
            _claim(
                claim_id="context_note",
                claim_ref="claim:context_note",
                legal_authority_required=False,
                required_authority_types=[],
                authority_types=[],
                no_legal_authority_rationale="Operational context only.",
            )
        ],
    )

    assert specs[0].mandatory is False
    assert specs[0].out_of_scope is True
    assert specs[0].authority_types == ()
    assert specs[0].fallback_policy.mode == "not_applicable"


def test_legal_requirement_artifact_is_persisted_for_lex_replay(tmp_path) -> None:
    artifact = compile_legal_authority_requirement_artifact(
        run_id="run-w7b",
        target_context={
            "jurisdiction": "UA-30-KYIV",
            "authority_profile": "production",
            "as_of": "2026-05-23",
        },
        claims=[_claim()],
        jurisdiction_fallback_config={"config_ref": "jurisdiction-fallback:ua-local-v1"},
    )

    path = write_legal_authority_requirement_artifact(artifact, tmp_path)
    persisted = json.loads(path.read_text(encoding="utf-8"))
    surface = legal_authority_requirement_audit_surface(artifact)

    assert path.name == "run-w7b-legal-authority-requirements.json"
    assert persisted["schema_version"] == "policyos.legal_requirement_artifact.v1"
    assert persisted["runtime_event_ref"] == "event://legal-requirement/run-w7b"
    assert persisted["requirements"][0]["requirement_id"] == (
        "legal-requirement:run-w7b:rec_local_credit"
    )
    assert surface["surface"] == "legal_requirement.audit_surface"
    assert surface["summary"]["requirement_count"] == 1
    assert surface["authority_boundary"]["authoritative_for"] == [
        "legal_authority_requirements",
        "lex_claim_level_competence_preconditions",
    ]
