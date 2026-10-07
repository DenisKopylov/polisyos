"Read-only independent Git/original-wave custody + actual A-attribution review."

import ast
import hashlib
import json
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path

from defusedxml import ElementTree as LegacyElementTree


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
BASE = ROOT / (
    "policy-engine/docs/research/e02-cloud-test-plan/implementati"
    "on-handoffs/E/continuation-20261006/pr38-r2"
)
OUT = Path(__file__).parent
REF = "1e1b5028274814b7c4318671588202480390a6bc"
WAVE = Path("/workspace/e02-E-pr38-r2-receipts/common-wave-5e3e37276")
FROZEN = "5e3e3727685132f270a3a07b9f63dd962a88cd96"


def identity(p: object) -> object:
    before = p.stat()
    sha = hashlib.sha256()
    with p.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            sha.update(block)
    after = p.stat()
    if not ((before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns)):
        raise AssertionError
    return {"bytes": after.st_size, "sha256": sha.hexdigest()}


def git(path: object, ref: object = REF) -> object:
    return subprocess.check_output(  # noqa: S603 - admitted utility argv uses no shell; executable/source refs are explicit
        [_resolve_executable("git"), "show", ref + ":" + str(path)], cwd=ROOT
    )


def check_record(row: object) -> object:
    path = ROOT / row["copied_path"]
    if not (path.read_bytes() == git(row["copied_path"])):
        raise AssertionError
    declared = {"bytes": row["bytes"], "sha256": row["sha256"]}
    if not (identity(path) == declared):
        raise AssertionError
    original = Path(row["source_path"])
    if not (identity(original) == declared):
        raise AssertionError
    return dict(path=row["copied_path"], source_path=row["source_path"], **declared)


portable = []
for folder in ["failed-wave-5e-collector", "failed-wave-5e", "failed-wave-5e-independent"]:
    idx = BASE / folder / "portable-copy-index.json"
    if not (idx.read_bytes() == git(idx.relative_to(ROOT))):
        raise AssertionError
    data = json.loads(idx.read_text())
    checked = [check_record(row) for row in data["records"]]
    if not (
        len(checked) == data["file_count"] and sum(row["bytes"] for row in checked) == data["bytes"]
    ):
        raise AssertionError
    if not (data["raw_private_config_included"] is False and data["large_raw_included"] is False):
        raise AssertionError
    portable.append(
        {
            "folder": folder,
            "index_identity": identity(idx),
            "files": len(checked),
            "bytes": sum(x["bytes"] for x in checked),
            "records": checked,
        }
    )
if not (sum(x["files"] for x in portable) == 79):
    raise AssertionError
# Parent's127 checks include48 nested asset checks below; they are not127 unique copies.
P = BASE / "failed-wave-5e"
receipt = json.loads((P / "publication-receipt.json").read_text())
index = json.loads((P / "copy-index.json").read_text())
plan = json.loads((WAVE / "plan.json").read_text())
if not (receipt["candidate_sha"] == plan["candidate_sha"] == FROZEN):
    raise AssertionError
if not (
    receipt["candidate_tree_sha"]
    == subprocess.check_output(  # noqa: S603 - admitted utility argv uses no shell; executable/source refs are explicit
        [_resolve_executable("git"), "rev-parse", FROZEN + "^{tree}"], cwd=ROOT, text=True
    ).strip()
):
    raise AssertionError
if not (index["file_count"] == 48 and len(index["files"]) == 48):
    raise AssertionError
if not (sum(x["files"] for x in portable) + len(index["files"]) == 127):
    raise AssertionError
for row in index["files"]:
    p = P / row["path"]
    if not (identity(p) == {"bytes": row["bytes"], "sha256": row["sha256"]}):
        raise AssertionError
if not (sum(x["bytes"] for x in index["files"]) == index["total_bytes"] == 6368501):
    raise AssertionError
source_assets = []
for row in index["wave_source_assets"]:
    original = (
        Path("/workspace/e02-E-pr38-r2-receipts/source-freeze-5e3e37276.json")
        if row["path"] == "source-freeze-receipt.json"
        else WAVE / row["path"]
    )
    if not (identity(original) == {"bytes": row["bytes"], "sha256": row["sha256"]}):
        raise AssertionError
    if not (identity(P / row["path"]) == identity(original)):
        raise AssertionError
    source_assets.append(dict(original=str(original), **row))
