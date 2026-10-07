"""Replay the current slice base from tracked inputs, without a new Git worktree."""

from __future__ import annotations

import hashlib
import io
import json
import os
import platform
import subprocess
import sys
import tarfile
import time
from pathlib import Path

BASE = "d53d147aacec22628eda54864c6f4a06bc7b214f"
OVERLAY = "b6e47f50c5bc24ecb0249d47e9dc0f4588c332aa"
PYTHON = "/workspace/polisyos/policy-engine/.venv/bin/python"
ROOT = Path.cwd().parent
SNAPSHOT = Path.cwd() / "_build/e02-B-current-cas-generation/snapshot-base-input"
RAW = Path.cwd() / "_build/e02-B-current-cas-generation/raw"
SOURCE_PATHS = [
    "policy-engine/src",
    "policy-engine/tests",
    "policy-engine/pytest.ini",
    "policy-engine/pyproject.toml",
    "policy-engine/uv.lock",
]
OVERLAY_PATHS = [
    "policy-engine/tests/unit/core/artifacts/test_verification_snapshot_report.py",
    "policy-engine/tests/unit/core/artifacts/snapshot_special_path_worker.py",
]
archive = subprocess.check_output(  # noqa: S603 - exact immutable authored Git input
    ["/usr/bin/git", "archive", BASE, *SOURCE_PATHS], cwd=ROOT
)
SNAPSHOT.mkdir(exist_ok=False)
with tarfile.open(fileobj=io.BytesIO(archive)) as source:
    source.extractall(SNAPSHOT, filter="data")
for path in OVERLAY_PATHS:
    data = subprocess.check_output(  # noqa: S603 - exact immutable authored Git input
        ["/usr/bin/git", "show", f"{OVERLAY}:{path}"], cwd=ROOT
    )
    (SNAPSHOT / path).write_bytes(data)
product = SNAPSHOT / "policy-engine"
store_path = "policy-engine/src/polisyos/core/artifacts/store.py"
base_store = subprocess.check_output(  # noqa: S603 - exact immutable authored Git input
    ["/usr/bin/git", "show", f"{BASE}:{store_path}"], cwd=ROOT
)
if (SNAPSHOT / store_path).read_bytes() != base_store:
    raise RuntimeError("source projection differs from its bound base")
environment = dict(os.environ, PYTHONPATH="src")
environment.pop("E02_B_PROPERTY_REMOVAL", None)
commands = {
    "snapshot-base-replay": [
        PYTHON,
        "-m",
        "pytest",
        "-q",
        "--tb=short",
        "tests/unit/core/artifacts/test_verification_snapshot_report.py",
        "--basetemp=" + str(RAW.parent / "snapshot-base-replay-tmp"),
        "-o",
        "cache_dir=" + str(RAW.parent / "snapshot-base-replay-cache"),
        "--junitxml=" + str(RAW / "snapshot-base-replay.xml"),
    ],
    "snapshot-base-mypy": [
        PYTHON,
        "-m",
        "mypy",
        "--follow-imports=silent",
        "src/polisyos/core/artifacts/store.py",
        "src/polisyos/core/artifacts/_signature_ops.py",
        "src/polisyos/core/artifacts/_integrity_ops.py",
        "src/polisyos/core/artifacts/cas_integrity_report.py",
        "src/polisyos/core/artifacts/protocol.py",
    ],
}
for tag, argv in commands.items():
    started = time.monotonic()
    with (RAW / (tag + ".txt")).open("wb") as output:
        # Authored fixed interpreter/arguments, with no shell or runner quota.
        child = subprocess.Popen(  # noqa: S603
            argv, cwd=product, env=environment, stdout=output, stderr=subprocess.STDOUT
        )
        waited, status, usage = os.wait4(child.pid, 0)
        if waited != child.pid:
            raise RuntimeError("resource accounting returned a different child")
        child.returncode = os.waitstatus_to_exitcode(status)
    record = {
        "target_sha": BASE,
        "base_tree": subprocess.check_output(  # noqa: S603 - exact immutable Git ref
            ["/usr/bin/git", "rev-parse", BASE + "^{tree}"], cwd=ROOT, text=True
        ).strip(),
        "cwd": str(product),
        "argv": argv,
        "python": PYTHON,
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "PYTHONPATH": "src",
        "source_archive": {
            "sha256": hashlib.sha256(archive).hexdigest(),
            "bytes": len(archive),
            "paths": SOURCE_PATHS,
        },
        "overlay": [
            {
                "ref": f"{path}@{OVERLAY}",
                "sha256": hashlib.sha256((SNAPSHOT / path).read_bytes()).hexdigest(),
            }
            for path in OVERLAY_PATHS
        ],
        "returncode": child.returncode,
        "wall_s": time.monotonic() - started,
        "max_rss_kib": usage.ru_maxrss,
        "runner_quota": None,
        "custody_boundary": (
            "Fresh tracked source projection inside the root-admitted CAS lane ignored scratch; "
            "no new Git checkout/worktree or retrospective admission claim."
        ),
        "rusage_boundary": (
            "os.wait4 exact subprocess PID; kernel child and descendant accounting, not VM peak"
        ),
    }
    (RAW / (tag + ".run.json")).write_text(json.dumps(record, indent=2) + "\n")
    sys.stdout.write(json.dumps(record) + "\n")
