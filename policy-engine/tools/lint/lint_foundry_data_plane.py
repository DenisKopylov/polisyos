#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT_DEFAULT = Path(__file__).resolve().parent.parent.parent

ASSUMPTION_ALLOWLIST = {
    "src/polisyos/foundry/execute/api.py",
    "src/polisyos/foundry/data_plane/bindings.py",
    "src/polisyos/scientist/nodes/builtins/simulate/run_distributional_analysis.py",
    "src/polisyos/scientist/agent/feasibility.py",
}

WORKFLOW_PATH = Path("src/polisyos/scientist/workflows/default.py")
FABRIC_BRIDGE_PATH = Path("src/polisyos/scientist/adapters/fabric_bridge.py")


@dataclass(frozen=True)
class Violation:
    path: Path
    lineno: int
    message: str

    def render(self, repo_root: Path) -> str:
        try:
            rel = self.path.relative_to(repo_root)
        except ValueError:
            rel = self.path
        return f"{rel}:{self.lineno}: {self.message}"


class _StateSnapshotAssumptionVisitor(ast.NodeVisitor):
    def __init__(self, path: Path) -> None:
        self.path = path
        self.violations: list[Violation] = []

    def visit_Compare(self, node: ast.Compare) -> None:  # noqa: N802
        if not _contains_data_ref_kind(node):
            self.generic_visit(node)
            return
        if _contains_foundry_state_snapshot_literal(node):
            self.violations.append(
                Violation(
                    path=self.path,
                    lineno=node.lineno,
                    message=(
                        "hard-coded DataSnapshot.data_ref.kind == foundry.state_snapshot "
                        "outside compatibility boundary"
                    ),
                )
            )
        self.generic_visit(node)


def _contains_data_ref_kind(node: ast.AST) -> bool:
    for child in ast.walk(node):
        if isinstance(child, ast.Attribute) and child.attr == "kind":
            value = child.value
            if isinstance(value, ast.Attribute) and value.attr == "data_ref":
                return True
    return False


def _contains_foundry_state_snapshot_literal(node: ast.AST) -> bool:
    for child in ast.walk(node):
        if isinstance(child, ast.Constant) and child.value == "foundry.state_snapshot":
            return True
    return False


def _scan_state_snapshot_assumptions(repo_root: Path) -> list[Violation]:
    src_root = repo_root / "src"
    violations: list[Violation] = []
    for py_file in sorted(src_root.rglob("*.py")):
        rel = str(py_file.relative_to(repo_root)).replace("\\", "/")
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        visitor = _StateSnapshotAssumptionVisitor(py_file)
        visitor.visit(tree)
        if rel in ASSUMPTION_ALLOWLIST:
            continue
        violations.extend(visitor.violations)
    return violations


def _check_workflow_has_p8_nodes(repo_root: Path) -> list[Violation]:
    path = repo_root / WORKFLOW_PATH
    if not path.exists():
        return [Violation(path=path, lineno=1, message="default workflow file not found")]
    text = path.read_text(encoding="utf-8")
    required_aliases = ("alias=\"bind_foundry_inputs\"", "alias=\"run_data_plane_gate\"")
    violations: list[Violation] = []
    for alias in required_aliases:
        if alias not in text:
            violations.append(
                Violation(
                    path=path,
                    lineno=1,
                    message=f"default workflow missing required node alias: {alias}",
                )
            )
    return violations


def _check_fabric_adapter_exists(repo_root: Path) -> list[Violation]:
    path = repo_root / FABRIC_BRIDGE_PATH
    if not path.exists():
        return [
            Violation(
                path=path,
                lineno=1,
                message="missing FabricPort adapter (fabric_bridge.py)",
            )
        ]
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    has_snapshot_method = False
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        for item in node.body:
            if isinstance(item, ast.FunctionDef) and item.name == "snapshot":
                has_snapshot_method = True
                break
        if has_snapshot_method:
            break
    if has_snapshot_method:
        return []
    return [
        Violation(
            path=path,
            lineno=1,
            message="Fabric adapter class does not implement snapshot(...)",
        )
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Enforce P8 Foundry data-plane invariants.")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=REPO_ROOT_DEFAULT,
        help="Repository root",
    )
    args = parser.parse_args()
    repo_root = args.repo_root.resolve()

    violations: list[Violation] = []
    violations.extend(_scan_state_snapshot_assumptions(repo_root))
    violations.extend(_check_workflow_has_p8_nodes(repo_root))
    violations.extend(_check_fabric_adapter_exists(repo_root))

    if violations:
        print("lint_foundry_data_plane: violations found:")
        for violation in violations:
            print(f"  - {violation.render(repo_root)}")
        return 1

    print("lint_foundry_data_plane: all checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
