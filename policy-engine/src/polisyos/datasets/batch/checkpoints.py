"""Checkpoint and stage-state helpers for resumable dataset runs."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any


def _json_dumps(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def load_json(path: Path, *, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except json.JSONDecodeError:
        return default


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2, sort_keys=True)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def hash_payload(payload: Any) -> str:
    return hashlib.sha256(_json_dumps(payload).encode("utf-8")).hexdigest()


def fingerprint_paths(paths: list[Path]) -> str:
    rows: list[dict[str, object]] = []
    for path in sorted({item.resolve() for item in paths if item is not None}):
        if not path.exists():
            rows.append({"path": str(path), "exists": False})
            continue
        stat = path.stat()
        rows.append(
            {
                "path": str(path),
                "exists": True,
                "size": int(stat.st_size),
                "mtime_ns": int(stat.st_mtime_ns),
            }
        )
    return hash_payload(rows)


def load_stage_state(path: Path) -> dict[str, dict[str, Any]]:
    payload = load_json(path, default={})
    return payload if isinstance(payload, dict) else {}


def save_stage_state(
    path: Path,
    *,
    stage: str,
    status: str,
    input_fingerprint: str,
    outputs: list[Path] | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    state = load_stage_state(path)
    state[str(stage)] = {
        "status": str(status),
        "input_fingerprint": str(input_fingerprint),
        "outputs": [str(item) for item in (outputs or [])],
        "metadata": metadata or {},
    }
    write_json(path, state)


def stage_can_skip(
    path: Path,
    *,
    stage: str,
    input_fingerprint: str,
    required_outputs: list[Path] | None = None,
) -> bool:
    state = load_stage_state(path)
    current = state.get(str(stage))
    if not isinstance(current, dict):
        return False
    if str(current.get("status")) != "complete":
        return False
    if str(current.get("input_fingerprint", "")) != str(input_fingerprint):
        return False
    outputs = required_outputs or [Path(item) for item in current.get("outputs", []) if item]
    return all(path.exists() for path in outputs)


__all__ = [
    "fingerprint_paths",
    "hash_payload",
    "load_json",
    "load_stage_state",
    "save_stage_state",
    "stage_can_skip",
    "write_json",
]
