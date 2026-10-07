"Read-only exact-Git assembly joins; prepare only, never execute any wave."

from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import json
import os
import platform
import runpy
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


def _write_stdout(*values: object, flush: bool = False) -> None:
    "Emit the existing CLI text and optionally flush without logging side effects."
    sys.stdout.write(" ".join(str(value) for value in values) + "\n")
    if flush:
        sys.stdout.flush()


ROOT = Path("/workspace/e02-E-continuation-20261006")
OUT = Path(__file__).resolve().parent
PREFIX = (
    "policy-engine/docs/research/e02-cloud-test-plan/implementati"
    "on-handoffs/E/continuation-20261006/pr38-r2/"
)
BASE = "5e3e3727685132f270a3a07b9f63dd962a88cd96"
CANDIDATE = "94d3e6ee67b70a5ef4f71e529275aa7db0fddcde"
TREE = "2220bc48d1ccfd62310de0737c3be939c06d2d2f"
HARNESS = "06aec834d817b1cc90d98308f0755729a4153031"
FACADE = "cfd79255aab85544082fcf24f93db894202fbfa2"
COLLECTOR = "2f7e7e12516dd98678903c5b4a89553a28b08608"
blob_cache = {}


def _admit_git_object_arguments(arguments: tuple[str, ...]) -> None:
    """Keep object reads from interpreting record refs as Git options.

    Named/abbreviated refs remain available to retired source-pinned replay
    scripts; live packet admissions separately require full immutable SHAs.
    """
    if not arguments or arguments[0] not in {"show", "rev-parse"}:
        return
    safe_information_flags = {"--show-toplevel", "--git-dir", "--git-common-dir"}
    for value in arguments[1:]:
        if not isinstance(value, str) or not value or "\0" in value:
            raise ValueError("Git object argument must be a nonempty string")
        if value.startswith("-"):
            if arguments[0] == "rev-parse" and value in safe_information_flags:
                continue
            raise ValueError("Git object reference must never be an option")
        if ":" in value:
            _, relative = value.split(":", 1)
            path = Path(relative)
            if (
                not path.parts
                or path.is_absolute()
                or ".." in path.parts
                or path.as_posix() != relative
                or "\0" in relative
            ):
                raise ValueError("Git object path must be repository relative")


def git(*args: object) -> object:
    _admit_git_object_arguments(args)
    return subprocess.check_output([_resolve_executable("git"), "-C", str(ROOT), *args])  # noqa: S603 - admitted utility argv uses no shell; executable/source refs are explicit


def trees(ref: object) -> object:
    rows = {}
    for record in git("ls-tree", "-rz", ref).split(b"\0"):
        if record:
            meta, path = record.split(b"\t", 1)
            mode, kind, blob = meta.decode().split()
            if not (kind == "blob"):
                raise AssertionError
            rows[path.decode()] = (mode, blob)
    return rows


CURRENT = trees(CANDIDATE)
OLD = trees(BASE)


def data(path: object, ref: object = CANDIDATE) -> object:
    key = (ref, path)
    if key not in blob_cache:
        blob_cache[key] = git("show", ref + ":" + path)
    return blob_cache[key]


def sha(payload: object) -> str:
    return hashlib.sha256(payload).hexdigest()


def identity(path: object, ref: object = CANDIDATE) -> dict[str, object]:
    payload = data(path, ref)
    return {
        "path": path,
        "bytes": len(payload),
        "sha256": sha(payload),
        "git_blob": git("rev-parse", ref + ":" + path).decode().strip(),
    }


def load(rel: object) -> object:
    return json.loads(data(PREFIX + rel))


