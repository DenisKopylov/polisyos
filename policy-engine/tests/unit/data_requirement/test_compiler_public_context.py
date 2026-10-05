from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

import polisyos.data_requirement.compiler as compiler_module
from polisyos.core.contracts.capability_resolution import RequirementToCapabilityQuery
from polisyos.core.contracts.runtime import UniversalAuthorityProfile
from polisyos.data_requirement import DataRequirementCompiler
from polisyos.ir.governance.policy_composition import PolicyLayerLevel
from polisyos.ir.governance.problem_frame import ProblemDomain
from polisyos.policy_grammar import (
    PolicyGrammarCompiler,
    PolicyGrammarConceptSpineRefs,
    PolicyGrammarIntent,
    facet_snapshots_for_obligation_graph,
)

_CREDIT_REQUEST = (
    "Create a concessional credit guarantee programme for displaced MSMEs in "
    "northern regions in 2026, funded by budget appropriation and delivered "
    "through partner banks to preserve employment."
)
_NATIONAL_CREDIT_REQUEST = (
    "Create a concessional credit guarantee programme for MSMEs at a national "
    "level in 2026, funded by budget appropriation and delivered through "
    "partner banks to preserve employment."
)


class _RecordingCapabilityResolver:
    def __init__(self) -> None:
        self.queries: list[RequirementToCapabilityQuery] = []

    def resolve(self, query: RequirementToCapabilityQuery) -> SimpleNamespace:
        self.queries.append(query)
        return SimpleNamespace(
            schema_version="policyos.capability_binding_result.v1",
            rule_version_ref="test-public-context-resolver",
            requirement_id=query.requirement_id,
            status="selected_derived",
            selected_capability_ref=f"capability:{query.construct}:test",
            construct_ref=f"construct:{query.construct}",
            capability_index_ref="capability-index:public-context-test",
            authority_level=query.authority_level,
            authority_envelope_result="limited",
            binding_reasons=("construct_match",),
            blocked_reasons=(),
            limitations=(),
            acquisition_strategies=(),
            rejected_alternatives=(),
            conflict_markers=(),
        )


def _real_grammar_facets(
    text: str,
) -> tuple[Any, tuple[dict[str, Any], ...]]:
    case = PolicyGrammarCompiler().compile(
        intent=PolicyGrammarIntent(
            intent_id="intent-public-context-test",
            text=text,
            domain=ProblemDomain.FISCAL,
        ),
        authority_profile=UniversalAuthorityProfile(
            profile_id="authority_profile.public_context_test",
            authority_type=PolicyLayerLevel.LOCAL,
        ),
        concept_spine_refs=PolicyGrammarConceptSpineRefs(
            concept_spine_ref="concept-spine://public-context-test",
            jurisdiction_spine_ref="jurisdiction-spine://ua",
            canonical_concept_refs=("concept://public-context-test",),
        ),
    )
    assert case.facets is not None, "fixture must traverse the real grammar path"
    return case, tuple(facet_snapshots_for_obligation_graph(case))


def _query_signature(
    resolver: _RecordingCapabilityResolver,
) -> tuple[tuple[str, str, str | None, str | None], ...]:
    return tuple(
        sorted(
            (
                query.construct,
                query.geography,
                query.time_window.start,
                query.time_window.end,
            )
            for query in resolver.queries
        )
    )


