"Independent v3 actual reader/custody controls, zero native/gate stages."

import json
import os
import runpy
import shutil
import subprocess
import sys
from argparse import Namespace
from collections import Counter
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


ROOT = Path("/workspace/e02-E-continuation-20261006")
OUT = Path(__file__).parent
SOURCE = Path(
    "/workspace/e02-E-pr38-r2-receipts/common-wave-publication-prep/collect_wave_v3_final.py"
)
AUTHOR = Path("/workspace/e02-E-pr38-r2-receipts/collector-v3-final-author-controls")
WAVE = Path("/workspace/e02-E-pr38-r2-receipts/common-wave-5e3e37276")
FROZEN = "5e3e3727685132f270a3a07b9f63dd962a88cd96"
FREEZE = Path("/workspace/e02-E-pr38-r2-receipts/source-freeze-5e3e37276.json")
MODULE = runpy.run_path(str(SOURCE), run_name="independent_actual_v3_reader_only")
identity = MODULE["identity"]
if not (
    identity(SOURCE)
    == {
        "bytes": 38152,
        "sha256": "a6399cc46cbfe25b103fa210259eff2be9483f582ae7cba773632f079f7194ec",
    }
):
    raise AssertionError


def check_index(path: object, absolute: bool = False) -> dict[str, object]:
    index = json.loads(path.read_text())
    files = index["files"]
    if not (len(files) == index["file_count"]):
        raise AssertionError
    if not (sum(row["bytes"] for row in files) == index["total_bytes"]):
        raise AssertionError
    for row in files:
        file = Path(row["path"]) if absolute else path.parent / row["path"]
        if not (identity(file) == {"bytes": row["bytes"], "sha256": row["sha256"]}):
            raise AssertionError
    return {
        "path": str(path),
        "identity": identity(path),
        "files": len(files),
        "bytes": index["total_bytes"],
    }


author_index = check_index(AUTHOR / "copy-index.json", absolute=True)
author_publication = Path(
    "/workspace/e02-E-pr38-r2-receipts/common-wave-publication-prep/actual-failed-5e3e37276-v3"
)
author_nested = check_index(author_publication / "copy-index.json")
root_before = subprocess.check_output(  # noqa: S603 - admitted utility argv uses no shell; executable/source refs are explicit
    [_resolve_executable("git"), "rev-parse", "HEAD", "HEAD^{tree}"], cwd=ROOT, text=True
).splitlines()
plan = json.loads((WAVE / "plan.json").read_text())
observed = MODULE["collect"](
    Namespace(
        repo=ROOT,
        candidate=FROZEN,
        wave_root=WAVE,
        publication_root=OUT / "actual-reader-publication",
        freeze_receipt=FREEZE,
        max_moderate_bytes=8 * 1024 * 1024,
        capture_incomplete=False,
    )
)
if not (observed["collection_state"] == "COMPLETE_BOUND" and not observed["issues"]):
    raise AssertionError
if not (
    observed["numeric_counts"]
    == {"cases": 1440, "passed": 1086, "failed": 3, "errors": 351, "skipped": 0}
):
    raise AssertionError
if not (
    observed["native_numeric_counts_excluding_A_packets"]
    == {"cases": 1433, "passed": 1086, "failed": 2, "errors": 345, "skipped": 0}
):
    raise AssertionError
if not (
    [p["counts"] for p in observed["foreign_owner_A_packet_cases"]]
    == [
        {"cases": 5, "passed": 0, "failed": 0, "errors": 5, "skipped": 0},
        {"cases": 2, "passed": 0, "failed": 1, "errors": 1, "skipped": 0},
    ]
):
    raise AssertionError
if not (observed["unattributed_owner_packet_counts"]["cases"] == 0):
    raise AssertionError
if observed["native_numeric_attribution_complete"] is not True:
    raise AssertionError
if not (observed["doctor_is_full_ci"] is False and observed["finding_closure"] is False):
    raise AssertionError
if not (observed["static_proxy"]["P41"].startswith("not_established")):
    raise AssertionError
publication = OUT / "actual-reader-publication"
own_index = check_index(publication / "copy-index.json")
index = json.loads((publication / "copy-index.json").read_text())
if not (len(index["wave_source_assets"]) == 45):
    raise AssertionError
