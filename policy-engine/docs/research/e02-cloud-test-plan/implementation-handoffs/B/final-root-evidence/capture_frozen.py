"""Capture complete child output and wait4 status on one unchanged Git candidate."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
import traceback
from pathlib import Path


def main() -> None:
    """Run argv without a shell, preserving output and the observed source boundary."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--tag", required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    argv = args.command[1:] if args.command[:1] == ["--"] else args.command
    repo = Path(args.repo)
    out = repo / ".polisyos/e02-B-current/raw/review"
    out.mkdir(parents=True, exist_ok=True)

    def git(*words: str) -> str:
        return subprocess.check_output(  # noqa: S603 - fixed Git, literal read-only subcommands
            ["/usr/bin/git", "-C", str(repo), *words], text=True
        ).strip()

    head = git("rev-parse", "HEAD")
    tree = git("rev-parse", "HEAD^{tree}")
    started = time.monotonic()
    log = out / (args.tag + ".txt")
    wrapper = out / (args.tag + ".json")
    if wrapper.exists():
        raise FileExistsError("Refuse to overwrite a prior deciding wrapper")
    fd = os.open(log, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    setup_read, setup_write = os.pipe2(os.O_CLOEXEC)
    pid = os.fork()
    if pid == 0:
        os.close(setup_read)
        try:
            os.dup2(fd, 1)
            os.dup2(fd, 2)
            os.close(fd)
            os.chdir(repo / "policy-engine")
            os.execvpe(argv[0], argv, dict(os.environ))  # noqa: S606 - reviewed argv-only launcher
        except BaseException as exc:
            os.write(setup_write, (type(exc).__name__ + ": " + str(exc)).encode()[:2048])
            traceback.print_exc()
            os._exit(127)
    os.close(fd)
    os.close(setup_write)
    _, status, usage = os.wait4(pid, 0)
    setup_error = os.read(setup_read, 2048).decode(errors="replace") or None
    os.close(setup_read)
    code = os.waitstatus_to_exitcode(status)
    record = {
        "command": argv,
        "cwd": str(repo / "policy-engine"),
        "head": head,
        "tree": tree,
        "head_after": git("rev-parse", "HEAD"),
        "wall_s": time.monotonic() - started,
        "process_rusage_maxrss_kib": usage.ru_maxrss,
        "exit_code": code,
        "exec_setup_error": setup_error,
        "harness_state": "UNRUN" if setup_error else "EXECUTED",
        "output_path": str(log),
        "output_sha256": hashlib.sha256(log.read_bytes()).hexdigest(),
        "source_environment": {
            key: os.environ.get(key)
            for key in (
                "PYTHONPATH",
                "PATH",
                "LANG",
                "POLISYOS_METRICS_PORT",
                "TIKTOKEN_CACHE_DIR",
                "E02_B_PROPERTY_REMOVAL",
                "UV_PROJECT_ENVIRONMENT",
                "UV_NO_SYNC",
                "E02_B_COHORT_INVENTORY_PATH",
            )
        },
        "limitations": [
            "Combined stdout/stderr; no separate stream-count claim.",
            "Source boundary is HEAD identity; the launcher checks initial cleanliness.",
            "RSS is wait4 child rusage, not an aggregate of independently concurrent gates.",
        ],
    }
    if record["head_after"] != head:
        raise RuntimeError("Candidate changed during deciding check")
    with wrapper.open("x") as stream:
        json.dump(record, stream, indent=2)
        stream.write("\n")
    sys.stdout.write(json.dumps(record, indent=2) + "\n")
    raise SystemExit(code)


if __name__ == "__main__":
    main()