if not (len(source_assets) == 45):
    raise AssertionError
raw_records = receipt["excluded_raw_custody"]
if not (len(raw_records) == 16):
    raise AssertionError
for row in raw_records:
    if not (identity(WAVE / row["path"]) == {"bytes": row["bytes"], "sha256": row["sha256"]}):
        raise AssertionError
    if (P / row["path"]).exists():
        raise AssertionError
    if not (row["path"] not in [x["path"] for x in index["files"]]):
        raise AssertionError
raw = next(row for row in raw_records if row["path"].endswith("production-invocation.raw.json"))
if not (
    raw["bytes"] == 171772803
    and raw["sha256"] == "404cdb1543a96433016ca3880c3d557e2d027f9fa62060be40d9b8e266b16fbd"
):
    raise AssertionError
if any(
    "git-config-private.nul" in x["path"] or "production-invocation.raw.json" in x["path"]
    for x in index["files"]
):
    raise AssertionError
# Independent actual JUnit attribution uses exact source/name/job uniqueness;
# actual seven packet cases have anonymous module/file labels.
origins = {}
sources = {p for rows in plan["groups"].values() for p in rows}
sources.update(x["source"] for x in plan["owner_packet_extra_inputs"])
if not (len(sources) == 123):
    raise AssertionError
for source in sorted(sources):
    data = git(source, FROZEN)
    for node in ast.walk(ast.parse(data)):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith(
            "test_"
        ):
            origins.setdefault(node.name, []).append(source)
packets = {}
for p in plan["owner_packet_extra_inputs"]:
    b = git(p["source"], FROZEN)
    if not (hashlib.sha256(b).hexdigest() == p["sha256"]):
        raise AssertionError
    if not (identity(Path(p["destination"])) == {"bytes": p["bytes"], "sha256": p["sha256"]}):
        raise AssertionError
    names = {
        n.name
        for n in ast.walk(ast.parse(b))
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name.startswith("test_")
    }
    packets[p["source"]] = {
        "names": names,
        "jobs": {j["name"] for j in plan["jobs"] if p["destination"] in j["argv"]},
    }
all_cases = []
A_cases = []
native = []
job_counts = []
for j in plan["jobs"]:
    if j["kind"] != "numerical":
        continue
    rows = []
    for case in LegacyElementTree.parse(j["junit"], forbid_dtd=True).getroot().iter("testcase"):
        outcomes = [name for name in ["failure", "error", "skipped"] if case.find(name) is not None]
        if not (len(outcomes) <= 1):
            raise AssertionError
        status = {"failure": "failed", "error": "errors", "skipped": "skipped"}.get(
            outcomes[0] if outcomes else "", "passed"
        )
        name = (case.get("name") or "").split("[", 1)[0]
        owners = [
            source
            for source, p in packets.items()
            if name in p["names"] and j["name"] in p["jobs"] and origins[name] == [source]
        ]
        row = {
            "name": case.get("name"),
            "classname": case.get("classname"),
            "file": case.get("file"),
            "job": j["name"],
            "outcome": status,
            "packet": owners,
        }
        if not (len(owners) <= 1):
            raise AssertionError
        if owners:
            if not (not row["classname"] and row["file"] is None):
                raise AssertionError
            A_cases.append(row)
        else:
            native.append(row)
        rows.append(row)
        all_cases.append(row)
    c = Counter(x["outcome"] for x in rows)
    actual = dict(cases=len(rows), **{k: c[k] for k in ["passed", "failed", "errors", "skipped"]})
    if not (actual == next(r["case_counts"] for r in receipt["jobs"] if r["name"] == j["name"])):
        raise AssertionError
    job_counts.append({"job": j["name"], "counts": actual})


def counts(rows: object) -> object:
    c = Counter(x["outcome"] for x in rows)
    return dict(cases=len(rows), **{k: c[k] for k in ["passed", "failed", "errors", "skipped"]})


if not (
    counts(all_cases)
    == receipt["numeric_counts"]
    == {"cases": 1440, "passed": 1086, "failed": 3, "errors": 351, "skipped": 0}
):
    raise AssertionError
