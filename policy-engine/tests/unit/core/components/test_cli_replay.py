from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from polisyos.core.artifacts import store as store_module
from polisyos.core.artifacts._transfer_ops import ImportReport
from polisyos.core.artifacts.graph import resolve_dependency_graph
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import (
    ArtifactRef,
    ArtifactTenantContextInfo,
    InputRef,
    SchemaInfo,
    input_ref_from_artifact_ref,
)
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.components import _cli_replay
from polisyos.scientist.replay.deterministic import completeness_check
from tools.ops_runners.runtime_cli import main


def _build_replay_bundle(
    store: FileSystemCAS,
    bundle_path: Path,
    *,
    run_id: str,
    tenant_id: str | None = None,
    cell_id: str | None = None,
) -> tuple[ArtifactRef, set[str]]:
    """Build a replay packet and export its real selected CAS dependency graph."""
    tenant_context = (
        ArtifactTenantContextInfo(tenant_id=tenant_id, cell_id=cell_id)
        if tenant_id is not None
        else None
    )
    artifact_inputs = {
        "registry_bundle_ref": ("core.registry_bundle", {"registry": {}, "run_id": run_id}),
        "input_bindings_ref": ("foundry.input_bindings", {"bindings": [], "run_id": run_id}),
        "state_snapshot_ref": ("foundry.state_snapshot", {"state": {}, "run_id": run_id}),
        "exec_plan_ref": ("foundry.exec_plan", {"order": [], "run_id": run_id}),
        "lowered_ir_ref": ("foundry.lowered_ir", {"nodes": [], "run_id": run_id}),
    }
    refs = {
        role: store.put_json(
            payload,
            PutOptions(kind=kind, media_type="application/json", tenant_context=tenant_context),
        )
        for role, (kind, payload) in artifact_inputs.items()
    }
    packet_ref = store.put_json(
        {
            "schema_version": "3.0",
            "run_id": run_id,
            "seed": 123,
            "inputs": {
                "registry_bundle_ref": str(refs["registry_bundle_ref"].artifact_id),
                "input_bindings_ref": str(refs["input_bindings_ref"].artifact_id),
                "state_snapshot_ref": str(refs["state_snapshot_ref"].artifact_id),
            },
            "artifacts": {
                "exec_plan_ref": str(refs["exec_plan_ref"].artifact_id),
                "lowered_ir_ref": str(refs["lowered_ir_ref"].artifact_id),
            },
        },
        PutOptions(
            kind="scientist.decision_packet",
            media_type="application/json",
            tenant_context=tenant_context,
            inputs=[InputRef(artifact_id=ref.artifact_id, role=role) for role, ref in refs.items()],
        ),
    )
    graph = resolve_dependency_graph(store, packet_ref.artifact_id)
    expected_ids = {str(artifact_id) for artifact_id in graph.all_artifact_ids()}
    export_report = store.export_subgraph(graph.all_artifact_ids(), bundle_path, compress=False)
    assert export_report.exported_artifacts == len(expected_ids)
    assert not export_report.missing_artifacts
    return packet_ref, expected_ids


