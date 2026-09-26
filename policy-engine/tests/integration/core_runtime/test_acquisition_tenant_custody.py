"""Actual acquisition keeps producer custody through the tenant-scoped CAS."""

from pathlib import Path
from typing import Any

import pytest

from polisyos.core import artifacts
from polisyos.core.artifacts.ownership import ArtifactOwnershipError
from polisyos.core.security.tenant_context import tenant_scope
from polisyos.runtime.http.resilience import guard_runtime_cas
from tests.integration.core_runtime.test_acquisition_world_growth_chain import (
    test_actual_wdi_admits_delta_and_reenters_same_case as run_actual_chain,
)
from tests.unit.runtime.http import test_control_service_di as control_fixture


@pytest.mark.asyncio
async def test_actual_acquisition_producers_preserve_tenant_custody_through_reentry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest
) -> None:
    """Reconstructing any producer's store loses ownership and breaks this chain."""
    stores = []

    def build_owned_store(path: Path):
        store = guard_runtime_cas(
            artifacts.FileSystemCAS(path).with_ambient_ownership_enforcement()
        )
        stores.append(store)
        request.addfinalizer(store.close)
        return store

    monkeypatch.setattr(control_fixture, "FileSystemCAS", build_owned_store)
    with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
        await run_actual_chain(tmp_path, monkeypatch, request, guarded_cas=False)
        assert len(stores) == 1
        store = stores[0]
        snapshots = [
            ref
            for ref in store.iter_artifact_ids()
            if store.get_manifest(ref).kind == "fabric.data_snapshot"
        ]
        assert snapshots
        original = {str(ref): store.get_bytes(ref) for ref in snapshots}
        assert all(store.verify(ref).ok for ref in snapshots)

    for tenant_id, cell_id in (("tenant-b", "cell-a"), ("tenant-a", "cell-b")):
        with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
            for ref in snapshots:
                with pytest.raises(ArtifactOwnershipError):
                    store.get_bytes(ref)

    with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
        assert {str(ref): store.get_bytes(ref) for ref in snapshots} == original


def _n7_skg_spec_and_record() -> tuple[dict[str, Any], Any]:
    from tests.unit.runtime.quality.test_acquisition_planner import (
        _compiled_requirement_specs,
        plan_requirement_gap_acquisition,
        requirement_gaps_from_compiled_specs,
    )

    spec = _compiled_requirement_specs()[0].model_dump(mode="json")
    spec.update(
        {
            "requirement_id": "data-requirement:claim-skg-runtime-custody",
            "claim_id": "claim-skg-runtime-custody",
            "required_data_families": ("owner_panel_missing",),
            "required_method_families": ("skg_schema_probe",),
        }
    )
    gap = requirement_gaps_from_compiled_specs(data_requirement_specs=(spec,))[0]
    report = plan_requirement_gap_acquisition(
        run_id="run-n7-runtime-custody",
        requirement_gaps=(gap,),
    )
    return spec, report.acquisition_records[0]