def write(name: str, value: object) -> None:
    (OUT / name).write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def snapshot() -> dict[str, object]:
    frame = hashlib.sha256()
    total = 0
    for path, (mode, expected_blob) in sorted(CURRENT.items()):
        local = ROOT / path
        payload = os.readlink(local).encode() if mode == "120000" else local.read_bytes()
        actual_blob = hashlib.sha1(
            b"blob " + str(len(payload)).encode() + b"\0" + payload, usedforsecurity=False
        ).hexdigest()
        if not (actual_blob == expected_blob):
            raise AssertionError(("working_vs_Git_mismatch", path))
        total += len(payload)
        frame.update(
            path.encode()
            + b"\0"
            + str(len(payload)).encode()
            + b"\0"
            + hashlib.sha256(payload).digest()
        )
    config_path = ROOT / git("rev-parse", "--git-path", "config").decode().strip()
    config = config_path.read_bytes()
    return {
        "head": git("rev-parse", "HEAD").decode().strip(),
        "tree": git("rev-parse", "HEAD^{tree}").decode().strip(),
        "tracked_dirty": git("status", "--porcelain=v1", "--untracked-files=no").decode(),
        "tracked_paths": len(CURRENT),
        "tracked_bytes": total,
        "frame_format": "sorted UTF8path NUL decimalBytes NUL rawSHA256digest",
        "framed_sha256": frame.hexdigest(),
        "private_Git_config": {
            "bytes": len(config),
            "sha256": sha(config),
            "payload_copied": False,
        },
    }


before = snapshot()
if not (before["head"] == CANDIDATE and before["tree"] == TREE and not before["tracked_dirty"]):
    raise AssertionError
diff = git("diff", "--name-only", BASE, CANDIDATE).decode().splitlines()
facade_review_path = PREFIX + "owned-facade-independent/review-cfd79255.json"
facade_review = load("owned-facade-independent/review-cfd79255.json")
harness_review_path = PREFIX + "harness-native-parent-independent/independent-review-06aec834.json"
harness_review = load("harness-native-parent-independent/independent-review-06aec834.json")
collector_review_path = PREFIX + "collector-v4-independent/review.json"
collector_review = load("collector-v4-independent/review.json")
facade_paths = facade_review["full_footprint"]
operational = set(facade_paths) | {
    PREFIX + "wave-controls/" + name for name in ["plan_wave.py", "collect_wave.py", "README.md"]
}
if not (facade_review["candidate_sha"] == FACADE and facade_review["reviewer"] == "/root/ddm_r2"):
    raise AssertionError
if not (facade_review["disposition"] == "GO_bounded_code_and_companions"):
    raise AssertionError
if not (harness_review["source_sha"] == HARNESS and harness_review["disposition"].startswith("GO")):
    raise AssertionError
if not (collector_review["reusable_collector_verdict"].startswith("GO")):
    raise AssertionError
if "doe_r2" not in collector_review["reviewer"]:
    raise AssertionError

source_joins = []
for rec in facade_review["tested_source_representation"]["exact12_postimages"]:
    actual = identity(rec["path"])
    if not (actual["bytes"] == rec["bytes"] and actual["sha256"] == rec["after_sha256"]):
        raise AssertionError
    if not (data(rec["path"]) == data(rec["path"], FACADE)):
        raise AssertionError
    source_joins.append(
        dict(
            actual,
            source=FACADE,
            review=facade_review_path,
            owner="backtest author / DDM independent reviewer",
        )
    )
for name, source, review in [
    ("plan_wave.py", HARNESS, harness_review_path),
    ("collect_wave.py", COLLECTOR, collector_review_path),
    ("README.md", COLLECTOR, collector_review_path),
]:
    path = PREFIX + "wave-controls/" + name
    if not (data(path) == data(path, source)):
        raise AssertionError
    source_joins.append(
        dict(
            identity(path),
            source=source,
            review=review,
            owner="FRC author / independent CAL harness or DoE collector reviewer",
        )
    )
if not (
    identity(PREFIX + "wave-controls/plan_wave.py")["sha256"]
    == harness_review["source_inputs"]["plan_wave"]["sha256"]
):
    raise AssertionError
if not (
    identity(PREFIX + "wave-controls/collect_wave.py")["sha256"]
    == collector_review["source"]["sha256"]
):
    raise AssertionError
if not (identity(PREFIX + "wave-controls/collect_wave.py")["bytes"] == 38197):
    raise AssertionError
