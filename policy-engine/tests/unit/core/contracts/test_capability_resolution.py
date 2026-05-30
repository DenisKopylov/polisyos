from __future__ import annotations

from typing import Any

from polisyos.core.contracts.capability_resolution import (
    RequirementToCapabilityQuery,
    construct_for_legacy_family,
    legacy_family_for_construct,
)


def test_requirement_to_capability_query_preserves_construct_alias() -> None:
    query = RequirementToCapabilityQuery(
        requirement_id="requirement:firm-survival",
        construct="construct:firm_survival",
        entity_scope="firm",
        geography="UA",
        claim_use="decision_support",
        required_evidence_modes=["derived", "derived", "observed"],
    )

    payload = query.model_dump(by_alias=True)

    assert query.construct == "firm_survival"
    assert payload["construct"] == "firm_survival"
    assert query.required_evidence_modes == ("derived", "observed")


def test_legacy_family_mapping_is_projection_only_contract() -> None:
    assert construct_for_legacy_family("production-msme-panel") == "firm_survival"
    assert legacy_family_for_construct("construct:firm_survival") == "production_msme_panel"
    assert construct_for_legacy_family("unknown_family") is None


def test_capability_resolver_port_shape_can_be_faked_without_runtime_imports() -> None:
    class _Binding:
        schema_version = "policyos.capability_binding_result.v1"
        rule_version_ref = "capability-v1"
        requirement_id = "requirement:firm-survival"
        status = "blocked_acquisition_required"
        selected_capability_ref = None
        construct_ref = "construct:firm_survival"
        capability_index_ref = None
        authority_level = "governed_pilot"
        authority_envelope_result = "blocked"
        binding_reasons: tuple[str, ...] = ()
        blocked_reasons = ("acquisition_required",)
        limitations: tuple[str, ...] = ()
        acquisition_strategies: tuple[dict[str, Any], ...] = ()
        rejected_alternatives: tuple[dict[str, Any], ...] = ()
        conflict_markers: tuple[dict[str, Any], ...] = ()

    class _Resolver:
        def resolve(self, query: RequirementToCapabilityQuery) -> _Binding:
            assert query.construct == "firm_survival"
            return _Binding()

    binding = _Resolver().resolve(
        RequirementToCapabilityQuery(
            requirement_id="requirement:firm-survival",
            construct="firm_survival",
            entity_scope="firm",
            geography="UA",
            claim_use="decision_support",
        )
    )

    assert binding.status == "blocked_acquisition_required"
