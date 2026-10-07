"""Exercise declared compiler profile scope without claiming source admission."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

import polisyos.data_requirement.compiler as compiler_module
from polisyos.core.contracts.capability_resolution import RequirementToCapabilityQuery
from polisyos.data_requirement import DataRequirementCompiler

_REQUEST = (
    "Create a concessional credit guarantee programme for displaced MSMEs in "
    "northern regions in 2026, funded by budget appropriation and delivered "
    "through partner banks to preserve employment."
)


class _RecordingCapabilityResolver:
    def __init__(self) -> None:
        self.queries: list[RequirementToCapabilityQuery] = []

    def resolve(self, query: RequirementToCapabilityQuery) -> SimpleNamespace:
        normalized = RequirementToCapabilityQuery.model_validate(query)
        self.queries.append(normalized)
        return SimpleNamespace(
            schema_version="policyos.capability_binding_result.v1",
            rule_version_ref="fixture-capability-resolver",
            requirement_id=normalized.requirement_id,
            status="selected_derived",
            selected_capability_ref=f"capability:{normalized.construct}:fixture",
            construct_ref=f"construct:{normalized.construct}",
            capability_index_ref="capability-index:fixture",
            authority_level=normalized.authority_level,
            authority_envelope_result="limited",
            binding_reasons=("fixture_resolver_selected",),
            blocked_reasons=(),
            limitations=(),
            acquisition_strategies=(),
            rejected_alternatives=(),
            conflict_markers=(),
        )


def _scenario(*, scenario_id: str, profile: dict[str, Any] | None = None) -> dict[str, Any]:
    scenario: dict[str, Any] = {
        "scenario_id": scenario_id,
        "request": _REQUEST,
        "domain_hint": "Fiscal support",
        "context": {
            "country": "Ukraine",
            "policy_domain": "wartime_msme_support",
            "query_outcome": "msme_survival_rate",
            "query_treatment": "wartime_credit_support",
            "target_population": "msme",
        },
        "expected_evidence_contract": {
            "admissible_data_source_families": ["datasets"],
        },
    }
    if profile is not None:
        scenario["scenario_profile"] = profile
    return scenario


@pytest.mark.parametrize(
    ("profile", "jurisdiction", "start", "end"),
    [
        (
            {
                "profile_id": "fixture-scope-alpha-v1",
                "jurisdiction": "fixture-jurisdiction-alpha",
                "time_window": {"start": "2026-01-01", "end": "2026-12-31"},
            },
            "fixture-jurisdiction-alpha",
            "2026-01-01",
            "2026-12-31",
        ),
        (
            {
                "profile_id": "fixture-scope-beta-v1",
                "scope": {"jurisdiction": "fixture-jurisdiction-beta"},
                "temporal_interval": {"from": "2024-07-01", "to": "2025-06-30"},
            },
            "fixture-jurisdiction-beta",
            "2024-07-01",
            "2025-06-30",
        ),
    ],
)
def test_compile_for_scenario_forwards_explicit_profile_context_to_real_queries(
    profile: dict[str, Any],
    jurisdiction: str,
    start: str,
    end: str,
) -> None:
    scenario = _scenario(scenario_id="opaque-case", profile=profile)
    typed_profile = compiler_module._scenario_scope_profile(scenario)
    resolver = _RecordingCapabilityResolver()

    report = DataRequirementCompiler(capability_resolver=resolver).compile_for_scenario(
        scenario
    )

    assert isinstance(typed_profile, compiler_module._ScenarioScopeProfile)
    assert typed_profile.profile_id == profile["profile_id"]
    assert typed_profile.jurisdiction == jurisdiction
    assert typed_profile.time_start == start
    assert typed_profile.time_end == end
    assert report.specs
    assert resolver.queries
    assert all(query.geography == jurisdiction for query in resolver.queries)
    assert all(
        query.time_window.start == start and query.time_window.end == end
        for query in resolver.queries
    )
    assert all(spec.scope.jurisdiction == jurisdiction for spec in report.specs)
    assert all(
        spec.metadata["scope_profile"]
        == {
            "profile_id": profile["profile_id"],
            "jurisdiction": jurisdiction,
            "time_window": {"start": start, "end": end},
        }
        for spec in report.specs
    )


def test_generic_geography_and_year_words_do_not_create_profile_context() -> None:
    scenario = _scenario(scenario_id="opaque-case")
    resolver = _RecordingCapabilityResolver()

    report = DataRequirementCompiler(capability_resolver=resolver).compile_for_scenario(
        scenario
    )

    assert report.specs
    assert resolver.queries
    assert compiler_module._scenario_scope_profile(scenario) is None
    assert all(spec.scope.jurisdiction is None for spec in report.specs)
    assert all("scope_profile" not in spec.metadata for spec in report.specs)
    assert all(
        query.time_window.start is None and query.time_window.end is None
        for query in resolver.queries
    )


def test_opaque_scenario_id_and_negated_topic_do_not_create_required_constructs() -> None:
    claim = SimpleNamespace(
        text="No housing or rent intervention is requested.",
        metadata={},
    )

    inputs = compiler_module._construct_resolution_inputs(
        facets=(),
        claims=(claim,),
        obligation_graph={"blocking_frontier": []},
        scenario_id="parent-support",
    )

    assert inputs.required_constructs == ()
