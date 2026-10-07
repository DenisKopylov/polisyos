import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
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


root = Path("/workspace/e02-E-pr38-r2-receipts/independent-cal-reviewer/frc")
lane = Path("/workspace/e02-E-frc-20261006")
sha = "58e2d97965c0826c44843a78dcb2f8698d9950a3"
overlay = root / "legacy-git-blob-overlay-58e2"
overlay.mkdir(exist_ok=True)
paths = [
    "policy-engine/src",
    "policy-engine/architecture",
    "policy-engine/pyproject.toml",
    "policy-engine/uv.lock",
    (
        "policy-engine/tests/unit/scientist/metho"  # Exact bound literal continuation.
        "ds/backtesting/test_forecast_owner.py"  # Exact bound literal continuation.
    ),
]
blob = subprocess.check_output(  # noqa: S603 - source-bound fixture
    [_resolve_executable("git"), "-C", str(lane), "archive", sha, *paths]
)
with tarfile.open(fileobj=io.BytesIO(blob)) as tar:
    tar.extractall(overlay, filter="data")
probe = root / "legacy_probe.py"
probe.write_bytes(
    (
        lane
        / (
            "policy-engine/docs/research/e02-cloud-test-plan/implementati"
            "on-handoffs/E/frc-source-measurement-r2/legacy-replay-probe."
            "py.txt"
        )
    ).read_bytes()
)
cas = root / "legacy-native-cas-58e2"
oldenv = dict(os.environ, PYTHONPATH=str(overlay / "policy-engine/src"))
cmd = [
    sys.executable,
    str(probe),
    "--cas",
    str(cas),
    "--helper",
    str(
        overlay
        / (
            "policy-engine/tests/unit/scientist/metho"  # Exact bound literal continuation.
            "ds/backtesting/test_forecast_owner.py"  # Exact bound literal continuation.
        )
    ),
]
_write_stdout("Exact archived producer argv:", json.dumps(cmd), flush=True)
old = subprocess.run(cmd, cwd=overlay / "policy-engine", env=oldenv, capture_output=True, text=True)  # noqa: S603 - admitted utility argv uses no shell; executable/source refs are explicit
_write_stdout(old.stdout, old.stderr, flush=True)
if not (old.returncode == 0):
    raise AssertionError(old.returncode)
before = {
    str(p.relative_to(cas)): hashlib.sha256(p.read_bytes()).hexdigest()
    for p in sorted(cas.rglob("*"))
    if p.is_file()
}
new = subprocess.run(  # noqa: S603 - admitted utility argv uses no shell; executable/source refs are explicit
    [sys.executable, str(probe), "--cas", str(cas)],
    cwd=lane / "policy-engine",
    env=os.environ,
    capture_output=True,
    text=True,
)
_write_stdout(new.stdout, new.stderr, flush=True)
if not (new.returncode == 0):
    raise AssertionError(new.returncode)
oldresult = json.loads(old.stdout.strip().splitlines()[-1])
newresult = json.loads(new.stdout.strip().splitlines()[-1])
if not (oldresult["request_version"] == "1.0"):
    raise AssertionError
if not (oldresult["candidate_ref"] == newresult["candidate_ref"]):
    raise AssertionError
if not (
    newresult["authority_scope"] == "predictive_only"
    and newresult["verifier_provenance"] == "not_established"
):
    raise AssertionError
after = {
    str(p.relative_to(cas)): hashlib.sha256(p.read_bytes()).hexdigest()
    for p in sorted(cas.rglob("*"))
    if p.is_file()
}
if not (before == after):
    raise AssertionError
(root / "legacy-replay-details.json").write_text(
    json.dumps(
        {
            "producer_sha": sha,
            "reader_sha": "8486baad6fdef8063cfaad80b15f6b6d8532460a",
            "archived_paths": paths,
            "archive_sha256": hashlib.sha256(blob).hexdigest(),
            "producer": oldresult,
            "reader": newresult,
            "cas_file_count": len(before),
            "cas_bytes_unchanged": True,
            "cas_content_sha256": hashlib.sha256(
                json.dumps(before, sort_keys=True).encode()
            ).hexdigest(),
            "old_PYTHONPATH": oldenv["PYTHONPATH"],
            "new_PYTHONPATH": os.environ["PYTHONPATH"],
            "cleanup_candidates": [str(overlay), str(cas)],
            "no_production_inputs": True,
        },
        indent=2,
    )
)
