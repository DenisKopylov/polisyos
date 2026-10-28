"""Actual acquisition source faults survive the cycle and a fresh persisted reader."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from polisyos.core.artifacts import FileSystemCAS, PutOptions, load_core_json_artifact
from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.canon import CanonSpec
from polisyos.data_forge.read_api import catalog as catalog_api
from polisyos.fabric.retrieval.service import RetrievalService
from polisyos.pdc import gy_content_hash
from polisyos.runtime.http.services.control.generation_cycle import (
    COMPILED_RECURSIVE_GENERATION_CYCLE_SCHEMA_VERSION,
    CompiledRecursiveGenerationCycleRun,
)
from polisyos.runtime.quality.acquisition_planner import RealAcquisitionOwnerGateway
from polisyos.runtime.quality.design_axes.coupling_composition import derive_recursive_design_graph
from polisyos.runtime.quality.generation_cycle import (
    GenerationCycleController,
    RealValueOwnerGateway,
    ValueOwnerAccessError,
    _blocked_value_owner_failure,
)
from polisyos.runtime.quality.recursive_generation_cycle import (
    RecursiveCycleBudget,
    RecursiveGenerationCycleController,
)
from polisyos.runtime.quality.substrate_registry import catalog_serving_source_scope
from tests._helpers import controlled_candidate_profile as fixtures
from tests._helpers.acquisition_production import install_fixture_wdi_cost_basis
from tests._helpers.measurement_execution_binding import measurement_execution_binding
from tests.unit.runtime.quality.test_catalog_source_identity import (
    _actual_profile_gateway_inputs,
    _selected_fixture,
)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("fault", "expected_code"),
    [
        ("wal", "catalog_read_source_checkpoint_required"),
        ("missing", "catalog_read_source_unavailable"),
        ("closed", "catalog_read_native_query_unavailable"),
    ],
)
async def test_actual_gateway_fault_is_persisted_as_exact_n7_cycle_refusal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fault: str, expected_code: str
) -> None:
    """This component fixture proves failure transport, not ordinary CGF/authority."""
    code, _owner, source = _selected_fixture(tmp_path)
    _gateway_type, problem, _candidate = _actual_profile_gateway_inputs()
    problem = problem.model_copy(
        update={
            "jurisdiction_time": problem.jurisdiction_time.model_copy(
                update={"region": "UKR", "data_time": "2024"}
            ),
            "objectives": [
                problem.objectives[0].model_copy(
                    update={"objective_id": "government.balance", "metric_id": "government.balance"}
                )
            ],
        }
    )
    store_root = tmp_path / "runtime-cas"
    store = FileSystemCAS(store_root)
    install_fixture_wdi_cost_basis(monkeypatch)
    scope_binding = measurement_execution_binding(tmp_path)
    # The existing helper obtains this through persisted job/event/outbox and
    # its execution fence. No caller-written eligibility flag substitutes here.
    assert scope_binding.authority_eligible is True
    value_owner = RealValueOwnerGateway(repo_root=code, catalog_serving_source=source)
    actual_gaps = []

    class ActualMissingValuePort:
        def __call__(self, *, candidate, problem, simulation, cycle_index):
            del cycle_index
            started = time.monotonic()
            failure = None
            try:
                value_owner.load_value_data_profile(
                    candidate=candidate, problem=problem, world_record=simulation.world_model_record
                )
            except ValueOwnerAccessError as exc:
                failure = exc
            assert failure is not None, "actual fixture variable should be unavailable"
            assert failure.owner_gap_evidence is not None
            actual_gaps.append(failure.owner_gap_evidence)
            return _blocked_value_owner_failure(
                failure=failure,
                fallback_code="fixture_fallback_must_not_run",
                fallback_reason_prefix="",
                candidate=candidate,
                problem=problem,
                mode="simulate_only",
                started=started,
                candidate_id=candidate.candidate_id,
            )

    entered_resolutions = []
    original_resolve = RetrievalService.resolve
    retained = tmp_path / "retained-transient-source-fault"
    wal = source.database_path.with_name(source.database_path.name + ".wal")

    def transient_actual_source_failure(self, request, *, run_profile=None):
        entered_resolutions.append(tuple(need.metric for need in request.data_needs))
        if fault == "wal":
            wal.write_bytes(b"controlled uncheckpointed owner state")
        elif fault == "missing":
            source.database_path.replace(retained)
        else:
            assert len(native_graphs) == 1
            native_graphs[0].close()
        try:
            return original_resolve(self, request, run_profile=run_profile)
        finally:
            if fault == "wal":
                wal.replace(retained)
            elif fault == "missing":
                retained.replace(source.database_path)

    monkeypatch.setattr(RetrievalService, "resolve", transient_actual_source_failure)
    native_graphs = []

    def graph_factory(database_path: Path, index_dir: Path):
        graph = catalog_api.DatasetCatalogGraph(
            database_path, index_dir, overlay_path=source.overlay_path
        )
        native_graphs.append(graph)
        return graph

    # The public gateway constructor selects a real graph factory, not an
    # acquisition or error result.
    gateway = RealAcquisitionOwnerGateway(
        repo_root=code,
        dataset_catalog_factory=graph_factory,
        artifact_store=store,
        catalog_serving_source=source,
        catalog_run_profile=source.catalog_run_profile,
    )

    def controller_factory(_node_ref, _node_problem):
        return GenerationCycleController(
            generation_port=fixtures._CgfGenerationPort(target_world_slots=("government.balance",)),
            value_port=ActualMissingValuePort(),
            authority_scope="contract_testing",
            artifact_store=store,
            repo_root=code,
            acquisition_owner_gateway=gateway,
            measurement_root_execution_binding=scope_binding,
            catalog_serving_source=source,
        )

    problem_ref = gy_content_hash(problem.model_dump(mode="json"))
    root_ref = "design-problem://" + problem_ref.removeprefix("sha256:")
    graph = derive_recursive_design_graph(
        design_ref=root_ref,
        module_refs=(),
        parent_child_edges=(),
        rule_version_ref="polisyos.runtime.recursive_generation_cycle.v1",
    )
    controller = RecursiveGenerationCycleController.for_contract_testing(
        cycle_controller_factory=controller_factory,
        repo_root=code,
        artifact_store=store,
    )
    with catalog_serving_source_scope(source):
        run = await controller.run(
            graph,
            problems_by_node={root_ref: problem},
            budget_state=fixtures._budget(),
            recursive_budget=RecursiveCycleBudget(
                max_depth=0, max_nodes=1, min_cycles_per_leaf=1, max_cycles_per_leaf=1
            ),
        )
    assert len(actual_gaps) == 1
    assert entered_resolutions == [("government.balance",)]
    assert len(native_graphs) == 1
    payload = {
        "schema_version": COMPILED_RECURSIVE_GENERATION_CYCLE_SCHEMA_VERSION,
        "design_problem_ref": problem_ref,
        "design_problem": problem.model_dump(mode="json"),
        "cycle_substrate_context_ref": None,
        "recursive_run": run.model_dump(mode="json", exclude={"leaf_nodes"}),
    }
    compiled = CompiledRecursiveGenerationCycleRun.model_validate(
        {**payload, "content_hash": gy_content_hash(payload)}
    )
    ref = store.put_json(
        compiled.model_dump(mode="json"),
        PutOptions(
            kind="runtime.compiled_recursive_generation_cycle",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.runtime.CompiledRecursiveGenerationCycleRun", version="1.0"
            ),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    fresh = CompiledRecursiveGenerationCycleRun.model_validate(
        load_core_json_artifact(FileSystemCAS(store_root), ref)
    )
    assert fresh == compiled
    cycles = [
        cycle
        for leaf in fresh.recursive_run.leaf_nodes
        if leaf.cycle_run is not None
        for cycle in leaf.cycle_run.cycles
    ]
    assert len(cycles) == 1
    cycle = cycles[0]
    assert cycle.terminal_kind == "acquisition_required"
    assert (
        cycle.counterexample.diagnostic.code
        == "n6.acquisition.n7_catalog_source_refused." + expected_code
    )
    assert cycle.acquisition_routing_report_ref is not None
    assert cycle.acquisition_receipt is None
    assert cycle.value_port.acquisition_requirement is not None
    assert cycle.value_port.acquisition_requirement.metadata["availability"] == actual_gaps[
        0
    ].model_dump(mode="json")
    assert gateway.network_counter.network_calls == 0
