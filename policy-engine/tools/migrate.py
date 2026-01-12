#!/usr/bin/env python3
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import argparse
import json
from typing import Tuple

try:
    import yaml  # type: ignore
except Exception:
    yaml = None

from polisyos.common.migrations import (
    MANIFEST_CURRENT_VERSION,
    POLICY_IR_CURRENT_VERSION,
    migrate_artifact,
)


def _load(path: Path) -> Tuple[dict, str]:
    raw = path.read_text(encoding="utf-8")
    if path.suffix.lower() in {".yaml", ".yml"}:
        if yaml is None:
            raise RuntimeError("PyYAML is not installed; only JSON is supported.")
        return yaml.safe_load(raw), "yaml"
    return json.loads(raw), "json"


def _dump(path: Path, data: dict, fmt: str) -> None:
    if fmt == "yaml":
        if yaml is None:
            raise RuntimeError("PyYAML is not installed; only JSON is supported.")
        path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
        return
    path.write_text(json.dumps(data, ensure_ascii=True, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate schema artifacts to target version.")
    parser.add_argument("artifact", choices=["policy_ir", "dataset_manifest", "run_manifest"])
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--to", dest="target_version")
    args = parser.parse_args()

    data, fmt = _load(args.input)
    if args.artifact == "run_manifest":
        # Convert absolute paths to relative and attach run_root
        manifest_dir = args.input.parent
        base_dir = manifest_dir.parent
        artifacts = data.get("artifacts", [])
        new_artifacts = []
        for art in artifacts:
            path_val = art.get("path")
            rel = art.get("relative_path")
            if rel is None and path_val:
                try:
                    rel_path = str(Path(path_val).relative_to(base_dir))
                except Exception:
                    rel_path = Path(path_val).name
                art["relative_path"] = rel_path
                art["path"] = rel_path
            new_artifacts.append(art)
        data["artifacts"] = new_artifacts
        data.setdefault("run_root", str(base_dir))
        _dump(args.output, data, fmt)
        return

    if args.target_version:
        target = args.target_version
    else:
        if args.artifact == "policy_ir":
            target = POLICY_IR_CURRENT_VERSION
        else:
            target = MANIFEST_CURRENT_VERSION

    migrated = migrate_artifact(data, args.artifact, target)
    _dump(args.output, migrated, fmt)


if __name__ == "__main__":
    main()
