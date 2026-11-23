"""Exercise distinct declared GDP and labor needs through the real N7 compiler."""

from __future__ import annotations

import pytest

from polisyos.data_requirement import DataRequirementCompiler, compiled_requirements_for_world_slot
from polisyos.runtime.quality.capability_index import CapabilityScope
from polisyos.runtime.quality.capability_resolver import RequirementToCapabilityResolver
from polisyos.runtime.quality.design_problem import DesignProblem
from polisyos.runtime.quality.generation_cycle import GenerationCycleController
from tests._helpers.annual_gdp_candidate import annual_gdp_candidate_problem
from tests._helpers.lane01_candidate_problem import labor_candidate_problem
from tests._helpers.lane01_candidate_source import UNEMPLOYMENT_COMPILER_INPUT


def _consistent_labor_problem():
    """Construct a new candidate input; do not reinterpret the retained C run."""
    base = labor_candidate_problem()
    statement = UNEMPLOYMENT_COMPILER_INPUT.text + " Minimize the annual unemployment rate."
    payload = base.model_dump(mode="json")
    payload["problem_statement"] = statement
    payload["nl_provenance"]["raw_request"] = (
        statement + " US labor analysts review the candidate. Do not promote generated candidates."
    )
    payload["outcome_of_interest"]["direction"] = "minimize"
    payload["stakeholders"] = [
        {"stakeholder_id": "labor_analysts", "name": "US labor analysts", "role": "reviewer"}
    ]
    payload["runtime_hints"]["n7_scope_profile"] = UNEMPLOYMENT_COMPILER_INPUT.as_scenario()[
        "scope_profile"
    ]
    return DesignProblem.model_validate(payload)


def _n7_basis(problem, resolver):
    return GenerationCycleController(
        capability_resolver=resolver,
        authority_scope="contract_testing",
    )._n7_data_requirement_basis_with_report(problem, acquisition_request={})


def test_n7_distinguishes_scoped_labor_and_gdp_with_real_resolver() -> None:
    """The compiler selects two actual source descriptors without granting authority."""
    labor = _consistent_labor_problem()
    gdp = annual_gdp_candidate_problem()
    assert labor.domain == "social" and gdp.domain == "economic"
    assert labor.outcome_of_interest.direction == labor.objectives[0].direction == "minimize"
    assert gdp.outcome_of_interest.direction == gdp.objectives[0].direction == "maximize"
    assert labor.problem_statement != gdp.problem_statement
    resolver = RequirementToCapabilityResolver.governed_fixture()

    actual = []
    for problem, construct, population, slot, indicator in (
        (
            labor,
            "labor.unemployment_rate",
            "total_labor_force",
            "global.unemployment_rate",
            "SL.UEM.TOTL.ZS",
        ),
        (gdp, "economic.gdp", "national_economy", "global.gdp", "NY.GDP.MKTP.CD"),
    ):
        basis = _n7_basis(problem, resolver)
        report = basis.compilation_report
        assert report.scenario_id == problem.design_problem_id
        assert report.requirement_basis.state == "established"
        assert report.requirement_basis.basis_grade == "recomputed"
        assert not basis.unbound_input_fields and basis.routing_limitation_code is None
        domain = report.metadata["scenario_domain_resolution"]
        assert domain["raw_inputs"] == {"domain": problem.domain}
        if problem.domain == "social":
            assert domain["canonical_domain"] == "social" and domain["status"] == "resolved"
        else:
            # `economic` is outside the current grammar vocabulary, so the
            # producer must preserve it as declared, not silently use fiscal.
            assert domain["canonical_domain"] == "custom" and domain["status"] == "unresolved"
            assert domain["reason_code"] == "domain_vocabulary_unknown"
        matches = compiled_requirements_for_world_slot(
            world_slot=slot,
            specs=basis.specs,
            capability_resolutions=basis.capability_resolutions,
        )
        assert len(matches) == 1
        (resolution,) = basis.capability_resolutions
        query = resolution.query
        assert query.construct == construct and query.geography == "USA"
        assert query.entity_scope == "country" and query.population_filter == {"type": population}
        assert (query.time_window.start, query.time_window.end) == ("2024-01-01", "2024-12-31")
        assert resolution.binding.status.startswith("blocked_")
        discovery = resolution.candidate_discovery
        assert discovery is not None and not discovery.satisfies_claim_evidence
        (candidate,) = discovery.candidates
        assert candidate.source_assets[0]["metadata"]["indicator_id"] == indicator
        assert candidate.source_assets[0]["metadata"]["target_world_slot"] == slot
        changed_payload = problem.model_dump(mode="json")
        changed_payload["problem_statement"] += " This is a separately declared candidate."
        changed_payload["nl_provenance"]["raw_request"] += (
            " This is a separately declared candidate."
        )
        changed = _n7_basis(DesignProblem.model_validate(changed_payload), resolver)
        assert changed.compilation_report.input_content_hash != report.input_content_hash
        actual.append((report.input_content_hash, query.construct, matches[0].requirement_id))
    assert actual[0][0] != actual[1][0]
    assert actual[0][1:] != actual[1][1:]


