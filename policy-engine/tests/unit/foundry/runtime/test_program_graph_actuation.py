"""Actual mixed Foundry execution under explicit candidate policy selection."""

from __future__ import annotations

import stat
from decimal import Decimal
from io import BytesIO

import numpy as np
import pytest

from polisyos.core.artifacts import (
    ArtifactRef,
    input_ref_from_artifact_ref,
    validate_core_model_json_artifact,
)
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.core.contracts.foundry import (
    ExecPlan,
    ExecuteRequest,
    FoundryExecConfig,
    LoweredIR,
    LoweredIRRef,
    ProgramGraph,
    ProgramGraphRef,
)
from polisyos.core.registry import build_default_registry_bundle, load_registry_bundle_content
from polisyos.foundry.data_plane.bindings import load_input_bindings
from polisyos.foundry.execute._internal.graph import (
    prepare_program_graph_mechanism_calls,
    prepare_program_graph_method_calls,
)
from polisyos.foundry.execute.actuation import (
    create_program_graph_actuation_selection,
    resolve_program_graph_actuation,
)
from polisyos.foundry.execute.api import admit_execution_source
from polisyos.foundry.execute.api import execute as execute_foundry
from polisyos.foundry.execute.executor import load_state_snapshot
from polisyos.foundry.methods.catalog.policy.accounting import PeriodFlowToStock
from tests._helpers.derived_selected_method_input import materialize_selected_method_input_case
from tests._helpers.selected_method_input import (
    prepare_selected_method_input_case,
    selected_method_tax_subsidy_policy,
)
from tests.unit.foundry.runtime.test_execute_feedback_selected_method_input import (
    _feedback_config_ref,
)
from tests.unit.foundry.runtime.test_selected_method_inputs import _fresh_process_read


def _selected_request(case, materialized, actuation_ref):
    return ExecuteRequest(
        schema_version="1.1",
        exec_plan_ref=case.exec_plan_ref,
        input_bindings_ref=materialized.input_bindings_ref,
        registry_bundle_ref=case.registry_bundle_ref,
        actuation_selection_ref=actuation_ref,
        exec_config=FoundryExecConfig(seed=23),
        return_selected_profile=True,
    )


def _close_store(store):
    close = getattr(store, "close", None)
    if callable(close):
        close()


