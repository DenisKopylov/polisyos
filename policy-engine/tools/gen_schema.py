#!/usr/bin/env python3
from __future__ import annotations

import argparse
import difflib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from polisyos.ir.contract import PolicyRequestIR


def generate_schema() -> str:
    schema = PolicyRequestIR.model_json_schema()
    return json.dumps(schema, indent=2)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate or check the committed JSON Schema snapshot."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("policy_ir_schema.json"),
        help="Schema snapshot path",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail if the snapshot does not match the generated schema",
    )
    args = parser.parse_args()

    output_path = args.output
    schema_str = generate_schema()

    if args.check:
        if not output_path.exists():
            print(f"Schema snapshot missing: {output_path}")
            return 1
        current = output_path.read_text(encoding="utf-8")
        if current != schema_str:
            print(f"Schema snapshot out of date: {output_path}")
            diff = difflib.unified_diff(
                current.splitlines(),
                schema_str.splitlines(),
                fromfile=str(output_path),
                tofile="generated",
                lineterm="",
            )
            print("\n".join(diff))
            return 1
        print("Schema snapshot: up to date")
        return 0

    output_path.write_text(schema_str, encoding="utf-8")
    print(f"Wrote schema snapshot: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