for name, key in [("run_check.py", "run_check"), ("uncapped_umbrella.py", "umbrella")]:
    path = PREFIX + "wave-controls/" + name
    if not (data(path) == data(path, BASE)):
        raise AssertionError
    if not (identity(path)["sha256"] == harness_review["source_inputs"][key]["sha256"]):
        raise AssertionError

# All native mathematical source bodies except facade/caller import routes are byte-identical.
product_paths = sorted(path for path in CURRENT if path.startswith("policy-engine/src/polisyos/"))
product_changes = [
    path
    for path in sorted(
        set(product_paths) | {p for p in OLD if p.startswith("policy-engine/src/polisyos/")}
    )
    if CURRENT.get(path) != OLD.get(path)
]
expected_product = sorted(path for path in facade_paths if path.startswith("policy-engine/src/"))
if not (product_changes == expected_product):
    raise AssertionError


class RemoveImports(ast.NodeTransformer):
    def visit_Import(self, node: object) -> None:
        return None

    def visit_ImportFrom(self, node: object) -> None:
        return None


def non_import_ast(payload: object) -> object:
    return ast.dump(RemoveImports().visit(ast.parse(payload)), include_attributes=False)


body_joins = []
for suffix in ["propagate_uncertainty.py", "propagate_welfare.py"]:
    path = "policy-engine/src/polisyos/scientist/nodes/builtins/simulate/" + suffix
    old_ast, new_ast = non_import_ast(data(path, BASE)), non_import_ast(data(path))
    if not (old_ast == new_ast):
        raise AssertionError
    body_joins.append(
        {
            "path": path,
            "old_sha256": sha(data(path, BASE)),
            "new_sha256": sha(data(path)),
            "nonimport_AST_sha256": sha(new_ast.encode()),
            "nonimport_AST_equal": True,
            "delta_review": facade_review_path,
        }
    )
fixed_math = [
    path
    for path in product_paths
    if path.startswith(
        (
            "policy-engine/src/polisyos/foundry/calibration/",
            "policy-engine/src/polisyos/foundry/uncertainty/",
        )
    )
    and path not in expected_product
]
if not (all(CURRENT[path] == OLD[path] for path in fixed_math)):
    raise AssertionError
if not (
    CURRENT["policy-engine/src/polisyos/foundry/uncertainty/covariance.py"]
    == OLD["policy-engine/src/polisyos/foundry/uncertainty/covariance.py"]
):
    raise AssertionError
if not (
    CURRENT["policy-engine/src/polisyos/foundry/calibration/preflight.py"]
    == OLD["policy-engine/src/polisyos/foundry/calibration/preflight.py"]
):
    raise AssertionError

# Exact existing family independent judgments; this author never approves own CAL mathematics.
prior = load("assembly-delta-independent/assembly-delta-review-d43.json")
c79 = load("assembly-independent/assembly-dependency-review-c79.json")
reused_reviews = []
for rec in prior["prior_independent_review_joins"]:
    actual = identity(rec["path"])
    if not (actual["sha256"] == rec["sha256"] and actual["bytes"] == rec["bytes"]):
        raise AssertionError
    reused_reviews.append(
        dict(
            actual,
            family=rec["family"],
            basis=(
                "unchanged independent receipt; reuse sou"
                "rce identities, not historical check cou"
                "nts"
            ),
        )
    )
budget_path = PREFIX + "doe-budget-independent/doe-budget-independent-review-70c4.json"
if not (data(budget_path) == data(budget_path, BASE)):
    raise AssertionError
reused_reviews.append(
    dict(
        identity(budget_path),
        family="DoE mutable-plan delta",
        basis="own independent70c review; unchanged complete source blobs",
    )
)
cal_review = load("independent-reviews/cal-ddm/review.json")
if not (
    "doe_r2" in cal_review["reviewer"]
    and cal_review["families"]["cal"]["code_verdict"].startswith("GO")
):
    raise AssertionError
if not (
    cal_review["families"]["cal"]["implementation_sha"]
    == "45b834534958c262a8146e6c4d847cf8d53846bc"
):
    raise AssertionError

