"Read-only author provenance recorded by the actual targeted pytest process."

from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path


def _resolve_executable(name: str) -> str:
    "Resolve an admitted executable and refuse an unavailable program before invocation."
    resolved = shutil.which(name)
    if resolved is None:
        raise RuntimeError(f"required utility executable unavailable: {name}")
    return str(Path(resolved).resolve())


ROOT = Path("/workspace/e02-E-continuation-20261006")
BASE = "5e3e3727685132f270a3a07b9f63dd962a88cd96"
OUT = Path(__file__).parent.parent
POST = OUT / "postimage"
FROZEN = {
    row["path"]: row["after_sha256"]
    for row in json.loads((OUT / "postimage-manifest.json").read_text())["paths"]
}


def pytest_sessionfinish(session: object, exitstatus: int) -> None:
    origins = []
    mismatches = []
    for name, module in sorted(sys.modules.items()):
        if not name.startswith("polisyos.") or not getattr(module, "__file__", None):
            continue
        path = Path(module.__file__).resolve()
        if path.suffix != ".py":
            continue
        if path.is_relative_to(POST):
            relative = str(path.relative_to(POST))
            expected = path.read_bytes()
            if hashlib.sha256(expected).hexdigest() != FROZEN[relative]:
                mismatches.append(
                    {
                        "module": name,
                        "origin": str(path),
                        "reason": "frozen postimage SHA256 changed",
                    }
                )
            role = "frozen proposed source overlay"
        elif path.is_relative_to(ROOT):
            relative = str(path.relative_to(ROOT))
            expected = subprocess.check_output(  # noqa: S603 - admitted utility argv uses no shell; executable/source refs are explicit
                [_resolve_executable("git"), "-C", str(ROOT), "show", BASE + ":" + relative]
            )
            role = "exact base5e Git bytes"
        else:
            mismatches.append(
                {"module": name, "origin": str(path), "reason": "foreign product source origin"}
            )
            continue
        if path.read_bytes() != expected:
            mismatches.append({"module": name, "origin": str(path), "reason": "source changed"})
        origins.append(
            {
                "module": name,
                "origin": str(path),
                "path": relative,
                "role": role,
                "sha256": hashlib.sha256(expected).hexdigest(),
                "bytes": len(expected),
            }
        )
    backend = {}
    if "jax" in sys.modules:
        jax = sys.modules["jax"]
        backend = {
            "jax_version": jax.__version__,
            "devices": [str(device) for device in jax.devices()],
            "platforms": sorted({device.platform for device in jax.devices()}),
            "jax_enable_x64": bool(jax.config.jax_enable_x64),
        }
    result = {
        "schema": "policyos.e02.loaded_native_overlay_origins.v1",
        "base": BASE,
        "pytest_exit": int(exitstatus),
        "python": sys.version,
        "executable": sys.executable,
        "platform": platform.platform(),
        "argv": sys.argv,
        "cwd": os.getcwd(),
        "environment": {
            name: os.environ.get(name)
            for name in (
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
            )
        },
        "backend": backend,
        "imported_product_module_count": len(origins),
        "module_origins": origins,
        "mismatches": mismatches,
    }
    (OUT / "native-origins-combined.json").write_text(json.dumps(result, indent=2) + "\n")
    if mismatches:
        session.exitstatus = 1
