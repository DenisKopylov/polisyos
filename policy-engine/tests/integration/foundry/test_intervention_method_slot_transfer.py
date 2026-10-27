from __future__ import annotations

from decimal import Decimal
from io import BytesIO

import numpy as np
import pytest


def _put_selected(store, payload, *, kind, schema_name, schema_version, inputs=None):
    from polisyos.core.artifacts.manifest import SchemaInfo
    from polisyos.core.artifacts.store import PutOptions
    from polisyos.core.canon import CanonSpec

    return store.put_json(
        payload,
        PutOptions(
            kind=kind,
            media_type="application/json",
            schema=SchemaInfo(name=schema_name, version=schema_version),
            inputs=inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )


def test_selected_intervention_output_is_captured_as_method_scenario(tmp_path):
    from pydantic import ValidationError

    from polisyos.core.artifacts import validate_core_model_json_artifact
    from polisyos.core.artifacts.async_store import ensure_async_artifact_store
    from polisyos.core.artifacts.manifest import input_ref_from_artifact_ref
    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.core.contracts.execution_plan import (
        ExecutionPlan,
        ExecutionPlanRef,
        MethodDagNode,
    )
    from polisyos.core.contracts.foundry import (
        CompileRequest,
        ExecuteRequest,
        FoundryExecConfig,
        FoundryInputBindingRule,
        MethodExecutionBundle,
        MethodMetricBindingRequest,
        MethodMetricInputCapturePayload,
        MethodOutputPayload,
        ProgramGraph,
        StateSnapshot,
    )
    from polisyos.core.registry import build_registry_bundle
    from polisyos.fabric.data_plane.orchestrator import _build_snapshot_from_evidence_async
    from polisyos.fabric.evidence.evidence import build_evidence_bundle, persist_evidence_bundle
    from polisyos.foundry.compile.api import compile as compile_foundry
    from polisyos.foundry.data_plane import build_input_bindings
    from polisyos.foundry.execute.api import execute as execute_foundry
    from polisyos.foundry.methods.catalog.policy.evaluation import ExAnteSimulationEstimator
    from polisyos.foundry.methods.registry import MethodRegistry
    from polisyos.ir.governance.policy_spec import InterventionSpec, MechanismBinding, PolicySpec
    from polisyos.ir.governance.problem_frame import ObjectiveSpec, ProblemDomain, ProblemFrame
    from polisyos.ir.governance.schedule import ScheduleSpec
    from polisyos.ir.governance.selector_expr import SelectorPredicate
    from polisyos.ir.kernel import (
        DEFAULT_CONSTRAINT_REGISTRY,
        DEFAULT_MECHANISM_REGISTRY,
        DEFAULT_MERGE_RULE_REGISTRY,
        DEFAULT_METRIC_REGISTRY,
        DEFAULT_SELECTOR_FIELD_REGISTRY,
        DEFAULT_SLOT_REGISTRY,
        DEFAULT_UNITS_REGISTRY,
    )
    from polisyos.ir.kernel.method_metrics import (
        METHOD_METRIC_EX_ANTE_MEAN_CHANGE_LAW_ID,
        MethodMetricInputRole,
        MethodMetricSemanticContract,
    )
    from polisyos.ir.kernel.metrics import MetricRegistry, MetricSpec
    from polisyos.ir.kernel.slots import SlotRegistry
    from polisyos.ir.kernel.units import GenericUnit
    from polisyos.ir.model_layer.model_spec import ModelSpec
    from polisyos.ir.model_layer.types import OptimizationDirection, SelectorOperator
    from polisyos.ir.trinity import TrinityBundle
    from polisyos.scientist.policy_design.schema import (
        PolicyCandidateSchema,
        TargetPopulationSpec,
        persist_policy_candidate_schema,
    )

    store = FileSystemCAS(tmp_path / "cas")
    MethodRegistry.get_instance().register(ExAnteSimulationEstimator, override=True)
    signature = ExAnteSimulationEstimator.signature
    method_node_id = "ex_ante_node"
    metric_id = "candidate_model_input_mean_change"
    objective_id = "candidate_model_input_objective"
    semantics = MethodMetricSemanticContract(
        quantity_kind="value",
        quantity_role="scenario_delta",
        population_id="captured_model_input_rows",
        axes=("n_agents",),
        denominator_id="n_agents",
        time_role="pre_dispatch_state",
        producer_contract_id=METHOD_METRIC_EX_ANTE_MEAN_CHANGE_LAW_ID,
        input_roles=(
            MethodMetricInputRole(role_id="baseline", method_input_slot_id="baseline"),
            MethodMetricInputRole(role_id="scenario", method_input_slot_id="scenario"),
        ),
        output_value_path=("mean_change",),
    )
    metric_registry = MetricRegistry(
        schema_version="1.1",
        metrics={
            **DEFAULT_METRIC_REGISTRY.metrics,
            metric_id: MetricSpec(
                metric_id=metric_id,
                unit_id="value",
                description="Candidate-only model-input mean scenario delta.",
                method_semantics=semantics,
            ),
        },
    )
    units_registry = DEFAULT_UNITS_REGISTRY.model_copy(
        update={
            "units": {
                **DEFAULT_UNITS_REGISTRY.units,
                "value": GenericUnit(label="value"),
            }
        }
    )

    def make_registry(scenario_path: str):
        slots = dict(DEFAULT_SLOT_REGISTRY.slots)
        slots["baseline"] = slots["agents.reported_income"].model_copy(
            update={"slot_id": "baseline", "state_path": "agents.reported_income"}
        )
        slots["scenario"] = slots["agents.income"].model_copy(
            update={"slot_id": "scenario", "state_path": scenario_path}
        )
        return build_registry_bundle(
            store,
            slot_registry=SlotRegistry(slots=slots),
            merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
            mechanism_registry=DEFAULT_MECHANISM_REGISTRY,
            constraint_registry=DEFAULT_CONSTRAINT_REGISTRY,
            selector_field_registry=DEFAULT_SELECTOR_FIELD_REGISTRY,
            metric_registry=metric_registry,
            units_registry=units_registry,
            return_selected_profile=True,
        )

    registry = make_registry("agents.income")
    wrong_slot_registry = make_registry("agents.savings")
    source_payload_ref = _put_selected(
        store,
        {
            "agents": {
                "reported_income": [100.0, 200.0],
                "income": [100.0, 200.0],
                "savings": [100.0, 200.0],
            }
        },
        kind="test.intervention_method_input",
        schema_name="polisyos.tests.InterventionMethodInput",
        schema_version="1.0",
    )
    evidence_ref = persist_evidence_bundle(
        store,
        build_evidence_bundle(
            sources=[source_payload_ref],
            notes=["Selected synthetic inputs for a candidate-only bridge test."],
        ),
        return_selected_profile=True,
    )
    data_snapshot_ref = _build_snapshot_from_evidence_async(
        store=ensure_async_artifact_store(store),
        evidence_ref=evidence_ref,
        datasets_fetched=1,
        source="v5_intervention_method_slot_transfer",
    )
    from polisyos.common.async_tools import run_coro_sync

    data_snapshot_ref = run_coro_sync(data_snapshot_ref)
    assert data_snapshot_ref is not None

    problem_frame = ProblemFrame(
        problem_id="v5_intervention_method_problem",
        domain=ProblemDomain.SOCIAL,
        objectives=[
            ObjectiveSpec(
                objective_id=objective_id,
                metric_id=metric_id,
                direction=OptimizationDirection.MAXIMIZE,
            )
        ],
    )

    def make_bindings(selected_registry, *, scenario_source: str):
        return build_input_bindings(
            store,
            data_snapshot_ref=data_snapshot_ref,
            registry_bundle_ref=selected_registry.bundle_ref,
            rules=[
                FoundryInputBindingRule(
                    binding_id="baseline-from-reported-income",
                    source_path="agents.reported_income",
                    target_slot_id="baseline",
                ),
                FoundryInputBindingRule(
                    binding_id="scenario-from-selected-path",
                    source_path=scenario_source,
                    target_slot_id="scenario",
                ),
            ],
            return_selected_profile=True,
        )

    def run_case(
        *,
        case_id: str,
        selected_registry,
        scenario_source: str,
        rate: Decimal | None,
    ):
        interventions = []
        bindings = []
        if rate is not None:
            interventions = [
                InterventionSpec(
                    intervention_id=f"{case_id}_tax",
                    kind="income_tax",
                    target=SelectorPredicate(
                        field="id",
                        operator=SelectorOperator.EQUALS,
                        value="all",
                    ),
                    schedule=ScheduleSpec(start_step=0, duration_steps=1),
                    params={"rate": rate},
                )
            ]
            bindings = [
                MechanismBinding(
                    binding_id=f"{case_id}_tax_binding",
                    mechanism_id="income_tax",
                    intervention_ids=[f"{case_id}_tax"],
                )
            ]
        bundle = TrinityBundle(
            problem_frame=problem_frame,
            policy_spec=PolicySpec(
                policy_id=f"{case_id}_policy",
                interventions=interventions,
                mechanism_bindings=bindings,
            ),
            model_spec=ModelSpec(
                model_id=f"{case_id}_model",
                data_snapshot_ref=str(data_snapshot_ref.artifact_id),
                registry_bundle_ref=str(selected_registry.bundle_ref.artifact_id),
            ),
        )
        candidate_ref = persist_policy_candidate_schema(
            store,
            PolicyCandidateSchema(
                candidate_id=f"{case_id}_candidate",
                trinity_bundle=bundle,
                target_population=TargetPopulationSpec(
                    population_id="captured_model_input_rows",
                    description="Rows materialized by the selected synthetic DataSnapshot.",
                ),
            ),
            inputs=[
                input_ref_from_artifact_ref(
                    data_snapshot_ref,
                    role="world_model_data_snapshot",
                ),
                input_ref_from_artifact_ref(
                    selected_registry.bundle_ref,
                    role="world_model_registry",
                ),
            ],
            return_selected_profile=True,
        )
        trinity_ref = _put_selected(
            store,
            bundle,
            kind=TrinityBundle.ARTIFACT_KIND,
            schema_name=TrinityBundle.ARTIFACT_SCHEMA_NAME,
            schema_version=TrinityBundle.ARTIFACT_SCHEMA_VERSION,
            inputs=[input_ref_from_artifact_ref(candidate_ref, role="policy_candidate")],
        )
        method_node = MethodDagNode(
            node_id=method_node_id,
            method_fqn=signature.fqn,
            method_version=signature.version,
            backend=signature.execution_backend.value,
            params={"poverty_line": None},
            reads_slots=["baseline", "scenario"],
            writes_slots=["result"],
        )
        selected_method_plan = ExecutionPlan(
            plan_id=f"{case_id}_plan",
            method_dag=[method_node],
        )
        plan_payload_ref = _put_selected(
            store,
            selected_method_plan,
            kind="scientist.execution_plan",
            schema_name="polisyos.core.ExecutionPlan",
            schema_version="1.0",
            inputs=[input_ref_from_artifact_ref(trinity_ref, role="policy_candidate")],
        )
        selected_plan_ref = ExecutionPlanRef.model_validate(
            plan_payload_ref.model_dump(mode="python")
        )
        result = compile_foundry(
            store,
            CompileRequest(
                schema_version="1.2",
                policy_ref=trinity_ref,
                method_execution_plan_ref=selected_plan_ref,
                registry_bundle_ref=selected_registry.bundle_ref,
                method_metric_bindings=[
                    MethodMetricBindingRequest(
                        objective_id=objective_id,
                        node_id=method_node_id,
                        output_slot_id="result",
                    )
                ],
                return_selected_profile=True,
            ),
        )
        assert result.ok, result.notes
        assert result.exec_plan_ref is not None
        graph_ref = next(item.ref for item in result.derived_refs if item.role == "program_graph")
        lowered_ref = next(item.ref for item in result.derived_refs if item.role == "lowered_ir")
        binding_ref = next(
            item.ref for item in result.derived_refs if item.role == "method_metric_binding_set"
        )
        graph = validate_core_model_json_artifact(ProgramGraph, store, graph_ref)
        lowered_registry_edges = [
            edge
            for edge in store.get_manifest(lowered_ref).inputs
            if edge.role == "registry_bundle"
        ]
        assert len(lowered_registry_edges) == 1
        assert lowered_registry_edges[0].artifact_id == selected_registry.bundle_ref.artifact_id
        assert (
            lowered_registry_edges[0].manifest_profile_sha256
            == selected_registry.bundle_ref.manifest_profile_sha256
        )
        method_transfer_edges = [
            edge
            for edge in graph.edges
            if edge.dst == method_node_id and edge.src != method_node_id
        ]
        if selected_registry is wrong_slot_registry:
            assert not method_transfer_edges
        elif rate is not None:
            assert any(edge.src == f"{case_id}_tax" for edge in method_transfer_edges)
        else:
            assert not method_transfer_edges

        if case_id == "v5_tax_quarter":
            stale_plan = selected_plan_ref.model_copy(update={"manifest_profile_sha256": None})
            with pytest.raises(
                ValidationError,
                match="method_execution_plan_ref_must_be_exact_selected_execution_plan",
            ):
                CompileRequest(
                    schema_version="1.2",
                    policy_ref=trinity_ref,
                    method_execution_plan_ref=stale_plan,
                    registry_bundle_ref=selected_registry.bundle_ref,
                    method_metric_bindings=[
                        MethodMetricBindingRequest(
                            objective_id=objective_id,
                            node_id=method_node_id,
                            output_slot_id="result",
                        )
                    ],
                    return_selected_profile=True,
                )

        if case_id == "v5_tax_quarter":
            # compile_trinity forces selected LoweredIR output when method inputs
            # are present. Exercise the distinct unsafe registry-lineage case by
            # keeping the same bundle artifact and omitting only its profile.
            profileless_registry_ref = selected_registry.bundle_ref.model_copy(
                update={"manifest_profile_sha256": None}
            )
            assert profileless_registry_ref.artifact_id == selected_registry.bundle_ref.artifact_id
            assert profileless_registry_ref.manifest_profile_sha256 is None
            profileless_compile = compile_foundry(
                store,
                CompileRequest(
                    schema_version="1.2",
                    policy_ref=trinity_ref,
                    method_execution_plan_ref=selected_plan_ref,
                    registry_bundle_ref=profileless_registry_ref,
                    method_metric_bindings=[
                        MethodMetricBindingRequest(
                            objective_id=objective_id,
                            node_id=method_node_id,
                            output_slot_id="result",
                        )
                    ],
                    return_selected_profile=False,
                ),
            )
            assert profileless_compile.ok is False
            assert (
                "execution_plan_method_registry_bundle_selected_profile_required_for_intervention_method_transfer"
                in profileless_compile.notes
            )
            profileless_lowered_refs = [
                item.ref for item in profileless_compile.derived_refs if item.role == "lowered_ir"
            ]
            assert len(profileless_lowered_refs) == 1
            profileless_lowered_ref = profileless_lowered_refs[0]
            # The compiler upgraded the LoweredIR ref; the refused edge itself
            # remains unprofiled in the selected LoweredIR manifest.
            assert profileless_lowered_ref.manifest_profile_sha256 is not None
            profileless_lowered_manifest = store.get_manifest(profileless_lowered_ref)
            profileless_registry_edges = [
                edge
                for edge in profileless_lowered_manifest.inputs
                if edge.role == "registry_bundle"
            ]
            assert len(profileless_registry_edges) == 1
            assert profileless_registry_edges[0].artifact_id == profileless_registry_ref.artifact_id
            assert profileless_registry_edges[0].manifest_profile_sha256 is None

        bindings_result = make_bindings(selected_registry, scenario_source=scenario_source)
        execute_result = execute_foundry(
            store,
            ExecuteRequest(
                exec_plan_ref=result.exec_plan_ref,
                input_bindings_ref=bindings_result.input_bindings_ref,
                registry_bundle_ref=selected_registry.bundle_ref,
                exec_config=FoundryExecConfig(seed=41, mode="dev", capture_env=True),
                return_selected_profile=True,
            ),
        )
        assert execute_result.ok, execute_result.notes
        assert execute_result.simulation_result_ref is not None
        assert execute_result.method_execution_bundle_ref is not None
        bundle_payload = validate_core_model_json_artifact(
            MethodExecutionBundle,
            store,
            execute_result.method_execution_bundle_ref,
        )
        occurrence = next(
            item for item in bundle_payload.occurrences if item.node_id == method_node_id
        )
        method_dispatch = occurrence.dispatch
        assert method_dispatch is not None and method_dispatch.outcome == "succeeded"
        assert method_dispatch.method_metric_input_capture_status == "captured"
        assert method_dispatch.method_metric_input_capture_ref is not None
        capture = validate_core_model_json_artifact(
            MethodMetricInputCapturePayload,
            store,
            method_dispatch.method_metric_input_capture_ref,
        )
        prestate = validate_core_model_json_artifact(
            StateSnapshot, store, capture.pre_dispatch_state_ref
        )
        with np.load(BytesIO(store.get_bytes(prestate.state_ref)), allow_pickle=False) as blob:
            captured_inputs = {key: np.array(blob[key]) for key in blob.files}
        output_slot = next(item for item in occurrence.output_slots if item.slot_id == "result")
        assert output_slot.output_ref is not None
        method_output = validate_core_model_json_artifact(
            MethodOutputPayload,
            store,
            output_slot.output_ref,
        )
        assert method_output.value_path == ("mean_change",)
        from polisyos.scientist.nodes.builtins.decide.policy_runtime_method_metrics import (
            _MethodMetricSourceTuple,
            prepare_method_metric_projection_admission,
        )

        admission = prepare_method_metric_projection_admission(
            store,
            source_tuple=_MethodMetricSourceTuple(
                job_id=f"{case_id}_job",
                run_id=case_id,
                attempt=1,
                method_result_ref=None,
                simulation_result_ref=execute_result.simulation_result_ref,
                method_execution_bundle_ref=execute_result.method_execution_bundle_ref,
                method_metric_binding_set_ref=binding_ref,
            ),
        )
        assert admission.status == "verified", admission.limitations
        assert admission.admission is not None
        assert admission.admission.source_candidate_ref == candidate_ref
        return (
            method_output.value,
            captured_inputs,
            result.exec_plan_ref,
            bindings_result.input_bindings_ref,
        )

    tax_quarter, quarter_inputs, quarter_exec_plan_ref, quarter_bindings_ref = run_case(
        case_id="v5_tax_quarter",
        selected_registry=registry,
        scenario_source="agents.income",
        rate=Decimal("0.25"),
    )
    tax_half, half_inputs, _, _ = run_case(
        case_id="v5_tax_half",
        selected_registry=registry,
        scenario_source="agents.income",
        rate=Decimal("0.50"),
    )
    removed, removed_inputs, _, _ = run_case(
        case_id="v5_removed_mechanism",
        selected_registry=registry,
        scenario_source="agents.income",
        rate=None,
    )
    wrong_slot, wrong_slot_inputs, _, _ = run_case(
        case_id="v5_wrong_slot_alias",
        selected_registry=wrong_slot_registry,
        scenario_source="agents.savings",
        rate=Decimal("0.25"),
    )

    np.testing.assert_allclose(quarter_inputs["baseline"], [100.0, 200.0])
    np.testing.assert_allclose(quarter_inputs["scenario"], [75.0, 150.0])
    np.testing.assert_allclose(half_inputs["scenario"], [50.0, 100.0])
    np.testing.assert_allclose(removed_inputs["scenario"], [100.0, 200.0])
    np.testing.assert_allclose(wrong_slot_inputs["scenario"], [100.0, 200.0])
    assert tax_quarter == pytest.approx(-37.5)
    assert tax_half == pytest.approx(-75.0)
    assert removed == pytest.approx(0.0)
    assert wrong_slot == pytest.approx(0.0)

    wrong_profile = registry.bundle_ref.model_copy(update={"manifest_profile_sha256": None})
    with pytest.raises(ValueError, match=r"^execution_source_selected_profile_missing$"):
        execute_foundry(
            store,
            ExecuteRequest(
                exec_plan_ref=quarter_exec_plan_ref,
                input_bindings_ref=quarter_bindings_ref,
                registry_bundle_ref=wrong_profile,
                exec_config=FoundryExecConfig(seed=41, mode="dev", capture_env=True),
                return_selected_profile=True,
            ),
        )