prior_source_joins = []
for rec in [*prior["prior_operational_joins"], *prior["new_reviewed_source_joins"]]:
    path = rec["path"]
    old_blob = rec.get("final_blob", rec.get("git_blob"))
    actual_blob = CURRENT[path][1]
    if actual_blob != old_blob:
        if path not in operational:
            raise AssertionError(("unreviewed_prior_join_delta", path))
        basis = "superseded only by exact independently reviewed canonical facade companion"
    else:
        basis = "prior independent assembly exact blob retained"
    prior_source_joins.append(
        {
            "path": path,
            "prior_blob": old_blob,
            "current_blob": actual_blob,
            "unchanged": actual_blob == old_blob,
            "basis": basis,
        }
    )

inventory = json.loads(data("policy-engine/architecture/public_surface/inventory.json"))
canonical_counts = {}
for module, count in [
    ("polisyos.calibration", 28),
    ("polisyos.foundry.uncertainty", 25),
    ("polisyos.ddm", 17),
]:
    parent = next(
        x
        for x in inventory["packages"]
        if x["module"] == module or any(e["module"] == module for e in x.get("entrypoints", []))
    )
    row = (
        parent
        if parent["module"] == module
        else next(e for e in parent["entrypoints"] if e["module"] == module)
    )
    if not (
        row["export_count"] == count
        and len(row["exports"]) == count
        and len(set(row["exports"])) == count
    ):
        raise AssertionError
    path = "policy-engine/src/" + module.replace(".", "/") + "/__init__.py"
    module_ast = ast.parse(data(path))
    names = ast.literal_eval(
        next(
            node.value
            for node in module_ast.body
            if isinstance(node, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == "__all__" for t in node.targets)
        )
    )
    if not (set(names) == set(row["exports"]) and len(names) == count):
        raise AssertionError
    canonical_counts[module] = {
        "exports": names,
        "count": count,
        "classification": parent["classification"],
        "owner": parent["owner"],
        "inventory_and_source_equal": True,
    }

portable_paths = [path for path in diff if path.endswith("/portable-copy-index.json")]
verified_indices, indexed_paths = [], set()
raw_private_digests = {
    before["private_Git_config"]["sha256"],
    "d81083de050dcc43f399ec332d582e70a2e501330be4aaf0387679114b5a7db8",
    "404cdb1543a96433016ca3880c3d557e2d027f9fa62060be40d9b8e266b16fbd",
}


def verify_record(rec: object) -> object:
    path = rec["copied_path"]
    if not (path in CURRENT and path.startswith(PREFIX)):
        raise AssertionError
    if not (type(rec["bytes"]) is int and rec["bytes"] >= 0):
        raise AssertionError
    payload = data(path)
    if not (len(payload) == rec["bytes"] and sha(payload) == rec["sha256"]):
        raise AssertionError
    if not (sha(payload) not in raw_private_digests and len(payload) < 171772803):
        raise AssertionError
    if not ((ROOT / path).read_bytes() == payload):
        raise AssertionError
    return path


for index_path in portable_paths:
    index = json.loads(data(index_path))
    records = index["records"]
    paths = [verify_record(rec) for rec in records]
    if not (len(paths) == len(set(paths))):
        raise AssertionError
    if index["complete"] is not True:
        raise AssertionError
    if "copies" in index and (
        not (type(index["copies"]) is int and index["copies"] == len(records))
    ):
        raise AssertionError
    if "bytes" in index and (
        not (type(index["bytes"]) is int and index["bytes"] == sum(x["bytes"] for x in records))
    ):
        raise AssertionError
    if index["primary_receipt"] not in paths:
        raise AssertionError
    indexed_paths.update(paths)
    indexed_paths.add(index_path)
    verified_indices.append(
        dict(
            identity(index_path),
            records=len(records),
            payload_bytes=sum(x["bytes"] for x in records),
            all_exact_Git_blobs=True,
            private_actual_payloads_copied=False,
        )
    )

