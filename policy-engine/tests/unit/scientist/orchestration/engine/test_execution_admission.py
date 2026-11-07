"""Real selected-CAS and fresh-process candidate executable admission."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from polisyos.core.artifacts import (
    ArtifactRef,
    ArtifactWriteOptions,
    FileSystemCAS,
    SchemaInfo,
    validate_core_model_json_artifact,
)
from polisyos.scientist.orchestration.engine.execution_admission import (
    ExecutionAdmissionError,
    WorkflowExecutionAdmission,
    persist_workflow_execution_admission,
    verify_workflow_execution_admission,
)
from polisyos.scientist.orchestration.engine.registry import NodeRegistry
from polisyos.scientist.orchestration.engine.workflow_spec import NodeInvocation, WorkflowSpec
from tests._helpers.execution_admission import (
    AdmissionNode,
    AdmissionSettings,
    BuiltinsImportAdmissionNode,
    ChangedAdmissionNode,
    ConfiguredAdmissionNode,
    DynamicImportAdmissionNode,
    NestedImportAdmissionNode,
    OtherAdmissionNode,
    RuntimeImportAdmissionNode,
)


def _fixture(tmp_path: Path) -> tuple[Any, ...]:
    store = FileSystemCAS(tmp_path / "cas")
    node = AdmissionNode(tmp_path / "effects.sqlite3")
    registry = NodeRegistry()
    registry.register(node)
    workflow = WorkflowSpec(
        workflow_id="admitted_probe",
        nodes=[
            NodeInvocation(alias="completed", node_id=node.spec.metadata.component_id),
            NodeInvocation(
                alias="remaining", node_id=node.spec.metadata.component_id, depends_on=["completed"]
            ),
        ],
    )
    ref = store.put_json(
        workflow.model_dump(mode="python"),
        ArtifactWriteOptions(
            kind="scientist.workflow_spec",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.scientist.orchestration.engine.WorkflowSpec", version="1.0"
            ),
        ),
        return_selected_profile=True,
    )
    admission_ref = persist_workflow_execution_admission(
        store, workflow, registry, workflow_ref=ref, run_id="admission-run"
    )
    return store, node, registry, workflow, ref, admission_ref


def _verify(
    store: FileSystemCAS,
    registry: NodeRegistry,
    workflow: WorkflowSpec,
    workflow_ref: ArtifactRef,
    admission_ref: ArtifactRef,
    residual_workflow: WorkflowSpec | None = None,
) -> None:
    verify_workflow_execution_admission(
        store,
        admission_ref,
        original_workflow_ref=workflow_ref,
        original_workflow=workflow,
        residual_workflow=(
            residual_workflow
            if residual_workflow is not None
            else workflow.model_copy(update={"nodes": [workflow.nodes[1]]})
        ),
        registry=registry,
        run_id="admission-run",
    )


def test_actual_source_backed_registry_is_admitted_before_real_fresh_process_effect(
    tmp_path: Path,
) -> None:
    store, node, _registry, workflow, workflow_ref, admission_ref = _fixture(tmp_path)
    assert not node.database.exists()
    payload = {
        "root": str(tmp_path),
        "workflow": workflow.model_dump(mode="json"),
        "workflow_ref": workflow_ref.model_dump(mode="json"),
        "admission_ref": admission_ref.model_dump(mode="json"),
    }
    script = """
import json, logging, sqlite3, sys
from pathlib import Path
from polisyos.core.artifacts import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.execution_admission import verify_workflow_execution_admission
from polisyos.scientist.orchestration.engine.registry import NodeRegistry
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.workflow_spec import WorkflowSpec
from tests._helpers.execution_admission import AdmissionNode
data=json.loads(sys.stdin.read()); root=Path(data['root'])
store=FileSystemCAS(root/'cas'); registry=NodeRegistry(); node=AdmissionNode(root/'effects.sqlite3')
registry.register(node); workflow=WorkflowSpec.model_validate(data['workflow'])
verify_workflow_execution_admission(store,ArtifactRef.model_validate(data['admission_ref']),
    original_workflow_ref=ArtifactRef.model_validate(data['workflow_ref']),
    original_workflow=workflow,residual_workflow=workflow.model_copy(update={'nodes':[workflow.nodes[1]]}),
    registry=registry,run_id='admission-run')
