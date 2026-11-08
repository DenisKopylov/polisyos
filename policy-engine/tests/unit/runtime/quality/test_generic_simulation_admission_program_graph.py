"""Owner-selected generic ProgramGraph plans retain exact compiler lineage."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from polisyos.core import artifacts, canon
from polisyos.core.artifacts import ArtifactRef, FileSystemCAS, ensure_ir_artifact_store
from polisyos.core.compiler.report import CompileReport, put_compile_report
from polisyos.core.contracts.foundry import (
    CompileRequest,
    ExecPlan,
    LoweredIR,
    LoweredIRRef,
    ProgramGraph,
    ProgramGraphRef,
)
from polisyos.core.registry import build_default_registry_bundle
from polisyos.foundry.compile.api import compile as compile_foundry
from polisyos.ir.analytics.interventions import QueryTarget, identification_plan_for_intervention
from polisyos.ir.governance.policy_spec import InterventionSpec
from polisyos.ir.trinity import (
    TrinityBundle,
    load_trinity_bundle_artifact,
    persist_trinity_bundle_artifact,
)
from polisyos.pdc import gy_content_hash, world_model_record_content_hash
from polisyos.runtime.quality.candidate_simulation import CandidateSimulationContextInputs
from polisyos.runtime.quality.generation_cycle import JointSimulationPort
from polisyos.runtime.quality.generic_simulation_admission import (
    GenericCycleN5ProgramGraphRequestProfileV4,
    GenericCycleSimulationAdmissionOwner,
    GenericCycleSimulationN5RequestBindingV2,
    GenericCycleSimulationProfileV1,
)
from polisyos.runtime.quality.intervention_atom_binding import (
    InterventionAtomBinding,
    build_intervention_atom_binding,
)
from polisyos.runtime.quality.joint_simulation_horizon import (
    HorizonSpec,
    JointSimulationHorizonController,
    JointSimulationRequest,
)
from polisyos.runtime.quality.substrate_registry import persist_substrate_registry
from polisyos.runtime.quality.world_model_record import (
    WorldModelRecord,
    build_world_model_record,
    load_world_model_record,
    persist_world_model_record,
    world_model_artifact_views,
)
from polisyos.scientist.orchestration.engine import BudgetInvocationQuotaPolicy
from tests._helpers import world_model_record as world_fixture
from tests.unit.runtime.quality.test_intervention_atom_binding import (
    _bundle,
    _context,
    _intervention,
    _linked,
    _node,
)

_OUTCOME = "government.balance"
_VARIABLES = {"agents.income": "agents.income"}


@dataclass(frozen=True)
class _CompiledSelection:
    store: FileSystemCAS
    world: WorldModelRecord
    profile: GenericCycleSimulationProfileV1
    atom: InterventionAtomBinding
    report: CompileReport
    trinity: TrinityBundle


def _with_hash(profile: GenericCycleSimulationProfileV1) -> GenericCycleSimulationProfileV1:
    body = profile.model_dump(mode="json", exclude={"content_hash"})
    return GenericCycleSimulationProfileV1.model_validate(
        {**body, "content_hash": gy_content_hash(body)}
    )


def _n4_atom(
    trinity: TrinityBundle,
    world: WorldModelRecord,
    intervention: InterventionSpec,
) -> InterventionAtomBinding:
    causal = _node()
    return build_intervention_atom_binding(
        problem_frame_ref=gy_content_hash(trinity.problem_frame.model_dump(mode="json")),
        policy_spec_ref=gy_content_hash(trinity.policy_spec.model_dump(mode="json")),
        intervention=intervention,
        linked_intervention=_linked(intervention),
        causal_intervention=causal,
        query_target=QueryTarget(outcome_variables=(_OUTCOME,)),
        identification_plan=identification_plan_for_intervention(causal),
        causal_context=_context(intervention),
        world_model_record_ref=world.world_model_record_id,
        producer_ref="tests.generic_program_graph_profile",
        operator_proof_type_map={intervention.kind: "node"},
    )


@pytest.fixture
def compiled_selection(tmp_path: Path) -> _CompiledSelection:
    """Build real compiler artifacts and the WMR that selects their graph."""
    store = FileSystemCAS(tmp_path / "cas")
    world_fixture._write_fabric_world_snapshot(tmp_path)
    snapshot_ref = world_fixture._data_snapshot_ref(store)
    registry = build_default_registry_bundle(store, return_selected_profile=True)
    model = world_fixture._model_spec(snapshot_ref, registry.bundle_ref)
    intervention = _intervention()
    trinity = _bundle(intervention).model_copy(update={"model_spec": model})
    trinity_ref = ArtifactRef.model_validate(
        persist_trinity_bundle_artifact(ensure_ir_artifact_store(store), trinity).model_dump(
            mode="python"
        )
    )
    compiled = compile_foundry(
        store,
        CompileRequest(
            input_kind="trinity",
            policy_ref=trinity_ref,
            registry_bundle_ref=registry.bundle_ref,
            return_selected_profile=True,
        ),
    )
    assert compiled.ok
    report = CompileReport.model_validate(
        artifacts.load_core_json_artifact(store, compiled.compile_report_ref)
    )
    assert report.program_graph_ref is not None
    substrate = world_fixture._substrate_registry()
    substrate_ref = persist_substrate_registry(store, substrate)
    built = build_world_model_record(
        store,
        fabric_world_ref=world_fixture._fabric_ref(tmp_path),
        data_forge_snapshot_binding_path=world_fixture._write_data_forge_binding(tmp_path),
        data_snapshot_ref=snapshot_ref,
        model_spec=model,
        skg_causal_prior_ref=world_fixture._skg_ref(tmp_path),
        substrate_registry=substrate,
        substrate_registry_artifact_ref=substrate_ref,
        registry_bundle_artifact_ref=registry.bundle_ref,
        region_or_jurisdiction="UA-30",
        population_scope="wartime_msme",
        policy_domain="fiscal_credit",
        valid_time_scope="2026-05-24/2026-12-31",
        tx_time_scope="2026-05-24T12:00:00+00:00",
        resolution="firm_month",
        branch_mode=world_fixture.BranchMode.OBSERVED,
        policy_slot_ids=("agents.income", _OUTCOME),
        producer_ref="test.generic_program_graph_profile",
        program_graph_refs=(str(report.program_graph_ref.artifact_id),),
        program_graph_view_refs=(report.program_graph_ref,),
        return_selected_profile=True,
    )
    n5 = GenericCycleN5ProgramGraphRequestProfileV4(
        budget_ref="budget://test/selected-graph",
        horizon=HorizonSpec(start=0, end=0, step=1),
        baseline_state={_OUTCOME: 0.0},
        compile_report_ref=ArtifactRef.model_validate(
            compiled.compile_report_ref.model_dump(mode="python")
        ),
        invocation_quota_policy=BudgetInvocationQuotaPolicy(
            allocation_id="test-selected-graph", total_units=2, protected_units=0
        ),
    )
    profile = _with_hash(
        GenericCycleSimulationProfileV1.model_construct(
            profile_id="test-selected-graph",
            profile_selection_ref=gy_content_hash({"test": "selected-graph"}),
            world_model_record_ref=built.record_ref,
            substrate_registry_ref=substrate_ref,
            context_inputs=CandidateSimulationContextInputs(
                substrate_registry=substrate,
                selected_registry_entry_hashes=tuple(
                    entry.entry_content_hash for entry in substrate.entries
                ),
                world_model_record=built.record,
            ),
            n5=n5,
            limitations=(
                "controlled_inputs_only",
                "currentness_not_established",
                "n5_simulation_not_world_evidence",
                "n9_not_admitted",
                "s8_blocked",
                "source_truth_not_established",
            ),
        )
    )
    selected_trinity = load_trinity_bundle_artifact(ensure_ir_artifact_store(store), trinity_ref)
    atom = _n4_atom(selected_trinity, built.record, selected_trinity.policy_spec.interventions[0])
    return _CompiledSelection(store, built.record, profile, atom, report, selected_trinity)


def test_selected_compilation_survives_typed_request_replay(
    compiled_selection: _CompiledSelection,
) -> None:
    case = compiled_selection
    owner = GenericCycleSimulationAdmissionOwner(profiles=(case.profile,), store=case.store)
    options = owner._profile_write_options(
        profile=case.profile, job_id="job", run_id="run", tenant_id="tenant", cell_id="cell"
    )
    n5 = case.profile.n5
    assert isinstance(n5, GenericCycleN5ProgramGraphRequestProfileV4)
    assert options.inputs[-1] == artifacts.input_ref_from_artifact_ref(
        n5.compile_report_ref, role="selected_program_compile_report"
    )
    assert "selected_ncm_ref" not in case.profile.model_dump(mode="json")
    assert all(edge.role != "selected_ncm" for edge in options.inputs)
    profile_ref = case.store.put_json(
        case.profile.model_dump(mode="json"),
        options,
        canon_spec=canon.CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    fresh_owner = GenericCycleSimulationAdmissionOwner(
        profiles=(case.profile,), store=FileSystemCAS(case.store.root)
    )
    reopened = fresh_owner.resolve_profile(
        profile_ref,
        expected_profile=case.profile,
        job_id="job",
        run_id="run",
        tenant_id="tenant",
        cell_id="cell",
    )
    (plan,) = fresh_owner.build_engine_plans(
        profile=reopened,
        world_record=case.world,
        outcome=_OUTCOME,
        variable_map=_VARIABLES,
        atoms=(case.atom,),
    )
    assert plan.engine_kind == "program_graph"
    assert plan.program_compilation_ref == n5.compile_report_ref
    assert plan.program_graph_ref == case.report.program_graph_ref
    assert plan.exec_plan_ref == case.report.exec_plan_ref
    assert plan.variable_map == {
        item.slot_id: item.state_path for item in case.world.policy_slot_map
    }
    request = JointSimulationRequest(
        world_model_record_ref=case.world.world_model_record_id,
        world_model_record=case.world,
        intervention_atoms=(case.atom,),
        selected_outcomes=(_OUTCOME,),
        horizon=n5.horizon,
        engine_plan=(plan,),
        baseline_state=n5.baseline_state,
        budget_ref=n5.budget_ref,
    )
    binding = GenericCycleSimulationN5RequestBindingV2.from_request(request)
    replay = GenericCycleSimulationN5RequestBindingV2.model_validate(
        binding.model_dump(mode="python")
    )
    assert replay.request.engine_plan[0].program_compilation_ref == n5.compile_report_ref
    assert replay.request_content_hash == binding.request_content_hash

    controller = JointSimulationHorizonController()
    port = JointSimulationPort(controller=controller, artifact_store=FileSystemCAS(case.store.root))
    bound_request, consumptions, failures = port._request_with_bound_program_state(request)
    assert not failures
    assert consumptions[0].program_graph_ref == str(case.report.program_graph_ref.artifact_id)
    result = controller.run(bound_request)
    controller.validate_selected_result(request=bound_request, result=result)
    assert result.receipt.engine_kind == "program_graph"
    assert {trajectory.run_level for trajectory in result.trajectories} == {"individual", "joint"}
    for trajectory in result.trajectories:
        # The compiled 20% subsidy transfers part of the actual two opening incomes.
        assert trajectory.points[-1].outcomes[_OUTCOME] == pytest.approx(-0.20 * (1200 + 1800))


@pytest.mark.parametrize(
    ("ref_field", "role", "error"),
    [
        ("program_graph_ref", "program_graph", "generic_cycle_program_graph_wmr_view_mismatch"),
        ("lowered_ir_ref", "lowered_ir", "generic_cycle_program_graph_lowered_ir_mismatch"),
    ],
)
def test_same_compiler_bytes_in_an_unselected_view_fail_exact_join(
    compiled_selection: _CompiledSelection,
    ref_field: str,
    role: str,
    error: str,
) -> None:
    case = compiled_selection
    selected_ref = getattr(case.report, ref_field)
    assert isinstance(selected_ref, ArtifactRef)
    selected_manifest = case.store.get_manifest(selected_ref)
    sibling_ref = case.store.put_bytes(
        case.store.get_bytes(selected_ref),
        artifacts.PutOptions(
            kind=selected_ref.kind,
            media_type=selected_ref.media_type,
            schema=selected_manifest.artifact_schema,
            canon=selected_manifest.canon,
            inputs=selected_manifest.inputs,
            warnings=[
                artifacts.WarningRecord(code="test.sibling_compiler_artifact", msg="Distinct view")
            ],
        ),
        return_selected_profile=True,
    )
    assert sibling_ref.artifact_id == selected_ref.artifact_id
    assert sibling_ref.manifest_profile_sha256 != selected_ref.manifest_profile_sha256
    n5 = case.profile.n5
    assert isinstance(n5, GenericCycleN5ProgramGraphRequestProfileV4)
    report_manifest = case.store.get_manifest(n5.compile_report_ref)
    sibling_report_ref = put_compile_report(
        case.store,
        case.report.model_copy(update={ref_field: sibling_ref}),
        inputs=[
            artifacts.input_ref_from_artifact_ref(sibling_ref, role=role)
            if edge.role == role
            else edge
            for edge in report_manifest.inputs
        ],
        return_selected_profile=True,
    )
    profile = _with_hash(
        case.profile.model_copy(
            update={"n5": n5.model_copy(update={"compile_report_ref": sibling_report_ref})}
        )
    )
    owner = GenericCycleSimulationAdmissionOwner(profiles=(profile,), store=case.store)
    assert world_model_artifact_views(case.world).program_graph_refs == (
        case.report.program_graph_ref,
    )
    with pytest.raises(ValueError, match=error):
        owner.build_engine_plans(
            profile=profile,
            world_record=case.world,
            outcome=_OUTCOME,
            variable_map=_VARIABLES,
            atoms=(case.atom,),
        )


def test_a_different_n4_intervention_cannot_label_the_compiled_action(
    compiled_selection: _CompiledSelection,
) -> None:
    case = compiled_selection
    owner = GenericCycleSimulationAdmissionOwner(profiles=(case.profile,), store=case.store)
    changed_intervention = case.trinity.policy_spec.interventions[0].model_copy(
        update={"params": {"rate": "0.25"}}
    )
    changed = _n4_atom(case.trinity, case.world, changed_intervention)
    with pytest.raises(ValueError, match="generic_cycle_program_graph_n4_intervention_mismatch"):
        owner.build_engine_plans(
            profile=case.profile,
            world_record=case.world,
            outcome=_OUTCOME,
            variable_map=_VARIABLES,
            atoms=(changed,),
        )


def _put_changed_compiler_body(
    store: FileSystemCAS,
    ref: ArtifactRef,
    body: Mapping[str, Any],
    changed_inputs: Mapping[str, ArtifactRef],
) -> ArtifactRef:
    manifest = store.get_manifest(ref)
    assert changed_inputs.keys() <= {edge.role for edge in manifest.inputs}
    return store.put_json(
        body,
        artifacts.PutOptions(
            kind=ref.kind,
            media_type=ref.media_type,
            schema=manifest.artifact_schema,
            inputs=[
                artifacts.input_ref_from_artifact_ref(changed_inputs[edge.role], role=edge.role)
                if edge.role in changed_inputs
                else edge
                for edge in manifest.inputs
            ],
        ),
        return_selected_profile=True,
    )


def _select_graph_in_world(
    world: WorldModelRecord,
    ref: ArtifactRef,
) -> WorldModelRecord:
    views = world_model_artifact_views(world).model_copy(update={"program_graph_refs": (ref,)})
    simulation = world.simulation_model_ref.model_copy(
        update={"program_graph_refs": (str(ref.artifact_id),)}
    )
    draft = world.model_copy(update={"artifact_views": views, "simulation_model_ref": simulation})
    content_hash = world_model_record_content_hash(draft)
    return WorldModelRecord.model_validate(
        {
            **draft.model_dump(mode="json"),
            "content_hash": content_hash,
            "world_model_record_id": f"world_model_record_{content_hash.removeprefix('sha256:')[:16]}",
        }
    )


def test_an_unbound_effective_parameter_cannot_enter_a_selected_graph(
    compiled_selection: _CompiledSelection,
) -> None:
    case = compiled_selection
    store = case.store
    n5 = case.profile.n5
    assert isinstance(n5, GenericCycleN5ProgramGraphRequestProfileV4)
    graph_ref = case.report.program_graph_ref
    lowered_ir_ref = case.report.lowered_ir_ref
    plan_ref = case.report.exec_plan_ref
    assert graph_ref is not None and lowered_ir_ref is not None and plan_ref is not None
    graph = ProgramGraph.model_validate(artifacts.load_core_json_artifact(store, graph_ref))
    (apply,) = (node for node in graph.nodes if node.op and node.op.op_kind == "apply_mechanism")
    assert apply.params_ref is not None
    payload = artifacts.load_core_json_artifact(store, apply.params_ref)
    assert payload["params"] == {"rate": "0.20"}
    # This option exists in the mechanism runtime and was never part of this N4 atom.
    changed_params_ref = _put_changed_compiler_body(
        store,
        apply.params_ref,
        {**payload, "params": {**payload["params"], "debug_mode": True}},
        {},
    )

    # Keep the selected chain internally coherent so the owner reaches the N4 join.
    lowered_ir = LoweredIR.model_validate(artifacts.load_core_json_artifact(store, lowered_ir_ref))
    (mechanism,) = lowered_ir.mechanisms
    changed_lowered_ir = lowered_ir.model_copy(
        update={
            "mechanisms": [
                mechanism.model_copy(update={"effective_params_ref": changed_params_ref})
            ]
        }
    )
    changed_lowered_ref = _put_changed_compiler_body(
        store, lowered_ir_ref, changed_lowered_ir.model_dump(mode="json"), {}
    )
    changed_graph = graph.model_copy(
        update={
            "lowered_ir_ref": LoweredIRRef.model_validate(changed_lowered_ref.model_dump()),
            "nodes": [
                node.model_copy(update={"params_ref": changed_params_ref})
                if node == apply
                else node
                for node in graph.nodes
            ],
        }
    )
    changed_graph_ref = _put_changed_compiler_body(
        store,
        graph_ref,
        changed_graph.model_dump(mode="json"),
        {"lowered_ir": changed_lowered_ref, f"params:{apply.node_id}": changed_params_ref},
    )
    plan = ExecPlan.model_validate(artifacts.load_core_json_artifact(store, plan_ref))
    changed_plan = plan.model_copy(
        update={"program_ref": ProgramGraphRef.model_validate(changed_graph_ref.model_dump())}
    )
    changed_plan_ref = _put_changed_compiler_body(
        store, plan_ref, changed_plan.model_dump(mode="json"), {"program_graph": changed_graph_ref}
    )
    changed_report = case.report.model_copy(
        update={
            "lowered_ir_ref": changed_lowered_ref,
            "program_graph_ref": changed_graph_ref,
            "exec_plan_ref": changed_plan_ref,
        }
    )
    changed_report_ref = _put_changed_compiler_body(
        store,
        n5.compile_report_ref,
        changed_report.model_dump(mode="json"),
        {
            "lowered_ir": changed_lowered_ref,
            "program_graph": changed_graph_ref,
            "exec_plan": changed_plan_ref,
        },
    )
    changed_world = _select_graph_in_world(case.world, changed_graph_ref)
    changed_world_ref = persist_world_model_record(
        store, changed_world, return_selected_profile=True
    )
    world = load_world_model_record(store, changed_world_ref)
    profile = _with_hash(
        case.profile.model_copy(
            update={
                "world_model_record_ref": changed_world_ref,
                "context_inputs": case.profile.context_inputs.model_copy(
                    update={"world_model_record": world}
                ),
                "n5": n5.model_copy(update={"compile_report_ref": changed_report_ref}),
            }
        )
    )
    atom = _n4_atom(case.trinity, world, case.trinity.policy_spec.interventions[0])
    owner = GenericCycleSimulationAdmissionOwner(profiles=(profile,), store=store)
    with pytest.raises(ValueError, match="generic_cycle_program_graph_n4_parameter_mismatch"):
        owner.build_engine_plans(
            profile=profile,
            world_record=world,
            outcome=_OUTCOME,
            variable_map=_VARIABLES,
            atoms=(atom,),
        )