root_bindings = {
    PREFIX + name
    for name in [
        "collector-v4-implementation.json",
        "harness-native-parent-implementation.json",
        "harness-native-parent-publication-validation.json",
        "owned-facade-implementation.json",
        "owned-facade-publication-validation.json",
    ]
}
if not (set(diff) - indexed_paths == operational | root_bindings):
    raise AssertionError
full_footprint = []
for path in diff:
    kind = (
        "reviewed_operational_source_or_companion"
        if path in operational
        else "root_exact_source_publication_binding"
        if path in root_bindings
        else "portable_deciding_evidence_or_index"
    )
    full_footprint.append(dict(identity(path), category=kind))

# Safe preparation: only stdlib plus read-only Git; explicitly do not call main/execute.
plan_file = ROOT / (PREFIX + "wave-controls/plan_wave.py")
namespace = runpy.run_path(str(plan_file), run_name="assembly_review_readonly_import")


def forbid_execute(*args: object, **kwargs: object) -> None:
    raise AssertionError("numeric_or_gate_execution_forbidden_in_assembly_review")


namespace["prepare"].__globals__["execute"] = forbid_execute
planning_root = OUT / "planned-wave-94d3"
if not (not planning_root.exists() and not planning_root.is_symlink()):
    raise AssertionError
plan = namespace["prepare"](
    argparse.Namespace(
        repo=ROOT,
        candidate=CANDIDATE,
        comparison_base="198076863e143dea9f89f02734b13d50dae3eed5",
        output_root=planning_root,
        no_owner_packets=False,
    )
)
if not (
    plan["execution_state"] == "NOT_RUN"
    and not plan["missing_required_paths"]
    and plan["old_paths_retained"]
):
    raise AssertionError
if not (all(row["in_candidate_history"] for row in plan["required_upstream"].values())):
    raise AssertionError
if planning_root.exists():
    raise AssertionError
actual_flat = [path for rows in plan["groups"].values() for path in rows]
if not (len(actual_flat) == len(set(actual_flat)) == plan["native_test_path_count"]):
    raise AssertionError
actual_lint = [
    path.removeprefix("policy-engine/")
    for path in git(
        "diff",
        "--name-only",
        "--diff-filter=ACMR",
        plan["comparison_base"],
        CANDIDATE,
        "--",
        "policy-engine",
    )
    .decode()
    .splitlines()
    if path.endswith(".py") and path in CURRENT
]
if not (plan["changed_python_lint_paths"] == actual_lint):
    raise AssertionError
old_plan = json.loads(data(PREFIX + "failed-wave-5e/plan.json"))
flat_old = {path for rows in old_plan["groups"].values() for path in rows}
if not (flat_old <= set(actual_flat)):
    raise AssertionError
write("prepared-plan-94d3.json", plan)


def assert_plan_claim(claim: object) -> None:
    if not (claim["candidate_sha"] == CANDIDATE and claim["candidate_tree_sha"] == TREE):
        raise AssertionError
    if not (claim["native_test_path_count"] == len(actual_flat)):
        raise AssertionError
    if not (
        claim["test_input_path_count_including_owner_packets"]
        == len(actual_flat) + len(plan["owner_packet_extra_inputs"])
    ):
        raise AssertionError
    if not (claim["changed_python_lint_paths"] == actual_lint):
        raise AssertionError
    if not (
        claim["execution_state"] == "NOT_RUN"
        and str(claim["runtime_test_case_count"]).startswith("UNRUN")
    ):
        raise AssertionError


negative_controls = []


def reject(name: str, callback: object) -> None:
    try:
        callback()
    except (AssertionError, KeyError):
        negative_controls.append(
            {
                "control": name,
                "state": "REJECTED",
                "mechanism": "actual independent byte/property validator",
            }
        )
    else:
        raise AssertionError(("negative_not_discriminating", name))


first_record = json.loads(data(portable_paths[0]))["records"][0]
for field, bad in [
    ("bytes", first_record["bytes"] + 1),
    ("sha256", "0" * 64),
    ("copied_path", PREFIX + "absent-unpublished-receipt.json"),
]:
    altered = dict(first_record, **{field: bad})
    reject("portable_" + field, lambda altered=altered: verify_record(altered))
