from __future__ import annotations

import json
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import ValidationError

import polisyos.data_requirement.compiler as compiler_module
from polisyos.core.contracts.capability_resolution import RequirementToCapabilityQuery
from polisyos.core.contracts.runtime import UniversalAuthorityProfile
from polisyos.data_requirement import (
    DATA_REQUIREMENT_SPEC_SCHEMA_VERSION,
    DataRequirementCompiler,
    DataRequirementScope,
    DataRequirementSpec,
    data_requirement_compilation_audit_surface,
    write_data_requirement_compilation_report,
)
from polisyos.ir.governance.policy_composition import PolicyLayerLevel
from polisyos.ir.governance.problem_frame import ProblemDomain
from polisyos.obligation_graph import ComplexityBudget, compile_obligation_graph
from polisyos.obligation_rules import build_seed_obligation_rule_catalog
from polisyos.policy_grammar import (
    PolicyGrammarCompiler,
    PolicyGrammarConceptSpineRefs,
    PolicyGrammarIntent,
    facet_snapshots_for_obligation_graph,
)
from polisyos.scientist.policy_design.claim_decomposition import compile_claim_decomposition

NOW = datetime(2026, 5, 23, 12, 0, tzinfo=UTC)


class _FakeCapabilityBinding:
    def __init__(self, *, query: RequirementToCapabilityQuery, capability_index_ref: str) -> None:
        self.schema_version = "policyos.capability_binding_result.v1"
        self.rule_version_ref = "test-capability-resolver-port"
        self.requirement_id = query.requirement_id
        self.status = (
            "blocked_acquisition_required"
            if query.construct == "credit_program_enrollment"
            else "selected_derived"
        )
        self.selected_capability_ref = (
            None if self.status.startswith("blocked_") else f"capability:{query.construct}:test"
        )
        self.construct_ref = f"construct:{query.construct}"
        self.capability_index_ref = capability_index_ref
        self.authority_level = query.authority_level
        self.authority_envelope_result = (
            "blocked" if self.status.startswith("blocked_") else "limited"
        )
        self.binding_reasons = ("construct_match",)
        self.blocked_reasons = (
            ("acquisition_required",) if self.status.startswith("blocked_") else ()
        )
        self.limitations = ()
        self.acquisition_strategies = ()
        self.rejected_alternatives = (
            {
                "capability_ref": f"capability:{query.construct}:rejected",
                "rejection_reason": "lower_ranked_test_candidate",
                "rejection_severity": "soft",
            },
        )
        self.conflict_markers = ()


class _FakeCapabilityResolver:
    def __init__(self, *, capability_index_ref: str) -> None:
        self.capability_index_ref = capability_index_ref

    def resolve(self, query: RequirementToCapabilityQuery) -> _FakeCapabilityBinding:
        return _FakeCapabilityBinding(
            query=RequirementToCapabilityQuery.model_validate(query),
            capability_index_ref=self.capability_index_ref,
        )


def _fake_resolver(
    *,
    capability_index_ref: str = "capability-index:test-port",
) -> _FakeCapabilityResolver:
    return _FakeCapabilityResolver(capability_index_ref=capability_index_ref)


class _RecordingCapabilityResolver(_FakeCapabilityResolver):
    def __init__(self, *, capability_index_ref: str = "capability-index:recording") -> None:
        super().__init__(capability_index_ref=capability_index_ref)
        self.queries: list[RequirementToCapabilityQuery] = []

    def resolve(self, query: RequirementToCapabilityQuery) -> _FakeCapabilityBinding:
        normalized = RequirementToCapabilityQuery.model_validate(query)
        self.queries.append(normalized)
        return _FakeCapabilityBinding(
            query=normalized,
            capability_index_ref=self.capability_index_ref,
        )


def test_compiler_emits_claim_bound_data_requirement_specs_from_universal_compilation() -> None:
    case, facets, graph, claim_ledger = _compiled_msme_credit_case()

    report = DataRequirementCompiler(capability_resolver=_fake_resolver()).compile_for_claim_ledger(
        run_id="run-msme-credit",
        scenario_id="ukraine_msme_wartime_credit_support",
        claim_ledger=claim_ledger,
        facet_snapshots=facets,
        obligation_graph=graph,
        authority_profile_refs=(case.authority_profile.profile_id,),
    )

    required_families = {family for spec in report.specs for family in spec.required_data_families}
    assert report.schema_version == "policyos.data_requirement_compilation.v1"
    assert report.capability_reality_label == "implemented"
    assert report.pattern_refs == ("P02", "P05", "P08", "P12", "P14")
    assert {
        "production_msme_panel",
        "credit_program_registry",
        "regional_displacement_indicators",
    } <= required_families
    resolver_bindings = [
        spec.metadata.get("capability_binding")
        for spec in report.specs
        if spec.metadata.get("capability_binding")
    ]
    assert {binding["construct_ref"] for binding in resolver_bindings} >= {
        "construct:firm_survival",
        "construct:credit_program_enrollment",
        "construct:regional_displacement_pressure",
    }
    assert all(binding["capability_index_ref"] for binding in resolver_bindings)
    assert all(
        spec.metadata.get("scenario_family_authority_status") == "sunset_projection_only"
        for spec in report.specs
    )
    assert all(
        "scenario_family_authority_lookup" in spec.metadata.get("may_not_use_for", ())
        for spec in report.specs
    )
    assert all(spec.schema_version == DATA_REQUIREMENT_SPEC_SCHEMA_VERSION for spec in report.specs)
    assert all(spec.claim_id for spec in report.specs)
    assert all(spec.scope.population == "msmes" for spec in report.specs)
    assert all(
        spec.scope.geography in {"state_or_region", "displacement_affected"}
        for spec in report.specs
    )
    assert all(spec.scope.time == "annual" for spec in report.specs)
    assert all(spec.recency_horizon == "P90D" for spec in report.specs)
    assert all(spec.lineage_strictness == "strict" for spec in report.specs)
    assert all(spec.quality_minima.min_quality_score >= 0.8 for spec in report.specs)
    assert all(spec.missingness_tolerance <= 0.05 for spec in report.specs)
    assert all(
        {
            "source_contract_ref",
            "dictionary_ref",
            "schema_ref",
            "field_refs",
            "unit_refs",
            "geography_refs",
            "time_coverage_refs",
            "freshness_ref",
            "lineage_refs",
            "transformation_refs",
            "quality_assertion_refs",
            "missingness_refs",
            "claim_bindability_refs",
        }
        <= set(spec.mandatory_facets)
        for spec in report.specs
    )
    assert all(
        {
            "source_family_matches_compiled_requirement",
            "source_contract_active",
            "observation_time_covers_claim_time",
            "lineage_preserves_required_transformations",
            "missingness_within_tolerance",
        }
        <= set(spec.admissibility_predicates)
        for spec in report.specs
    )


