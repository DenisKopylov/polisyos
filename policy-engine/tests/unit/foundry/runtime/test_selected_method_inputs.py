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
from polisyos.foundry.execute._internal.graph import execute_program_graph
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
from tests._helpers.selected_method_input import prepare_selected_method_input_case


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
from polisyos.foundry.execute import api as execute_api
from polisyos.foundry.execute.executor import load_state_snapshot
store = FileSystemCAS(sys.argv[1])
ref = SimulationResultRef.model_validate_json(sys.argv[2])
assert Path(execute_api.__file__).resolve().is_relative_to(Path(os.environ["PYTHONPATH"]))
admitted = execute_api.admit_execution_source(store, ref)
state = load_state_snapshot(store, snapshot_ref=admitted.simulation_result.state_snapshot_ref)
bindings = load_input_bindings(store, admitted.basis.input_bindings_ref)
(selected,) = bindings.selected_method_inputs
value = np.load(BytesIO(store.get_bytes(selected.npy_value_ref)), allow_pickle=False)
digest = hashlib.sha256()
digest.update(value.dtype.str.encode("ascii"))
digest.update(json.dumps(value.shape, separators=(",", ":")).encode("ascii"))
digest.update(value.tobytes(order="C"))
value_sha256 = digest.hexdigest()
edge = next(item for item in store.get_manifest(ref).inputs if item.role == "method_execution")
bundle_ref = ArtifactRef(artifact_id=edge.artifact_id,
    manifest_profile_sha256=edge.manifest_profile_sha256,
    kind=MethodExecutionBundle.ARTIFACT_KIND, media_type="application/json")
bundle = validate_core_model_json_artifact(MethodExecutionBundle, store, bundle_ref)
(occurrence,) = (item for item in bundle.occurrences if item.node_kind == "method")
(argument,) = occurrence.dispatch.input_slot_values
assert argument.value_sha256 == selected.value_sha256 == value_sha256
print(json.dumps({"stock": float(state.government_balance), "value_sha256": value_sha256}))
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


def test_mapped_wire_contract_is_refused_before_legacy_dispatch(tmp_path, monkeypatch):
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
                inputs=["ledger.flow"],
                input_ports={
                    "period_flow": {"source_kind": "registry_slot", "slot_id": "ledger.flow"}
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
    assert caught.value.code == "unsupported_program_graph_input_profile"
    assert calls == []
