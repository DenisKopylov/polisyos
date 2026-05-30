from __future__ import annotations

# ruff: noqa: S101
from typing import TYPE_CHECKING

import pytest

import polisyos.obligation_rules as obligation_rules
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import from_canonical_bytes
from polisyos.obligation_rules import (
    OBLIGATION_RULE_CATALOG_SCHEMA_VERSION,
    ObligationRuleCandidate,
    ObligationRuleFamily,
    ObligationRuleGovernanceError,
    ObligationRuleSourceClass,
    PublicRevalidationEffect,
    RuleGovernanceDecision,
    build_rule_evolution_registry_for_catalog,
    build_seed_obligation_rule_catalog,
    govern_rule_candidate,
    governed_rule_catalog_public_surface,
    persist_obligation_rule_catalog,
    select_governed_rules,
)

if TYPE_CHECKING:
    from pathlib import Path


def _sha(char: str) -> str:
    return "sha256:" + char * 64


def test_facet_match_models_remain_internal_to_catalog_surface() -> None:
    assert "FacetMatchPattern" not in obligation_rules.__all__
    assert "FacetPredicate" not in obligation_rules.__all__
    assert not hasattr(obligation_rules, "FacetMatchPattern")
    assert not hasattr(obligation_rules, "FacetPredicate")


def test_seed_catalog_has_required_governed_rules_and_family_coverage() -> None:
    catalog = build_seed_obligation_rule_catalog()

    governed_rules = [rule for rule in catalog.rules if rule.status == "governed"]
    governed_families = {rule.rule_family for rule in governed_rules}

    assert catalog.schema_version == OBLIGATION_RULE_CATALOG_SCHEMA_VERSION
    assert catalog.summary.governed_rule_count >= 50
    assert {
        ObligationRuleFamily.LEGAL,
        ObligationRuleFamily.FISCAL,
        ObligationRuleFamily.EQUITY,
        ObligationRuleFamily.DATA,
        ObligationRuleFamily.IMPLEMENTATION,
        ObligationRuleFamily.METHOD,
        ObligationRuleFamily.PARTICIPATION,
    } <= governed_families
    assert catalog.capability_reality["reality_state"] == "implemented"

    for rule in governed_rules:
        assert rule.rule_version
        assert rule.logic_hash.startswith("sha256:")
        assert rule.owner
        assert rule.scope.jurisdictions
        assert rule.authority_level
        assert rule.evidence_basis
        assert rule.public_revalidation_effect is not PublicRevalidationEffect.NONE
        assert rule.source_refs


def test_catalog_exports_replay_safe_rule_evolution_registry_with_w6_metadata() -> None:
    catalog = build_seed_obligation_rule_catalog()

    registry = build_rule_evolution_registry_for_catalog(catalog)

    assert registry["status"] == "pass"
    assert registry["rule_registry_ref"] == catalog.catalog_ref
    assert registry["capability_reality"]["orchestration_bridge"] == (
        "polisyos.obligation_rules.build_rule_evolution_registry_for_catalog"
    )
    assert registry["summary"]["rule_ref_count"] == catalog.summary.governed_rule_count

    competence_rule = next(
        row
        for row in registry["rule_refs"]
        if row["requirement_id"] == "obligation.legal.competence_proof_required"
    )
    assert competence_rule["rule_family"] == "legal"
    assert competence_rule["rule_version"] == "2026.05.0"
    assert competence_rule["owner"] == "team-lex-governance"
    assert competence_rule["authority_level"] == "production"
    assert competence_rule["evidence_basis"] == [
        "deterministic_critic_output",
        "temporal_logic_pattern",
    ]
    assert competence_rule["public_revalidation_effect"] == "revalidate_public_cases"


