"""Capture immutable review execution metadata around a native child."""

import hashlib
import importlib.metadata
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path


def _write_stdout(*values: object, flush: bool = False) -> None:
    "Emit the existing CLI text and optionally flush without logging side effects."
    sys.stdout.write(" ".join(str(value) for value in values) + "\n")
    if flush:
        sys.stdout.flush()


out = Path(__file__).resolve().parent
name, cwd, pythonpath = sys.argv[1:4]
argv = sys.argv[4:]
env = dict(os.environ, UV_NO_SYNC="1", PYTHONPATH=pythonpath)
started = time.time()
with (out / (name + ".stdout")).open("wb") as stream:
    process = subprocess.run(argv, cwd=cwd, env=env, stdout=stream, stderr=subprocess.STDOUT)  # noqa: S603 - admitted utility argv uses no shell; executable/source refs are explicit
stdout = (out / (name + ".stdout")).read_bytes()
receipt = {
    "command": argv,
    "cwd": cwd,
    "pythonpath": pythonpath,
    "environment": {
        "UV_NO_SYNC": "1",
        "caps": {
            key: env.get(key)
            for key in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "XLA_FLAGS")
        },
        "python": sys.version,
        "executable": sys.executable,
        "platform": platform.platform(),
        "packages": {
            name: importlib.metadata.version(name)
            for name in ("numpy", "scipy", "jax", "jaxlib", "pydantic", "jsonschema", "pytest")
        },
    },
    "exit_code": process.returncode,
    "wall_s": time.time() - started,
    "stdout_ref": {
        "path": str(out / (name + ".stdout")),
        "bytes": len(stdout),
        "sha256": hashlib.sha256(stdout).hexdigest(),
    },
}
(out / (name + ".json")).write_text(json.dumps(receipt, indent=2) + "\n")
_write_stdout(
    json.dumps(
        {
            "name": name,
            "exit_code": process.returncode,
            "wall_s": receipt["wall_s"],
            "output": receipt["stdout_ref"],
        }
    )
)
sys.exit(process.returncode)