def test_source_family_list_is_derived_from_compiled_requirements_not_legacy_fixture() -> None:
    scenario = {
        "scenario_id": "ukraine_msme_wartime_credit_support",
        "request": (
            "Create a concessional credit guarantee programme for displaced MSMEs in "
            "northern regions in 2026, funded by budget appropriation and delivered "
            "through partner banks to preserve employment."
        ),
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
            "normative_fact_classes": ["wartime_business_support_authority"],
            "foundry_method_expectations": ["causal_effect_estimation"],
            "conflict_checks": ["eligibility_mismatch"],
            "unacceptable_recommendations": ["recommendation_without_budget_guardrail"],
        },
    }

    report = DataRequirementCompiler(capability_resolver=_fake_resolver()).compile_for_scenario(
        scenario
    )

    assert set(report.legacy_admissible_data_source_families) >= {
        "production_msme_panel",
        "credit_program_registry",
        "regional_displacement_indicators",
    }
    assert "datasets" not in report.legacy_admissible_data_source_families


def test_missing_resolver_does_not_load_runtime_fixture_when_fallback_is_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("POLISYOS_DATA_REQ_FAMILY_FALLBACK_FROM_HARDCODED", raising=False)
    case, facets, _graph, claim_ledger = _compiled_msme_credit_case()

    report = DataRequirementCompiler().compile_for_claim_ledger(
        run_id="run-msme-credit",
        scenario_id="ukraine_msme_wartime_credit_support",
        claim_ledger=claim_ledger,
        facet_snapshots=facets,
        obligation_graph={"blocking_frontier": []},
        authority_profile_refs=(case.authority_profile.profile_id,),
    )

    assert report.specs == ()
    assert report.metadata["capability_index_refs"] == ()


def test_compile_claim_ledger_uses_injected_release_backed_resolver() -> None:
    resolver = _fake_resolver(capability_index_ref="capability-index:release-duckdb-fixture")
    case, facets, graph, claim_ledger = _compiled_msme_credit_case()

    report = DataRequirementCompiler(
        capability_resolver=resolver,
        require_capability_index=True,
    ).compile_for_claim_ledger(
        run_id="run-msme-credit",
        scenario_id="ukraine_msme_wartime_credit_support",
        claim_ledger=claim_ledger,
        facet_snapshots=facets,
        obligation_graph=graph,
        authority_profile_refs=(case.authority_profile.profile_id,),
    )

    binding_refs = {
        spec.metadata.get("capability_binding", {}).get("capability_index_ref")
        for spec in report.specs
    }
    assert binding_refs == {"capability-index:release-duckdb-fixture"}
    assert report.metadata["capability_index_refs"] == ("capability-index:release-duckdb-fixture",)


def test_compile_claim_ledger_requires_injected_resolver_when_configured() -> None:
    case, facets, graph, claim_ledger = _compiled_msme_credit_case()

    with pytest.raises(FileNotFoundError, match="capability resolver"):
        DataRequirementCompiler(require_capability_index=True).compile_for_claim_ledger(
            run_id="run-msme-credit",
            scenario_id="ukraine_msme_wartime_credit_support",
            claim_ledger=claim_ledger,
            facet_snapshots=facets,
            obligation_graph=graph,
            authority_profile_refs=(case.authority_profile.profile_id,),
        )


@pytest.mark.parametrize(
    ("surface", "alias"),
    [
        ("top", "scenario_profile"),
        ("top", "pilot_profile"),
        ("top", "scope_profile"),
        ("top", "profile"),
        ("context", "scenario_profile"),
        ("context", "pilot_profile"),
        ("context", "scope_profile"),
    ],
)
def test_scenario_profile_aliases_preserve_declared_unresolved_identity(
    surface: str,
    alias: str,
) -> None:
    profile = {"profile_ref": "future:ua:2026", "jurisdiction": "UA"}
    scenario = {alias: profile} if surface == "top" else {"context": {alias: profile}}

    parsed = compiler_module._scenario_scope_profile(scenario)

    assert parsed is not None
    assert parsed.profile_id == "future:ua:2026"
    assert parsed.jurisdiction == "UA"


@pytest.mark.parametrize(
    "scenario",
    [
        {"scenario_profile": {}},
        {"scenario_profile": {"profile_id": "  "}},
        {"scenario_profile": {"profile_id": 17}},
        {"scenario_profile": "future:profile"},
        {"scenario_profile": {"profile_id": "future:a", "id": "future:b"}},
        {"scenario_profile": {"profile_id": "future:a", "time_window": []}},
        {"scenario_profile": {"profile_id": "future:a", "scope": "UA"}},
        {"context": {"scope_profile": None}},
        {
            "scenario_profile": {"profile_id": "future:a"},
            "context": {"scope_profile": {"profile_id": "future:b"}},
        },
        {
            "scenario_profile": {
                "profile_id": "future:a",
                "jurisdiction": "UA",
                "scope": {"jurisdiction": "PL"},
            }
        },
        {
            "scenario_profile": {
                "profile_id": "future:a",
                "required_constructs": ["firm_survival"],
                "declared_constructs": ["credit_program_enrollment"],
            }
        },
    ],
)
def test_malformed_or_conflicting_supplied_profile_is_typed_refused(
    scenario: dict[str, object],
) -> None:
    with pytest.raises(compiler_module.ScenarioScopeProfileInputError) as raised:
        DataRequirementCompiler(capability_resolver=_fake_resolver()).compile_for_scenario(
            {
                "scenario_id": "profile_case",
                "request": "Create a credit support programme for MSMEs.",
                "domain_hint": "Fiscal support",
                **scenario,
            }
        )

    assert raised.value.code == "scenario_scope_profile_invalid"
    assert raised.value.reason_code
    assert raised.value.field_path


