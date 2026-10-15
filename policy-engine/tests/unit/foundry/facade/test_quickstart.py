from __future__ import annotations

import importlib
import sys

import pytest

from polisyos.common.canonical_profile import CanonicalProfileRefusalError
from polisyos.core.artifacts import validate_core_model_json_artifact
from polisyos.core.artifacts.manifest import ArtifactRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.contracts.fabric import DataSnapshot
from polisyos.core.contracts.foundry import (
    CompileResult,
    ExecPlan,
    FoundryInputBindings,
    ProgramGraph,
    ProgramGraphRef,
    ProgramNode,
    StateSnapshotRef,
)
from polisyos.core.registry import build_default_registry_bundle
from polisyos.foundry import compile as compile_foundry
from polisyos.foundry import compile_program, execute
from polisyos.foundry._quickstart import (
    prepare_trivial_input_bindings,
    run_feedback_compile_execute,
    run_feedback_multiplicity_demo,
    run_trivial_compile_execute,
)
from polisyos.foundry.contracts.state import GlobalState
from polisyos.foundry.data_plane.bindings import load_input_bindings
from polisyos.foundry.execute.executor import put_state_snapshot


def test_foundry_package_exports_docs_facing_api() -> None:
    importlib.import_module("polisyos.foundry.compile")
    importlib.import_module("polisyos.foundry.execute")
    assert compile_program is compile_foundry
    assert callable(execute)


def test_foundry_package_exports_docs_facing_api_when_submodule_imported_first(
    monkeypatch,
) -> None:
    for module_name in (
        "polisyos.foundry",
        "polisyos.foundry.compile",
        "polisyos.foundry.execute",
    ):
        monkeypatch.delitem(sys.modules, module_name, raising=False)

    foundry = importlib.import_module("polisyos.foundry")
    importlib.import_module("polisyos.foundry.compile")
    importlib.import_module("polisyos.foundry.execute")

    assert foundry.compile_program is foundry.compile
    assert callable(foundry.execute)


def test_run_trivial_compile_execute(tmp_path) -> None:
    result = run_trivial_compile_execute(cas_root=tmp_path)

    assert result.compile_ok is True
    assert result.execute_ok is True
    assert result.exec_plan_artifact_id is not None
    assert result.simulation_result_artifact_id is not None


def test_run_feedback_compile_execute(tmp_path) -> None:
    result = run_feedback_compile_execute(cas_root=tmp_path)

    assert result.compile_ok is True
    assert result.execute_ok is True
    assert result.exec_plan_artifact_id is not None
    assert result.simulation_result_artifact_id is not None
    assert result.feedback_result_artifact_id is not None
    assert result.feedback_convergence_certificate_artifact_id is not None


@pytest.mark.parametrize(
    "runner",
    [run_feedback_compile_execute, run_feedback_multiplicity_demo],
)
def test_feedback_quickstart_reports_missing_exec_plan_without_loading_none(
    runner, tmp_path, monkeypatch
) -> None:
    import polisyos.foundry._quickstart as quickstart

    report_ref = ArtifactRef(
        artifact_id="sha256:" + "a" * 64,
        kind="foundry.compile_report",
        media_type="application/json",
    )
    monkeypatch.setattr(
        quickstart,
        "compile_foundry",
        lambda store, request: CompileResult(ok=False, compile_report_ref=report_ref),
    )

    result = runner(cas_root=tmp_path)

    assert result.compile_ok is False
    assert result.execute_ok is False
    assert result.exec_plan_artifact_id is None
    assert result.simulation_result_artifact_id is None
    assert result.feedback_result_artifact_id is None
    assert result.feedback_convergence_certificate_artifact_id is None


