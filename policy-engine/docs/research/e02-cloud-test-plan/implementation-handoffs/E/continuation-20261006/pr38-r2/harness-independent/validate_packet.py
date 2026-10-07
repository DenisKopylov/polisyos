"Recompute moderate copy custody and native-harness predicate denominators."

import argparse
import copy
import hashlib
import json
import sys
from pathlib import Path, PurePosixPath


def _write_stdout(*values: object, flush: bool = False) -> None:
    "Emit the existing CLI text and optionally flush without logging side effects."
    sys.stdout.write(" ".join(str(value) for value in values) + "\n")
    if flush:
        sys.stdout.flush()


def validate_index(root: object, index: object) -> tuple[object, ...]:
    rows = index["files"]
    seen = set()
    total = 0
    for row in rows:
        name = row["path"]
        path = PurePosixPath(name)
        if not (not path.is_absolute() and ".." not in path.parts and name not in seen):
            raise AssertionError
        seen.add(name)
        data = (root / name).read_bytes()
        total += len(data)
        if not (len(data) == row["size_bytes"]):
            raise AssertionError(name)
        if not (hashlib.sha256(data).hexdigest() == row["sha256"]):
            raise AssertionError(name)
    if not (index["total_files"] == len(rows) and index["total_bytes"] == total):
        raise AssertionError
    return len(rows), total


def validate_properties(root: object, review: object = None) -> bool:
    review = review or json.loads((root / "review.json").read_text())
    plan = json.loads((root / "plan-snapshot.json").read_text())
    correction = json.loads((root / "denominator-correction.json").read_text())
    raw = json.loads((root / "harness-independent-review.json").read_text())
    if not (
        review["candidate"]
        == plan["candidate_sha"]
        == raw["source_sha"]
        == correction["source_sha"]
        == "4758d495abb81aa51fea8e28cd071ca9ff989155"
    ):
        raise AssertionError
    if not (review["tree"] == plan["candidate_tree_sha"] == raw["source_tree"]):
        raise AssertionError
    if not (review["verdict"] == "GO-bounded-owned-harness-readiness-and-preservation"):
        raise AssertionError
    d = review["input_denominators"]
    groups = plan["groups"]
    native = [x for xs in groups.values() for x in xs]
    if not (
        len(native)
        == len(set(native))
        == d["native_test_paths"]
        == plan["native_test_path_count"]
        == 120
    ):
        raise AssertionError
    if not (len(plan["owner_packet_extra_inputs"]) == d["A_owner_packet_paths"] == 2):
        raise AssertionError
    if not (
        d["total_test_file_inputs"] == len(native) + len(plan["owner_packet_extra_inputs"]) == 122
    ):
        raise AssertionError
    if not (d["native_groups"] == len(groups) == 7):
        raise AssertionError
    paths = plan["changed_python_lint_paths"]
    docs = [x for x in paths if x.startswith("docs/")]
    if not (
        d["planned_Ruff_changed_Python_exact4758"]
        == len(paths)
        == correction["total_denominator"]
        == 211
    ):
        raise AssertionError
    if not (
        d["docs_witnesses_in_Ruff_denominator_exact4758"]
        == len(docs)
        == correction["actual_value"]
        == 109
    ):
        raise AssertionError
    if not (
        correction["historical_reported_value"] == raw["planned_Ruff_docs_artifact_paths"] == 0
    ):
        raise AssertionError
    if not (d["focused_configured_Ruff_files"] == 3):
        raise AssertionError
    gate_names = [j["name"] for j in plan["jobs"] if j["kind"] == "gate"]
    if not (
        gate_names
        == raw["required_gate_sequence"]
        == [
            "architecture",
            "runtime-api-contract",
            "static-invocation",
            "ruff",
            "ruff-format",
            "workspace-verify",
            "ci-parity",
        ]
    ):
        raise AssertionError
    if not (plan["execution_state"] == "NOT_RUN" and raw["native_wave_state"].startswith("UNRUN")):
        raise AssertionError
    if not (plan["missing_required_paths"] == [] and plan["old_paths_retained"]):
        raise AssertionError
    for j in plan["jobs"]:
        if j["kind"] == "numerical" and (
            not ("addopts=" not in j["argv"] and "no:cacheprovider" not in j["argv"])
        ):
            raise AssertionError
    if not (raw["controls"][0]["prepare_counter"] == raw["controls"][1]["process_counter"] == 0):
        raise AssertionError
    if not (
        raw["controls"][2]["process_spy_counter"] == 1
        and raw["controls"][2]["real_children_launched"] == 0
    ):
        raise AssertionError
    if not (
        raw["controls"][3]["counts"]
        == {
            "cases": 4,
            "passed": 1,
            "failed": 1,
            "errors": 1,
            "skipped": 1,
        }
    ):
        raise AssertionError
    browser = json.loads((root / "browser-capability-receipt.json").read_text())
    if not (browser["capability"]["actualRenderedText"] == "4"):
        raise AssertionError
    data = (root / "browser-capability.stdout").read_bytes()
    if not (
        len(data) == browser["stdout_size_bytes"]
        and hashlib.sha256(data).hexdigest() == browser["stdout_sha256"]
    ):
        raise AssertionError
    if not (browser["exit_code"] == 0):
        raise AssertionError
    return True


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).parent)
    a = parser.parse_args()
    index = json.loads((a.root / "copy-index.json").read_text())
    _count, _total = validate_index(a.root, index)
    if not (validate_properties(a.root)):
        raise AssertionError
    negatives = []
    for field, value in [("size_bytes", -1), ("sha256", "0" * 64)]:
        damaged = copy.deepcopy(index)
        damaged["files"][0][field] = value
        try:
            validate_index(a.root, damaged)
        except AssertionError:
            negatives.append(field + " REFUSED")
        else:
            raise AssertionError("custody corruption accepted")
    damaged = json.loads((a.root / "review.json").read_text())
    damaged["input_denominators"]["native_test_paths"] = 119
    try:
        validate_properties(a.root, damaged)
    except AssertionError:
        negatives.append("native denominator REFUSED")
    else:
        raise AssertionError("predicate count corruption accepted")
    _write_stdout(
        json.dumps(
            {
                "outcome": "PASS-recomputing-moderate-custody-and-predicate-validator",
                "corrupt_field_controls": negatives,
                "numeric_and_full_CI": "UNRUN",
            }
        )
    )


if __name__ == "__main__":
    main()
