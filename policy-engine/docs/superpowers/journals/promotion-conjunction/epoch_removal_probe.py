"""Exercise each epoch forwarding omission in memory, retaining the call markers."""

from __future__ import annotations
import __future__

import ast
import hashlib
import importlib
import inspect
import json
import marshal
import sys
import textwrap
import time
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

import polisyos.runtime.quality.generation_cycle as owner

if TYPE_CHECKING:
    from types import FunctionType, ModuleType


def remove_forwarded_resolver(function: FunctionType) -> tuple[FunctionType, str]:
    original_source = textwrap.dedent(inspect.getsource(function))
    tree = ast.parse(original_source)
    removed = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            for keyword in node.keywords:
                if keyword.arg == "epoch_validity_resolver":
                    keyword.value = ast.Constant(value=None)
                    removed += 1
    if removed != 1:
        raise AssertionError(f"expected one real forwarding link, found {removed}")
    ast.fix_missing_locations(tree)
    namespace = {}
    exec(  # noqa: S102 - execute the deliberate in-memory removal of the inspected owner function.
        compile(
            tree,
            f"<epoch-forwarding-removal:{function.__qualname__}>",
            "exec",
            flags=__future__.annotations.compiler_flag,
        ),
        vars(owner),
        namespace,
    )
    return namespace[function.__name__], hashlib.sha256(original_source.encode()).hexdigest()


class FailureWitness:
    def __init__(self) -> None:
        self.reports: list[dict[str, str]] = []

    def pytest_runtest_logreport(self, report: pytest.TestReport) -> None:
        self.reports.append({
            "nodeid": report.nodeid, "when": report.when,
            "outcome": report.outcome, "longrepr": report.longreprtext,
        })


def run_case(target: ModuleType | type, name: str, selector: str) -> dict[str, object]:
    source = Path(inspect.getfile(owner))
    original = getattr(target, name)
    replacement, function_hash = remove_forwarded_resolver(original)
    original_code = original.__code__
    if replacement.__code__.co_freevars != original_code.co_freevars:
        raise RuntimeError("epoch_removal_freevars_changed")
    witness = FailureWitness()
    started = time.monotonic()
    try:
        # Every existing import alias retains this object and executes its mutated code.
        original.__code__ = replacement.__code__
        code = pytest.main(
            [selector, "-q", "--tb=short", "-p", "no:cacheprovider"], plugins=[witness],
        )
    finally:
        original.__code__ = original_code
    expected = (
        "epoch_owner_forwarding_missing_at_generation_run" if name == "run"
        else "epoch_owner_replay_is_not_clean"
    )
    failures = [row for row in witness.reports if row["when"] == "call"
                and row["outcome"] == "failed" and expected in row["longrepr"]]
    actual_witness = len(failures) == 1 and not any(
        row["when"] in {"setup", "teardown"} and row["outcome"] == "failed"
        for row in witness.reports
    )
    if name != "run":
        actual_witness = actual_witness and (
            "epoch_validity_resolver_not_established" in failures[0]["longrepr"]
            if failures else False
        )
    return {
        "boundary": name, "actual_input_read": str(source),
        "inputs_read": [
            str(Path(__file__)) + "@sha256:" + hashlib.sha256(
                Path(__file__).read_bytes()
            ).hexdigest(),
            str(source) + "@sha256:" + hashlib.sha256(source.read_bytes()).hexdigest(),
            selector.split("::", 1)[0] + "@sha256:" + hashlib.sha256(
                Path(selector.split("::", 1)[0]).read_bytes()
            ).hexdigest(),
        ],
        "unresolved_by_construction": [
            "other_promotion_conjuncts_are_not_certified_by_epoch_forwarding_probe",
            "nonselected_forwarding_boundaries_are_not_mutated_in_this_case",
            "pytest_transitive_imports_and_external_services_not_enumerated",
        ],
        "freevars_preserved": replacement.__code__.co_freevars == original_code.co_freevars,
        "function_identity_preserved": getattr(target, name) is original,
        "original_code_restored": original.__code__ is original_code,
        "original_code_sha256": hashlib.sha256(marshal.dumps(original_code)).hexdigest(),
        "mutated_code_sha256": hashlib.sha256(marshal.dumps(replacement.__code__)).hexdigest(),
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "function_sha256": function_hash, "test_selector": selector,
        "returncode": int(code), "expected_returncode": 1,
        "seconds": round(time.monotonic() - started, 3),
        "mutation": "forwarded epoch resolver replaced by None; signature, keyword, call retained",
        "intended_call_phase_witness": actual_witness, "reports": witness.reports,
    }


