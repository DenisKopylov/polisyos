from __future__ import annotations

from polisyos.ir.observation.contracts import IdentificationMode, ObservationFamily
from polisyos.ir.observation.governance import (
    DEFAULT_GOVERNANCE_PASS_ALIAS_REGISTRY,
    DEFAULT_GOVERNANCE_PASS_MAPPING_REGISTRY,
    DEFAULT_OBSERVATION_FAMILY_POLICY_REGISTRY,
    GovernancePassAliasStatus,
)


def test_every_section_9_3_family_is_present() -> None:
    registry = DEFAULT_OBSERVATION_FAMILY_POLICY_REGISTRY
    assert set(registry.policies) == {family.value for family in ObservationFamily}
    assert len(registry.policies) == 13


def test_no_policy_is_missing_primary_identification_mode() -> None:
    registry = DEFAULT_OBSERVATION_FAMILY_POLICY_REGISTRY
    assert all(policy.primary_identification_mode for policy in registry.policies.values())


def test_selection_and_survival_fallbacks_are_normalized_as_annotations() -> None:
    registry = DEFAULT_OBSERVATION_FAMILY_POLICY_REGISTRY

    firm_policy = registry.for_family(ObservationFamily.FIRM_FUNDAMENTALS)
    assert firm_policy.fallback_identification_mode == IdentificationMode.POINT_IDENTIFIED
    assert firm_policy.fallback_mode_annotation == "selection_corrected"

    distress_policy = registry.for_family(ObservationFamily.DISTRESS_ENFORCEMENT)
    assert distress_policy.fallback_identification_mode == IdentificationMode.PARTIALLY_IDENTIFIED
    assert distress_policy.fallback_mode_annotation == "survival_censored"


def test_canonical_pass_ids_resolve_through_alias_registry() -> None:
    policies = DEFAULT_OBSERVATION_FAMILY_POLICY_REGISTRY
    aliases = DEFAULT_GOVERNANCE_PASS_ALIAS_REGISTRY

    for policy in policies.policies.values():
        for pass_id in policy.mandatory_governance_passes:
            alias = aliases.resolve(pass_id)
            assert alias is not None, f"missing alias for canonical pass {pass_id}"
            if alias.status == GovernancePassAliasStatus.RUNTIME:
                assert alias.runtime_pass_id
            else:
                assert alias.status == GovernancePassAliasStatus.DEFERRED


def test_mapping_registry_materializes_section_18_10_table() -> None:
    mapping = DEFAULT_GOVERNANCE_PASS_MAPPING_REGISTRY

    assert mapping.global_mandatory_passes == ["budget", "confidence", "freshness", "checkpoint"]
    assert mapping.for_family(ObservationFamily.BUDGET_FLOWS) == [
        "sutva_check",
        "freshness",
        "equity",
        "cross_graph_evidence",
    ]
    assert mapping.for_family(ObservationFamily.HOUSEHOLD_DISTRIBUTION) == [
        "equity",
        "confidence",
        "refutation",
        "privacy",
    ]
    assert mapping.for_family(ObservationFamily.PROCUREMENT_FLOWS) == [
        "sutva_check",
        "transportability_required",
        "confidence",
        "strategic_gaming_adversarial",
    ]
