"""Replay real filesystem oracles after one explicit in-memory source removal."""

from __future__ import annotations

import ast
import hashlib
import inspect
import json
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import TYPE_CHECKING, cast

import pytest

import polisyos.scientist.orchestration.engine.async_executor as executor_module
import polisyos.scientist.orchestration.engine.checkpoint as checkpoint_module

if TYPE_CHECKING:
    from collections.abc import Callable
    from types import ModuleType

case, expected_sha, product, test, scratch, xml = sys.argv[1:]
product_root = Path(product).resolve()
git_executable = shutil.which("git")
if git_executable is None:
    raise RuntimeError("Git executable is unavailable")
# Fixed read-only argv and an admitted product root; no shell execution.
actual_sha = subprocess.check_output(  # noqa: S603
    [git_executable, "-C", str(product_root.parent), "rev-parse", "HEAD"], text=True
).strip()
if actual_sha != expected_sha:
    raise ValueError("Actual product HEAD differs from the frozen input")
for source_module in (checkpoint_module, executor_module):
    if source_module.__file__ is None:
        raise ValueError("Imported source module has no file origin")
    if not Path(source_module.__file__).resolve().is_relative_to(product_root):
        raise ValueError("Imported source module escaped the declared product root")
changes: list[dict[str, object]] = []


class _GuardRemoval(ast.NodeTransformer):
    def __init__(self, *, drop_budget: bool) -> None:
        self.drop_budget = drop_budget
        self.removed = 0

    def visit_If(self, node: ast.If) -> ast.AST | list[ast.stmt]:
        if not self.drop_budget and ast.unparse(node.test) == "budget is not None":
            if len(node.body) != 1:
                raise ValueError("Guard body changed from the frozen shape")
            call = node.body[0]
            if not isinstance(call, ast.Expr) or not isinstance(call.value, ast.Call):
                raise ValueError("Guard body is not the expected call")
            if ast.unparse(call.value.func) != "budget.require_active":
                raise ValueError("Guard no longer calls the original budget predicate")
            self.removed += 1
            return []
        return self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> ast.AST:
        if self.drop_budget and any(
            isinstance(target, ast.Name) and target.id == "checkpoint_budget"
            for target in node.targets
        ):
            if not isinstance(node.value, ast.Call):
                raise ValueError("Checkpoint budget assignment changed shape")
            if ast.unparse(node.value.func) != "CheckpointPublicationBudget":
                raise ValueError("Checkpoint budget assignment changed constructor")
            node.value = ast.Constant(value=None)
            self.removed += 1
        return self.generic_visit(node)


def _replace(
    function: Callable[..., object], module: ModuleType, *, drop_budget: bool
) -> Callable[..., object]:
    source = textwrap.dedent(inspect.getsource(function))
    tree = ast.parse(source)
    removal = _GuardRemoval(drop_budget=drop_budget)
    tree = ast.fix_missing_locations(removal.visit(tree))
    if removal.removed != (1 if drop_budget else 2):
        raise ValueError("The exact expected removal denominator was not reached")
    transformed = ast.unparse(tree)
    namespace = dict(vars(module))
    # Source overlay is explicitly recorded; the physical CAS, filesystem
    # operations and independent test input remain their real implementations.
    if module.__file__ is None:
        raise ValueError("Source module has no file origin")
    # Only immutable canonical source with the exact verified AST removal is executed.
    exec(  # noqa: S102
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
    return cast("Callable[..., object]", namespace[function.__name__])


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
sys.stdout.write(
    "CHECKPOINT_REMOVAL_OVERLAY="
    + json.dumps(
        {
            "case": case,
            "base_source_sha": expected_sha,
            "changes": changes,
            "qualification": (
                "Explicit in-memory execution overlay; printed module file hashes "
                "name the base source, not the changed executable functions."
            ),
        },
        sort_keys=True,
    )
    + "\n"
)
sys.stdout.flush()
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
