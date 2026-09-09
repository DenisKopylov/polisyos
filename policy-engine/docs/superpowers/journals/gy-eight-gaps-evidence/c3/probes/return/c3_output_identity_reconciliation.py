"""Reconcile complete selected pytest identities for output preservation controls."""

from __future__ import annotations

import ast
import hashlib
import json
import re
from pathlib import Path


ROOT = Path("_build/gy-gaps/c3")


def read(name: str):
    path = ROOT / name
    receipt = json.loads(path.read_text())
    rows = re.findall(r"^(PASSED|FAILED|ERROR|SKIPPED|XFAIL|XPASS) (.+)$", receipt["stdout"], re.M)
    observed = {identity.split(" - ", 1)[0]: status for status, identity in rows}
    progress = re.findall(r"^([.FEsxX]+)\s+\[\s*\d+%\]", receipt["stdout"], re.M)
    if len(rows) != len(observed) or sum(map(len, progress)) != len(observed):
        raise ValueError(f"pytest identity/progress mismatch: {name}")
    if receipt["timed_out"] or not observed:
        raise ValueError(f"incomplete deciding output: {name}")
    return receipt, observed, f"{path}@sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


def selection(stdout: str) -> list[str]:
    for line in stdout.splitlines():
        if line.startswith("{'selected_native_targets':"):
            return ast.literal_eval(line)["selected_native_targets"]
    raise ValueError("removal selection not recorded")


def selected_identities(all_ids, targets):
    return {
        identity for identity in all_ids
        if any(identity == target or identity.startswith(target + "[") or identity.startswith(target + "::") for target in targets)
    }


def main() -> int:
    baseline, first, baseline_ref = read("output-return-native-final.json")
    corrected, corrections, corrected_ref = read("output-return-corrected-controls.json")
    failed_initially = {identity for identity, result in first.items() if result == "FAILED"}
    expected_corrections = selected_identities(first, [arg for arg in corrected["command"] if arg.startswith("tests/")])
    if (
        baseline["returncode"] != 1 or set(first.values()) - {"PASSED", "FAILED"}
        or corrected["returncode"] != 0 or set(corrections.values()) != {"PASSED"}
        or corrections.keys() != expected_corrections
        or not failed_initially or not failed_initially <= corrections.keys()
    ):
        raise ValueError("initial and corrected native identity populations do not reconcile")
    passed = {**first, **corrections}
    if set(passed.values()) != {"PASSED"}:
        raise ValueError("a measured native failure remains unresolved")
    old, red, old_ref = read("output-transport-old-readers-red.json")
    expected_old = selected_identities(passed, [arg for arg in old["command"] if arg.startswith("tests/")])
    if old["returncode"] != 1 or expected_old != red.keys() or set(red.values()) - {"PASSED", "FAILED"}:
        raise ValueError("old-reader selected identity population does not reconcile")
    deltas = []
    for mode in ("wire-decoder", "cache-custody", "current-emission", "consulted-premise", "causal-premise"):
        receipt, observed, ref = read(f"output-{mode}-removal.json")
        expected = selected_identities(passed, selection(receipt["stdout"]))
        failed = {identity for identity, status in observed.items() if status == "FAILED"}
        if receipt["returncode"] != 1 or set(observed) != expected or not failed or set(observed.values()) - {"PASSED", "FAILED"}:
            raise ValueError(f"incomplete or unexpected selected removal identities: {mode}")
        deltas.append({
            "receipt": ref,
            "selected_baseline_denominator": len(expected),
            "identity_difference": sorted(expected ^ observed.keys()),
            "pass_to_fail": sorted(failed),
            "preserved_passes": sorted(set(observed) - failed),
        })
    print(json.dumps({
        "initial_native_receipt": baseline_ref,
        "corrected_controls_receipt": corrected_ref,
        "initial_failed_to_corrected_passed": sorted(failed_initially),
        "complete_native_population_reconciled": len(passed),
        "initial_identity_and_independent_progress_count": len(first),
        "corrected_identity_and_independent_progress_count": len(corrections),
        "old_reader_receipt": old_ref,
        "old_reader_selected_denominator": len(red),
        "old_failed_to_passed": sorted(identity for identity, result in red.items() if result == "FAILED"),
        "old_passes_preserved": sorted(identity for identity, result in red.items() if result == "PASSED"),
        "comparison_scope": "Each complete explicitly selected mutation population; unselected baseline tests are not claimed rerun.",
        "removals": deltas,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