def test_named_unresolved_profile_binds_requirements_without_promoting_proposals() -> None:
    resolver = _RecordingCapabilityResolver()
    scenario = {
        "scenario_id": "ukraine_msme_wartime_credit_support",
        "request": (
            "Create a concessional credit guarantee programme for displaced MSMEs in "
            "northern regions in 2026, funded by budget appropriation and delivered "
            "through partner banks to preserve employment."
        ),
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
        "scenario_profile": {
            "profile_id": "future:ua:2026",
            "jurisdiction": "UA",
            "time_window": {"start": "2026-01-01", "end": "2026-12-31"},
            "required_constructs": [
                "firm_survival",
                "credit_program_enrollment",
                "scope_only_unique_probe",
            ],
            "candidate_construct_proposals": ["candidate_only_future_construct"],
        },
    }

    report = DataRequirementCompiler(capability_resolver=resolver).compile_for_scenario(scenario)

    assert report.specs
    queried_constructs = {query.construct for query in resolver.queries}
    assert {
        "firm_survival",
        "credit_program_enrollment",
        "scope_only_unique_probe",
    } <= queried_constructs
    assert "candidate_only_future_construct" not in queried_constructs
    admitted_profile = compiler_module._scenario_scope_profile(scenario)
    assert admitted_profile is not None
    resolution_inputs = compiler_module._construct_resolution_inputs(
        facets=(),
        claims=(),
        obligation_graph=None,
        scenario_id=scenario["scenario_id"],
        declared_constructs=admitted_profile.required_constructs,
        candidate_construct_proposals=admitted_profile.candidate_construct_proposals,
    )
    assert resolution_inputs.required_constructs == (
        "firm_survival",
        "credit_program_enrollment",
        "scope_only_unique_probe",
    )
    assert resolution_inputs.candidate_construct_proposals == ("candidate_only_future_construct",)
    assert all(query.geography == "UA" for query in resolver.queries)
    assert all(query.time_window.start == "2026-01-01" for query in resolver.queries)
    assert all(query.time_window.end == "2026-12-31" for query in resolver.queries)
    assert all(spec.scope.jurisdiction == "UA" for spec in report.specs)
    assert all(
        spec.metadata["scope_profile"]["profile_id"] == "future:ua:2026" for spec in report.specs
    )
    assert all(
        spec.metadata["scope_profile"]["required_constructs"]
        == ["firm_survival", "credit_program_enrollment", "scope_only_unique_probe"]
        for spec in report.specs
    )
    assert all(
        spec.metadata["scope_profile"]["candidate_construct_proposals"]
        == ["candidate_only_future_construct"]
        for spec in report.specs
    )
    assert "candidate_only_future_construct" in report.metadata["candidate_construct_proposals"]
    assert report.capability_resolution_schema_version == (
        "policyos.data_requirement.capability_requirement_resolution.v1"
    )
    resolutions = report.capability_requirement_resolutions
    assert resolutions is not None
    by_construct = {row.query.construct: row for row in resolutions}
    assert set(by_construct) == queried_constructs
    unique = by_construct["scope_only_unique_probe"]
    assert unique.scope_profile_id == "future:ua:2026"
    assert unique.state == "binding_returned"
    assert unique.binding is not None
    assert unique.binding.requirement_id == unique.query.requirement_id
    assert unique.binding.construct_ref == "construct:scope_only_unique_probe"
    assert unique.binding.status == "selected_derived"
    assert unique.binding.capability_index_ref == "capability-index:recording"
    tampered = unique.model_dump(mode="json")
    tampered["binding"]["requirement_id"] = "data-requirement:other:construct"
    from polisyos.data_requirement import CapabilityRequirementResolution

    with pytest.raises(ValidationError, match="capability_resolution_requirement_id_mismatch"):
        CapabilityRequirementResolution.model_validate(tampered)
    assert "candidate_only_future_construct" not in by_construct
    assert tuple(row.query for row in resolutions) == tuple(resolver.queries)
    from polisyos.runtime.quality.acquisition_planner import requirement_gaps_from_compiled_specs

    routed_gaps = requirement_gaps_from_compiled_specs(
        data_requirement_specs=report.specs,
        capability_requirement_resolutions=resolutions,
    )
    for resolution in resolutions:
        if resolution.query.source_family_alias:
            assert any(
                resolution in (gap.capability_requirement_resolutions or ())
                for gap in routed_gaps
                if resolution.query.source_family_alias in gap.scenario_requirement_refs
            )
    round_trip = type(report).model_validate(report.model_dump(mode="json"))
    assert round_trip.capability_requirement_resolutions == resolutions
    assert (
        data_requirement_compilation_audit_surface(report)["capability_requirement_resolutions"]
        == report.model_dump(mode="json")["capability_requirement_resolutions"]
    )
    blocked = by_construct["credit_program_enrollment"]
    assert blocked.binding is not None
    assert blocked.binding.status == "blocked_acquisition_required"
    assert blocked.binding.blocked_reasons == ("acquisition_required",)
    assert any(
        blocked in (gap.capability_requirement_resolutions or ())
        for gap in routed_gaps
        if "credit_program_registry" in gap.scenario_requirement_refs
    )


def test_construct_resolution_inputs_merge_required_sources_without_promoting_proposals() -> None:
    profile_required = ("profile_required", "shared_required")
    resolution_inputs = compiler_module._construct_resolution_inputs(
        facets=({"required_constructs": ["facet_required", "graph_required"]},),
        claims=(
            {
                "claim_id": "claim:requirements",
                "required_constructs": ["claim_required", "profile_required"],
            },
        ),
        obligation_graph={
            "blocking_frontier": [
                {
                    "metadata": {
                        "required_evidence_constructs": ["graph_required", "shared_required"]
                    }
                }
            ]
        },
        scenario_id="merged-requirements",
        declared_constructs=profile_required,
        candidate_construct_proposals=("proposal_only",),
    )

    assert resolution_inputs.required_constructs == (
        "graph_required",
        "shared_required",
        "profile_required",
        "facet_required",
        "claim_required",
    )
    assert resolution_inputs.candidate_construct_proposals == ("proposal_only",)