def test_selected_actuation_controls_real_mixed_execution_and_fresh_admission(tmp_path):
    incomes = (2**26, 2**27)
    subsidy_total = sum(incomes) // 8
    case, metadata = prepare_selected_method_input_case(
        tmp_path,
        method_class=PeriodFlowToStock,
        policy_spec=selected_method_tax_subsidy_policy(),
        income_values=incomes,
    )
    try:
        baseline_ref = create_program_graph_actuation_selection(
            case.store,
            program_ref=case.program_graph_ref,
            exec_plan_ref=case.exec_plan_ref,
            selected_intervention_ids=(),
        )
        baseline_resolution = resolve_program_graph_actuation(
            case.store,
            program_ref=case.program_graph_ref,
            exec_plan_ref=case.exec_plan_ref,
            actuation_selection_ref=baseline_ref,
        )
        groups = baseline_resolution.binding_groups
        assert groups
        selected_ids = tuple(
            sorted(
                {intervention_id for group in groups for intervention_id in group.intervention_ids}
            )
        )
        assert selected_ids

        treatment_ref = create_program_graph_actuation_selection(
            case.store,
            program_ref=case.program_graph_ref,
            exec_plan_ref=case.exec_plan_ref,
            selected_intervention_ids=selected_ids,
        )
        treatment_resolution = resolve_program_graph_actuation(
            case.store,
            program_ref=case.program_graph_ref,
            exec_plan_ref=case.exec_plan_ref,
            actuation_selection_ref=treatment_ref,
        )
        assert treatment_resolution.binding_groups == groups
        apply_node_ids = {group.apply_node_id for group in groups}
        assert set(baseline_resolution.inactive_apply_node_ids) == apply_node_ids
        assert baseline_resolution.active_apply_node_ids == ()
        assert set(treatment_resolution.active_apply_node_ids) == apply_node_ids
        assert treatment_resolution.inactive_apply_node_ids == ()

        legacy_resolution = resolve_program_graph_actuation(
            case.store,
            program_ref=case.program_graph_ref,
            exec_plan_ref=case.exec_plan_ref,
            actuation_selection_ref=None,
        )
        assert legacy_resolution.selected_intervention_ids is None
        assert set(legacy_resolution.active_apply_node_ids) == apply_node_ids

        registry = load_registry_bundle_content(case.store, case.registry_bundle_ref)
        base_state = load_state_snapshot(case.store, snapshot_ref=case.bound_state_snapshot_ref)
        materialized = materialize_selected_method_input_case(
            case,
            metadata,
            ratio_value=Decimal("-0.03"),
            denominator_value=Decimal("200000000000"),
        )
        bindings = load_input_bindings(case.store, materialized.input_bindings_ref)
        assert bindings.schema_version == "1.4"
        (selected_flow,) = (
            item for item in bindings.selected_method_inputs if item.slot_id == "period_flow"
        )
        selected_flow_value = np.load(
            BytesIO(case.store.get_bytes(selected_flow.npy_value_ref)), allow_pickle=False
        )
        assert selected_flow_value.dtype == np.dtype(np.float64)
        assert selected_flow_value.shape == ()
        assert float(selected_flow_value) == -6_000_000_000.0

        results = []
        prepared_methods = []
        for label, actuation_ref, resolution in (
            ("baseline", baseline_ref, baseline_resolution),
            ("treatment", treatment_ref, treatment_resolution),
        ):
            request = _selected_request(case, materialized, actuation_ref)
            method_calls = prepare_program_graph_method_calls(
                case.store,
                program_ref=case.program_graph_ref,
                exec_plan_ref=case.exec_plan_ref,
                registry_bundle_ref=case.registry_bundle_ref,
                input_bindings_ref=materialized.input_bindings_ref,
                base_state=base_state,
                steps=(0,),
                seed=request.exec_config.seed,
                actuation_selection_ref=actuation_ref,
            )
            (method_call,) = method_calls
            assert float(method_call.input_values["period_flow"]) == -6_000_000_000.0
            prepared_methods.append(method_call)

            mechanism_calls = prepare_program_graph_mechanism_calls(
                case.store,
                program_ref=case.program_graph_ref,
                exec_plan_ref=case.exec_plan_ref,
                base_state=base_state,
                mechanism_registry=registry.mechanism_registry,
                steps=(0,),
                actuation_selection_ref=actuation_ref,
            )
            assert len(mechanism_calls) == len(resolution.active_apply_node_ids)

            class Observer:
                def __init__(self):
                    self.started = []
                    self.nodes = []
                    self.mechanisms = []
                    self.methods = []
                    self.finished = []

                def graph_started(self, **values):
                    self.started.append(values)

                def graph_finished(self, **values):
                    self.finished.append(("graph", values))

                def node_finished(self, **values):
                    self.nodes.append(values)

                def mechanism_started(self, **values):
                    self.mechanisms.append(values)

                def mechanism_finished(self, **values):
                    self.finished.append(("mechanism", values))

                def method_started(self, **values):
                    self.methods.append(values)

                def method_finished(self, **values):
                    self.finished.append(("method", values))

            observer = Observer()
            executed = execute_foundry(case.store, request, observer=observer)
            assert executed.ok and executed.simulation_result_ref is not None
            assert executed.method_execution_bundle_ref is not None
            assert len(observer.methods) == 1
            assert len(observer.mechanisms) == len(resolution.active_apply_node_ids)
            assert observer.methods[0]["prepared_call"].node_id == method_call.node_id
            assert observer.methods[0]["prepared_call"].seed == method_call.seed
            assert observer.methods[0]["prepared_call"].key_words == method_call.key_words
            returned_methods = [
                values for family, values in observer.finished if family == "method"
            ]
            finished_graphs = [values for family, values in observer.finished if family == "graph"]
            assert len(returned_methods) == 1
            assert returned_methods[0]["status"] == "returned"
            assert len(finished_graphs) == 1
            assert observer.started[0]["seed"] == 23
            assert [row["node_id"] for row in observer.nodes] == [
                node_id for node_id, _mode in resolution.node_execution
            ]
            assert [row["status"] for row in observer.nodes] == [
                "skipped" if mode == "skip" else "succeeded"
                for _node_id, mode in resolution.node_execution
            ]

            if label == "baseline":
                assert observer.mechanisms == []
            else:
                assert len(mechanism_calls) == 1
                plan_index, node_id, step, prepared_call = mechanism_calls[0]
                actual = observer.mechanisms[0]
                assert (actual["plan_index"], actual["node_id"], actual["step"]) == (
                    plan_index,
                    node_id,
                    step,
                )
                assert actual["selected_call"].__func__ is prepared_call.__func__
                assert (
                    float(actual["selected_call"].__self__.rate)
                    == float(prepared_call.__self__.rate)
                    == 0.125
                )
                np.testing.assert_array_equal(
                    np.asarray(actual["selected_call"].__self__.target_sector_mask),
                    np.asarray(prepared_call.__self__.target_sector_mask),
                )

            fresh = FileSystemCAS(case.store_root)
            try:
                admitted = admit_execution_source(fresh, executed.simulation_result_ref)
                assert admitted.basis.actuation_selection_ref == actuation_ref
                assert admitted.basis.request.actuation_selection_ref == actuation_ref
                cold_resolution = resolve_program_graph_actuation(
                    fresh,
                    program_ref=admitted.basis.program_graph_ref,
                    exec_plan_ref=admitted.basis.exec_plan_ref,
                    actuation_selection_ref=admitted.basis.actuation_selection_ref,
                )
                assert (
                    cold_resolution.selected_intervention_ids
                    == resolution.selected_intervention_ids
                )
                assert cold_resolution.node_execution == resolution.node_execution
                assert admitted.simulation_result.state_snapshot_ref is not None
                state = load_state_snapshot(
                    fresh, snapshot_ref=admitted.simulation_result.state_snapshot_ref
                )
                mean_income = float(np.mean(np.asarray(state.agents.income, dtype=np.float64)))
                stock = float(state.government_balance)
                results.append(
                    (
                        executed.simulation_result_ref,
                        actuation_ref,
                        stock,
                        mean_income,
                    )
                )
            finally:
                _close_store(fresh)

            cold_read = _fresh_process_read(case, executed.simulation_result_ref)
            assert cold_read["stock"] == stock
            assert cold_read["occurrences"] == 1
            assert cold_read["value_sha256"] == selected_flow.value_sha256

        baseline_result, _baseline_selection, baseline_stock, baseline_mean_income = results[0]
        treatment_result, _treatment_selection, treatment_stock, treatment_mean_income = results[1]
        assert baseline_stock == 4_000_000_000.0
        assert treatment_stock == 3_974_834_176.0
        assert baseline_mean_income == 100_663_296.0
        assert treatment_mean_income == 113_246_208.0
        assert treatment_stock - baseline_stock == -float(subsidy_total)
        assert treatment_mean_income - baseline_mean_income == 12_582_912.0
        assert treatment_result != baseline_result
        assert prepared_methods[0].seed == prepared_methods[1].seed
        assert prepared_methods[0].key_words == prepared_methods[1].key_words

        with pytest.raises(ValueError, match="program_graph_actuation_unknown_intervention"):
            create_program_graph_actuation_selection(
                case.store,
                program_ref=case.program_graph_ref,
                exec_plan_ref=case.exec_plan_ref,
                selected_intervention_ids=tuple(sorted((*selected_ids, "foreign.intervention"))),
            )

        unprofiled_ref = baseline_ref.model_copy(update={"manifest_profile_sha256": None})
        with pytest.raises(ValueError, match="program_graph_actuation_selected_source_required"):
            resolve_program_graph_actuation(
                case.store,
                program_ref=case.program_graph_ref,
                exec_plan_ref=case.exec_plan_ref,
                actuation_selection_ref=unprofiled_ref,
            )

        foreign_case, _ = prepare_selected_method_input_case(
            tmp_path / "foreign",
            method_class=PeriodFlowToStock,
            store=case.store,
        )
        try:
            foreign_ref = create_program_graph_actuation_selection(
                case.store,
                program_ref=foreign_case.program_graph_ref,
                exec_plan_ref=foreign_case.exec_plan_ref,
                selected_intervention_ids=(),
            )
            assert foreign_case.program_graph_ref != case.program_graph_ref
            with pytest.raises(
                ValueError,
                match="program_graph_actuation_selection_source_mismatch",
            ):
                resolve_program_graph_actuation(
                    case.store,
                    program_ref=case.program_graph_ref,
                    exec_plan_ref=case.exec_plan_ref,
                    actuation_selection_ref=foreign_ref,
                )
        finally:
            foreign_case.close()

        # The current fixture has a singleton binding group; the compiler-level
        # actuation suite owns the multi-intervention partial-group control.
        assert all(len(group.intervention_ids) == 1 for group in groups)

        # A fresh reader must refuse the actual selected result if its selector
        # payload disappears, then admit the same result after exact restoration.
        selection_blob, _ = case.store._paths(baseline_ref.artifact_id)
        original_blob = selection_blob.read_bytes()
        original_mode = stat.S_IMODE(selection_blob.stat().st_mode)
        selection_blob.unlink()
        missing_reader = None
        try:
            missing_reader = FileSystemCAS(case.store_root)
            with pytest.raises(
                FileNotFoundError,
                match=str(baseline_ref.artifact_id).removeprefix("sha256:"),
            ):
                admit_execution_source(missing_reader, baseline_result)
        finally:
            if missing_reader is not None:
                _close_store(missing_reader)
            selection_blob.write_bytes(original_blob)
            selection_blob.chmod(original_mode)

        restored_reader = FileSystemCAS(case.store_root)
        try:
            restored = admit_execution_source(restored_reader, baseline_result)
            assert restored.basis.actuation_selection_ref == baseline_ref
            assert restored.simulation_result_ref == baseline_result
        finally:
            _close_store(restored_reader)
    finally:
        case.close()