def _build_executable_foundry_packet(
    store: FileSystemCAS,
    *,
    default_bindings_schema: str | None = None,
    qualified_source: bool = True,
    legacy_packet: bool = False,
) -> ArtifactRef:
    """Create a packet through Foundry's real registry, compiler, and input producers."""
    from decimal import Decimal

    from polisyos.core.artifacts import ensure_ir_artifact_store
    from polisyos.core.contracts.fabric import DataSnapshot
    from polisyos.core.contracts.foundry import (
        CompileRequest,
        ExecuteRequest,
        FoundryExecConfig,
        FoundryInputBindings,
        StateSnapshotRef,
    )
    from polisyos.core.registry import build_default_registry_bundle, load_registry_bundle_content
    from polisyos.foundry.compile.api import compile as compile_foundry
    from polisyos.foundry.contracts.state import GlobalState
    from polisyos.foundry.data_plane import build_input_bindings
    from polisyos.foundry.execute import execute as execute_foundry
    from polisyos.foundry.execute.executor import put_state_snapshot
    from polisyos.ir.governance.policy_spec import InterventionSpec, PolicySpec
    from polisyos.ir.governance.problem_frame import ProblemDomain, ProblemFrame
    from polisyos.ir.governance.schedule import ScheduleSpec
    from polisyos.ir.governance.selector_expr import SelectorPredicate
    from polisyos.ir.model_layer.model_spec import ModelSpec
    from polisyos.ir.model_layer.types import SelectorOperator
    from polisyos.ir.trinity import (
        TrinityBundle,
        load_trinity_bundle_artifact,
        persist_trinity_bundle_artifact,
    )
    from polisyos.scientist.policy_design.schema import (
        PolicyCandidateSchema,
        TargetPopulationSpec,
        persist_policy_candidate_schema,
    )

    registry = build_default_registry_bundle(store, return_selected_profile=True)
    load_registry_bundle_content(store, registry.bundle_ref)
    state_blob = put_state_snapshot(
        store,
        state=GlobalState.empty(n_agents=2, n_firms=1),
        step=0,
        return_selected_profile=True,
    )
    state_ref = StateSnapshotRef.model_validate(state_blob.model_dump(mode="python"))
    data_snapshot = store.put_json(
        DataSnapshot(data_ref=state_ref),
        PutOptions(
            kind=DataSnapshot.ARTIFACT_KIND,
            media_type="application/json",
            schema=SchemaInfo(
                name=DataSnapshot.ARTIFACT_SCHEMA_NAME,
                version=DataSnapshot.ARTIFACT_SCHEMA_VERSION,
            ),
            inputs=[input_ref_from_artifact_ref(state_ref, role="data_ref")],
        ),
        return_selected_profile=True,
    )
    policy = TrinityBundle(
        problem_frame=ProblemFrame(problem_id="rep_01_replay", domain=ProblemDomain.FISCAL),
        policy_spec=PolicySpec(
            policy_id="rep_01_replay_policy",
            interventions=[
                InterventionSpec(
                    intervention_id="rep_01_tax_cut",
                    kind="income_tax",
                    target=SelectorPredicate(
                        field="id",
                        operator=SelectorOperator.EQUALS,
                        value="all",
                    ),
                    schedule=ScheduleSpec(start_step=0, duration_steps=1),
                    params={"rate": Decimal("0.1")},
                )
            ],
        ),
        model_spec=ModelSpec(
            model_id="rep_01_model",
            data_snapshot_ref=str(data_snapshot.artifact_id),
            registry_bundle_ref=str(registry.bundle_ref.artifact_id),
        ),
    )
    qualified_source = qualified_source and not legacy_packet
    if qualified_source:
        candidate_ref = persist_policy_candidate_schema(
            store,
            PolicyCandidateSchema(
                candidate_id="rep01_controlled_candidate",
                trinity_bundle=policy,
                target_population=TargetPopulationSpec(
                    population_id="rep01_controlled_agents",
                    description="Two synthetic agents in the declared native replay fixture.",
                ),
            ),
            inputs=[
                input_ref_from_artifact_ref(data_snapshot, role="world_model_data_snapshot"),
                input_ref_from_artifact_ref(registry.bundle_ref, role="world_model_registry"),
            ],
            return_selected_profile=True,
        )
        ir_store = ensure_ir_artifact_store(store)
        persisted_policy = persist_trinity_bundle_artifact(
            ir_store,
            policy,
            inputs=[input_ref_from_artifact_ref(candidate_ref, role="policy_candidate")],
        )
        read_policy = load_trinity_bundle_artifact(ir_store, persisted_policy)
        assert read_policy.policy_spec.policy_id == policy.policy_spec.policy_id
        assert read_policy.model_spec.data_snapshot_ref == str(data_snapshot.artifact_id)
        policy_ref = ArtifactRef.model_validate(persisted_policy.model_dump(mode="json"))
    else:
        # The supported candidate route predates selected execution-source basis.
        policy_ref = store.put_json(
            policy,
            PutOptions(
                kind=TrinityBundle.ARTIFACT_KIND,
                media_type=TrinityBundle.ARTIFACT_MEDIA_TYPE,
                schema=SchemaInfo(
                    name=TrinityBundle.ARTIFACT_SCHEMA_NAME,
                    version=TrinityBundle.ARTIFACT_SCHEMA_VERSION,
                ),
            ),
            return_selected_profile=True,
        )
    compile_result = compile_foundry(
        store,
        CompileRequest(
            input_kind="trinity",
            policy_ref=policy_ref,
            registry_bundle_ref=registry.bundle_ref,
            return_selected_profile=True,
        ),
    )
    assert compile_result.ok, compile_result.notes
    assert compile_result.exec_plan_ref is not None
    lowered_ir_ref = next(
        item.ref for item in compile_result.derived_refs if item.role == "lowered_ir"
    )
    program_graph_ref = next(
        item.ref for item in compile_result.derived_refs if item.role == "program_graph"
    )

    class FirstBindingsDefaultControl:
        """Prepublish only the adversarial view of the real producer's exact bytes."""

        def __getattr__(self, name: str):
            return getattr(store, name)

        def put_json(self, value, options, *, return_selected_profile=False):
            if options.kind == FoundryInputBindings.ARTIFACT_KIND:
                assert options.schema is not None
                store.put_json(
                    value,
                    replace(
                        options,
                        schema=SchemaInfo(
                            name=default_bindings_schema, version=options.schema.version
                        ),
                    ),
                    return_selected_profile=True,
                )
            return store.put_json(value, options, return_selected_profile=return_selected_profile)

    built = build_input_bindings(
        FirstBindingsDefaultControl() if default_bindings_schema is not None else store,
        data_snapshot_ref=data_snapshot,
        registry_bundle_ref=registry.bundle_ref,
        return_selected_profile=True,
    )
    input_bindings = built.input_bindings_ref
    packet_inputs = {
        "registry_bundle_ref": registry.bundle_ref,
        "input_bindings_ref": input_bindings,
        "data_snapshot_ref": data_snapshot,
        "state_snapshot_ref": built.bound_state_snapshot_ref,
        "trinity_bundle_ref": policy_ref,
    }
    packet_artifacts = {
        "exec_plan_ref": compile_result.exec_plan_ref,
        "lowered_ir_ref": lowered_ir_ref,
        "program_graph_ref": program_graph_ref,
    }
    if qualified_source:
        original = execute_foundry(
            store,
            ExecuteRequest(
                exec_plan_ref=compile_result.exec_plan_ref,
                input_bindings_ref=input_bindings,
                registry_bundle_ref=registry.bundle_ref,
                exec_config=FoundryExecConfig(seed=17, capture_env=True),
                return_selected_profile=True,
            ),
        )
        assert original.ok and original.simulation_result_ref is not None, original.notes
        packet_artifacts["simulation_result_ref"] = original.simulation_result_ref
    payload = {
        "schema_version": "3.0",
        "run_id": "R_rep_01_cli_replay",
        "seed": 17,
        "inputs": {name: str(ref.artifact_id) for name, ref in packet_inputs.items()},
        "artifacts": {name: str(ref.artifact_id) for name, ref in packet_artifacts.items()},
    }
    return store.put_json(
        payload,
        PutOptions(
            kind="scientist.decision_packet",
            media_type="application/json",
            inputs=[
                input_ref_from_artifact_ref(
                    ref.model_copy(update={"manifest_profile_sha256": None})
                    if legacy_packet
                    else ref,
                    role=role,
                )
                for role, ref in (*packet_inputs.items(), *packet_artifacts.items())
            ],
        ),
        return_selected_profile=True,
    )


def _run_existing_store_export(
    *,
    store: FileSystemCAS,
    packet_id: ArtifactID,
    report: ImportReport,
    export_path: Path,
    as_json: bool,
) -> int:
    """Exercise the actual replay consumer with a real report and existing CAS."""
    return _cli_replay._cmd_replay_with_store(
        args=SimpleNamespace(export=str(export_path), check_only=False, json=as_json),
        store=store,
        packet_ref=packet_id,
        completeness_check=completeness_check,
        VerificationConfig=None,
        VerificationMode=None,
        ReplayStrategy=None,
        import_report=report,
    )


def _payload_ref_ids(payload: dict[str, object], field: str) -> set[str]:
    report_payload = payload["bundle_import"]
    assert isinstance(report_payload, dict)
    refs = report_payload[field]
    assert isinstance(refs, list)
    return {str(ref["artifact_id"]) for ref in refs if isinstance(ref, dict)}


