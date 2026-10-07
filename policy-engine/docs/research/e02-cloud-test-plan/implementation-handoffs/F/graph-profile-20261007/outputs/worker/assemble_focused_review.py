"""Assemble immutable focused execution evidence; never run a scientific test.

The test bodies/reader/control program remain in pinned Git. Their exact bytes
and reconstructible program digest are bound here without copying product code.
"""
from __future__ import annotations

import argparse
import ast
import gzip
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile
import xml.etree.ElementTree as ET

D = Path(__file__).resolve().parent
OLD = D / "frozen-4ee-native"
N = OLD / "wait4-replay"
REPO = Path("/workspace/e02-F-closeout-20261006")
SHA = "4ee2f2a4f1d9c4d42c6e5ec7f85f973e07358f0d"
TREE = "551d4e760dc1168f6ad8182c9b176f00e94a2281"
TEST = "policy-engine/tests/unit/foundry/methods/catalog/causal/test_dowhy_worker.py"


def digest(raw: bytes) -> dict:
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def binding(path: Path) -> dict:
    return {"path": str(path), **digest(path.read_bytes())}


def load(path: Path) -> dict:
    return json.loads(path.read_bytes())


def put(path: Path, obj: dict) -> None:
    assert not path.exists(), f"Refusing to replace frozen output: {path}"
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n")


def git_bytes(path: str) -> bytes:
    return subprocess.check_output(["git", "show", f"{SHA}:{path}"], cwd=REPO)


def git_body_contract() -> dict:
    raw = git_bytes(TEST)
    text = raw.decode("utf-8")
    lines = text.splitlines(keepends=True)
    parsed = ast.parse(text)
    functions = {node.name: node for node in parsed.body if isinstance(node, ast.FunctionDef)}

    def function(name: str) -> dict:
        node = functions[name]
        exact = "".join(lines[node.lineno - 1:node.end_lineno]).encode()
        return {"git_ref": SHA, "path": TEST, "name": name,
                "start_line": node.lineno, "end_line": node.end_lineno,
                "exact_function_source": digest(exact)}

    point_name = "test_real_estimate_point_only_survives_parent_cas_and_reader"
    point = functions[point_name]
    calls = [n for n in ast.walk(point) if isinstance(n, ast.Call)
             and isinstance(n.func, ast.Name) and n.func.id == "instrument_actual_worker"]
    assert len(calls) == 1
    mutation = ast.literal_eval(calls[0].args[1])
    helper = functions["instrument_actual_worker"]
    assignments = {n.targets[0].id: n.value for n in helper.body
                   if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name)}
    prefix = ast.literal_eval(assignments["prefix"])
    program_expr = assignments["program"]
    assert isinstance(program_expr, ast.BinOp)
    suffix = ast.literal_eval(program_expr.right)
    program = (prefix + mutation + suffix).encode()
    reader_node = next(n for n in functions["test_real_worker_job_cas_fresh_python314_reader"].body
                       if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name)
                       and n.targets[0].id == "reader")
    reader = ast.literal_eval(reader_node.value).encode()
    return {
        "whole_test_git_ref": SHA, "whole_test_path": TEST,
        "whole_test": digest(raw),
        "defining_functions": [function(name) for name in [
            "dgp", "test_public_complete_report_builder_abi_and_real_producer_invocation",
            "test_real_worker_job_cas_fresh_python314_reader", point_name,
            "instrument_actual_worker"]],
        "fresh_reader_program": digest(reader),
        "controlled_point_only_program": digest(program),
        "controlled_point_only_mutation_literal": digest(mutation.encode()),
        "program_custody": "Reconstructed deterministically from the exact pinned maintained test body, not separately intercepted process argv. Complete body is reachable by Git ref/path; this assembler reconstructs both program hashes without executing them.",
        "point_only_scope": "CausalModel.estimate_effect executes the genuine original numerical fit. Only the actual returned estimate's confidence-interval and standard-error getters are then controlled to return None. This is a post-fit inference-unavailability negative, not a naturally returned point-only backend positive."
    }


