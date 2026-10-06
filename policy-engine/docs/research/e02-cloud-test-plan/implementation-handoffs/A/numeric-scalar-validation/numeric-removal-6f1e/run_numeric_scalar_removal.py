"""Run the three real mixed-Boolean consumers with the property-removal plugin.

This runner intentionally does not execute itself. Root/reviewer supplies an
immutable worktree containing the expected production and test blobs plus a
fresh, unique output directory.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path

EXPECTED_SOURCE_BLOB = "7965deabd278db8a4e9e73092ad3fc7bfaf59545"
EXPECTED_TEST_BLOB = "f10006ebaa677d876ad7477ce09fbda36b837cf5"
EXPECTED_PLUGIN_SHA256 = "7c4df93a168d2b523da15c9059c9c3a886a68abd97cfd179293df2a53db4fd1d"
NODES = (
    "tests/unit/runtime/quality/test_joint_simulation_e02_semantics.py::"
    "test_shared_required_output_projection_rejects_invalid_original_elements[mixed-python-bool-float]",
    "tests/unit/runtime/quality/test_joint_simulation_e02_semantics.py::"
    "test_coupled_output_adapter_rejects_mixed_boolean_sequence",
    "tests/unit/runtime/quality/test_joint_simulation_e02_semantics.py::"
    "test_replication_cache_aggregator_rejects_mixed_boolean_sequence",
)

if len(sys.argv) != 3:
    raise SystemExit("usage: run_numeric_scalar_removal.py <worker-worktree> <fresh-output-dir>")

worker = Path(sys.argv[1])
output = Path(sys.argv[2])
product = worker / "policy-engine"
plugin_dir = Path(__file__).resolve().parent
plugin_path = plugin_dir / "remove_original_element_guard.py"
runner_path = Path(__file__).resolve()
output.mkdir(parents=True, exist_ok=False)


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=worker, text=True).strip()  # noqa: S603, S607


candidate = git("rev-parse", "HEAD")
tree = git("rev-parse", "HEAD^{tree}")
branch = git("symbolic-ref", "-q", "--short", "HEAD")
status_before = git("status", "-sb")
source_path = "src/polisyos/runtime/quality/joint_simulation_horizon.py"
test_path = "tests/unit/runtime/quality/test_joint_simulation_e02_semantics.py"
source_blob = git("rev-parse", f"HEAD:policy-engine/{source_path}")
test_blob = git("rev-parse", f"HEAD:policy-engine/{test_path}")
if source_blob != EXPECTED_SOURCE_BLOB:
    raise SystemExit(f"source blob mismatch: expected {EXPECTED_SOURCE_BLOB}, got {source_blob}")
if test_blob != EXPECTED_TEST_BLOB:
    raise SystemExit(f"test blob mismatch: expected {EXPECTED_TEST_BLOB}, got {test_blob}")

plugin_sha = hashlib.sha256(plugin_path.read_bytes()).hexdigest()
if plugin_sha != EXPECTED_PLUGIN_SHA256:
    raise SystemExit(f"plugin hash mismatch: expected {EXPECTED_PLUGIN_SHA256}, got {plugin_sha}")
inputs = {}
for relative, expected_blob in (
    (source_path, EXPECTED_SOURCE_BLOB),
    (test_path, EXPECTED_TEST_BLOB),
):
    path = product / relative
    blob = git("hash-object", str(path))
    committed_blob = git("rev-parse", f"HEAD:policy-engine/{relative}")
    if blob != expected_blob or blob != committed_blob:
        raise SystemExit(f"input blob mismatch for {relative}")
    inputs[relative] = {"git_blob": blob, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
inputs[str(plugin_path)] = {"sha256": plugin_sha, "git_blob": None, "ignored_scratch": True}
runner_sha = hashlib.sha256(runner_path.read_bytes()).hexdigest()
inputs[str(runner_path)] = {"sha256": runner_sha, "git_blob": None, "ignored_scratch": True}

command = [
    sys.executable,
    "-u",
    "-m",
    "pytest",
    "-c",
    "pytest.ini",
    "-vv",
    "--durations=0",
    f"--basetemp={output / 'basetemp'}",
    f"--junitxml={output / 'junit.xml'}",
    "-p",
    "remove_original_element_guard",
    *NODES,
]
env = dict(os.environ)
env.update(
    {
        "PYTHONPATH": os.pathsep.join((str(plugin_dir), str(product / "src"), str(product))),
        "JAX_PLATFORMS": "cpu",
    }
)
for key in (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
):
    env[key] = "1"
record = {
    "schema": "policyos.e02.numeric_scalar_removal_run.v1",
    "purpose": "remove shared original-element guard while retaining consumer/test markers",
    "candidate_sha": candidate,
    "candidate_tree_sha": tree,
    "candidate_branch": branch,
    "status_before": status_before,
    "command_argv": command,
    "cwd": str(product),
    "selected_test_nodes": list(NODES),
    "expected_semantic_decision": {
        "mixed_python_bool_test": "must fail with its DID NOT RAISE assertion",
        "coupled_adapter_test": "must fail with its DID NOT RAISE assertion",
        "replication_cache_test": "must fail with its DID NOT RAISE assertion",
        "pytest_errors_or_collection_failures": "harness error, never property-removal evidence",
        "pytest_exit_code_zero": "property-removal NO-GO because the runtime accepted the mutant",
    },
    "plugin": {
        "module": "remove_original_element_guard",
        "directory_on_pythonpath": str(plugin_dir),
        "path": str(plugin_path),
        "sha256": plugin_sha,
        "runner_path": str(runner_path),
        "runner_sha256": runner_sha,
        "mutation": "_contains_invalid_original_numeric_element returns False",
        "receipt_signal": "PROPERTY_REMOVAL_RECEIPT=... in stdout.txt",
        "no_hit_signal": "PROPERTY_REMOVAL_HARNESS_ERROR in stdout.txt and exit status 2",
    },
    "input_paths": inputs,
    "interpreter_literal": sys.executable,
    "interpreter_prefix": sys.prefix,
    "interpreter_target_identity_only": str(Path(sys.executable).resolve()),
    "python": sys.version,
    "platform": platform.platform(),
    "packages": {
        name: importlib.metadata.version(name)
        for name in ("pytest", "numpy", "scipy", "jax", "jaxlib", "pydantic")
    },
    "environment": {
        key: env[key]
        for key in (
            "PYTHONPATH",
            "JAX_PLATFORMS",
            "OMP_NUM_THREADS",
            "OPENBLAS_NUM_THREADS",
            "MKL_NUM_THREADS",
            "NUMEXPR_NUM_THREADS",
            "VECLIB_MAXIMUM_THREADS",
        )
    },
    "timeout_seconds": 120,
    "timeout_basis": (
        "The 11-case pre-fix RED completed in 12.89s; this selects three nodes "
        "and preserves ample import/startup headroom."
    ),
}
started = time.monotonic()
with (output / "stdout.txt").open("w") as stdout, (output / "stderr.txt").open("w") as stderr:
    try:
        result = subprocess.run(  # noqa: S603
            command,
            cwd=product,
            env=env,
            stdout=stdout,
            stderr=stderr,
            timeout=120,
            check=False,
        )
        record["exit_code"] = result.returncode
    except subprocess.TimeoutExpired:
        record["exit_code"] = None
        record["runner_error"] = "timeout"
record["wall_seconds"] = time.monotonic() - started
record["status_after"] = git("status", "-sb")
(output / "environment-and-inputs.json").write_text(json.dumps(record, indent=2) + "\n")
sys.stdout.write(
    json.dumps(
        {
            "candidate": candidate,
            "exit": record["exit_code"],
            "wall_seconds": record["wall_seconds"],
            "output": str(output),
        }
    )
    + "\n"
)
raise SystemExit(record["exit_code"] if record["exit_code"] is not None else 2)