def test_n7_labor_refuses_foreign_source_and_unbound_spec_override() -> None:
    """A rehashed wrong source and a caller-supplied spec cannot replace the owner basis."""
    problem = _consistent_labor_problem()
    original = RequirementToCapabilityResolver.governed_fixture()
    positive = _n7_basis(problem, original)
    (selected,) = compiled_requirements_for_world_slot(
        world_slot="global.unemployment_rate",
        specs=positive.specs,
        capability_resolutions=positive.capability_resolutions,
    )
    controller = GenerationCycleController(
        capability_resolver=original, authority_scope="contract_testing"
    )
    refused = controller._n7_data_requirement_basis_with_report(
        problem,
        acquisition_request={"data_requirement_specs": [selected.model_dump(mode="json")]},
    )
    assert refused.unbound_input_fields == ("acquisition_request.data_requirement_specs",)
    assert refused.specs == positive.specs
    assert refused.compilation_report == positive.compilation_report
    assert not refused.routed_compiler_gaps

    capabilities = []
    for capability in original.capabilities:
        if capability.construct_id == "labor.unemployment_rate":
            (asset,) = capability.source_assets
            asset = asset.model_copy(
                update={"metadata": {**asset.metadata, "population_scope": "households"}}
            )
            capability = capability.model_copy(update={"source_assets": (asset,)})
        capabilities.append(capability)
    foreign = RequirementToCapabilityResolver(
        capabilities=tuple(capabilities),
        failure_modes=original.failure_modes,
        acquisition_strategies=original.acquisition_strategies,
        conflicts=original.conflicts,
        capability_index_ref=original.capability_index_ref,
    )
    altered = _n7_basis(problem, foreign)
    (resolution,) = altered.capability_resolutions
    assert resolution.candidate_discovery.candidates
    assert not compiled_requirements_for_world_slot(
        world_slot="global.unemployment_rate",
        specs=altered.specs,
        capability_resolutions=altered.capability_resolutions,
    )
    assert compiled_requirements_for_world_slot(
        world_slot="global.unemployment_rate",
        specs=positive.specs,
        capability_resolutions=positive.capability_resolutions,
    ) == (selected,)


def test_n7_unknown_requirement_basis_is_not_a_no_data_claim() -> None:
    """No declared construct remains not established, even when the spec set is empty."""
    base = _consistent_labor_problem()
    scope = dict(base.runtime_hints["n7_scope_profile"])
    scope.pop("required_constructs")
    payload = base.model_dump(mode="json")
    payload["problem_statement"] = "Assess an unspecified candidate question for USA in 2024."
    payload["nl_provenance"]["raw_request"] = (
        payload["problem_statement"]
        + " US labor analysts review the candidate. Do not promote generated candidates."
    )
    payload["runtime_hints"]["n7_scope_profile"] = scope
    unknown = DesignProblem.model_validate(payload)
    basis = _n7_basis(unknown, RequirementToCapabilityResolver.governed_fixture())
    assert basis.specs == ()
    assert basis.compilation_report.requirement_basis.state == "not_established"
    assert basis.compilation_report.requirement_basis.basis_grade == "not_established"


