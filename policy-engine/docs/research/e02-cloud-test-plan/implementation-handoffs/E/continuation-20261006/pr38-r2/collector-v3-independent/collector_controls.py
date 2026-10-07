"Independent immutable v3 protocol controls; no numerical or gate execution."

import ast
import hashlib
import json
import runpy
import shutil
import sys
from argparse import Namespace
from pathlib import Path


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
EXPECTED = "a6399cc46cbfe25b103fa210259eff2be9483f582ae7cba773632f079f7194ec"
original = SOURCE.read_bytes()
if not (hashlib.sha256(original).hexdigest() == EXPECTED):
    raise AssertionError
MODULE = runpy.run_path(str(SOURCE), run_name="independent_v3_protocol_only")
OLD = Path(
    "/workspace/e02-E-pr38-r2-receipts/common-wave-publication-pr"
    "ep/synthetic-controls-v2/positive/wave"
)
old_files = {
    str(p.relative_to(OLD)): hashlib.sha256(p.read_bytes()).hexdigest()
    for p in OLD.rglob("*")
    if p.is_file()
}


def rewritten(value: object, wave: object) -> object:
    if isinstance(value, str):
        return value.replace(str(OLD), str(wave))
    if isinstance(value, list):
        return [rewritten(v, wave) for v in value]
    if isinstance(value, dict):
        return {k: rewritten(v, wave) for k, v in value.items()}
    return value


def fixture(name: str, mutation: object = None, module: object = MODULE) -> dict[str, object]:
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
    elif mutation in {"private-as-stdout", "stdout-alias", "leaf-symlink"}:
        target = next(j for j in plan["jobs"] if j["kind"] == "importer")
        receipt_path = Path(target["output"]) / (target["name"] + ".json")
        receipt = json.loads(receipt_path.read_text())
        canonical = Path(receipt["stdout_path"])
        if mutation == "private-as-stdout":
            alternate = Path(receipt["git_input_config"]["private_complete_path"])
            if not (
                alternate.read_bytes() == b"collector-control-private-sentinel-not-real-config\0"
            ):
                raise AssertionError
        elif mutation == "stdout-alias":
            alternate = canonical.parent / "same-byte-alias.stdout.txt"
            alternate.write_bytes(canonical.read_bytes())
        else:
            held = canonical.parent / "saved-original.stdout.txt"
            canonical.rename(held)
            canonical.symlink_to(held)
            alternate = canonical
        receipt.update(
            stdout_path=str(alternate),
            stdout_bytes=alternate.stat().st_size,
            stdout_sha256=hashlib.sha256(alternate.read_bytes()).hexdigest(),
        )
        receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
    elif mutation in {
        "wrong-classname",
        "anonymous",
        "wrong-file",
        "anonymous-wrong-file",
        "exact-file",
        "parent-symlink",
    }:
        job = next(
            j for j in plan["jobs"] if j["group"] == "BKT_FRC_S10_and_adjacent_report_consumers"
        )
        xml = Path(job["junit"])
        data = xml.read_text()
        if mutation == "wrong-classname":
            data = data.replace(
                'classname="test_a_cas_contract"',
                'classname="unrelated_test_a_cas_contract_counterfeit"',
            )
        if mutation in {"anonymous", "anonymous-wrong-file"}:
            data = data.replace('classname="test_a_cas_contract"', 'classname=""')
        if mutation in {"wrong-file", "anonymous-wrong-file", "exact-file"}:
            packet = next(
                p
                for p in plan["owner_packet_extra_inputs"]
                if Path(p["destination"]).stem == "test_a_cas_contract"
            )
            file_label = (
                packet["destination"]
                if mutation == "exact-file"
                else str(wave / "owner-packets" / "wrong.py")
            )
            replacement = (
                'classname=""'
                if mutation == "anonymous-wrong-file"
                else 'classname="test_a_cas_contract"'
            )
            data = data.replace(replacement, replacement + ' file="' + file_label + '"')
        xml.write_text(data)
        if mutation == "parent-symlink":
            check = Path(job["output"])
            saved = check.with_name(check.name + "-preserved")
            check.rename(saved)
            check.symlink_to(saved, target_is_directory=True)
    try:
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
        state = result["collection_state"]
        summary = {
            key: result[key]
            for key in [
                "issues",
                "native_numeric_counts_excluding_A_packets",
                "unattributed_owner_packet_counts",
                "native_numeric_attribution_complete",
            ]
        }
        summary["A_counts"] = [p["counts"] for p in result["foreign_owner_A_packet_cases"]]
    except module["EvidenceAdmissionError"] as error:
        state = "TYPED_REFUSAL"
        summary = {"reason": str(error)}
    private = [
        str(p.relative_to(pub))
        for p in pub.rglob("*")
        if p.is_file()
        and (p.name.endswith("git-config-private.nul") or "raw" in p.relative_to(pub).parts)
    ]
    return {
        "fixture": name,
        "mutation": mutation,
        "state": state,
        "private_or_raw_payload_paths_published": private,
        "product_native_or_gate_commands_executed": 0,
        "synthetic_only": True,
        **summary,
    }


