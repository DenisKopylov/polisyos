"""Shadow-compatible unified snapshot finalization helpers."""

from __future__ import annotations

import json
import pathlib

from polisyos.data_forge.kernel._base import utc_now
from polisyos.data_forge.kernel.io import sha256_file

DEFAULT_PIPELINES = ("datasets", "academic", "lex")


def finalize_snapshot(
    snapshot_root: str | pathlib.Path,
    *,
    update_latest_symlink: bool = True,
    pipelines: tuple[str, ...] = DEFAULT_PIPELINES,
) -> pathlib.Path:
    """Create a legacy-compatible `snapshot_manifest.json` from publish manifests."""
    root = pathlib.Path(snapshot_root)
    pipeline_manifests: dict[str, dict[str, object]] = {}
    artifacts: list[dict[str, str]] = []

    for pipeline in pipelines:
        manifest_path = root / pipeline / "publish" / "manifest.json"
        manifest = _read_optional_json(manifest_path)
        pipeline_manifests[pipeline] = manifest
        pipeline_root = root / pipeline
        for item in _list_value(manifest.get("artifacts")):
            if not isinstance(item, dict):
                continue
            artifact_path = _resolve_artifact_path(pipeline_root, str(item.get("path") or ""))
            if artifact_path.exists():
                artifacts.append(
                    {
                        "pipeline": pipeline,
                        "path": str(artifact_path),
                        "sha256": str(item.get("sha256") or sha256_file(artifact_path)),
                    }
                )

    payload: dict[str, object] = {
        "kind": "snapshot",
        "snapshot_root": str(root),
        "generated_at": utc_now().isoformat(),
        "pipelines": pipeline_manifests,
        "artifacts": artifacts,
    }

    out_path = root / "snapshot_manifest.json"
    out_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    if update_latest_symlink:
        _update_latest_symlink(root)

    return out_path


def _read_optional_json(path: pathlib.Path) -> dict[str, object]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object at {path}")
    return {str(key): value for key, value in payload.items()}


def _resolve_artifact_path(pipeline_root: pathlib.Path, raw_path: str) -> pathlib.Path:
    path = pathlib.Path(raw_path)
    if path.is_absolute():
        return path
    return pipeline_root / path


def _list_value(value: object) -> list[object]:
    if not isinstance(value, list):
        return []
    return value


def _update_latest_symlink(root: pathlib.Path) -> None:
    latest = root.parent / "policyos_snapshot_latest"
    try:
        if latest.is_symlink() or latest.exists():
            latest.unlink()
        latest.symlink_to(root.name)
    except OSError:
        return


__all__ = ["DEFAULT_PIPELINES", "finalize_snapshot"]
