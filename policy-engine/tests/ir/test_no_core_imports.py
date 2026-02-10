from __future__ import annotations

import ast
from pathlib import Path


def test_ir_tree_has_no_core_imports() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    ir_root = repo_root / "src" / "polisyos" / "ir"

    violations: list[str] = []
    for file_path in sorted(ir_root.rglob("*.py")):
        rel_path = file_path.relative_to(repo_root)
        module = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(rel_path))
        for node in ast.walk(module):
            if isinstance(node, ast.ImportFrom) and node.module:
                if node.module == "polisyos.core" or node.module.startswith("polisyos.core."):
                    violations.append(f"{rel_path}:{node.lineno} from {node.module}")
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "polisyos.core" or alias.name.startswith("polisyos.core."):
                        violations.append(f"{rel_path}:{node.lineno} import {alias.name}")

    assert not violations, "Found forbidden ir -> core imports:\n" + "\n".join(violations)