def test_opaque_scenario_id_is_not_semantic_input() -> None:
    claim = SimpleNamespace(text="", metadata={})

    constructs = compiler_module._required_constructs_from_semantics(
        facets=(),
        claims=(claim,),
        scenario_id="parent-support",
    )

    assert constructs == ()


def test_negated_topic_does_not_become_required_construct() -> None:
    claim = SimpleNamespace(
        text="No housing or rent intervention is requested.",
        metadata={},
    )

    constructs = compiler_module._required_constructs_from_semantics(
        facets=(),
        claims=(claim,),
        scenario_id="case-alpha",
    )

    assert constructs == ()


def test_generic_scope_does_not_infer_pilot_jurisdiction_or_start() -> None:
    facets = {
        "facet:geography": {
            "facet_type": "geography_predicate",
            "value": "national",
        },
        "facet:time": {
            "facet_type": "time_predicate",
            "value": "annual",
        },
    }

    scope = compiler_module._scope_from_facets(facets)

    assert scope.jurisdiction is None
    assert compiler_module._time_start_for_scope(scope) is None


def test_explicit_constructs_are_not_replaced_by_semantic_proposals() -> None:
    claim = SimpleNamespace(text="housing rent support", metadata={})
    scope = DataRequirementScope(
        population="population",
        geography="geography",
        time="time",
    )

    explicit_resolver = _RecordingCapabilityResolver()
    compiler_module._capability_bindings_for_requirements(
        facets=(),
        claims=(claim,),
        obligation_graph={
            "blocking_frontier": [
                {
                    "metadata": {
                        "required_evidence_constructs": ["firm_survival"],
                    }
                }
            ]
        },
        scenario_id="parent-support",
        scope=scope,
        resolver=explicit_resolver,
    )
    assert [query.construct for query in explicit_resolver.queries] == ["firm_survival"]

    proposal_resolver = _RecordingCapabilityResolver()
    bindings = compiler_module._capability_bindings_for_requirements(
        facets=(),
        claims=(claim,),
        obligation_graph={"blocking_frontier": []},
        scenario_id="case-alpha",
        scope=scope,
        resolver=proposal_resolver,
    )
    assert bindings == ()
    assert proposal_resolver.queries == []


def test_semantic_topic_proposal_does_not_cross_capability_authority_boundary() -> None:
    resolver = _RecordingCapabilityResolver()
    claim = SimpleNamespace(text="housing rent support", metadata={})

    bindings = compiler_module._capability_bindings_for_requirements(
        facets=(),
        claims=(claim,),
        obligation_graph=None,
        scenario_id="case-alpha",
        scope=DataRequirementScope(
            population="population",
            geography="geography",
            time="time",
        ),
        resolver=resolver,
    )

    assert bindings == ()
    assert resolver.queries == []


def test_scenario_adapter_accepts_text_request_and_domain_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: list[tuple[str, ProblemDomain]] = []

    def capture_compile(
        _self: object,
        *,
        intent: PolicyGrammarIntent,
        authority_profile: UniversalAuthorityProfile,
        concept_spine_refs: PolicyGrammarConceptSpineRefs,
    ) -> SimpleNamespace:
        del authority_profile, concept_spine_refs
        captured.append((intent.text, intent.domain))
        return SimpleNamespace(facets=None)

    monkeypatch.setattr(compiler_module.PolicyGrammarCompiler, "compile", capture_compile)

    compiler = DataRequirementCompiler()
    compiler.compile_for_scenario(
        {
            "scenario_id": "opaque-case",
            "text": "A neutral health policy statement.",
            "domain": "healthcare",
            "expected_evidence_contract": {
                "admissible_data_source_families": ["health_panel"],
            },
        }
    )
    compiler.compile_for_scenario(
        {
            "scenario_id": "opaque-case-two",
            "request": "A neutral fiscal policy request.",
            "domain_hint": "fiscal",
            "expected_evidence_contract": {
                "admissible_data_source_families": ["fiscal_panel"],
            },
        }
    )

    assert captured == [
        ("A neutral health policy statement.", ProblemDomain.HEALTHCARE),
        ("A neutral fiscal policy request.", ProblemDomain.FISCAL),
    ]


def test_legacy_family_heuristic_only_runs_when_phase4_flag_is_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("POLISYOS_DATA_REQ_FAMILY_FALLBACK_FROM_HARDCODED", "true")
    claim_ledger = {
        "claims": [
            {
                "claim_id": "claim:legacy-worker",
                "claim_family": "implementation",
                "claim_type": "implementation",
                "claim_use": "decision_support",
                "text": "Worker employment outcomes need a labor-force panel.",
                "facet_refs": ("facet:workers",),
                "authority_profile_refs": ("authority_profile.legacy",),
                "concept_spine_refs": ("concept://legacy/workers",),
            }
        ]
    }
    facets = (
        {
            "facet_id": "facet:workers",
            "facet_type": "population_predicate",
            "value": "workers",
            "concept_ref": "concept://legacy/workers",
            "authority_profile": "authority_profile.legacy",
        },
    )

    report = DataRequirementCompiler(capability_resolver=_fake_resolver()).compile_for_claim_ledger(
        run_id="run-legacy-worker",
        scenario_id="legacy_worker_case",
        claim_ledger=claim_ledger,
        facet_snapshots=facets,
        obligation_graph={"blocking_frontier": []},
        authority_profile_refs=("authority_profile.legacy",),
    )

    assert {family for spec in report.specs for family in spec.required_data_families} >= {
        "labor_force_panel",
        "employment_registry",
    }
    assert all(
        spec.metadata.get("family_derivation") == "legacy_heuristic_fallback"
        for spec in report.specs
    )


def test_hardcoded_claim_text_fallback_is_not_used_when_phase4_flag_is_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("POLISYOS_DATA_REQ_FAMILY_FALLBACK_FROM_HARDCODED", raising=False)
    claim_ledger = {
        "claims": [
            {
                "claim_id": "claim:legacy-worker",
                "claim_family": "implementation",
                "claim_type": "implementation",
                "claim_use": "decision_support",
                "text": "Worker employment outcomes need a labor-force panel.",
                "facet_refs": ("facet:workers",),
                "authority_profile_refs": ("authority_profile.legacy",),
                "concept_spine_refs": ("concept://legacy/workers",),
            }
        ]
    }
    facets = (
        {
            "facet_id": "facet:workers",
            "facet_type": "population_predicate",
            "value": "workers",
            "concept_ref": "concept://legacy/workers",
            "authority_profile": "authority_profile.legacy",
        },
    )

    report = DataRequirementCompiler().compile_for_claim_ledger(
        run_id="run-legacy-worker",
        scenario_id="legacy_worker_case",
        claim_ledger=claim_ledger,
        facet_snapshots=facets,
        obligation_graph={"blocking_frontier": []},
        authority_profile_refs=("authority_profile.legacy",),
    )

    assert report.specs == ()
    assert report.legacy_admissible_data_source_families == ()