def test_changed_governed_rule_logic_flows_through_w2b_revalidation() -> None:
    old_catalog = build_seed_obligation_rule_catalog(catalog_version="2026.05.0")
    new_catalog = build_seed_obligation_rule_catalog(
        catalog_version="2026.06.0",
        rule_logic_overrides={
            "obligation.fiscal.budget_overrun_blocker": {
                "predicate": "budget_overrun_blocks_publication",
                "max_budget_ratio": "0.98",
                "requested_authority_levels": ["production"],
            }
        },
    )

    registry = build_rule_evolution_registry_for_catalog(
        new_catalog,
        previous_catalog=old_catalog,
    )

    assert registry["status"] == "blocked"
    assert registry["revalidation_state"]["state"] == "revalidation_required"
    assert registry["revalidation_state"]["affected_requirement_ids"] == [
        "obligation.fiscal.budget_overrun_blocker"
    ]
    assert registry["public_annotation"]["public_annotation_state"] == "semantic_change"
    assert registry["public_annotation"]["silent_upgrade_allowed"] is False


def test_llm_candidate_cannot_silently_become_governed_rule() -> None:
    candidate = ObligationRuleCandidate(
        candidate_id="candidate.llm.method.generic_execute_warning",
        proposed_rule_id="obligation.method.generic_execute_warning",
        rule_family=ObligationRuleFamily.METHOD,
        source_class=ObligationRuleSourceClass.LLM_CANDIDATE,
        proposed_logic={
            "predicate": "generic_foundry_execute_requires_method_specific_validation",
            "authority_levels": ["governed", "production"],
        },
        rationale="LLM suggested that generic execution should not satisfy method validity.",
        prompt_fingerprint=_sha("a"),
        tool_refs=(_sha("b"),),
        repair_decision_lineage=(_sha("c"),),
    )

    with pytest.raises(ObligationRuleGovernanceError, match="LLM"):
        govern_rule_candidate(candidate)

    decision = RuleGovernanceDecision(
        owner="team-foundry-methods",
        authority_level="governed",
        evidence_basis=("deterministic_critic_output", "historical_failure_corpus"),
        admission_authority_ref=_sha("d"),
        validation_refs=(_sha("e"),),
        public_revalidation_effect=PublicRevalidationEffect.REVALIDATE_PUBLIC_CASES,
    )

    rule = govern_rule_candidate(candidate, decision=decision)

    assert rule.status == "governed"
    assert rule.candidate_source_class == ObligationRuleSourceClass.LLM_CANDIDATE
    assert rule.governance_decision_ref == _sha("d")
    assert "silent_rulebook_admission" in rule.may_not_use_for


def test_public_surface_and_consumer_expose_governed_rules_without_authority_leak() -> None:
    catalog = build_seed_obligation_rule_catalog()

    data_rules = select_governed_rules(
        catalog,
        families=(ObligationRuleFamily.DATA,),
        authority_levels=("production",),
    )
    all_data_rules = select_governed_rules(
        catalog,
        families=(ObligationRuleFamily.DATA,),
    )
    public_surface = governed_rule_catalog_public_surface(catalog)

    assert data_rules
    assert {rule.rule_family for rule in data_rules} == {ObligationRuleFamily.DATA}
    assert {rule.status for rule in data_rules} == {"governed"}
    assert public_surface["authoritative_for"] == ["obligation_rule_catalog_inspection"]
    assert "claim_evidence_authority" in public_surface["may_not_use_for"]
    assert public_surface["summary"]["governed_rule_count"] == catalog.summary.governed_rule_count
    assert public_surface["rules_by_family"]["data"] == len(all_data_rules)


def test_obligation_rule_catalog_persists_as_runtime_artifact(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    catalog = build_seed_obligation_rule_catalog()

    ref = persist_obligation_rule_catalog(catalog, store=store)
    stored = from_canonical_bytes(store.get_bytes(ref.artifact_id))

    assert str(ref.artifact_id).startswith("sha256:")
    assert stored["schema_version"] == OBLIGATION_RULE_CATALOG_SCHEMA_VERSION
    assert stored["catalog_id"] == catalog.catalog_id
    assert stored["capability_reality"]["artifact_ref"] == catalog.catalog_ref
