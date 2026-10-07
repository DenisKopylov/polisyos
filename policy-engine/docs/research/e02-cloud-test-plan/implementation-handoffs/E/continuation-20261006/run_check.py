"""Capture a command against an immutable E02 source candidate."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import resource
import shutil
import subprocess
import sys
import time
from pathlib import Path


def main() -> int:
    """Save complete stdout and actual exit/source/environment evidence."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--cwd", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command
    if command[:1] == ["--"]:
        command = command[1:]
    if not command:
        parser.error("supply an actual command after --")

    def git(*argv: str) -> str:
        # Operator-selected Git arguments are passed directly, without a shell.
        return subprocess.check_output(  # noqa: S603
            [shutil.which("git") or "/usr/bin/git", "-C", str(args.repo), *argv], text=True
        ).strip()

    def source_identity() -> str:
        paths = git("ls-files", "policy-engine/src", "policy-engine/tests").splitlines()
        digest = hashlib.sha256()
        for relative in paths:
            path = args.repo / relative
            digest.update(relative.encode() + b"\0")
            digest.update(path.read_bytes() if path.is_file() else b"ABSENT")
            digest.update(b"\0")
        return digest.hexdigest()

    args.output.mkdir(parents=True, exist_ok=True)
    if git("rev-parse", "HEAD") != args.candidate:
        raise RuntimeError("checkout HEAD differs from the declared immutable candidate")
    before = source_identity()
    environment_names = (
        "OMP_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "MKL_NUM_THREADS",
        "NUMEXPR_NUM_THREADS",
        "VECLIB_MAXIMUM_THREADS",
        "BLIS_NUM_THREADS",
        "XLA_FLAGS",
        "JAX_PLATFORMS",
        "JAX_ENABLE_X64",
        "POLISYOS_PYTEST_WORKERS",
        "UV_NO_SYNC",
        "PYTHONPATH",
        "TMPDIR",
    )
    started = time.time()
    stdout_path = args.output / (args.name + ".stdout.txt")
    with stdout_path.open("wb") as output:
        # This receipt runner executes the explicit operator command, without a shell.
        completed = subprocess.run(  # noqa: S603
            command, cwd=args.cwd, stdout=output, stderr=subprocess.STDOUT
        )
    after = source_identity()
    result = {
        "schema": "policyos.e02.frozen_check.v1",
        "candidate_sha": args.candidate,
        "candidate_tree_sha": git("rev-parse", args.candidate + "^{tree}"),
        "head_at_end": git("rev-parse", "HEAD"),
        "command": command,
        "cwd": str(args.cwd),
        "exit_code": completed.returncode,
        "outcome": "PASS" if completed.returncode == 0 and before == after else "FAIL",
        "started_unix": started,
        "wall_seconds": time.time() - started,
        "max_rss_kib": resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "selected_variables": {name: os.environ.get(name) for name in environment_names},
        },
        "source_identity_before": before,
        "source_identity_after": after,
        "source_immutable": before == after,
        "stdout_path": str(stdout_path),
        "stdout_bytes": stdout_path.stat().st_size,
        "stdout_sha256": hashlib.sha256(stdout_path.read_bytes()).hexdigest(),
        "P41": "not_established; no inherited-red attribution",
    }
    (args.output / (args.name + ".json")).write_text(json.dumps(result, indent=2) + "\n")
    sys.stdout.write(
        json.dumps(
            {
                key: result[key]
                for key in (
                    "command",
                    "exit_code",
                    "outcome",
                    "wall_seconds",
                    "source_immutable",
                    "stdout_path",
                )
            }
        )
        + "\n"
    )
    return completed.returncode if before == after else 1


if __name__ == "__main__":
    raise SystemExit(main())
