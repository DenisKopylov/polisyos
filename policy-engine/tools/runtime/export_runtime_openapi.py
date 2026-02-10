#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export Runtime API v1 OpenAPI schema to a deterministic JSON file."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("schemas/runtime_api_v1.openapi.json"),
        help="Output JSON path.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    repo_root = Path(__file__).resolve().parents[2]
    src_root = repo_root / "src"
    if str(src_root) not in sys.path:
        sys.path.insert(0, str(src_root))

    from polisyos.runtime.http.app import create_runtime_api_app

    app = create_runtime_api_app(enable_security_middlewares=False)
    schema = app.openapi()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(args.output.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
