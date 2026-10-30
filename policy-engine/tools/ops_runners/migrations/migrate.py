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
from tools.ops_runners.migrations.contracts import (
    resolve_contract_root,
    resolve_helper_implementation,
    validate_helper_binding,
)


def _resolve_migration_roots(module_path: str | Path) -> tuple[Path, Path]:
    """Resolve contract roots without adding a checkout to an installed runner."""
    module_file = Path(module_path).resolve()
    root = resolve_contract_root(module_path=module_file)
    if module_file == (root / "tools/ops_runners/migrations/migrate.py").resolve():
        ensure_repo_import_roots(module_file)
    return root, root / "src"


REPO_ROOT, SRC_ROOT = _resolve_migration_roots(__file__)

try:
    import yaml  # type: ignore
except ImportError:
    yaml = None

from polisyos.common.migrations import (
    migrate_artifact as migrate_common_artifact,
)
from polisyos.ir.migrations import POLICY_IR_CURRENT_VERSION


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
    if not isinstance(data, dict):
        raise TypeError("migration output must be a JSON/YAML object")
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
    binding = validate_helper_binding(args.artifact, REPO_ROOT)
    implementation = resolve_helper_implementation(binding)

    data, fmt = _load(args.input)
    if args.artifact == "run_manifest":
        migrated = implementation(
            data,
            manifest_path=args.input,
            target_version=args.target_version,
        )
        _dump(args.output, migrated, fmt)
        return 0

    if args.artifact == "policy_ir":
        target = args.target_version or POLICY_IR_CURRENT_VERSION
        migrated = implementation(data, target)
    else:
        from polisyos.fabric.identity.migrations import MANIFEST_CURRENT_VERSION

        target = args.target_version or MANIFEST_CURRENT_VERSION
        migrated = migrate_common_artifact(
            data, args.artifact, target, selected_edges={"0.9": ("1.0", implementation)}
        )
    _dump(args.output, migrated, fmt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
