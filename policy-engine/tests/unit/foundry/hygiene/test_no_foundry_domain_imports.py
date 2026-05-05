from __future__ import annotations

import ast
from pathlib import Path


def test_foundry_tree_has_no_domain_imports_outside_domain() -> None:
    repo_root = Path(__file__).resolve().parents[4]
    foundry_root = repo_root / "src" / "polisyos" / "foundry"
    domain_root = foundry_root / "domain"

    violations: list[str] = []
    for file_path in sorted(foundry_root.rglob("*.py")):
        if domain_root in file_path.parents:
            continue

        rel_path = file_path.relative_to(repo_root)
        module = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(rel_path))

        for node in ast.walk(module):
            if isinstance(node, ast.ImportFrom) and node.module:
                if node.module == "polisyos.foundry.domain" or node.module.startswith(
                    "polisyos.foundry.domain."
                ):
                    violations.append(f"{rel_path}:{node.lineno} from {node.module}")

            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "polisyos.foundry.domain" or alias.name.startswith(
                        "polisyos.foundry.domain."
                    ):
                        violations.append(f"{rel_path}:{node.lineno} import {alias.name}")

    assert not violations, "Found forbidden foundry -> foundry.domain imports:\n" + "\n".join(
        violations
    )
