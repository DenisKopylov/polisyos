"""Reconcile complete production AST constructor/forwarding identities for N8 source input."""
from __future__ import annotations

import ast
import json
import os
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[5]
    source = root / "src"
    paths = {path.relative_to(root).as_posix() for path in source.rglob("*.py")}
    independently = {Path(folder, name).relative_to(root).as_posix()
                     for folder, _dirs, names in os.walk(source)
                     for name in names if name.endswith(".py")}
    first, second, rows, ambiguous = set(), set(), [], []
    names = {"FoundryValuePort", "_DefaultSimulationBoundFoundryValuePort"}

    def relevant(node: ast.AST) -> bool:
        if not isinstance(node, ast.Call):
            return False
        name = getattr(node.func, "id", getattr(node.func, "attr", ""))
        return name in names or any(keyword.arg == "observation_to_contract_manifest"
                                    for keyword in node.keywords)

    for relative in sorted(paths):
        text = (root / relative).read_text()
        try:
            tree = ast.parse(text)
        except (SyntaxError, UnicodeError) as exc:
            ambiguous.append({"path": relative, "reason": str(exc)})
            continue
        for node in ast.walk(tree):
            if relevant(node):
                first.add((relative, node.lineno, node.col_offset))
                rows.append({"path": relative, "line": node.lineno,
                             "column": node.col_offset, "source": ast.get_source_segment(text, node)})

        class Visitor(ast.NodeVisitor):
            def visit_Call(self, node: ast.Call) -> None:
                if relevant(node):
                    second.add((relative, node.lineno, node.col_offset))
                self.generic_visit(node)

        Visitor().visit(tree)
    print(json.dumps({"denominator": sorted(paths), "file_type": "src/**/*.py",
        "independent_file_difference": sorted(paths ^ independently),
        "calls": rows, "first_only": sorted(first-second), "second_only": sorted(second-first),
        "ambiguous": ambiguous,
        "limitation": "Complete syntactic production constructor and explicit manifest keyword calls. Dynamic kwargs are recorded at the actual default-wrapper reentry call and resolved by the same stored source sentinel, not presumed omitted."}, indent=2))
    assert paths == independently and first == second and not ambiguous


if __name__ == "__main__":
    main()