def test_replay_cli_runs_native_foundry_replay_and_persists_result(
    tmp_path: Path,
    capsys,
) -> None:
    """The ordinary non-dry CLI path executes Foundry and leaves a readable result."""
    store = FileSystemCAS(tmp_path / "cas")
    packet_ref = _build_executable_foundry_packet(store)
    # Compiler diagnostics belong to setup; the CLI must itself emit one JSON value.
    capsys.readouterr()

    exit_code = main(
        [
            "replay",
            str(packet_ref.artifact_id),
            "--cas-root",
            str(store.root),
            "--mode",
            "skip",
            "--no-verify",
            "--json",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.err == ""
    payload = json.loads(captured.out)
    assert payload["success"] is True
    assert payload["strategy"] == "foundry"
    assert payload["errors"] == []
    result_id = payload["replay_simulation_result_ref"]
    assert isinstance(result_id, str)
    result_manifest = FileSystemCAS(store.root).get_manifest(result_id)
    assert result_manifest.kind == "foundry.simulation_result"


def _fresh_replay_cli(
    store: FileSystemCAS,
    *arguments: str,
    protect_json: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Invoke the actual registered CLI from a fresh process on this checkout."""
    product = Path(__file__).resolve().parents[4]
    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join((str(product / "src"), str(product)))
    command = [sys.executable, "-B", "-m", "tools.ops_runners.runtime_cli", *arguments]
    if not protect_json:
        # A test-only removal of the real stream boundary; execution stays native.
        command = [
            sys.executable,
            "-B",
            "-c",
            "import sys; from contextlib import nullcontext; "
            "from polisyos.core.components import _cli_replay; "
            "_cli_replay._library_output = lambda _as_json: nullcontext(); "
            "from tools.ops_runners.runtime_cli import main; "
            "raise SystemExit(main(sys.argv[1:]))",
            *arguments,
        ]
    return subprocess.run(
        command,
        cwd=product,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )


def _manifest_members(store: FileSystemCAS) -> set[str]:
    """Observe published artifact views in this small, owned native fixture."""
    return {str(path.relative_to(store.root)) for path in store.root.rglob("*.manifest.json")}


def _fresh_cli_json(result: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    """Retain complete child diagnostics when its public JSON stream is malformed."""
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        pytest.fail(
            f"CLI JSON decoding failed ({exc}); exit={result.returncode}\n"
            f"complete stdout:\n{result.stdout}\ncomplete stderr:\n{result.stderr}"
        )
    assert isinstance(value, dict), value
    return value


def test_fresh_cli_checks_then_executes_real_compiled_packet_with_skipped_verification(
    tmp_path: Path,
) -> None:
    """A real compiled graph reaches a fresh CLI and backend, with explicit SKIP."""
    store = FileSystemCAS(tmp_path / "cas")
    packet_ref = _build_executable_foundry_packet(store)
    packet_bytes = store.get_bytes(packet_ref)
    before_check = _manifest_members(store)

    checked = _fresh_replay_cli(
        store,
        "replay",
        str(packet_ref.artifact_id),
        "--cas-root",
        str(store.root),
        "--check-only",
        "--json",
    )
    assert checked.returncode == 0, f"stdout={checked.stdout}\nstderr={checked.stderr}"
    completeness = _fresh_cli_json(checked)
    assert completeness["level"] == "complete"
    assert completeness["strategy"] == "foundry"
    assert completeness["missing"] == completeness["corrupted"] == []
    assert _manifest_members(store) == before_check

    replayed = _fresh_replay_cli(
        store,
        "replay",
        str(packet_ref.artifact_id),
        "--cas-root",
        str(store.root),
        "--mode",
        "skip",
        "--json",
    )
    assert replayed.returncode == 0, replayed.stderr
    payload = _fresh_cli_json(replayed)
    assert payload["success"] is True
    assert payload["strategy"] == "foundry"
    assert payload["errors"] == []
    assert "method_registered" not in replayed.stdout
    assert "method_registered" in replayed.stderr
    assert payload["verification"] == {
        "passed": False,
        "skipped": True,
        "mode": "skip",
        "details": {"reason": "verification_skipped"},
    }
    fresh = FileSystemCAS(store.root)
    result_ref = payload["replay_simulation_result_ref"]
    selected_result = ArtifactRef.model_validate(
        payload["replay_artifact_refs"]["simulation_result"]
    )
    assert str(selected_result.artifact_id) == result_ref
    assert selected_result.manifest_profile_sha256 is not None
    assert fresh.get_manifest(result_ref).kind == "foundry.simulation_result"
    assert fresh.get_bytes(selected_result)
    assert fresh.get_bytes(packet_ref) == packet_bytes
    assert _manifest_members(fresh) > before_check

    unprotected = _fresh_replay_cli(
        store,
        "replay",
        str(packet_ref.artifact_id),
        "--cas-root",
        str(store.root),
        "--mode",
        "skip",
        "--json",
        protect_json=False,
    )
    assert unprotected.returncode == 0, unprotected.stderr
    assert "method_registered" in unprotected.stdout
    with pytest.raises(json.JSONDecodeError):
        json.loads(unprotected.stdout)


def test_fresh_cli_replay_uses_packet_selected_input_view_instead_of_valid_default(
    tmp_path: Path,
) -> None:
    """A first-writer default cannot replace the packet's exact selected input."""
    from polisyos.core.artifacts import artifact_manifest_profile_sha256
    from polisyos.core.contracts.foundry import FoundryInputBindings, SimulationResultRef
    from polisyos.foundry.data_plane import load_input_bindings
    from polisyos.foundry.execute import admit_execution_source

    store = FileSystemCAS(tmp_path / "cas")
    packet_ref = _build_executable_foundry_packet(
        store, default_bindings_schema="rep01.other_bindings_schema"
    )
    packet_manifest = store.get_manifest(packet_ref)
    edge = next(item for item in packet_manifest.inputs if item.role == "input_bindings_ref")
    selected = ArtifactRef(
        artifact_id=edge.artifact_id,
        kind=FoundryInputBindings.ARTIFACT_KIND,
        media_type="application/json",
        manifest_profile_sha256=edge.manifest_profile_sha256,
    )
    default_manifest = store.get_manifest(selected.artifact_id)
    assert default_manifest.artifact_schema is not None
    assert default_manifest.artifact_schema.name == "rep01.other_bindings_schema"
    assert artifact_manifest_profile_sha256(default_manifest) != selected.manifest_profile_sha256
    assert store.verify(selected.artifact_id).ok
    assert store.verify(selected).ok
    assert load_input_bindings(store, selected).registry_bundle_ref is not None
    with pytest.raises(ValueError, match="canon_profile_typed_artifact_schema_name_mismatch"):
        load_input_bindings(store, selected.model_copy(update={"manifest_profile_sha256": None}))
    original_edge = next(
        item for item in packet_manifest.inputs if item.role == "simulation_result_ref"
    )
    original_source = admit_execution_source(
        store,
        SimulationResultRef(
            artifact_id=original_edge.artifact_id,
            manifest_profile_sha256=original_edge.manifest_profile_sha256,
        ),
    )
    assert original_source.basis is not None

    replayed = _fresh_replay_cli(
        store,
        "replay",
        str(packet_ref.artifact_id),
        "--cas-root",
        str(store.root),
        "--mode",
        "skip",
        "--json",
    )
    assert replayed.returncode == 0, f"stdout={replayed.stdout}\nstderr={replayed.stderr}"
    observed = _fresh_cli_json(replayed)
    assert observed["success"] is True
    assert observed["completeness"]["level"] == "complete"
    fresh = FileSystemCAS(store.root)
    simulation_manifest = fresh.get_manifest(observed["replay_simulation_result_ref"])
    selected_result = ArtifactRef.model_validate(
        observed["replay_artifact_refs"]["simulation_result"]
    )
    assert selected_result.manifest_profile_sha256 is not None
    assert fresh.get_manifest(selected_result) == simulation_manifest
    replay_source = admit_execution_source(
        fresh, SimulationResultRef.model_validate(selected_result.model_dump(mode="python"))
    )
    assert replay_source.basis is not None
    assert (
        replay_source.basis.request_exec_config_fields_set
        == original_source.basis.request_exec_config_fields_set
    )
    for field in type(original_source.basis).model_fields:
        if field.startswith("effective_"):
            assert getattr(replay_source.basis, field) == getattr(original_source.basis, field), (
                field
            )
    plan = next(item for item in packet_manifest.inputs if item.role == "exec_plan_ref")
    execution_plan = next(item for item in simulation_manifest.inputs if item.role == "exec_plan")
    assert execution_plan.artifact_id == plan.artifact_id
    assert execution_plan.manifest_profile_sha256 == plan.manifest_profile_sha256
    assert fresh.get_bytes(selected) == store.get_bytes(selected)


@pytest.mark.parametrize("legacy_packet", [True, False], ids=["id-only", "selected-inputs"])
def test_fresh_cli_preserves_candidate_replay_without_claiming_execution_source(
    tmp_path: Path, legacy_packet: bool
) -> None:
    """Both bounded candidate modes execute without claiming a stronger result view."""
    store = FileSystemCAS(tmp_path / "cas")
    packet_ref = _build_executable_foundry_packet(
        store,
        qualified_source=False,
        legacy_packet=legacy_packet,
        default_bindings_schema=None if legacy_packet else "rep01.other_bindings_schema",
    )
    if legacy_packet:
        checked = _fresh_replay_cli(
            store,
            "replay",
            str(packet_ref.artifact_id),
            "--cas-root",
            str(store.root),
            "--check-only",
            "--json",
        )
        assert checked.returncode == 0, f"stdout={checked.stdout}\nstderr={checked.stderr}"
        completeness = _fresh_cli_json(checked)
        assert completeness["level"] == "complete"
        assert "legacy_payload_reference_profiles_not_established" in completeness["reason_codes"]
    replayed = _fresh_replay_cli(
        store,
        "replay",
        str(packet_ref.artifact_id),
        "--cas-root",
        str(store.root),
        "--mode",
        "skip",
        "--json",
    )
    assert replayed.returncode == 0, f"stdout={replayed.stdout}\nstderr={replayed.stderr}"
    payload = _fresh_cli_json(replayed)
    assert payload["success"] is True
    assert payload["errors"] == []
    assert "original_execution_source_not_established:legacy_candidate" in payload["warnings"]
    assert "replay_output_profile_not_established:simulation_result" in payload["warnings"]
    legacy_warning = any(
        value.startswith("legacy_payload_reference_profiles_not_established:")
        for value in payload["warnings"]
    )
    assert legacy_warning is legacy_packet
    output_ref = ArtifactRef.model_validate(payload["replay_artifact_refs"]["simulation_result"])
    assert output_ref.manifest_profile_sha256 is None
    assert FileSystemCAS(store.root).get_bytes(output_ref)


@pytest.mark.parametrize("shared_dag", [False, True], ids=["new-leaf", "shared-leaf"])
def test_legacy_completeness_shares_merged_node_and_root_relative_depth_limits(
    tmp_path: Path,
    shared_dag: bool,
) -> None:
    """The weaker reader bounds work conservatively even if a shared union would fit."""
    from polisyos.scientist.replay.deterministic import CompletenessLevel

    store = FileSystemCAS(tmp_path / "cas")
    child = store.put_json(
        {"source": 1}, PutOptions(kind="test.source", media_type="application/json")
    )
    second_inputs = []
    if shared_dag:
        extra = store.put_json(
            {"source": 2}, PutOptions(kind="test.source", media_type="application/json")
        )
        second_inputs = [
            InputRef(artifact_id=child.artifact_id, role="shared_source"),
            InputRef(artifact_id=extra.artifact_id, role="new_source"),
        ]
    refs = {
        "registry_bundle_ref": store.put_json(
            {"registry": {}},
            PutOptions(
                kind="core.registry_bundle",
                media_type="application/json",
                inputs=[InputRef(artifact_id=child.artifact_id, role="source")],
            ),
        ),
        "input_bindings_ref": store.put_json(
            {"bindings": []},
            PutOptions(
                kind="foundry.input_bindings", media_type="application/json", inputs=second_inputs
            ),
        ),
        "exec_plan_ref": store.put_json(
            {"order": []}, PutOptions(kind="foundry.exec_plan", media_type="application/json")
        ),
        "lowered_ir_ref": store.put_json(
            {"nodes": []}, PutOptions(kind="foundry.lowered_ir", media_type="application/json")
        ),
    }
    packet_ref = store.put_json(
        {
            "inputs": {
                name: str(refs[name].artifact_id)
                for name in ("registry_bundle_ref", "input_bindings_ref")
            },
            "artifacts": {
                name: str(refs[name].artifact_id) for name in ("exec_plan_ref", "lowered_ir_ref")
            },
        },
        PutOptions(
            kind="scientist.decision_packet",
            media_type="application/json",
            inputs=[InputRef(artifact_id=ref.artifact_id, role=role) for role, ref in refs.items()],
        ),
    )
    complete = completeness_check(store, packet_ref.artifact_id)
    assert complete.level is CompletenessLevel.COMPLETE
    assert complete.total_artifacts == 6 + int(shared_dag)
    with pytest.raises(ValueError, match="final union feasibility not established"):
        completeness_check(store, packet_ref.artifact_id, max_nodes=7 if shared_dag else 5)
    if shared_dag:
        less_conservative = completeness_check(store, packet_ref.artifact_id, max_nodes=8)
        assert less_conservative.level is CompletenessLevel.COMPLETE
        assert less_conservative.total_artifacts == 7
    bounded = completeness_check(store, packet_ref.artifact_id, max_depth=1)
    assert bounded.level is not CompletenessLevel.COMPLETE
    assert bounded.graph is not None
    assert all(node.depth <= 1 for node in bounded.graph.nodes.values() if node.is_present)
    registry_id = refs["registry_bundle_ref"].artifact_id
    digest = registry_id.hex
    blob = store.root / "artifacts" / "sha256" / digest[:2] / digest[2:4] / f"{digest}.blob"
    original = blob.read_bytes()
    try:
        blob.write_bytes(original + b"tamper")
        corrupted = completeness_check(store, packet_ref.artifact_id)
        assert corrupted.level is CompletenessLevel.INCOMPLETE
        assert any(item.artifact_id == str(registry_id) for item in corrupted.corrupted)
    finally:
        blob.write_bytes(original)


@pytest.mark.parametrize("damage", ["payload_id", "multiple_profiles", "partly_selected"])
def test_fresh_cli_refuses_ambiguous_or_unbound_selected_packet_roles(
    tmp_path: Path, damage: str
) -> None:
    """Real compiled packets cannot hide mismatched/ambiguous consumed CAS edges."""
    from polisyos.core.artifacts import (
        artifact_manifest_profile_sha256,
        load_core_json_artifact,
    )

    store = FileSystemCAS(tmp_path / "cas")
    packet_ref = _build_executable_foundry_packet(
        store,
        qualified_source=False,
        default_bindings_schema="rep01.other_bindings_schema",
    )
    manifest = store.get_manifest(packet_ref)
    payload = load_core_json_artifact(store, packet_ref)
    payload["run_id"] += "_" + damage
    edges = [edge.model_copy(deep=True) for edge in manifest.inputs]
    target = next(edge for edge in edges if edge.role == "input_bindings_ref")
    if damage == "payload_id":
        payload["inputs"]["input_bindings_ref"] = payload["inputs"]["registry_bundle_ref"]
    elif damage == "multiple_profiles":
        default = store.get_manifest(target.artifact_id)
        other_profile = artifact_manifest_profile_sha256(default)
        assert other_profile != target.manifest_profile_sha256
        edges.append(target.model_copy(update={"manifest_profile_sha256": other_profile}))
    else:
        edges = [
            edge.model_copy(update={"manifest_profile_sha256": None}) if edge is target else edge
            for edge in edges
        ]
    damaged = store.put_json(
        payload,
        PutOptions(kind=manifest.kind, media_type="application/json", inputs=edges),
        return_selected_profile=True,
    )
    before = _manifest_members(store)
    refused = _fresh_replay_cli(
        store,
        "replay",
        str(damaged.artifact_id),
        "--cas-root",
        str(store.root),
        "--mode",
        "skip",
        "--json",
    )
    assert refused.returncode == 1, refused.stderr
    observed = _fresh_cli_json(refused)
    assert observed["success"] is False
    assert observed["completeness"]["level"] == "incomplete"
    assert any(
        reason.startswith("replay_input_binding_")
        for reason in observed["completeness"]["reason_codes"]
    )
    assert observed["replay_simulation_result_ref"] is None
    assert observed["replay_artifact_refs"] == {}
    assert observed["verification"] is None
    assert _manifest_members(store) == before


def test_fresh_cli_refuses_seed_override_of_admitted_original_execution_source(
    tmp_path: Path,
) -> None:
    """A packet cannot claim seed 18 while reusing the original seed-17 execution."""
    from polisyos.core.artifacts import load_core_json_artifact

    store = FileSystemCAS(tmp_path / "cas")
    original_packet = _build_executable_foundry_packet(store)
    manifest = store.get_manifest(original_packet)
    payload = load_core_json_artifact(store, original_packet)
    payload["run_id"] += "_seed_override"
    payload["replay"] = {"effective_seed": 18}
    packet_ref = store.put_json(
        payload,
        PutOptions(kind=manifest.kind, media_type="application/json", inputs=manifest.inputs),
        return_selected_profile=True,
    )
    before = _manifest_members(store)
    refused = _fresh_replay_cli(
        store,
        "replay",
        str(packet_ref.artifact_id),
        "--cas-root",
        str(store.root),
        "--mode",
        "skip",
        "--json",
    )
    assert refused.returncode == 1, refused.stderr
    observed = _fresh_cli_json(refused)
    assert observed["success"] is False
    assert any(
        "replay_seed_disagrees_with_execution_source" in error for error in observed["errors"]
    )
    assert observed["replay_simulation_result_ref"] is None
    assert observed["replay_artifact_refs"] == {}
    assert _manifest_members(store) == before


@pytest.mark.parametrize(
    ("option", "value", "error_field"),
    [
        ("--tolerance", "nan", "relative_tolerance"),
        ("--tolerance", "inf", "relative_tolerance"),
        ("--tolerance", "-inf", "relative_tolerance"),
        ("--tolerance", "-0.1", "relative_tolerance"),
        ("--confidence-level", "nan", "confidence_level"),
        ("--confidence-level", "inf", "confidence_level"),
        ("--confidence-level", "-inf", "confidence_level"),
        ("--confidence-level", "0", "confidence_level"),
        ("--confidence-level", "1", "confidence_level"),
    ],
)
def test_cli_refuses_invalid_verification_configuration_before_execution(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    option: str,
    value: str,
    error_field: str,
) -> None:
    """Invalid comparison options are usage errors, without an executed backend."""
    store = FileSystemCAS(tmp_path / "cas")
    before = _manifest_members(store)
    exit_code = main(
        [
            "replay",
            "sha256:" + "f" * 64,
            "--cas-root",
            str(store.root),
            "--mode",
            "ci_bounded",
            f"{option}={value}",
            "--json",
        ]
    )
    captured = capsys.readouterr()
    assert exit_code == 2
    assert captured.out == ""
    assert f"{error_field} must be finite" in captured.err
    assert _manifest_members(store) == before


@pytest.mark.parametrize("damage", ["packet_tamper", "missing_plan"])
def test_fresh_cli_refuses_damaged_real_packet_before_backend_execution(
    tmp_path: Path, damage: str
) -> None:
    """Missing/corrupt real inputs cannot produce a new replay result."""
    from polisyos.core.artifacts import load_core_json_artifact

    store = FileSystemCAS(tmp_path / "cas")
    packet_ref = _build_executable_foundry_packet(store)
    packet = load_core_json_artifact(store, packet_ref)
    damaged_id = (
        packet_ref.artifact_id
        if damage == "packet_tamper"
        else ArtifactID.model_validate(packet["artifacts"]["exec_plan_ref"])
    )
    digest = damaged_id.hex
    blob = store.root / "artifacts" / "sha256" / digest[:2] / digest[2:4] / f"{digest}.blob"
    original = blob.read_bytes()
    moved = blob.with_suffix(".withheld")
    if damage == "packet_tamper":
        blob.write_bytes(original + b"tamper")
    else:
        blob.rename(moved)
    before = _manifest_members(store)
    try:
        report = completeness_check(store, packet_ref.artifact_id)
        assert report.level.value == "incomplete"
        for item in (*report.missing, *report.corrupted):
            assert str(ArtifactID.model_validate(item.artifact_id)) == item.artifact_id
            if damage == "missing_plan" and item.artifact_id == str(damaged_id):
                selected = next(
                    edge
                    for edge in store.get_manifest(packet_ref).inputs
                    if edge.role == "exec_plan_ref"
                )
                assert item.manifest_profile_sha256 == selected.manifest_profile_sha256
        refused = _fresh_replay_cli(
            store,
            "replay",
            str(packet_ref.artifact_id),
            "--cas-root",
            str(store.root),
            "--mode",
            "skip",
            "--json",
        )
        assert refused.returncode == 1, refused.stderr
        payload = _fresh_cli_json(refused)
        assert payload["success"] is False
        assert payload["completeness"]["level"] == "incomplete"
        assert payload["replay_simulation_result_ref"] is None
        assert payload["verification"] is None
        assert _manifest_members(store) == before
    finally:
        if damage == "packet_tamper":
            blob.write_bytes(original)
        else:
            moved.rename(blob)


def test_fresh_cli_refuses_check_only_export_without_publishing_output(tmp_path: Path) -> None:
    """The conflicting non-execution options fail before store or output creation."""
    store = FileSystemCAS(tmp_path / "cas")
    output = tmp_path / "forbidden.tar.gz"
    result = _fresh_replay_cli(
        store,
        "replay",
        "sha256:" + "f" * 64,
        "--cas-root",
        str(store.root),
        "--check-only",
        "--export",
        str(output),
        "--json",
    )
    assert result.returncode == 2
    assert "cannot be used together" in result.stderr
    assert result.stdout == ""
    assert not output.exists()


def _persisted_snapshot(root: Path) -> dict[str, bytes]:
    """Capture all persisted CAS members, claims, and owner generations."""
    return {
        str(path.relative_to(root)): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file() and not path.name.endswith(".lock")
    }


@pytest.mark.parametrize("as_json", [True, False])
def test_bundle_cli_exports_actual_import_report_and_selected_graph(
    tmp_path: Path, capsys, as_json: bool
) -> None:
    """Bundle import, report production, CLI projection, and re-import use real CAS APIs."""
    source = FileSystemCAS(tmp_path / "source")
    packet_ref, expected_ids = _build_replay_bundle(
        source, tmp_path / "bundle", run_id="B148_valid_export"
    )
    export_path = tmp_path / "cli-export.tar.gz"
    argv = [
        "replay",
        str(packet_ref.artifact_id),
        "--bundle",
        str(tmp_path / "bundle"),
        "--export",
        str(export_path),
    ]
    if as_json:
        argv.append("--json")

    exit_code = main(argv)

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.err == ""
    if as_json:
        payload = json.loads(captured.out)
        report_payload = payload["bundle_import"]
        assert payload["exported_artifacts"] == len(expected_ids)
        assert payload["missing_artifacts"] == []
        assert payload["missing_manifests"] == []
        assert report_payload["imported_artifacts"] == len(expected_ids)
        assert report_payload["received_artifact_ids"] == sorted(expected_ids)
        assert (
            report_payload["received_artifact_count_basis"]
            == "unique recognized IDs from incoming CAS members"
        )
        assert _payload_ref_ids(payload, "published_refs") == expected_ids
        assert _payload_ref_ids(payload, "reused_refs") == set()
        assert _payload_ref_ids(payload, "integrity_verified_refs") == set()
        assert report_payload["integrity_verification_requested"] is False
        assert report_payload["verification_failed"] == []
        assert report_payload["disposition_basis"] == "durable_owner_manifest_stage_intent"
    else:
        assert f"exported={len(expected_ids)}" in captured.out
        assert f"published_views={len(expected_ids)} reused_views=0" in captured.out
        assert "integrity=not_requested:0" in captured.out
        assert "verification_failed=0" in captured.out
        assert "disposition_basis=durable_owner_manifest_stage_intent" in captured.out

    readback = FileSystemCAS(tmp_path / "readback")
    readback_report = readback.import_subgraph(export_path, verify_integrity=True)
    assert set(readback_report.received_artifact_ids) == expected_ids
    assert {str(item) for item in readback.iter_artifact_ids()} == expected_ids


@pytest.mark.parametrize("as_json", [True, False])
def test_replay_cli_consumes_real_noop_report_and_selected_input_refs(
    tmp_path: Path, capsys, monkeypatch: pytest.MonkeyPatch, as_json: bool
) -> None:
    """The existing-store consumer renders an exact same-owner no-op report."""
    context = ArtifactTenantContextInfo(tenant_id="tenant-a", cell_id="cell-a")
    source = FileSystemCAS(
        tmp_path / "source", tenant_id=context.tenant_id, cell_id=context.cell_id
    )
    packet_ref, expected_ids = _build_replay_bundle(
        source,
        tmp_path / "bundle",
        run_id="B148_noop",
        tenant_id=context.tenant_id,
        cell_id=context.cell_id,
    )
    assert all(
        source.get_manifest(artifact_id).tenant_context == context
        for artifact_id in source.iter_artifact_ids()
    )
    target = FileSystemCAS(
        tmp_path / "target", tenant_id=context.tenant_id, cell_id=context.cell_id
    )
    first_report = target.import_subgraph(tmp_path / "bundle", verify_integrity=True)
    assert {str(ref.artifact_id) for ref in first_report.published_refs} == expected_ids
    assert first_report.disposition_basis == "durable_owner_manifest_stage_intent"
    assert all(
        target.get_manifest(artifact_id).tenant_context == context
        for artifact_id in target.iter_artifact_ids()
    )
    selected_input_ids = {
        str(item.artifact_id) for item in target.get_manifest(packet_ref.artifact_id).inputs
    }
    assert selected_input_ids == expected_ids - {str(packet_ref.artifact_id)}

    before_noop = _persisted_snapshot(target.root)
    staged: list[Path] = []
    make_stage = store_module.tempfile.mkdtemp

    def observe_stage(*args: Any, **kwargs: Any) -> str:
        result = make_stage(*args, **kwargs)
        if str(kwargs.get("prefix", "")).startswith(".cas-import"):
            staged.append(Path(result))
        return result

    monkeypatch.setattr(store_module.tempfile, "mkdtemp", observe_stage)
    report = target.import_subgraph(tmp_path / "bundle", verify_integrity=True)
    assert staged == [], "exact same-owner no-op must not create a private import stage"
    assert _persisted_snapshot(target.root) == before_noop, (
        "exact same-owner no-op changed persisted views, claims, or owner generation"
    )
    assert report.imported_files == 0
    assert report.published_refs == ()
    assert {str(ref.artifact_id) for ref in report.reused_refs} == expected_ids
    assert {str(ref.artifact_id) for ref in report.integrity_verified_refs} == expected_ids
    assert report.disposition_basis == "exact_owned_view_admission"
    assert report.imported_artifacts == len(expected_ids)

    export_path = tmp_path / "noop-reexport.tar.gz"
    exit_code = _run_existing_store_export(
        store=target,
        packet_id=packet_ref.artifact_id,
        report=report,
        export_path=export_path,
        as_json=as_json,
    )
    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.err == ""
    if as_json:
        payload = json.loads(captured.out)
        report_payload = payload["bundle_import"]
        assert payload["exported_artifacts"] == len(expected_ids)
        assert report_payload["imported_artifacts"] == len(expected_ids)
        assert report_payload["received_artifact_ids"] == sorted(expected_ids)
        assert (
            report_payload["received_artifact_count_basis"]
            == "unique recognized IDs from incoming CAS members"
        )
        assert _payload_ref_ids(payload, "published_refs") == set()
        assert _payload_ref_ids(payload, "reused_refs") == expected_ids
        assert _payload_ref_ids(payload, "integrity_verified_refs") == expected_ids
        assert report_payload["integrity_verification_requested"] is True
        assert report_payload["disposition_basis"] == "exact_owned_view_admission"
    else:
        assert f"exported={len(expected_ids)}" in captured.out
        assert "published_views=0" in captured.out
        assert f"reused_views={len(expected_ids)}" in captured.out
        assert f"integrity=requested:{len(expected_ids)}" in captured.out
        assert "disposition_basis=exact_owned_view_admission" in captured.out

    reopened = FileSystemCAS(target.root, tenant_id=context.tenant_id, cell_id=context.cell_id)
    assert {str(item) for item in reopened.iter_artifact_ids()} == expected_ids
    readback = FileSystemCAS(
        tmp_path / "noop-readback", tenant_id=context.tenant_id, cell_id=context.cell_id
    )
    readback_report = readback.import_subgraph(export_path, verify_integrity=True)
    assert set(readback_report.received_artifact_ids) == expected_ids


@pytest.mark.parametrize("as_json", [True, False])
def test_replay_cli_exports_prior_generation_after_real_import_refusal(
    tmp_path: Path, capsys, monkeypatch: pytest.MonkeyPatch, as_json: bool
) -> None:
    """A corrupt replacement is refused while the prior bound owner view stays readable."""
    context = ArtifactTenantContextInfo(tenant_id="tenant-a", cell_id="cell-a")
    source = FileSystemCAS(
        tmp_path / "source", tenant_id=context.tenant_id, cell_id=context.cell_id
    )
    packet_ref, expected_ids = _build_replay_bundle(
        source,
        tmp_path / "bundle",
        run_id="B148_prior_generation",
        tenant_id=context.tenant_id,
        cell_id=context.cell_id,
    )
    target = FileSystemCAS(
        tmp_path / "target", tenant_id=context.tenant_id, cell_id=context.cell_id
    )
    initial_report = target.import_subgraph(tmp_path / "bundle", verify_integrity=True)
    assert {str(ref.artifact_id) for ref in initial_report.published_refs} == expected_ids
    assert all(
        target.get_manifest(artifact_id).tenant_context == context
        for artifact_id in target.iter_artifact_ids()
    )
    prior_ids = {str(item) for item in target.iter_artifact_ids()}
    prior_bytes = target.get_bytes(packet_ref.artifact_id)
    prior_manifest = target.get_manifest(packet_ref.artifact_id)

    damaged_bundle = tmp_path / "damaged-bundle"
    shutil.copytree(tmp_path / "bundle", damaged_bundle)
    inventory_path = damaged_bundle / "export_manifest.json"
    inventory_before = inventory_path.read_bytes()
    packet_hex = str(packet_ref.artifact_id).removeprefix("sha256:")
    damaged_blob = (
        damaged_bundle
        / "artifacts"
        / "sha256"
        / packet_hex[:2]
        / packet_hex[2:4]
        / f"{packet_hex}.blob"
    )
    damaged_blob.write_bytes(b"corrupt bytes with the original inventory still present")
    assert inventory_path.read_bytes() == inventory_before

    before_refusal = _persisted_snapshot(target.root)
    staged: list[Path] = []
    make_stage = store_module.tempfile.mkdtemp

    def observe_stage(*args: Any, **kwargs: Any) -> str:
        result = make_stage(*args, **kwargs)
        if str(kwargs.get("prefix", "")).startswith(".cas-import"):
            staged.append(Path(result))
        return result

    monkeypatch.setattr(store_module.tempfile, "mkdtemp", observe_stage)
    report = target.import_subgraph(damaged_bundle, verify_integrity=True)
    assert staged == [], "integrity refusal must happen before private import staging"
    assert _persisted_snapshot(target.root) == before_refusal, (
        "refused replacement changed persisted views, claims, or owner generation"
    )
    assert report.imported_files == 0
    assert report.disposition_basis == "received_members_rejected_before_admission"
    assert report.received_artifact_ids == tuple(sorted(expected_ids))
    assert report.imported_artifacts == len(expected_ids)
    assert report.verification_failed == [str(packet_ref.artifact_id)]
    assert report.published_refs == ()
    assert report.reused_refs == ()
    assert {str(item) for item in target.iter_artifact_ids()} == prior_ids
    assert target.get_bytes(packet_ref.artifact_id) == prior_bytes
    assert target.get_manifest(packet_ref.artifact_id) == prior_manifest

    export_path = tmp_path / "prior-generation-export.tar.gz"
    exit_code = _run_existing_store_export(
        store=target,
        packet_id=packet_ref.artifact_id,
        report=report,
        export_path=export_path,
        as_json=as_json,
    )
    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.err == ""
    if as_json:
        payload = json.loads(captured.out)
        report_payload = payload["bundle_import"]
        assert payload["exported_artifacts"] == len(expected_ids)
        assert payload["missing_artifacts"] == []
        assert report_payload["imported_artifacts"] == len(expected_ids)
        assert report_payload["received_artifact_ids"] == sorted(expected_ids)
        assert (
            report_payload["received_artifact_count_basis"]
            == "unique recognized IDs from incoming CAS members"
        )
        assert report_payload["verification_failed"] == [str(packet_ref.artifact_id)]
        assert _payload_ref_ids(payload, "published_refs") == set()
        assert _payload_ref_ids(payload, "reused_refs") == set()
        assert report_payload["disposition_basis"] == "received_members_rejected_before_admission"
    else:
        assert f"exported={len(expected_ids)}" in captured.out
        assert "published_views=0 reused_views=0" in captured.out
        assert "integrity=requested:0" in captured.out
        assert "verification_failed=1" in captured.out
        assert "disposition_basis=received_members_rejected_before_admission" in captured.out

    readback = FileSystemCAS(
        tmp_path / "prior-generation-readback",
        tenant_id=context.tenant_id,
        cell_id=context.cell_id,
    )
    readback_report = readback.import_subgraph(export_path, verify_integrity=True)
    assert set(readback_report.received_artifact_ids) == expected_ids
    assert {str(item) for item in readback.iter_artifact_ids()} == expected_ids


def test_replay_export_json_reports_refused_bundle_import(tmp_path: Path, capsys) -> None:
    """The actual bundle-import refusal remains visible when export lacks a graph."""
    source = FileSystemCAS(tmp_path / "source")
    ref = source.put_bytes(
        b"{}",
        PutOptions(kind="test.replay_packet", media_type="application/json"),
    )
    export = source.export_subgraph(
        [ref.artifact_id],
        tmp_path / "bundle",
        compress=False,
    )
    artifact_id = ref.artifact_id
    blob = (
        export.output_path
        / "artifacts"
        / "sha256"
        / artifact_id.hex[:2]
        / artifact_id.hex[2:4]
        / f"{artifact_id.hex}.blob"
    )
    blob.write_bytes(b"wrong bytes")

    exit_code = main(
        [
            "replay",
            str(artifact_id),
            "--bundle",
            str(export.output_path),
            "--export",
            str(tmp_path / "reexport.tar.gz"),
            "--json",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.err == ""
    payload = json.loads(captured.out)
    assert payload["error"] == "dependency graph is unavailable"
    assert payload["bundle_import"] == {
        "imported_files": 0,
        "imported_artifacts": 1,
        "received_artifact_ids": [str(artifact_id)],
        "received_artifact_count_basis": "unique recognized IDs from incoming CAS members",
        "published_refs": [],
        "reused_refs": [],
        "integrity_verification_requested": False,
        "integrity_verified_refs": [],
        "verification_failed": [str(artifact_id)],
        "disposition_basis": "received_members_rejected_before_admission",
    }


@pytest.mark.parametrize("route", ["export_missing", "export_success", "check", "replay"])
@pytest.mark.parametrize("as_json", [True, False])
def test_all_replay_import_surfaces_project_one_typed_report(
    tmp_path: Path, capsys, monkeypatch: pytest.MonkeyPatch, route: str, as_json: bool
) -> None:
    """Keep a projection-only route check; real CAS outcomes are covered separately."""
    report = ImportReport(
        imported_files=2,
        imported_artifacts=1,
        total_bytes=12,
        source=tmp_path / "bundle",
        skipped_entries=[],
        verification_failed=[],
        received_artifact_ids=("a" * 64,),
        published_refs=(),
        reused_refs=(),
        integrity_verified_refs=(),
        integrity_verification_requested=False,
        disposition_basis="exact_owned_view_admission",
    )
    completeness = SimpleNamespace(
        graph=None if route == "export_missing" else SimpleNamespace(all_artifact_ids=lambda: ()),
        summary=lambda: "complete",
        ok=True,
        level=SimpleNamespace(value="complete"),
        strategy=SimpleNamespace(value="selected"),
        total_artifacts=0,
        present_artifacts=0,
        missing=[],
        corrupted=[],
        reason_codes=[],
    )
    args = SimpleNamespace(
        export=str(tmp_path / "export") if route.startswith("export") else None,
        check_only=route == "check",
        json=as_json,
        strategy="auto",
        mode="skip",
        tolerance=0.0,
        confidence_level=0.95,
        no_verify=True,
    )
    store = SimpleNamespace(
        export_subgraph=lambda *_args, **_kwargs: SimpleNamespace(
            exported_artifacts=1,
            total_bytes=12,
            output_path=tmp_path / "export",
            missing_artifacts=[],
            missing_manifests=[],
            previous_generation=None,
        )
    )
    replay_result = SimpleNamespace(
        success=True,
        run_id="run-1",
        strategy=SimpleNamespace(value="selected"),
        original_packet_ref="original",
        replay_decision_packet_ref=None,
        replay_simulation_result_ref=None,
        errors=[],
        warnings=[],
        completeness=completeness,
        verification=None,
        replay_artifact_refs={},
    )
    replay_backend = SimpleNamespace(replay_packet=lambda *_args, **_kwargs: replay_result)
    monkeypatch.setattr(_cli_replay.importlib, "import_module", lambda _name: replay_backend)
    monkeypatch.setattr(_cli_replay, "_bundle_import_payload", _cli_replay._bundle_import_payload)
    _cli_replay._cmd_replay_with_store(
        args=args,
        store=store,
        packet_ref="packet",
        completeness_check=lambda *_args: completeness,
        VerificationConfig=lambda **kwargs: kwargs,
        VerificationMode=SimpleNamespace(
            BIT_EXACT="bit_exact", CI_BOUNDED="ci_bounded", SKIP="skip"
        ),
        ReplayStrategy=SimpleNamespace(),
        import_report=report,
    )
    captured = capsys.readouterr()
    output = captured.out + captured.err
    if as_json:
        payload = json.loads(output)
        projected = payload["bundle_import"]
        assert projected["disposition_basis"] == "exact_owned_view_admission"
        assert projected["integrity_verification_requested"] is False
        assert projected["received_artifact_ids"] == ["a" * 64]
    else:
        assert "bundle_import received_unique_ids=1" in output
        assert "integrity=not_requested:0" in output
        assert "disposition_basis=exact_owned_view_admission" in output


@pytest.mark.parametrize("as_json", [True, False])
def test_export_overwrite_cli_exposes_the_actual_retained_generation(
    tmp_path: Path,
    capsys,
    as_json: bool,
) -> None:
    """The real CLI export names retained bytes; the first export shape stays stable."""
    source = FileSystemCAS(tmp_path / "source")
    packet_ref, _expected_ids = _build_replay_bundle(
        source, tmp_path / "bundle", run_id="retained_export_cli"
    )
    target = tmp_path / "cli-export.tar.gz"
    argv = [
        "replay",
        str(packet_ref.artifact_id),
        "--bundle",
        str(tmp_path / "bundle"),
        "--export",
        str(target),
    ]
    if as_json:
        argv.append("--json")
    assert main(argv) == 0
    first = capsys.readouterr()
    assert first.err == ""
    if as_json:
        first_payload = json.loads(first.out)
        assert "previous_generation" not in first_payload
        assert "previous_generation_retention" not in first_payload
    else:
        assert "previous_generation=" not in first.out
    original_bytes = target.read_bytes()
    assert main(argv) == 0
    second = capsys.readouterr()
    assert second.err == ""
    if as_json:
        payload = json.loads(second.out)
        retained = Path(payload["previous_generation"])
        assert payload["previous_generation_retention"] == "caller_owned_manual_reclamation"
    else:
        line = next(
            line for line in second.out.splitlines() if line.startswith("previous_generation=")
        )
        retained = Path(line.removeprefix("previous_generation=").split(" retention=", 1)[0])
        assert "retention=caller_owned_manual_reclamation" in line
    assert retained.parent == target.parent
    assert retained.read_bytes() == original_bytes
    fresh = FileSystemCAS(tmp_path / "fresh-reader")
    imported = fresh.import_subgraph(retained, verify_integrity=True)
    assert imported.verification_failed == []
    assert fresh.get_bytes(packet_ref) == source.get_bytes(packet_ref)