for field, bad in [
    ("candidate_sha", BASE),
    ("native_test_path_count", old_plan["native_test_path_count"]),
    ("execution_state", "PASS"),
    ("runtime_test_case_count", "1440 PASS"),
]:
    altered = copy.deepcopy(plan)
    altered[field] = bad
    reject("plan_" + field, lambda altered=altered: assert_plan_claim(altered))
altered = copy.deepcopy(plan)
altered["changed_python_lint_paths"].pop()
reject("plan_omitted_lint_path", lambda: assert_plan_claim(altered))


def source_hash_assert(altered: object) -> None:
    if not (
        altered["sha256"] == sha(data(altered["path"]))
        and altered["bytes"] == len(data(altered["path"]))
    ):
        raise AssertionError


altered = dict(source_joins[0], sha256="f" * 64)
reject("reviewed_postimage_false_digest", lambda: source_hash_assert(altered))


def body_assert(payload: object) -> None:
    if not (
        non_import_ast(payload)
        == non_import_ast(
            data(
                (
                    "policy-engine/src/polisyos/scientist/nod"
                    "es/builtins/simulate/propagate_welfare.p"
                    "y"
                ),
                BASE,
            )
        )
    ):
        raise AssertionError


altered_body = ast.parse(
    data("policy-engine/src/polisyos/scientist/nodes/builtins/simulate/propagate_welfare.py")
)
empirical_reconciler = next(
    n
    for n in altered_body.body
    if isinstance(n, ast.FunctionDef) and n.name == "_reconcile_welfare_empirical_rows"
)
weight_zero = next(
    n
    for n in ast.walk(empirical_reconciler)
    if isinstance(n, ast.Constant) and type(n.value) is float and n.value == 0.0
)
weight_zero.value = 1.0
reject(
    "same_import_markers_changed_actual_Welfare_empirical_weight_predicate",
    lambda: body_assert(ast.unparse(altered_body).encode()),
)


def cal_reviewer_assert(reviewer: object) -> None:
    if not ("doe_r2" in reviewer and "cal_uq_r3" not in reviewer):
        raise AssertionError


reject(
    "own_CAL_author_substituted_as_independent_reviewer",
    lambda: cal_reviewer_assert("/root/cal_uq_r3"),
)


def facade_count_assert(count: int) -> None:
    if not (count == len(canonical_counts["polisyos.foundry.uncertainty"]["exports"])):
        raise AssertionError


reject("old_uncertainty20_count_retained", lambda: facade_count_assert(20))

# Exact foreign/schema/results/ownership boundaries never changed by this new delta.
foreign_prefixes = [
    "policy-engine/schemas/",
    "policy-engine/architecture/policy",
    "policy-engine/src/polisyos/core/",
    "policy-engine/src/polisyos/ir/",
    "policy-engine/src/polisyos/runtime/",
    "policy-engine/src/polisyos/scientist/search/",
]
if any(path.startswith(tuple(foreign_prefixes)) for path in diff):
    raise AssertionError
if any(
    path.startswith("policy-engine/docs/research/e02-cloud-test-plan/results/")
    or path.startswith("policy-engine/docs/research/e02-cloud-test-plan/closure-decisions/")
    for path in diff
):
    raise AssertionError
if any(
    "generation_cycle.py" in path or "run_lifecycle.py" in path or "baseline" in path
    for path in diff
):
    raise AssertionError
ancestry = {}
for label, ref in [
    ("main", "198076863e143dea9f89f02734b13d50dae3eed5"),
    ("G_owner_audit53", "53b309019913b938909d6dc0fc13f8edb409f368"),
    ("G_docs363", "363e7ae0cb2929a92d9667334fdc0ac3087daf5e"),
]:
    if not (
        subprocess.run(  # noqa: S603 - admitted utility argv uses no shell; executable/source refs are explicit
            [
                _resolve_executable("git"),
                "-C",
                str(ROOT),
                "merge-base",
                "--is-ancestor",
                ref,
                CANDIDATE,
            ],
            check=False,
        ).returncode
        == 0
    ):
        raise AssertionError
    ancestry[label] = ref
