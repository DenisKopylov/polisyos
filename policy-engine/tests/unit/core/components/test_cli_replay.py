from __future__ import annotations

import json
from pathlib import Path

from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
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
        "verification_failed": [str(artifact_id)],
    }