def test_standalone_n7_owner_uses_explicit_tenant_store(
    tmp_path: Path,
) -> None:
    """Standalone SKG capture remains usable when its owner supplies a store."""
    from polisyos.core.artifacts.backends.config import (
        with_ambient_ownership_enforcement_if_supported,
    )
    from polisyos.runtime.quality.acquisition_planner import RealAcquisitionOwnerGateway

    store_root = tmp_path / "explicit-n7-owner-cas"
    store = with_ambient_ownership_enforcement_if_supported(
        artifacts.FileSystemCAS(store_root)
    )
    reader_stores = []
    spec, record = _n7_skg_spec_and_record()
    gateway = RealAcquisitionOwnerGateway(
        repo_root=tmp_path / "source-checkout",
        artifact_store=store,
    )

    try:
        with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
            artifact = gateway.acquire(record=record, compiled_requirement_spec=spec)
            assert artifact is not None
            assert artifact.owner_component == "data_forge.skg"
            resolution = artifact.payload["owner_response"]["resolution"]
            assert "source_snapshot_unavailable" in resolution["refusal_reasons"]
            assert resolution["n8_admission"] == "blocked"
            assert artifact.payload["acquired_substrate_registrations"] == []

            ref = artifacts.ArtifactRef.model_validate(
                artifact.payload["owner_response"]["resolution_ref"]
            )
            tenant_store = artifacts.FileSystemCAS(store_root).for_tenant(
                "tenant-a", "cell-a"
            )
            foreign_store = artifacts.FileSystemCAS(store_root).for_tenant(
                "tenant-b", "cell-b"
            )
            reader_stores.extend((tenant_store, foreign_store))
            assert tenant_store.get_manifest(ref).kind == (
                "runtime.production_grounding_source_resolution"
            )
            assert tenant_store.get_bytes(ref)
            with pytest.raises(ArtifactOwnershipError):
                foreign_store.get_bytes(ref)
        assert not (tmp_path / "source-checkout" / ".n7-live-cas").exists()
    finally:
        for opened_store in (store, *reader_stores):
            close = getattr(opened_store, "close", None)
            if callable(close):
                close()