def main() -> int:
    posture_selector = (
        "tests/unit/runtime/quality/test_promotion_sequence.py::"
        "test_injected_posture_flags_are_a_bounded_predicate_not_evidence_admission"
    )
    test_path = Path(posture_selector.split("::", 1)[0])
    importlib.invalidate_caches()
    reloaded_modules = []
    function_name = posture_selector.rsplit("::", 1)[1]
    for module_name, module in tuple(sys.modules.items()):
        module_file = getattr(module, "__file__", None)
        if module_file is not None and Path(module_file).resolve() == test_path.resolve():
            before = getattr(module, function_name)
            before_signature = str(inspect.signature(before))
            before_code_hash = hashlib.sha256(marshal.dumps(before.__code__)).hexdigest()
            importlib.reload(module)
            after = getattr(module, function_name)
            reloaded_modules.append({
                "module": module_name,
                "before_signature": before_signature,
                "before_code_sha256": before_code_hash,
                "after_signature": str(inspect.signature(after)),
                "after_code_sha256": hashlib.sha256(marshal.dumps(after.__code__)).hexdigest(),
                "current_file_sha256": hashlib.sha256(test_path.read_bytes()).hexdigest(),
            })
    print(json.dumps({"final_test_module_reload": reloaded_modules}), flush=True)  # noqa: T201
    preflight_witness = FailureWitness()
    started = time.monotonic()
    preflight_code = pytest.main(
        [posture_selector, "-vv", "-rA", "-s"], plugins=[preflight_witness],
    )
    intended_call = sum(
        row["when"] == "call" and row["outcome"] == "passed"
        and row["nodeid"] == posture_selector for row in preflight_witness.reports
    ) == 1
    preflight = {
        "test_selector": posture_selector, "returncode": int(preflight_code),
        "reloaded_final_test_modules": reloaded_modules,
        "intended_call_phase_witness": intended_call,
        "reports": preflight_witness.reports,
        "seconds": round(time.monotonic() - started, 3),
        "inputs_read": [str(test_path) + "@sha256:" + hashlib.sha256(
            test_path.read_bytes()
        ).hexdigest()],
        "unresolved_by_construction": [
            "injected_posture_predicate_witness_does_not_establish_source_admission",
        ],
    }
    print(json.dumps({"final_posture_preflight": preflight}), flush=True)  # noqa: T201
    (Path(__file__).parent / "raw" / "posture-final-preflight.json").write_text(
        json.dumps(preflight, indent=2) + "\n"
    )
    if preflight_code != 0 or not intended_call:
        return int(preflight_code) or 1
    test_file = "tests/unit/runtime/quality/test_generation_cycle.py"
    cases = (
        (
            owner.GenerationCycleController,
            "run",
            f"{test_file}::test_generation_run_carries_epoch_owner_into_decision_front_replay",
        ),
        (
            owner,
            "_apply_promotion_to_summaries",
            f"{test_file}::test_decision_front_replays_epoch_owner_and_preserves_refusal[valid]",
        ),
        (
            owner,
            "_promotion_receipt_allows_decision_front",
            f"{test_file}::test_decision_front_replays_epoch_owner_and_preserves_refusal[valid]",
        ),
    )
    receipts = []
    for target, name, selector in cases:
        receipt = run_case(target, name, selector)
        receipts.append(receipt)
        print(json.dumps(receipt), flush=True)  # noqa: T201
    destination = Path(__file__).parent / "raw" / "epoch-bridge-removal.json"
    destination.write_text(json.dumps(receipts, indent=2) + "\n")
    return 0 if all(
        item["returncode"] == 1 and item["intended_call_phase_witness"] for item in receipts
    ) and all(
        item["freevars_preserved"] and item["function_identity_preserved"]
        and item["original_code_restored"] for item in receipts
    ) else 1


if __name__ == "__main__":
    raise SystemExit(main())
