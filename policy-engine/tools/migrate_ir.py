#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Tuple

try:
    import yaml  # type: ignore
except Exception:
    yaml = None

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from polisyos.ir.loaders import load_policy


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
    parser = argparse.ArgumentParser(description="Migrate policy IR artifacts.")
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--to", dest="target_version", default="2.0")
    parser.add_argument("--allow-major", action="store_true")
    args = parser.parse_args()

    data, fmt = _load(args.input)
    policy = load_policy(data)
    output_payload = policy.model_dump(mode="json")
    if args.target_version and args.target_version != policy.schema_version:
        print(
            f"Requested target_version={args.target_version}, "
            f"but PolicySurfaceIR schema_version is {policy.schema_version}. "
            "Only 2.x is supported."
        )
    _dump(args.output, output_payload, fmt)


if __name__ == "__main__":
    main()
