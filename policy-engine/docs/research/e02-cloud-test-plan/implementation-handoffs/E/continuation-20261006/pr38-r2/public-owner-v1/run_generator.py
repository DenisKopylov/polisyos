"Canonical generator only; outputs redirected, no active checkout mutation."

import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path


def _write_stdout(*values: object, flush: bool = False) -> None:
    "Emit the existing CLI text and optionally flush without logging side effects."
    sys.stdout.write(" ".join(str(value) for value in values) + "\n")
    if flush:
        sys.stdout.flush()


observed_o = Path(__file__).parent
R = Path("/workspace/e02-E-continuation-20261006")
F = observed_o / "fixture-current" / "policy-engine"
PY = R / "policy-engine/.venv/bin/python"
phase = sys.argv[1]
D = observed_o / ("generated-" + phase)
D.mkdir(exist_ok=True)
args = [
    str(PY),
    "tools/devx/architecture/guardrails.py",
    "sync",
    "--skip-deep-import-baseline",
    "--public-json",
    str(D / "inventory.json"),
    "--public-md",
    str(D / "public-surface.md"),
    "--generated-md",
    str(D / "generated-artifacts.md"),
]
start = time.time()
env = dict(os.environ, UV_NO_SYNC="1")
p = subprocess.run(args, cwd=F, env=env, capture_output=True, text=True)  # noqa: S603 - admitted utility argv uses no shell; executable/source refs are explicit
(D / "sync.stdout").write_text(p.stdout + p.stderr)
sourcepaths = [
    "src/polisyos/calibration/__init__.py",
    "src/polisyos/calibration/forecast_bridge.py",
    "src/polisyos/scientist/methods/backtesting/forecast_owner.py",
    "src/polisyos/foundry/uncertainty/__init__.py",
    "tools/devx/architecture/guardrails.py",
    "architecture/public_surface/contract.toml",
]
result = {
    "phase": phase,
    "command": args,
    "cwd": str(F),
    "UV_NO_SYNC": "1",
    "exit_code": p.returncode,
    "wall_seconds": time.time() - start,
    "fixture_is_git_candidate": False,
    "no_full_global_guard": True,
    "input_paths": {
        s: {
            "sha256": hashlib.sha256((F / s).read_bytes()).hexdigest(),
            "bytes": (F / s).stat().st_size,
        }
        for s in sourcepaths
    },
}
(D / "execution.json").write_text(json.dumps(result, indent=2) + "\n")
_write_stdout(json.dumps(result, indent=2))
sys.exit(p.returncode)
