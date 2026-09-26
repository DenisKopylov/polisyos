#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

from tools.lib.imports import repo_root_from


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
    parser.add_argument(
        "--scratch-root",
        type=Path,
        help="Keep the runtime CAS used for export at this new directory.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    repo_root = repo_root_from(__file__)
    src_root = repo_root / "src"
    if str(src_root) not in sys.path:
        sys.path.insert(0, str(src_root))

    from polisyos.runtime.http.app import create_runtime_api_app

    args.output.parent.mkdir(parents=True, exist_ok=True)

    def render(scratch: Path) -> dict:
        app = create_runtime_api_app(enable_security_middlewares=False, cas_root=scratch / "cas")
        return app.openapi()

    if args.scratch_root is None:
        with tempfile.TemporaryDirectory(
            prefix="runtime_openapi_", dir=args.output.parent
        ) as scratch:
            schema = render(Path(scratch))
    else:
        scratch = args.scratch_root.resolve()
        scratch.mkdir(parents=True, exist_ok=False)
        schema = render(scratch)

    args.output.write_text(
        json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(args.output.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
