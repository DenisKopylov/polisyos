"""Run the complete Q2 source protocol cohort with retained bounded evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
from contextlib import suppress
from pathlib import Path
from typing import Any

import psutil

ROOT = next(
    parent
    for parent in Path(__file__).resolve().parents
    if (parent / ".git").exists() and (parent / "policy-engine").is_dir()
)
POLICY_ENGINE = ROOT / "policy-engine"
SOURCE_ROOT = Path(__file__).resolve().parent
TEST_ROOT = POLICY_ENGINE / "tests/repo_quality/tools/q2_composite"
RAW_ROOT = POLICY_ENGINE / "docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw"
R10_MANIFEST = SOURCE_ROOT / "source-manifest-r10.json"
COORDINATION_SCRIPT = (
    RAW_ROOT / "root-source-compute-coordination-20261020-r1/with_source_freeze_lock.py"
)
COORDINATION_SCRIPT_SHA256 = "662f9c1bbd665244c5c53cd846ade1ccc64ea0f23ced30f7570bb0f77218364f"
SOURCE_MANIFEST_DATA = json.loads(R10_MANIFEST.read_text(encoding="utf-8"))
SOURCE_SET = SOURCE_MANIFEST_DATA.get("source_set")
if type(SOURCE_SET) is not dict or type(SOURCE_SET.get("files")) is not list:
    raise ValueError("R10 source manifest has no complete source_set.files list")
SOURCE_FILES = (
    *(ROOT.joinpath(*Path(row["path"]).parts) for row in SOURCE_SET["files"]),
    R10_MANIFEST,
)
MAX_WALL_SECONDS = 90
MAX_TREE_RSS_BYTES = 1536 * 1024 * 1024
MIN_FREE_BYTES = 1 * 1024 * 1024 * 1024


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git(*args: str) -> str:
    result = subprocess.run(  # noqa: S603 -- fixed git path and local read-only arguments.
        ["/usr/bin/git", "-C", str(ROOT), *args],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    return result.stdout.strip()


def _process_tree_rss(process: psutil.Process) -> tuple[int, list[dict[str, int]]]:
    rows: list[dict[str, int]] = []
    for child in [process, *process.children(recursive=True)]:
        try:
            rows.append({"pid": child.pid, "rss_bytes": child.memory_info().rss})
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return sum(row["rss_bytes"] for row in rows), rows


def _kill_group(process: subprocess.Popen[bytes]) -> None:
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        with suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=2)


def _command(output: Path, *, pytest_tmp: Path) -> list[str]:
    python = str(POLICY_ENGINE / ".venv/bin/python")
    return [
        python,
        "-B",
        "-m",
        "pytest",
        "-q",
        "-o",
        "addopts=",
        "-o",
        f"cache_dir={output / 'pytest-cache'}",
        "--basetemp",
        str(pytest_tmp),
        "--junitxml",
        str(output / "pytest.xml"),
        str(TEST_ROOT / "test_split_protocol.py"),
        str(TEST_ROOT / "test_profile_composite.py"),
        str(TEST_ROOT / "test_worker_mounts.py"),
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--expected-head", required=True)
    parser.add_argument("--expected-tree", required=True)
    parser.add_argument("--state-parent", required=True, type=Path)
    args = parser.parse_args()
    if args.output.is_symlink():
        parser.error("output path may not be a symlink")
    output = args.output.resolve()
    if output.parent != RAW_ROOT / "q2-composite-r10" / "protocol-runs":
        parser.error("output must be an isolated child of the Q2 R10 protocol-runs directory")
    if not output.name or any(
        character not in "abcdefghijklmnopqrstuvwxyz0123456789-_" for character in output.name
    ):
        parser.error("output directory name must be a lowercase filesystem-safe token")
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists() and any(output.iterdir()):
        parser.error("output directory must be new and empty")
    output.mkdir(parents=True, exist_ok=True)
    for name in ("home", "tmp", "config", "cache"):
        (output / name).mkdir()
    # Do not let pytest or Hatchling place fixture trees below this checkout.
    # Hatchling's real sdist selector reads ancestor .gitignore files, so a
    # temporary root under LOCAL/raw changes the observed producer inputs.
    external_temp_root = args.state_parent.resolve(strict=True)
    if not external_temp_root.is_dir():
        parser.error("neutral state parent must be an existing directory")
    if external_temp_root.is_relative_to(ROOT):
        parser.error("neutral temporary root unexpectedly resolves inside the source checkout")
    pytest_tmp = Path(
        tempfile.mkdtemp(prefix=f"e02-q2-a94-{output.name}-", dir=external_temp_root)
    ).resolve(strict=True)
    if pytest_tmp.is_relative_to(ROOT):
        parser.error("pytest temporary state must be outside the source checkout")
    pytest_basetemp = pytest_tmp / "pytest-basetemp"
    python_temp = pytest_tmp / "python-tmp"
    pytest_basetemp.mkdir()
    python_temp.mkdir()
    disk_before = os.statvfs(output)
    free_before = disk_before.f_bavail * disk_before.f_frsize
    if free_before < MIN_FREE_BYTES:
        parser.error("free disk space is below the 1 GiB run floor")
    head_before = _git("rev-parse", "HEAD")
    tree_before = _git("rev-parse", "HEAD^{tree}")
    if head_before != args.expected_head or tree_before != args.expected_tree:
        parser.error("canonical source base differs from the authorized run identity")
    source_before = {str(path): _sha256(path) for path in SOURCE_FILES}
    if _sha256(COORDINATION_SCRIPT) != COORDINATION_SCRIPT_SHA256:
        parser.error("source-freeze coordinator differs from its reviewed SHA-256")
    command = _command(output, pytest_tmp=pytest_basetemp)
    environment = {
        "PATH": "/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin:/usr/local/bin",
        "HOME": str(output / "home"),
        # Hatchling reads ancestor .gitignore files while resolving source
        # fixtures. Keep both pytest basetemp and Python temp files outside the
        # checkout so fixtures observe only their own repository roots.
        "TMPDIR": str(python_temp),
        "XDG_CONFIG_HOME": str(output / "config"),
        "XDG_CACHE_HOME": str(output / "cache"),
        "PYTEST_ADDOPTS": "",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONNOUSERSITE": "1",
        "OPENBLAS_NUM_THREADS": "1",
        "OMP_NUM_THREADS": "1",
        "MKL_NUM_THREADS": "1",
        "NUMEXPR_NUM_THREADS": "1",
    }
    request = {
        "schema": "policyos.e02.q2.protocol-a94-request.v1",
        "canonical_source": {"head": head_before, "tree": tree_before},
        "candidate_source_sha256": source_before,
        "runner_sha256": _sha256(Path(__file__).resolve()),
        "source_freeze_coordinator": {
            "path": str(COORDINATION_SCRIPT),
            "sha256": COORDINATION_SCRIPT_SHA256,
        },
        "argv": command,
        "cwd": str(POLICY_ENGINE),
        "environment": environment,
        "timeout_seconds": MAX_WALL_SECONDS,
        "rss_limit_bytes": MAX_TREE_RSS_BYTES,
        "disk_floor_bytes": MIN_FREE_BYTES,
        "numeric_threads": 1,
        "pytest_plugin_autoload": "enabled",
        "pytest_temp_root": str(pytest_tmp),
        "pytest_temp_parent_requested": str(args.state_parent),
        "pytest_temp_parent_resolved": str(external_temp_root),
        "pytest_temp_root_outside_checkout": not pytest_tmp.is_relative_to(ROOT),
    }
    (output / "request.json").write_text(
        json.dumps(request, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    environment_view = dict(sorted(environment.items()))
    (output / "stdout.txt").write_bytes(b"")
    (output / "stderr.txt").write_bytes(b"")
    started = time.monotonic()
    max_tree_rss = 0
    rss_observations: list[dict[str, Any]] = []
    timed_out = False
    memory_limited = False
    with (output / "stdout.txt").open("wb") as stdout, (output / "stderr.txt").open("wb") as stderr:
        process = subprocess.Popen(  # noqa: S603 -- fixed pytest command from the local request.
            command,
            cwd=POLICY_ENGINE,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=stdout,
            stderr=stderr,
            start_new_session=True,
        )
        observed = psutil.Process(process.pid)
        while process.poll() is None:
            elapsed = time.monotonic() - started
            if elapsed >= MAX_WALL_SECONDS:
                timed_out = True
                _kill_group(process)
                break
            try:
                rss, members = _process_tree_rss(observed)
            except psutil.NoSuchProcess:
                rss, members = 0, []
            max_tree_rss = max(max_tree_rss, rss)
            if len(rss_observations) < 200 and (
                not rss_observations or elapsed - rss_observations[-1]["elapsed_seconds"] >= 1
            ):
                rss_observations.append(
                    {"elapsed_seconds": round(elapsed, 3), "rss_bytes": rss, "members": members}
                )
            if rss > MAX_TREE_RSS_BYTES:
                memory_limited = True
                _kill_group(process)
                break
            time.sleep(0.1)
        returncode = process.wait()
    elapsed = round(time.monotonic() - started, 3)
    source_after = {str(path): _sha256(path) for path in SOURCE_FILES}
    head_after = _git("rev-parse", "HEAD")
    tree_after = _git("rev-parse", "HEAD^{tree}")
    disk_after = os.statvfs(output)
    free_after = disk_after.f_bavail * disk_after.f_frsize
    result = {
        "schema": "policyos.e02.q2.protocol-a94-result.v1",
        "exit_code": returncode,
        "timed_out": timed_out,
        "memory_limited": memory_limited,
        "elapsed_seconds": elapsed,
        "max_process_tree_rss_bytes": max_tree_rss,
        "rss_observations": rss_observations,
        "stdout_bytes": (output / "stdout.txt").stat().st_size,
        "stdout_sha256": _sha256(output / "stdout.txt"),
        "stderr_bytes": (output / "stderr.txt").stat().st_size,
        "stderr_sha256": _sha256(output / "stderr.txt"),
        "environment": environment_view,
        "canonical_source_before": {"head": head_before, "tree": tree_before},
        "canonical_source_after": {"head": head_after, "tree": tree_after},
        "candidate_source_before_sha256": source_before,
        "candidate_source_after_sha256": source_after,
        "candidate_source_unchanged": source_before == source_after,
        "free_disk_before_bytes": free_before,
        "free_disk_after_bytes": free_after,
        "pytest_temp_root": str(pytest_tmp),
    }
    (output / "result.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    if (output / "pytest.xml").is_file():
        (output / "junit_sha256.txt").write_text(
            _sha256(output / "pytest.xml") + "\n", encoding="ascii"
        )
    sys.stdout.write(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return (
        returncode
        if returncode
        else int(
            timed_out
            or memory_limited
            or not result["candidate_source_unchanged"]
            or head_before != head_after
            or tree_before != tree_after
            or free_after < MIN_FREE_BYTES
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
