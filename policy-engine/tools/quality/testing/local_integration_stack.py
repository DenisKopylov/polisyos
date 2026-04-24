#!/usr/bin/env python3
"""Run the local runtime-dashboard integration stack and smoke profile."""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import time
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

from tools._lib.imports import repo_root_from

REPO_ROOT = repo_root_from(__file__)
DASHBOARD_ROOT = REPO_ROOT / "frontend" / "runtime-dashboard"
DEFAULT_RUNTIME_HOST = "127.0.0.1"
DEFAULT_RUNTIME_PORT = 8000
DEFAULT_DASHBOARD_HOST = "127.0.0.1"
DEFAULT_DASHBOARD_PORT = 5173
DEFAULT_METADATA_FILE = DASHBOARD_ROOT / ".tmp" / "fixture-runtime.local.json"


@dataclass(frozen=True)
class StackConfig:
    runtime_host: str
    runtime_port: int
    dashboard_host: str
    dashboard_port: int
    metadata_file: Path | None
    demo_data: str
    health_timeout_seconds: float


@dataclass
class ManagedProcess:
    name: str
    process: subprocess.Popen[bytes]

    def terminate(self) -> None:
        if self.process.poll() is not None:
            return
        self.process.terminate()
        try:
            self.process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=5)


def _http_ok(url: str) -> bool:
    try:
        with urlopen(url, timeout=2) as response:  # noqa: S310 - local-only URLs
            return 200 <= response.status < 300
    except URLError:
        return False


def _wait_for_url(url: str, *, timeout_seconds: float, name: str) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if _http_ok(url):
            return
        time.sleep(1)
    raise RuntimeError(f"Timed out waiting for {name} at {url}")


def _runtime_command(config: StackConfig) -> list[str]:
    command = [
        "uv",
        "run",
        "--extra",
        "runtime-http",
        "python",
        "frontend/runtime-dashboard/scripts/serve_fixture_runtime_api.py",
        "--host",
        config.runtime_host,
        "--port",
        str(config.runtime_port),
    ]
    if config.metadata_file is not None:
        command.extend(["--metadata-file", str(config.metadata_file)])
    return command


def _dashboard_command(config: StackConfig) -> list[str]:
    return [
        "npm",
        "run",
        "dev",
        "--",
        "--host",
        config.dashboard_host,
        "--port",
        str(config.dashboard_port),
    ]


def _spawn_process(
    name: str,
    command: list[str],
    *,
    cwd: Path,
    env_overrides: Mapping[str, str] | None = None,
) -> ManagedProcess:
    env = os.environ.copy()
    if env_overrides:
        env.update(env_overrides)
    process = subprocess.Popen(command, cwd=cwd, env=env)
    return ManagedProcess(name=name, process=process)


def _build_stack(config: StackConfig) -> list[ManagedProcess]:
    if config.metadata_file is not None:
        config.metadata_file.parent.mkdir(parents=True, exist_ok=True)

    runtime = _spawn_process(
        "runtime-api",
        _runtime_command(config),
        cwd=REPO_ROOT,
    )
    dashboard = _spawn_process(
        "runtime-dashboard",
        _dashboard_command(config),
        cwd=DASHBOARD_ROOT,
        env_overrides={
            "RUNTIME_API_URL": f"http://{config.runtime_host}:{config.runtime_port}",
            "VITE_DISABLE_RUNS_LIVE": "true",
        },
    )
    return [runtime, dashboard]


def _health_urls(config: StackConfig) -> dict[str, str]:
    runtime_base = f"http://{config.runtime_host}:{config.runtime_port}"
    dashboard_base = f"http://{config.dashboard_host}:{config.dashboard_port}"
    return {
        "runtime health": f"{runtime_base}/health",
        "dashboard dev server": dashboard_base,
        "dashboard proxy health": f"{dashboard_base}/api/v1/health",
    }


def _ensure_stack_healthy(config: StackConfig) -> None:
    for name, url in _health_urls(config).items():
        _wait_for_url(url, timeout_seconds=config.health_timeout_seconds, name=name)


def _cleanup(processes: list[ManagedProcess]) -> None:
    for process in reversed(processes):
        process.terminate()


