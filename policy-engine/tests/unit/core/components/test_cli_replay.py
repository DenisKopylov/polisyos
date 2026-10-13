from __future__ import annotations

import json
import shutil
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


def _build_executable_foundry_packet(store: FileSystemCAS) -> ArtifactRef:
    """Create a packet through Foundry's real registry, compiler, and input producers."""
    from decimal import Decimal

    from polisyos.core.contracts.fabric import DataSnapshot
    from polisyos.core.contracts.foundry import (
        CompileRequest,
        FoundryInputBindings,
        StateSnapshotRef,
    )
    from polisyos.core.registry import build_default_registry_bundle, load_registry_bundle_content
    from polisyos.foundry.compile.api import compile as compile_foundry
    from polisyos.foundry.contracts.state import GlobalState
    from polisyos.foundry.execute.executor import put_state_snapshot
    from polisyos.ir.governance.policy_spec import InterventionSpec, PolicySpec
    from polisyos.ir.governance.problem_frame import ProblemDomain, ProblemFrame
    from polisyos.ir.governance.schedule import ScheduleSpec
    from polisyos.ir.governance.selector_expr import SelectorPredicate
    from polisyos.ir.model_layer.model_spec import ModelSpec
    from polisyos.ir.model_layer.types import SelectorOperator
    from polisyos.ir.trinity import TrinityBundle

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
        PutOptions(kind="fabric.data_snapshot", media_type="application/json"),
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
            data_snapshot_ref=str(state_ref.artifact_id),
            registry_bundle_ref=str(registry.bundle_ref.artifact_id),
        ),
    )
    policy_ref = store.put_json(
        policy,
        PutOptions(kind="ir.trinity_bundle", media_type="application/json"),
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
    input_bindings = store.put_json(
        FoundryInputBindings(
            data_snapshot_ref=data_snapshot,
            registry_bundle_ref=registry.bundle_ref,
            rules=[],
            bound_state_snapshot_ref=state_ref,
        ),
        PutOptions(kind="foundry.input_bindings", media_type="application/json"),
        return_selected_profile=True,
    )
    packet_inputs = {
        "registry_bundle_ref": registry.bundle_ref,
        "input_bindings_ref": input_bindings,
        "data_snapshot_ref": data_snapshot,
        "state_snapshot_ref": state_ref,
        "trinity_bundle_ref": policy_ref,
    }
    packet_artifacts = {
        "exec_plan_ref": compile_result.exec_plan_ref,
        "lowered_ir_ref": lowered_ir_ref,
        "program_graph_ref": program_graph_ref,
    }
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
                input_ref_from_artifact_ref(ref, role=role)
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
