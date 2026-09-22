"""Checkpoint and stage-state helpers for resumable dataset runs."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from polisyos.data_forge.kernel.io.atomic import atomic_write_text
from polisyos.data_forge.kernel.io.hashing import sha256_file


CONTENT_BASIS_SCHEMA_VERSION = "policyos.catalog_stage_basis.v1"
OUTPUT_INVENTORY_SCHEMA_VERSION = "policyos.catalog_stage_outputs.v1"


def _json_dumps(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def load_json(path: Path, *, default: Any) -> Any:
    """Load json."""
    if not path.exists():
        return default
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return default


def write_json(path: Path, payload: Any) -> None:
    """Write json helper."""
    path.parent.mkdir(parents=True, exist_ok=True)
    # Keep the historical formatter byte-for-byte while sharing the kernel's
    # directory-fsyncing atomic publication boundary.
    atomic_write_text(
        path,
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
    )


def hash_payload(payload: Any) -> str:
    """Hash payload helper."""
    return hashlib.sha256(_json_dumps(payload).encode("utf-8")).hexdigest()


def fingerprint_paths(paths: list[Path]) -> str:
    """Fingerprint paths helper."""
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


def build_content_basis(
    *,
    stage: str,
    rule_version: str,
    config: Mapping[str, object],
    inputs: Mapping[str, Path | Sequence[Path] | None],
    trusted_inputs: Mapping[str, Mapping[str, object]] | None = None,
) -> dict[str, object]:
    """Build a small content-bound basis for one stage's selected inputs.

    ``inputs`` is deliberately caller-selected.  This helper does not scan a
    repository or a snapshot root implicitly.  A trusted input receipt may be
    reused when its path and stat tuple still match the pipeline-owned
    immutable output it describes; otherwise the current bytes are hashed.
    """
    normalized_inputs: dict[str, object] = {}
    trusted_inputs = trusted_inputs or {}
    for label, selected in sorted(inputs.items()):
        if selected is None:
            paths: list[Path] | None = None
        elif isinstance(selected, Path):
            paths = [selected]
        else:
            paths = list(selected)
        normalized_inputs[label] = {
            "paths": None if paths is None else [str(path.resolve()) for path in paths],
            "records": (
                None
                if paths is None
                else [
                    _content_record(
                        path,
                        trusted=trusted_inputs.get(label) if len(paths) == 1 else None,
                    )
                    for path in paths
                ]
            ),
        }
    payload: dict[str, object] = {
        "schema_version": CONTENT_BASIS_SCHEMA_VERSION,
        "stage": str(stage),
        "rule_version": str(rule_version),
        "config": _json_safe(config),
        "inputs": normalized_inputs,
    }
    return {**payload, "basis_digest": hash_payload(payload)}


def build_output_inventory(paths: Sequence[Path]) -> dict[str, object]:
    """Describe selected stage outputs by bytes, not existence alone."""
    entries = [_content_record(path, recurse=path.is_dir()) for path in paths]
    entries.sort(key=lambda item: str(item.get("path", "")))
    payload: dict[str, object] = {
        "schema_version": OUTPUT_INVENTORY_SCHEMA_VERSION,
        "entries": entries,
    }
    return {**payload, "inventory_digest": hash_payload(payload)}


def load_stage_state(path: Path) -> dict[str, dict[str, Any]]:
    """Load stage state."""
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
    input_basis: Mapping[str, object] | None = None,
    output_inventory: Mapping[str, object] | None = None,
) -> None:
    """Save stage state helper."""
    state = load_stage_state(path)
    stage_state: dict[str, object] = {
        "status": str(status),
        "input_fingerprint": str(input_fingerprint),
        "outputs": [str(item) for item in (outputs or [])],
        "metadata": metadata or {},
    }
    if input_basis is not None:
        stage_state["input_basis"] = dict(input_basis)
    if output_inventory is not None:
        stage_state["output_inventory"] = dict(output_inventory)
    state[str(stage)] = stage_state
    write_json(path, state)


def stage_can_skip(
    path: Path,
    *,
    stage: str,
    input_fingerprint: str,
    required_outputs: list[Path] | None = None,
    expected_input_basis: Mapping[str, object] | None = None,
    expected_output_inventory: Mapping[str, object] | None = None,
    require_content_bound: bool = False,
) -> bool:
    """Stage can skip helper."""
    state = load_stage_state(path)
    current = state.get(str(stage))
    if not isinstance(current, dict):
        return False
    if str(current.get("status")) != "complete":
        return False
    if str(current.get("input_fingerprint", "")) != str(input_fingerprint):
        return False
    if require_content_bound:
        recorded_basis = current.get("input_basis")
        recorded_inventory = current.get("output_inventory")
        if not isinstance(recorded_basis, Mapping) or not isinstance(
            recorded_inventory, Mapping
        ):
            return False
        if expected_input_basis is None or dict(recorded_basis) != dict(expected_input_basis):
            return False
        if expected_output_inventory is None or dict(recorded_inventory) != dict(
            expected_output_inventory
        ):
            return False
    outputs = (
        [Path(item) for item in current.get("outputs", []) if item]
        if required_outputs is None
        else required_outputs
    )
    return all(path.exists() for path in outputs)


def _content_record(
    path: Path,
    *,
    recurse: bool = False,
    trusted: Mapping[str, object] | None = None,
) -> dict[str, object]:
    resolved = Path(path).resolve()
    if resolved.is_file():
        stat = resolved.stat()
        if (
            trusted is not None
            and str(trusted.get("path")) == str(resolved)
            and trusted.get("exists") is True
            and trusted.get("kind") == "file"
            and trusted.get("size") == int(stat.st_size)
            and trusted.get("mtime_ns") == int(stat.st_mtime_ns)
            and isinstance(trusted.get("sha256"), str)
            and trusted.get("sha256")
        ):
            return {
                **{key: value for key, value in trusted.items() if key != "mtime_ns"},
                "source": "pipeline_owned_immutable_receipt",
            }
        record: dict[str, object] = {
            "path": str(resolved),
            "kind": "file",
            "exists": True,
            "size": int(stat.st_size),
            "sha256": sha256_file(resolved),
        }
        if (
            trusted is not None
            and str(trusted.get("path")) == str(resolved)
            and trusted.get("sha256") == record["sha256"]
        ):
            record["source"] = "pipeline_owned_immutable_receipt"
        return record
    if resolved.is_dir() and recurse:
        members: list[dict[str, object]] = []
        for child in sorted(item for item in resolved.rglob("*") if item.is_file()):
            stat = child.stat()
            members.append(
                {
                    "path": str(child.relative_to(resolved)),
                    "size": int(stat.st_size),
                    "sha256": sha256_file(child),
                }
            )
        return {
            "path": str(resolved),
            "kind": "directory",
            "exists": True,
            "members": members,
        }
    if resolved.is_dir():
        return {"path": str(resolved), "kind": "directory", "exists": True}
    return {
        "path": str(resolved),
        "kind": "directory" if recurse else "file",
        "exists": False,
    }


def _json_safe(value: object) -> object:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


__all__ = [
    "CONTENT_BASIS_SCHEMA_VERSION",
    "OUTPUT_INVENTORY_SCHEMA_VERSION",
    "build_content_basis",
    "build_output_inventory",
    "fingerprint_paths",
    "hash_payload",
    "load_json",
    "load_stage_state",
    "save_stage_state",
    "stage_can_skip",
    "write_json",
]