def test_public_compiler_keeps_negative_text_and_opaque_ids_out_of_requirement_authority(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("POLISYOS_DATA_REQ_FAMILY_FALLBACK_FROM_HARDCODED", raising=False)
    text = _CREDIT_REQUEST + " No housing or rent intervention is requested."
    _case, facets = _real_grammar_facets(text)
    facet_refs = [str(facet["facet_id"]) for facet in facets]
    claim = {
        "claim_id": "claim:public-context-negative",
        "claim_family": "causal",
        "claim_type": "causal",
        "claim_use": "decision_support",
        "text": text,
        "metadata": {},
        "facet_refs": facet_refs,
    }
    claim_ledger = {"claims": [claim]}
    scope_profile = compiler_module._scenario_scope_profile(
        {
            "scenario_profile": {
                "profile_id": "candidate-snapshot:public-context-test",
                "candidate_construct_proposals": ["housing_rent_burden"],
            }
        }
    )
    assert scope_profile is not None

    parent_resolver = _RecordingCapabilityResolver()
    parent_report = DataRequirementCompiler(
        capability_resolver=parent_resolver
    ).compile_for_claim_ledger(
        run_id="run-public-context-parent",
        scenario_id="parent-support",
        claim_ledger=claim_ledger,
        facet_snapshots=facets,
        obligation_graph={"blocking_frontier": []},
        scope_profile=scope_profile,
    )
    opaque_resolver = _RecordingCapabilityResolver()
    opaque_report = DataRequirementCompiler(
        capability_resolver=opaque_resolver
    ).compile_for_claim_ledger(
        run_id="run-public-context-opaque",
        scenario_id="case-alpha",
        claim_ledger=claim_ledger,
        facet_snapshots=facets,
        obligation_graph={"blocking_frontier": []},
        scope_profile=scope_profile,
    )

    assert "housing_rent_burden" in parent_report.metadata["candidate_construct_proposals"]
    assert parent_report.metadata["candidate_construct_proposals"] == (
        opaque_report.metadata["candidate_construct_proposals"]
    )
    assert parent_resolver.queries == opaque_resolver.queries == []
    assert parent_report.specs == opaque_report.specs == ()

    admitted_resolver = _RecordingCapabilityResolver()
    admitted_report = DataRequirementCompiler(
        capability_resolver=admitted_resolver
    ).compile_for_claim_ledger(
        run_id="run-public-context-explicit",
        scenario_id="parent-support",
        claim_ledger=claim_ledger,
        facet_snapshots=facets,
        obligation_graph={
            "blocking_frontier": [
                {
                    "metadata": {
                        "required_evidence_constructs": ["credit_program_enrollment"],
                    }
                }
            ]
        },
        scope_profile=scope_profile,
    )

    assert [query.construct for query in admitted_resolver.queries] == [
        "credit_program_enrollment"
    ]
    assert "housing_rent_burden" in admitted_report.metadata["candidate_construct_proposals"]
    assert {
        family for spec in admitted_report.specs for family in spec.required_data_families
    } == {"credit_program_registry"}


def test_public_scenario_adapter_uses_only_named_pilot_scope() -> None:
    named_resolver = _RecordingCapabilityResolver()
    named_report = DataRequirementCompiler(
        capability_resolver=named_resolver
    ).compile_for_scenario(
        {
            "scenario_id": "pilot-case",
            "request": _NATIONAL_CREDIT_REQUEST,
            "domain_hint": "fiscal",
            "scenario_profile": {
                "profile_id": "ua-msme-pilot:2022-v1",
                "jurisdiction": "UA",
                "time_window": {"start": "2022-02-01", "end": "2022-12-31"},
            },
        }
    )
    generic_resolver = _RecordingCapabilityResolver()
    generic_report = DataRequirementCompiler(
        capability_resolver=generic_resolver
    ).compile_for_scenario(
        {
            "scenario_id": "generic-case",
            "text": _NATIONAL_CREDIT_REQUEST,
            "domain": "fiscal",
        }
    )

    expected_constructs = {
        "credit_program_enrollment",
        "credit_access",
        "program_participation_rate",
        "firm_survival",
        "employment_count",
    }
    assert named_report.metadata.get("fallback") is None
    assert generic_report.metadata.get("fallback") is None
    assert {query.construct for query in named_resolver.queries} == expected_constructs
    assert {query.construct for query in generic_resolver.queries} == expected_constructs
    assert {
        family for spec in named_report.specs for family in spec.required_data_families
    } == {
        "credit_program_registry",
        "production_msme_panel",
    }
    assert {
        family for spec in generic_report.specs for family in spec.required_data_families
    } == {"credit_program_registry", "production_msme_panel"}
    assert {spec.scope.time for spec in generic_report.specs} == {"annual"}

    assert all(
        query.geography == "UA"
        and query.time_window.start == "2022-02-01"
        and query.time_window.end == "2022-12-31"
        for query in named_resolver.queries
    )
    assert all(
        query.geography == "national"
        and query.time_window.start is None
        and query.time_window.end is None
        for query in generic_resolver.queries
    )
    assert _query_signature(named_resolver) != _query_signature(generic_resolver)
