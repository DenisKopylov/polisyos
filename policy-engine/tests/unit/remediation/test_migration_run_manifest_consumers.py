"""RunManifest migration preserves the paths used by the persisted reader."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from polisyos.runtime.api import resolve_artifact_path
from polisyos.runtime.manifest import RunManifest
from tools.ops_runners.migrations.migrate import main as migrate

pytestmark = pytest.mark.unit


def test_explicit_relative_path_reopens_selected_bytes_from_run_root(tmp_path: Path) -> None:
    """A manifest with only relative_path survives migration and real reader lookup."""
    run_root = tmp_path / "run"
    source = run_root / "nested" / "data.json"
    source.parent.mkdir(parents=True)
    source.write_text("selected source", encoding="utf-8")
    original = tmp_path / "input.json"
    output = tmp_path / "output.json"
    original.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "run_id": "run-selected",
                "run_root": str(run_root),
                "artifacts": [
                    {
                        "artifact_type": "payload",
                        "relative_path": "nested/data.json",
                        "media_type": "application/json",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    assert migrate(["run_manifest", str(original), str(output)]) == 0
    result = RunManifest.model_validate_json(output.read_bytes())
    assert result.artifacts[0].path is None
    selected = resolve_artifact_path(result.artifacts[0], run_root=Path(result.run_root or ""))
    assert selected == source.resolve()
    assert selected.read_text(encoding="utf-8") == "selected source"


def test_conflicting_paths_are_refused_before_existing_output_changes(tmp_path: Path) -> None:
    """A separate existing file cannot replace the declared path through a basename match."""
    root = tmp_path / "run"
    first = root / "one" / "data.json"
    second = root / "two" / "data.json"
    first.parent.mkdir(parents=True)
    second.parent.mkdir(parents=True)
    first.write_text("one", encoding="utf-8")
    second.write_text("two", encoding="utf-8")
    original = tmp_path / "input.json"
    output = tmp_path / "output.json"
    original.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "run_id": "run-conflict",
                "run_root": str(root),
                "artifacts": [
                    {
                        "artifact_type": "payload",
                        "path": str(first),
                        "relative_path": "two/data.json",
                        "media_type": "application/json",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    output.write_text("original output", encoding="utf-8")

    with pytest.raises(ValueError, match="identify different sources"):
        migrate(["run_manifest", str(original), str(output)])
    assert output.read_text(encoding="utf-8") == "original output"
    assert first.read_text(encoding="utf-8") == "one"
    assert second.read_text(encoding="utf-8") == "two"