def test_quickstart_input_bindings_persist_owner_schema_for_fresh_reader(tmp_path) -> None:
    cas_root = tmp_path / "cas"
    writer = FileSystemCAS(cas_root)
    registry_bundle = build_default_registry_bundle(writer)

    state_ref = put_state_snapshot(
        writer,
        state=GlobalState.empty(n_agents=2, n_firms=1),
        step=0,
    )
    legacy_snapshot_ref = writer.put_json(
        DataSnapshot(data_ref=StateSnapshotRef(artifact_id=state_ref.artifact_id)),
        PutOptions(
            kind=DataSnapshot.ARTIFACT_KIND,
            media_type=DataSnapshot.ARTIFACT_MEDIA_TYPE,
        ),
    )
    assert writer.get_manifest(legacy_snapshot_ref).artifact_schema is None
    state_snapshot_ref = StateSnapshotRef(artifact_id=state_ref.artifact_id)
    selected_snapshot_ref = writer.put_json(
        DataSnapshot(data_ref=state_snapshot_ref),
        PutOptions(
            kind=DataSnapshot.ARTIFACT_KIND,
            media_type=DataSnapshot.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=DataSnapshot.ARTIFACT_SCHEMA_NAME,
                version=DataSnapshot.ARTIFACT_SCHEMA_VERSION,
            ),
        ),
        return_selected_profile=True,
    )
    legacy_bindings_ref = writer.put_json(
        FoundryInputBindings(
            data_snapshot_ref=selected_snapshot_ref,
            registry_bundle_ref=registry_bundle.bundle_ref,
            rules=[],
            bound_state_snapshot_ref=state_snapshot_ref,
        ),
        PutOptions(
            kind=FoundryInputBindings.ARTIFACT_KIND,
            media_type=FoundryInputBindings.ARTIFACT_MEDIA_TYPE,
        ),
    )
    assert writer.get_manifest(legacy_bindings_ref).artifact_schema is None

    bindings_ref = prepare_trivial_input_bindings(writer, registry_bundle.bundle_ref)

    reader = FileSystemCAS(cas_root)
    manifest = reader.get_manifest(bindings_ref)
    assert bindings_ref.manifest_profile_sha256 is not None
    assert reader.get_manifest(legacy_snapshot_ref).artifact_schema is None
    assert reader.get_manifest(legacy_bindings_ref).artifact_schema is None
    assert manifest.artifact_schema == SchemaInfo(
        name=FoundryInputBindings.ARTIFACT_SCHEMA_NAME,
        version=FoundryInputBindings.ARTIFACT_SCHEMA_VERSION,
    )
    loaded = load_input_bindings(reader, bindings_ref)
    assert loaded.registry_bundle_ref.artifact_id == registry_bundle.bundle_ref.artifact_id
    assert loaded.data_snapshot_ref.manifest_profile_sha256 is not None
    snapshot_edge = next(edge for edge in manifest.inputs if edge.role == "input.data_snapshot_ref")
    assert loaded.data_snapshot_ref.manifest_profile_sha256 == (
        snapshot_edge.manifest_profile_sha256
    )
    loaded_snapshot = validate_core_model_json_artifact(
        DataSnapshot, reader, loaded.data_snapshot_ref
    )
    assert loaded_snapshot.data_ref.manifest_profile_sha256 is not None
    snapshot_manifest = reader.get_manifest(loaded.data_snapshot_ref)
    nested_data_edges = [edge for edge in snapshot_manifest.inputs if edge.role == "data_ref"]
    assert len(nested_data_edges) == 1
    assert nested_data_edges[0].artifact_id == loaded_snapshot.data_ref.artifact_id
    assert nested_data_edges[0].manifest_profile_sha256 == (
        loaded_snapshot.data_ref.manifest_profile_sha256
    )
    with pytest.raises(CanonicalProfileRefusalError):
        validate_core_model_json_artifact(DataSnapshot, reader, legacy_snapshot_ref)
    with pytest.raises(CanonicalProfileRefusalError):
        load_input_bindings(reader, legacy_bindings_ref)


def test_run_feedback_multiplicity_demo(tmp_path) -> None:
    result = run_feedback_multiplicity_demo(cas_root=tmp_path)

    assert result.compile_ok is True
    assert result.execute_ok is True
    assert result.feedback_result_artifact_id is not None
    assert result.feedback_convergence_certificate_artifact_id is not None
    assert result.equilibrium_multiplicity_report_artifact_id is not None


def test_quickstart_feedback_loader_rejects_program_version_drift(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    graph = ProgramGraph(
        ir_ref=ArtifactRef(
            artifact_id="sha256:" + "a" * 64,
            kind="ir.trinity_bundle",
            media_type="application/json",
        ),
        nodes=[ProgramNode(node_id="tax", mechanism_type="income_tax")],
    )
    graph_payload = graph.model_dump(mode="json")
    graph_payload["schema_version"] = "0.3"
    graph_ref = store.put_json(
        graph_payload,
        PutOptions(
            kind=ProgramGraph.ARTIFACT_KIND,
            media_type=ProgramGraph.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=ProgramGraph.ARTIFACT_SCHEMA_NAME,
                version=ProgramGraph.ARTIFACT_SCHEMA_VERSION,
            ),
        ),
    )
    plan = ExecPlan(
        program_ref=ProgramGraphRef(artifact_id=graph_ref.artifact_id),
        order=["tax"],
    )
    plan_ref = store.put_json(
        plan,
        PutOptions(
            kind=ExecPlan.ARTIFACT_KIND,
            media_type=ExecPlan.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=ExecPlan.ARTIFACT_SCHEMA_NAME,
                version=ExecPlan.ARTIFACT_SCHEMA_VERSION,
            ),
        ),
    )

    from polisyos.foundry._quickstart import prepare_trivial_feedback_config

    with pytest.raises(
        CanonicalProfileRefusalError,
        match="canon_profile_typed_artifact_schema_version_mismatch",
    ):
        prepare_trivial_feedback_config(store, exec_plan_ref=plan_ref)
