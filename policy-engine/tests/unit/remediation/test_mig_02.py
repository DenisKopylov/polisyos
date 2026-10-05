"""Test-first witnesses for identity-preserving RunManifest path migration.

The current migration CLI rewrites paths relative to the input location and
falls back to a basename when that calculation fails.  These tests pin the
identity and fail-closed contract that the Runtime-owned converter must
provide before the CLI relocation is implemented.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

import tools.lib.fs as fs
from polisyos.runtime.api import resolve_artifact_path
from polisyos.runtime.manifest import RunManifest
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
    """The emitted bytes must load and resolve through Runtime's real consumer."""
    run_root = tmp_path / "run-root"
    source = run_root / "nested" / "data.json"
    source.parent.mkdir(parents=True)
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
    """A failed atomic publish leaves the old output and permits consumer readback on retry."""
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
