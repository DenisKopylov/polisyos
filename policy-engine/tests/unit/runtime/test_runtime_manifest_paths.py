from pathlib import Path

import polisyos.runtime.api as runtime_api
import pytest
from polisyos.runtime.api import (
    RuntimeArtifactWrite,
    append_audit,
    log_artifact,
    log_artifacts,
    resolve_artifact_path,
    start_run,
)
from polisyos.runtime.manifest import ArtifactRef, RunManifest


def test_log_artifact_uses_relative_paths(tmp_path: Path) -> None:
    base_dir = tmp_path / "runs"
    man = start_run(run_id="r1", base_dir=base_dir)
    log_artifact(
        run_id=man.run_id,
        artifact_type="test_artifact",
        payload={"hello": "world"},
        base_dir=base_dir,
    )

    manifest_path = base_dir / man.run_id / "manifest.json"
    loaded = RunManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))

    assert loaded.run_root == str(base_dir)
    assert loaded.artifacts[0].relative_path is not None
    assert not Path(loaded.artifacts[0].path or "").is_absolute()

    # Перенос каталога не ломает доступ к артефакту
    new_root = tmp_path / "moved"
    new_root.mkdir()
    new_base = new_root / "runs"
    base_dir.rename(new_base)

    moved_manifest = RunManifest.model_validate_json(
        (new_base / man.run_id / "manifest.json").read_text(encoding="utf-8")
    )
    artifact_path = new_base / moved_manifest.artifacts[0].relative_path
    assert artifact_path.exists()


def test_start_run_seeds_audit_trail_and_file(tmp_path: Path) -> None:
    base_dir = tmp_path / "runs"

    manifest = start_run(run_id="r1", base_dir=base_dir)

    manifest_path = base_dir / manifest.run_id / "manifest.json"
    loaded = RunManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))

    assert any(ref.artifact_type == "audit_trail" for ref in loaded.artifacts)
    assert (base_dir / manifest.run_id / "audit.jsonl").read_text(encoding="utf-8") == ""


def test_resolve_artifact_path_handles_relative_and_absolute(tmp_path: Path) -> None:
    base_dir = tmp_path / "runs"
    base_dir.mkdir()

    rel_ref = ArtifactRef(
        artifact_type="x", relative_path="foo/bar.json", media_type="application/json"
    )
    abs_ref = ArtifactRef(
        artifact_type="x",
        path=str((tmp_path / "abs.json").resolve()),
        media_type="application/json",
    )
    (tmp_path / "abs.json").write_text("hello", encoding="utf-8")
    (base_dir / "foo").mkdir(parents=True)
    (base_dir / "foo" / "bar.json").write_text("world", encoding="utf-8")

    assert (
        resolve_artifact_path(rel_ref, base_dir=base_dir)
        == (base_dir / "foo" / "bar.json").resolve()
    )
    with pytest.raises(ValueError, match="Absolute artifact paths"):
        resolve_artifact_path(abs_ref, base_dir=base_dir)


def test_log_artifact_rejects_path_traversal(tmp_path: Path) -> None:
    base_dir = tmp_path / "runs"
    start_run(run_id="r1", base_dir=base_dir)

    with pytest.raises(ValueError, match="filename"):
        log_artifact(
            run_id="r1",
            artifact_type="safe",
            payload={"hello": "world"},
            filename="../escape.json",
            base_dir=base_dir,
        )

    with pytest.raises(ValueError, match="artifact_type"):
        log_artifact(
            run_id="r1",
            artifact_type="../unsafe",
            payload={"hello": "world"},
            base_dir=base_dir,
        )


def test_log_artifacts_batches_manifest_write(monkeypatch, tmp_path: Path) -> None:
    base_dir = tmp_path / "runs"
    start_run(run_id="r1", base_dir=base_dir)
    writes = 0
    original = runtime_api._write_manifest

    def _counting_write_manifest(*args, **kwargs):
        nonlocal writes
        writes += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(runtime_api, "_write_manifest", _counting_write_manifest)

    refs = log_artifacts(
        run_id="r1",
        base_dir=base_dir,
        entries=[
            RuntimeArtifactWrite(artifact_type="a", payload={"a": 1}),
            RuntimeArtifactWrite(artifact_type="b", payload={"b": 2}),
        ],
    )

    assert len(refs) == 2
    assert writes == 1
    manifest = RunManifest.model_validate_json(
        (base_dir / "r1" / "manifest.json").read_text(encoding="utf-8")
    )
    assert [ref.artifact_type for ref in manifest.artifacts] == ["audit_trail", "a", "b"]


def test_append_audit_does_not_rewrite_manifest_when_audit_trail_preseeded(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    base_dir = tmp_path / "runs"
    start_run(run_id="r1", base_dir=base_dir)

    writes = 0
    original = runtime_api._write_manifest

    def _counting_write_manifest(*args, **kwargs):
        nonlocal writes
        writes += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(runtime_api, "_write_manifest", _counting_write_manifest)

    append_audit(run_id="r1", record={"event": "hello"}, base_dir=base_dir)

    assert writes == 0
    assert (base_dir / "r1" / "audit.jsonl").read_text(encoding="utf-8").strip() == (
        '{"event":"hello"}'
    )


def test_log_artifacts_recovers_manifest_after_interrupted_write(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    base_dir = tmp_path / "runs"
    start_run(run_id="r1", base_dir=base_dir)

    original = runtime_api._write_manifest
    should_fail = True

    def _failing_write_manifest(*args, **kwargs):
        nonlocal should_fail
        if should_fail:
            should_fail = False
            raise OSError("simulated manifest crash")
        return original(*args, **kwargs)

    monkeypatch.setattr(runtime_api, "_write_manifest", _failing_write_manifest)

    with pytest.raises(OSError, match="simulated manifest crash"):
        log_artifacts(
            run_id="r1",
            base_dir=base_dir,
            entries=[RuntimeArtifactWrite(artifact_type="a", payload={"a": 1})],
        )

    journal_path = base_dir / "r1" / ".manifest-journal.json"
    assert journal_path.exists()

    monkeypatch.setattr(runtime_api, "_write_manifest", original)
    recovered = runtime_api._load_manifest(base_dir, "r1")

    assert [ref.artifact_type for ref in recovered.artifacts] == ["audit_trail", "a"]
    assert not journal_path.exists()


def test_append_audit_recovers_pending_record_after_interrupted_append(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    base_dir = tmp_path / "runs"
    start_run(run_id="r1", base_dir=base_dir)

    original = runtime_api._append_audit_line
    should_fail = True

    def _failing_append(path: Path, line: str) -> None:
        nonlocal should_fail
        if should_fail:
            should_fail = False
            raise OSError("simulated audit crash")
        original(path, line)

    monkeypatch.setattr(runtime_api, "_append_audit_line", _failing_append)

    with pytest.raises(OSError, match="simulated audit crash"):
        append_audit(run_id="r1", record={"event": "recover"}, base_dir=base_dir)

    journal_path = base_dir / "r1" / ".manifest-journal.json"
    assert journal_path.exists()

    monkeypatch.setattr(runtime_api, "_append_audit_line", original)
    recovered = runtime_api._load_manifest(base_dir, "r1")

    assert any(ref.artifact_type == "audit_trail" for ref in recovered.artifacts)
    assert not journal_path.exists()
    assert (base_dir / "r1" / "audit.jsonl").read_text(encoding="utf-8").strip() == (
        '{"event":"recover"}'
    )
