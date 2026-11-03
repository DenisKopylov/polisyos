"""Candidate prefetch world checks over real controlled WDI/CAS/profile owners.

The closure transport, prior-owner selection and fetch-boundary probe are test
adapters. The production compiler selector, world guard, route selector,
configured profile owner and CanonicalAcquisitionAuthority.resolve run
unchanged. This is a unit prefetch composition check, not a served-route,
live-prior-selection or empirical-authority claim.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, replace
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING

import aiohttp
import pytest

from polisyos.core.artifacts import FileSystemCAS, load_core_json_artifact
from polisyos.core.contracts.fabric import (
    CandidateAcquisitionSourceDataSnapshotLineage,
    DataSnapshot,
)
from polisyos.core.security.tenant_context import tenant_scope
from polisyos.data_forge.read_api import catalog
from polisyos.data_requirement import DataRequirementCompilationReport
from polisyos.pdc import gy_content_hash
from polisyos.runtime.quality import acquisition_executor
from polisyos.runtime.quality.acquisition_world_growth import (
    AcquisitionCandidateSourceRoute,
    AcquisitionWorldGrowthBridge,
    AcquisitionWorldGrowthConfig,
)
from polisyos.runtime.quality.candidate_acquisition_source import (
    validate_candidate_acquisition_selection,
)
from polisyos.runtime.quality.candidate_simulation import (
    CandidateSimulationScenarioProfile,
    CandidateSimulationSyntheticModelDeclarationV1,
    candidate_simulation_profile_ref,
)
from polisyos.runtime.quality.cycle_substrate import (
    ConfiguredCandidateSimulationContextAdmissionOwner,
)
from polisyos.runtime.quality.data_snapshot_lineage import validate_data_snapshot_owner_lineage
from polisyos.runtime.quality.data_state_substrate import (
    CandidateAcquisitionSourceSlotBinding,
    DataStateSubstrateError,
    _require_candidate_acquisition_world_values,
)
from polisyos.runtime.quality.design_problem import DesignProblem
from polisyos.runtime.quality.world_model_record import (
    read_world_model_record_owner_values,
    world_model_artifact_views,
)
from tests._helpers.lane01_wdi_profiles import (
    UNEMPLOYMENT_PROFILE,
    build_fixture_wdi_authority,
)
from tests.unit.runtime.quality.test_candidate_acquisition_world import (
    CELL_ID,
    TENANT_ID,
    _candidate_world_case,
)
from tests.unit.runtime.quality.test_candidate_source_basis import _inputs
from tests.unit.runtime.quality.test_lane01_candidate_prefetch import (
    _persist_descriptor_variant,
    _PrefetchFixture,
)

if TYPE_CHECKING:
    from polisyos.runtime.quality.acquisition_planner import AcquisitionRequirementBasisBinding
    from tests.unit.runtime.quality.test_candidate_acquisition_world import _CandidateWorldCase


@dataclass(frozen=True, slots=True)
class _PlannerSelector:
    compiled_requirement_ref: str


@dataclass(frozen=True, slots=True)
class _ClosureTransport:
    """Exactly the fields consumed by the real route/world scope methods."""

    tenant_id: str
    cell_id: str
    run_id: str
    route_id: str
    design_problem_ref: str
    design_problem_basis: DesignProblem
    planner_record: _PlannerSelector


@dataclass(slots=True)
class _WorldScopeAdapter:
    """Run both production methods with real configured owners and a unit closure."""

    artifact_store: FileSystemCAS
    authority: catalog.CanonicalAcquisitionAuthority
    cycle_substrate_context_admission_owner: ConfiguredCandidateSimulationContextAdmissionOwner
    config: AcquisitionWorldGrowthConfig
    world_checks: int = 0

    def candidate_source_selection(
        self, closure: _ClosureTransport
    ) -> AcquisitionCandidateSourceRoute | None:
        return AcquisitionWorldGrowthBridge.candidate_source_selection(self, closure)

    def _candidate_source_prior_owner(
        self, *, closure: _ClosureTransport
    ) -> tuple[
        CandidateSimulationScenarioProfile,
        CandidateSimulationSyntheticModelDeclarationV1,
        ConfiguredCandidateSimulationContextAdmissionOwner,
    ]:
        """Supply the real configured owner for this world-scope-only adapter."""
        selection = self.candidate_source_selection(closure)
        assert selection is not None
        owner = self.cycle_substrate_context_admission_owner
        profile = owner.configured_profile_for_selection_ref(selection.profile_selection_ref)
        assert type(profile) is CandidateSimulationScenarioProfile
        declarations = tuple(
            item
            for item in owner.model_declarations
            if item.profile_config_ref == candidate_simulation_profile_ref(profile)
        )
        assert len(declarations) == 1
        assert type(declarations[0]) is CandidateSimulationSyntheticModelDeclarationV1
        return profile, declarations[0], owner

    def validate_candidate_source_world_scope(
        self, *, closure: _ClosureTransport, resolved: catalog.ResolvedAcquisitionAuthority
    ) -> None:
        self.world_checks += 1
        AcquisitionWorldGrowthBridge.validate_candidate_source_world_scope(
            self, closure=closure, resolved=resolved
        )


@dataclass(slots=True)
class _FetchBoundary:
    calls: int = 0

    def reached(self) -> None:
        self.calls += 1


def _no_fetch(*_args: object, **_kwargs: object) -> None:
    pytest.fail("candidate world prefetch invoked a source execution")


def _guard_fetch(monkeypatch: pytest.MonkeyPatch) -> None:
    async def no_http(*_args: object, **_kwargs: object) -> None:
        pytest.fail("candidate world prefetch invoked HTTP transport")

    monkeypatch.setattr(acquisition_executor, "execute_live_catalog_acquisition", _no_fetch)
    monkeypatch.setattr(aiohttp.ClientSession, "_request", no_http)


def _prefetch_fixture(case: _CandidateWorldCase) -> _PrefetchFixture:
    source = case.source_case
    report = DataRequirementCompilationReport.model_validate(
        load_core_json_artifact(case.store, source.binding.compiler_report_ref)
    )
    resolutions = tuple(
        row
        for row in (report.capability_requirement_resolutions or ())
        if row.query.requirement_id == source.requirement_id
    )
    assert len(resolutions) == 1
    discovery = resolutions[0].candidate_discovery
    assert discovery is not None
    candidates = tuple(
        row for row in discovery.candidates if row.content_digest == source.candidate_digest
    )
    specs = tuple(
        row
        for row in report.specs
        if row.metadata.get("capability_binding", {}).get("requirement_id") == source.requirement_id
    )
    assert len(candidates) == len(specs) == 1
    return _PrefetchFixture(
        case.store,
        report,
        source.binding,
        source.authority,
        source.entry.entry_id,
        source.authority.resolve(source.entry.entry_id),
        specs[0].requirement_id,
        source.requirement_id,
        candidates[0],
    )


def _world_adapter(
    case: _CandidateWorldCase,
    prefetch: _PrefetchFixture,
    *,
    selection_updates: dict[str, object] | None = None,
    authority: catalog.CanonicalAcquisitionAuthority | None = None,
) -> tuple[_WorldScopeAdapter, _ClosureTransport, AcquisitionCandidateSourceRoute]:
    inputs = _inputs(case)
    owner = ConfiguredCandidateSimulationContextAdmissionOwner(
        profiles=(inputs.configured_profile,),
        model_declarations=(inputs.original_model_declaration,),
        store=case.store,
    )
    problem_ref = gy_content_hash(case.problem.model_dump(mode="json"))
    route_ref = gy_content_hash({"fixture_route": "candidate-prefetch-world"})
    route_values = {
        "tenant_id": TENANT_ID,
        "cell_id": CELL_ID,
        "run_id": case.source_case.source.run_id,
        "route_id": route_ref,
        "design_problem_ref": problem_ref,
        "compiled_requirement_ref": prefetch.compiled_ref,
        "requirement_id": prefetch.requirement_id,
        "candidate_digest": prefetch.candidate.content_digest,
        "profile_selection_ref": case.binding.profile_selection_ref,
        "canonical_variable_id": case.binding.canonical_variable_id,
        "target_slot_id": case.binding.target_slot_id,
        "country_code": "USA",
        "year": 2024,
        "population": "total_labor_force",
        "reentry_budget_usd": Decimal("1.00"),
        **(selection_updates or {}),
    }
    selection = AcquisitionCandidateSourceRoute.model_validate(route_values)
    closure = _ClosureTransport(
        TENANT_ID,
        CELL_ID,
        selection.run_id,
        route_ref,
        problem_ref,
        case.problem,
        _PlannerSelector(prefetch.compiled_ref),
    )
    bridge = _WorldScopeAdapter(
        case.store,
        authority or prefetch.authority,
        owner,
        AcquisitionWorldGrowthConfig(candidate_source_routes=(selection,)),
    )
    return bridge, closure, selection


def _world_arguments(
    case: _CandidateWorldCase,
    selection: AcquisitionCandidateSourceRoute,
    resolved: catalog.ResolvedAcquisitionAuthority,
) -> dict[str, object]:
    scope = resolved.entry.source_measure_scope
    assert scope is not None and scope.denominator is not None
    return {
        "problem": case.problem,
        "base": case.base.record,
        "binding": CandidateAcquisitionSourceSlotBinding(
            profile_selection_ref=selection.profile_selection_ref,
            candidate_digest=selection.candidate_digest,
            canonical_variable_id=selection.canonical_variable_id,
            target_slot_id=selection.target_slot_id,
        ),
        "candidate_digest": selection.candidate_digest,
        "canonical_variable_id": resolved.entry.target_variable,
        "target_slot_id": resolved.entry.target_variable,
        "country_code": selection.country_code,
        "year": selection.year,
        "population": scope.population,
        "canonical_unit": resolved.entry.canonical_unit,
        "quantity_kind": scope.quantity_kind,
        "denominator": scope.denominator,
    }


def _before_fetch(
    *,
    bridge: _WorldScopeAdapter,
    closure: _ClosureTransport,
    prefetch: _PrefetchFixture,
    selection: AcquisitionCandidateSourceRoute,
    boundary: _FetchBoundary,
    entry_id: str,
    binding: AcquisitionRequirementBasisBinding | None = None,
) -> None:
    """Exercise the two production prefetch owners before a unit fetch boundary."""
    _candidate, resolved = validate_candidate_acquisition_selection(
        bridge.artifact_store,
        requirement_basis_binding=binding or prefetch.binding,
        compiled_requirement_ref=selection.compiled_requirement_ref,
        requirement_id=selection.requirement_id,
        candidate_digest=selection.candidate_digest,
        authority=bridge.authority,
        entry_id=entry_id,
        target_slot_id=selection.target_slot_id,
        country_code=selection.country_code,
        year=selection.year,
        population=selection.population,
    )
    bridge.validate_candidate_source_world_scope(closure=closure, resolved=resolved)
    boundary.reached()


def test_candidate_prefetch_world_accepts_real_candidate_scope_before_fetch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with tenant_scope(None, tenant_id=TENANT_ID, cell_id=CELL_ID):
        case = _candidate_world_case(tmp_path, monkeypatch)
        prefetch = _prefetch_fixture(case)
        bridge, closure, selection = _world_adapter(case, prefetch)
        views = world_model_artifact_views(case.base.record)
        reopened = read_world_model_record_owner_values(
            case.store,
            world_model_record=case.base.record,
            registry_bundle_ref=views.registry_bundle_ref,
            substrate_registry=case.substrate_registry,
        )
        assert reopened.model_spec.calibrated is False
        assert reopened.model_spec.time_semantics.start_date == "2024-01-01"
        assert case.source_case.source.observation == pytest.approx(0.175)
        assert type(bridge.authority) is catalog.CanonicalAcquisitionAuthority
        assert prefetch.resolved.entry.source_provenance_class == "model_output"
        _guard_fetch(monkeypatch)
        snapshot = DataSnapshot.model_validate(
            load_core_json_artifact(case.store, case.materialization.data_snapshot_ref)
        )
        lineage = validate_data_snapshot_owner_lineage(
            case.store, case.materialization.data_snapshot_ref, snapshot, candidate_only=True
        )
        assert isinstance(snapshot.source_lineage, CandidateAcquisitionSourceDataSnapshotLineage)
        assert snapshot.source_lineage.candidate_source_ref == case.source_case.source_ref
        payload = load_core_json_artifact(case.store, snapshot.data_ref)
        assert payload["acquisition"]["selected"]["value"] == pytest.approx(0.175)
        assert "candidate_source_not_an_observation" in lineage.required_admissibility_blockers
        before = {str(item) for item in case.store.iter_artifact_ids()}
        _require_candidate_acquisition_world_values(
            **_world_arguments(case, selection, prefetch.resolved)
        )
        boundary = _FetchBoundary()
        _before_fetch(
            bridge=bridge,
            closure=closure,
            prefetch=prefetch,
            selection=selection,
            boundary=boundary,
            entry_id=prefetch.entry_id,
        )
        assert bridge.world_checks == boundary.calls == 1
        assert {str(item) for item in case.store.iter_artifact_ids()} == before
        assert "measurement_validity_not_established" in case.source_case.source.limitations


@pytest.mark.parametrize(
    "difference", ["population", "year", "unit", "canonical_variable", "descriptor"]
)
def test_candidate_prefetch_world_refuses_foreign_scope_before_fetch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, difference: str
) -> None:
    with tenant_scope(None, tenant_id=TENANT_ID, cell_id=CELL_ID):
        case = _candidate_world_case(tmp_path, monkeypatch)
        prefetch = _prefetch_fixture(case)
        authority = prefetch.authority
        resolved = prefetch.resolved
        updates: dict[str, object] = {}
        compiler_binding = prefetch.binding
        if difference == "population":
            foreign = replace(
                UNEMPLOYMENT_PROFILE,
                population="working_age_population",
                denominator="working_age_population",
            )
            authority, entry = build_fixture_wdi_authority(tmp_path / "foreign-population", foreign)
            resolved = authority.resolve(entry.entry_id)
            updates["population"] = foreign.population
        elif difference == "unit":
            foreign = replace(UNEMPLOYMENT_PROFILE, canonical_unit="percent")
            authority, entry = build_fixture_wdi_authority(tmp_path / "foreign-unit", foreign)
            resolved = authority.resolve(entry.entry_id)
            assert (
                resolved.entry.canonical_unit
                != case.base.record.slot_binding(case.binding.target_slot_id).unit
            )
        elif difference == "year":
            updates["year"] = 2023
        elif difference == "canonical_variable":
            updates["canonical_variable_id"] = "global.tax_rate"
        else:
            descriptor = copy.deepcopy(prefetch.candidate.descriptor)
            descriptor["scope"]["geography"] = "CAN"
            compiler_binding, digest = _persist_descriptor_variant(prefetch, descriptor)
            assert digest != prefetch.candidate.content_digest
            updates["candidate_digest"] = digest
        bridge, closure, selection = _world_adapter(
            case, prefetch, selection_updates=updates, authority=authority
        )
        _guard_fetch(monkeypatch)
        if difference != "descriptor":
            with pytest.raises(DataStateSubstrateError) as world_refusal:
                _require_candidate_acquisition_world_values(
                    **_world_arguments(case, selection, resolved)
                )
            assert world_refusal.value.code == "candidate_source_world_scope_mismatch"
            with pytest.raises(ValueError) as direct:
                bridge.validate_candidate_source_world_scope(closure=closure, resolved=resolved)
            if difference == "year":
                assert str(direct.value) == "acquisition_candidate_source_route_binding_mismatch"
            else:
                assert type(direct.value) is DataStateSubstrateError
                assert direct.value.code == "candidate_source_world_scope_mismatch"
        else:
            # Descriptor meaning belongs to its compiler/source owner; a digest
            # marker must not masquerade as a world-scope verification result.
            _require_candidate_acquisition_world_values(
                **_world_arguments(case, selection, resolved)
            )
        before = {str(item) for item in case.store.iter_artifact_ids()}
        checks_before = bridge.world_checks
        boundary = _FetchBoundary()
        with pytest.raises(ValueError) as prefetched:
            _before_fetch(
                bridge=bridge,
                closure=closure,
                prefetch=prefetch,
                selection=selection,
                boundary=boundary,
                entry_id=resolved.entry.entry_id,
                binding=compiler_binding,
            )
        expected = {
            "population": "candidate_source_compiler_relation_mismatch",
            "year": "candidate_source_compiler_relation_mismatch",
            "unit": "candidate_source_descriptor_scope_mismatch",
            "canonical_variable": "candidate_source_world_scope_mismatch",
            "descriptor": "candidate_source_descriptor_scope_mismatch",
        }
        assert str(prefetched.value).partition(":")[0] == expected[difference]
        assert boundary.calls == 0
        assert {str(item) for item in case.store.iter_artifact_ids()} == before
        if difference == "descriptor":
            assert bridge.world_checks == checks_before
