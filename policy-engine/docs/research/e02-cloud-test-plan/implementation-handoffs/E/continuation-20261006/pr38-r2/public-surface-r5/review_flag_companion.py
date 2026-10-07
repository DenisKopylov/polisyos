import hashlib
import json
import shutil
import subprocess
import sys
import tomllib
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


R = Path("/workspace/e02-E-continuation-20261006")
observed_o = Path(__file__).parent
CANONICAL = "7dc540d08d30bad8cf23744172c253c934dfc77e"
CANDIDATE = "7bc65f73d333bc4a526c55d8a959d2b7dea7e472"
PARENT = subprocess.check_output(  # noqa: S603 - source-bound fixture
    [_resolve_executable("git"), "rev-parse", CANDIDATE + "^"], cwd=R, text=True
).strip()
PATH = (
    "policy-engine/release-fragments/unreleas"  # Exact bound literal continuation.
    "ed/2026-10-06-e02-foundry-calibration-re"  # Exact bound literal continuation.
    "ader.toml"  # Exact bound literal continuation.
)
paths = subprocess.check_output(  # noqa: S603 - admitted utility argv uses no shell; executable/source refs are explicit
    [_resolve_executable("git"), "diff", "--name-only", PARENT, CANDIDATE], cwd=R, text=True
).splitlines()
if not (paths == [PATH]):
    raise AssertionError
a = subprocess.check_output([_resolve_executable("git"), "show", PARENT + ":" + PATH], cwd=R)  # noqa: S603 - admitted utility argv uses no shell; executable/source refs are explicit
b = subprocess.check_output([_resolve_executable("git"), "show", CANDIDATE + ":" + PATH], cwd=R)  # noqa: S603 - admitted utility argv uses no shell; executable/source refs are explicit
if not (
    a.replace(
        b"public_surface_inventory_reviewed = false", b"public_surface_inventory_reviewed = true"
    )
    == b
):
    raise AssertionError
if not ((R / PATH).read_bytes() == b):
    raise AssertionError
x = tomllib.loads(b.decode())
if not (
    x["public_surface_inventory_reviewed"] is True
    and x["surface_classification"] == "public_stable"
):
    raise AssertionError
if subprocess.check_output(  # noqa: S603 - admitted utility argv uses no shell; executable/source refs are explicit
    [
        _resolve_executable("git"),
        "diff",
        "--name-only",
        CANONICAL,
        CANDIDATE,
        "--",
        "policy-engine/src",
    ],
    cwd=R,
    text=True,
).strip():
    raise AssertionError
review = {
    "source_sha": "bf3b54c3a894d2d9d9bfb0cd13edb13177405f33",
    "canonical_companion": CANONICAL,
    "flag_parent": PARENT,
    "flag_companion": CANDIDATE,
    "flag_tree": "2c1b3fd02d751a6a8bd3053954ace7be4fce65ad",
    "footprint": [PATH],
    "exact_one_line_false_to_true": True,
    "classification": "public_stable",
    "source_and_canonical_metadata_unchanged": True,
    "path_sha256": hashlib.sha256(b).hexdigest(),
    "verdict": "GO-bounded-declaration-of-completed-independent-review",
    "harness_history": (
        "Initial whole7dc→7bc footprint assertion failed because pare"
        "ntc3 also committed r4 receipts. Corrected to exactflagcommi"
        "t parent→candidate. No product failure; full canonical→flag "
        "delta includes those separate docs receipts."
    ),
}
(observed_o / "reviewflag-companion.json").write_text(json.dumps(review, indent=2) + "\n")
_write_stdout(json.dumps(review, indent=2))
