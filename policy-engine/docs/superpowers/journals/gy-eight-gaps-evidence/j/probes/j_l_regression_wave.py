"""Run the complete existing L regression population and exact J importer delta.

Source-only planning is available with --plan-only. No source snapshots are stored.
Corrections replay every expanded identity of each previously failed definition.
"""

from __future__ import annotations

import argparse
import ast
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import subprocess

from _build.gy_gaps import l_receipt_reconcile as receipts

ROOT = Path(__file__).resolve().parents[2]
TEST = "tests/repo_quality/architecture/test_layer3_gy_artifact_lifecycle.py"
OWNER = "tools/quality/validation/check_layer3_gy_loop_artifacts.py"
SUITE = "gy_j_l_regression_and_importers.v1"
HISTORICAL_COLLECTION = (
    "docs/superpowers/journals/gy-eight-gaps-evidence/l/"
    "native-live-wave-after-typed-readback.json"
)
HISTORICAL_SHA256 = "68ca192072dcb0cc52587bda2e5bafa89113ba3f2d64ec03a91efafe075d016d"
IMPORTERS = (
    "test_layer3_gy_loop_family_uses_honest_generated_and_source_classifications",
    "test_layer3_gy_outcome_run_is_http_triggered_and_honestly_blocked",
    "test_layer3_gy_outcome_validator_rejects_direct_helper_and_hand_authored_proof",
    "test_layer3_gy_outcome_replay_corrupt_field_detects_drift",
    "test_layer3_gy_outcome_validator_rejects_gx_terminal_drift",
    "test_layer3_gy_loop_validator_recomputes_graded_outcome_routing_report",
)
HARNESS = (
    "_build/gy_gaps/j_l_regression_wave.py",
    "_build/gy_gaps/l_receipt_reconcile.py",
    "_build/gy_gaps/receipt.py",
)


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise ValueError(reason)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical_hash(value: object) -> str:
    return sha(json.dumps(value, sort_keys=True, separators=(",", ":")).encode())


