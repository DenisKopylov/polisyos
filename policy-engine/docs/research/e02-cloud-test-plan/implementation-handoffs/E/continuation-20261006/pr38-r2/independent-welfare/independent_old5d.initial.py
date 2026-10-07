(
    "Independent fresh native old-source fals"  # Exact bound literal continuation.
    "ifier, using Git blob overlay, no checko"  # Exact bound literal continuation.
    "ut."  # Exact bound literal continuation.
)

import hashlib
import io
import json
import os
import runpy
import shutil
import subprocess
import sys
import tarfile
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


ROOT = Path("/workspace/e02-E-pr38-r2-receipts/independent-cal-reviewer/welfare")
LANE = Path("/workspace/e02-E-backtest-20261006")
BASE = "5d4e01011a0b7e0a3954decdb622a9e9cf1fb787"
MODULE = (
    "policy-engine/src/polisyos/scientist/nod"  # Exact bound literal continuation.
    "es/builtins/simulate/propagate_welfare.p"  # Exact bound literal continuation.
    "y"  # Exact bound literal continuation.
)
OVERLAY = ROOT / "old5d-git-blob-overlay"
OVERLAY.mkdir(exist_ok=True)
archive = subprocess.check_output(  # noqa: S603 - admitted utility argv uses no shell; executable/source refs are explicit
    [
        _resolve_executable("git"),
        "-C",
        str(LANE),
        "archive",
        BASE,
        "policy-engine/src",
        "policy-engine/pyproject.toml",
        "policy-engine/uv.lock",
    ]
)
with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
    tar.extractall(OVERLAY, filter="data")
src = str(OVERLAY / "policy-engine/src")
sys.path[:] = [src] + [p for p in sys.path if "policy-engine/src" not in p]
os.environ["PYTHONPATH"] = src
files = {
    str(p.relative_to(OVERLAY)): hashlib.sha256(p.read_bytes()).hexdigest()
    for p in (OVERLAY / "policy-engine/src").rglob("*")
    if p.is_file()
}
source = (OVERLAY / MODULE).read_bytes()
if not (
    hashlib.sha256(source).hexdigest()
    == "f9421a672185153e7a55e1f0944f25a30e1a7950b3c978ac332fae12091625e8"
):
    raise AssertionError
from polisyos.scientist.nodes.builtins.simulate import (  # noqa: E402 - source-bound fixture
    propagate_welfare as module,
)

fixture = runpy.run_path(str(ROOT / "independent_welfare_tests.py"))
start = time.monotonic()
fresh, bundle, receipt, samples, ref = fixture["run"](ROOT / "independent-old5d-cas")
values = [r["sampled_input"]["A"] for r in receipt["sampled_inputs"]]
if not (len(values) == 128 and all(v not in (0.0, 1.0) for v in values)):
    raise AssertionError
if not (receipt["failed_draw_count"] == 0 and receipt["support_complete"] is True):
    raise AssertionError
if not (bundle.credible_interval is not None and bundle.robust_interval is not None):
    raise AssertionError
origins = {
    n: str(Path(m.__file__).resolve())
    for n, m in sys.modules.items()
    if n.startswith("polisyos") and getattr(m, "__file__", None)
}
if not (all(Path(p).is_relative_to(Path(src)) for p in origins.values())):
    raise AssertionError
if not (all(hashlib.sha256((OVERLAY / p).read_bytes()).hexdigest() == h for p, h in files.items())):
    raise AssertionError
result = {
    "status": "EXPECTED_PROPERTY_FAIL",
    "source_base": BASE,
    "source_tree": subprocess.check_output(  # noqa: S603 - admitted utility argv uses no shell; executable/source refs are explicit
        [_resolve_executable("git"), "-C", str(LANE), "rev-parse", BASE + "^{tree}"], text=True
    ).strip(),
    "archive_sha256": hashlib.sha256(archive).hexdigest(),
    "source_file_count": len(files),
    "source_digest": hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest(),
    "welfare_blob_sha256": hashlib.sha256(source).hexdigest(),
    "source_origin": str(Path(module.__file__).resolve()),
    "source_unchanged": True,
    "all_polisyos_origins_exact": True,
    "origin_count": len(origins),
    "python": sys.version,
    "executable": sys.executable,
    "PYTHONPATH": src,
    "oracle": {
        "atoms": [0, 1],
        "weights": [3, 1],
        "seed": 31415,
        "N": 128,
        "native_GE": "2/(1-A)",
        "correct_success": 92,
        "correct_failures": 36,
    },
    "observed": {
        "out_of_atom_count": sum(v not in (0, 1) for v in values),
        "failed": receipt["failed_draw_count"],
        "success": receipt["successful_draw_count"],
        "support_complete": receipt["support_complete"],
        "false_credible_interval": bundle.credible_interval,
        "false_robust_interval": bundle.robust_interval,
        "first_five_sampled_inputs": values[:5],
        "sampled_input_list_sha256": hashlib.sha256(json.dumps(values).encode()).hexdigest(),
    },
    "artifacts": fixture["RESULTS"],
    "elapsed_seconds": time.monotonic() - start,
}
(ROOT / "independent-old5d-result.json").write_text(json.dumps(result, indent=2))
_write_stdout(json.dumps(result, indent=2))
