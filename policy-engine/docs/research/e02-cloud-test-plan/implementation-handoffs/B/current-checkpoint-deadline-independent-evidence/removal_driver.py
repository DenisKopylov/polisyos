"""Replay real filesystem oracles after one explicit in-memory source removal."""

from __future__ import annotations

import ast
import hashlib
import inspect
import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

import polisyos.scientist.orchestration.engine.async_executor as executor_module
import polisyos.scientist.orchestration.engine.checkpoint as checkpoint_module

case, expected_sha, product, test, scratch, xml = sys.argv[1:]
product_root = Path(product).resolve()
actual_sha = subprocess.check_output(
    ["git", "-C", str(product_root.parent), "rev-parse", "HEAD"], text=True
).strip()
assert actual_sha == expected_sha
assert Path(checkpoint_module.__file__).resolve().is_relative_to(product_root)
assert Path(executor_module.__file__).resolve().is_relative_to(product_root)
changes: list[dict[str, object]] = []


class _GuardRemoval(ast.NodeTransformer):
    def __init__(self, *, drop_budget: bool) -> None:
        self.drop_budget = drop_budget
        self.removed = 0

    def visit_If(self, node: ast.If) -> ast.AST | list[ast.stmt]:
        if not self.drop_budget and ast.unparse(node.test) == "budget is not None":
            assert len(node.body) == 1
            call = node.body[0]
            assert isinstance(call, ast.Expr) and isinstance(call.value, ast.Call)
            assert ast.unparse(call.value.func) == "budget.require_active"
            self.removed += 1
            return []
        return self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> ast.AST:
        if self.drop_budget and any(
            isinstance(target, ast.Name) and target.id == "checkpoint_budget"
            for target in node.targets
        ):
            assert isinstance(node.value, ast.Call)
            assert ast.unparse(node.value.func) == "CheckpointPublicationBudget"
            node.value = ast.Constant(value=None)
            self.removed += 1
        return self.generic_visit(node)


def _replace(function, module, *, drop_budget: bool):
    source = textwrap.dedent(inspect.getsource(function))
    tree = ast.parse(source)
    removal = _GuardRemoval(drop_budget=drop_budget)
    tree = ast.fix_missing_locations(removal.visit(tree))
    assert removal.removed == (1 if drop_budget else 2)
    transformed = ast.unparse(tree)
    namespace = dict(vars(module))
    # Source overlay is explicitly recorded; the physical CAS, filesystem
    # operations and independent test input remain their real implementations.
    exec(
        compile("from __future__ import annotations\n" + transformed, module.__file__, "exec"),
        namespace,
    )
    changes.append(
        {
            "function": function.__qualname__,
            "source_sha256": hashlib.sha256(source.encode()).hexdigest(),
            "overlay_sha256": hashlib.sha256(transformed.encode()).hexdigest(),
            "removed_nodes": removal.removed,
            "overlay_source": transformed,
        }
    )
    return namespace[function.__name__]


selection = ""
if case == "head":
    checkpoint_module.update_checkpoint_head = _replace(
        checkpoint_module.update_checkpoint_head, checkpoint_module, drop_budget=False
    )
    selection = "head_fsync"
elif case == "gc":
    checkpoint_module.write_checkpoint_history = _replace(
        checkpoint_module.write_checkpoint_history, checkpoint_module, drop_budget=False
    )
    selection = "gc_read"
elif case == "budget":
    executor_module.AsyncWorkflowExecutor.execute = _replace(
        executor_module.AsyncWorkflowExecutor.execute, executor_module, drop_budget=True
    )
else:
    raise ValueError("Unknown removal class")
print(
    "CHECKPOINT_REMOVAL_OVERLAY="
    + json.dumps(
        {
            "case": case,
            "base_source_sha": expected_sha,
            "changes": changes,
            "qualification": "Explicit in-memory execution overlay; printed module file hashes name the base source, not the changed executable functions.",
        },
        sort_keys=True,
    ),
    flush=True,
)
argv = [
    "-q",
    "-s",
    "--noconftest",
    test,
    "-c",
    str(product_root / "pytest.ini"),
    "-o",
    "addopts=",
    "--basetemp",
    scratch,
    "--junitxml",
    xml,
]
if selection:
    argv.extend(["-k", selection])
raise SystemExit(pytest.main(argv))
