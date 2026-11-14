"""Actual candidate input owner, method invocation, patch and fresh-reader route."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from dataclasses import replace
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from typing import ClassVar

import numpy as np
import pytest

from polisyos.core.artifacts import validate_core_model_json_artifact
from polisyos.core.artifacts.manifest import ArtifactRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.contracts.foundry import (
    ExecPlan,
    ExecPlanRef,
    ExecuteRequest,
    LoweredIR,
    LoweredIRRef,
    MethodExecutionBundle,
    ProgramGraph,
    ProgramGraphRef,
    ProgramNode,
    StateDelta,
)
from polisyos.foundry.contracts.state import GlobalState
from polisyos.foundry.data_plane.bindings import load_input_bindings
from polisyos.foundry.execute._internal.graph import (
    execute_program_graph,
    prepare_program_graph_mechanism_calls,
    prepare_program_graph_method_calls,
    read_program_graph_method_input_sources,
)
from polisyos.foundry.execute.api import admit_execution_source
from polisyos.foundry.execute.api import execute as execute_foundry
from polisyos.foundry.execute.executor import load_state_snapshot
from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
from polisyos.foundry.methods.base import MethodMetadata, MethodSignature
from polisyos.foundry.methods.catalog.policy.accounting import PeriodFlowToStock
from polisyos.foundry.methods.exceptions import ProgramNodeValidationError
from polisyos.foundry.methods.registry import MethodRegistry
from polisyos.ir.kernel import (
    DEFAULT_MECHANISM_REGISTRY,
    DEFAULT_MERGE_RULE_REGISTRY,
    DEFAULT_SLOT_REGISTRY,
)
from tests._helpers.program_graph_tax_subsidy_input import (
    prepare_program_graph_tax_subsidy_input_case,
)
from tests._helpers.selected_method_input import (
    prepare_selected_method_input_case,
    selected_method_tax_subsidy_policy,
)


def _independent_value_sha256(value: float) -> str:
    array = np.asarray(value, dtype=np.float64)
    digest = hashlib.sha256()
    digest.update(array.dtype.str.encode("ascii"))
    digest.update(json.dumps(array.shape, separators=(",", ":")).encode("ascii"))
    digest.update(array.tobytes(order="C"))
    return digest.hexdigest()


def _materialize(case, metadata, *, ratio_value=Decimal("-0.03")):
    from tests._helpers.derived_selected_method_input import materialize_selected_method_input_case

    return materialize_selected_method_input_case(case, metadata, ratio_value=ratio_value)


def _request(case, materialized):
    return ExecuteRequest(
        exec_plan_ref=case.exec_plan_ref,
        registry_bundle_ref=case.registry_bundle_ref,
        input_bindings_ref=materialized.input_bindings_ref,
        return_selected_profile=True,
    )


def _close_store(store):
    close = getattr(store, "close", None)
    if callable(close):
        close()


def _fresh_process_read(case, result_ref):
    product_root = Path(__file__).resolve().parents[4]
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(product_root / "src")
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    code = """
import json
import sys
import hashlib
import os
from io import BytesIO
from pathlib import Path
import numpy as np
from polisyos.core.artifacts import validate_core_model_json_artifact
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.contracts.foundry import MethodExecutionBundle, SimulationResultRef
from polisyos.foundry.data_plane.bindings import load_input_bindings
from polisyos.foundry.execute._internal.graph import read_program_graph_method_input_sources
from polisyos.foundry.execute import api as execute_api
from polisyos.foundry.execute.executor import load_state_snapshot
store = FileSystemCAS(sys.argv[1])
ref = SimulationResultRef.model_validate_json(sys.argv[2])
assert Path(execute_api.__file__).resolve().is_relative_to(Path(os.environ["PYTHONPATH"]))
admitted = execute_api.admit_execution_source(store, ref)
state = load_state_snapshot(store, snapshot_ref=admitted.simulation_result.state_snapshot_ref)
bindings = load_input_bindings(store, admitted.basis.input_bindings_ref)
selected_by_slot = {record.slot_id: record for record in bindings.selected_method_inputs}
hashes_by_slot = {}
for selected in selected_by_slot.values():
    value = np.load(BytesIO(store.get_bytes(selected.npy_value_ref)), allow_pickle=False)
    digest = hashlib.sha256()
    digest.update(value.dtype.str.encode("ascii"))
    digest.update(json.dumps(value.shape, separators=(",", ":")).encode("ascii"))
    digest.update(value.tobytes(order="C"))
    hashes_by_slot[selected.slot_id] = digest.hexdigest()
