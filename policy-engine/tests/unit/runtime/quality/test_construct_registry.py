from __future__ import annotations

# ruff: noqa: S101
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from polisyos.obligation_rules import build_seed_obligation_rule_catalog
from polisyos.runtime.quality.concept_spine import ReconciledConcept
from polisyos.runtime.quality.construct_registry import (
    CONSTRUCT_REGISTRY_SCHEMA_VERSION,
    ConstructRegistry,
    assert_scenario_family_name_alone_does_not_grant_authority,
    construct_refs_for_alias,
    construct_registry_concept_spine_entries,
    load_construct_registry,
    non_ukraine_bound_constructs,
    validate_construct_registry_coverage,
    validate_obligation_rule_construct_refs,
)

REPO_ROOT = Path(__file__).resolve().parents[4]
UNIVERSAL_CORPUS_MANIFEST = REPO_ROOT / "tests/fixtures/universal-corpus/manifest.json"
REALITY_REPORT = REPO_ROOT / "architecture/policy_design_case/capability_reality_report.json"


def test_default_construct_registry_has_phase2_shape_and_seed_coverage() -> None:
    registry = load_construct_registry()
    constructs = {entry.construct_id: entry for entry in registry.constructs}

    assert registry.schema_version == CONSTRUCT_REGISTRY_SCHEMA_VERSION
    assert len(registry.constructs) >= 40
    assert {
        "msme_credit",
        "health_service_delivery",
        "housing_regulation",
        "fiscal_program_delivery",
        "participation",
        "climate_environment",
    } <= set(registry.summary["domains"])

    for construct in registry.constructs:
        assert construct.concept_spine_ref
        assert construct.required_time_roles
        assert construct.allowed_evidence_modes
        assert set(construct.authority_requirements) == {
            "research",
            "governed_pilot",
            "production",
        }
        assert construct.construct_validity_requirements.minimum_status_by_posture
        assert construct.proxy_validation_rules
        assert construct.corpus_bindings or construct.corpus_binding_status == "research_only"

    assert "metrics_map.yaml" in " ".join(constructs["construct:gdp_per_capita"].source_refs)
    assert "metrics_map.yaml" in " ".join(constructs["construct:inflation"].source_refs)
    assert "measurement_registry.json" in " ".join(
        constructs["construct:logistics_friction"].source_refs
    )
    assert construct_refs_for_alias(registry, "production_msme_panel") == (
        "construct:firm_survival",
        "construct:credit_access",
        "construct:employment_count",
    )


def test_universal_corpus_cases_resolve_to_three_constructs_and_gap_blocks() -> None:
    registry = load_construct_registry()
    report = validate_construct_registry_coverage(
        registry,
        corpus_manifest_path=UNIVERSAL_CORPUS_MANIFEST,
    )

    assert report["status"] == "pass", report["blockers"]
    assert report["summary"]["case_count"] == 13
    assert all(row["construct_count"] >= 3 for row in report["case_coverage"])
    assert report["blockers"] == []

    broken_payload = registry.model_dump(mode="json")
    broken_case_id = "w11a_netherlands_room_for_river_2007"
    for construct in broken_payload["constructs"]:
        construct["corpus_bindings"] = [
            binding
            for binding in construct.get("corpus_bindings", [])
            if binding.get("case_id") != broken_case_id
        ]
        if not construct["corpus_bindings"]:
            construct["corpus_binding_status"] = "research_only"
    broken = ConstructRegistry.model_validate(broken_payload)

    broken_report = validate_construct_registry_coverage(
        broken,
        corpus_manifest_path=UNIVERSAL_CORPUS_MANIFEST,
    )

    assert broken_report["status"] == "blocked"
    assert any(
        blocker["code"] == "construct_registry_coverage_gap"
        and blocker["case_id"] == broken_case_id
        for blocker in broken_report["blockers"]
    )


