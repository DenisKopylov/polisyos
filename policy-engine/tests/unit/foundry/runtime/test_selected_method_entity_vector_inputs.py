"""Candidate entity-vector steps through real method dispatch and stored replay."""

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
from fractions import Fraction
from pathlib import Path

import numpy as np
import pytest

from polisyos.core.artifacts import ArtifactRef, input_ref_from_artifact_ref
from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.contracts.foundry import (
    ExecuteRequest,
    FoundryInputBindings,
    FoundryInputBindingsRef,
    SemanticHorizonStepContext,
)
from polisyos.core.contracts.model_input_requirements import (
    load_model_input_obligation_set,
    persist_model_input_obligation_set,
)
from polisyos.core.contracts.semantic_input_binding import (
    load_resolved_input_binding_manifest,
    persist_resolved_input_binding_manifest,
)
from polisyos.data_forge.domains.catalog.knowledge import measurement_binding
from polisyos.data_forge.read_api.catalog import prepare_registered_entity_vector_input_steps
from polisyos.foundry.data_plane.bindings import (
    build_input_bindings,
    replay_selected_method_input_step_facts,
)
from polisyos.foundry.execute import api as execute_api
from polisyos.foundry.execute._internal.models import put_tensor
from tests._helpers.selected_method_entity_vector import (
    prepare_selected_method_entity_vector_case,
    vector_read_limits,
)


def _pairwise_gini(values: tuple[int, ...]) -> Fraction:
    """Use pairwise differences, independently of the method's sorted-rank code."""
    return Fraction(
        sum(abs(left - right) for left in values for right in values),
        2 * len(values) * sum(values),
    )


def _prepare_complete_inputs(tmp_path):
    fixture = prepare_selected_method_entity_vector_case(tmp_path)
    case = fixture.case
    manifest_ref = prepare_registered_entity_vector_input_steps(
        case.store,
        data_snapshot_ref=case.data_snapshot_ref,
        obligation_set_ref=fixture.obligation_set_ref,
        source_inputs=fixture.source_inputs,
        read_limits=vector_read_limits(),
    )
    selected_set, _ = load_model_input_obligation_set(case.store, fixture.obligation_set_ref)
    built = build_input_bindings(
        case.store,
        data_snapshot_ref=case.data_snapshot_ref,
        registry_bundle_ref=case.registry_bundle_ref,
        resolved_binding_manifest_ref=manifest_ref,
        return_selected_profile=True,
    )
    facts = replay_selected_method_input_step_facts(
        case.store,
        input_bindings_ref=built.input_bindings_ref,
        expected_invocation=selected_set.invocation,
    )
    return fixture, selected_set.invocation, built, facts


def _persist_binding_rows(case, original_ref, bindings, rows):
    inputs = [
        edge
        for edge in case.store.get_manifest(original_ref).inputs
        if not edge.role.startswith("method_input.")
    ]
    for row in rows:
        record = row.input
        inputs.extend(
            (
                input_ref_from_artifact_ref(
                    record.model_input_obligation_ref,
                    role=f"method_input.{record.binding_id}.obligation",
                ),
                input_ref_from_artifact_ref(
                    record.npy_value_ref, role=f"method_input.{record.binding_id}.value"
                ),
            )
        )
    ref = case.store.put_json(
        bindings.model_copy(update={"selected_method_input_steps": rows}),
        PutOptions(
            kind=FoundryInputBindings.ARTIFACT_KIND,
            media_type="application/json",
            schema=SchemaInfo(name=FoundryInputBindings.ARTIFACT_SCHEMA_NAME, version="1.5"),
            inputs=inputs,
        ),
        return_selected_profile=True,
    )
    return FoundryInputBindingsRef.model_validate(ref.model_dump(mode="python"))