def test_requirement_spec_rejects_authority_free_or_structural_only_specs() -> None:
    with pytest.raises(ValidationError, match="authority_profile_refs"):
        DataRequirementSpec(
            requirement_id="data-requirement:claim-a",
            claim_id="claim-a",
            required_data_families=("production_msme_panel",),
            scope={
                "population": "msmes",
                "geography": "state_or_region",
                "time": "annual",
                "time_role": "observation_time",
            },
            recency_horizon="P90D",
            lineage_strictness="strict",
            quality_minima={"min_quality_score": 0.8, "min_completeness": 0.95},
            missingness_tolerance=0.05,
            transformation_tolerance="traceable",
            admissibility_predicates=("source_family_matches_compiled_requirement",),
            mandatory_facets=("source_contract_ref",),
            facet_refs=("facet:instrument",),
            obligation_refs=("obl:data",),
            concept_spine_refs=("concept:msme",),
            authority_profile_refs=(),
        )


def test_compilation_report_is_persisted_as_replayable_artifact(tmp_path) -> None:
    case, facets, graph, claim_ledger = _compiled_msme_credit_case()
    report = DataRequirementCompiler().compile_for_claim_ledger(
        run_id="run-msme-credit",
        scenario_id="ukraine_msme_wartime_credit_support",
        claim_ledger=claim_ledger,
        facet_snapshots=facets,
        obligation_graph=graph,
        authority_profile_refs=(case.authority_profile.profile_id,),
    )

    path = write_data_requirement_compilation_report(report, tmp_path)
    persisted = json.loads(path.read_text(encoding="utf-8"))
    surface = data_requirement_compilation_audit_surface(report)

    assert path.name == "run-msme-credit-data-requirements.json"
    assert persisted["schema_version"] == "policyos.data_requirement_compilation.v1"
    assert persisted["runtime_event_ref"] == "event://data-requirement/run-msme-credit"
    assert surface["surface"] == "data_requirement.audit_surface"
    assert surface["summary"]["requirement_count"] == len(report.specs)
    assert surface["authority_boundary"]["authoritative_for"] == [
        "data_requirements",
        "fabric_source_selection_preconditions",
        "scenario_evidence_contract_legacy_projection",
    ]


def _compiled_msme_credit_case() -> tuple[Any, tuple[dict[str, object], ...], Any, Any]:
    text = (
        "Create a concessional credit guarantee programme for displaced MSMEs in "
        "northern regions in 2026, funded by budget appropriation and delivered "
        "through partner banks to preserve employment."
    )
    case = PolicyGrammarCompiler().compile(
        intent=PolicyGrammarIntent(
            intent_id="intent-msme-credit",
            text=text,
            domain=ProblemDomain.FISCAL,
        ),
        authority_profile=UniversalAuthorityProfile(
            profile_id="authority_profile.msme_governed",
            authority_type=PolicyLayerLevel.LOCAL,
        ),
        concept_spine_refs=PolicyGrammarConceptSpineRefs(
            concept_spine_ref="concept-spine://w7/msme-credit",
            jurisdiction_spine_ref="jurisdiction-spine://ua",
            canonical_concept_refs=("concept://policy/msme-credit",),
        ),
    )
    facets = facet_snapshots_for_obligation_graph(case)
    graph = compile_obligation_graph(
        run_id="run-msme-credit",
        facets=facets,
        governed_rules=build_seed_obligation_rule_catalog().rules,
        generated_at=NOW,
        complexity_budget=ComplexityBudget(max_frontier_items=8),
        intent_text=text,
    )
    claim_ledger = compile_claim_decomposition(
        {
            "run_id": "run-msme-credit",
            "intent": text,
            "facets": [
                {
                    "facet_id": facet["facet_id"],
                    "facet_type": facet["facet_type"],
                    "value": facet["value"],
                    "concept_spine_refs": [facet["concept_ref"]],
                    "authority_profile_refs": [facet["authority_profile"]],
                }
                for facet in facets
            ],
            "obligations": [
                {
                    "obligation_id": item.frontier_id,
                    "family": item.bundle_key.family,
                    "description": item.obligation_text,
                    "facet_refs": [facet["facet_id"] for facet in facets],
                    "concept_spine_refs": [facet["concept_ref"] for facet in facets],
                    "authority_profile_refs": [facet["authority_profile"] for facet in facets],
                }
                for item in graph.blocking_frontier
            ],
            "named_alternatives": [
                {
                    "alternative_id": "alternative-cash-grant",
                    "label": "Direct cash grant",
                    "description": "Direct grant instead of a credit guarantee.",
                }
            ],
            "concept_spine_refs": [case.concept_spine_ref],
            "authority_profile_refs": [case.authority_profile.profile_id],
        }
    )
    return case, facets, graph, claim_ledger


