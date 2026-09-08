"""Observe the complete real deep-import owner and independent AST/file identities."""

# ruff: noqa: S101, T201 - bounded forensic observer, never writes an owned artifact

import ast
import hashlib
import json
import os
import sys
import tomllib
from dataclasses import asdict
from pathlib import Path

root = Path(sys.argv[1]).resolve()
output = Path(sys.argv[2]).resolve()
sys.path.insert(0, str(root / "src"))
sys.path.insert(0, str(root))
from tools.devx.architecture import guardrails as owner  # noqa: E402

assert root == owner.REPO_ROOT
policies = owner._parse_public_surface(owner.DEFAULT_PUBLIC_MANIFEST)
source_files = owner._iter_py_files()
walk_files = sorted(
    Path(folder) / name
    for folder, folders, names in os.walk(root / "src")
    if "__pycache__" not in Path(folder).parts
    for name in names
    if name.endswith(".py")
)
assert source_files == walk_files
manifest = tomllib.loads(owner.DEFAULT_PUBLIC_MANIFEST.read_text())
allowed = {entry for package in manifest["package"] for entry in package["supported_entrypoints"]}
independent = {}
ambiguous = []
inputs = {}


class Imports(ast.NodeVisitor):
    """Resolve all static import statements independently of the owner's ast.walk."""

    def __init__(self, path: Path) -> None:
        self.path = path
        relative = path.relative_to(root / "src").with_suffix("")
        parts = list(relative.parts)
        self.package = parts[-1] == "__init__"
        if self.package:
            parts.pop()
        self.module = ".".join(parts)
        self.parts = parts

    def admit(self, target: str) -> None:
        parts = target.split(".")
        if len(self.parts) < 2 or self.parts[0] != "polisyos":
            return
        if len(parts) < 2 or parts[0] != "polisyos":
            return
        if parts[1] == self.parts[1] or len(parts) == 2 or target in allowed:
            return
        row = {
            "source_module": self.module,
            "source_root": self.parts[1],
            "source_file": str(self.path.relative_to(root)),
            "target_module": target,
            "target_root": parts[1],
        }
        independent[self.module + "->" + target] = row

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self.admit(alias.name)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if not node.level:
            if node.module:
                self.admit(node.module)
            return
        package = self.parts if self.package else self.parts[:-1]
        if node.level - 1 > len(package):
            return
        prefix = package[: len(package) - node.level + 1]
        if node.module:
            prefix += node.module.split(".")
        self.admit(".".join(prefix))


for path in walk_files:
    try:
        content = path.read_bytes()
        inputs[str(path.relative_to(root))] = hashlib.sha256(content).hexdigest()
        Imports(path).visit(ast.parse(content, filename=str(path)))
    except (OSError, SyntaxError, UnicodeError) as exc:
        ambiguous.append({"path": str(path), "error": repr(exc)})
for relative in (
    "architecture/public_surface/contract.toml",
    "architecture/baselines/imports/deep_import.json",
    "tools/devx/architecture/guardrails.py",
    "tools/lib/imports.py",
):
    inputs[relative] = hashlib.sha256((root / relative).read_bytes()).hexdigest()
edges = owner.collect_deep_import_edges(policies)
expected_text = owner.render_deep_import_baseline_json(edges)
frozen_text = owner.DEFAULT_DEEP_IMPORT_BASELINE.read_text()
expected = {edge.key: asdict(edge) for edge in edges}
frozen_payload = json.loads(frozen_text)
frozen = {
    row["source_module"] + "->" + row["target_module"]: row for row in frozen_payload["edges"]
}
assert len(frozen) == len(frozen_payload["edges"])
assert expected == independent
packet = {
    "root": str(root),
    "owner_module_file": owner.__file__,
    "denominator": (
        "Complete owner src/**/*.py AST import set; independent os.walk and NodeVisitor; "
        "public entrypoints from the full contract.toml package set."
    ),
    "source_file_identities": [str(path.relative_to(root)) for path in source_files],
    "independent_file_identities": [str(path.relative_to(root)) for path in walk_files],
    "complete_observed_input_hashes": inputs,
    "ambiguous": ambiguous,
    "complete_owner_expected_identities": expected,
    "complete_independent_expected_identities": independent,
    "complete_frozen_identities": frozen,
    "expected_absent_from_frozen": sorted(expected.keys() - frozen.keys()),
    "frozen_absent_from_expected": sorted(frozen.keys() - expected.keys()),
    "same_identity_value_drift": sorted(
        key for key in frozen.keys() & expected.keys() if frozen[key] != expected[key]
    ),
    "actual_owner_creep_findings": [
        asdict(item)
        for item in owner._check_deep_import_creep(
            baseline_path=owner.DEFAULT_DEEP_IMPORT_BASELINE, current_edges=edges
        )
    ],
    "actual_owner_baseline_equal": frozen_text == expected_text,
    "actual_owner_complete_diff": owner._diff(
        "architecture/baselines/imports/deep_import.json", expected_text, frozen_text
    ),
    "actual_expected_artifact": json.loads(expected_text),
    "frozen_artifact": frozen_payload,
}
output.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n")
print(
    json.dumps(
        {
            "evidence": str(output),
            "owner_module": owner.__file__,
            "ambiguous": ambiguous,
            "actual_owner_baseline_equal": packet["actual_owner_baseline_equal"],
            "expected_absent_from_frozen": packet["expected_absent_from_frozen"],
            "frozen_absent_from_expected": packet["frozen_absent_from_expected"],
            "actual_owner_creep_findings": packet["actual_owner_creep_findings"],
        },
        indent=2,
    )
)
raise SystemExit(2 if ambiguous else (0 if frozen_text == expected_text else 1))
