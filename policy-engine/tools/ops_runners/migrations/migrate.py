#!/usr/bin/env python3
"""Migrate schema artifacts to their declared target versions."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from tools.lib.fs import atomic_write_text
from tools.lib.imports import ensure_repo_import_roots

REPO_ROOT, SRC_ROOT = ensure_repo_import_roots(__file__)

try:
    import yaml  # type: ignore
except ImportError:
    yaml = None

from polisyos.common.migrations import (
    MANIFEST_CURRENT_VERSION,
)
from polisyos.common.migrations import (
    migrate_artifact as migrate_common_artifact,
)
from polisyos.ir.migrations import POLICY_IR_CURRENT_VERSION, migrate_policy_ir
from tools.ops_runners.migrations.contracts import validate_helper_binding


def _load(path: Path) -> tuple[dict[str, Any], str]:
    raw = path.read_text(encoding="utf-8")
    if path.suffix.lower() in {".yaml", ".yml"}:
        if yaml is None:
            raise RuntimeError("PyYAML is not installed; only JSON is supported.")
        payload = yaml.safe_load(raw)
        fmt = "yaml"
    else:
        payload = json.loads(raw)
        fmt = "json"
    if not isinstance(payload, dict):
        raise ValueError(f"migration input must be a JSON/YAML object: {path}")
    return payload, fmt


def _dump(path: Path, data: dict[str, Any], fmt: str) -> None:
    if fmt == "yaml":
        if yaml is None:
            raise RuntimeError("PyYAML is not installed; only JSON is supported.")
        atomic_write_text(path, yaml.safe_dump(data, sort_keys=False))
        return
    atomic_write_text(path, json.dumps(data, ensure_ascii=True, indent=2) + "\n")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Migrate schema artifacts to target version.")
    parser.add_argument("artifact", choices=["policy_ir", "dataset_manifest", "run_manifest"])
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--to", dest="target_version")
    args = parser.parse_args(argv)
    validate_helper_binding(args.artifact, REPO_ROOT)

    data, fmt = _load(args.input)
    if args.artifact == "run_manifest":
        # Convert absolute paths to relative and attach run_root
        manifest_dir = args.input.parent
        base_dir = manifest_dir.parent
        artifacts = data.get("artifacts", [])
        if not isinstance(artifacts, list):
            raise ValueError("run_manifest artifacts must be a list")
        new_artifacts = []
        for art in artifacts:
            if not isinstance(art, dict):
                raise ValueError("run_manifest artifact entries must be objects")
            path_val = art.get("path")
            rel = art.get("relative_path")
            if rel is None and path_val:
                try:
                    rel_path = str(Path(path_val).relative_to(base_dir))
                except ValueError:
                    rel_path = Path(path_val).name
                art["relative_path"] = rel_path
                art["path"] = rel_path
            new_artifacts.append(art)
        data["artifacts"] = new_artifacts
        data.setdefault("run_root", str(base_dir))
        _dump(args.output, data, fmt)
        return 0

    if args.target_version:
        target = args.target_version
    else:
        if args.artifact == "policy_ir":
            target = POLICY_IR_CURRENT_VERSION
        else:
            target = MANIFEST_CURRENT_VERSION

    if args.artifact == "policy_ir":
        migrated = migrate_policy_ir(data, target)
    else:
        migrated = migrate_common_artifact(data, args.artifact, target)
    _dump(args.output, migrated, fmt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
