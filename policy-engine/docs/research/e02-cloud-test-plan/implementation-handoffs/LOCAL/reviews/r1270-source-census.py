#!/usr/bin/env python3
"""Reproduce the R1270 complete source/test/dashboard file census."""

from __future__ import annotations

import ast
from pathlib import Path

HERE = Path(__file__).resolve()
PRODUCT = next(
    parent
    for parent in HERE.parents
    if (parent / "src/polisyos").is_dir() and (parent / "apps/runtime-dashboard/src").is_dir()
)

SETS = {
    "product_py": (PRODUCT / "src", {".py"}),
    "product_pyi": (PRODUCT / "src", {".pyi"}),
    "tests_py": (PRODUCT / "tests", {".py"}),
    "dashboard_ts": (PRODUCT / "apps/runtime-dashboard/src", {".ts"}),
    "dashboard_tsx": (PRODUCT / "apps/runtime-dashboard/src", {".tsx"}),
}
READER_WRITER_NAMES = {
    "read_core_json_artifact",
    "read_core_json_artifact_bytes",
    "read_core_manifest_profile",
    "load_core_json_artifact",
    "load_core_json_frame_records",
    "aload_core_json_artifact",
    "validate_core_model_json_artifact",
    "get_json_artifact",
    "put_json_artifact",
}

summary: dict[str, object] = {
    "schema": "r1270-source-census-v1",
    "product_root": str(PRODUCT),
    "sets": {},
    "direct_lexical_calls": {},
    "limitations": [
        "AST direct-name/direct-attribute call count, not binding-resolved call graph",
        "no product modules imported and no runtime/test execution performed",
    ],
}
for label, (base, suffixes) in SETS.items():
    paths = sorted(path for path in base.rglob("*") if path.is_file() and path.suffix in suffixes)
    summary["sets"][label] = {"root": str(base), "count": len(paths)}
    if label != "product_py":
        continue
    syntax_errors: list[dict[str, object]] = []
    calls = {name: {"calls": 0, "files": 0} for name in sorted(READER_WRITER_NAMES)}
    for path in paths:
        try:
            tree = ast.parse(path.read_bytes(), filename=str(path))
        except SyntaxError as exc:
            syntax_errors.append({"path": str(path), "line": exc.lineno, "message": exc.msg})
            continue
        seen: set[str] = set()
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            function = node.func
            name = (
                function.id
                if isinstance(function, ast.Name)
                else function.attr
                if isinstance(function, ast.Attribute)
                else None
            )
            if name in calls:
                calls[name]["calls"] += 1
                seen.add(name)
        for name in seen:
            calls[name]["files"] += 1
    summary["product_py_ast_syntax_errors"] = syntax_errors
    summary["direct_lexical_calls"] = calls
