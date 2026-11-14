"""Actual selected inputs survive model-stock execution and a cold reader."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import numpy as np
import pytest

from polisyos.core.artifacts import validate_core_model_json_artifact
from polisyos.core.contracts.foundry import ExecuteRequest, MethodExecutionBundle, SimulationResult
from polisyos.foundry.data_plane.bindings import load_input_bindings
from polisyos.foundry.execute._internal.graph import (
    _ClosedWorldMethodInputs,
    _materialize_exact_method_input_state,
    _ProgramGraphCallInventory,
    _require_preparable_method_inputs,
    execute_program_graph,
    prepare_program_graph_method_calls,
)
from polisyos.foundry.execute._internal.precision import METHOD_PATCH_PRECISION_REFUSAL
from polisyos.foundry.execute.api import execute as execute_foundry
from polisyos.foundry.execute.patch_vm import ModelStatePatchContext
from polisyos.foundry.methods.catalog.policy.accounting import PeriodFlowToStock
from tests._helpers.registered_derived_method_input import materialize_registered_method_input_case
from tests._helpers.selected_method_input import prepare_selected_method_input_case

_STOCK = "model.accumulated_flow"


def _cold_read(case, result_ref):
    product_root = Path(__file__).resolve().parents[4]
    environment = dict(os.environ)
    environment["PYTHONPATH"] = os.pathsep.join(
        str(path) for path in (product_root / "src", product_root / "tests", product_root)
    )
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    code = """
import hashlib
import json
import sys
from io import BytesIO
from pathlib import Path
import numpy as np
from polisyos.core.artifacts import validate_core_model_json_artifact
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.contracts.foundry import MethodExecutionBundle, SimulationResultRef
from polisyos.foundry.data_plane.bindings import load_input_bindings
from polisyos.foundry.execute.api import admit_execution_source
from polisyos.foundry.execute._internal.snapshots import load_bound_model_state_snapshot
from polisyos.foundry.execute.patch_vm import ModelStatePatchContext
from polisyos.foundry.model_state_slots import read_model_scalar_state_slot
store = FileSystemCAS(sys.argv[1])
source_root = Path(sys.argv[4]).resolve()
for name, module in tuple(sys.modules.items()):
    if name == 'polisyos' or name.startswith('polisyos.'):
        path = getattr(module, '__dict__', {}).get('__file__')
        if isinstance(path, str):
            assert Path(path).resolve().is_relative_to(source_root), (name, path)
result_ref = SimulationResultRef.model_validate_json(sys.argv[2])
admitted = admit_execution_source(store, result_ref)
bindings = load_input_bindings(store, admitted.basis.input_bindings_ref)
assert bindings.schema_version == '1.4'
bound = load_bound_model_state_snapshot(store,
    snapshot_ref=admitted.simulation_result.state_snapshot_ref)
value = np.asarray(read_model_scalar_state_slot(bound, slot_id=sys.argv[3],
    selected_registry_bundle_ref=admitted.basis.runtime_registry_ref,
    selected_layout_sha256=bound.layout.layout_sha256))
assert value.dtype == np.dtype(np.float32) and value.shape == ()
selected, = bindings.selected_method_inputs
argument = np.load(BytesIO(store.get_bytes(selected.npy_value_ref)), allow_pickle=False)
digest = hashlib.sha256(argument.dtype.str.encode('ascii')
    + json.dumps(argument.shape, separators=(',', ':')).encode('ascii')
    + argument.tobytes(order='C')).hexdigest()
edge = next(item for item in store.get_manifest(result_ref).inputs
    if item.role == 'method_execution')
bundle_ref = ArtifactRef(artifact_id=edge.artifact_id,
    manifest_profile_sha256=edge.manifest_profile_sha256,
    kind=MethodExecutionBundle.ARTIFACT_KIND, media_type='application/json')
bundle = validate_core_model_json_artifact(MethodExecutionBundle, store, bundle_ref)
occurrence, = [item for item in bundle.occurrences if item.node_kind == 'method']
physical, = occurrence.dispatch.input_slot_values
assert occurrence.status == 'succeeded' and physical.status == 'captured'
assert digest == selected.value_sha256 == physical.value_sha256
assert physical.runtime_dtype == argument.dtype.str
# Reopen the actual poststate as a new opening owner; no historical context is
# manufactured from the old state's bytes or from an in-memory layout.
next_opening = ModelStatePatchContext(store=store,
    base_ref=admitted.simulation_result.state_snapshot_ref,
    registry_bundle_ref=admitted.basis.runtime_registry_ref)
next_opening.require_opening_state()
assert next_opening.resolve_input_source(sys.argv[3], external_selected=False) == 'model_layout_slot'
assert np.asarray(next_opening.read_slot(sys.argv[3])).tobytes() == value.tobytes()
print(json.dumps({'stock': float(value), 'stock_dtype': value.dtype.str,
    'selected_dtype': argument.dtype.str, 'value_sha256': digest,
    'layout_sha256': bound.layout.layout_sha256,
    'base_ref': bindings.bound_state_snapshot_ref.model_dump(mode='json')}))
