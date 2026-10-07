"Independent synthetic protocol controls: no product/native/gate execution."

import ast
import hashlib
import json
import runpy
import shutil
import subprocess
import sys
from argparse import Namespace
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
REF = "1e1b5028274814b7c4318671588202480390a6bc"
SOURCE = ROOT / (
    "policy-engine/docs/research/e02-cloud-test-plan/implementati"
    "on-handoffs/E/continuation-20261006/pr38-r2/failed-wave-5e-c"
    "ollector/collect_wave_v2.py"
)
REL = str(SOURCE.relative_to(ROOT))
original = SOURCE.read_bytes()
if not (
    original
    == subprocess.check_output([_resolve_executable("git"), "show", REF + ":" + REL], cwd=ROOT)  # noqa: S603 - admitted utility argv uses no shell; executable/source refs are explicit
):
    raise AssertionError
MODULE = runpy.run_path(str(SOURCE), run_name="independent_collector_protocol_only")
OLD = Path(
    "/workspace/e02-E-pr38-r2-receipts/common-wave-publication-pr"
    "ep/synthetic-controls-v2/positive/wave"
)
old_files = {
    str(p.relative_to(OLD)): hashlib.sha256(p.read_bytes()).hexdigest()
    for p in OLD.rglob("*")
    if p.is_file()
}


def rewritten(x: object, prefix: str) -> object:
    if isinstance(x, str):
        return x.replace(str(OLD), str(prefix))
    if isinstance(x, list):
        return [rewritten(v, prefix) for v in x]
    if isinstance(x, dict):
        return {k: rewritten(v, prefix) for k, v in x.items()}
    return x


def fixture(name: str, mutation: object = None, module: object = MODULE) -> object:
    wave = OUT / "synthetic-controls" / name / "wave"
    pub = wave.parent / "publication"
    shutil.copytree(OLD, wave)
    for p in wave.rglob("*.json"):
        p.write_text(json.dumps(rewritten(json.loads(p.read_text()), wave), indent=2) + "\n")
    plan = json.loads((wave / "plan.json").read_text())
    if plan["collector_control_only"] is not True:
        raise AssertionError
    target = next(j for j in plan["jobs"] if j["kind"] == "numerical")
    receipt_path = Path(target["output"]) / (target["name"] + ".json")
    receipt = json.loads(receipt_path.read_text())
    if mutation == "counts":
        receipt["counts"]["cases"] = 999
        receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
    elif mutation == "private-as-stdout":
        target = next(j for j in plan["jobs"] if j["kind"] == "importer")
        receipt_path = Path(target["output"]) / (target["name"] + ".json")
        receipt = json.loads(receipt_path.read_text())
        private = Path(receipt["git_input_config"]["private_complete_path"])
        if not (private.read_bytes() == b"collector-control-private-sentinel-not-real-config\0"):
            raise AssertionError
        receipt.update(
            stdout_path=str(private),
            stdout_bytes=private.stat().st_size,
            stdout_sha256=hashlib.sha256(private.read_bytes()).hexdigest(),
        )
        receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
    elif mutation == "wrong-classname":
        job = next(
            j for j in plan["jobs"] if j["group"] == "BKT_FRC_S10_and_adjacent_report_consumers"
        )
        xml = Path(job["junit"])
        data = xml.read_text()
        data = data.replace(
            'classname="test_a_cas_contract"',
            'classname="unrelated_test_a_cas_contract_counterfeit"',
        )
        xml.write_text(data)
    result = module["collect"](
        Namespace(
            repo=ROOT,
            candidate=plan["candidate_sha"],
            wave_root=wave,
            publication_root=pub,
            max_moderate_bytes=8 * 1024 * 1024,
            capture_incomplete=False,
        )
    )
    raw = [
        str(p.relative_to(pub))
        for p in pub.rglob("*")
        if p.is_file() and p.name.endswith("git-config-private.nul")
    ]
    summary = {
        "fixture": name,
        "source_reference": plan["candidate_sha"],
        "collector_control_only": True,
        "product_native_or_gate_commands_executed": 0,
        "state": result["collection_state"],
        "issues": result["issues"],
        "native_counts": result["native_numeric_counts_excluding_A_packets"],
        "A_counts": [x["counts"] for x in result["foreign_owner_A_packet_cases"]],
        "private_paths_published": raw,
        "stdout_only_synthetic_sentinel": True,
    }
    return summary


rows = [
    fixture("independent-positive"),
    fixture("independent-corrupt-counts", "counts"),
    fixture("independent-private-as-stdout", "private-as-stdout"),
    fixture("independent-wrong-classname", "wrong-classname"),
]
if not (rows[0]["state"] == "CONTROL_COMPLETE_BOUND" and not rows[0]["private_paths_published"]):
    raise AssertionError
if not (rows[1]["state"] == "CONTROL_LIMITED_INCOMPLETE_OR_INCONSISTENT"):
    raise AssertionError
if not (rows[2]["private_paths_published"] and rows[2]["state"] == "CONTROL_COMPLETE_BOUND"):
    raise AssertionError
if not (
    rows[3]["state"] == "CONTROL_COMPLETE_BOUND" and rows[3]["A_counts"] == rows[0]["A_counts"]
):
    raise AssertionError
# Effective property removal keeps the collector protocol/field/function names.
tree = ast.parse(original)
removed = 0
for node in ast.walk(tree):
    if isinstance(node, ast.If) and ast.unparse(node.test) == "counts != receipt['counts']":
        node.test = ast.Constant(False)
        removed += 1
if not (removed == 1):
    raise AssertionError
ast.fix_missing_locations(tree)
removal_source = ast.unparse(tree) + "\n"
(OUT / "counts_guard_removed.py.txt").write_text(removal_source)
namespace = {"__name__": "independent_removed_collector", "__file__": str(SOURCE)}
exec(compile(tree, str(SOURCE) + "[count-predicate-removed]", "exec"), namespace)  # noqa: S102 - isolated removal control executes exact Git/AST fixture, never external input
row = fixture("independent-count-guard-removed", "counts", namespace)
if not (row["state"] == "CONTROL_COMPLETE_BOUND" and not row["issues"]):
    raise AssertionError
row["outcome"] = "EXPECTED_DISCRIMINATING_ESCAPE"
rows.append(row)
if not (SOURCE.read_bytes() == original):
    raise AssertionError
for name, h in old_files.items():
    if not (hashlib.sha256((OLD / name).read_bytes()).hexdigest() == h):
        raise AssertionError
result = {
    "source_sha": REF,
    "collector_sha256": hashlib.sha256(original).hexdigest(),
    "scope": (
        "Synthetic independent protocol controls only; no product/num"
        "erical/gate/production evidence"
    ),
    "controls": rows,
    "original_source_and_author_fixture_unchanged": True,
    "actual5e_publication_bytes": "Not changed; separate custody read-only verification",
    "verdict": (
        "HOLD-reusable-collector-raw-path-and-exact-module-attributio"
        "n; actual5e bounded custody separately assessable"
    ),
}
(OUT / "controls.json").write_text(json.dumps(result, indent=2) + "\n")
_write_stdout(json.dumps(result, indent=2))
