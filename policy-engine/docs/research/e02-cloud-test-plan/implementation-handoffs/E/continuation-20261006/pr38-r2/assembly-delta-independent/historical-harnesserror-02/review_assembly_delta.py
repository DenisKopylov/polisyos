"""Read-only Git assembly joins; never import product code or execute a wave."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import platform
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

BASE = "c79de1a8779482cf485317039fe12e3570ae2273"
FINAL = "d43f8d4693767637424da759ae960f7b51736449"
FINAL_TREE = "6d38589b1b21a40ca64796cd018f766646099f7e"
DOE = "70c4a14fc872f5ef66437d958ba63884ecdda168"
META = "25ab29c0f527c90f4281a4cf04256acb8f62f051"
HARNESS = "4758d495abb81aa51fea8e28cd071ca9ff989155"
G53 = "53b309019913b938909d6dc0fc13f8edb409f368"
PREFIX = "policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/E/continuation-20261006/pr38-r2/"
AUTHOR = "policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/E/doe-runtime-admission-20261006"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    repo, out = args.repo.resolve(), args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)

    def git(*argv: str) -> bytes:
        return subprocess.check_output(["git", "-C", str(repo), *argv])

    def text(*argv: str) -> str:
        return git(*argv).decode().strip()

    trees: dict[str, dict[str, str]] = {}
    contents: dict[str, bytes] = {}

    def tree(sha: str) -> dict[str, str]:
        if sha not in trees:
            entries = git("ls-tree", "-r", "-z", sha).split(b"\0")
            trees[sha] = {
                row.split(b"\t", 1)[1].decode(): row.split(b"\t", 1)[0].split()[2].decode()
                for row in entries if row and row.split(b"\t", 1)[0].split()[1] == b"blob"
            }
        return trees[sha]

    def blob(sha: str, path: str) -> bytes:
        oid = tree(sha)[path]
        if oid not in contents:
            contents[oid] = git("cat-file", "blob", oid)
        return contents[oid]

    def asset(sha: str, path: str) -> dict[str, object]:
        value = blob(sha, path)
        return {"path": path, "git_blob": tree(sha)[path], "bytes": len(value), "sha256": hashlib.sha256(value).hexdigest()}

    def load(path: str) -> dict[str, object]:
        return json.loads(blob(FINAL, path))

    def diff(a: str, b: str, *paths: str) -> list[tuple[str, str]]:
        lines = text("diff", "--name-status", "--no-renames", a, b, "--", *paths).splitlines()
        return [tuple(line.split("\t", 1)) for line in lines if line]

    def save(name: str, value: object) -> None:
        data = value if isinstance(value, bytes) else (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode()
        with (out / name).open("xb") as stream:
            stream.write(data)

    observed_head_start = text("rev-parse", "HEAD")
    observed_status_start = text("status", "--porcelain", "--untracked-files=no")
    assert observed_head_start == FINAL and not observed_status_start
    assert text("rev-parse", FINAL + "^{tree}") == FINAL_TREE
    assert subprocess.run(["git", "-C", str(repo), "merge-base", "--is-ancestor", BASE, FINAL], check=False).returncode == 0

    old_path = PREFIX + "assembly-independent/assembly-dependency-review-c79.json"
    old = load(old_path)
    assert old["candidate"] == BASE and old["scope_decision"].startswith("GO")
    assert asset(FINAL, old_path)["sha256"] == "3c4e7a931a9fe76129f3d783106a2092e8655af3ce49ef68c00461115e28ae97"
    doe_path = PREFIX + "doe-budget-independent/doe-budget-independent-review-70c4.json"
    doe = load(doe_path)
    assert doe["source"] == DOE and doe["verdict"] == "GO_bounded_runtime_plan_admission" and not doe["blocking_findings"]
    harness_path = PREFIX + "harness-independent/review.json"
    harness = load(harness_path)
    assert harness["candidate"] == HARNESS and harness["verdict"].startswith("GO")
    release_path = PREFIX + "release-compatibility-independent/receipt.json"
    release = load(release_path)
    assert release["source_sha"] == META and release["code_verdict"].startswith("GO")

    doe_paths = {row["path"] for row in doe["immutable_footprint"]}
    metadata_paths = set(release["source_footprint"])
    harness_paths = {PREFIX + "wave-controls/" + name for name in ("README.md", "plan_wave.py", "run_check.py", "uncapped_umbrella.py")}
    replacements = dict.fromkeys(doe_paths, "independent CAL DoE70c runtime-admission GO")
    replacements.update(dict.fromkeys(metadata_paths, "canonical-owner release metadata25ab independent GO"))
    replacements.update(dict.fromkeys(harness_paths, "independent DoE harness4758/b7c GO"))

    source_joins = []
    for row in doe["immutable_footprint"]:
        current = asset(FINAL, row["path"])
        assert current["git_blob"] == row["git_blob"] and current["sha256"] == row["sha256"] and current["bytes"] == row["bytes"]
        assert tree(DOE)[row["path"]] == current["git_blob"]
        source_joins.append({"owner": "DoE author; independent CAL reviewer", "review_source": DOE, "review": doe_path, **current})
    for path in sorted(metadata_paths):
        assert tree(META)[path] == tree(FINAL)[path]
        selected = PREFIX + "release-compatibility-independent/selected-fragments/" + Path(path).name
        assert blob(FINAL, selected) == blob(FINAL, path)
        source_joins.append({"owner": "canonical team-scientist/team-polisyos and team-architecture per selected row", "review_source": META, "review": release_path, **asset(FINAL, path)})
    for path in sorted(harness_paths):
        assert tree(HARNESS)[path] == tree(FINAL)[path]
        source_joins.append({"owner": "root/FRC writers; independent DoE harness reviewer", "review_source": HARNESS, "review": harness_path, **asset(FINAL, path)})
    for path, row in harness["source_inputs"].items():
        if path.startswith(str(repo) + "/"):
            path = path.removeprefix(str(repo) + "/")
        if not path.startswith("policy-engine/"):
            path = "policy-engine/" + path
        if path not in tree(FINAL):
            # Independently reviewed proposal/original group files were originally scratch inputs.
            path = PREFIX + "wave-controls/" + Path(path).name
        current = asset(FINAL, path)
        assert current["sha256"] == row["sha256"] and current["bytes"] == row["bytes"]
        source_joins.append({"owner": "unchanged configured harness dependency", "review": harness_path, **current})
    for name in ("plan_wave.py", "run_check.py", "uncapped_umbrella.py"):
        assert blob(FINAL, PREFIX + "harness-author-v2/" + name) == blob(FINAL, PREFIX + "wave-controls/" + name)

    prior_review_joins = []
    for family, row in old["reviews"].items():
        current = asset(FINAL, row["path"])
        assert current["sha256"] == row["sha256"] and current["bytes"] == row["bytes"]
        prior_review_joins.append({"family": family, "basis": "attributed independent receipt unchanged; no new family test/review claim", **current})
    prior_operational_joins = []
    for path, owner in old["footprint"]["coverage"].items():
        equal = tree(BASE).get(path) == tree(FINAL).get(path)
        assert equal or path in replacements
        prior_operational_joins.append({"path": path, "previous_owner": owner, "prior_blob": tree(BASE).get(path), "final_blob": tree(FINAL).get(path), "equal": equal, "basis": "prior independent assembly/review retained" if equal else replacements[path]})

    full_old = PREFIX + "assembly-independent/full-committed-footprint.tsv"
    old_rows = [line.split("\t", 1) for line in blob(FINAL, full_old).decode().splitlines()[1:] if line]
    assert len(old_rows) == old["footprint"]["full_paths"] == 929
    assert asset(FINAL, full_old)["sha256"] == old["footprint"]["full_footprint_sha256"]
    old_footprint_delta = [path for _, path in old_rows if tree(BASE).get(path) != tree(FINAL).get(path)]
    delta = diff(BASE, FINAL)
    assert set(old_footprint_delta) <= {path for _, path in delta}

    portable_joins = []
    indexed_paths: set[str] = set()
    packet_names = ("assembly-independent", "harness-author-v2", "harness-independent", "readiness-b97", "release-compatibility-author", "release-compatibility-independent", "doe-budget-independent")
    for name in packet_names:
        index_path = PREFIX + name + "/portable-copy-index.json"
        index = load(index_path)
        records = index["records"]
        for row in records:
            current = asset(FINAL, row["copied_path"])
            assert current["sha256"] == row["sha256"] and current["bytes"] == row["bytes"]
            indexed_paths.add(row["copied_path"])
        if "total_files" in index:
            assert len(records) == index["total_files"]
        if "total_bytes" in index:
            assert sum(row["bytes"] for row in records) == index["total_bytes"]
        portable_joins.append({**asset(FINAL, index_path), "records": len(records), "all_Git_bytes_match": True})
        indexed_paths.add(index_path)
    author_index_path = AUTHOR + "/evidence-index.json"
    author_index = load(author_index_path)
    for name, row in author_index.items():
        current = asset(FINAL, AUTHOR + "/" + name)
        assert current["sha256"] == row["sha256"] and current["bytes"] == row["size_bytes"]
        indexed_paths.add(current["path"])
    indexed_paths.add(author_index_path)
    portable_joins.append({**asset(FINAL, author_index_path), "records": len(author_index), "all_Git_bytes_match": True})
    author_receipt_path = AUTHOR + ".json"
    author = load(author_receipt_path)
    assert author["candidate_sha"] == DOE and author["candidate_tree"] == text("rev-parse", DOE + "^{tree}")
    assert author["independent_review_refs"]["sha256"] == asset(FINAL, doe_path)["sha256"]
    indexed_paths.add(author_receipt_path)

    groups = {name: list(paths) for name, paths in load(PREFIX + "wave-controls/original-wave-groups.json")["groups"].items()}
    proposal = load(PREFIX + "wave-controls/proposal.json")
    original_set = {path for paths in groups.values() for path in paths}
    for name, paths in proposal["required_additions"].items():
        groups.setdefault(name, [])
        groups[name].extend(path for path in paths if path not in groups[name])
    # Execute only the reviewed pure string-classifier AST. No product import, planner, backend or test launch.
    plan_ast = ast.parse(blob(FINAL, PREFIX + "wave-controls/plan_wave.py"))
    classifier = next(node for node in plan_ast.body if isinstance(node, ast.FunctionDef) and node.name == "family_for")
    namespace: dict[str, object] = {}
    exec(compile(ast.Module(body=[classifier], type_ignores=[]), "<Git-pinned-pure-family-classifier>", "exec"), namespace)
    unassigned = []
    for status, path in diff(proposal["delta_selection_base"], FINAL, "policy-engine/tests"):
        if status == "D":
            continue
        name = namespace["family_for"](path)
        if name and path not in groups[name]:
            groups[name].append(path)
        elif name is None and path != "policy-engine/tests/unit/runtime/http/test_control_plane_store.py":
            unassigned.append(path)
    flat = [path for paths in groups.values() for path in paths]
    assert len(flat) == len(set(flat)) == 121 and original_set <= set(flat)
    assert not unassigned and all(path in tree(FINAL) for path in flat)
    new_test = "policy-engine/tests/unit/scientist/methods/doe/test_plan_runtime_admission.py"
    assert new_test in groups["DOE_SALib_and_consumer_factory"]
    owner_packet_paths = ["policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/E/frc-source-measurement-r2/" + name for name in ("a-cas-contract-tests.py.txt", "a-status-reason-tests.py.txt")]
    assert all(path in tree(FINAL) and tree(BASE)[path] == tree(FINAL)[path] for path in owner_packet_paths)
    lint_paths = [path for status, path in diff(proposal["default_comparison_base"], FINAL, "policy-engine") if status != "D" and path.endswith(".py") and path in tree(FINAL)]

    def category(path: str) -> str:
        if path in doe_paths:
            return "reviewed DoE70c mechanism/test/paired companion"
        if path in metadata_paths:
            return "reviewed six canonical release metadata25ab"
        if path in harness_paths:
            return "reviewed primary operational harness4758"
        if path.startswith(AUTHOR):
            return "DoE author bounded evidence; errors/history retained"
        if path.startswith(PREFIX):
            for name in packet_names:
                if path.startswith(PREFIX + name + "/"):
                    return "indexed " + name + " evidence" + ("; executable witness, not product caller" if path.endswith((".py", ".cjs", ".py.txt")) else "")
        if path.startswith("policy-engine/docs/research/e02-cloud-test-plan/integration/"):
            return "G53 integration audit/evidence only; B/E owners separate"
        return "UNREVIEWED"

    footprint = []
    for status, path in delta:
        cat = category(path)
        assert cat != "UNREVIEWED", path
        assert path in indexed_paths or path in replacements or path.startswith("policy-engine/docs/research/e02-cloud-test-plan/integration/"), path
        footprint.append({"status": status, **asset(FINAL, path), "base_blob": tree(BASE).get(path), "category": cat})
    product_delta = diff(BASE, FINAL, "policy-engine/src", "policy-engine/tests", "policy-engine/schemas", "policy-engine/architecture")
    assert {path for _, path in product_delta} == {path for path in doe_paths if path.startswith(("policy-engine/src/", "policy-engine/tests/"))}
    runtime_paths = [path for _, path in product_delta if path.startswith("policy-engine/src/") and path.endswith(".py")]
    assert len(runtime_paths) == 7
    g53_delta = diff(G53 + "^", G53)
    assert all(path.startswith("policy-engine/docs/") for _, path in g53_delta)
    no_shared_edits = not diff(BASE, FINAL, "policy-engine/src/polisyos/runtime", "policy-engine/src/polisyos/core", "policy-engine/src/polisyos/ir", "policy-engine/schemas", "policy-engine/architecture", "policy-engine/pyproject.toml", "policy-engine/uv.lock", "policy-engine/pnpm-lock.yaml", "policy-engine/pytest.ini", "policy-engine/ruff.toml")
    assert no_shared_edits
    ledger_paths = ("policy-engine/docs/research/e02-cloud-test-plan/results", "policy-engine/docs/research/e02-cloud-test-plan/closure-decisions", "policy-engine/docs/research/e02-cloud-test-plan/execution-organization")
    assert not diff(BASE, FINAL, *ledger_paths)

    negatives = []
    def admit_join(actual: dict[str, object], expected: dict[str, object]) -> bool:
        return all(key in actual and actual[key] == expected[key] for key in ("git_blob", "sha256", "bytes"))
    positive = asset(FINAL, "policy-engine/src/polisyos/scientist/methods/doe/sampling.py")
    assert admit_join(positive, positive)
    fake = dict(positive, git_blob=tree(BASE)[positive["path"]])
    assert not admit_join(fake, positive)
    negatives.append({"name": "same path/name retained, substitute old unguarded DoE blob", "outcome": "REFUSED", "scope": "static source-custody predicate; native marker-removal control is independently attributed to CAL70c"})
    fake = dict(positive)
    fake.pop("sha256")
    assert not admit_join(fake, positive)
    negatives.append({"name": "retain source identity marker but remove defining SHA256 field", "outcome": "REFUSED", "scope": "static custody predicate"})
    required_companions = {doe_path, release_path, harness_path, old_path}
    for removed in required_companions:
        observed = required_companions - {removed}
        assert not required_companions <= observed
        negatives.append({"name": "present source but remove required primary review companion", "removed": removed, "outcome": "REFUSED", "scope": "assembly completeness predicate"})

    observed_head_end = text("rev-parse", "HEAD")
    observed_status_end = text("status", "--porcelain", "--untracked-files=no")
    assert observed_head_end == observed_head_start == FINAL and observed_status_end == observed_status_start == ""
    tsv = "status\tpath\tbase_blob\tfinal_blob\tsha256\tbytes\tcategory\n" + "".join("\t".join(str(row.get(key) or "") for key in ("status", "path", "base_blob", "git_blob", "sha256", "bytes", "category")) + "\n" for row in footprint)
    save("full-c79-to-d43-footprint.tsv", tsv.encode())
    save("prior-assembly-review-c79.original.json", blob(FINAL, old_path))
    save("doe-budget-independent-review-70c4.original.json", blob(FINAL, doe_path))
    save("harness-independent-review-4758.original.json", blob(FINAL, harness_path))
    save("release-independent-receipt-25ab.original.json", blob(FINAL, release_path))
    save("DOE-author-receipt-70c4.original.json", blob(FINAL, author_receipt_path))

    operational_import_delta = []
    for path in runtime_paths:
        def imports(source: bytes) -> list[str]:
            return sorted(ast.dump(node, include_attributes=False) for node in ast.walk(ast.parse(source)) if isinstance(node, (ast.Import, ast.ImportFrom)))
        before, after = imports(blob(BASE, path)), imports(blob(FINAL, path))
        operational_import_delta.append({"path": path, "added_AST_imports": sorted(set(after) - set(before)), "removed_AST_imports": sorted(set(before) - set(after)), "owner": "same DoE package; shared private constructor-admission helper independently reviewed at70c; no foreign facade added"})
    report = {
        "schema": "policyos.e02.independent_assembly_delta_review.v1",
        "state": "READY", "reviewer": "root/backtest_r3; independent assembly joins only; own BKT/Welfare judgments attributed to existing independent DDM/CAL receipts",
        "mode": "read-only Git/source AST/receipt reconciliation; scratch output only; no product imports, numerical tests, broad checks, environment/worktree creation or source writes",
        "base": BASE, "base_tree": text("rev-parse", BASE + "^{tree}"), "candidate": FINAL, "tree": FINAL_TREE,
        "observed_head_start": observed_head_start, "observed_head_end": observed_head_end, "working_status_start": observed_status_start, "working_status_end": observed_status_end,
        "verdict": "GO_bounded_assembly_delta_and_source_dependency_joins", "blocking_unreviewed_product_delta": [],
        "prior_assembly": asset(FINAL, old_path), "prior_full_footprint": asset(FINAL, full_old), "prior_929_paths_reconciled": True, "prior_footprint_paths_changed_again": old_footprint_delta,
        "delta_footprint": {"paths": len(footprint), "statuses": dict(Counter(row["status"] for row in footprint)), "categories": dict(Counter(row["category"] for row in footprint)), "file": "full-c79-to-d43-footprint.tsv", "sha256": hashlib.sha256(tsv.encode()).hexdigest(), "bytes": len(tsv.encode()), "all_paths_assigned": True, "docs_executable_witnesses_counted": sum(row["path"].startswith("policy-engine/docs/") and row["path"].endswith(".py") for row in footprint)},
        "prior_operational_joins": prior_operational_joins, "prior_independent_review_joins": prior_review_joins, "new_reviewed_source_joins": source_joins,
        "portable_companion_joins": portable_joins, "all_primary_review_companions_committed": True,
        "product_delta": {"full_paths": product_delta, "runtime_Python_files": len(runtime_paths), "new_native_test_files": 1, "source_README": 1, "new_release_companion": 1, "source_all_exact70c": True, "schemas_API_inventory_environment_lockfiles_unchanged": no_shared_edits},
        "operational_import_delta": operational_import_delta,
        "new_DoE_judgment": {"receipt": asset(FINAL, doe_path), "source": DOE, "source_tree": doe["tree"], "independent_reviewer": doe["reviewer"], "code_verdict": doe["verdict"], "native_checks_at_original_source": doe["independent_checks"], "P37": doe["P37"], "P40": doe["P40"], "P41": doe["P41"], "new_checks_by_this_review": False, "old_unchanged_algorithm_oracle_reuse": "Earlier f07 whole-block/Morris geometry receipts retained only for unchanged portions;70c changed admission has its own CAL witness, no inherited PASS transfer."},
        "harness_judgment": {"source": HARNESS, "publication": "b7c00a45ce5b86ae2e0aff6d65fe4774facec71f", "receipt": asset(FINAL, harness_path), "all_source_inputs_byte_exact": True, "author_copies_equal_primary_harness": True, "meaning": "Scratch-admission/options/JUnit/canonical stage planning GO only; browser readiness is not browser-suite/global CI PASS; initial validator and docs-count harness errors remain indexed."},
        "canonical_metadata_judgment": {"source": META, "receipt": asset(FINAL, release_path), "six_rows_equal_reviewed_Git_and_selected_copies": True, "current_exports": release["current_export_counts"], "DDM_v1_v2_code_reuse": release["DDM_reuse"], "owner_predicate": "Canonical owners/classification/version ownership from tracked G53/contract; nonempty owner E generic-parser PASS does not meet canonical-owner predicate.", "no_new_parser_or_family_run": True},
        "G53": {"sha": G53, "delta_paths": len(g53_delta), "all_docs_only": True, "meaning": "G audit and owner-action evidence retained as exact historical claims; no B/D/A/IR runtime implementation or E production authority imported."},
        "dependency_joins": {"old_join_basis": old["dependency_joins"], "unchanged_BKT_Welfare": "Independent DDM0983 and CAL884 receipts/blobs unchanged; this author does not self-review these mechanisms.", "new_DoE": "Single existing SensitivityPlan constructor predicate reused before every owned materializer; captured plan drives native design/identity/CAS. No public/schema/foreign owner edge introduced.", "paired_metadata": "Canonical29Calibration/public_experimental team-scientist;20Foundryuncertainty/public_stable team-polisyos;version owner team-architecture. DDM17 internal unchanged; explicit persisted v1/v2 migration owned team-scientist.", "default_Search": "DOE artifact-to-D DefaultSearch proposal-ranking consumer remains consumer_missing/bridge_missing; D codec/signoff cannot be supplied by E metadata.", "FRC_A": "A CYC-01→FRC-01 and EMP-01→FRC-02 lifecycle/verifier/fresh served read remain A-owned; source measurements never grant causal/policy authority.", "Core_IR_execute": "Unratified owner-entrypoint and wire semantic packets unchanged; no deep-edge/admission waiver inferred from reexport identity."},
        "final_static_input_denominators": {"native_test_files": len(flat), "owner_packet_files": len(owner_packet_paths), "total_test_file_inputs": len(flat) + len(owner_packet_paths), "groups": {name: len(paths) for name, paths in groups.items()}, "old110_paths_preserved": True, "new_DoE_admission_test_in_actual_family": True, "required_upstream": {name: {"sha": sha, "in_history": subprocess.run(["git", "-C", str(repo), "merge-base", "--is-ancestor", sha, FINAL], check=False).returncode == 0} for name, sha in proposal["required_upstream"].items()}, "changed_python_from_original198_base": len(lint_paths), "changed_docs_python_from_original198_base": sum(path.startswith("policy-engine/docs/") for path in lint_paths), "runtime_parametrized_case_count": "UNRUN; actual JUnit only", "global_outcomes": "UNRUN; no historical count/PASS transferred to finalcandidate; final planner must recompute after receipt-only freeze publication"},
        "negative_controls": negatives,
        "initial_harness_error": {"path": "historical-harnesserror-01", "meaning": "Metadata adapter initially expected a list for source_inputs but the original harness receipt stores a path-keyed dict. Initial TypeError/script/stdout/stderr retained; corrected adapter does not change any input/source/property."},
        "predicate_basis": "independently_reconciled Git blob, exact primary independent review and consumer/source/companion joins; no institutional decision supplied",
        "finding_ledger": {"ledger_results_ownership_files_unchanged": True, "held": ["B194", "B197", "B201", "B202"], "B198": "historic closed retained as regression; no new falsifier of closure measured here", "other_statuses": "Historical partial/open retained. Code assembly GO and check PASS/FAIL/UNRUN do not close findings or replace original criterion-specific adjudication.", "54_findings_22_bundles": "No collective closure vote"},
        "remaining_checks_and_owners": {"E_root": "Freeze one clean exact descendant with this moderate receipt, refresh actual plan/input denominator and run one common numerical/global wave; true fail-fast successors UNRUN; no repeat unchanged family checks.", "D": "DoE persisted artifact/threshold/statistic/units/denominator→DefaultSearch ranking consumer implementation/readback.", "A": "Default FRC bridge/lifecycle independently recomputed verifier and fresh served status/reason checks.", "IR_semantic_owner": "Ratify distinct v2 point/interval/source-law carrier choices; B201/B202 held until decisions; preserve v1.1 replay.", "Calibration_runtime_owner": "B194/B197 exact served evaluator/source-law/profile/calibrator authority remains held notwithstanding generic native consumer witnesses.", "Core_IR_Foundry_API_owners": "Explicit foreign canonical entrypoint admission and version rollout are owner decisions; reexports do not ratify them.", "G": "Code integration acceptance and individual original-criterion closure separately; local read-only exact-production/source-law checks only when criterion requires, no generic-fixture deferral or synthetic production claim."},
        "environment": {"python": sys.version, "executable": sys.executable, "platform": platform.platform(), "cwd": os.getcwd(), "product_backend": "NOT_INITIALIZED; only stdlib+Git", "no_caps_added": True, "new_environment_or_worktree": False},
        "exact_command": {"argv": [sys.executable, *sys.argv], "cwd": os.getcwd(), "environment": {name: os.environ.get(name) for name in ("PYTHONDONTWRITEBYTECODE", "UV_NO_SYNC", "UV_PROJECT_ENVIRONMENT")}},
        "cleanup": {"permanent_deletion": False, "native_trash_operation": False, "preserve": "all source/docs/deciding original receipts and exported evidence", "new_repeatable_test_environment_candidates": [], "shared_active_environment": "/workspace/e02-E-continuation-20261006/policy-engine/.venv"},
        "reviewed_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    save("assembly-delta-review-d43.json", report)
    save("receipt.json", {"schema": "policyos.e02.independent_assembly_delta_receipt.v1", "state": "READY", "unit": "E", "base": BASE, "candidate": FINAL, "tree": FINAL_TREE, "verdict": report["verdict"], "property": "Complete c79→d43 footprint and exact prior/new source, operational dependency and primary companion joins; independently reviewed changed mechanism required", "predicate_basis": report["predicate_basis"], "reviewer": report["reviewer"], "primary_review": "assembly-delta-review-d43.json", "script": "review_assembly_delta.py", "stdout": "review.stdout", "index": "copy-index.json", "exact_command": report["exact_command"], "environment": report["environment"], "input": {"Git": FINAL, "base": BASE, "prior_assembly": old_path, "DOE_source": DOE, "DOE_review": doe_path, "harness_source": HARNESS, "harness_review": harness_path, "metadata_source": META, "metadata_review": release_path}, "outcome": "PASS_static_assembly_join_only", "no_numeric_or_global_check_launched": True, "closure_ratified": False, "remaining_checks_and_owners": report["remaining_checks_and_owners"], "cleanup": report["cleanup"]})
    print(json.dumps({"state": "READY", "candidate": FINAL, "tree": FINAL_TREE, "delta_paths": len(footprint), "prior_operational_joins": len(prior_operational_joins), "source_dependency_joins": len(source_joins), "portable_records": sum(row["records"] for row in portable_joins), "native_files": len(flat), "packet_files": len(owner_packet_paths), "new_numeric_runs": 0, "new_global_runs": 0, "verdict": report["verdict"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