edge = next(item for item in store.get_manifest(ref).inputs if item.role == "method_execution")
bundle_ref = ArtifactRef(artifact_id=edge.artifact_id,
    manifest_profile_sha256=edge.manifest_profile_sha256,
    kind=MethodExecutionBundle.ARTIFACT_KIND, media_type="application/json")
bundle = validate_core_model_json_artifact(MethodExecutionBundle, store, bundle_ref)
occurrences = [item for item in bundle.occurrences if item.node_kind == "method"]
assert occurrences
consumed_selected = set()
for occurrence in occurrences:
    sources = read_program_graph_method_input_sources(store,
        program_ref=admitted.basis.program_graph_ref, node_id=occurrence.node_id,
        signature_input_slot_ids=occurrence.dispatch.signature_input_slot_ids)
    for argument in occurrence.dispatch.input_slot_values:
        source_slot = sources[argument.slot_id]
        if source_slot not in selected_by_slot:
            continue  # state-backed registry input, independently admitted above
        selected = selected_by_slot[source_slot]
        assert argument.value_sha256 == selected.value_sha256 == hashes_by_slot[source_slot]
        consumed_selected.add(source_slot)
assert consumed_selected == set(selected_by_slot)
summary = {"stock": float(state.government_balance), "occurrences": len(occurrences),
           "value_sha256_by_slot": hashes_by_slot}
if len(hashes_by_slot) == 1:
    summary["value_sha256"] = next(iter(hashes_by_slot.values()))
