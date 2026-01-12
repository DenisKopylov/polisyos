from pathlib import Path

from polisyos.runtime.api import log_artifact, resolve_artifact_path, start_run
from polisyos.runtime.manifest import ArtifactRef, RunManifest


def test_log_artifact_uses_relative_paths(tmp_path: Path) -> None:
    base_dir = tmp_path / "runs"
    man = start_run(run_id="r1", base_dir=base_dir)
    ref = log_artifact(
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
    assert resolve_artifact_path(abs_ref, base_dir=base_dir) == (tmp_path / "abs.json").resolve()