def test_n7_known_labor_need_without_resolver_is_not_no_need() -> None:
    """An unavailable resolver cannot turn a declared construct into an empty success."""
    problem = _consistent_labor_problem()
    controller = GenerationCycleController(authority_scope="contract_testing")
    assert controller._n7_capability_resolver(problem) is None
    basis = controller._n7_data_requirement_basis_with_report(problem, acquisition_request={})
    assert basis.compilation_report.requirement_basis.state == "not_established"
    assert basis.compilation_report.requirement_basis.basis_grade == "not_established"
    assert not basis.specs
    (resolution,) = basis.capability_resolutions
    assert resolution.query.construct == "labor.unemployment_rate"
    assert resolution.query.population_filter == {"type": "total_labor_force"}
    assert resolution.state == "not_established" and resolution.binding is None
    assert "capability_resolver_not_established" in resolution.reason_codes
    (gap,) = basis.routed_compiler_gaps
    assert gap.compiled_requirement_ref == resolution.query.requirement_id
    assert gap.capability_requirement_resolutions == (resolution,)
    assert gap.metadata["source"] == "data_requirement_capability_resolution"
    assert gap.metadata["authority_purpose"] == "routing_only"
    assert gap.metadata["resolution_state"] == "not_established"
    assert "compiled_data_requirement_spec_missing" in gap.missing_requirement_fields
    assert "capability_resolution_not_established" in gap.missing_requirement_fields
    assert gap.mandatory_gate_state.value == "non_overridable"
    assert not gap.limitation_permitted
    with pytest.raises(FileNotFoundError, match="capability resolver"):
        DataRequirementCompiler(require_capability_index=True).compile_for_scenario(
            {
                "scenario_id": problem.design_problem_id,
                "text": problem.problem_statement,
                "domain": problem.domain,
                "scope_profile": problem.runtime_hints["n7_scope_profile"],
            }
        )


def test_n7_labor_source_outside_declared_year_is_not_selected() -> None:
    """A known stale source interval is distinct from the current 2024 input."""
    problem = _consistent_labor_problem()
    current = RequirementToCapabilityResolver.governed_fixture()
    capabilities = []
    for capability in current.capabilities:
        if capability.construct_id == "labor.unemployment_rate":
            scope = CapabilityScope.model_validate(
                {
                    **capability.scope.model_dump(mode="python"),
                    "time_start": "2023-01-01",
                    "time_end": "2023-12-31",
                }
            )
            capability = capability.model_copy(update={"scope": scope})
        capabilities.append(capability)
    stale = RequirementToCapabilityResolver(
        capabilities=tuple(capabilities),
        failure_modes=current.failure_modes,
        acquisition_strategies=current.acquisition_strategies,
        conflicts=current.conflicts,
        capability_index_ref=current.capability_index_ref,
    )
    stale_basis = _n7_basis(problem, stale)
    (resolution,) = stale_basis.capability_resolutions
    discovery = resolution.candidate_discovery
    assert discovery is not None and discovery.state == "no_match"
    assert not discovery.candidates
    assert discovery.rejected_candidates[0]["rejection_reason"] == "time_window_outside_claim"
    assert not compiled_requirements_for_world_slot(
        world_slot="global.unemployment_rate",
        specs=stale_basis.specs,
        capability_resolutions=stale_basis.capability_resolutions,
    )
    restored = _n7_basis(problem, current)
    assert compiled_requirements_for_world_slot(
        world_slot="global.unemployment_rate",
        specs=restored.specs,
        capability_resolutions=restored.capability_resolutions,
    )