print(json.dumps(summary))
"""
    result = subprocess.run(
        [sys.executable, "-B", "-c", code, str(case.store_root), result_ref.model_dump_json()],
        cwd=product_root,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    assert result.returncode == 0, (result.stdout, result.stderr)
    return json.loads(result.stdout)


def test_prepared_method_call_matches_actual_held_public_execution(tmp_path, monkeypatch):
    calls = []

    class HeldFlow:
        signature = replace(
            PeriodFlowToStock.signature,
            namespace="tests.selected_prepared",
            name="held_flow",
        )
        metadata = PeriodFlowToStock.metadata

        @staticmethod
        def pure_step(state, params):
            calls.append((tuple(state), float(state["period_flow"]), params["__seed__"]))
            return PeriodFlowToStock.pure_step(state, params)

    case, metadata = prepare_selected_method_input_case(tmp_path, method_class=HeldFlow)
    try:
        materialized = _materialize(case, metadata)
        request = _request(case, materialized)
        base_state = load_state_snapshot(case.store, snapshot_ref=case.bound_state_snapshot_ref)
        (predicted,) = prepare_program_graph_method_calls(
            case.store,
            program_ref=case.program_graph_ref,
            exec_plan_ref=case.exec_plan_ref,
            registry_bundle_ref=case.registry_bundle_ref,
            input_bindings_ref=materialized.input_bindings_ref,
            base_state=base_state,
            steps=(0,),
            seed=request.exec_config.seed if request.exec_config is not None else None,
        )
        assert calls == []
        assert predicted.input_slot_sources == {"period_flow": "period_flow"}
        assert predicted.resolved_parameters == {"target_slot": "government.balance"}
        assert predicted.method_abi_digest == HeldFlow.signature.abi_digest()
        assert predicted.rng_state == np.random.default_rng(predicted.seed).bit_generator.state
        observed = []
        held_function = HeldFlow.pure_step

        class Observer:
            def graph_started(self, **_):
                pass

            def graph_finished(self, **_):
                pass

            def node_finished(self, **_):
                pass

            def method_started(self, *, step, plan_index, node_id, prepared_call):
                assert (step, plan_index, node_id) == (
                    predicted.step,
                    predicted.plan_index,
                    predicted.node_id,
                )
                assert prepared_call.selected_call is predicted.selected_call is held_function
                assert prepared_call.seed == predicted.seed
                assert prepared_call.key_words == predicted.key_words
                assert prepared_call.root_seed == predicted.root_seed
                assert prepared_call.rng_state == predicted.rng_state
                assert prepared_call.resolved_parameters == predicted.resolved_parameters
                assert prepared_call.input_slot_sources == predicted.input_slot_sources
                np.testing.assert_array_equal(
                    prepared_call.input_values["period_flow"], predicted.input_values["period_flow"]
                )
                observed.append("started")
                monkeypatch.setattr(
                    HeldFlow,
                    "pure_step",
                    staticmethod(
                        lambda *_: (_ for _ in ()).throw(
                            AssertionError("executor re-read the replaced class slot")
                        )
                    ),
                )
                monkeypatch.setattr(
                    HeldFlow,
                    "dematerialize_output",
                    staticmethod(
                        lambda *_: (_ for _ in ()).throw(
                            AssertionError("executor re-read the replaced output projection")
                        )
                    ),
                    raising=False,
                )
                monkeypatch.setattr(HeldFlow, "strict_output_contract", True, raising=False)

            def method_finished(self, *, status, **_):
                observed.append(status)
                monkeypatch.setattr(HeldFlow, "pure_step", staticmethod(held_function))
                monkeypatch.delattr(HeldFlow, "dematerialize_output", raising=False)
                monkeypatch.delattr(HeldFlow, "strict_output_contract", raising=False)

        result = execute_foundry(case.store, request, observer=Observer())
        assert result.ok and result.simulation_result_ref is not None
        assert observed == ["started", "returned"]
        assert calls == [(("period_flow",), -6_000_000_000.0, predicted.seed)]
        assert result.method_execution_bundle_ref is not None
        bundle = validate_core_model_json_artifact(
            MethodExecutionBundle, case.store, result.method_execution_bundle_ref
        )
        (occurrence,) = (row for row in bundle.occurrences if row.node_kind == "method")
        (argument,) = occurrence.dispatch.input_slot_values
        assert argument.value_sha256 == _independent_value_sha256(-6_000_000_000.0)
        admitted = admit_execution_source(case.store, result.simulation_result_ref)
        state = load_state_snapshot(
            case.store, snapshot_ref=admitted.simulation_result.state_snapshot_ref
        )
        assert float(state.government_balance) == 4_000_000_000.0
    finally:
        _close_store(case.store)


def test_selected_method_input_reaches_actual_patch_and_fresh_reader(tmp_path):
    case, metadata = prepare_selected_method_input_case(tmp_path, method_class=PeriodFlowToStock)
    hashes = []
    try:
        for ratio, expected_delta, expected_stock in (
            (Decimal("-0.03"), -6_000_000_000.0, 4_000_000_000.0),
            (Decimal("0"), 0.0, 10_000_000_000.0),
        ):
            materialized = _materialize(case, metadata, ratio_value=ratio)
            executed = execute_foundry(case.store, _request(case, materialized))
            assert executed.ok and executed.simulation_result_ref is not None
            assert executed.method_execution_bundle_ref is not None
            if ratio == Decimal("-0.03"):
                independent_read = _fresh_process_read(case, executed.simulation_result_ref)
                assert independent_read["stock"] == expected_stock
                assert independent_read["value_sha256"] == _independent_value_sha256(expected_delta)
            fresh = FileSystemCAS(case.store_root)
            try:
                admitted = admit_execution_source(fresh, executed.simulation_result_ref)
                assert admitted.semantic_input_limitation_codes is not None
                assert (
                    "external_empirical_context_not_established"
                    in admitted.semantic_input_limitation_codes
                )
                assert "derivation_uncertainty_not_established" in (
                    admitted.semantic_input_limitation_codes
                )
                state = load_state_snapshot(
                    fresh, snapshot_ref=admitted.simulation_result.state_snapshot_ref
                )
                assert float(state.government_balance) == expected_stock
                delta_edge = next(
                    edge
                    for edge in fresh.get_manifest(executed.simulation_result_ref).inputs
                    if edge.role == "state_delta"
                )
                delta = validate_core_model_json_artifact(
                    StateDelta,
                    fresh,
                    ArtifactRef(
                        artifact_id=delta_edge.artifact_id,
                        manifest_profile_sha256=delta_edge.manifest_profile_sha256,
                        kind=StateDelta.ARTIFACT_KIND,
                        media_type="application/json",
                    ),
                )
                (operation,) = delta.ops
                assert operation.slot_id == "government.balance" and operation.op == "add"
                value = np.load(BytesIO(fresh.get_bytes(operation.value_ref)), allow_pickle=False)
                assert float(value) == expected_delta
                capture = validate_core_model_json_artifact(
                    MethodExecutionBundle, fresh, executed.method_execution_bundle_ref
                )
                (occurrence,) = (item for item in capture.occurrences if item.node_kind == "method")
                assert occurrence.status == "succeeded" and occurrence.dispatch is not None
                (argument,) = occurrence.dispatch.input_slot_values
                assert argument.slot_id == "period_flow" and argument.status == "captured"
                independent = _independent_value_sha256(expected_delta)
                assert argument.value_sha256 == independent
                assert argument.runtime_shape == ()
                assert argument.runtime_dtype == np.dtype(np.float64).str
                bindings = load_input_bindings(fresh, materialized.input_bindings_ref)
                assert bindings.schema_version == "1.4"
                assert bindings.selected_method_inputs is not None
                assert bindings.selected_method_inputs[0].value_sha256 == independent
                hashes.append(independent)
            finally:
                _close_store(fresh)
        assert len(set(hashes)) == 2
    finally:
        case.close()


class _UndeclaredReader:
    signature: ClassVar[MethodSignature] = replace(
        PeriodFlowToStock.signature,
        namespace="tests.selected_input",
        name="undeclared_reader",
        patch_targets=(),
    )
    metadata: ClassVar[MethodMetadata] = PeriodFlowToStock.metadata

    @staticmethod
    def pure_step(state, params):
        # GlobalState has GDP; only the declared ABI map must reach this method.
        return {"result": float(state["period_flow"]) + float(state["gdp"])}


class _UndeclaredWriter:
    signature: ClassVar[MethodSignature] = replace(
        PeriodFlowToStock.signature,
        namespace="tests.selected_input",
        name="undeclared_writer",
        patch_targets=(),
    )
    metadata: ClassVar[MethodMetadata] = PeriodFlowToStock.metadata

    @staticmethod
    def pure_step(state, params):
        return PeriodFlowToStock.pure_step(state, params)


class _VectorPatch:
    signature: ClassVar[MethodSignature] = replace(
        PeriodFlowToStock.signature, namespace="tests.selected_input", name="vector_patch"
    )
    metadata: ClassVar[MethodMetadata] = PeriodFlowToStock.metadata

    @staticmethod
    def pure_step(state, params):
        value = float(state["period_flow"])
        return {
            "result": value,
            "patch_records": {params["target_slot"]: [{"delta": np.asarray([value])}]},
        }


class _MutationAttempt:
    signature: ClassVar[MethodSignature] = replace(
        PeriodFlowToStock.signature,
        namespace="tests.selected_input",
        name="mutation_attempt",
        patch_targets=(),
    )
    metadata: ClassVar[MethodMetadata] = PeriodFlowToStock.metadata

    @staticmethod
    def pure_step(state, params):
        value = state["period_flow"]
        value.setflags(write=True)
        return {"result": float(value)}


@pytest.mark.parametrize(
    ("method_class", "state_writes", "failure_message"),
    [
        (_UndeclaredReader, (), "unavailable lookup"),
        (_UndeclaredWriter, (), "unexpected patch outputs"),
        (_VectorPatch, ("government.balance",), "finite scalar delta"),
        (_MutationAttempt, (), "writeable"),
    ],
)
def test_declared_method_refuses_ambient_reads_and_invalid_effects(
    tmp_path, caplog, method_class, state_writes, failure_message
):
    case, metadata = prepare_selected_method_input_case(
        tmp_path, method_class=method_class, state_writes=state_writes
    )
    try:
        materialized = _materialize(case, metadata)
        result = execute_foundry(case.store, _request(case, materialized))
        assert not result.ok and result.simulation_result_ref is None
        assert result.method_execution_bundle_ref is not None
        bundle = validate_core_model_json_artifact(
            MethodExecutionBundle, case.store, result.method_execution_bundle_ref
        )
        (occurrence,) = (item for item in bundle.occurrences if item.node_kind == "method")
        assert occurrence.status == "failed"
        assert "method_execution_aborted" in result.notes
        assert "state_source:input_bindings_ref" in result.notes
        assert "semantic_input_limitation:method_external_reads_not_observed" in result.notes
        assert "semantic_input_limitation:derivation_uncertainty_not_established" in result.notes
        assert any(failure_message in record.getMessage().lower() for record in caplog.records)
    finally:
        case.close()


def test_old_selected_result_remains_readable_after_live_method_abi_changes(tmp_path):
    case, metadata = prepare_selected_method_input_case(tmp_path, method_class=PeriodFlowToStock)
    registry = MethodRegistry.get_instance()
    try:
        materialized = _materialize(case, metadata)
        request = _request(case, materialized)
        executed = execute_foundry(case.store, request)
        assert executed.ok and executed.simulation_result_ref is not None
        source = next(iter(PeriodFlowToStock.signature.input_slots))

        class ChangedABI(PeriodFlowToStock):
            signature = replace(
                PeriodFlowToStock.signature,
                input_slots=frozenset(
                    (*PeriodFlowToStock.signature.input_slots, replace(source, name="new_input"))
                ),
            )

        registry.register(ChangedABI, override=True)
        with pytest.raises(ValueError):
            execute_foundry(case.store, request)
        fresh = FileSystemCAS(case.store_root)
        try:
            admitted = admit_execution_source(fresh, executed.simulation_result_ref)
            assert admitted.simulation_result_ref == executed.simulation_result_ref
        finally:
            _close_store(fresh)
    finally:
        registry.register(PeriodFlowToStock, override=True)
        case.close()


def test_method_output_map_is_refused_before_legacy_dispatch(tmp_path, monkeypatch):
    store = FileSystemCAS(tmp_path / "cas")
    MethodRegistry.get_instance().register(_UndeclaredReader, override=True)
    anchor = store.put_json(
        {"candidate": "legacy-anchor"},
        PutOptions(kind="ir.trinity_bundle", media_type="application/json"),
        return_selected_profile=True,
    )
    lowered = LoweredIR(ir_ref=anchor, mechanisms=[], constraints=[])
    lowered_ref = store.put_json(
        lowered,
        PutOptions(
            kind="foundry.lowered_ir",
            media_type="application/json",
        ),
        return_selected_profile=True,
    )
    graph = ProgramGraph(
        schema_version="0.3",
        ir_ref=anchor,
        lowered_ir_ref=LoweredIRRef.model_validate(lowered_ref.model_dump()),
        nodes=[
            ProgramNode(
                node_id="mapped-method",
                node_kind="method",
                method_fqn=_UndeclaredReader.signature.fqn,
                method_version=_UndeclaredReader.signature.version,
                inputs=[],
                input_ports={
                    "period_flow": {
                        "source_kind": "method_output",
                        "producer_node_id": "prior-method",
                        "output_slot_id": "result",
                    }
                },
            )
        ],
    )
    graph_ref = store.put_json(
        graph,
        PutOptions(
            kind=ProgramGraph.ARTIFACT_KIND,
            media_type="application/json",
            schema=SchemaInfo(
                name=ProgramGraph.ARTIFACT_SCHEMA_NAME, version=graph.artifact_schema_version
            ),
        ),
        return_selected_profile=True,
    )
    plan = ExecPlan(
        program_ref=ProgramGraphRef.model_validate(graph_ref.model_dump()), order=["mapped-method"]
    )
    plan_ref = store.put_json(
        plan,
        PutOptions(
            kind=ExecPlan.ARTIFACT_KIND,
            media_type="application/json",
            schema=SchemaInfo(
                name=ExecPlan.ARTIFACT_SCHEMA_NAME, version=ExecPlan.ARTIFACT_SCHEMA_VERSION
            ),
        ),
        return_selected_profile=True,
    )
    calls = []

    def forbidden_dispatch(*args, **kwargs):
        calls.append(True)
        raise AssertionError("Mapped wire entered legacy method dispatch")

    monkeypatch.setattr(MethodDispatcher, "dispatch", forbidden_dispatch)
    with pytest.raises(ProgramNodeValidationError) as caught:
        execute_program_graph(
            store,
            program_ref=graph_ref,
            exec_plan_ref=plan_ref,
            base_state=GlobalState.empty(n_agents=1, n_firms=1),
            mechanism_registry=DEFAULT_MECHANISM_REGISTRY,
            slot_registry=DEFAULT_SLOT_REGISTRY,
            merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
        )
    assert caught.value.code == "unsupported_method_output_input_profile"
    assert calls == []


def test_two_mapped_instances_consume_global_input_and_preserve_local_capture(tmp_path):
    case, metadata = prepare_selected_method_input_case(
        tmp_path,
        method_class=PeriodFlowToStock,
        method_input_slot="ledger.flow",
        method_instances=2,
        mapped=True,
    )
    try:
        materialized = _materialize(case, metadata)
        request = _request(case, materialized)
        graph = validate_core_model_json_artifact(ProgramGraph, case.store, case.program_graph_ref)
        assert graph.schema_version == "0.3"
        method_nodes = [node for node in graph.nodes if node.node_kind == "method"]
        assert len(method_nodes) == 2
        assert len({node.method_fqn for node in method_nodes}) == 1
        assert all(node.inputs == ["ledger.flow"] for node in method_nodes)
        base_state = load_state_snapshot(case.store, snapshot_ref=case.bound_state_snapshot_ref)
        prepared = prepare_program_graph_method_calls(
            case.store,
            program_ref=case.program_graph_ref,
            exec_plan_ref=case.exec_plan_ref,
            registry_bundle_ref=case.registry_bundle_ref,
            input_bindings_ref=materialized.input_bindings_ref,
            base_state=base_state,
            steps=(0,),
            seed=request.exec_config.seed,
        )
        assert len(prepared) == 2
        assert all(row.input_slot_sources == {"period_flow": "ledger.flow"} for row in prepared)
        assert all(tuple(row.input_values) == ("period_flow",) for row in prepared)
        result = execute_foundry(case.store, request)
        assert result.ok and result.simulation_result_ref is not None
        assert result.method_execution_bundle_ref is not None
        bundle = validate_core_model_json_artifact(
            MethodExecutionBundle, case.store, result.method_execution_bundle_ref
        )
        occurrences = [row for row in bundle.occurrences if row.node_kind == "method"]
        assert len(occurrences) == 2
        for occurrence in occurrences:
            assert occurrence.status == "succeeded"
            assert occurrence.dispatch.graph_input_ids == ("ledger.flow",)
            assert occurrence.dispatch.signature_input_slot_ids == ("period_flow",)
            (argument,) = occurrence.dispatch.input_slot_values
            assert argument.slot_id == "period_flow"
            assert argument.value_sha256 == _independent_value_sha256(-6_000_000_000.0)
            assert read_program_graph_method_input_sources(
                case.store,
                program_ref=case.program_graph_ref,
                node_id=occurrence.node_id,
                signature_input_slot_ids=occurrence.dispatch.signature_input_slot_ids,
            ) == {"period_flow": "ledger.flow"}
            with pytest.raises(ValueError, match="stored_method_input_source_abi_mismatch"):
                read_program_graph_method_input_sources(
                    case.store,
                    program_ref=case.program_graph_ref,
                    node_id=occurrence.node_id,
                    signature_input_slot_ids=("foreign_local_name",),
                )
        # Reopen actual persisted result, selected NPY and both local argument
        # captures in a separate interpreter, without our fixture registry.
        fresh = _fresh_process_read(case, result.simulation_result_ref)
        assert fresh["stock"] == -2_000_000_000.0
        assert fresh["occurrences"] == 2
        assert fresh["value_sha256"] == _independent_value_sha256(-6_000_000_000.0)
    finally:
        _close_store(case.store)


def test_stored_method_alias_reader_needs_no_current_registry(tmp_path, monkeypatch):
    case, _ = prepare_selected_method_input_case(
        tmp_path,
        method_class=PeriodFlowToStock,
        method_input_slot="ledger.flow",
        method_instances=2,
        mapped=True,
    )
    try:

        def unavailable_registry(*_, **__):
            raise AssertionError("historical map read consulted the current method registry")

        monkeypatch.setattr(MethodRegistry.get_instance(), "get", unavailable_registry)
        sources = read_program_graph_method_input_sources(
            case.store,
            program_ref=case.program_graph_ref,
            node_id="period_flow_node_0",
            signature_input_slot_ids=("period_flow",),
        )
        assert sources == {"period_flow": "ledger.flow"}
        with pytest.raises(TypeError):
            sources["period_flow"] = "foreign.source"
        with pytest.raises(ValueError, match="stored_method_input_source_abi_mismatch"):
            read_program_graph_method_input_sources(
                case.store,
                program_ref=case.program_graph_ref,
                node_id="period_flow_node_0",
                signature_input_slot_ids=("foreign_local",),
            )
    finally:
        _close_store(case.store)


def test_real_mixed_policy_prepares_and_executes_both_call_families(tmp_path):
    incomes = (2**26, 2**27)
    subsidy_total = sum(incomes) // 8
    case, metadata = prepare_selected_method_input_case(
        tmp_path,
        method_class=PeriodFlowToStock,
        policy_spec=selected_method_tax_subsidy_policy(),
        income_values=incomes,
    )
    try:
        from polisyos.core.registry import load_registry_bundle_content

        registry = load_registry_bundle_content(case.store, case.registry_bundle_ref)
        base_state = load_state_snapshot(case.store, snapshot_ref=case.bound_state_snapshot_ref)
        mechanism_calls = prepare_program_graph_mechanism_calls(
            case.store,
            program_ref=case.program_graph_ref,
            exec_plan_ref=case.exec_plan_ref,
            base_state=base_state,
            mechanism_registry=registry.mechanism_registry,
            steps=(0,),
        )
        assert len(mechanism_calls) == 1
        results = []
        for ratio, flow in ((Decimal("-0.03"), -6_000_000_000), (Decimal("0"), 0)):
            materialized = _materialize(case, metadata, ratio_value=ratio)
            request = _request(case, materialized)
            (method_call,) = prepare_program_graph_method_calls(
                case.store,
                program_ref=case.program_graph_ref,
                exec_plan_ref=case.exec_plan_ref,
                registry_bundle_ref=case.registry_bundle_ref,
                input_bindings_ref=materialized.input_bindings_ref,
                base_state=base_state,
                steps=(0,),
                seed=request.exec_config.seed,
            )

            class Observer:
                def __init__(self, expected_method, expected_flow):
                    self.expected_method = expected_method
                    self.expected_flow = expected_flow
                    self.calls = []

                def graph_started(self, **_):
                    pass

                def graph_finished(self, **_):
                    pass

                def node_finished(self, **_):
                    pass

                def mechanism_started(self, *, plan_index, node_id, step, selected_call, **_):
                    expected_index, expected_node, expected_step, prepared_call = mechanism_calls[0]
                    assert (plan_index, node_id, step) == (
                        expected_index,
                        expected_node,
                        expected_step,
                    )
                    assert selected_call.__func__ is prepared_call.__func__
                    assert (
                        float(selected_call.__self__.rate)
                        == float(prepared_call.__self__.rate)
                        == 0.125
                    )
                    np.testing.assert_array_equal(
                        np.asarray(selected_call.__self__.target_sector_mask),
                        np.asarray(prepared_call.__self__.target_sector_mask),
                    )
                    self.calls.append(("mechanism", node_id))

                def mechanism_finished(self, *, status, **_):
                    assert status == "returned"

                def method_started(self, *, plan_index, node_id, step, prepared_call):
                    assert (plan_index, node_id, step) == (
                        self.expected_method.plan_index,
                        self.expected_method.node_id,
                        self.expected_method.step,
                    )
                    assert prepared_call.seed == self.expected_method.seed
                    assert prepared_call.key_words == self.expected_method.key_words
                    assert float(prepared_call.input_values["period_flow"]) == self.expected_flow
                    self.calls.append(("method", node_id))

                def method_finished(self, *, status, **_):
                    assert status == "returned"

            observer = Observer(method_call, flow)
            executed = execute_foundry(case.store, request, observer=observer)
            assert executed.ok and executed.simulation_result_ref is not None
            assert {family for family, _ in observer.calls} == {"method", "mechanism"}
            assert len(observer.calls) == 2
            admitted = admit_execution_source(case.store, executed.simulation_result_ref)
            state = load_state_snapshot(
                case.store, snapshot_ref=admitted.simulation_result.state_snapshot_ref
            )
            np.testing.assert_array_equal(
                np.asarray(state.agents.income),
                np.asarray([value + value // 8 for value in incomes]),
            )
            expected_stock = 10_000_000_000 - subsidy_total + flow
            assert float(state.government_balance) == expected_stock
            results.append(float(state.government_balance))
        assert results[1] - results[0] == 6_000_000_000
    finally:
        _close_store(case.store)


def test_mixed_dynamic_key_profile_refuses_before_any_numerical_call(tmp_path):
    case, metadata = prepare_selected_method_input_case(
        tmp_path,
        method_class=PeriodFlowToStock,
        policy_spec=selected_method_tax_subsidy_policy(),
        income_values=(2**26, 2**27),
    )
    try:
        plan = validate_core_model_json_artifact(ExecPlan, case.store, case.exec_plan_ref)
        dynamic = plan.model_copy(
            update={"notes": [note for note in plan.notes if not note.startswith("randomization:")]}
        )
        plan_ref = case.store.put_json(
            dynamic,
            PutOptions(
                kind=ExecPlan.ARTIFACT_KIND,
                media_type=ExecPlan.ARTIFACT_MEDIA_TYPE,
                schema=SchemaInfo(
                    name=ExecPlan.ARTIFACT_SCHEMA_NAME, version=ExecPlan.ARTIFACT_SCHEMA_VERSION
                ),
                inputs=list(case.store.get_manifest(case.exec_plan_ref).inputs),
            ),
            return_selected_profile=True,
        )
        dynamic_case = replace(
            case, exec_plan_ref=ExecPlanRef.model_validate(plan_ref.model_dump(mode="python"))
        )
        materialized = _materialize(dynamic_case, metadata)
        observed = []

        class Observer:
            def graph_started(self, **_):
                observed.append("graph")

            def mechanism_started(self, **_):
                observed.append("mechanism")

            def method_started(self, **_):
                observed.append("method")

        with pytest.raises(ValueError, match="program_graph_mixed_treasury_profile_required"):
            execute_foundry(case.store, _request(dynamic_case, materialized), observer=Observer())
        assert observed == []
    finally:
        _close_store(case.store)


def test_mixed_preparation_component_refuses_future_state_without_execution(tmp_path, monkeypatch):
    flow_slot = next(iter(PeriodFlowToStock.signature.input_slots))

    class FutureStateMethod:
        signature = replace(
            PeriodFlowToStock.signature,
            namespace="tests.selected_mixed",
            name="future_state",
            input_slots=PeriodFlowToStock.signature.input_slots
            | frozenset(
                {
                    replace(
                        flow_slot,
                        name="government.balance",
                        description="Current accumulated stock.",
                    )
                }
            ),
        )
        metadata = PeriodFlowToStock.metadata

        @staticmethod
        def pure_step(state, params):
            raise AssertionError("method with an unknown future input was numerically executed")

    case, metadata = prepare_selected_method_input_case(
        tmp_path,
        method_class=FutureStateMethod,
        policy_spec=selected_method_tax_subsidy_policy(),
        income_values=(2**26, 2**27),
    )
    try:
        from graphlib import TopologicalSorter

        plan = validate_core_model_json_artifact(ExecPlan, case.store, case.exec_plan_ref)
        graph = validate_core_model_json_artifact(ProgramGraph, case.store, case.program_graph_ref)
        method_ids = {node.node_id for node in graph.nodes if node.node_kind == "method"}
        mechanism_ids = {
            node.node_id
            for node in graph.nodes
            if node.node_kind == "op"
            and node.op is not None
            and node.op.op_kind == "apply_mechanism"
        }
        order = TopologicalSorter()
        for node in graph.nodes:
            order.add(node.node_id)
        for edge in graph.edges:
            order.add(edge.dst, edge.src)
        # Preserve every actual graph edge (including method→final merge),
        # choosing the valid order with the mechanism before the state reader.
        for method_id in method_ids:
            order.add(method_id, *mechanism_ids)
        reordered = plan.model_copy(update={"order": list(order.static_order())})
        plan_ref = case.store.put_json(
            reordered,
            PutOptions(
                kind=ExecPlan.ARTIFACT_KIND,
                media_type=ExecPlan.ARTIFACT_MEDIA_TYPE,
                schema=SchemaInfo(
                    name=ExecPlan.ARTIFACT_SCHEMA_NAME, version=ExecPlan.ARTIFACT_SCHEMA_VERSION
                ),
                inputs=list(case.store.get_manifest(case.exec_plan_ref).inputs),
            ),
            return_selected_profile=True,
        )
        # Component scope: this order is topological but differs from the public
        # preflight's canonical order. Do not present it as an admitted runtime.
        from polisyos.core.registry import load_registry_bundle_content
        from polisyos.foundry.execute._internal.graph import (
            _program_graph_call_inventory,
            _require_preparable_method_inputs,
        )
        from polisyos.foundry.execute.mechanisms.fiscal import TaxSubsidy

        selected_plan_ref = ExecPlanRef.model_validate(plan_ref.model_dump(mode="python"))
        graph = validate_core_model_json_artifact(ProgramGraph, case.store, case.program_graph_ref)
        selected_plan = validate_core_model_json_artifact(ExecPlan, case.store, selected_plan_ref)
        positions = {node_id: index for index, node_id in enumerate(selected_plan.order)}
        assert all(positions[edge.src] < positions[edge.dst] for edge in graph.edges)
        registry = load_registry_bundle_content(case.store, case.registry_bundle_ref)
        observed = []

        def forbidden_numeric_call(*_, **__):
            observed.append("mechanism")
            raise AssertionError("preparation executed an upstream numerical mechanism")

        monkeypatch.setattr(TaxSubsidy, "emit_patches", forbidden_numeric_call)
        inventory = _program_graph_call_inventory(
            case.store,
            program_ref=case.program_graph_ref,
            exec_plan_ref=selected_plan_ref,
            graph=graph,
            plan=selected_plan,
            mechanism_registry=registry.mechanism_registry,
            steps=(0,),
        )
        with pytest.raises(ValueError, match="program_graph_method_future_state_not_established"):
            _require_preparable_method_inputs(
                inventory, slot_registry=registry.slot_registry, step=0
            )
        assert observed == []
    finally:
        _close_store(case.store)


def test_legacy_pure_mechanism_factory_and_public_execution_are_preserved(tmp_path):
    case = prepare_program_graph_tax_subsidy_input_case(tmp_path, opening_balance_usd=1000)
    try:
        from polisyos.core.registry import load_registry_bundle_content

        registry = load_registry_bundle_content(case.store, case.registry_bundle_ref)
        base_state = load_state_snapshot(case.store, snapshot_ref=case.bound_state_snapshot_ref)
        prepared = prepare_program_graph_mechanism_calls(
            case.store,
            program_ref=case.program_graph_ref,
            exec_plan_ref=case.exec_plan_ref,
            base_state=base_state,
            mechanism_registry=registry.mechanism_registry,
            steps=(0,),
        )
        assert len(prepared) == 1 and len(prepared[0]) == 4
        executed = execute_foundry(case.store, _request(case, case))
        assert executed.ok and executed.simulation_result_ref is not None
        admitted = admit_execution_source(case.store, executed.simulation_result_ref)
        state = load_state_snapshot(
            case.store, snapshot_ref=admitted.simulation_result.state_snapshot_ref
        )
        np.testing.assert_array_equal(np.asarray(state.agents.income), np.asarray([112.5, 225]))
        assert float(state.government_balance) == 962.5
    finally:
        case.close()
