"""Launch a live runtime canary from the installed release artifact and probe it."""

from __future__ import annotations

import argparse
import json
import socket
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import uvicorn

from polisyos.runtime.http.app import create_runtime_api_app


PROBES = (
    ("/health", {"status": "ok"}),
    ("/ready", {"status": "ready"}),
    ("/api/v1/health", {"status": "ok", "service": "runtime_api_v1"}),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run release canary probes against a live runtime app")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8010)
    parser.add_argument("--summary", help="Optional markdown summary output path")
    parser.add_argument("--json-output", help="Optional JSON output path")
    return parser.parse_args()


def _wait_for_port(host: str, port: int, *, timeout_seconds: float) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.25)
            if sock.connect_ex((host, port)) == 0:
                return
        time.sleep(0.1)
    raise TimeoutError(f"Timed out waiting for {host}:{port}")


def _probe(base_url: str) -> list[dict[str, object]]:
    checks: list[dict[str, object]] = []
    for path, expected in PROBES:
        url = f"{base_url}{path}"
        with urllib.request.urlopen(url, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
        missing = {
            key: expected_value
            for key, expected_value in expected.items()
            if payload.get(key) != expected_value
        }
        checks.append(
            {
                "path": path,
                "status": "ok" if not missing else "mismatch",
                "payload": payload,
                "expected": expected,
                "missing": missing,
            }
        )
    return checks


def _write_summary(path: Path, checks: list[dict[str, object]]) -> None:
    lines = ["# Release Canary Summary", ""]
    for check in checks:
        lines.append(
            f"- `{check['path']}`: {check['status']} -> `{json.dumps(check['payload'], sort_keys=True)}`"
        )
    lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    args = parse_args()
    tmp_root = Path(tempfile.mkdtemp(prefix="release-canary-"))
    app = create_runtime_api_app(cas_root=tmp_root / ".polisyos")
    config = uvicorn.Config(app, host=args.host, port=args.port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    checks: list[dict[str, object]] = []
    try:
        _wait_for_port(args.host, args.port, timeout_seconds=20)
        checks = _probe(f"http://{args.host}:{args.port}")
    except (OSError, TimeoutError, urllib.error.URLError, ValueError) as exc:
        checks = [{"path": "startup", "status": "error", "payload": {"error": str(exc)}}]
        if args.summary:
            _write_summary(Path(args.summary).resolve(), checks)
        if args.json_output:
            Path(args.json_output).resolve().write_text(
                json.dumps({"checks": checks}, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        return 1
    finally:
        server.should_exit = True
        thread.join(timeout=10)

    if args.summary:
        _write_summary(Path(args.summary).resolve(), checks)
    if args.json_output:
        Path(args.json_output).resolve().write_text(
            json.dumps({"checks": checks}, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    failures = [check for check in checks if check["status"] != "ok"]
    if failures:
        for failure in failures:
            print(f"Release canary probe failed: {failure['path']}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
