#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from tools._lib.imports import ensure_repo_import_roots

REPO_ROOT_DEFAULT, SRC_ROOT = ensure_repo_import_roots(__file__)

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


# ---------------------------------------------------------------------------
# Phase 9.2 — Cross-reference lint checks
# ---------------------------------------------------------------------------


def _camel_to_snake(name: str) -> str:
    s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


def _extract_base_name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _check_constraint_slots_have_state_path(repo_root: Path) -> list[Violation]:
    """Verify every constraint with a slot_id references a valid slot with state_path."""
    try:
        from polisyos.ir.kernel import DEFAULT_CONSTRAINT_REGISTRY, DEFAULT_SLOT_REGISTRY
    except ImportError as exc:
        return [
            Violation(
                path=repo_root / "src" / "polisyos" / "ir" / "kernel",
                lineno=1,
                message=f"degraded: cannot import IR kernel registries: {exc}",
            )
        ]

    violations: list[Violation] = []
    constraints_file = repo_root / "src" / "polisyos" / "ir" / "kernel" / "constraints.py"

    for cid, cspec in DEFAULT_CONSTRAINT_REGISTRY.constraints.items():
        if cspec.slot_id is None:
            continue
        slot = DEFAULT_SLOT_REGISTRY.slots.get(cspec.slot_id)
        if slot is None:
            violations.append(Violation(
                path=constraints_file,
                lineno=1,
                message=f"constraint '{cid}' references unknown slot '{cspec.slot_id}'",
            ))
        elif not slot.state_path:
            violations.append(Violation(
                path=constraints_file,
                lineno=1,
                message=f"constraint '{cid}' slot '{cspec.slot_id}' has no state_path",
            ))
    return violations


def _check_mechanisms_registered(repo_root: Path) -> list[Violation]:
    """Verify mechanism classes in foundry/mechanisms/ have kernel registry entries."""
    try:
        from polisyos.ir.kernel import DEFAULT_MECHANISM_REGISTRY
    except ImportError as exc:
        return [
            Violation(
                path=repo_root / "src" / "polisyos" / "ir" / "kernel",
                lineno=1,
                message=f"degraded: cannot import mechanism registry: {exc}",
            )
        ]

    mechanisms_dir = repo_root / "src" / "polisyos" / "foundry" / "mechanisms"
    if not mechanisms_dir.exists():
        return []

    registered_ids = set(DEFAULT_MECHANISM_REGISTRY.mechanisms.keys())
    violations: list[Violation] = []

    for py_file in sorted(mechanisms_dir.glob("*.py")):
        if py_file.name.startswith("_") or py_file.name == "__init__.py":
            continue
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            for base in node.bases:
                base_name = _extract_base_name(base)
                if not base_name or "Mechanism" not in base_name:
                    continue
                # Strip "Mechanism" suffix before converting to snake_case
                class_name = node.name
                if class_name.endswith("Mechanism") and class_name != "Mechanism":
                    class_name = class_name[: -len("Mechanism")]
                inferred_id = _camel_to_snake(class_name)
                if inferred_id not in registered_ids:
                    violations.append(Violation(
                        path=py_file,
                        lineno=node.lineno,
                        message=(
                            f"mechanism class '{node.name}' (inferred id '{inferred_id}') "
                            f"not found in DEFAULT_MECHANISM_REGISTRY"
                        ),
                    ))
                break  # only check first matching base
    return violations


def _check_input_binding_slot_refs(repo_root: Path) -> list[Violation]:
    """Verify hardcoded target_slot_id values in bindings reference existing slots."""
    try:
        from polisyos.ir.kernel import DEFAULT_SLOT_REGISTRY
    except ImportError as exc:
        return [
            Violation(
                path=repo_root / "src" / "polisyos" / "ir" / "kernel",
                lineno=1,
                message=f"degraded: cannot import slot registry: {exc}",
            )
        ]

    bindings_path = repo_root / "src" / "polisyos" / "foundry" / "data_plane" / "bindings.py"
    if not bindings_path.exists():
        return []

    valid_slots = set(DEFAULT_SLOT_REGISTRY.slots.keys())
    tree = ast.parse(bindings_path.read_text(encoding="utf-8"), filename=str(bindings_path))
    violations: list[Violation] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.keyword):
            continue
        if node.arg != "target_slot_id":
            continue
        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            slot_id = node.value.value
            if slot_id not in valid_slots:
                violations.append(Violation(
                    path=bindings_path,
                    lineno=node.value.lineno,
                    message=f"input binding references non-existent slot '{slot_id}'",
                ))
    return violations


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Enforce P8 Foundry data-plane invariants.")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=REPO_ROOT_DEFAULT,
        help="Repository root",
    )
    args = parser.parse_args(argv)
    repo_root = args.repo_root.resolve()

    violations: list[Violation] = []
    violations.extend(_scan_state_snapshot_assumptions(repo_root))
    violations.extend(_check_workflow_has_p8_nodes(repo_root))
    violations.extend(_check_fabric_adapter_exists(repo_root))
    violations.extend(_check_constraint_slots_have_state_path(repo_root))
    violations.extend(_check_mechanisms_registered(repo_root))
    violations.extend(_check_input_binding_slot_refs(repo_root))

    if violations:
        print("lint_foundry_data_plane: violations found:")
        for violation in violations:
            print(f"  - {violation.render(repo_root)}")
        return 1

    print("lint_foundry_data_plane: all checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
