"""Bind the complete C05 staged change and known canonical suppliers."""
import ast
import hashlib
import json
from pathlib import Path
import subprocess

repo = Path("/workspace/orch02-c05")
out = Path("/workspace/orch02-r2/c05/frozen")
out.mkdir(parents=True, exist_ok=True)


def git(*args):
    return subprocess.check_output(["git", *args], cwd=repo)


def identity(ref, path):
    result = subprocess.run(["git", "show", f"{ref}:{path}"], cwd=repo, capture_output=True)
    if result.returncode:
        return None
    raw = result.stdout
    return {"blob": git("rev-parse", f"{ref}:{path}").decode().strip(), "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}


head = git("rev-parse", "HEAD").decode().strip()
tree = git("write-tree").decode().strip()
assert not git("diff", "--name-only")
changed = git("diff", "--name-only", head, tree).decode().splitlines()
patch = git("diff", "--binary", "--full-index", head, tree)
(out / "c05-typed-r2.patch").write_bytes(patch)
prior = json.loads(Path("/workspace/orch02-recovery/reviews/c05-source-binding-66151f3b.json").read_text())
dependency_paths = {row["path"] for row in prior["dependencies"]}
dependency_paths.update([
    "policy-engine/src/polisyos/fabric/connectors/__init__.py",
    "policy-engine/src/polisyos/fabric/connectors/profiles/__init__.py",
    "policy-engine/src/polisyos/core/artifacts/__init__.py",
    "policy-engine/src/polisyos/data_forge/domains/catalog/__init__.py",
    "policy-engine/src/polisyos/ir/connectors/__init__.py",
    "policy-engine/src/polisyos/fabric/connectors/sources/http_base.py",
    "policy-engine/src/polisyos/fabric/connectors/sources/world_bank.py",
    "policy-engine/src/polisyos/fabric/connectors/sources/eurostat.py",
    "policy-engine/src/polisyos/fabric/connectors/sources/sdmx_source.py",
    "policy-engine/src/polisyos/fabric/connectors/sources/unesco_uis.py",
    "policy-engine/src/polisyos/data_forge/domains/catalog/batch/_core_sources_ingest_contracts.py",
    "policy-engine/architecture/tooling/mypy/generated.ini",
    "policy-engine/pyproject.toml",
    "policy-engine/architecture/imports/policy.toml",
    "policy-engine/architecture/packages/boundaries.toml",
])
refs = {"CAT": prior["base"], "DFI": "ab44166335130463178e65dfc29a252c96afe479", "r1_source": prior["source"], "r2_parent": head, "r2_tree": tree, "G": "dee58973f7673299070b7c7374f419b0adb8175c"}
rows = []
for path in sorted(dependency_paths | set(changed)):
    rows.append({"path": path, "changed_r2": path in changed, "declared_dependency": path in dependency_paths, "identities": {label: identity(ref, path) for label, ref in refs.items()}})
tests = "policy-engine/tests/unit/remediation/test_dfi_03.py"
old = ast.parse(git("show", f"{head}:{tests}"))
new = ast.parse(git("show", f"{tree}:{tests}"))
old_functions = {node.name: ast.dump(node, include_attributes=False) for node in old.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}
new_functions = {node.name: ast.dump(node, include_attributes=False) for node in new.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}
changed_old = [name for name in old_functions if new_functions.get(name) != old_functions[name]]
assert changed_old == []
document = {
    "schema": "policyos.e02.c05.typed-r2-author-freeze.v1", "producer": "/root/c05_writer",
    "refs": refs, "branch": git("branch", "--show-current").decode().strip(), "changed_paths": changed,
    "patch_sha256": hashlib.sha256(patch).hexdigest(), "patch_bytes": len(patch),
    "dependency_denominator": len(dependency_paths), "all_binding_rows": rows,
    "old_test_ast": {"count": len(old_functions), "changed": changed_old, "added": sorted(set(new_functions) - set(old_functions))},
    "DFI_is_CAT_ancestor": subprocess.run(["git", "merge-base", "--is-ancestor", refs["DFI"], refs["CAT"]], cwd=repo).returncode == 0,
    "complete_DFI_CAT_DAG_existing_ref": "/workspace/orch02-recovery/reviews/c05-independent-source-DAG-66151f3b.json",
    "G_proposal_lane": {"path": "/workspace/orch02-c05-r2-gproposal", "branch": "codex/e02-C-orch02-c05-r2-gproposal", "base": refs["G"], "state": "clean_admitted_port_pending"},
    "quality": "strict isolated-stub source PASS, shared-profile missing stubs and architecture FAIL separately captured; no inherited gate classification",
    "native": "r1 112 remains qualified to 66151f3b only; r2 independent affected wave pending nonauthor GO",
}
(out / "source-freeze.json").write_text(json.dumps(document, indent=2) + "\n")
print(json.dumps({key: document[key] for key in ("refs", "changed_paths", "dependency_denominator", "patch_sha256", "old_test_ast")}, indent=2))