rows = [
    fixture("positive"),
    fixture("anonymous-positive", "anonymous"),
    fixture("exact-file-positive", "exact-file"),
]
for row in rows:
    if not (
        row["state"] == "CONTROL_COMPLETE_BOUND"
        and not row["private_or_raw_payload_paths_published"]
    ):
        raise AssertionError
    if not (row["native_numeric_counts_excluding_A_packets"]["cases"] == 7):
        raise AssertionError
    if not (row["unattributed_owner_packet_counts"]["cases"] == 0):
        raise AssertionError
for name in [
    "counts",
    "private-as-stdout",
    "stdout-alias",
    "leaf-symlink",
    "wrong-classname",
    "wrong-file",
    "anonymous-wrong-file",
    "parent-symlink",
]:
    row = fixture(name, name)
    if row["state"] not in {"CONTROL_LIMITED_INCOMPLETE_OR_INCONSISTENT", "TYPED_REFUSAL"}:
        raise AssertionError
    if row["private_or_raw_payload_paths_published"]:
        raise AssertionError
    if name in {"wrong-classname", "wrong-file", "anonymous-wrong-file"}:
        if not (row["unattributed_owner_packet_counts"]["cases"] == 2):
            raise AssertionError
        if not (row["native_numeric_counts_excluding_A_packets"]["cases"] == 7):
            raise AssertionError
        if not (row["A_counts"][0]["cases"] == 0):
            raise AssertionError
        if row["native_numeric_attribution_complete"] is not False:
            raise AssertionError
    rows.append(row)


def removed_module(label: str, mutate: object) -> object:
    tree = ast.parse(original)
    count = mutate(tree)
    if not (count == 1):
        raise AssertionError((label, count))
    ast.fix_missing_locations(tree)
    (OUT / (label + ".py.txt")).write_text(ast.unparse(tree) + "\n")
    namespace = {"__name__": "independent_removed_v3_collector", "__file__": str(SOURCE)}
    exec(compile(tree, str(SOURCE) + "[" + label + "]", "exec"), namespace)  # noqa: S102 - isolated removal control executes exact Git/AST fixture, never external input
    return namespace


def remove_counts(tree: str) -> object:
    nodes = [
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.If) and ast.unparse(n.test) == "counts != receipt['counts']"
    ]
    for node in nodes:
        node.test = ast.Constant(False)
    return len(nodes)


def remove_module(tree: str) -> object:
    nodes = [
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "named_module" for t in n.targets)
    ]
    for node in nodes:
        node.value = ast.parse("packet['module_stem'] in classname", mode="eval").body
    return len(nodes)


def remove_role(tree: str) -> object:
    nodes = [
        n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "public_evidence"
    ]
    for node in nodes:
        node.body = ast.parse("return inside(root, path)").body
    return len(nodes)


for label, mutation, remover in [
    ("counts-removed", "counts", remove_counts),
    ("module-removed", "wrong-classname", remove_module),
    ("role-removed", "private-as-stdout", remove_role),
]:
    row = fixture(label, mutation, removed_module(label, remover))
    if not (row["state"] == "CONTROL_COMPLETE_BOUND"):
        raise AssertionError
    if label == "role-removed" and not (row["private_or_raw_payload_paths_published"]):
        raise AssertionError
    row["outcome"] = "EXPECTED_DISCRIMINATING_ESCAPE"
    rows.append(row)

if not (SOURCE.read_bytes() == original):
    raise AssertionError
for name, digest in old_files.items():
    if not (hashlib.sha256((OLD / name).read_bytes()).hexdigest() == digest):
        raise AssertionError
result = {
    "source_path": str(SOURCE),
    "source_sha256": EXPECTED,
    "source_bytes": len(original),
    "scope": (
        "Independent synthetic protocol-only source review; zero product/native/gate commands"
    ),
    "controls": rows,
    "control_count": len(rows),
    "original_source_and_author_fixture_unchanged": True,
    "verdict": "GO-bounded-path-role-and-exact-owner-attribution-protocol",
    "finding_closure": False,
}
(OUT / "controls.json").write_text(json.dumps(result, indent=2) + "\n")
_write_stdout(json.dumps(result, indent=2))