@pytest.mark.parametrize(
    "legacy_family",
    [
        "production_msme_panel",
        "regional_displacement_indicators",
        "credit_program_registry",
    ],
)
def test_scenario_family_name_alone_does_not_grant_authority(legacy_family: str) -> None:
    registry = load_construct_registry()

    assert construct_refs_for_alias(registry, legacy_family)
    with pytest.raises(ValueError, match="scenario_family_name_not_authority"):
        assert_scenario_family_name_alone_does_not_grant_authority(
            registry,
            legacy_family,
            posture="production",
        )


def test_construct_missing_posture_specific_authority_requirements_is_rejected() -> None:
    payload = load_construct_registry().model_dump(mode="json")
    payload["constructs"][0]["authority_requirements"].pop("production")

    with pytest.raises(ValidationError, match="authority_requirements"):
        ConstructRegistry.model_validate(payload)


def test_construct_registry_rejects_wrong_schema_version() -> None:
    payload = load_construct_registry().model_dump(mode="json")
    payload["schema_version"] = "policyos.construct_registry.v0"

    with pytest.raises(ValidationError, match="schema_version"):
        ConstructRegistry.model_validate(payload)


def test_construct_registry_rejects_ungoverned_time_roles_and_evidence_modes() -> None:
    payload = load_construct_registry().model_dump(mode="json")
    payload["constructs"][0]["required_time_roles"] = ["made_up_time_role"]
    payload["constructs"][0]["allowed_evidence_modes"] = ["llm_authority_magic"]

    with pytest.raises(ValidationError, match="governed"):
        ConstructRegistry.model_validate(payload)


def test_legacy_scenario_family_alias_requires_deprecation_metadata() -> None:
    payload = load_construct_registry().model_dump(mode="json")
    payload["constructs"][0]["compatibility_aliases"][0]["deprecation"] = None

    with pytest.raises(ValidationError, match="deprecation"):
        ConstructRegistry.model_validate(payload)


def test_concept_spine_bearing_policy_construct_requires_construct_ref() -> None:
    with pytest.raises(ValidationError, match="bearing_policy_construct"):
        ReconciledConcept.model_validate(
            {
                "concept_id": "concept:legacy_family",
                "concept_type": "metric",
                "label": "legacy family",
                "bearing_policy_construct": "production_msme_panel",
            }
        )


def test_concept_spine_entries_mark_policy_decision_bearing_constructs() -> None:
    registry = load_construct_registry()
    entries = construct_registry_concept_spine_entries(registry)

    assert len(entries) == len(registry.constructs)
    assert {
        entry["bearing_policy_construct"]
        for entry in entries
        if entry["concept_id"] == "concept:firm_survival"
    } == {"construct:firm_survival"}

    concept = ReconciledConcept.model_validate(entries[0])
    assert concept.bearing_policy_construct == entries[0]["bearing_policy_construct"]


def test_w6b_vertical_required_evidence_refs_are_construct_refs() -> None:
    registry = load_construct_registry()
    catalog = build_seed_obligation_rule_catalog()

    report = validate_obligation_rule_construct_refs(registry, catalog)

    assert report["status"] == "pass", report["blockers"]
    assert report["summary"]["checked_rule_count"] >= 1
    assert report["blockers"] == []
    for rule in catalog.rules:
        if rule.logic.get("vertical_rule"):
            assert "required_evidence_family" not in rule.logic
            if rule.logic.get("required_evidence_constructs"):
                assert all(
                    str(ref).startswith("construct:")
                    for ref in rule.logic["required_evidence_constructs"]
                )


def test_at_least_three_non_ukraine_constructs_bind_to_corpus_cases() -> None:
    bound = non_ukraine_bound_constructs(load_construct_registry())

    assert len(bound) >= 3
    assert {
        "construct:housing_rent_burden",
        "construct:regional_emissions_intensity",
        "construct:education_outcomes",
    } <= set(bound)


def test_capability_reality_report_moves_construct_registry_to_phase7_label() -> None:
    report = json.loads(REALITY_REPORT.read_text(encoding="utf-8"))
    claims = {claim["capability_id"]: claim for claim in report["capability_claims"]}

    assert claims["construct_registry"]["reality_state"] == "implemented"
    assert claims["construct_registry"]["evidence_refs"]["artifact_ref"].endswith(
        "architecture/policy_design_case/construct_registry_v1.yaml"
    )
