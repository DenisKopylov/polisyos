"""Qualify the exact compiler-descriptor join, without claiming source admission."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime

import pytest

from polisyos.data_requirement import DataRequirementCompiler, DataRequirementSpec
from polisyos.runtime.quality import acquisition_planner as owner
from polisyos.runtime.quality.capability_resolver import RequirementToCapabilityResolver
from polisyos.runtime.quality.data_state_substrate import L1VariableAvailability
from tests.unit.data_requirement.test_compiler import _declared_source_scenario


def _compilation(construct: str, population: str):
    scenario = _declared_source_scenario(construct, population)
    scenario["scenario_id"] = "join-" + construct
    return DataRequirementCompiler(
        capability_resolver=RequirementToCapabilityResolver.governed_fixture(),
        require_capability_index=True,
    ).compile_for_scenario(scenario)


def _source_gap(world_slot: str = "global.unemployment_rate"):
    # The pure join consumes a declared test absence. This does not measure a
    # real Catalog or establish the source cycle's protected-job provenance.
    return owner.l1_variable_availability_requirement_gap(
        candidate_id="candidate-source-join",
        candidate_content_hash="sha256:" + "1" * 64,
        design_problem_ref="sha256:" + "2" * 64,
        authority_level=owner.AuthorityLevel.RESEARCH,
        availability=L1VariableAvailability(
            variable_id=world_slot,
            status="unavailable",
            dataset_count=0,
            metric_binding_count=0,
            observation_count=0,
            coverage_ref="fixture://declared-unavailable/" + world_slot,
        ),
    )


def test_exact_descriptor_join_preserves_source_slot_other_gaps_and_fresh_replay() -> None:
    labor = _compilation("labor.unemployment_rate", "total_labor_force")
    gdp = _compilation("economic.gdp", "national_economy")
    specs = (*labor.specs, *gdp.specs)
    resolutions = (
        *labor.capability_requirement_resolutions,
        *gdp.capability_requirement_resolutions,
    )
    source = _source_gap()
    routed, error = owner._n7_route_compiler_gaps(
        source_gap=source,
        specs=specs,
        capability_resolutions=resolutions,
        require_descriptor_join=True,
    )
    assert error is None
    selected = [gap for gap in routed if source.requirement_gap_id in gap.scenario_requirement_refs]
    assert len(selected) == 1
    assert selected[0].compiled_requirement_ref in {spec.requirement_id for spec in labor.specs}
    assert selected[0].compiled_requirement_ref != source.compiled_requirement_ref
    assert {gap.compiled_requirement_ref for gap in routed} == {
        spec.requirement_id for spec in specs
    }

    planning = owner._n7_source_semantic_planning_gaps(
        source_gap=source,
        compiler_gaps=routed,
        specs=specs,
    )
    actual = owner.plan_evidence_acquisition(
        run_id="source-join",
        gaps=planning,
        generated_at=datetime(2026, 11, 3, tzinfo=UTC),
    )
    assert owner._n7_planner_join_records_match(
        source_gap=source,
        specs=specs,
        capability_resolutions=resolutions,
        report=actual,
        require_descriptor_join=True,
    )
    record = next(
        row
        for row in actual.acquisition_records
        if row.gap_type == owner.AcquisitionGapType.DATA_SNAPSHOT_RELEASE
    )
    assert "global.unemployment_rate" in record.scenario_requirement_refs
    assert source.requirement_gap_id in record.scenario_requirement_refs
    assert source.compiled_requirement_ref in record.scenario_requirement_refs
    assert record.compiled_requirement_ref == selected[0].compiled_requirement_ref
    # Newly qualified joins need the explicit producer marker. The historical
    # unmarked law is not broadened by discovery's presence.
    unmarked, refusal = owner._n7_unmarked_current_compiler_gaps(
        source_gap=source,
        specs=specs,
        capability_resolutions=resolutions,
    )
    assert unmarked == () and refusal == "requirement_gap_not_compiled"


@pytest.mark.parametrize("corruption", ["scope", "descriptor_digest", "duplicate_spec"])
def test_descriptor_join_refuses_unbound_or_ambiguous_compiler_carriers(corruption: str) -> None:
    report = _compilation("labor.unemployment_rate", "total_labor_force")
    specs = report.specs
    resolutions = report.capability_requirement_resolutions
    if corruption == "scope":
        values = deepcopy(specs[0].model_dump(mode="json"))
        values["metadata"]["scope_profile"]["population"] = "unrelated_population"
        specs = (DataRequirementSpec.model_validate(values),)
    elif corruption == "descriptor_digest":
        changed = resolutions[0].model_copy(deep=True)
        changed.candidate_discovery.candidates[0].descriptor["source_assets"][0]["metadata"][
            "target_world_slot"
        ] = "global.gdp"
        resolutions = (changed,)
    else:
        specs = (*specs, *specs)
    routed, error = owner._n7_route_compiler_gaps(
        source_gap=_source_gap(),
        specs=specs,
        capability_resolutions=resolutions,
        require_descriptor_join=True,
    )
    assert routed == () and error == "requirement_gap_not_compiled"


def test_rehashed_wrong_target_cannot_fall_back_to_retained_legacy_slot_tail() -> None:
    resolver = RequirementToCapabilityResolver.governed_fixture()
    capabilities = []
    for capability in resolver.capabilities:
        if capability.construct_id == "labor.unemployment_rate":
            assets = tuple(
                asset.model_copy(
                    update={"metadata": {**asset.metadata, "target_world_slot": "global.gdp"}}
                )
                for asset in capability.source_assets
            )
            capability = capability.model_copy(update={"source_assets": assets})
        capabilities.append(capability)
    scenario = _declared_source_scenario("labor.unemployment_rate", "total_labor_force")
    scenario["expected_evidence_contract"] = {
        "admissible_data_source_families": ["global.unemployment_rate"]
    }
    report = DataRequirementCompiler(
        capability_resolver=RequirementToCapabilityResolver(capabilities=capabilities),
        require_capability_index=True,
    ).compile_for_scenario(scenario)
    assert len(report.specs) == 2
    # The real producer recomputes a valid descriptor digest for the wrong target.
    assert report.capability_requirement_resolutions[0].candidate_discovery.candidates
    source = _source_gap()
    legacy, old_error = owner._n7_route_compiler_gaps(
        source_gap=source,
        specs=report.specs,
        capability_resolutions=report.capability_requirement_resolutions,
    )
    assert old_error is None
    assert (
        len([gap for gap in legacy if source.requirement_gap_id in gap.scenario_requirement_refs])
        == 1
    )
    exact, error = owner._n7_route_compiler_gaps(
        source_gap=source,
        specs=report.specs,
        capability_resolutions=report.capability_requirement_resolutions,
        require_descriptor_join=True,
    )
    assert exact == () and error == "requirement_gap_not_compiled"
