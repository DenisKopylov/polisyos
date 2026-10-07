"""Capture four bounded removal controls on one admitted immutable candidate."""

from __future__ import annotations

import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET

ROOT = Path("/dev/shm/e02-D-oct07-continuation")
PRODUCT = ROOT / "policy-engine"
PLUGINS = Path(__file__).resolve().parent
PYTHON = "/tmp/e02-D-runtime-minimal-20261006/bin/python"
EXPECTED = sys.argv[1]
CONTROLS = json.loads((PLUGINS / "control-manifest-v2.json").read_text())["controls"]


def git(*args):
    return subprocess.check_output(["git", "-C", str(ROOT), *args], text=True).strip()


def binding(path):
    data = Path(path).read_bytes()
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


assert git("rev-parse", "HEAD") == EXPECTED, "unexpected source candidate"
assert git("status", "--porcelain=v1") == "", "source candidate is mutable"
OUTPUT = Path(tempfile.mkdtemp(prefix="e02-D-B124-removal-four-", dir="/dev/shm"))
env = dict(os.environ)
for key in (
    "OMP_NUM_THREADS",
    "MKL_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
    "PYTEST_XDIST_AUTO_NUM_WORKERS",
):
    env.pop(key, None)
env.update(
    PYTHONDONTWRITEBYTECODE="1",
    PYTHONPATH=os.pathsep.join([str(PRODUCT / "src"), str(PRODUCT), str(PLUGINS)]),
    UV_CACHE_DIR=str(OUTPUT / "uv-cache"),
    POLISYOS_TOOLS_TIMING_LOG=str(OUTPUT / "timing.jsonl"),
)
runtime = json.loads(
    subprocess.check_output(
        [
            PYTHON,
            "-c",
            "import sys,platform,json,importlib.metadata as m,polisyos;"
            "print(json.dumps({'python':sys.version,'executable':sys.executable,"
            "'platform':platform.platform(),'polisyos_origin':polisyos.__file__,"
            "'packages':{n:m.version(n) for n in ['pytest','pydantic','numpy','cryptography']}}))",
        ],
        cwd=PRODUCT,
        env=env,
        text=True,
    )
)
assert Path(runtime["polisyos_origin"]).is_relative_to(PRODUCT / "src")
source_paths = [
    "src/polisyos/scientist/methods/autotune/dedup.py",
    "src/polisyos/scientist/methods/autotune/runtime.py",
    "src/polisyos/scientist/methods/autotune/models.py",
    "src/polisyos/scientist/methods/autotune/registry.py",
    "src/polisyos/scientist/methods/search/frontier.py",
    "src/polisyos/scientist/methods/search/controller.py",
    "src/polisyos/scientist/methods/search/service.py",
    "src/polisyos/scientist/methods/search/contracts.py",
    "src/polisyos/scientist/methods/search/run_state.py",
    "src/polisyos/scientist/methods/search/pareto_registry.py",
    "src/polisyos/scientist/methods/search/objective.py",
    "src/polisyos/core/artifacts/store.py",
    "src/polisyos/core/artifacts/manifest.py",
    "src/polisyos/core/artifacts/manifest_profile.py",
    "src/polisyos/core/artifacts/_integrity_ops.py",
    "src/polisyos/core/artifacts/_atomic_write.py",
    "src/polisyos/core/canon/canon_json.py",
    "src/polisyos/common/serialization.py",
    "tests/unit/scientist/methods/search/test_service_trial_deduplication.py",
    "tests/unit/scientist/methods/search/test_semantic_dates_persisted_consumers.py",
]
inputs_before = {name: binding(PRODUCT / name) for name in source_paths}
records = []
for control in CONTROLS:
    name = control["plugin"]
    argv = [
        PYTHON,
        "-m",
        "pytest",
        "-o",
        "addopts=",
        "-o",
        "junit_family=xunit1",
        "--noconftest",
        "-p",
        "no:cacheprovider",
        "-p",
        name,
        "-s",
        "-ra",
        "--basetemp",
        str(OUTPUT / f"{name}-fixtures"),
        "--junitxml",
        str(OUTPUT / f"{name}.junit.xml"),
        control["selector"],
    ]
    record = {
        "control": control,
        "source_sha": EXPECTED,
        "source_tree": git("rev-parse", "HEAD^{tree}"),
        "command": argv,
        "cwd": str(PRODUCT),
        "runtime": runtime,
        "environment_overrides": {
            key: env[key]
            for key in (
                "PYTHONDONTWRITEBYTECODE",
                "PYTHONPATH",
                "UV_CACHE_DIR",
                "POLISYOS_TOOLS_TIMING_LOG",
            )
        },
        "no_artificial_resource_limits": True,
        "numerical_backend_requirement": "not_applicable; actual native evaluator/CAS/service",
        "inputs_before": inputs_before,
        "plugins": {
            f"{name}.py": binding(PLUGINS / f"{name}.py"),
            "removal_observation.py": binding(PLUGINS / "removal_observation.py"),
        },
        "started_utc": datetime.datetime.now(datetime.UTC).isoformat(),
    }
    (OUTPUT / f"{name}.command.json").write_text(json.dumps(record, indent=2) + "\n")
    started = time.monotonic()
    stdout_path = OUTPUT / f"{name}.stdout.txt"
    stderr_path = OUTPUT / f"{name}.stderr.txt"
    with stdout_path.open("w") as stdout, stderr_path.open("w") as stderr:
        result = subprocess.run(
            argv, cwd=PRODUCT, env=env, stdout=stdout, stderr=stderr
        )
    phases = {"PASS": 0, "FAIL": 0, "ERROR": 0, "SKIP": 0}
    junit = OUTPUT / f"{name}.junit.xml"
    if junit.exists():
        for case in ET.parse(junit).getroot().iter("testcase"):
            outcome = next(
                (
                    label
                    for label in ("failure", "error", "skipped")
                    if case.find(label) is not None
                ),
                None,
            )
            phases[
                {None: "PASS", "failure": "FAIL", "error": "ERROR", "skipped": "SKIP"}[
                    outcome
                ]
            ] += 1
    observations = [
        json.loads(line.split("REMOVAL_PERSISTED_OBSERVATION:", 1)[1])
        for line in stdout_path.read_text().splitlines()
        if line.startswith("REMOVAL_PERSISTED_OBSERVATION:")
    ]
    record.update(
        returncode=result.returncode,
        elapsed_seconds=time.monotonic() - started,
        completed_utc=datetime.datetime.now(datetime.UTC).isoformat(),
        case_phases=phases,
        persisted_observations=observations,
        outputs={
            path.name: binding(path)
            for path in (stdout_path, stderr_path, junit)
            if path.exists()
        },
        source_sha_after=git("rev-parse", "HEAD"),
        status_after=git("status", "--porcelain=v1"),
        inputs_after={name: binding(PRODUCT / name) for name in source_paths},
    )
    record["source_unchanged"] = (
        record["source_sha_after"] == EXPECTED
        and record["status_after"] == ""
        and record["inputs_after"] == inputs_before
    )
    record["negative_receipt_admitted"] = (
        record["source_unchanged"]
        and result.returncode == 1
        and phases == {"PASS": 0, "FAIL": 1, "ERROR": 0, "SKIP": 0}
        and bool(observations)
    )
    (OUTPUT / f"{name}.receipt.json").write_text(json.dumps(record, indent=2) + "\n")
    records.append(record)
    print(
        json.dumps(
            {
                "plugin": name,
                "returncode": result.returncode,
                "phases": phases,
                "observation_count": len(observations),
                "source_unchanged": record["source_unchanged"],
            }
        ),
        flush=True,
    )  # noqa: T201
summary = {
    "output_directory": str(OUTPUT),
    "source_sha": EXPECTED,
    "source_tree": git("rev-parse", "HEAD^{tree}"),
    "all_negatives_admitted": all(row["negative_receipt_admitted"] for row in records),
    "receipt_files": {
        f"{row['control']['plugin']}.receipt.json": binding(
            OUTPUT / f"{row['control']['plugin']}.receipt.json"
        )
        for row in records
    },
    "limitations": [
        "Four bounded runtime removal controls; expected pytest failures are counterfactual mechanism falsifiers, not product FAIL on unchanged source.",
        "No formal finding closure, scientific authority or G integration acceptance established.",
        "No ignored/local historical outputs silently carried as current evidence.",
    ],
}
(OUTPUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
print(json.dumps(summary, indent=2), flush=True)  # noqa: T201