"""
    completed = subprocess.run(
        [
            sys.executable,
            "-B",
            "-c",
            code,
            str(case.store_root),
            result_ref.model_dump_json(),
            _STOCK,
            str(product_root),
        ],
        cwd=product_root,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    assert completed.returncode == 0, (completed.stdout, completed.stderr)
    return json.loads(completed.stdout)


def test_selected_flow_reaches_persistent_stock_and_cold_reader(tmp_path):
    case, metadata = prepare_selected_method_input_case(
        tmp_path,
        method_class=PeriodFlowToStock,
        state_writes=(_STOCK,),
        persistent_stock_slot=_STOCK,
    )
    try:
        original_context = ModelStatePatchContext(
            store=case.store,
            base_ref=case.bound_state_snapshot_ref,
            registry_bundle_ref=case.registry_bundle_ref,
        )
        materialized = materialize_registered_method_input_case(case, metadata)
        bindings = load_input_bindings(case.store, materialized.input_bindings_ref)
        assert bindings.bound_state_snapshot_ref == case.bound_state_snapshot_ref
        executed = execute_foundry(
            case.store,
            ExecuteRequest(
                exec_plan_ref=case.exec_plan_ref,
                registry_bundle_ref=case.registry_bundle_ref,
                input_bindings_ref=materialized.input_bindings_ref,
                return_selected_profile=True,
            ),
        )
        assert executed.ok and executed.simulation_result_ref is not None, executed.notes
        (tmp_path / "actual-execution.json").write_text(
            json.dumps(
                {
                    "cas_root": str(case.store_root),
                    "simulation_result_ref": executed.simulation_result_ref.model_dump(mode="json"),
                },
                sort_keys=True,
            )
            + "\n"
        )
        observed = _cold_read(case, executed.simulation_result_ref)
        expected = np.float32(10_000_000_000) + np.float32(-6_000_000_000)
        assert observed["stock"] == float(expected)
        assert observed["stock_dtype"] == np.dtype(np.float32).str
        assert observed["selected_dtype"] == np.dtype(np.float64).str
        assert observed["layout_sha256"] == original_context.bound_state.layout.layout_sha256
        assert observed["base_ref"] == case.bound_state_snapshot_ref.model_dump(mode="json")
        with pytest.raises(
            ValueError, match="program_graph_method_model_state_basis_not_established"
        ):
            prepare_program_graph_method_calls(
                case.store,
                program_ref=case.program_graph_ref,
                exec_plan_ref=case.exec_plan_ref,
                registry_bundle_ref=case.registry_bundle_ref,
                input_bindings_ref=materialized.input_bindings_ref,
                base_state=original_context.bound_state.state,
                steps=(0,),
            )

        # These are executions of the same genuine selected route with one
        # context fact removed. No negative may reach numerical dispatch.
        class Observer:
            def __init__(self):
                self.started = []

            def graph_started(self, **kwargs):
                self.started.append(kwargs)

        common = {
            "program_ref": case.program_graph_ref,
            "exec_plan_ref": case.exec_plan_ref,
            "base_state": original_context.bound_state.state,
            "base_ref": case.bound_state_snapshot_ref,
            "registry_bundle_ref": case.registry_bundle_ref,
            "input_bindings_ref": materialized.input_bindings_ref,
            "mechanism_registry": original_context.registry.mechanism_registry,
            "slot_registry": original_context.registry.slot_registry,
            "merge_registry": original_context.registry.merge_registry,
        }
        stored_result = validate_core_model_json_artifact(
            SimulationResult, case.store, executed.simulation_result_ref
        )
        post_context = ModelStatePatchContext(
            store=case.store,
            base_ref=stored_result.state_snapshot_ref,
            registry_bundle_ref=case.registry_bundle_ref,
        )
        for update, reason in (
            ({"model_state_context": None}, "model_scalar_state_execution_context_required"),
            (
                {"base_state": original_context.bound_state.state.replace()},
                "model_scalar_state_patch_base_state_mismatch",
            ),
            ({"base_ref": None}, "model_scalar_state_execution_base_ref_mismatch"),
            (
                {"registry_bundle_ref": None},
                "model_scalar_state_execution_registry_mismatch",
            ),
            (
                {
                    "model_state_context": post_context,
                    "base_state": post_context.bound_state.state,
                    "base_ref": post_context.base_ref,
                },
                "model_scalar_state_execution_binding_base_mismatch",
            ),
        ):
            observer = Observer()
            invocation = {**common, "model_state_context": original_context, **update}
            with pytest.raises(ValueError, match=reason):
                execute_program_graph(case.store, **invocation, observer=observer)
            assert observer.started == []
    finally:
        case.close()


def test_persistent_state_input_is_read_only_and_future_read_is_not_prepared(tmp_path):
    from types import MappingProxyType

    from polisyos.core.contracts.foundry import ProgramNode
    from tests.unit.foundry.execute.test_model_state_patching import _context

    context = _context(tmp_path, slot_id=_STOCK)
    flow_slot = next(iter(PeriodFlowToStock.signature.input_slots))

    class StockReader:
        signature = replace(
            PeriodFlowToStock.signature,
            namespace="tests.persistent_model_state",
            name="stock_reader",
            input_slots=frozenset({replace(flow_slot, name=_STOCK)}),
            patch_targets=(),
        )

    node = ProgramNode(
        node_id="reader",
        node_kind="method",
        method_fqn=StockReader.signature.fqn,
        method_version=StockReader.signature.version,
        inputs=[_STOCK],
    )
    selected = _ClosedWorldMethodInputs(
        registry=context.registry,
        values=MappingProxyType({}),
        records=MappingProxyType({}),
        notes=(),
    )
    materialized = _materialize_exact_method_input_state(
        context.bound_state.state,
        node=node,
        method_class=StockReader,
        slot_registry=context.registry.slot_registry,
        closed_world=selected,
        model_state_context=context,
    )
    actual = materialized[_STOCK]
    assert actual.shape == () and actual.dtype == np.dtype(np.float32)
    assert float(actual) == 10.0
    with pytest.raises(ValueError):
        actual.setflags(write=True)
    with pytest.raises(TypeError):
        materialized[_STOCK] = np.asarray(0, dtype=np.float32)

    shadowed = replace(
        selected,
        values=MappingProxyType({_STOCK: np.asarray(10, dtype=np.float32)}),
    )
    with pytest.raises(ValueError, match="model_scalar_state_input_source_ambiguous"):
        _materialize_exact_method_input_state(
            context.bound_state.state,
            node=node,
            method_class=StockReader,
            slot_registry=context.registry.slot_registry,
            closed_world=shadowed,
            model_state_context=context,
        )

    writer = ProgramNode(
        node_id="writer",
        node_kind="method",
        method_fqn=StockReader.signature.fqn,
        outputs=[_STOCK],
    )
    inventory = _ProgramGraphCallInventory(
        order=("writer", "reader"),
        nodes=MappingProxyType({"writer": writer, "reader": node}),
        mixed=False,
        active_mechanisms=MappingProxyType({}),
        mechanism_writes=MappingProxyType({}),
        treasury=None,
    )
    with pytest.raises(ValueError, match="program_graph_method_future_state_not_established"):
        _require_preparable_method_inputs(
            inventory,
            slot_registry=context.registry.slot_registry,
            step=0,
            model_state_context=context,
        )


def test_persistent_float32_stock_refuses_a_lost_selected_dollar(tmp_path):
    """A supported float64 input cannot silently become a zero stock effect."""
    case, metadata = prepare_selected_method_input_case(
        tmp_path,
        method_class=PeriodFlowToStock,
        state_writes=(_STOCK,),
        persistent_stock_slot=_STOCK,
    )
    try:
        materialized = materialize_registered_method_input_case(
            case,
            metadata,
            ratio_value=Decimal("-1"),
            denominator_value=Decimal("1"),
        )
        bindings = load_input_bindings(case.store, materialized.input_bindings_ref)
        (selected,) = bindings.selected_method_inputs
        assert selected.canonical_value == Decimal("-1")
        expected_argument = np.asarray(-1, dtype=np.float64)
        expected_hash = hashlib.sha256(
            expected_argument.dtype.str.encode("ascii")
            + json.dumps(expected_argument.shape, separators=(",", ":")).encode("ascii")
            + expected_argument.tobytes(order="C")
        ).hexdigest()
        assert selected.value_sha256 == expected_hash

        executed = execute_foundry(
            case.store,
            ExecuteRequest(
                exec_plan_ref=case.exec_plan_ref,
                registry_bundle_ref=case.registry_bundle_ref,
                input_bindings_ref=materialized.input_bindings_ref,
                return_selected_profile=True,
            ),
        )
        assert not executed.ok
        assert executed.simulation_result_ref is None
        assert METHOD_PATCH_PRECISION_REFUSAL in executed.notes
        assert executed.method_execution_bundle_ref is not None
        capture = validate_core_model_json_artifact(
            MethodExecutionBundle, case.store, executed.method_execution_bundle_ref
        )
        (occurrence,) = (item for item in capture.occurrences if item.node_kind == "method")
        assert occurrence.status == "succeeded"
        (argument,) = occurrence.dispatch.input_slot_values
        assert argument.status == "captured"
        assert argument.runtime_dtype == np.dtype(np.float64).str
        assert argument.value_sha256 == expected_hash

        # The state owner stays float32. With no tolerance or wider carrier,
        # its inability to represent 10B - 1 is an explicit refusal, not PASS0.
        original = ModelStatePatchContext(
            store=case.store,
            base_ref=case.bound_state_snapshot_ref,
            registry_bundle_ref=case.registry_bundle_ref,
        )
        original_value = np.asarray(original.read_slot(_STOCK))
        assert original_value.dtype == np.dtype(np.float32)
        assert float(original_value) == 10_000_000_000.0
    finally:
        case.close()