for row in index["wave_source_assets"]:
    original = FREEZE if row["path"] == "source-freeze-receipt.json" else WAVE / row["path"]
    expected = {"bytes": row["bytes"], "sha256": row["sha256"]}
    if not (identity(original) == identity(publication / row["path"]) == expected):
        raise AssertionError
    if not (identity(author_publication / row["path"]) == expected):
        raise AssertionError
if not (len(observed["excluded_raw_custody"]) == 16):
    raise AssertionError
for row in observed["excluded_raw_custody"]:
    if not (identity(WAVE / row["path"]) == {"bytes": row["bytes"], "sha256": row["sha256"]}):
        raise AssertionError
    if (publication / row["path"]).exists():
        raise AssertionError
if any("raw" in Path(r["path"]).parts or "git-config-private" in r["path"] for r in index["files"]):
    raise AssertionError
raw = next(
    r
    for r in observed["excluded_raw_custody"]
    if r["path"].endswith("production-invocation.raw.json")
)
if not (
    raw["bytes"] == 171772803
    and raw["sha256"] == "404cdb1543a96433016ca3880c3d557e2d027f9fa62060be40d9b8e266b16fbd"
):
    raise AssertionError
stage_counts = {}
for row in observed["jobs"]:
    if row["name"] in {"workspace-verify", "ci-parity"}:
        c = dict(
            Counter(
                s["outcome"] for scope in row["umbrella_stages"]["scopes"] for s in scope["steps"]
            )
        )
        if not (c == row["umbrella_stage_outcomes"]):
            raise AssertionError
        stage_counts[row["name"]] = c
if not (
    stage_counts
    == {
        "workspace-verify": {"PASS": 1, "FAIL": 1, "UNRUN": 13},
        "ci-parity": {"FAIL": 1, "UNRUN": 23},
    }
):
    raise AssertionError
controls = []
first = index["files"][0]
for field, wrong in [("bytes", -1), ("sha256", "0" * 64)]:
    forged = dict(first)
    forged[field] = wrong
    if not (
        identity(publication / forged["path"])
        != {"bytes": forged["bytes"], "sha256": forged["sha256"]}
    ):
        raise AssertionError
    controls.append(field + " REFUSED")
forged_counts = dict(observed["native_numeric_counts_excluding_A_packets"], cases=1440)
if not (forged_counts != {"cases": 1433, "passed": 1086, "failed": 2, "errors": 345, "skipped": 0}):
    raise AssertionError
controls.append("native/A denominator forgery REFUSED")
caps = {name: os.environ.get(name) for name in MODULE["CAPS"]}
if not (all(value is None for value in caps.values())):
    raise AssertionError
if not (
    identity(SOURCE)
    == {
        "bytes": 38152,
        "sha256": "a6399cc46cbfe25b103fa210259eff2be9483f582ae7cba773632f079f7194ec",
    }
):
    raise AssertionError
if not (check_index(AUTHOR / "copy-index.json", absolute=True) == author_index):
    raise AssertionError
root_after = subprocess.check_output(  # noqa: S603 - admitted utility argv uses no shell; executable/source refs are explicit
    [_resolve_executable("git"), "rev-parse", "HEAD", "HEAD^{tree}"], cwd=ROOT, text=True
).splitlines()
result = {
    "source_path": str(SOURCE),
    "source_identity": identity(SOURCE),
    "author_index_verified": author_index,
    "author_actual_nested_index_verified": author_nested,
    "independent_actual_index_verified": own_index,
    "root_metadata_before": root_before,
    "root_metadata_after": root_after,
    "original_actual_wave_candidate": FROZEN,
    "counts": observed["numeric_counts"],
    "native_counts": observed["native_numeric_counts_excluding_A_packets"],
    "A_counts": [p["counts"] for p in observed["foreign_owner_A_packet_cases"]],
    "unattributed": observed["unattributed_owner_packet_counts"],
    "scope": (
        "Reader-only collection of same completed historical5e bytes,"
        " no command replay or new numeric evidence"
    ),
    "moderate_original_source_assets": 45,
    "raw_and_private_hash_only_records": 16,
    "large_raw_bytes_not_copied": 171772803,
    "stage_outcomes": stage_counts,
    "independent_corrupt_controls": controls,
    "product_native_or_gate_commands_executed": 0,
    "cpu_caps": caps,
    "verdict": "GO-bounded-actual-reader-custody-and-preserved-attribution",
    "finding_closure": False,
}
(OUT / "reader-custody.json").write_text(json.dumps(result, indent=2) + "\n")
_write_stdout(json.dumps(result, indent=2))
