from __future__ import annotations

import argparse
import importlib
import json
import sys
import tempfile
from pathlib import Path

import uvicorn


def _load_fixture_builder():
    policy_engine_root = Path(__file__).resolve().parents[3]
    import_roots = [
        policy_engine_root / "src",
        policy_engine_root,
        policy_engine_root / "tests",
    ]
    for root in import_roots:
        root_str = str(root)
        if root_str not in sys.path:
            sys.path.insert(0, root_str)

    module = importlib.import_module("fixtures.runtime_http")
    return module.build_runtime_api_env


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve fixture-backed runtime API for frontend e2e.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--metadata-file", default=None)
    args = parser.parse_args()

    build_runtime_api_env = _load_fixture_builder()
    tmp_root = Path(tempfile.mkdtemp(prefix="runtime-dashboard-e2e-"))
    env = build_runtime_api_env(tmp_root, include_test_client=False)
    app = env["app"]

    if args.metadata_file:
        metadata_path = Path(args.metadata_file)
        metadata_path.parent.mkdir(parents=True, exist_ok=True)
        metadata = {
            key: value
            for key, value in env.items()
            if key not in {"app", "client", "cas_root"}
        }
        metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
