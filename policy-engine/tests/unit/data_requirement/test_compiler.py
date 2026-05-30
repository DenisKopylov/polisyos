from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from polisyos.core.contracts.capability_resolution import RequirementToCapabilityQuery
from polisyos.core.contracts.runtime import UniversalAuthorityProfile
from polisyos.data_requirement import (
    DATA_REQUIREMENT_SPEC_SCHEMA_VERSION,
    DataRequirementCompiler,
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
            None
            if self.status.startswith("blocked_")
            else f"capability:{query.construct}:test"
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


def test_compiler_emits_claim_bound_data_requirement_specs_from_universal_compilation() -> None:
    case, facets, graph, claim_ledger = _compiled_msme_credit_case()

    report = DataRequirementCompiler(
        capability_resolver=_fake_resolver()
    ).compile_for_claim_ledger(
        run_id="run-msme-credit",
        scenario_id="ukraine_msme_wartime_credit_support",
        claim_ledger=claim_ledger,
        facet_snapshots=facets,
        obligation_graph=graph,
        authority_profile_refs=(case.authority_profile.profile_id,),
    )

    required_families = {
        family for spec in report.specs for family in spec.required_data_families
    }
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
    assert {
        binding["construct_ref"]
        for binding in resolver_bindings
    } >= {
        "construct:firm_survival",
        "construct:credit_program_enrollment",
        "construct:regional_displacement_pressure",
    }
    assert all(binding["capability_index_ref"] for binding in resolver_bindings)
    assert all(
        spec.metadata.get("scenario_family_authority_status")
        == "sunset_projection_only"
        for spec in report.specs
    )
    assert all(
        "scenario_family_authority_lookup"
        in spec.metadata.get("may_not_use_for", ())
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
    assert report.metadata["capability_index_refs"] == (
        "capability-index:release-duckdb-fixture",
    )


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

    report = DataRequirementCompiler(
        capability_resolver=_fake_resolver()
    ).compile_for_claim_ledger(
        run_id="run-legacy-worker",
        scenario_id="legacy_worker_case",
        claim_ledger=claim_ledger,
        facet_snapshots=facets,
        obligation_graph={"blocking_frontier": []},
        authority_profile_refs=("authority_profile.legacy",),
    )

    assert {
        family for spec in report.specs for family in spec.required_data_families
    } >= {"labor_force_panel", "employment_registry"}
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