def test_selected_entity_vector_steps_refuse_grafts_and_incomplete_coverage_before_dispatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def forbid_dispatch(*_args, **_kwargs):
        raise AssertionError("invalid vector selection reached physical graph dispatch")

    monkeypatch.setattr(execute_api, "execute_program_graph", forbid_dispatch)
    fixture, invocation, built, facts = _prepare_complete_inputs(tmp_path)
    case = fixture.case
    try:
        assert facts.coverage.is_complete
        assert all(row.input_kind == "vector" for row in facts.records)
        assert facts.values[(fixture.port.slot_id, 0)].tolist() == [10, 20, 30, 40]
        assert facts.values[(fixture.port.slot_id, 1)].tolist() == [20, 20, 20, 40]
        for code in ("source_meaning_consumer_asserted", "source_scope_consumer_asserted"):
            assert f"semantic_input_limitation:{code}" in facts.notes
        assert facts.bindings.data_snapshot_ref.model_dump(
            mode="json"
        ) == case.data_snapshot_ref.model_dump(mode="json")
        assert facts.bindings.bound_state_snapshot_ref.model_dump(
            mode="json"
        ) == case.bound_state_snapshot_ref.model_dump(mode="json")

        original_set, _ = load_model_input_obligation_set(case.store, fixture.obligation_set_ref)
        supplied_invocation = invocation.model_copy(
            update={"input_bindings_ref": built.input_bindings_ref}
        )
        supplied_set_ref = persist_model_input_obligation_set(
            case.store,
            original_set.model_copy(
                update={"invocation": supplied_invocation, "obligation_refs": ()}
            ),
        )
        supplied_set, supplied_members = load_model_input_obligation_set(
            case.store, supplied_set_ref
        )
        assert supplied_members == ()
        assert supplied_set.invocation.context == invocation.context
        assert supplied_set.invocation.registry_bundle_ref.model_dump(mode="json") == (
            invocation.registry_bundle_ref.model_dump(mode="json")
        )
        assert supplied_set.prestate_ref.model_dump(
            mode="json"
        ) == original_set.prestate_ref.model_dump(mode="json")
        persisted_manifests = []
        original_manifest_writer = measurement_binding.persist_resolved_input_binding_manifest

        def record_manifest_write(*args, **kwargs):
            persisted_manifests.append((args, kwargs))
            return original_manifest_writer(*args, **kwargs)

        with monkeypatch.context() as producer_guard:
            producer_guard.setattr(
                measurement_binding,
                "persist_resolved_input_binding_manifest",
                record_manifest_write,
            )
            code = "foundry_selected_method_input_step_original_prestate_required"
            with pytest.raises(ValueError, match=f"^{code}$") as refused:
                prepare_registered_entity_vector_input_steps(
                    case.store,
                    data_snapshot_ref=case.data_snapshot_ref,
                    obligation_set_ref=supplied_set_ref,
                    source_inputs=fixture.source_inputs,
                    read_limits=vector_read_limits(),
                )
            assert refused.value.code == code
        assert persisted_manifests == []

        first, second = facts.records
        wrong_value = np.asarray([20, 10, 30, 40], dtype=np.float64)
        wrong_ref = put_tensor(
            case.store,
            wrong_value,
            return_selected_profile=True,
            kind="foundry.selected_method_input_value",
            inputs=list(case.store.get_manifest(first.input.npy_value_ref).inputs),
        )
        wrong_rows = (
            first.model_copy(
                update={"input": first.input.model_copy(update={"npy_value_ref": wrong_ref})}
            ),
            second,
        )
        wrong_binding = _persist_binding_rows(
            case, built.input_bindings_ref, facts.bindings, wrong_rows
        )
        full_manifest = load_resolved_input_binding_manifest(
            case.store, facts.bindings.resolved_binding_manifest_ref
        )
        partial_manifest = full_manifest.model_copy(
            update={"entity_vector_steps": full_manifest.entity_vector_steps[:1]}
        )
        partial = build_input_bindings(
            case.store,
            data_snapshot_ref=case.data_snapshot_ref,
            registry_bundle_ref=case.registry_bundle_ref,
            resolved_binding_manifest_ref=persist_resolved_input_binding_manifest(
                case.store, partial_manifest
            ),
            return_selected_profile=True,
        )

        step = SemanticHorizonStepContext(
            obligation_set_ref=fixture.obligation_set_ref,
            steps=invocation.steps,
            step_index=0,
            replication_seed=23,
        )
        for binding_ref, code in (
            (wrong_binding, "foundry_selected_method_input_value_identity_mismatch"),
            (partial.input_bindings_ref, "model_input_step_coverage_incomplete"),
        ):
            with pytest.raises(ValueError, match=f"^{code}$"):
                execute_api.execute_semantic_horizon_step(
                    case.store,
                    ExecuteRequest(
                        exec_plan_ref=case.exec_plan_ref,
                        registry_bundle_ref=case.registry_bundle_ref,
                        input_bindings_ref=binding_ref,
                        return_selected_profile=True,
                    ),
                    expected_invocation=invocation,
                    step=step,
                )
    finally:
        case.close()