ancestry["origin/main_current_tracking"] = git("rev-parse", "origin/main").decode().strip()
if not (ancestry["origin/main_current_tracking"] == ancestry["main"]):
    raise AssertionError
after = snapshot()
if not (before == after):
    raise AssertionError

write("full-footprint-5e-to-94d3.json", full_footprint)
write(
    "source-review-joins-94d3.json",
    {
        "current_source": source_joins,
        "retained_prior_joins": prior_source_joins,
        "independent_reuse": reused_reviews,
        "consumer_body_AST": body_joins,
        "fixed_CAL_UQ_source_wholeblob_paths": fixed_math,
    },
)
write(
    "portable-Git-copies-94d3.json",
    {"indices": verified_indices, "unique_indexed_paths": len(indexed_paths), "complete": True},
)
write("negative-controls-94d3.json", negative_controls)
review = {
    "schema": "e02.E.independent-final-assembly-delta.v1",
    "reviewer": (
        "/root/cal_uq_r3; assembly joins only, own CAL source uses DoE independent judgment"
    ),
    "disposition": "GO_bounded_source_readiness_for_distinct_corrected_freeze",
    "base": BASE,
    "candidate": CANDIDATE,
    "tree": TREE,
    "source_before": before,
    "source_after": after,
    "immutable": before == after,
    "full_footprint": {
        "paths": len(diff),
        "operational_paths": len(operational),
        "root_binding_paths": len(root_bindings),
        "portable_delta_paths": len(set(diff) & indexed_paths),
        "complete_asset": "full-footprint-5e-to-94d3.json",
    },
    "source_deltas": {
        "harness": HARNESS,
        "facade": FACADE,
        "collector": COLLECTOR,
        "all_postimages_reviewed_and_exact": True,
    },
    "product_source": {
        "paths": len(product_paths),
        "changed_paths": product_changes,
        "unchanged_paths": len(product_paths) - len(product_changes),
        "four_runtime_Python_files_are_only_import_facade_or_caller_routes": True,
        "both_consumer_nonimport_AST_equal": True,
        "fixed_CAL_UQ_wholeblob_paths": len(fixed_math),
        "covariance_and_CAL_scalar_std_preflight_wholeblob_equal": True,
        "CAL_mechanism_reviewer": cal_review["reviewer"],
        "new_CAL_self_review": False,
    },
    "canonical_exports": canonical_counts,
    "portable_custody": {
        "indices": len(verified_indices),
        "indexed_records": sum(x["records"] for x in verified_indices),
        "indexed_payload_bytes": sum(x["payload_bytes"] for x in verified_indices),
        "all_local_and_Git_exact": True,
        "actual_raw171MB_and_private_config_copied": False,
    },
    "prepared_not_executed": {
        "native_files": plan["native_test_path_count"],
        "A_owner_packet_files": len(plan["owner_packet_extra_inputs"]),
        "total_file_inputs": plan["test_input_path_count_including_owner_packets"],
        "lint_Python_paths": len(actual_lint),
        "group_path_counts": plan["group_path_counts"],
        "actual_new_native_files_vs5e": sorted(set(actual_flat) - flat_old),
        "actual_parametrized_JUnit_cases": "UNRUN",
        "global_gates": "UNRUN",
        "planning_output_root_exists": planning_root.exists(),
        "no_owner_packet_materialization": True,
    },
    "source_scope": {
        "foreign_A_B_C_D_Core_IR_shared_schema_baseline_edits": False,
        "dependency_ancestry": ancestry,
        "G_remote_freshness": (
            "existing parent-provided last fetch plus current tracking/an"
            "cestry; no fetch or remote mutation in this read-only review"
        ),
    },
    "P37": (
        "Exact source/read-only input denominator, canonical caller o"
        "bject routes and support quantities retain frozen basis; met"
        "adata and numerical result remain separate. Unknown multi-in"
        "put law nominal diagnostic remains allowed, stochastic claim"
        "s withheld. Current prepare is not an execution receipt."
    ),
    "P40": (
        "Single harness parent admission includes full job set and se"
        "cond guard; canonical facade repairs actual owned import sea"
        "ms; collector role admission covers complete public roles/fu"
        "ll source components. Exact independent negative/removal con"
        "trols are reused only for unchanged reviewed source."
    ),
    "P41": (
        "Actual5e first attempt remains1086PASS/3FAIL/351ERROR. Previ"
        "ous red cause/old fullguard replay not_established; no inher"
        "ited failure waiver and no new common-wave PASS in this revi"
        "ew."
    ),
    "boundaries": {
        "held": ["B194", "B197", "B201", "B202"],
        "B198": "historical closed regression retained; no falsifier measured here",
        "partial_open": "preserved current ledger, no automatic reclassification",
        "A": (
            "default configured ForecastOwner/strict CAS independent veri"
            "fier/fresh served read and named S6/tier reason seam remain "
            "A-owned; prior8486 positives not current5ePASS"
        ),
        "D": (
            "actual Search sensitivity codec/default proposal-ranking con"
            "sumer remains bridge_missing/consumer_missing; E producer do"
            "es not ratify D codec"
        ),
        "Core_IR_execute": (
            "owner facade/wire packets unratified and no baseline/admission exception applied"
        ),
        "G": (
            "canonical generator/source schema/OpenAPI client compatibili"
            "ty and production history/source law local checks remain sep"
            "arate owner actions"
        ),
    },
    "negative_controls": negative_controls,
    "next_owners": [
        (
            "Root publishes exact moderate review/index append-only, then"
            " freezes distinct candidate and executes corrected common wa"
            "ve once"
        ),
        (
            "CAL independently recomputes actual frozen wave inputs/check"
            "/JUnit/staged UNRUN/source custody without own CAL source ap"
            "proval"
        ),
        (
            "PCL all54 criteria and DDM closeout; G integration/source/lo"
            "cal production checks separate"
        ),
        ("A/D/Core/IR/generator owners resolve concrete unapplied consumer/authority seams"),
    ],
    "finding_closure": False,
    "numerical_or_global_wave_launched": False,
    "command": {
        "argv": [sys.executable, str(Path(__file__).resolve())],
        "cwd": str(ROOT),
        "environment": {"UV_NO_SYNC": "1", "PYTHONDONTWRITEBYTECODE": "1"},
        "exit_code": 0,
        "complete_stdout": "review.stdout.txt",
        "complete_stderr": "review.stderr.txt",
    },
    "initial_auditor_error": (
        "Non-deciding initial parse expected all facades as top-level"
        " inventory packages; Foundry uncertainty is an explicit nest"
        "ed public entrypoint. Full initial script/stdout/stderr pres"
        "erved; corrected parser joins parent owner/classification an"
        "d actual entrypoint exports."
    ),
    "environment": {
        "python": sys.executable,
        "version": sys.version,
        "platform": platform.platform(),
        "UV_NO_SYNC": os.getenv("UV_NO_SYNC"),
        "PYTHONDONTWRITEBYTECODE": os.getenv("PYTHONDONTWRITEBYTECODE"),
        "numeric_imports": False,
        "caps": {key: os.getenv(key) for key in namespace["CAP_VARIABLES"]},
    },
    "cleanup": {
        "performed": "none",
        "native_Trash": "not established; preserve all exact receipts and scripts",
        "future_repeatable_candidate": str(planning_root),
        "candidate_exists": False,
        "permanent_delete": False,
    },
}
write("independent-assembly-review-94d3.json", review)
_write_stdout(
    json.dumps(
        {
            "disposition": review["disposition"],
            "candidate": CANDIDATE,
            "tree": TREE,
            "diff_paths": len(diff),
            "operational_paths": len(operational),
            "indices": len(verified_indices),
            "native_files": plan["native_test_path_count"],
            "owner_packet_files": len(plan["owner_packet_extra_inputs"]),
            "lint_paths": len(actual_lint),
            "negative_controls": len(negative_controls),
            "source_immutable": before == after,
        },
        indent=2,
    )
)