def test_execute_revalidates_actuation_request_profile_before_feedback_or_dispatch(tmp_path):
    case, _metadata = prepare_selected_method_input_case(
        tmp_path,
        method_class=PeriodFlowToStock,
        policy_spec=selected_method_tax_subsidy_policy(),
        income_values=(2**26, 2**27),
    )
    try:
        baseline_ref = create_program_graph_actuation_selection(
            case.store,
            program_ref=case.program_graph_ref,
            exec_plan_ref=case.exec_plan_ref,
            selected_intervention_ids=(),
        )
        request = ExecuteRequest(
            schema_version="1.1",
            exec_plan_ref=case.exec_plan_ref,
            input_bindings_ref=case.input_bindings_ref,
            registry_bundle_ref=case.registry_bundle_ref,
            actuation_selection_ref=baseline_ref,
            exec_config=FoundryExecConfig(seed=23),
            return_selected_profile=True,
        )
        request.validate_actuation_profile()
        feedback_ref = _feedback_config_ref(case.store, max_iter=1)

        class Observer:
            def __init__(self):
                self.events = []

            def graph_started(self, **_values):
                self.events.append("graph_started")

            def graph_finished(self, **_values):
                self.events.append("graph_finished")

            def node_finished(self, **_values):
                self.events.append("node_finished")

            def mechanism_started(self, **_values):
                self.events.append("mechanism_started")

            def mechanism_finished(self, **_values):
                self.events.append("mechanism_finished")

            def method_started(self, **_values):
                self.events.append("method_started")

            def method_finished(self, **_values):
                self.events.append("method_finished")

        incompatible_requests = (
            (
                request.model_copy(update={"feedback_config_ref": feedback_ref}),
                "program_graph_actuation_feedback_profile_not_established",
            ),
            (
                request.model_copy(update={"schema_version": "1.0"}),
                "execute_request_actuation_selection_schema_version_mismatch",
            ),
            (
                request.model_copy(update={"actuation_selection_ref": None}),
                "execute_request_actuation_selection_schema_version_mismatch",
            ),
        )
        for incompatible, reason in incompatible_requests:
            observer = Observer()
            with pytest.raises(ValueError, match=f"^{reason}$"):
                execute_foundry(case.store, incompatible, observer=observer)
            assert observer.events == []

        legacy_request = request.model_copy(
            update={"schema_version": "1.0", "actuation_selection_ref": None}
        )
        legacy_request.validate_actuation_profile()
        unknown_profile_request = request.model_copy(
            update={"schema_version": "9.7", "actuation_selection_ref": None}
        )
        unknown_profile_request.validate_actuation_profile()
    finally:
        case.close()


