#!/usr/bin/env python3
"Run affected native boundary checks on immutable proposed module bytes."

import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
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


OUT = Path(__file__).parent
PRODUCT = Path("/workspace/e02-E-continuation-20261006/policy-engine")
PYTHON = PRODUCT / ".venv/bin/python"
BASE = "5e3e3727685132f270a3a07b9f63dd962a88cd96"


def main() -> None:
    env = os.environ.copy()
    removed = {
        name: env.pop(name)
        for name in [
            "OMP_NUM_THREADS",
            "OPENBLAS_NUM_THREADS",
            "MKL_NUM_THREADS",
            "NUMEXPR_NUM_THREADS",
            "POLISYOS_PYTEST_WORKERS",
            "XLA_FLAGS",
            "JAX_PLATFORMS",
        ]
        if name in env
    }
    env.update(
        {
            "PYTHONDONTWRITEBYTECODE": "1",
            "UV_NO_SYNC": "1",
            "E02_WELFARE_OVERLAY_METADATA": str(OUT / "native-overlay.json"),
            "PYTHONPATH": str(OUT / "hooks") + ":" + str(PRODUCT / "src") + ":" + str(PRODUCT),
        }
    )
    selectors = [
        str(OUT / "test_independent_api.py"),
        (
            "tests/unit/scientist/nodes/test_calibration_report_consumer."
            "py::test_actual_tied_calibrator_v2_reaches_fresh_legacy_node"
        ),
        (
            "tests/unit/scientist/nodes/test_calibration_report_consumer."
            "py::test_legacy_node_refuses_same_bytes_wrong_cas_profile_be"
            "fore_dispatch"
        ),
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
    fixture_refs = []
    for selector in selectors[1:]:
        relative = selector.split("::")[0]
        payload = (PRODUCT / relative).read_bytes()
        original = subprocess.check_output(  # noqa: S603 - admitted utility argv uses no shell; executable/source refs are explicit
            [
                _resolve_executable("git"),
                "-C",
                str(PRODUCT),
                "show",
                BASE + ":policy-engine/" + relative,
            ]
        )
        if not (original == payload):
            raise AssertionError
        fixture_refs.append(
            {
                "selector": selector,
                "source_sha": BASE,
                "bytes": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
        )
    argv = [
        str(PYTHON),
        "-m",
        "pytest",
        "-p",
        "origin_plugin",
        "-q",
        "-o",
        "cache_dir=" + str(OUT / "native-cache"),
        "--benchmark-storage=file://" + str(OUT / "native-benchmark"),
        "--basetemp",
        str(OUT / "native-basetemp"),
        "--junitxml",
        str(OUT / "native.xml"),
        *selectors,
    ]
    started = time.time()
    with (
        (OUT / "native.stdout").open("wb") as stdout,
        (OUT / "native.stderr").open("wb") as stderr,
    ):
        result = subprocess.run(argv, cwd=PRODUCT, env=env, stdout=stdout, stderr=stderr)  # noqa: S603 - admitted utility argv uses no shell; executable/source refs are explicit
    origins = json.loads((OUT / "independent-native-origins.json").read_text())
    if origins["mismatches"]:
        raise AssertionError(origins["mismatches"])
    manifest = OUT / "immutable-inputs/postimage-manifest.json"
    receipt = {
        "schema": "policyos.e02.independent-owned-facade-native.v1",
        "base_sha": BASE,
        "patch_sha256": json.loads(manifest.read_text())["patch_sha256"],
        "immutable_manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
        "argv": argv,
        "cwd": str(PRODUCT),
        "fixture_refs": fixture_refs,
        "framing_head": subprocess.check_output(  # noqa: S603 - source-bound fixture
            [_resolve_executable("git"), "-C", str(PRODUCT), "rev-parse", "HEAD"]
        )
        .decode()
        .strip(),
        "environment": {
            k: env.get(k)
            for k in [
                "PYTHONPATH",
                "PYTHONDONTWRITEBYTECODE",
                "UV_NO_SYNC",
                "E02_WELFARE_OVERLAY_METADATA",
                "OMP_NUM_THREADS",
                "OPENBLAS_NUM_THREADS",
                "MKL_NUM_THREADS",
                "NUMEXPR_NUM_THREADS",
                "POLISYOS_PYTEST_WORKERS",
                "XLA_FLAGS",
                "JAX_PLATFORMS",
            ]
        },
        "removed_artificial_caps": removed,
        "exit_code": result.returncode,
        "wall_seconds": time.time() - started,
        "actual_imported_product_module_count": origins["imported_product_module_count"],
        "actual_backend": origins["backend"],
        "source_mismatches": origins["mismatches"],
        "scope": (
            "Independent identity/optional-stack/proxy controls and affec"
            "ted actual strict legacy/Welfare caller, tied nullspace, fai"
            "led-support fresh-CAS boundaries. No full family/global wave"
            " or finding closure."
        ),
    }
    (OUT / "native-receipt.json").write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + "\n"
    )
    _write_stdout(
        json.dumps(
            {
                k: receipt[k]
                for k in [
                    "exit_code",
                    "wall_seconds",
                    "actual_imported_product_module_count",
                    "source_mismatches",
                ]
            },
            indent=2,
        )
    )
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
