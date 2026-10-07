"""Remove accumulated-issue retention in memory while keeping public markers/ABI."""

import ast
import inspect
import json
import textwrap

import pytest

from polisyos.scientist.governance.passes.confidence_pass import ConfidencePass

original = ConfidencePass.validate
source = textwrap.dedent(inspect.getsource(original))
tree = ast.parse(source)
matched = []
for handler in ast.walk(tree):
    if not isinstance(handler, ast.ExceptHandler) or len(handler.body) < 2:
        continue
    append, terminal = handler.body[-2:]
    if not (
        isinstance(append, ast.Expr)
        and isinstance(append.value, ast.Call)
        and isinstance(append.value.func, ast.Attribute)
        and isinstance(append.value.func.value, ast.Name)
        and append.value.func.value.id == "issues"
        and append.value.func.attr == "append"
        and isinstance(terminal, ast.Return)
        and isinstance(terminal.value, ast.Name)
        and terminal.value.id == "issues"
    ):
        continue
    handler.body[-2:] = [ast.Return(value=ast.List(elts=append.value.args, ctx=ast.Load()))]
    matched.append(handler.lineno)
assert len(matched) == 1, matched
ast.fix_missing_locations(tree)
namespace = {}
exec(compile(tree, original.__code__.co_filename, "exec"), original.__globals__, namespace)
original.__code__ = namespace[original.__name__].__code__
assert ConfidencePass.validate is original
print(json.dumps({
    "control": "replace accumulated issues with only the same degraded warning",
    "changed_in_memory_only": True,
    "class": f"{ConfidencePass.__module__}.{ConfidencePass.__qualname__}",
    "method_identity_retained": ConfidencePass.validate is original,
    "signature": str(inspect.signature(original)),
    "preserved": ["class", "method object", "issue codes", "issue types", "source labels",
                  "gate thresholds", "artifact reference values", "degraded-path emission"],
}, sort_keys=True))
raise SystemExit(pytest.main([
    "tests/unit/scientist/governance/test_confidence_issue_accumulation.py::"
    "test_simulation_load_failure_preserves_causal_blocker_and_warning"
    "[0.0-artifacts_index-missing_bytes]",
    "-o", "addopts=", "-q", "-ra",
    "--basetemp=/tmp/e02-F-continuation-20261006/confidence-issue-preservation/removal-tmp",
]))