def native_archive() -> dict:
    root = N / "frozen-native-cas"
    paths = sorted(p for p in root.rglob("*") if p.is_file()
                   and (p.name.endswith(".blob") or p.name.endswith(".manifest.json")))
    assert paths
    rows = []
    output = D / "synthetic-native-cas.tar.gz"
    assert not output.exists()
    with output.open("wb") as target:
        with gzip.GzipFile(filename="", fileobj=target, mode="wb", mtime=0) as gz:
            with tarfile.open(fileobj=gz, mode="w|") as tf:
                for path in paths:
                    raw = path.read_bytes()
                    relative = path.relative_to(root).as_posix()
                    rows.append({"original_path": str(path), "archive_path": relative, **digest(raw)})
                    info = tarfile.TarInfo(relative)
                    info.size, info.mode, info.mtime = len(raw), 0o644, 0
                    tf.addfile(info, io.BytesIO(raw))
    return {"archive": binding(output), "files": rows,
            "scope": "Complete actual synthetic inputs/report/evidence CAS blobs and manifests from the three executed tests. No copied tracked source, production data, locks or font cache. Original scratch files remain intact."}


def assemble() -> None:
    native = load(N / "frozen-native.receipt.json")
    spec = load(N / "frozen-native.spec.json")
    assert native["candidate_sha"] == spec["candidate_sha"] == SHA
    assert native["candidate_tree_sha"] == spec["candidate_tree_sha"] == TREE
    assert native["exit_code"] == 0 and native["junit_counts"] == {
        "tests": 3, "failures": 0, "errors": 0, "skips": 0, "passes": 3}
    assert spec["start_guard"] == native["end_guard"]
    assert len(native["end_guard"]["complete_guard_path_set"]) == 12
    for row in native["end_guard"]["complete_guard_path_set"]:
        assert digest(git_bytes(row["path"])) == {"bytes": row["bytes"], "sha256": row["sha256"]}
    cases = list(ET.parse(N / "frozen-native.junit.xml").iter("testcase"))
    assert len(cases) == 3 and all(not list(case) for case in cases)
    stdout = (N / "frozen-native.stdout.txt").read_text()
    assert "3 passed, 1 warning" in stdout and "PytestConfigWarning: Unknown config option: cache_dir" in stdout
    contracts = git_body_contract()
    put(D / "synthetic-native-cas-bindings.json", native_archive())
    put(D / "initial-launch-error-observation.json", {
        "outcome": "ERROR", "exit_code": 1, "scientific_tests_executed": 0,
        "classification": "Scratch timing harness environment limitation: optional /usr/bin/time executable absent; AssertionError occurred before pytest launch. No scientific failure/skip or backend fit was executed in this attempt.",
        "exact_launcher_input": binding(OLD / "launcher-input.json"),
        "stdout": binding(OLD / "launcher.stdout.json"),
        "stderr": binding(OLD / "launcher.stderr.txt"),
        "original_runner": binding(D / "run_frozen_focused_native.py"),
        "forward_correction": binding(D / "wait4-harness-forward.json"),
        "initial_total_wall_and_RSS": "Not recorded as a structured complete subprocess measurement; not inferred from the corrected run."
    })
    selectors = spec["pytest_argv"][4:7]
    assert all("test_dowhy_worker.py::" in selector for selector in selectors)
    report = {
        "schema": "policyos.e02.focused_real_worker_review.v1",
        "unit": "F", "author": "F/fit_tmle read-only leaf", "outcome": "PASS",
        "decision": "GO_BOUNDED", "finding_ids": ["B212", "B213"], "closure_ids": [],
        "candidate_sha": SHA, "candidate_tree_sha": TREE,
        "entry_source_sha": "25cdea9064ddea2c3a812fd68670076bd4b088cb",
        "source_implementation_or_Git_changes_by_this_leaf": False,
        "scope": "Fresh exact-source real configured Python3.12/DoWhy0.14 fit and public factory/MethodJob/CAS/fresh Python3.14 consumer. Three existing selectors executed once. Formal finding closure and whole production authority remain ROOT/G decisions.",
        "specification_verdict": "PASS for the three commissioned bounded properties and current changed reader body.",
        "engineering_verdict": "PASS for the scoped public ABI/content-bound CAS/native worker consumer; no broader quality gate inferred.",
        "native": binding(N / "frozen-native.receipt.json"),
        "spec": binding(N / "frozen-native.spec.json"),
        "native_environment": {"parent": binding(OLD / "parent-versions.stdout.json"),
                               "worker": binding(OLD / "worker-versions.stdout.json"),
                               "backend_module_and_API_preflight": binding(D / "worker-backend.stdout.json")},
        "native_counts": native["junit_counts"],
        "warning": {"count": 1, "type": "PytestConfigWarning", "message": "Unknown config option: cache_dir", "cause": "Existing pytest cache_dir configuration with this read-only run's no:cacheprovider option; full raw warning preserved."},
        "timing": {"wall_seconds": native["wall_seconds"], "pytest_seconds": 20.50,
                   "full_rusage": binding(N / "frozen-native.time.txt"),
                   "scope": "Linux os.wait4 actual pytest child/waited-descendant high-water rusage; no simultaneous cgroup/global budget proof."},
        "source_window": {"guards": "Start/end guard objects exactly equal for attached HEAD/tree, whole tracked-clean check and 12 enumerated source/test/profile inputs. The allowed untracked existing .venv symlink is recorded, preserved and never synchronized.",
                          "start_guard": spec["start_guard"], "end_guard": native["end_guard"]},
        "test_body_and_program_binding": contracts,
        "source_delta": {"complete_patch": binding(D / "old-native-to-25c.full.patch"),
                         "preflight": binding(D / "source-and-backend-preflight.json"),
                         "description": "Only the old423-to-current fresh-reader assertions changed: non-gating reason plus preserved confidence level/CI. The public complete builder test body is unchanged. Seven producer/worker/protocol/profile inputs are byte-equal old423 to entry25c; source equality is not old PASS carry to the changed test."},
        "checks": [
            {"name": "actual isolated worker import/API/version preflight", "outcome": "PASS", "output": "worker-backend.stdout.json", "output_ref": binding(D / "worker-backend.stdout.json"), "execution": binding(D / "worker-backend.execution.json")},
            {"name": "three frozen genuine backend/public consumer selectors", "outcome": "PASS", "output": "frozen-4ee-native/wait4-replay/frozen-native.stdout.txt", "output_ref": binding(N / "frozen-native.stdout.txt"), "execution": binding(N / "frozen-native.receipt.json"), "command": spec["argv"], "cwd": spec["cwd"], "environment_overrides": spec["environment_overrides"]},
            {"name": "complete source guard equality", "outcome": "PASS", "output": "frozen-4ee-native/wait4-replay/frozen-native.receipt.json", "output_ref": binding(N / "frozen-native.receipt.json"), "source_count": 12},
            {"name": "original external-time launcher", "outcome": "ERROR", "output": "frozen-4ee-native/launcher.stderr.txt", "output_ref": binding(OLD / "launcher.stderr.txt"), "scientific_tests_executed": 0, "correction": binding(D / "wait4-harness-forward.json")},
            {"name": "baseline Python3.14 optional DoWhy/EconML positive witness", "outcome": "UNRUN", "output": "frozen-4ee-native/parent-versions.stdout.json", "reason": "DoWhy/EconML excluded/absent in the parent baseline. Genuine DoWhy positive is exclusively the configured separate Python3.12 worker; no shim or markers bypass."},
            {"name": "production identification/admitted study budget", "outcome": "UNRUN", "output": "No production identifying data/graph authority or B56 admitted shared study budget owner packet was supplied or exercised by these tests."}
        ],
        "per_id": [
            {"id": "B212", "criterion": "Point-only effect survives; no fabricated confidence interval or confidence level when supported inference is unavailable.", "bounded_check_outcome": "PASS", "selectors": [selectors[1], selectors[2]], "negative": "Genuine CausalModel fit followed by controlled CI/SE accessor unavailability. Point is retained, status NUMERICAL_FAILURE, interval/level absent, envelope non-gating; actual CAS reopen/worker binding check passes.", "positive": "The genuine native interval profile preserves point/CI/level across persisted result and fresh Python3.14 reader, with gate_eligible false and explicit identification-not-established reason.", "limit": "Controlled post-estimate negative is not a naturally returned point-only backend configuration. No formal authority or admitted-real-data identification conclusion."},
            {"id": "B213", "criterion": "Pass and preserve explicit estimand type, treatment/control contrast and target through identification/estimation and persisted consumer binding.", "bounded_check_outcome": "PASS", "selectors": [selectors[0], selectors[1]], "positive": "Current public factory receives genuine worker result and complete typed projection equality; actual supported nonparametric-ate, 0→1, target ate selected profile is source/request-bound through MethodJob/CAS/fresh reader.", "negative": "Fresh successful worker response with target_units changed to att in parent-observed request payload is refused as binding mismatch.", "limit": "Supported selected nonparametric-ATE profile only. No general NIE/ATT capability, production causal-identification issuer, real-data authority or value-gate admission positive."}
        ],
        "input_completeness": {"original_cards_and_owner_receipts": binding(D / "source-and-backend-preflight.json"),
                               "actual_synthetic_CAS": binding(D / "synthetic-native-cas-bindings.json"),
                               "profile": "Existing deterministic DGP, exact current source fixture/worker profile, actual configured parent/worker environments. No production inputs requested or copied."},
        "limitations": ["Known synthetic DGP and selected finite profile, not admitted real-data inference.", "Fresh-reader child stdout is asserted inside the exact maintained test; it was not separately captured by the outer harness. Complete persisted synthetic CAS and exact reader-program Git binding are retained; no invented external child stream.", "No estimator/cache/fold/coverage rerun, shared study scheduling or resource quota claim.", "No broader global/static/lint/architecture verdict, P41 disjoint proof or formal closure."],
        "sanitation": {"redactions": False, "scope": "Only explicit environment overrides, version/module origins and synthetic local CAS/test streams are selected; inherited secret environment values are not dumped. Local absolute paths are preserved. No credentials/signed request query strings observed in deciding streams."}
    }
    put(D / "focused-real-worker-review.json", report)
    paths = []
    seed = load(D / "preflight-transfer-selection.json")
    for row in seed["files"]:
        path = Path(row["path"])
        assert binding(path) == row
        paths.append(path)
    paths += [D / "preflight-transfer-selection.json", Path(__file__),
              D / "run_frozen_focused_native_wait4.py", D / "wait4-harness-forward.full.diff",
              D / "wait4-harness-forward.stderr.txt", D / "wait4-harness-forward.json",
              D / "initial-launch-error-observation.json", D / "synthetic-native-cas.tar.gz",
              D / "synthetic-native-cas-bindings.json", D / "focused-real-worker-review.json"]
    paths += sorted(p for p in OLD.iterdir() if p.is_file())
    paths += sorted(p for p in N.iterdir() if p.is_file())
    paths = sorted(set(paths))
    rows = [{**binding(path), "relative_path": path.relative_to(D).as_posix()} for path in paths]
    assert len({row["relative_path"] for row in rows}) == len(rows)
    put(D / "focused-real-worker-transfer-selection.json", {
        "schema": "policyos.e02.explicit_transport_selection.v1", "files": rows,
        "source_sha": SHA, "source_tree_sha": TREE, "pending_inputs": [],
        "complete_file_count": len(rows), "complete_file_bytes": sum(row["bytes"] for row in rows),
        "scope": "Complete preflight/initial harness ERROR/forward correction/current native outputs and synthetic CAS. No copied tracked source or recursive selection self-binding. Root owns committed transfer; full bytes may be losslessly gzip encoded for whitespace-safe transport, with both stored/decoded identities preserved."})


