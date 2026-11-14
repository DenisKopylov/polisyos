"""Actual Runtime call content under the source-recorded candidate host.

This component proof joins a held NumPy call to its actual Foundry execution
record. It does not fabricate Generic cycle inputs, a full N5 content witness,
physical quota completion, verifier appointment or protected-use permission.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from dataclasses import replace
from types import MappingProxyType

import pytest


def test_runtime_held_method_provider_content_inside_host(tmp_path, monkeypatch, request):
    """Observe and persist one genuine selected method invocation, without N5."""
    node = f"{__file__}::test_runtime_held_method_provider_content_inside_host"
    if node not in request.config.invocation_params.args:
        pytest.skip("requires the explicit fresh-host test invocation")
    session = vars(sys).get("_polisyos_loaded_host_v1")
    assert type(session) is dict and session["phase"] == "collecting"
    assert session["profile"]["native_capture_scope"] == (
        "actually-loaded-locked-wheel-providers/1"
    )
    # The host intentionally drops ambient environment configuration. This is
    # an explicit component-test profile, selected before the method is loaded.
    assert "polisyos.foundry.methods.catalog.policy.accounting" not in sys.modules
    for name, value in {
        "FOUNDRY_SHAPE_CHECK": "0",
        "JAX_PLATFORMS": "cpu",
        "OMP_NUM_THREADS": "1",
        "OPENBLAS_NUM_THREADS": "1",
        "MKL_NUM_THREADS": "1",
        "VECLIB_MAXIMUM_THREADS": "1",
        "NUMEXPR_NUM_THREADS": "1",
    }.items():
        monkeypatch.setenv(name, value)

    import numpy as np

    from polisyos.core.artifacts import validate_core_model_json_artifact
    from polisyos.core.contracts.foundry import ExecuteRequest, MethodExecutionBundle
    from polisyos.core.contracts.model_input_requirements import load_model_input_obligation_set
    from polisyos.core.contracts.semantic_input_binding import load_resolved_input_binding_manifest
    from polisyos.foundry.data_plane.bindings import reconcile_selected_method_input_bindings
    from polisyos.foundry.execute import execute as execute_foundry
    from polisyos.foundry.execute import load_state_snapshot, prepare_program_graph_method_calls
    from polisyos.foundry.execute.api import admit_execution_source
    from polisyos.foundry.methods.backends.numpy_runner import NumpyRunner
    from polisyos.foundry.methods.catalog.policy.accounting import PeriodFlowToStock
    from polisyos.runtime.quality.acquisition_evaluation import _generic_method_call_content
    from tests._helpers.derived_selected_method_input import materialize_selected_method_input_case
    from tests._helpers.selected_method_input import prepare_selected_method_input_case
    from tests.unit.foundry.runtime.test_selected_method_inputs import _fresh_process_read

    held_runner = NumpyRunner.execute
    case, metadata = prepare_selected_method_input_case(tmp_path, method_class=PeriodFlowToStock)
    try:
        selected = materialize_selected_method_input_case(case, metadata)
        manifest = load_resolved_input_binding_manifest(
            case.store, selected.resolved_binding_manifest_ref
        )
        obligation_set, _ = load_model_input_obligation_set(
            case.store, manifest.model_input_obligation_set_ref
        )
        state = load_state_snapshot(case.store, snapshot_ref=case.bound_state_snapshot_ref)
        (predicted,) = prepare_program_graph_method_calls(
            case.store,
            program_ref=case.program_graph_ref,
            exec_plan_ref=case.exec_plan_ref,
            registry_bundle_ref=case.registry_bundle_ref,
            input_bindings_ref=selected.input_bindings_ref,
            base_state=state,
            steps=(0,),
            expected_invocation=obligation_set.invocation,
            seed=0,
        )
        content = _generic_method_call_content(predicted)
        projected = json.loads(content)
        assert projected["profile"] == "foundry-mapped-numpy-method-call/1"
        assert float(predicted.input_values["period_flow"]) == -6_000_000_000.0
        assert predicted.rng_state == np.random.default_rng(predicted.seed).bit_generator.state
        assert predicted.resolved_parameters == {"target_slot": "government.balance"}
        assert set(projected["providers"]) == set(predicted.provider_callables)
        assert all(value is not None for value in projected["providers"].values())
        native = json.loads(projected["providers"]["default_rng"])["nodes"][0]
        assert native["kind"] == "recorded_native_export"
        assert native["binding"]["native_state_completeness"] == "not_established"
        runner = json.loads(projected["providers"]["runner_execute"])["nodes"]
        receiver = next(row for row in runner if row.get("kind") == "plain_bound_receiver")
        assert receiver["receiver_profile"].endswith("/2")
        assert receiver["external_state_completeness"] == "not_established"

        removed = dict(predicted.provider_callables)
        del removed["runner_execute"]
        with pytest.raises(ValueError, match="generic_method_call_provider_census_not_established"):
            _generic_method_call_content(
                replace(predicted, provider_callables=MappingProxyType(removed))
            )
        assert _generic_method_call_content(replace(predicted, seed=predicted.seed + 1)) != content

        observed = []

        def forbidden_refetch(*_args, **_kwargs):
            raise AssertionError("the executor re-read the changed runner class slot")

        class Observer:
            def graph_started(self, **_):
                pass

            def graph_finished(self, **_):
                observed.append("graph_finished")

            def node_finished(self, **_):
                pass

            def method_started(self, *, prepared_call, step, plan_index, node_id):
                assert (step, plan_index, node_id) == (
                    predicted.step,
                    predicted.plan_index,
                    predicted.node_id,
                )
                assert prepared_call.provider_callables["runner_execute"].__func__ is held_runner
                assert prepared_call.rng_state == predicted.rng_state
                assert _generic_method_call_content(prepared_call) == content
                observed.append(prepared_call)
                monkeypatch.setattr(NumpyRunner, "execute", forbidden_refetch)

            def method_finished(self, *, status, **_):
                assert status == "returned"
                assert _generic_method_call_content(observed[0]) == content
                observed.append("returned")
                monkeypatch.setattr(NumpyRunner, "execute", held_runner)

        execution = execute_foundry(
            case.store,
            ExecuteRequest(
                exec_plan_ref=case.exec_plan_ref,
                registry_bundle_ref=case.registry_bundle_ref,
                input_bindings_ref=selected.input_bindings_ref,
                return_selected_profile=True,
            ),
            observer=Observer(),
        )
        assert execution.ok and execution.simulation_result_ref is not None
        assert len(observed) == 3 and observed[1:] == ["returned", "graph_finished"]
        assert execution.method_execution_bundle_ref is not None
        bundle = validate_core_model_json_artifact(
            MethodExecutionBundle, case.store, execution.method_execution_bundle_ref
        )
        (occurrence,) = (item for item in bundle.occurrences if item.node_kind == "method")
        dispatch = occurrence.dispatch
        assert dispatch.outcome == "succeeded"
        assert dispatch.root_seed == predicted.root_seed
        assert dispatch.method_seed == dispatch.reproducibility_seed == predicted.seed
        assert dispatch.method_key_words == predicted.key_words
        assert dispatch.actual_backend == "numpy" and dispatch.seed_status == "reconciled"
        # The legacy dispatch record retains keys/seeds, not the entire RNG
        # prestate. The full Generic/N5 content artifact is a separate bridge.
        assert dispatch.rng_state_status == "runner_rng_state_not_retained"
        facts = reconcile_selected_method_input_bindings(
            case.store, input_bindings_ref=selected.input_bindings_ref
        )
        (argument,) = dispatch.input_slot_values
        assert argument.value_sha256 == facts.records[0].value_sha256
        admitted = admit_execution_source(case.store, execution.simulation_result_ref)
        assert admitted.basis.input_bindings_ref == selected.input_bindings_ref
        final = load_state_snapshot(
            case.store, snapshot_ref=admitted.simulation_result.state_snapshot_ref
        )
        assert float(final.government_balance) == 4_000_000_000.0
        cold = _fresh_process_read(case, execution.simulation_result_ref)
        assert cold["stock"] == 4_000_000_000.0
        assert cold["value_sha256"] == argument.value_sha256
        assert cold["occurrences"] == 1
        print(
            json.dumps(
                {
                    "scope": "runtime_provider_content_and_foundry_execution_only",
                    "source": session["source_frame"],
                    "shape_check": os.environ["FOUNDRY_SHAPE_CHECK"],
                    "actual_method_calls": 1,
                    "method_content_sha256": hashlib.sha256(content).hexdigest(),
                    "argument_sha256": argument.value_sha256,
                    "stock": cold["stock"],
                    "full_n5_witness": "unrun",
                    "protected_authority": "not_established",
                },
                sort_keys=True,
            )
        )
    finally:
        monkeypatch.setattr(NumpyRunner, "execute", held_runner)
        case.close()
