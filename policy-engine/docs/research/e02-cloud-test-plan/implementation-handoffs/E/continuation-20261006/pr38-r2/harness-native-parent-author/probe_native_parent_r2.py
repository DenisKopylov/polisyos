(
    "Exact old/new harness execution with one"  # Exact bound literal continuation.
    " native fixture job, not a common wave."  # Exact bound literal continuation.
)

from __future__ import annotations

import asyncio
import json
import os
import runpy
import shutil
import subprocess
import sys
from pathlib import Path


def _resolve_executable(name: str) -> str:
    (
        "Resolve an admitted executable and refus"  # Exact bound literal continuation.
        "e an unavailable program before invocati"  # Exact bound literal continuation.
        "on."  # Exact bound literal continuation.
    )
    resolved = shutil.which(name)
    if resolved is None:
        raise RuntimeError(f"required utility executable unavailable: {name}")
    return str(Path(resolved).resolve())


def _write_stdout(*values: object, flush: bool = False) -> None:
    (
        "Emit the existing CLI text and optionall"  # Exact bound literal continuation.
        "y flush without logging side effects."  # Exact bound literal continuation.
    )
    sys.stdout.write(" ".join(str(value) for value in values) + "\n")
    if flush:
        sys.stdout.flush()


REPO = Path("/workspace/e02-E-continuation-20261006")
OUT = Path("/workspace/e02-E-pr38-r2-receipts/harness-native-parent-repair-5e3e37276")
BASE = "5e3e3727685132f270a3a07b9f63dd962a88cd96"
PREFIX = (
    "policy-engine/docs/research/e02-cloud-test-plan/implementati"
    "on-handoffs/E/continuation-20261006/pr38-r2/wave-controls/"
)
PY = REPO / "policy-engine/.venv/bin/python"
OLD = OUT / "old-exact"
for name in ("plan_wave.py", "run_check.py"):
    expected = subprocess.check_output(  # noqa: S603 - source-bound fixture
        [_resolve_executable("git"), "-C", str(REPO), "show", BASE + ":" + PREFIX + name]
    )
    if not ((OLD / name).read_bytes() == expected):
        raise AssertionError
old = runpy.run_path(str(OLD / "plan_wave.py"), run_name="exact_old_fixture_harness")
new = runpy.run_path(str(OUT / "plan_wave.py"), run_name="new_fixture_harness")
selected = new["runtime_environment"](REPO)
for name in new["CAP_VARIABLES"]:
    selected.pop(name, None)
os.environ.clear()
os.environ.update(selected)
results = []
for name, namespace in [
    ("old-exact", old),
    ("new-parent-admission", new),
    ("removed-parent-property", new),
]:
    output = OUT / "native-checks-r2" / name
    output.mkdir(parents=True, exist_ok=False)
    temp = output / "temporary/native-case"
    callback = output / "callback-count.json"
    os.environ["NATIVE_CALLBACK_RECEIPT"] = str(callback)
    os.environ["NATIVE_EXPECTED_BASETEMP"] = str(temp)
    importer = {
        "name": "native-fixture-preflight",
        "kind": "importer",
        "argv": [
            str(PY),
            "-c",
            'print("Native harness fixture preflight only; not results importer")',
        ],
        "cwd": str(REPO / "policy-engine"),
        "output": str(output / "checks/native-fixture-preflight"),
        "junit": None,
        "environment": {"TMPDIR": str(output / "tmp-env/preflight")},
    }
    native = {
        "name": "native-tmp-cas",
        "kind": "numerical",
        "argv": [
            str(PY),
            "-m",
            "pytest",
            "-q",
            "-s",
            "-c",
            str(REPO / "policy-engine/pytest.ini"),
            "-o",
            "cache_dir=" + str(output / "cache/pytest"),
            "--benchmark-storage=" + (output / "cache/benchmark").as_uri(),
            "--junitxml",
            str(output / "checks/native-tmp-cas/pytest.xml"),
            "--basetemp",
            str(temp),
            str(OUT / "test_native_tmp_cas_r2.py"),
        ],
        "cwd": str(REPO / "policy-engine"),
        "output": str(output / "checks/native-tmp-cas"),
        "junit": str(output / "checks/native-tmp-cas/pytest.xml"),
        "environment": {"TMPDIR": str(output / "tmp-env/native")},
    }
    plan = {
        "repo": str(REPO),
        "output_root": str(output),
        "tracked_dirty": "",
        "candidate_sha": BASE,
        "observed_head": BASE,
        "missing_required_paths": [],
        "required_upstream": {},
        "owner_packet_extra_inputs": [],
        "jobs": [importer, native],
        "interpreter": str(PY),
    }
    original = None
    if name == "removed-parent-property":
        original = namespace["execute"].__globals__["create_numeric_scratch_parents"]
        namespace["execute"].__globals__["create_numeric_scratch_parents"] = lambda *args: None
    try:
        code = asyncio.run(namespace["execute"](plan))
    finally:
        if original is not None:
            namespace["execute"].__globals__["create_numeric_scratch_parents"] = original
    receipt = json.loads((output / "checks/native-tmp-cas/native-tmp-cas.json").read_text())
    row = {
        "case": name,
        "scope": "bounded native harness fixture only, no full common wave/product family",
        "source_base": BASE,
        "harness_exit_code": code,
        "check_outcome": receipt["outcome"],
        "pytest_exit_code": receipt["exit_code"],
        "case_counts": receipt["counts"],
        "native_callback_count": json.loads(callback.read_text())["native_callback_count"]
        if callback.exists()
        else 0,
        "source_immutable": receipt["source_immutable"],
        "basetemp_parent_exists_after": temp.parent.exists(),
        "stdout": receipt["stdout_path"],
        "stdout_sha256": receipt["stdout_sha256"],
        "stdout_bytes": receipt["stdout_bytes"],
    }
    if name == "new-parent-admission":
        if not (
            code == 0 and receipt["counts"]["passed"] == 1 and row["native_callback_count"] == 1
        ):
            raise AssertionError
    else:
        if not (
            code != 0 and receipt["counts"]["errors"] == 1 and row["native_callback_count"] == 0
        ):
            raise AssertionError
    results.append(row)
(OUT / "native-parent-results-r2.json").write_text(
    json.dumps(
        {
            "scope": (
                "Actual pytest tmp_path and nativeCAS IO;"  # Exact bound literal continuation.
                " no calibration/backend wave repeated"  # Exact bound literal continuation.
            ),
            "results": results,
            "all_deciding_outputs_preserved": True,
        },
        indent=2,
    )
    + "\n"
)
_write_stdout(json.dumps({"results": results, "full_common_wave_run": False}))
