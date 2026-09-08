"""Restore only the pre-repair loop consumer; keep current contract markers."""

import ast
import subprocess

import pytest

from polisyos.runtime.quality.workspace import loop
from polisyos.runtime.quality.workspace.scientist_node_adapters import ScientistNodeAdapter

BASE = "43580c80b8761d4aecb34ee3300f64d389be80c8"
PATH = "policy-engine/src/polisyos/runtime/quality/workspace/loop.py"
source = subprocess.run(
    ["git", "show", f"{BASE}:{PATH}"], check=True, capture_output=True, text=True,
).stdout
tree = ast.parse(source)
owner = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "WorkspaceLoop")
method = next(n for n in owner.body if isinstance(n, ast.FunctionDef) and n.name == "run_intent")
namespace = loop.__dict__
namespace["ScientistNodeAdapter"] = ScientistNodeAdapter
exec(compile(ast.Module(body=[method], type_ignores=[]), f"{PATH}@{BASE}", "exec"), namespace)
loop.WorkspaceLoop.run_intent = namespace["run_intent"]
print(f"REMOVAL: restored {PATH}@{BASE}:WorkspaceLoop.run_intent only; current adapter and projection markers retained")
raise SystemExit(pytest.main([
    "-q", "--tb=short",
    "tests/unit/runtime/quality/test_workspace_workflow_playbook_projection.py::"
    "test_loop_refuses_nonproducing_node_before_operation_or_foundry_consumption",
]))