def _print_stack_banner(config: StackConfig) -> None:
    print("Local integration stack is ready.")
    print(f"- runtime API: http://{config.runtime_host}:{config.runtime_port}")
    print(f"- dashboard:   http://{config.dashboard_host}:{config.dashboard_port}")
    if config.metadata_file is not None:
        print(f"- demo data:   {config.demo_data} ({config.metadata_file})")
    else:
        print(f"- demo data:   {config.demo_data}")
    print("Press Ctrl+C to stop both processes.")


def _run_smoke_suite(config: StackConfig) -> int:
    smoke_env = os.environ.copy()
    smoke_env["RUNTIME_API_URL"] = f"http://{config.runtime_host}:{config.runtime_port}"
    smoke_env["VITE_DISABLE_RUNS_LIVE"] = "true"
    smoke_env.setdefault("PLAYWRIGHT_RETRIES", "0")
    command = ["npm", "run", "test:e2e:smoke"]
    return subprocess.run(command, cwd=DASHBOARD_ROOT, env=smoke_env, check=False).returncode


def _run_stack_until_interrupted(config: StackConfig) -> int:
    processes = _build_stack(config)
    try:
        _ensure_stack_healthy(config)
        _print_stack_banner(config)
        stop_requested = False

        def _handle_signal(_signum: int, _frame) -> None:  # pragma: no cover - interactive path
            nonlocal stop_requested
            stop_requested = True

        previous_sigint = signal.signal(signal.SIGINT, _handle_signal)
        previous_sigterm = signal.signal(signal.SIGTERM, _handle_signal)
        try:
            while not stop_requested:
                for process in processes:
                    if process.process.poll() is not None:
                        raise RuntimeError(
                            f"{process.name} exited early with code {process.process.returncode}"
                        )
                time.sleep(1)
        finally:
            signal.signal(signal.SIGINT, previous_sigint)
            signal.signal(signal.SIGTERM, previous_sigterm)
        return 0
    finally:
        _cleanup(processes)


def _run_stack_smoke(config: StackConfig) -> int:
    processes = _build_stack(config)
    try:
        _ensure_stack_healthy(config)
        print("Smoke profile: runtime + dashboard + proxy health are ready.")
        return _run_smoke_suite(config)
    finally:
        _cleanup(processes)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the fixture-backed local integration stack for runtime-dashboard.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    for subcommand in ("up", "smoke"):
        subparser = subparsers.add_parser(subcommand)
        subparser.add_argument("--runtime-host", default=DEFAULT_RUNTIME_HOST)
        subparser.add_argument("--runtime-port", type=int, default=DEFAULT_RUNTIME_PORT)
        subparser.add_argument("--dashboard-host", default=DEFAULT_DASHBOARD_HOST)
        subparser.add_argument("--dashboard-port", type=int, default=DEFAULT_DASHBOARD_PORT)
        subparser.add_argument(
            "--demo-data",
            choices=("fixture", "none"),
            default="fixture",
            help=(
                "fixture writes metadata for the lightweight demo dataset; "
                "none skips metadata export"
            ),
        )
        subparser.add_argument(
            "--metadata-file",
            default=str(DEFAULT_METADATA_FILE),
            help="where the fixture metadata file should be written when demo-data=fixture",
        )
        subparser.add_argument(
            "--health-timeout-seconds",
            type=float,
            default=120.0,
            help="per-endpoint health-check timeout",
        )

    return parser.parse_args()


def _config_from_args(args: argparse.Namespace) -> StackConfig:
    metadata_file = None
    if args.demo_data == "fixture":
        metadata_file = Path(args.metadata_file).resolve()

    return StackConfig(
        runtime_host=args.runtime_host,
        runtime_port=args.runtime_port,
        dashboard_host=args.dashboard_host,
        dashboard_port=args.dashboard_port,
        metadata_file=metadata_file,
        demo_data=args.demo_data,
        health_timeout_seconds=args.health_timeout_seconds,
    )


def main() -> int:
    args = _parse_args()
    config = _config_from_args(args)
    if args.command == "up":
        return _run_stack_until_interrupted(config)
    if args.command == "smoke":
        return _run_stack_smoke(config)
    raise ValueError(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
