"""Bind the complete repair footprint, current intake API, and unchanged scientific owners."""

import ast
import hashlib
import inspect
import json
import platform
import subprocess
import sys
from importlib.metadata import version
from pathlib import Path

from polisyos.scientist.governance.passes.confidence_pass import ConfidencePass

root = Path.cwd().parent
base = "6fe6e352ad5aff4055b490a7892ae123dad1c0ab"
candidate = "df5057dd3816885fc5bfacd9a9f1ee772df9ac51"
provider = "policy-engine/src/polisyos/scientist/governance/passes/confidence_pass.py"


def git(*args):
    return subprocess.check_output(["git", *args], cwd=root).decode().strip()


def data_at(sha, path):
    return subprocess.check_output(["git", "show", f"{sha}:{path}"], cwd=root)


assert git("rev-parse", "HEAD") == candidate
assert Path(inspect.getfile(ConfidencePass)).resolve() == root / provider
paths = git("diff", "--name-only", base, candidate).splitlines()
expected = [
    provider,
    "policy-engine/tests/unit/scientist/governance/test_confidence_issue_accumulation.py",
    "policy-engine/docs/reference/scientist/causal-confidence-issue-preservation.md",
    "policy-engine/release-fragments/unreleased/2026-10-06-causal-confidence-issue-preservation.toml",
]
assert set(paths) == set(expected), paths
trees = {sha: ast.parse(data_at(sha, provider)) for sha in [base, candidate]}
imports = {
    sha: [ast.dump(node) for node in ast.walk(tree)
          if isinstance(node, (ast.Import, ast.ImportFrom))]
    for sha, tree in trees.items()
}
assert imports[base] == imports[candidate]
function = next(
    node for node in ast.walk(trees[candidate])
    if isinstance(node, ast.FunctionDef) and node.name == "validate"
)
returns = [node for node in ast.walk(function) if isinstance(node, ast.Return)]
assert all(isinstance(node.value, ast.Name) and node.value.id == "issues" for node in returns)
unchanged = [
    "policy-engine/src/polisyos/ir/analytics/causal.py",
    "policy-engine/src/polisyos/ir/analytics/uncertainty.py",
    "policy-engine/src/polisyos/foundry/methods/catalog/causal/tmle_core.py",
    "policy-engine/src/polisyos/foundry/methods/catalog/causal/nuisance_layer.py",
    "policy-engine/src/polisyos/foundry/methods/catalog/causal/treatment_effects.py",
]
bindings = []
for path in unchanged:
    data = data_at(candidate, path)
    assert data == data_at(base, path), path
    bindings.append({"path": path, "git_blob": git("rev-parse", f"{candidate}:{path}"),
                     "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
                     "equality_to_slice_base": True})
g_record = "policy-engine/docs/research/e02-cloud-test-plan/integration/reviews/F-delta-owner-actions-2026-10-06.md"
g_sha = "127dc7ab8365d29eb656fe32c0c894f6cc971286"
g_data = data_at(g_sha, g_record)
print(json.dumps({
    "scope": "four owned paths; unchanged import AST; validate return denominator; five unchanged scientific owners",
    "base_sha": base, "candidate_sha": candidate, "candidate_tree": git("rev-parse", "HEAD^{tree}"),
    "actual_changed_paths": paths, "validate_return_sites": len(returns),
    "all_return_sites_preserve_accumulated_issues": True,
    "runtime_provider_origin": inspect.getfile(ConfidencePass),
    "validate_signature": str(inspect.signature(ConfidencePass.validate)),
    "scientific_owner_bindings": bindings,
    "g_original_owner_action": {"git_ref": g_sha, "path": g_record,
                                "bytes": len(g_data), "sha256": hashlib.sha256(g_data).hexdigest()},
    "environment": {"executable": sys.executable, "python": platform.python_version(),
                    "pytest": version("pytest"), "pydantic": version("pydantic")},
    "limitations": "This source-bound scope audit is not a runtime authority, whole architecture, estimator, or production budget witness.",
}, indent=2))