@pytest.mark.asyncio
async def test_control_service_serves_n7_through_runtime_store_with_tenant_custody(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    request: pytest.FixtureRequest,
) -> None:
    """The public service route preserves its guarded store into default N7."""
    from polisyos.runtime.quality import generation_cycle as cycle_module
    from polisyos.runtime.quality.acquisition_planner import AcquisitionWorldSnapshot
    from tests.unit.runtime.quality.test_generation_cycle import (
        _AcquisitionGrounding,
        _CounterexampleAwareGenerator,
        _budget,
        _canonical_n7_test_atom,
        _n7_substrate_registry,
        _problem,
    )

    stores = []

    def build_owned_store(path: Path):
        store = guard_runtime_cas(
            artifacts.FileSystemCAS(path).with_ambient_ownership_enforcement()
        )
        stores.append(store)
        request.addfinalizer(store.close)
        return store

    monkeypatch.setattr(control_fixture, "FileSystemCAS", build_owned_store)
    foreign_stores = []
    runtime_store_path = tmp_path / ".polisyos"
    emitted_local_receipts = []

    with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
        service = control_fixture._build_control_service(tmp_path)
        try:
            store = service._artifact_store
            runtime = service._promotion_runtime
            assert runtime.store is store
            assert store in stores

            spec, _ = _n7_skg_spec_and_record()
            world = AcquisitionWorldSnapshot(
                world_ref="world://before/served-n7-runtime-custody",
                known_slots=("owner_panel_missing",),
                dependency_index={"owner_panel_missing": ("candidate_cycle_1",)},
                design_revalidation_stages={
                    "candidate_cycle_1": (
                        "identification",
                        "calibration",
                        "value_set",
                        "grounding",
                    )
                },
                substrate_registry=_n7_substrate_registry().model_dump(mode="json"),
            )
            problem = _problem("served_n7_runtime_custody").model_copy(
                update={
                    "runtime_hints": {
                        "n7_data_requirement_specs": (spec,),
                        "n7_world_snapshot": world,
                        "n7_useful_design_rate_before": 0.0,
                    }
                }
            )
            atom = _canonical_n7_test_atom(
                problem,
                candidate_id="candidate_cycle_1",
                target_world_slot="owner_panel_missing",
            )
            generator = _CounterexampleAwareGenerator(first_atom=atom)

            async def generate(_port, candidate_problem, *, cycle_index):
                return await generator(candidate_problem, cycle_index=cycle_index)

            def ground(_port, **kwargs):
                return _AcquisitionGrounding()(**kwargs)

            def block_simulation(_port, *, candidate, problem, cycle_index):
                del problem, cycle_index
                return cycle_module.SimulationPortObservation(
                    candidate_id=str(candidate.candidate_id),
                    status="simulation_blocked",
                    authority_blockers=("test_unknown_simulation_scope",),
                )

            monkeypatch.setattr(cycle_module.N4GenerationPort, "__call__", generate)
            monkeypatch.setattr(cycle_module.PolicyGroundingPort, "__call__", ground)
            monkeypatch.setattr(
                cycle_module.JointSimulationPort, "__call__", block_simulation
            )

            original_acquisition = cycle_module.run_acquisition_closed_loop

            def capture_local_receipt(*args, **kwargs):
                receipt = original_acquisition(*args, **kwargs)
                emitted_local_receipts.append(receipt)
                return receipt

            monkeypatch.setattr(
                cycle_module,
                "run_acquisition_closed_loop",
                capture_local_receipt,
            )

            async def compile_problem(**_kwargs):
                return problem

            monkeypatch.setattr(
                control_fixture.generation_cycle_service,
                "build_design_problem_from_nl_request",
                compile_problem,
            )
            monkeypatch.setattr(
                control_fixture.generation_cycle_service,
                "_build_cycle_substrate_context_from_owner",
                lambda **_kwargs: None,
            )
            from polisyos.runtime.quality import substrate_registry

            monkeypatch.setattr(
                substrate_registry,
                "DEFAULT_L2_SCHOLAR_KG_PATH",
                Path("missing-skg-source-for-custody-test.duckdb"),
            )

            compiled = await service.compile_and_run_recursive_generation_cycle(
                raw_request=problem.nl_provenance.raw_request,
                context={},
                model_name="custody-fixture",
                execution_intent="simulate_only",
                compiler_gateway=object(),  # type: ignore[arg-type]
                budget_state=_budget(),
                recursive_budget=control_fixture.RecursiveCycleBudget(
                    max_depth=0,
                    max_nodes=1,
                    min_cycles_per_leaf=1,
                    max_cycles_per_leaf=1,
                ),
                root_evaluation_context=None,
            )

            assert isinstance(
                compiled,
                control_fixture.generation_cycle_service.CompiledRecursiveGenerationCycleRun,
            )
            leaves = compiled.recursive_run.leaf_nodes
            assert len(leaves) == 1
            cycle_run = leaves[0].cycle_run
            assert cycle_run is not None and len(cycle_run.cycles) == 1
            cycle = cycle_run.cycles[0]
            assert cycle.terminal_kind == "acquisition_required"
            assert cycle.simulation.status == "simulation_blocked"
            assert cycle.selected_candidate_ref == "candidate_cycle_1"
            assert cycle.acquisition_receipt is None
            assert cycle.search_iteration.status == "acquisition_required"
            assert cycle.counterexample.diagnostic.code == (
                "n6.acquisition.n7_native_admission_not_established"
            )
            assert len(emitted_local_receipts) == 1
            owner_artifact = emitted_local_receipts[0].owner_artifacts[0]
            assert owner_artifact.owner_component == "data_forge.skg"
            resolution = owner_artifact.payload["owner_response"]["resolution"]
            assert "source_snapshot_unavailable" in resolution["refusal_reasons"]
            assert resolution["n8_admission"] == "blocked"
            assert owner_artifact.payload["acquired_substrate_registrations"] == []

            ref = artifacts.ArtifactRef.model_validate(
                owner_artifact.payload["owner_response"]["resolution_ref"]
            )
            assert store.get_manifest(ref).kind == (
                "runtime.production_grounding_source_resolution"
            )
            assert store.get_bytes(ref)
            foreign_store = artifacts.FileSystemCAS(runtime_store_path).for_tenant(
                "tenant-b", "cell-b"
            )
            foreign_stores.append(foreign_store)
            with pytest.raises(ArtifactOwnershipError):
                foreign_store.get_bytes(ref)
            assert not (tmp_path / ".n7-live-cas").exists()
        finally:
            service.close()
            for store in foreign_stores:
                close = getattr(store, "close", None)
                if callable(close):
                    close()