def population() -> dict:
    raw = (ROOT / TEST).read_bytes()
    source = raw.decode("utf-8")
    functions = {
        node.name: node for node in ast.parse(source).body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    prefix = {name: node for name, node in functions.items() if name.startswith("test_gy_l_")}
    independent = re.findall(r"^(?:async )?def (test_gy_l_[A-Za-z0-9_]+)\(", source, re.M)
    require(set(prefix) == set(independent) and len(prefix) == len(independent),
            "complete_L_definition_derivations_disagree")
    require(set(IMPORTERS) <= functions.keys(), "required_J_importer_definition_absent")
    require(len(IMPORTERS) == len(set(IMPORTERS)), "duplicate_importer_definition")
    selected = {**prefix, **{name: functions[name] for name in IMPORTERS}}
    expansion = {}
    for name, node in selected.items():
        count = 1
        for decorator in node.decorator_list:
            require(isinstance(decorator, ast.Call)
                    and ast.unparse(decorator.func) == "pytest.mark.parametrize",
                    "unclassified_test_decorator:" + name)
            count *= len(ast.literal_eval(decorator.args[1]))
        expansion[f"{TEST}::{name}"] = count
    historical_raw = (ROOT / HISTORICAL_COLLECTION).read_bytes()
    require(sha(historical_raw) == HISTORICAL_SHA256, "historical_collection_pin_mismatch")
    historical = receipts.strict_json(historical_raw)
    packets = receipts.packets(historical, "GY_L_NATIVE_READBACK ")
    require(len(packets) == 1, "historical_collection_packet_missing_or_duplicated")
    old = receipts.unique_strings(packets[0]["payload"]["collected"], "historical_collection")
    require(Counter(receipts.base_node(node) for node in old)
            == {f"{TEST}::{name}": expansion[f"{TEST}::{name}"] for name in prefix},
            "complete_L_expansion_differs_from_independent_real_collection")
    importer_nodes = {f"{TEST}::{name}" for name in IMPORTERS}
    require(all(expansion[node] == 1 for node in importer_nodes),
            "importer_parameter_expansion_requires_new_independent_collection")
    expected = old | importer_nodes
    require(len(expected) == sum(expansion.values()), "complete_expanded_population_mismatch")
    require((ROOT / TEST).read_bytes() == raw, "test_source_changed_during_population_read")
    return {
        "source": TEST, "source_sha256": sha(raw), "suite_id": SUITE,
        "definition_denominator": len(selected),
        "independent_denominator": len(independent) + len(IMPORTERS),
        "L_definition_denominator": len(prefix), "L_expanded_denominator": len(old),
        "importer_definitions": list(IMPORTERS),
        "expected_expanded_identities": sorted(expected),
        "complete_expansion": dict(sorted(expansion.items())),
        "historical_collection": HISTORICAL_COLLECTION,
        "historical_collection_sha256": HISTORICAL_SHA256,
    }


def source_snapshot() -> dict:
    """Hash every Git-visible product Python input plus this explicit harness."""
    def listed(arguments: list[str]) -> set[str]:
        raw = subprocess.check_output(
            ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard", *arguments],
            cwd=ROOT,
        )
        paths = [item.decode("utf-8") for item in raw.split(b"\0") if item]
        require(len(paths) == len(set(paths)), "duplicate_git_source_identity")
        return set(paths)

    direct = listed(["--", "*.py"])
    independent = {path for path in listed([]) if Path(path).suffix == ".py"}
    require(direct == independent, "complete_python_source_identity_derivations_disagree")
    values = {}
    for relative in sorted(direct | set(HARNESS)):
        path = ROOT / relative
        try:
            content = path.read_bytes()
        except FileNotFoundError:
            values[relative] = {"state": "absent"}
        else:
            values[relative] = {"state": "present", "sha256": sha(content)}
        if path.is_symlink():
            values[relative]["symlink_target"] = str(path.readlink())
    return values


def source_summary(values: dict) -> dict:
    return {
        "scope": "all Git-visible product .py paths, including untracked files, plus explicit harness",
        "path_denominator": len(values),
        "complete_path_identity_sha256": canonical_hash(sorted(values)),
        "complete_source_state_sha256": canonical_hash(values),
        "test_source": values[TEST], "owner_source": values[OWNER],
        "harness_sources": {path: values[path] for path in HARNESS},
        "absent_paths": sorted(path for path, value in values.items() if value["state"] == "absent"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--failed-from", type=Path)
    parser.add_argument("--plan-only", action="store_true")
    args = parser.parse_args()
    require(Path.cwd().resolve() == ROOT, "run_from_product_root")
    basis = population()
    nodes = list(basis["complete_expansion"])
    expected = set(basis["expected_expanded_identities"])
    predecessor_sha = None
    if args.failed_from:
        raw = args.failed_from.read_bytes()
        previous = receipts.strict_json(raw)
        metadata, outcomes = receipts.reconcile_native(previous)
        packets = receipts.packets(previous, "GY_L_NATIVE_POPULATION ")
        require(len(packets) == 1 and packets[0]["payload"].get("suite_id") == SUITE,
                "correction_predecessor_is_not_this_complete_suite")
        readbacks = receipts.packets(previous, "GY_L_NATIVE_READBACK ")
        require(len(readbacks) == 1 and readbacks[0]["payload"].get("source_frozen") is True
                and readbacks[0]["payload"].get("complete_identity_readback") is True,
                "correction_predecessor_source_or_identity_basis_not_established")
        require(outcomes is not None and metadata["measurement_state"] == "measured",
                "correction_predecessor_unmeasurable")
        require(set(outcomes) <= expected, "correction_predecessor_identity_outside_current_basis")
        failed = {receipts.base_node(node) for node, status in outcomes.items() if status != "passed"}
        require(bool(failed), "correction_has_no_prior_nonpassing_definition")
        nodes = [node for node in nodes if node in failed]
        expected = {node for node in expected if receipts.base_node(node) in failed}
        predecessor_sha = sha(raw)
        require(args.failed_from.read_bytes() == raw, "correction_receipt_changed_during_read")
    before = source_snapshot()
    population_packet = {
        **{key: value for key, value in basis.items()
           if key not in {"expected_expanded_identities", "complete_expansion"}},
        "nodes": nodes,
        "failed_from": str(args.failed_from) if args.failed_from else None,
        "failed_from_sha256": predecessor_sha,
        "complete_expected_identity_sha256": canonical_hash(basis["expected_expanded_identities"]),
        "selected_expected_identity_sha256": canonical_hash(sorted(expected)),
        "selected_expected_expanded_denominator": len(expected),
        "source_before": source_summary(before),
    }
    if args.plan_only:
        require(source_snapshot() == before, "sources_changed_during_plan_only")
        print("GY_J_L_NATIVE_PLAN " + json.dumps(population_packet, sort_keys=True))
        return 0

    # Import pytest only after the execution source basis has been captured.
    import pytest

    collected, outcomes = [], []

    class Recorder:
        def pytest_collection_finish(self, session):
            collected.extend(item.nodeid for item in session.items)
            require(len(collected) == len(set(collected)), "duplicate_collected_identity")
            require(set(collected) == expected, "actual_collection_differs_from_complete_expected_set:"
                    + json.dumps({"lost": sorted(expected - set(collected)),
                                  "added": sorted(set(collected) - expected)}, sort_keys=True))

        def pytest_runtest_logreport(self, report):
            if report.when == "call" or report.failed or report.skipped:
                outcomes.append({"nodeid": report.nodeid, "when": report.when,
                                 "outcome": report.outcome})

    print("GY_L_NATIVE_POPULATION " + json.dumps(population_packet, sort_keys=True), flush=True)
    result = int(pytest.main(["-q", "-s", "-rA", "--show-capture=no", "--tb=short", *nodes],
                             plugins=[Recorder()]))
    after = source_snapshot()
    changed = {path: {"before": before[path], "after": after[path]}
               for path in before.keys() & after.keys() if before[path] != after[path]}
    source_delta = {
        "lost": {path: before[path] for path in sorted(before.keys() - after.keys())},
        "added": {path: after[path] for path in sorted(after.keys() - before.keys())},
        "changed": dict(sorted(changed.items())),
    }
    emitted = {row["nodeid"] for row in outcomes}
    complete = set(collected) == expected == emitted and len(collected) == len(set(collected))
    frozen = before == after
    final_rc = result if complete and frozen else 2
    print("GY_L_NATIVE_READBACK " + json.dumps({
        "suite_id": SUITE, "collected": collected, "outcomes": outcomes,
        "collected_denominator": len(collected), "reported_denominator": len(emitted),
        "returncode": final_rc, "pytest_returncode": result,
        "complete_identity_readback": complete, "source_frozen": frozen,
        "source_after": source_summary(after), "complete_source_delta": source_delta,
        "measurement_state": "measured" if complete and frozen else "not_established",
        "missing_expected_identities": sorted(expected - set(collected)),
        "unreported_collected_identities": sorted(set(collected) - emitted),
    }, sort_keys=True), flush=True)
    return final_rc


if __name__ == "__main__":
    raise SystemExit(main())
