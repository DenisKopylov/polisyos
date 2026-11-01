"""Qualify path normalization with native Runtime persistence and fresh readers."""

from __future__ import annotations

import base64
import hashlib
import json
import pickle
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

import tools.lib.fs as fs
from polisyos.runtime.api import (
    append_audit,
    finalize_run,
    log_artifact,
    resolve_artifact_path,
    start_run,
)
from polisyos.runtime.manifest import RunManifest
from polisyos.runtime.manifest_migrations import (
    RunManifestPathMigrationError,
    migrate_run_manifest_paths,
)
from tools.cli import main as tools_cli_main
from tools.ops_runners.migrations.migrate import main as canonical_main

pytestmark = pytest.mark.unit


def _manifest_payload(
    *,
    run_root: Path,
    artifacts: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build the smallest persisted RunManifest payload for a path witness."""
    return {
        "schema_version": "1.0",
        "run_id": "run-mig02",
        "run_root": str(run_root),
        "artifacts": artifacts,
    }


def _write_input_and_output(
    tmp_path: Path,
    payload: dict[str, Any],
    *,
    output_sentinel: str | None = None,
) -> tuple[Path, Path]:
    """Persist an input manifest outside its declared run root."""
    input_path = tmp_path / "input" / "manifest.json"
    output_path = tmp_path / "output" / "manifest.json"
    input_path.parent.mkdir(parents=True)
    output_path.parent.mkdir(parents=True)
    input_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    if output_sentinel is not None:
        output_path.write_text(output_sentinel, encoding="utf-8")
    return input_path, output_path


def _artifact(path: str, *, artifact_type: str = "payload") -> dict[str, str]:
    """Return a minimal artifact reference without precomputed relative_path."""
    return {
        "artifact_type": artifact_type,
        "path": path,
        "media_type": "application/json",
    }


def _read_manifest(path: Path) -> dict[str, Any]:
    """Read a migrated JSON manifest."""
    return json.loads(path.read_text(encoding="utf-8"))


def test_nested_relative_path_survives_basename_collision(tmp_path: Path) -> None:
    """A nested relative reference must not be replaced by a same-name root file."""
    run_root = tmp_path / "run-root"
    nested = run_root / "sub" / "data.json"
    nested.parent.mkdir(parents=True)
    nested.write_text("original", encoding="utf-8")
    (run_root / "data.json").write_text("unrelated", encoding="utf-8")
    payload = _manifest_payload(run_root=run_root, artifacts=[_artifact("sub/data.json")])
    input_path, output_path = _write_input_and_output(tmp_path, payload)

    assert canonical_main(["run_manifest", str(input_path), str(output_path)]) == 0

    migrated = _read_manifest(output_path)
    reference = migrated["artifacts"][0]
    assert reference["path"] == "sub/data.json"
    assert reference["relative_path"] == "sub/data.json"
    assert (run_root / reference["relative_path"]).read_text(encoding="utf-8") == "original"


def test_absolute_path_uses_declared_root_and_preserves_nested_layout(tmp_path: Path) -> None:
    """An absolute source under run_root becomes the same root-relative path."""
    run_root = tmp_path / "declared-root"
    source = run_root / "nested" / "data.json"
    source.parent.mkdir(parents=True)
    source.write_text("source-bytes", encoding="utf-8")
    payload = _manifest_payload(run_root=run_root, artifacts=[_artifact(str(source))])
    input_path, output_path = _write_input_and_output(tmp_path, payload)

    assert canonical_main(["run_manifest", str(input_path), str(output_path)]) == 0

    migrated = _read_manifest(output_path)
    reference = migrated["artifacts"][0]
    assert migrated["run_root"] == str(run_root)
    assert reference["path"] == "nested/data.json"
    assert reference["relative_path"] == "nested/data.json"
    assert (run_root / reference["relative_path"]).read_text(encoding="utf-8") == "source-bytes"


def test_serialized_migration_loads_through_runtime_consumer(tmp_path: Path) -> None:
    """The canonical CLI output must resolve to the same nested artifact in Runtime."""
    run_root = tmp_path / "run-root"
    source = run_root / "nested" / "data.json"
    source.parent.mkdir(parents=True)
    (run_root / "data.json").write_bytes(b'{"consumer":"wrong-basename"}')
    source.write_bytes(b'{"consumer":"runtime"}')
    payload = _manifest_payload(run_root=run_root, artifacts=[_artifact(str(source))])
    input_path, output_path = _write_input_and_output(tmp_path, payload)

    assert canonical_main(["run_manifest", str(input_path), str(output_path)]) == 0

    manifest = RunManifest.model_validate_json(output_path.read_text(encoding="utf-8"))
    resolved = resolve_artifact_path(
        manifest.artifacts[0],
        run_root=Path(manifest.run_root),
    )
    assert resolved == source.resolve()
    assert resolved.read_bytes() == b'{"consumer":"runtime"}'


def test_publish_fault_preserves_destination_and_retry_is_readable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failed atomic publish preserves prior bytes and allows a fresh Runtime read on retry."""
    run_root = tmp_path / "run-root"
    source = run_root / "nested" / "data.json"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"stable-source")
    payload = _manifest_payload(run_root=run_root, artifacts=[_artifact(str(source))])
    sentinel = "previous-output\n"
    input_path, output_path = _write_input_and_output(
        tmp_path,
        payload,
        output_sentinel=sentinel,
    )
    input_bytes = input_path.read_bytes()
    original_replace = fs.os.replace

    def fail_replace(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise OSError("injected publish fault")

    monkeypatch.setattr(fs.os, "replace", fail_replace)
    with pytest.raises(OSError, match="injected publish fault"):
        canonical_main(["run_manifest", str(input_path), str(output_path)])

    assert output_path.read_text(encoding="utf-8") == sentinel
    assert input_path.read_bytes() == input_bytes
    assert source.read_bytes() == b"stable-source"
    assert not list(output_path.parent.glob(f".{output_path.stem}.*.tmp"))

    monkeypatch.setattr(fs.os, "replace", original_replace)
    assert canonical_main(["run_manifest", str(input_path), str(output_path)]) == 0
    manifest = RunManifest.model_validate_json(output_path.read_text(encoding="utf-8"))
    resolved = resolve_artifact_path(
        manifest.artifacts[0],
        run_root=Path(manifest.run_root),
    )
    assert resolved == source.resolve()
    assert resolved.read_bytes() == b"stable-source"


def test_missing_source_fails_closed_without_basename_substitution(tmp_path: Path) -> None:
    """A missing source cannot be made to look valid by emitting its basename."""
    run_root = tmp_path / "run-root"
    run_root.mkdir()
    payload = _manifest_payload(
        run_root=run_root,
        artifacts=[_artifact(str(run_root / "missing" / "data.json"))],
    )
    input_path, output_path = _write_input_and_output(
        tmp_path,
        payload,
        output_sentinel="previous-output\n",
    )

    with pytest.raises(ValueError, match=r"(?i)(missing|exist|source|identity)"):
        canonical_main(["run_manifest", str(input_path), str(output_path)])

    assert output_path.read_text(encoding="utf-8") == "previous-output\n"


def test_symlink_escape_fails_closed_before_output_write(tmp_path: Path) -> None:
    """A link resolving outside the declared root is not an admissible source."""
    run_root = tmp_path / "run-root"
    outside = tmp_path / "outside" / "secret.json"
    outside.parent.mkdir(parents=True)
    outside.write_text("outside-bytes", encoding="utf-8")
    run_root.mkdir()
    link = run_root / "escape.json"
    try:
        link.symlink_to(outside)
    except OSError as exc:  # pragma: no cover - platform capability guard
        pytest.skip(f"symlink witness unavailable: {exc}")

    payload = _manifest_payload(run_root=run_root, artifacts=[_artifact(str(link))])
    input_path, output_path = _write_input_and_output(
        tmp_path,
        payload,
        output_sentinel="previous-output\n",
    )

    with pytest.raises(ValueError, match=r"(?i)(escape|outside|contain|symlink|identity)"):
        canonical_main(["run_manifest", str(input_path), str(output_path)])

    assert output_path.read_text(encoding="utf-8") == "previous-output\n"
    assert outside.read_text(encoding="utf-8") == "outside-bytes"


def test_repeated_migration_preserves_bytes_and_is_idempotent(tmp_path: Path) -> None:
    """Migrating an already migrated manifest must not change its representation."""
    run_root = tmp_path / "run-root"
    source = run_root / "sub" / "data.json"
    source.parent.mkdir(parents=True)
    source.write_text("stable", encoding="utf-8")
    payload = _manifest_payload(run_root=run_root, artifacts=[_artifact(str(source))])
    input_path, first_output = _write_input_and_output(tmp_path, payload)
    second_output = tmp_path / "output" / "manifest-second.json"

    assert canonical_main(["run_manifest", str(input_path), str(first_output)]) == 0
    first_bytes = first_output.read_bytes()

    assert canonical_main(["run_manifest", str(first_output), str(second_output)]) == 0
    assert second_output.read_bytes() == first_bytes
    migrated = _read_manifest(second_output)
    assert migrated["run_root"] == str(run_root)
    assert migrated["artifacts"][0]["relative_path"] == "sub/data.json"


def test_path_only_run_manifest_rejects_explicit_target_version(tmp_path: Path) -> None:
    """Path-only normalization must not silently ignore an explicit ``--to``."""
    run_root = tmp_path / "run-root"
    source = run_root / "data.json"
    run_root.mkdir()
    source.write_text("payload", encoding="utf-8")
    payload = _manifest_payload(run_root=run_root, artifacts=[_artifact(str(source))])
    input_path, output_path = _write_input_and_output(
        tmp_path,
        payload,
        output_sentinel="previous-output\n",
    )

    with pytest.raises(ValueError, match=r"(?i)(--to|target|path.only|version)"):
        canonical_main(["run_manifest", str(input_path), str(output_path), "--to", "2.0"])

    assert output_path.read_text(encoding="utf-8") == "previous-output\n"


def test_path_only_does_not_copy_external_file_implicitly(tmp_path: Path) -> None:
    """An external absolute reference requires explicit relocation authority."""
    run_root = tmp_path / "run-root"
    external = tmp_path / "external" / "report.json"
    run_root.mkdir()
    external.parent.mkdir()
    external.write_text("external-bytes", encoding="utf-8")
    payload = _manifest_payload(run_root=run_root, artifacts=[_artifact(str(external))])
    input_path, output_path = _write_input_and_output(
        tmp_path,
        payload,
        output_sentinel="previous-output\n",
    )

    with pytest.raises(ValueError, match=r"(?i)(external|outside|relocat|source|root)"):
        canonical_main(["run_manifest", str(input_path), str(output_path)])

    assert output_path.read_text(encoding="utf-8") == "previous-output\n"
    assert external.read_text(encoding="utf-8") == "external-bytes"
    assert not (run_root / external.name).exists()


def test_external_paths_fail_closed_without_implicit_copy(tmp_path: Path) -> None:
    """Distinct external objects are rejected rather than copied or relabeled."""
    run_root = tmp_path / "run-root"
    first = tmp_path / "external-a" / "data.json"
    second = tmp_path / "external-b" / "data.json"
    run_root.mkdir()
    first.parent.mkdir()
    second.parent.mkdir()
    first.write_text("first", encoding="utf-8")
    second.write_text("second", encoding="utf-8")
    payload = _manifest_payload(
        run_root=run_root,
        artifacts=[
            _artifact(str(first), artifact_type="first"),
            _artifact(str(second), artifact_type="second"),
        ],
    )
    input_path, output_path = _write_input_and_output(
        tmp_path,
        payload,
        output_sentinel="previous-output\n",
    )

    with pytest.raises(ValueError, match=r"(?i)(external|ambiguous|outside|relocat|root)"):
        canonical_main(["run_manifest", str(input_path), str(output_path)])

    assert output_path.read_text(encoding="utf-8") == "previous-output\n"
    assert first.read_text(encoding="utf-8") == "first"
    assert second.read_text(encoding="utf-8") == "second"


_FRESH_READER = r"""
import hashlib
import json
import sys
from pathlib import Path
import polisyos.runtime.api as api
from polisyos.runtime.manifest import RunManifest
source = Path(sys.argv[1])
if source.suffix == ".json":
    raw = json.loads(source.read_text())
else:
    import yaml
    raw = yaml.safe_load(source.read_text())
manifest = RunManifest.model_validate(raw)
if len(sys.argv) > 2:
    persisted = api._load_manifest(source.parent.parent, source.parent.name)
    assert persisted.model_dump(mode="json") == manifest.model_dump(mode="json")
refs = []
for ref in manifest.artifacts:
    root = Path(manifest.run_root) if manifest.run_root else source.resolve().parent.parent
    path = api.resolve_artifact_path(ref, run_root=root, allow_absolute=True)
    refs.append({"type": ref.artifact_type, "path": str(path),
                 "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
print(json.dumps({"schema": manifest.schema_version, "status": manifest.status,
                  "root": manifest.run_root, "refs": refs,
                  "api_origin": str(Path(api.__file__).resolve())}, sort_keys=True))
"""


def _fresh_read(path: Path, *, runtime_load: bool = False) -> dict[str, Any]:
    """Read every reference with a new native Runtime process."""
    result = subprocess.run(
        [
            sys.executable,
            "-B",
            "-c",
            _FRESH_READER,
            str(path),
            *(["runtime"] if runtime_load else []),
        ],
        check=False,
        text=True,
        capture_output=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    observed = json.loads(result.stdout)
    import polisyos.runtime.api as runtime_api

    assert observed["api_origin"] == str(Path(runtime_api.__file__).resolve())
    return observed


@pytest.mark.parametrize("suffix", [".json", ".yaml"])
def test_actual_runtime_writer_registered_cli_and_fresh_all_entry_reader(
    tmp_path: Path, suffix: str
) -> None:
    """Real lifecycle/audit/payload bytes survive the registered converter."""
    root = tmp_path / "runs"
    run = start_run(run_id="native-mig02", base_dir=root)
    log_artifact(
        run_id=run.run_id,
        artifact_type="payload",
        payload={"actual": [1, 2]},
        filename="payload.json",
        base_dir=root,
    )
    append_audit(run_id=run.run_id, record={"event": "native-migration"}, base_dir=root)
    finalize_run(run_id=run.run_id, status="completed", base_dir=root)
    original = root / run.run_id / "manifest.json"
    source_bytes = original.read_bytes()
    before = _fresh_read(original, runtime_load=True)
    assert {ref["type"] for ref in before["refs"]} == {"audit_trail", "payload"}
    assert before["schema"] == "1.0"
    assert before["status"] == "completed"
    source = tmp_path / f"source{suffix}"
    if suffix == ".json":
        source.write_bytes(source_bytes)
    else:
        yaml = pytest.importorskip("yaml")
        source.write_text(yaml.safe_dump(json.loads(source_bytes), sort_keys=False))
    source_copy = source.read_bytes()
    outputs = tmp_path / "elsewhere"
    outputs.mkdir()
    output = outputs / f"normalized{suffix}"
    second = outputs / f"normalized-again{suffix}"
    for selected_input, selected_output in ((source, output), (output, second)):
        assert (
            tools_cli_main(
                [
                    "migrations",
                    "migrate",
                    "--timing-log",
                    str(tmp_path / "timing.jsonl"),
                    "run_manifest",
                    str(selected_input),
                    str(selected_output),
                ]
            )
            == 0
        )
        assert _fresh_read(selected_output) == before
    assert output.read_bytes() == second.read_bytes()
    restored = tmp_path / "fresh-runtime" / run.run_id / "manifest.json"
    restored.parent.mkdir(parents=True)
    if suffix == ".json":
        restored.write_bytes(output.read_bytes())
    else:
        restored.write_text(json.dumps(yaml.safe_load(output.read_text())))
    assert _fresh_read(restored, runtime_load=True) == before
    assert original.read_bytes() == source_bytes
    assert source.read_bytes() == source_copy


@pytest.mark.parametrize("bad_kind", ["missing", "conflict", "escape", "broken_link"])
def test_mixed_second_entry_refuses_before_any_output(tmp_path: Path, bad_kind: str) -> None:
    """A valid first entry never hides a later identity failure."""
    root = tmp_path / "run"
    root.mkdir()
    first = root / "first.json"
    first.write_bytes(b"first")
    second = root / "second.json"
    second.write_bytes(b"second")
    bad = _artifact("missing.json")
    match = "source does not exist"
    if bad_kind == "conflict":
        bad = _artifact("first.json")
        bad["relative_path"] = "second.json"
        match = "identify different sources"
    elif bad_kind in {"escape", "broken_link"}:
        outside = tmp_path / "outside.json"
        outside.write_bytes(b"outside")
        target = outside if bad_kind == "escape" else root / "absent.json"
        (root / "link.json").symlink_to(target)
        bad = _artifact("link.json")
        if bad_kind == "escape":
            match = "outside declared run_root"
    source, output = _write_input_and_output(
        tmp_path,
        _manifest_payload(run_root=root, artifacts=[_artifact("first.json"), bad]),
        output_sentinel="old output",
    )
    original = source.read_bytes()
    with pytest.raises(RunManifestPathMigrationError, match=match):
        canonical_main(["run_manifest", str(source), str(output)])
    assert output.read_bytes() == b"old output"
    assert source.read_bytes() == original
    assert first.read_bytes() == b"first"
    assert second.read_bytes() == b"second"


def test_internal_symlink_preserves_real_source_not_alias_basename(tmp_path: Path) -> None:
    """An internal link normalizes to its same-root target."""
    root = tmp_path / "run"
    target = root / "nested" / "data.json"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"chosen")
    (root / "data.json").write_bytes(b"wrong-basename")
    (root / "alias.json").symlink_to(target)
    source, output = _write_input_and_output(
        tmp_path, _manifest_payload(run_root=root, artifacts=[_artifact("alias.json")])
    )
    before = _fresh_read(source)
    assert canonical_main(["run_manifest", str(source), str(output)]) == 0
    assert _fresh_read(output) == before
    assert _read_manifest(output)["artifacts"][0]["path"] == "nested/data.json"


def test_relative_root_is_cwd_bound_not_output_relative(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Root spelling is retained; changing CWD is not portable relocation."""
    first_cwd = tmp_path / "first-cwd"
    first_root = first_cwd / "runs"
    first_root.mkdir(parents=True)
    (first_root / "data.json").write_bytes(b"first-root")
    source, output = _write_input_and_output(
        tmp_path, _manifest_payload(run_root=Path("runs"), artifacts=[_artifact("data.json")])
    )
    monkeypatch.chdir(first_cwd)
    assert canonical_main(["run_manifest", str(source), str(output)]) == 0
    assert _read_manifest(output)["run_root"] == "runs"
    before = _fresh_read(output)
    assert before["refs"][0]["path"] == str((first_root / "data.json").resolve())
    moved = tmp_path / "moved-manifest.json"
    moved.write_bytes(output.read_bytes())
    assert _fresh_read(moved) == before
    second_cwd = tmp_path / "second-cwd"
    second_root = second_cwd / "runs"
    second_root.mkdir(parents=True)
    (second_root / "data.json").write_bytes(b"different-root")
    monkeypatch.chdir(second_cwd)
    changed = _fresh_read(moved)
    assert changed["refs"][0]["path"] == str((second_root / "data.json").resolve())
    assert changed["refs"][0]["sha256"] != before["refs"][0]["sha256"]


def test_absent_root_uses_input_grandparent_without_mutating_source(tmp_path: Path) -> None:
    """The legacy default follows input ancestry, not output location."""
    root = tmp_path / "legacy"
    source = root / "run-id" / "manifest.json"
    source.parent.mkdir(parents=True)
    artifact = root / "run-id" / "data.json"
    artifact.write_bytes(b"legacy-default")
    data = _manifest_payload(run_root=root, artifacts=[_artifact("run-id/data.json")])
    del data["run_root"]
    source.write_text(json.dumps(data))
    original = source.read_bytes()
    output = tmp_path / "elsewhere.json"
    before = _fresh_read(source)
    result = migrate_run_manifest_paths(data, manifest_path=source)
    assert result["run_root"] == str(root.resolve())
    assert "run_root" not in data
    assert canonical_main(["run_manifest", str(source), str(output)]) == 0
    observed = _fresh_read(output)
    assert observed["refs"] == before["refs"]
    assert observed["refs"][0]["path"] == str(artifact.resolve())
    assert observed["refs"][0]["sha256"] == hashlib.sha256(artifact.read_bytes()).hexdigest()
    assert source.read_bytes() == original


@pytest.mark.parametrize("artifacts", [{"legacy_name": "data.json"}, ["data.json"]])
def test_unsupported_layout_is_diagnostic_without_basename_fallback(
    tmp_path: Path, artifacts: Any
) -> None:
    """Unknown legacy containers are not promoted into the supported DTO profile."""
    root = tmp_path / "run"
    root.mkdir()
    (root / "data.json").write_bytes(b"available but not a guessed reference")
    payload = _manifest_payload(run_root=root, artifacts=[])
    payload["artifacts"] = artifacts
    source, output = _write_input_and_output(tmp_path, payload, output_sentinel="old output")
    original = source.read_bytes()
    with pytest.raises(RunManifestPathMigrationError, match=r"artifacts must be a list|entry 0"):
        canonical_main(["run_manifest", str(source), str(output)])
    assert source.read_bytes() == original
    assert output.read_bytes() == b"old output"


def test_git_retained_protocol4_model_qualifies_legacy_relative_only_layout(
    tmp_path: Path,
) -> None:
    """Historical model bytes bind the layout; artifact bytes remain controlled."""
    fixture_path = (
        Path(__file__).resolve().parents[2]
        / "fixtures/package_path_compatibility/runtime_abi_protocol4.json"
    )
    fixture_bytes = fixture_path.read_bytes()
    fixture = json.loads(fixture_bytes)
    assert fixture["source_head"] == "cf6a076a8415dc4092cfd3d4e9c8862f81c15a9a"
    serialized = base64.b64decode(fixture["objects"]["RunManifest"]["pickle_base64"])
    assert hashlib.sha256(serialized).hexdigest() == fixture["objects"]["RunManifest"]["sha256"]
    historical = pickle.loads(serialized)  # noqa: S301 -- fixed repo-owned historical fixture.
    assert type(historical) is RunManifest
    assert historical.run_root is None
    assert historical.artifacts[0].path is None
    assert historical.artifacts[0].relative_path == "legacy/evidence.json"
    root = tmp_path / "controlled-root"
    artifact = root / "legacy/evidence.json"
    artifact.parent.mkdir(parents=True)
    artifact.write_bytes(b"controlled payload, not historical production data")
    source = root / historical.run_id / "manifest.json"
    source.parent.mkdir()
    source.write_text(json.dumps(historical.model_dump(mode="json")))
    before = source.read_bytes()
    observed_before = _fresh_read(source, runtime_load=True)
    output = tmp_path / "normalized.json"
    assert canonical_main(["run_manifest", str(source), str(output)]) == 0
    observed_after = _fresh_read(output)
    assert observed_after["refs"] == observed_before["refs"]
    assert observed_after["status"] == observed_before["status"] == "limited"
    assert observed_after["schema"] == "1.0"
    assert source.read_bytes() == before
    assert fixture_path.read_bytes() == fixture_bytes