ctx=ExecutionContext(store=store,run=None,logger=logging.getLogger('admission-test'))
outcome=node.execute(ctx,ExperimentState(run_id='admission-run'))
fresh=FileSystemCAS(root/'cas'); assert json.loads(fresh.get_bytes(outcome.artifacts[0]))=={'value':7}
with sqlite3.connect(root/'effects.sqlite3') as connection:
    assert connection.execute('SELECT value FROM effects').fetchall()==[(7,)]
print(json.dumps({'status':outcome.status,'output_ref':outcome.artifacts[0].model_dump(mode='json')}))
"""
    completed = subprocess.run(
        [sys.executable, "-B", "-c", script],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=False,
        env={**os.environ, "PYTHONPATH": f"{Path.cwd() / 'src'}{os.pathsep}{Path.cwd()}"},
        timeout=30,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    result = json.loads(completed.stdout)
    ref = ArtifactRef.model_validate(result["output_ref"])
    assert result["status"] == "ok" and ref.manifest_profile_sha256 is not None
    assert store.verify(ref).ok
    assert json.loads(store.get_bytes(ref)) == {"value": 7}


@pytest.mark.parametrize("change", ["implementation", "config", "spec", "params"])
def test_actual_residual_drift_refuses_before_the_producer(
    tmp_path: Path, change: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, node, registry, workflow, workflow_ref, admission_ref = _fixture(tmp_path)
    residual = workflow.model_copy(
        deep=True, update={"nodes": [workflow.nodes[1].model_copy(deep=True)]}
    )
    if change == "implementation":
        registry.register(ChangedAdmissionNode(node.database), override=True)
    elif change == "config":
        node.value = 8
    elif change == "spec":
        original_spec = node.spec

        def changed_spec(self):
            return original_spec.model_copy(update={"state_writes": ["params.other"]})

        monkeypatch.setattr(AdmissionNode, "spec", property(changed_spec))
    else:
        residual.nodes[0].params["value"] = 8
    with pytest.raises(
        ExecutionAdmissionError, match="execution_admission_residual_definition_changed"
    ):
        _verify(store, registry, workflow, workflow_ref, admission_ref, residual)
    assert not node.database.exists()


def test_completed_reopen_and_completed_aliases_do_not_need_registry_lookup(tmp_path: Path) -> None:
    store, _node, registry, workflow, workflow_ref, admission_ref = _fixture(tmp_path)

    class PoisonRegistry(NodeRegistry):
        def get(self, _node_id):
            raise AssertionError("completed reopen must not resolve removed nodes")

    verify_workflow_execution_admission(
        store,
        admission_ref,
        original_workflow_ref=workflow_ref,
        original_workflow=workflow,
        residual_workflow=workflow.model_copy(update={"nodes": []}),
        registry=PoisonRegistry(),
        run_id="admission-run",
    )
    calls = []
    actual_get = registry.get

    def observed_get(node_id):
        calls.append(node_id)
        return actual_get(node_id)

    registry.get = observed_get
    _verify(store, registry, workflow, workflow_ref, admission_ref)
    assert calls == [workflow.nodes[1].node_id]


def test_wrong_selected_view_missing_bytes_and_foreign_run_do_not_authorize(tmp_path: Path) -> None:
    store, _node, registry, workflow, workflow_ref, admission_ref = _fixture(tmp_path)
    assert admission_ref.manifest_profile_sha256 is not None
    admission = validate_core_model_json_artifact(WorkflowExecutionAdmission, store, admission_ref)
    assert all(node.status == "recomputed" for node in admission.nodes)
    wrong = store.put_json(
        admission.model_dump(mode="python"),
        ArtifactWriteOptions(
            kind=admission.ARTIFACT_KIND,
            media_type=admission.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(name="tests.WrongAdmissionView", version="1.0"),
        ),
        return_selected_profile=True,
    )
    assert wrong.artifact_id == admission_ref.artifact_id
    with pytest.raises(ValueError):
        _verify(store, registry, workflow, workflow_ref, wrong)
    with pytest.raises(ExecutionAdmissionError, match="selected_ref_invalid"):
        _verify(
            store,
            registry,
            workflow,
            workflow_ref,
            admission_ref.model_copy(update={"manifest_profile_sha256": None}),
        )
    missing = ArtifactRef.model_validate(
        {**admission_ref.model_dump(mode="python"), "artifact_id": "sha256:" + "f" * 64}
    )
    with pytest.raises(ExecutionAdmissionError, match="selected_ref_invalid"):
        _verify(store, registry, workflow, workflow_ref, missing)
    with pytest.raises(ExecutionAdmissionError, match="original_basis_mismatch"):
        verify_workflow_execution_admission(
            store,
            admission_ref,
            original_workflow_ref=workflow_ref,
            original_workflow=workflow,
            residual_workflow=workflow,
            registry=registry,
            run_id="different-run",
        )


def test_opaque_live_service_is_declared_unsupported_and_strict_continuation_refuses(
    tmp_path: Path,
) -> None:
    store, node, registry, workflow, workflow_ref, _ref = _fixture(tmp_path)
    node.service = object()
    ref = persist_workflow_execution_admission(
        store, workflow, registry, workflow_ref=workflow_ref, run_id="admission-run"
    )
    admission = validate_core_model_json_artifact(WorkflowExecutionAdmission, store, ref)
    assert all(node.reason == "execution_admission_opaque_config" for node in admission.nodes)
    with pytest.raises(ExecutionAdmissionError, match="original_definition_not_established"):
        _verify(store, registry, workflow, workflow_ref, ref)
    assert not node.database.exists()


def test_admission_never_speculatively_calls_a_binder(tmp_path: Path, monkeypatch) -> None:
    store, _node, registry, workflow, workflow_ref, _ref = _fixture(tmp_path)
    workflow.nodes[1].params["value"] = 8
    workflow_ref = store.put_json(
        workflow.model_dump(mode="python"),
        ArtifactWriteOptions(
            kind="scientist.workflow_spec",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.scientist.orchestration.engine.WorkflowSpec", version="1.0"
            ),
        ),
        return_selected_profile=True,
    )

    def no_speculative_bind(self, params):
        raise AssertionError("admission must not execute an unstarted producer binder")

    monkeypatch.setattr(AdmissionNode, "bind", no_speculative_bind)
    ref = persist_workflow_execution_admission(
        store, workflow, registry, workflow_ref=workflow_ref, run_id="admission-run"
    )
    admission = validate_core_model_json_artifact(WorkflowExecutionAdmission, store, ref)
    assert admission.nodes[1].reason == "execution_admission_parameter_binding_requires_held_owner"
    with pytest.raises(ExecutionAdmissionError, match="original_definition_not_established"):
        _verify(store, registry, workflow, workflow_ref, ref)


def test_original_workflow_object_cannot_claim_different_selected_bytes(tmp_path: Path) -> None:
    store, _node, registry, workflow, workflow_ref, admission_ref = _fixture(tmp_path)
    changed = workflow.model_copy(deep=True)
    changed.nodes[1].params["different"] = True
    with pytest.raises(ExecutionAdmissionError, match="workflow_bytes_mismatch"):
        persist_workflow_execution_admission(
            store, changed, registry, workflow_ref=workflow_ref, run_id="admission-run"
        )
    with pytest.raises(ExecutionAdmissionError, match="workflow_bytes_mismatch"):
        _verify(store, registry, changed, workflow_ref, admission_ref)


def test_workflow_schema_is_checked_before_a_node_can_claim_its_selected_view(
    tmp_path: Path,
) -> None:
    store, node, registry, workflow, _workflow_ref, _ref = _fixture(tmp_path)
    wrong = store.put_json(
        workflow.model_dump(mode="python"),
        ArtifactWriteOptions(
            kind="scientist.workflow_spec",
            media_type="application/json",
            schema=SchemaInfo(name="tests.WrongWorkflowOwner", version="1.0"),
        ),
        return_selected_profile=True,
    )
    with pytest.raises(ExecutionAdmissionError, match="workflow_schema_mismatch"):
        persist_workflow_execution_admission(
            store, workflow, registry, workflow_ref=wrong, run_id="admission-run"
        )
    assert not node.database.exists()


def test_unavailable_completed_definition_does_not_block_supported_residual(tmp_path: Path) -> None:
    store, first, registry, workflow, _workflow_ref, _ref = _fixture(tmp_path)
    first.service = object()
    remaining = OtherAdmissionNode(first.database)
    registry.register(remaining)
    workflow.nodes[1].node_id = remaining.spec.metadata.component_id
    workflow_ref = store.put_json(
        workflow.model_dump(mode="python"),
        ArtifactWriteOptions(
            kind="scientist.workflow_spec",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.scientist.orchestration.engine.WorkflowSpec", version="1.0"
            ),
        ),
        return_selected_profile=True,
    )
    admission_ref = persist_workflow_execution_admission(
        store, workflow, registry, workflow_ref=workflow_ref, run_id="admission-run"
    )
    model = validate_core_model_json_artifact(WorkflowExecutionAdmission, store, admission_ref)
    assert [item.status for item in model.nodes] == ["not_established", "recomputed"]
    registry.unregister(str(first.spec.metadata.component_id))
    _verify(store, registry, workflow, workflow_ref, admission_ref)
    assert not first.database.exists()


@pytest.mark.parametrize("field", ["private", "extra", "fields_set"])
def test_behavior_relevant_private_and_extra_model_settings_are_not_ignored(
    tmp_path: Path, field: str
) -> None:
    store, original, registry, workflow, workflow_ref, _ref = _fixture(tmp_path)
    node = ConfiguredAdmissionNode(original.database)
    registry.register(node, override=True)
    ref = persist_workflow_execution_admission(
        store, workflow, registry, workflow_ref=workflow_ref, run_id="admission-run"
    )
    model = validate_core_model_json_artifact(WorkflowExecutionAdmission, store, ref)
    assert all(item.status == "recomputed" for item in model.nodes)
    if field == "private":
        node.settings._offset = 99
    elif field == "extra":
        node.settings.extra_offset = 99
    else:
        old = node.settings
        node.settings = AdmissionSettings(value=7, extra_offset=2)
        assert node.settings.__dict__ == old.__dict__
        assert node.settings.model_extra == old.model_extra
        assert node.settings._offset == old._offset
        assert node.settings.model_fields_set != old.model_fields_set
    with pytest.raises(ExecutionAdmissionError, match="residual_definition_changed"):
        _verify(store, registry, workflow, workflow_ref, ref)
    assert not node.database.exists()


@pytest.mark.parametrize(
    ("node_type", "reason"),
    [
        (RuntimeImportAdmissionNode, "execution_admission_runtime_import_not_established"),
        (NestedImportAdmissionNode, "execution_admission_runtime_import_not_established"),
        (DynamicImportAdmissionNode, "execution_admission_dynamic_dependency"),
        (BuiltinsImportAdmissionNode, "execution_admission_dynamic_dependency"),
    ],
)
def test_dynamic_source_resolution_is_explicitly_unsupported_before_effect(
    tmp_path: Path, node_type, reason: str
) -> None:
    store, original, registry, workflow, workflow_ref, _ref = _fixture(tmp_path)
    node = node_type(original.database)
    registry.register(node, override=True)
    ref = persist_workflow_execution_admission(
        store, workflow, registry, workflow_ref=workflow_ref, run_id="admission-run"
    )
    model = validate_core_model_json_artifact(WorkflowExecutionAdmission, store, ref)
    assert all(item.reason == reason for item in model.nodes)
    with pytest.raises(ExecutionAdmissionError, match="original_definition_not_established"):
        _verify(store, registry, workflow, workflow_ref, ref)
    assert not node.database.exists()


def _managed_wrapper():
    from polisyos.scientist.orchestration.engine.sub_workflow import (
        StateMapping,
        SubWorkflowConfig,
        SubWorkflowNode,
    )

    class NoChildLookupRegistry(NodeRegistry):
        def get(self, _node_id):
            raise AssertionError("terminal wrapper observation must not look up completed children")

        def values(self):
            raise AssertionError(
                "terminal wrapper observation must not enumerate completed children"
            )

    config = SubWorkflowConfig(
        workflow=WorkflowSpec(
            workflow_id="source_bound_child",
            nodes=[NodeInvocation(alias="done", node_id="scientist.node_unavailable_child@1.0.0")],
        ),
        input_mappings=[StateMapping(source_path="params.input", target_path="params.child_input")],
        output_mappings=[
            StateMapping(source_path="params.result", target_path="params.child_result")
        ],
    )
    return SubWorkflowNode(config, NoChildLookupRegistry(), alias="child")


def test_managed_wrapper_observation_excludes_completed_registry_and_roundtrips() -> None:
    from polisyos.scientist.orchestration.engine.execution_admission import (
        ManagedSubWorkflowDefinition,
        capture_managed_subworkflow_definition,
    )

    node = _managed_wrapper()
    observed = capture_managed_subworkflow_definition(node)
    assert observed.profile == "managed_subworkflow_wrapper_v1"
    assert observed.purpose == "candidate_wrapper_mapping_continuity"
    assert len(observed.definition_sha256) == 64
    assert ManagedSubWorkflowDefinition.model_validate_json(observed.model_dump_json()) == observed
    assert capture_managed_subworkflow_definition(_managed_wrapper()) == observed


def test_managed_wrapper_observation_matches_a_fresh_process_without_registry_lookup() -> None:
    from polisyos.scientist.orchestration.engine.execution_admission import (
        ManagedSubWorkflowDefinition,
        capture_managed_subworkflow_definition,
    )

    observed = capture_managed_subworkflow_definition(_managed_wrapper())
    command = (
        "from tests.unit.scientist.orchestration.engine.test_execution_admission "
        "import _managed_wrapper; "
        "from polisyos.scientist.orchestration.engine.execution_admission "
        "import capture_managed_subworkflow_definition; "
        "print(capture_managed_subworkflow_definition(_managed_wrapper()).model_dump_json())"
    )
    completed = subprocess.run(
        [sys.executable, "-B", "-c", command],
        capture_output=True,
        text=True,
        check=False,
        timeout=45,
        env={**os.environ, "PYTHONPATH": f"{Path.cwd() / 'src'}{os.pathsep}{Path.cwd()}"},
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert ManagedSubWorkflowDefinition.model_validate_json(completed.stdout) == observed


@pytest.mark.parametrize("change", ["alias", "input_mapping", "output_mapping", "child_workflow"])
def test_managed_wrapper_definition_tracks_actual_selected_configuration(change: str) -> None:
    from polisyos.scientist.orchestration.engine.execution_admission import (
        capture_managed_subworkflow_definition,
    )

    node = _managed_wrapper()
    original = capture_managed_subworkflow_definition(node)
    if change == "alias":
        node._alias = "other_child"
    elif change == "input_mapping":
        node._config.input_mappings[0].target_path = "params.different_input"
    elif change == "output_mapping":
        node._config.output_mappings[0].target_path = "params.different_output"
    else:
        node._config.workflow.nodes[0].params["different"] = True
    assert capture_managed_subworkflow_definition(node) != original


def test_managed_wrapper_definition_tracks_real_mapping_helper_replacement(monkeypatch) -> None:
    from polisyos.scientist.orchestration.engine import sub_workflow
    from polisyos.scientist.orchestration.engine.execution_admission import (
        capture_managed_subworkflow_definition,
    )

    node = _managed_wrapper()
    original = capture_managed_subworkflow_definition(node)
    # Use another real source-backed function from this actual module: source
    # reconciliation succeeds, so only the selected behavior/source binding
    # distinguishes this substitution.
    monkeypatch.setattr(sub_workflow, "_write_to_state", sub_workflow._set_nested)
    assert capture_managed_subworkflow_definition(node) != original


def test_managed_wrapper_refuses_forged_actual_helper_code(monkeypatch) -> None:
    from polisyos.scientist.orchestration.engine import sub_workflow
    from polisyos.scientist.orchestration.engine.execution_admission import (
        capture_managed_subworkflow_definition,
    )

    node = _managed_wrapper()
    original = sub_workflow._write_to_state
    forged_module = compile(
        "def forged(*args):\n    return None\n", original.__code__.co_filename, "exec"
    )
    forged = next(value for value in forged_module.co_consts if hasattr(value, "co_code"))
    monkeypatch.setattr(original, "__code__", forged)
    with pytest.raises(ExecutionAdmissionError, match="managed_subworkflow_source_not_established"):
        capture_managed_subworkflow_definition(node)


def test_managed_wrapper_observes_changed_spec_without_calling_it(monkeypatch) -> None:
    from polisyos.scientist.orchestration.engine import sub_workflow
    from polisyos.scientist.orchestration.engine.execution_admission import (
        capture_managed_subworkflow_definition,
    )

    node = _managed_wrapper()
    original = capture_managed_subworkflow_definition(node)
    calls = []

    def changed_spec(self):
        calls.append(self)
        raise AssertionError("an unverified changed getter must never run in the observer")

    monkeypatch.setattr(sub_workflow.SubWorkflowNode, "spec", property(changed_spec))
    assert capture_managed_subworkflow_definition(node) != original
    assert calls == []


def test_managed_wrapper_rejects_changed_method_descriptor_before_binding(monkeypatch) -> None:
    from polisyos.scientist.orchestration.engine import sub_workflow
    from polisyos.scientist.orchestration.engine.execution_admission import (
        capture_managed_subworkflow_definition,
    )

    node = _managed_wrapper()
    calls = []

    def changed_execute(self):
        calls.append(self)
        raise AssertionError("unverified dispatch descriptors must not execute")

    monkeypatch.setattr(sub_workflow.SubWorkflowNode, "execute", property(changed_execute))
    with pytest.raises(
        ExecutionAdmissionError, match="managed_subworkflow_dispatch_not_established"
    ):
        capture_managed_subworkflow_definition(node)
    assert calls == []