def _fresh_read_vector_chain(case, result_refs):
    product_root = Path(__file__).resolve().parents[4]
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(product_root / "src")
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    code = r"""
import json
import sys
from io import BytesIO
from pathlib import Path
import numpy as np
from polisyos.core.artifacts import validate_core_model_json_artifact
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.contracts.foundry import (
    MethodExecutionBundle, MethodMetricBindingSet, MethodOutputPayload, SimulationResultRef,
)
from polisyos.foundry.data_plane.bindings import load_input_bindings
from polisyos.foundry.data_plane.selected_tensors import selected_tensor_value_sha256
from polisyos.foundry.execute import api as execute_api

def forbidden(*args, **kwargs):
    raise AssertionError('cold reader invoked physical execution')

execute_api.execute = forbidden
execute_api.execute_semantic_horizon_step = forbidden
execute_api.execute_program_graph = forbidden
assert Path(execute_api.__file__).resolve().is_relative_to(Path(sys.argv[3]).resolve())
store = FileSystemCAS.open_existing_read_only(Path(sys.argv[1]))
refs = tuple(SimulationResultRef.model_validate(item) for item in json.loads(sys.argv[2]))
admissions = execute_api.admit_semantic_horizon_step_chain(store, refs)
expected = ([10,20,30,40], [20,20,20,40])
rows = []
for index, (ref, admission) in enumerate(zip(refs, admissions, strict=True)):
    bindings = load_input_bindings(store, admission.basis.input_bindings_ref)
    row, = (row for row in bindings.selected_method_input_steps if row.step_scope.step == index)
    selected = row.input
    value = np.load(BytesIO(store.get_bytes(selected.npy_value_ref)), allow_pickle=False)
    digest = selected_tensor_value_sha256(value.dtype, value.shape, value.tobytes(order='C'))
    assert value.tolist() == expected[index]
    assert value.dtype == np.dtype('float64') and value.shape == (4,)
    assert digest == selected.tensor_value_sha256
    edge, = (edge for edge in store.get_manifest(ref).inputs if edge.role == 'method_execution')
    bundle_ref = ArtifactRef(artifact_id=edge.artifact_id, kind=MethodExecutionBundle.ARTIFACT_KIND,
        media_type='application/json', manifest_profile_sha256=edge.manifest_profile_sha256)
    bundle = validate_core_model_json_artifact(MethodExecutionBundle, store, bundle_ref)
    occurrence, = (item for item in bundle.occurrences if item.node_id == 'gini')
    assert occurrence.status == 'succeeded' and occurrence.dispatch is not None
    argument, = (item for item in occurrence.dispatch.input_slot_values if item.slot_id == 'values')
    assert argument.status == 'captured' and argument.value_sha256 == digest
    assert argument.runtime_shape == (4,) and argument.runtime_dtype == np.dtype('float64').str
    parameter, = (item for item in occurrence.dispatch.parameter_values if item.name == 'nu')
    assert parameter.status == 'captured' and parameter.source == 'requested'
    assert type(parameter.value) is int and parameter.value == 2
    output, = (item for item in occurrence.output_slots if item.slot_id == 'result')
    assert output.status == 'captured'
    payload = validate_core_model_json_artifact(MethodOutputPayload, store, output.output_ref)
    assert payload.value_path == ('generalized_gini',)
    binding_set = validate_core_model_json_artifact(MethodMetricBindingSet, store, bundle.method_metric_binding_set_ref)
    binding, = binding_set.bindings
    assert binding.availability == 'unavailable'
    assert 'registered_method_metric_law_missing' in binding.limitation.split(';')
    assert 'semantic_input_limitation:source_meaning_consumer_asserted' in admission.simulation_result.notes
    assert 'semantic_input_limitation:source_scope_consumer_asserted' in admission.simulation_result.notes
    rows.append({'step': index, 'digest': digest, 'gini': payload.value,
                 'output_ref': output.output_ref.model_dump(mode='json')})
print(json.dumps(rows, sort_keys=True))
"""
    result = subprocess.run(
        [
            sys.executable,
            "-B",
            "-c",
            code,
            str(case.store_root),
            json.dumps([ref.model_dump(mode="json") for ref in result_refs]),
            str(product_root / "src"),
        ],
        cwd=product_root,
        env=environment,
        capture_output=True,
        text=True,
        timeout=90,
        check=False,
    )
    assert result.returncode == 0, (result.stdout, result.stderr)
    return json.loads(result.stdout)


