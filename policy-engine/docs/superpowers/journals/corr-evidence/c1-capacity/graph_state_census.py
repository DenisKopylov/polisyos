"""Walk the complete graph-owner Python state denominator; no provider or credentials."""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

OWNER_ROOT = Path("src/polisyos/data_forge/domains/academic/batch")
OWNERS = ("graph_builder.py", "edge_synthesize.py", "_graph_staging.py")


def census(path: Path) -> dict[str, object]:
    source = path.read_bytes()
    tree = ast.parse(source)
    parents = {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}
    assignments = []
    file_output_calls = []
    mutable_expressions = 0
    for node in ast.walk(tree):
        call = ast.unparse(node.func) if isinstance(node, ast.Call) else ""
        if isinstance(node, ast.Call) and call.rsplit(".", 1)[-1] in {
            "open",
            "write",
            "write_text",
            "write_bytes",
            "dump",
            "text_output",
            "publish_output",
            "publish_owned_output",
            "write_stage_manifest",
            "atomic_commit_path",
        }:
            parent = node
            while parent in parents and not isinstance(
                parent, (ast.FunctionDef, ast.AsyncFunctionDef)
            ):
                parent = parents[parent]
            file_output_calls.append(
                {
                    "line": node.lineno,
                    "function": getattr(parent, "name", "<module>"),
                    "call": call,
                    "arguments": [ast.unparse(arg) for arg in node.args],
                }
            )
        if (
            isinstance(node, (ast.Dict, ast.List, ast.Set, ast.DictComp, ast.ListComp, ast.SetComp))
            or call in {"dict", "list", "set", "Counter", "defaultdict"}
            or call.endswith((".fetchall", ".rows", ".groups", ".values", ".counts"))
        ):
            mutable_expressions += 1
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)) or node.value is None:
            continue
        value = node.value
        call = ast.unparse(value.func) if isinstance(value, ast.Call) else ""
        selected = (
            isinstance(
                value, (ast.Dict, ast.List, ast.Set, ast.DictComp, ast.ListComp, ast.SetComp)
            )
            or call in {"dict", "list", "set", "Counter", "defaultdict"}
            or call.endswith((".fetchall", ".rows", ".groups", ".values", ".counts"))
        )
        if not selected:
            continue
        parent = node
        while parent in parents and not isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef)):
            parent = parents[parent]
        targets = [node.target] if isinstance(node, ast.AnnAssign) else node.targets
        assignments.append(
            {
                "line": node.lineno,
                "function": getattr(parent, "name", "<module>"),
                "target": ",".join(ast.unparse(target) for target in targets),
                "initializer": type(value).__name__,
                "call": call,
            }
        )
    schemas = {}
    classes = {}
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            schema = ast.dump(
                ast.ClassDef(
                    name=node.name,
                    bases=node.bases,
                    keywords=node.keywords,
                    body=[
                        item for item in node.body if isinstance(item, (ast.Assign, ast.AnnAssign))
                    ],
                    decorator_list=node.decorator_list,
                    type_params=node.type_params,
                ),
                include_attributes=False,
            )
            classes[node.name] = hashlib.sha256(schema.encode()).hexdigest()
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in {"_DDL", "_INDEXES"}:
                    schemas[target.id] = hashlib.sha256(str(node.value.value).encode()).hexdigest()
    return {
        "path": str(path),
        "file_type": ".py",
        "sha256": hashlib.sha256(source).hexdigest(),
        "assignment_count": len(assignments),
        "complete_mutable_expression_count": mutable_expressions,
        "assignments": sorted(assignments, key=lambda r: r["line"]),
        "file_output_call_index": sorted(file_output_calls, key=lambda r: r["line"]),
        "schema_literal_fingerprints": schemas,
        "complete_owned_class_field_fingerprints": classes,
    }


def main() -> None:
    print(  # noqa: T201 - captured complete source census.
        json.dumps(
            {
                "synthetic": True,
                "scope": "source_census_not_runtime_authority",
                "path_denominator": [str(OWNER_ROOT / owner) for owner in OWNERS],
                "file_type_denominator": ".py",
                "limitation": (
                    "AST assignments are a candidate census; aliases and called owners "
                    "require the accompanying manual reconciliation."
                ),
                "owners": [census(OWNER_ROOT / owner) for owner in OWNERS],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
