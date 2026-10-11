from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from polisyos.core.artifacts._transfer_ops import ImportReport
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.components import _cli_replay
from tools.ops_runners.runtime_cli import main


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
    """Every JSON and text route exposes disposition and verification fields."""
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
