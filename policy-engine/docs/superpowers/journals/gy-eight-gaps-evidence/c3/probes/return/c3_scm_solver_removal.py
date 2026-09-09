"""Warm current control then historical-solver removal; no product-file edits."""

from __future__ import annotations

import ast
import hashlib
import importlib
import json
from pathlib import Path
import subprocess

import pytest


class Reports:
    def __init__(self):
        self.collected = []
        self.reports = []

    def pytest_collection_finish(self, session):
        self.collected = [item.nodeid for item in session.items]

    def pytest_runtest_logreport(self, report):
        self.reports.append(
            {"identity": report.nodeid, "phase": report.when, "outcome": report.outcome}
        )


def main() -> int:
    source = Path("src/polisyos/foundry/methods/catalog/causal/synthetic_control.py")
    test = Path("tests/unit/foundry/methods/catalog/causal/test_synthetic_control.py")
    snapshots = {path: path.read_bytes() for path in (source, test)}
    predecessor = "e2cf7f10f2853b7561034b8e0ba699e6bacd32ba"
    previous = subprocess.check_output(["git", "show", f"{predecessor}:policy-engine/{source}"])
    original_node = next(
        node
        for node in ast.parse(previous).body
        if isinstance(node, ast.FunctionDef) and node.name == "_fit_scm_weights"
    )
    owner = importlib.import_module("polisyos.foundry.methods.catalog.causal.synthetic_control")
    current = owner._fit_scm_weights
    signature_before = owner.SyntheticControlMethod.signature.stable_digest()
    fqn_before = owner.SyntheticControlMethod.signature.fqn
    assert fqn_before == "causal.inference.synthetic_control@2.0.0"
    namespace = {"np": owner.np, "__name__": owner.__name__}
    exec(
        compile(
            ast.fix_missing_locations(ast.Module(body=[original_node], type_ignores=[])),
            str(source),
            "exec",
        ),
        namespace,
    )
    legacy = namespace["_fit_scm_weights"]
    args = ["-q", "--tb=short", str(test), "-k", "scm_solver"]
    baseline = Reports()
    baseline_exit = int(pytest.main(args, plugins=[baseline]))
    mutant = Reports()
    if baseline_exit == 0:
        try:
            owner._fit_scm_weights = legacy
            mutant_exit = int(pytest.main(args, plugins=[mutant]))
        finally:
            owner._fit_scm_weights = current
    else:
        mutant_exit = None
    independent_count = 0
    for node in ast.parse(snapshots[test]).body:
        if not isinstance(node, ast.FunctionDef) or not node.name.startswith("test_scm_solver"):
            continue
        count = 1
        for decorator in node.decorator_list:
            assert isinstance(decorator, ast.Call) and isinstance(
                decorator.args[1], (ast.List, ast.Tuple)
            )
            count *= len(decorator.args[1].elts)
        independent_count += count
    failed = lambda reports: {
        row["identity"] for row in reports.reports if row["outcome"] == "failed"
    }
    baseline_failures, mutant_failures = failed(baseline), failed(mutant)
    payload = {
        "scope": "Exact current numerical native population; current registered v2/rule/signature/source markers retained; only old solver function restored in memory.",
        "command": ["pytest.main", *args],
        "source_sha256": {
            str(path): hashlib.sha256(raw).hexdigest() for path, raw in snapshots.items()
        },
        "predecessor": predecessor,
        "predecessor_owner_sha256": hashlib.sha256(previous).hexdigest(),
        "removed_property_function_ast_sha256": hashlib.sha256(
            ast.dump(original_node, include_attributes=False).encode()
        ).hexdigest(),
        "method_fqn_before": fqn_before,
        "method_fqn_after": owner.SyntheticControlMethod.signature.fqn,
        "signature_digest_before": signature_before,
        "signature_digest_after": owner.SyntheticControlMethod.signature.stable_digest(),
        "baseline_pytest_exit": baseline_exit,
        "mutant_pytest_exit": mutant_exit,
        "case_denominator_ast": independent_count,
        "baseline_collected": baseline.collected,
        "mutant_collected": mutant.collected,
        "collection_identity_delta": sorted(set(baseline.collected) ^ set(mutant.collected)),
        "baseline_reports": baseline.reports,
        "mutant_reports": mutant.reports,
        "added_finding_identities": sorted(mutant_failures - baseline_failures),
        "lost_finding_identities": sorted(baseline_failures - mutant_failures),
        "owner_function_restored": owner._fit_scm_weights is current,
        "source_unchanged": all(path.read_bytes() == raw for path, raw in snapshots.items()),
    }
    print("\nSCM_SOLVER_REMOVAL_COMPLETE\n" + json.dumps(payload, indent=2), flush=True)
    assert baseline_exit == 0, "current numerical baseline failed; mutation is not a receipt"
    assert len(baseline.collected) == independent_count
    assert len(baseline.collected) == len(set(baseline.collected))
    assert baseline.collected == mutant.collected
    assert all(row["phase"] == "call" for row in mutant.reports if row["outcome"] == "failed")
    assert signature_before == owner.SyntheticControlMethod.signature.stable_digest()
    assert payload["source_unchanged"] and owner._fit_scm_weights is current
    if mutant_exit == 0:
        return 0
    assert mutant_exit == 1 and mutant_failures and not baseline_failures
    return mutant_exit


if __name__ == "__main__":
    raise SystemExit(main())
