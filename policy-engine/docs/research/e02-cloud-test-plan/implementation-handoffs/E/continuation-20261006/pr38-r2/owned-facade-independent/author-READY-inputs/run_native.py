import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path


def _resolve_executable(name: str) -> str:
    "Resolve an admitted executable and refuse an unavailable program before invocation."
    resolved = shutil.which(name)
    if resolved is None:
        raise RuntimeError(f"required utility executable unavailable: {name}")
    return str(Path(resolved).resolve())


def _write_stdout(*values: object, flush: bool = False) -> None:
    "Emit the existing CLI text and optionally flush without logging side effects."
    sys.stdout.write(" ".join(str(value) for value in values) + "\n")
    if flush:
        sys.stdout.flush()


OUT = Path(__file__).parent
PRODUCT = Path("/workspace/e02-E-continuation-20261006/policy-engine")
PY = PRODUCT / ".venv/bin/python"
env = os.environ.copy()
removed = {
    k: env.pop(k)
    for k in (
        "OMP_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "MKL_NUM_THREADS",
        "NUMEXPR_NUM_THREADS",
        "POLISYOS_PYTEST_WORKERS",
        "XLA_FLAGS",
        "JAX_PLATFORMS",
    )
    if k in env
}
env.update(
    {
        "PYTHONDONTWRITEBYTECODE": "1",
        "UV_NO_SYNC": "1",
        "UV_PROJECT_ENVIRONMENT": str(PRODUCT / ".venv"),
        "E02_WELFARE_OVERLAY_METADATA": str(OUT / "overlay.json"),
        "PYTHONPATH": str(OUT / "hooks") + ":" + str(PRODUCT / "src") + ":" + str(PRODUCT),
    }
)
argv = [
    str(PY),
    "-m",
    "pytest",
    "-p",
    "origin_plugin",
    "-q",
    "-o",
    "cache_dir=" + str(OUT / "native-combined-cache"),
    "--benchmark-storage=file://" + str(OUT / "native-combined-benchmark"),
    "--basetemp",
    str(OUT / "native-combined-basetemp"),
    "--junitxml",
    str(OUT / "native-combined.xml"),
    str(OUT / ("postimage/policy-engine/tests/unit/foundry/uncertainty/test_covariance_facade.py")),
    str(OUT / "postimage/policy-engine/tests/unit/calibration/test_evidence_facades.py"),
    "tests/unit/scientist/nodes/test_calibration_report_consumer.py",
    (
        "tests/unit/scientist/nodes/builtins/simulate/test_welfare_em"
        "pirical_law.py::test_native_ge_preserves_empirical_atoms_fai"
        "led_support_and_conditional_values"
    ),
    (
        "tests/unit/scientist/nodes/builtins/simulate/test_propagate_"
        "welfare.py::test_calibrator_tied_report_reaches_delta_and_mo"
        "nte_carlo_welfare"
    ),
]
start = time.time()
with (
    (OUT / "native-combined.stdout").open("wb") as stdout,
    (OUT / "native-combined.stderr").open("wb") as stderr,
):
    run = subprocess.run(argv, cwd=PRODUCT, env=env, stdout=stdout, stderr=stderr)  # noqa: S603 - admitted utility argv uses no shell; executable/source refs are explicit
receipt = {
    "schema": "policyos.e02.author_native_proposed_facade.v1",
    "argv": argv,
    "cwd": str(PRODUCT),
    "base": "5e3e3727685132f270a3a07b9f63dd962a88cd96",
    "framing_HEAD": subprocess.check_output(  # noqa: S603 - admitted utility argv uses no shell; executable/source refs are explicit
        [_resolve_executable("git"), "-C", str(PRODUCT), "rev-parse", "HEAD"], text=True
    ).strip(),
    "source_manifest_sha256": hashlib.sha256(
        (OUT / "postimage-manifest.json").read_bytes()
    ).hexdigest(),
    "patch_sha256": hashlib.sha256((OUT / "owned-facade-route.patch").read_bytes()).hexdigest(),
    "actual_overlay_manifest": json.loads((OUT / "overlay.json").read_text()),
    "environment": {
        key: env.get(key)
        for key in (
            "PYTHONDONTWRITEBYTECODE",
            "UV_NO_SYNC",
            "UV_PROJECT_ENVIRONMENT",
            "E02_WELFARE_OVERLAY_METADATA",
            "PYTHONPATH",
            "OMP_NUM_THREADS",
            "OPENBLAS_NUM_THREADS",
            "MKL_NUM_THREADS",
            "NUMEXPR_NUM_THREADS",
            "POLISYOS_PYTEST_WORKERS",
            "XLA_FLAGS",
            "JAX_PLATFORMS",
        )
    },
    "removed_caps": removed,
    "exit_code": run.returncode,
    "wall_seconds": time.time() - start,
    "scope": (
        "Five facade API controls, four existing evidence facade cont"
        "rols, six actual legacy Node producer/readback/adversarial c"
        "ases, two actual Welfare covariance/GE cases. Generic native"
        " fixtures; no full family or global wave."
    ),
}
(OUT / "native-combined-receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
_write_stdout(
    json.dumps({"exit_code": run.returncode, "wall_seconds": receipt["wall_seconds"]}, indent=2)
)
raise SystemExit(run.returncode)