def verify() -> None:
    selection = load(D / "focused-real-worker-transfer-selection.json")
    for row in selection["files"]:
        assert binding(Path(row["path"])) == {key: row[key] for key in ["path", "bytes", "sha256"]}
    report = load(D / "focused-real-worker-review.json")
    assert report["test_body_and_program_binding"] == git_body_contract()
    archive = load(D / "synthetic-native-cas-bindings.json")
    assert binding(Path(archive["archive"]["path"])) == archive["archive"]
    expected = {row["archive_path"]: row for row in archive["files"]}
    with tarfile.open(archive["archive"]["path"], "r:gz") as tf:
        assert set(tf.getnames()) == set(expected)
        for name, row in expected.items():
            assert digest(tf.extractfile(name).read()) == {key: row[key] for key in ["bytes", "sha256"]}
    print(json.dumps({"outcome": "PASS", "files": len(selection["files"]),
                      "complete_bytes": selection["complete_file_bytes"],
                      "synthetic_CAS_files": len(expected), "review": binding(D / "focused-real-worker-review.json"),
                      "selection": binding(D / "focused-real-worker-transfer-selection.json"),
                      "scope": "Receipt/body/archive verification only; no scientific test executed."}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if args.verify:
        verify()
    else:
        assemble()
        verify()