if not (
    counts(native)
    == receipt["native_numeric_counts_excluding_A_packets"]
    == {"cases": 1433, "passed": 1086, "failed": 2, "errors": 345, "skipped": 0}
):
    raise AssertionError
if not (counts(A_cases) == {"cases": 7, "passed": 0, "failed": 1, "errors": 6, "skipped": 0}):
    raise AssertionError
for p in receipt["foreign_owner_A_packet_cases"]:
    if not (p["counts"] == counts([x for x in A_cases if x["packet"] == [p["source"]]])):
        raise AssertionError
# Hash/content corruption is independently rejected by custody equality.
controls = []
for field, value in [("bytes", -1), ("sha256", "0" * 64)]:
    row = dict(index["files"][0])
    row[field] = value
    if not (identity(P / row["path"]) != {"bytes": row["bytes"], "sha256": row["sha256"]}):
        raise AssertionError
    controls.append(field + " REFUSED")
changed = receipt["native_numeric_counts_excluding_A_packets"].copy()
changed["cases"] = 1440
if not (changed != counts(native)):
    raise AssertionError
controls.append("native1433/A7 denominator forgery REFUSED")
# Verify source framework/observer labels and UNRUN stage counts without native commands.
if not (receipt["doctor_is_full_ci"] is False and receipt["finding_closure"] is False):
    raise AssertionError
stage_counts = {}
for row in receipt["jobs"]:
    if row["name"] in ["workspace-verify", "ci-parity"]:
        steps = [s for scope in row["umbrella_stages"]["scopes"] for s in scope["steps"]]
        observed = dict(Counter(s["outcome"] for s in steps))
        if not (observed == row["umbrella_stage_outcomes"]):
            raise AssertionError
        stage_counts[row["name"]] = observed
if not (
    stage_counts
    == {
        "workspace-verify": {"PASS": 1, "FAIL": 1, "UNRUN": 13},
        "ci-parity": {"FAIL": 1, "UNRUN": 23},
    }
):
    raise AssertionError
for row in receipt["jobs"]:
    if not (
        row["backend_observer_scope"]
        == ("Post-command observer process; test-child changed JAX config is not inferred.")
    ):
        raise AssertionError
if not (receipt["static_proxy"]["P41"].startswith("not_established")):
    raise AssertionError
for part in portable:
    for row in part["records"]:
        if not (identity(ROOT / row["path"]) == {"bytes": row["bytes"], "sha256": row["sha256"]}):
            raise AssertionError
result = {
    "source_sha": REF,
    "tree": "a4ed7ca77636c4e0165923e3d5400aea0c5068d5",
    "actual_wave_source": FROZEN,
    "portable_indexes": portable,
    "custody_denominators": {
        "portable_records": 79,
        "nested_moderate_asset_records": 48,
        "record_checks": 127,
        "distinct_copied_paths": 79,
    },
    "source_assets": source_assets,
    "raw_exclusions": raw_records,
    "counts": counts(all_cases),
    "native": counts(native),
    "A": counts(A_cases),
    "A_attribution": A_cases,
    "job_counts": job_counts,
    "stage_counts": stage_counts,
    "independent_corrupt_controls": controls,
    "publication_verdict": "GO-bounded-actual5e-custody-and-attribution",
    "reusable_collector_verdict": "HOLD-two synthetic protocol escapes separately recorded",
    "numeric_or_product_commands_executed": 0,
    "limitations": [
        "Custody COMPLETE_BOUND is not successful wave or finding closure.",
        (
            "Source-frame completeness is separately under independent CA"
            "L review; this validates exact existing bytes/declared frame"
            " consistency, not a new whole framework proof."
        ),
        (
            "Observer backend does not establish child JAX state; static "
            "proxy P41 inherited-red remains not_established."
        ),
        (
            "Actual raw171772803B and15 private config files were hashed "
            "only, not read into output or copied."
        ),
        ("No deletion/Trash action. Existing original and source bytes remain unchanged."),
    ],
}
(OUT / "custody-review.json").write_text(json.dumps(result, indent=2) + "\n")
_write_stdout(
    json.dumps(
        {
            k: v
            for k, v in result.items()
            if k not in ["portable_indexes", "source_assets", "A_attribution", "raw_exclusions"]
        },
        indent=2,
    )
)