def test_obligation_basis_compiler_preserves_inputs_and_candidate_status() -> None:
    import polisyos.data_requirement as data_requirement

    assert data_requirement.PolicyGrammarConceptSpineRefs is PolicyGrammarConceptSpineRefs
    assert data_requirement.PolicyGrammarIntent is PolicyGrammarIntent
    assert data_requirement.UniversalAuthorityProfile is UniversalAuthorityProfile

    compiler = DataRequirementCompiler()
    intent = PolicyGrammarIntent(
        intent_id="runtime-constraint-stage",
        text="Create a concessional credit programme for MSMEs in 2026.",
        domain=ProblemDomain.FISCAL,
    )
    profile = UniversalAuthorityProfile(
        profile_id="runtime-constraint-candidate",
        authority_type=PolicyLayerLevel.FEDERAL,
        source_classification="llm_candidate",
        authoritative_for=("compilation_facets",),
    )
    concept_refs = PolicyGrammarConceptSpineRefs(
        concept_spine_ref="cas://concept-spine/runtime-constraint-stage",
        jurisdiction_spine_ref="cas://jurisdiction/runtime-constraint-stage",
        canonical_concept_refs=("concept://runtime-constraint-stage",),
    )

    candidate = compiler.compile_obligation_basis(
        intent=intent,
        authority_profile=profile,
        concept_spine_refs=concept_refs,
        run_id="runtime-constraint-stage",
        generated_at=NOW,
        intent_text=intent.text,
    )

    assert candidate.case.status == "candidate_unverified"
    assert candidate.case.authority_profile is profile
    assert candidate.case.concept_spine_ref == concept_refs.concept_spine_ref
    assert candidate.facets is None
    assert candidate.rule_catalog is None
    assert candidate.obligation_graph is None

    admitted = compiler.compile_obligation_basis(
        intent=intent,
        authority_profile=UniversalAuthorityProfile(
            profile_id="runtime-constraint-deterministic",
            authority_type=PolicyLayerLevel.LOCAL,
        ),
        concept_spine_refs=concept_refs,
        run_id="runtime-constraint-stage",
        generated_at=NOW,
        intent_text=intent.text,
    )

    assert admitted.case.status == "compiled"
    assert admitted.facets
    assert admitted.rule_catalog is not None
    assert admitted.obligation_graph is not None
    assert admitted.obligation_graph.run_id == "runtime-constraint-stage"
    assert admitted.obligation_graph.generated_at == NOW
    assert admitted.obligation_graph.facets


def test_legacy_scenario_fallback_preserves_scope_profile_declaration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def compile_without_facets(
        _self: object,
        *,
        intent: PolicyGrammarIntent,
        authority_profile: UniversalAuthorityProfile,
        concept_spine_refs: PolicyGrammarConceptSpineRefs,
    ) -> SimpleNamespace:
        del intent, authority_profile, concept_spine_refs
        return SimpleNamespace(facets=None)

    monkeypatch.setattr(compiler_module.PolicyGrammarCompiler, "compile", compile_without_facets)
    profile = {
        "profile_id": "future:ua:2026",
        "jurisdiction": "UA",
        "time_window": {"start": "2026-01-01", "end": "2026-12-31"},
        "required_constructs": ["firm_survival"],
        "candidate_construct_proposals": ["candidate_only_future_construct"],
    }

    report = DataRequirementCompiler().compile_for_scenario(
        {
            "scenario_id": "legacy_profile_case",
            "text": "A neutral policy statement.",
            "expected_evidence_contract": {
                "admissible_data_source_families": ["health_panel"],
            },
            "scenario_profile": profile,
        }
    )

    assert len(report.specs) == 1
    assert report.specs[0].required_data_families == ("health_panel",)
    assert report.specs[0].metadata["scope_profile"] == profile


def test_legacy_scope_profile_carries_only_explicit_time_role_and_granularity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def compile_without_facets(
        _self: object,
        *,
        intent: PolicyGrammarIntent,
        authority_profile: UniversalAuthorityProfile,
        concept_spine_refs: PolicyGrammarConceptSpineRefs,
    ) -> SimpleNamespace:
        del intent, authority_profile, concept_spine_refs
        return SimpleNamespace(facets=None)

    monkeypatch.setattr(compiler_module.PolicyGrammarCompiler, "compile", compile_without_facets)
    profile = {
        "profile_id": "future:ua:2026",
        "jurisdiction": "UA",
        "time_window": {"start": "2026-01-01", "end": "2026-12-31"},
        "time_role": "valid_time",
        "granularity": "annual",
    }

    report = DataRequirementCompiler().compile_for_scenario(
        {
            "scenario_id": "explicit_temporal_scope",
            "text": "A neutral policy statement.",
            "expected_evidence_contract": {
                "admissible_data_source_families": ["health_panel"],
            },
            "scenario_profile": profile,
        }
    )

    assert len(report.specs) == 1
    assert report.specs[0].scope.time_role == "valid_time"
    assert report.specs[0].metadata["scope_profile"] == {
        **profile,
        "required_constructs": [],
        "candidate_construct_proposals": [],
    }


@pytest.mark.parametrize(
    ("scenario", "expected_state"),
    [
        ({"scenario_id": "missing_frontier", "text": "No required family."}, "not_supplied"),
        (
            {
                "scenario_id": "empty_frontier",
                "text": "No required family.",
                "expected_evidence_contract": {
                    "admissible_data_source_families": [],
                },
            },
            "explicit_empty",
        ),
    ],
)
def test_legacy_family_frontier_missing_and_empty_never_invent_production_data(
    monkeypatch: pytest.MonkeyPatch,
    scenario: dict[str, object],
    expected_state: str,
) -> None:
    def compile_without_facets(
        _self: object,
        *,
        intent: PolicyGrammarIntent,
        authority_profile: UniversalAuthorityProfile,
        concept_spine_refs: PolicyGrammarConceptSpineRefs,
    ) -> SimpleNamespace:
        del intent, authority_profile, concept_spine_refs
        return SimpleNamespace(facets=None)

    monkeypatch.setattr(compiler_module.PolicyGrammarCompiler, "compile", compile_without_facets)
    report = DataRequirementCompiler().compile_for_scenario(scenario)

    assert report.specs == ()
    assert report.legacy_admissible_data_source_families == ()
    assert report.metadata["family_declaration"] == expected_state
    assert "production_data" not in report.metadata.values()


def test_legacy_family_frontier_rejects_malformed_entries() -> None:
    with pytest.raises(compiler_module.ScenarioFamilyDeclarationInputError):
        compiler_module._legacy_scenario_family_declaration(
            {
                "expected_evidence_contract": {
                    "admissible_data_source_families": ["health_panel", None],
                },
            }
        )