def test_selected_entity_vector_steps_reach_gini_and_a_fresh_read_only_consumer(
    tmp_path: Path,
) -> None:
    fixture, invocation, built, facts = _prepare_complete_inputs(tmp_path)
    case = fixture.case
    try:
        expected_gini = (_pairwise_gini((10, 20, 30, 40)), _pairwise_gini((20, 20, 20, 40)))
        assert expected_gini == (Fraction(1, 4), Fraction(3, 20))
        request = ExecuteRequest(
            exec_plan_ref=case.exec_plan_ref,
            registry_bundle_ref=case.registry_bundle_ref,
            input_bindings_ref=built.input_bindings_ref,
            return_selected_profile=True,
        )
        result_refs = []
        handoff_path = tmp_path / "selected-entity-vector-results.json"
        for index in invocation.steps:
            result = execute_api.execute_semantic_horizon_step(
                case.store,
                request,
                expected_invocation=invocation,
                step=SemanticHorizonStepContext(
                    obligation_set_ref=fixture.obligation_set_ref,
                    steps=invocation.steps,
                    step_index=index,
                    replication_seed=23,
                    previous_result_ref=None if index == 0 else result_refs[-1],
                ),
            )
            if result.simulation_result_ref is not None:
                result_refs.append(result.simulation_result_ref)
            handoff_path.write_text(
                json.dumps(
                    {
                        "cas_root": str(case.store_root),
                        "request": request.model_dump(mode="json"),
                        "result_refs": [ref.model_dump(mode="json") for ref in result_refs],
                        "source_view_ref": fixture.source_view_ref.model_dump(mode="json"),
                        "notes": result.notes,
                    },
                    sort_keys=True,
                    indent=2,
                )
                + "\n"
            )
            assert result.ok and result.simulation_result_ref is not None
        print(f"SELECTED_VECTOR_COLD_READ_HANDOFF={handoff_path}")
        cold = _fresh_read_vector_chain(case, tuple(result_refs))
        assert tuple(row["gini"] for row in cold) == pytest.approx(
            tuple(float(value) for value in expected_gini), rel=0, abs=1e-15
        )
        assert len({row["digest"] for row in cold}) == 2

        selected_ref = facts.records[1].input.npy_value_ref
        output_ref = ArtifactRef.model_validate(cold[0]["output_ref"])
        axis_ref = facts.records[0].input.entity_axis_ref
        for removed_ref in (selected_ref, output_ref, axis_ref):
            blob, _ = case.store._paths(removed_ref.artifact_id)
            saved = blob.read_bytes()
            original_mode = stat.S_IMODE(blob.stat().st_mode)
            blob.unlink()
            try:
                reader = FileSystemCAS.open_existing_read_only(case.store_root)
                with pytest.raises(
                    FileNotFoundError, match=str(removed_ref.artifact_id).removeprefix("sha256:")
                ):
                    execute_api.admit_semantic_horizon_step_chain(reader, tuple(result_refs))
            finally:
                blob.write_bytes(saved)
                os.chmod(blob, original_mode)
        assert _fresh_read_vector_chain(case, tuple(result_refs)) == cold
    finally:
        case.close()
