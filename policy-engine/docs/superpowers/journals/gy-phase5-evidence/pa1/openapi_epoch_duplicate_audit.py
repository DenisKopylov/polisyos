"""Measure the preexisting overwritten epoch example without changing its owner."""
# ruff: noqa: S603, T201 - read-only source/history research witness
from __future__ import annotations

import ast
import json
import subprocess
from pathlib import Path

root = Path.cwd()
path = Path("src/polisyos/runtime/http/openapi_contract.py")
source = path.read_text()
tree = ast.parse(source)
mapping = next(
    node.value for node in tree.body
    if isinstance(node, ast.AnnAssign)
    and isinstance(node.target, ast.Name)
    and node.target.id == "_SUCCESS_EXAMPLES_BY_OPERATION"
)
entries = [
    {"line": key.lineno, "key": key.value, "expression": ast.get_source_segment(source, value)}
    for key, value in zip(mapping.keys, mapping.values, strict=True)
    if isinstance(key, ast.Constant) and key.value == "admit_epoch_validity_batch"
]
function = next(
    node for node in tree.body
    if isinstance(node, ast.FunctionDef) and node.name == "_epoch_validity_batch_example"
)
history_commands = [
    ["git", "log", "--format=%H %s", "-S",
     '"admit_epoch_validity_batch": _epoch_validity_batch_example()', "--", str(path)],
    ["git", "log", "--format=%H %s", "-S", '"epoch-validity-batch-001"', "--", str(path)],
]
history = []
for command in history_commands:
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    history.append({
        "argv": command, "cwd": str(root), "returncode": result.returncode,
        "stdout": result.stdout, "stderr": result.stderr,
    })
print(json.dumps({
    "owner_file": str(path),
    "complete_mapping_duplicate_key_entries": entries,
    "helper_full_source": ast.get_source_segment(source, function),
    "helper_all_call_expressions": [
        ast.get_source_segment(source, node.func)
        for node in ast.walk(function) if isinstance(node, ast.Call)
    ],
    "history": history,
    "disposition": "Unchanged pending root's executed-task scope decision; not excluded from Ruff",
}, indent=2))