def test_profile_only_required_resolution_reaches_n7_gap_and_planner_record() -> None:
    from polisyos.runtime.quality.acquisition_planner import (
        AcquisitionWorldSnapshot,
        RecordedAcquisitionOwnerGateway,
        plan_requirement_gap_acquisition,
        requirement_gaps_from_compiled_specs,
        run_acquisition_closed_loop,
    )

    scenario = {
        "scenario_id": "profile_only_n7",
        "request": "A neutral policy statement.",
        "domain_hint": "general",
        "expected_evidence_contract": {"admissible_data_source_families": []},
        "scenario_profile": {
            "profile_id": "profile:controlled-n7",
            "required_constructs": ["scope_only_unique_probe"],
            "candidate_construct_proposals": ["candidate_only_future_construct"],
        },
    }
    report = DataRequirementCompiler(
        capability_resolver=_RecordingCapabilityResolver()
    ).compile_for_scenario(scenario)

    assert report.capability_requirement_resolutions is not None
    resolution = next(
        item
        for item in report.capability_requirement_resolutions
        if item.query.construct == "scope_only_unique_probe"
    )
    gaps = requirement_gaps_from_compiled_specs(
        data_requirement_specs=report.specs,
        capability_requirement_resolutions=report.capability_requirement_resolutions,
    )
    gap = next(
        item
        for item in gaps
        if any(
            row.query.requirement_id == resolution.query.requirement_id
            for row in (item.capability_requirement_resolutions or ())
        )
    )
    assert gap.scenario_requirement_refs == (
        resolution.query.requirement_id,
        "construct:scope_only_unique_probe",
    )
    assert "compiled_data_requirement_spec_missing" in gap.missing_requirement_fields
    assert gap.capability_requirement_resolutions == (resolution,)

    planner = plan_requirement_gap_acquisition(
        run_id="profile-only-n7",
        requirement_gaps=gaps,
    )
    record = next(
        item
        for item in planner.acquisition_records
        if item.compiled_requirement_ref == resolution.query.requirement_id
    )
    assert record.capability_requirement_resolutions == (resolution,)
    assert record.capability_requirement_resolutions[0].binding is not None
    assert record.capability_requirement_resolutions[0].binding.status == "selected_derived"

    receipt = run_acquisition_closed_loop(
        run_id="profile-only-n7-receipt",
        acquisition_request={"cycle_index": 1, "driver": "acquire_data:scope_only_unique_probe"},
        data_requirement_specs=report.specs,
        capability_requirement_resolutions=report.capability_requirement_resolutions,
        world_snapshot=AcquisitionWorldSnapshot(world_ref="world:profile-only-n7"),
        owner_gateway=RecordedAcquisitionOwnerGateway(artifacts_by_requirement={}),
    )
    receipt_record = next(
        item
        for item in receipt.planner_report.acquisition_records
        if item.compiled_requirement_ref == resolution.query.requirement_id
    )
    assert receipt.capability_requirement_resolutions == report.capability_requirement_resolutions
    assert receipt_record.capability_requirement_resolutions == (resolution,)
    assert receipt_record.capability_requirement_resolutions[0].query.construct == (
        "scope_only_unique_probe"
    )
    restored = type(receipt).model_validate(receipt.model_dump(mode="json"))
    assert restored.capability_requirement_resolutions == report.capability_requirement_resolutions
    restored_record = next(
        item
        for item in restored.planner_report.acquisition_records
        if item.compiled_requirement_ref == resolution.query.requirement_id
    )
    assert restored_record.capability_requirement_resolutions == (resolution,)


def test_profile_only_requirement_without_resolver_is_typed_not_established() -> None:
    report = DataRequirementCompiler().compile_for_scenario(
        {
            "scenario_id": "unknown_profile_n7",
            "request": "A neutral policy statement.",
            "domain_hint": "general",
            "expected_evidence_contract": {"admissible_data_source_families": []},
            "scenario_profile": {
                "profile_id": "profile:unknown-n7",
                "required_constructs": ["firm_survival", "scope_only_unique_probe"],
            },
        }
    )

    assert report.capability_requirement_resolutions is not None
    assert tuple(row.query.construct for row in report.capability_requirement_resolutions) == (
        "firm_survival",
        "scope_only_unique_probe",
    )
    assert all(
        row.scope_profile_id == "profile:unknown-n7"
        for row in report.capability_requirement_resolutions
    )
    assert all(row.state == "not_established" for row in report.capability_requirement_resolutions)
    assert all(row.binding is None for row in report.capability_requirement_resolutions)
    assert all(
        row.reason_codes == ("capability_resolver_not_established",)
        for row in report.capability_requirement_resolutions
    )


def test_direct_and_profile_construct_sources_join_conjunctively() -> None:
    resolver = _RecordingCapabilityResolver()
    profile = {
        "profile_id": "profile:conjunctive-sources",
        "jurisdiction": "UA",
        "required_constructs": ["profile_top_unique_probe"],
        "candidate_construct_proposals": ["profile_candidate_only"],
    }
    context_profile = {
        "profile_id": "profile:conjunctive-sources",
        "jurisdiction": "UA",
        "required_constructs": ["profile_context_unique_probe"],
        "candidate_construct_proposals": ["context_candidate_only"],
    }
    scenario = {
        "scenario_id": "direct_and_profile_construct_sources",
        "request": "A neutral policy statement.",
        "domain_hint": "general",
        "expected_evidence_contract": {"admissible_data_source_families": ["health_panel"]},
        "scenario_profile": profile,
        "context": {"scope_profile": context_profile},
        "required_constructs": ["direct_required_unique_probe"],
        "construct_refs": ["direct_ref_unique_probe"],
        "candidate_construct_proposals": ["direct_candidate_only"],
    }

    report = DataRequirementCompiler(capability_resolver=resolver).compile_for_scenario(scenario)

    required = {
        "profile_top_unique_probe",
        "profile_context_unique_probe",
        "direct_required_unique_probe",
        "direct_ref_unique_probe",
    }
    queried = {query.construct for query in resolver.queries}
    assert required <= queried
    assert {"profile_candidate_only", "context_candidate_only", "direct_candidate_only"} <= set(
        report.metadata["candidate_construct_proposals"]
    )
    assert not queried.intersection(
        {"profile_candidate_only", "context_candidate_only", "direct_candidate_only"}
    )
    admitted = compiler_module._scenario_scope_profile(scenario)
    assert admitted is not None
    assert set(admitted.required_constructs) == required
    assert set(admitted.candidate_construct_proposals) == {
        "profile_candidate_only",
        "context_candidate_only",
        "direct_candidate_only",
    }