def test_actuation_reconciles_the_exact_lowered_and_graph_registry_sources(tmp_path):
    case, _metadata = prepare_selected_method_input_case(
        tmp_path,
        method_class=PeriodFlowToStock,
        policy_spec=selected_method_tax_subsidy_policy(),
    )
    try:
        graph = validate_core_model_json_artifact(ProgramGraph, case.store, case.program_graph_ref)
        plan = validate_core_model_json_artifact(ExecPlan, case.store, case.exec_plan_ref)
        graph_manifest = case.store.get_manifest(case.program_graph_ref)
        plan_manifest = case.store.get_manifest(case.exec_plan_ref)
        assert graph.lowered_ir_ref is not None
        lowered_manifest = case.store.get_manifest(graph.lowered_ir_ref)
        from polisyos.core.artifacts import load_core_json_artifact

        lowered = LoweredIR.model_validate(
            load_core_json_artifact(case.store, graph.lowered_ir_ref)
        )
        foreign_registry = build_default_registry_bundle(
            case.store, return_selected_profile=True
        ).bundle_ref
        assert foreign_registry.artifact_id != case.registry_bundle_ref.artifact_id
        (registry_edge,) = (
            edge for edge in lowered_manifest.inputs if edge.role == "registry_bundle"
        )
        changed_edges = (
            input_ref_from_artifact_ref(foreign_registry, role="registry_bundle"),
            registry_edge.model_copy(update={"manifest_profile_sha256": None}),
            None,
        )
        for changed_edge in changed_edges:
            lowered_inputs = [
                edge for edge in lowered_manifest.inputs if edge.role != "registry_bundle"
            ]
            if changed_edge is not None:
                lowered_inputs.append(changed_edge)
            bad_lowered_ref = case.store.put_json(
                lowered,
                PutOptions(
                    kind=lowered_manifest.kind,
                    media_type=lowered_manifest.media_type,
                    schema=lowered_manifest.artifact_schema,
                    inputs=lowered_inputs,
                ),
                canon_spec=CanonSpec(forbid_floats=False),
                return_selected_profile=True,
            )
            bad_graph = graph.model_copy(
                update={
                    "lowered_ir_ref": LoweredIRRef.model_validate(
                        bad_lowered_ref.model_dump(mode="python")
                    )
                }
            )
            bad_graph_ref = case.store.put_json(
                bad_graph.to_artifact_payload(),
                PutOptions(
                    kind=ProgramGraph.ARTIFACT_KIND,
                    media_type=ProgramGraph.ARTIFACT_MEDIA_TYPE,
                    schema=graph_manifest.artifact_schema,
                    inputs=[
                        input_ref_from_artifact_ref(bad_lowered_ref, role="lowered_ir")
                        if edge.role == "lowered_ir"
                        else edge
                        for edge in graph_manifest.inputs
                    ],
                ),
                return_selected_profile=True,
            )
            bad_plan = plan.model_copy(
                update={
                    "program_ref": ProgramGraphRef.model_validate(
                        bad_graph_ref.model_dump(mode="python")
                    )
                }
            )
            bad_plan_ref = case.store.put_json(
                bad_plan,
                PutOptions(
                    kind=ExecPlan.ARTIFACT_KIND,
                    media_type=ExecPlan.ARTIFACT_MEDIA_TYPE,
                    schema=plan_manifest.artifact_schema,
                    inputs=[
                        input_ref_from_artifact_ref(bad_graph_ref, role="program_graph")
                        if edge.role == "program_graph"
                        else edge
                        for edge in plan_manifest.inputs
                    ],
                ),
                return_selected_profile=True,
            )
            # All selected graph/plan/lowered edges agree with their payloads;
            # only the actual compiler registry source is spliced or missing.
            with pytest.raises(
                ValueError, match="^program_graph_actuation_registry_source_mismatch$"
            ):
                create_program_graph_actuation_selection(
                    case.store,
                    program_ref=ArtifactRef.model_validate(bad_graph_ref.model_dump(mode="json")),
                    exec_plan_ref=ArtifactRef.model_validate(bad_plan_ref.model_dump(mode="json")),
                    selected_intervention_ids=(),
                )
    finally:
        case.close()