def test_malformed_direct_construct_source_is_typed_refused() -> None:
    with pytest.raises(compiler_module.ScenarioScopeProfileInputError) as raised:
        DataRequirementCompiler(capability_resolver=_fake_resolver()).compile_for_scenario(
            {
                "scenario_id": "malformed_direct_construct_source",
                "request": "A neutral policy statement.",
                "domain_hint": "general",
                "required_constructs": {"not": "a sequence"},
            }
        )

    assert raised.value.code == "scenario_scope_profile_invalid"
    assert raised.value.reason_code == "profile_constructs_wrong_type"
    assert raised.value.field_path == "scenario.required_constructs"


_PROFILE_SOURCE_PATHS = (
    *compiler_module._SCENARIO_PROFILE_TOP_LEVEL_ALIASES,
    *(f"context.{alias}" for alias in compiler_module._SCENARIO_PROFILE_CONTEXT_ALIASES),
)
_PROFILE_CONSTRUCT_ALIASES = tuple(
    dict.fromkeys(
        (
            *compiler_module._SCENARIO_PROFILE_REQUIRED_CONSTRUCT_ALIASES,
            *compiler_module._SCENARIO_PROFILE_CANDIDATE_CONSTRUCT_ALIASES,
        )
    )
)
_NULL_CONSTRUCT_ALIAS_PATHS = (
    *(
        ("scenario", alias)
        for alias in (
            *compiler_module._SCENARIO_DIRECT_REQUIRED_CONSTRUCT_ALIASES,
            *compiler_module._SCENARIO_DIRECT_CANDIDATE_CONSTRUCT_ALIASES,
        )
    ),
    *tuple(
        (profile_path, field_name)
        for profile_path in _PROFILE_SOURCE_PATHS
        for field_name in _PROFILE_CONSTRUCT_ALIASES
    ),
)


@pytest.mark.parametrize(
    ("source_path", "field_name"),
    _NULL_CONSTRUCT_ALIAS_PATHS,
    ids=lambda value: str(value),
)
def test_present_null_construct_alias_is_typed_refused_across_all_sources(
    source_path: str,
    field_name: str,
) -> None:
    scenario: dict[str, object] = {
        "scenario_id": "present_null_construct_alias",
        "request": "A neutral policy statement.",
        "domain_hint": "general",
    }
    if source_path == "scenario":
        scenario[field_name] = None
    else:
        profile = {"profile_id": "profile:present-null", field_name: None}
        if source_path.startswith("context."):
            alias = source_path.removeprefix("context.")
            scenario["context"] = {alias: profile}
        else:
            scenario[source_path] = profile

    with pytest.raises(compiler_module.ScenarioScopeProfileInputError) as raised:
        DataRequirementCompiler(capability_resolver=_fake_resolver()).compile_for_scenario(scenario)

    assert raised.value.code == "scenario_scope_profile_invalid"
    assert raised.value.reason_code == "profile_constructs_wrong_type"
    assert raised.value.field_path == f"{source_path}.{field_name}"


@pytest.mark.parametrize(
    ("source_path", "field_name", "malformed_value"),
    [
        ("scenario", "required_constructs", {"not": "a sequence"}),
        ("scenario", "construct_refs", [None]),
        ("scenario", "candidate_construct_proposals", [""]),
        ("scenario_profile", "required_constructs", {"not": "a sequence"}),
        ("context.scope_profile", "required_evidence_constructs", [None]),
        ("profile", "topic_proposals", [""]),
    ],
)
def test_wrong_type_or_invalid_construct_item_is_typed_refused(
    source_path: str,
    field_name: str,
    malformed_value: object,
) -> None:
    scenario: dict[str, object] = {
        "scenario_id": "malformed_construct_alias",
        "request": "A neutral policy statement.",
        "domain_hint": "general",
    }
    if source_path == "scenario":
        scenario[field_name] = malformed_value
    else:
        profile = {"profile_id": "profile:malformed-alias", field_name: malformed_value}
        if source_path.startswith("context."):
            alias = source_path.removeprefix("context.")
            scenario["context"] = {alias: profile}
        else:
            scenario[source_path] = profile

    with pytest.raises(compiler_module.ScenarioScopeProfileInputError) as raised:
        DataRequirementCompiler(capability_resolver=_fake_resolver()).compile_for_scenario(scenario)

    assert raised.value.reason_code in {
        "profile_constructs_wrong_type",
        "profile_construct_invalid",
    }


def test_construct_alias_strings_and_empty_sequences_remain_valid() -> None:
    parsed = compiler_module._scenario_scope_profile(
        {
            "required_constructs": "direct_single_construct",
            "candidate_construct_proposals": "direct_candidate",
            "scenario_profile": {
                "profile_id": "profile:string-aliases",
                "required_constructs": "profile_single_construct",
                "candidate_construct_proposals": "profile_candidate",
            },
        }
    )

    assert parsed is not None
    assert parsed.required_constructs == (
        "profile_single_construct",
        "direct_single_construct",
    )
    assert parsed.candidate_construct_proposals == (
        "profile_candidate",
        "direct_candidate",
    )

    empty_profile = compiler_module._scenario_scope_profile(
        {
            "scenario_profile": {
                "profile_id": "profile:empty-aliases",
                "required_constructs": [],
                "candidate_construct_proposals": (),
            }
        }
    )
    assert empty_profile is not None
    assert empty_profile.required_constructs == ()
    assert empty_profile.candidate_construct_proposals == ()
    assert (
        compiler_module._scenario_scope_profile({"required_constructs": (), "construct_refs": ()})
        is None
    )


def test_candidate_only_scenario_proposal_does_not_replace_semantic_requirements() -> None:
    resolver = _RecordingCapabilityResolver()
    scenario = {
        "scenario_id": "candidate_only_does_not_suppress_requirements",
        "request": (
            "Create a concessional credit guarantee programme for displaced MSMEs in "
            "northern regions in 2026, funded by budget appropriation and delivered "
            "through partner banks to preserve employment."
        ),
        "domain_hint": "Fiscal support",
        "candidate_construct_proposals": ["candidate_only_future_construct"],
    }

    report = DataRequirementCompiler(capability_resolver=resolver).compile_for_scenario(scenario)

    assert resolver.queries
    assert "candidate_only_future_construct" not in {query.construct for query in resolver.queries}
    assert "candidate_only_future_construct" in report.metadata["candidate_construct_proposals"]
