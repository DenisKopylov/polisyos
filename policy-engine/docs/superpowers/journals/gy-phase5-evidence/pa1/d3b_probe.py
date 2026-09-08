"""Remove temporal attachment/publication while retaining recorded head and producer markers."""
from __future__ import annotations

import ast
import inspect
import json
import textwrap
import sys

import pytest

from polisyos.runtime.http.services.control.run_lifecycle import ControlPlaneService
from polisyos.runtime.http.services.control_plane_store import ControlPlaneStore

mode = sys.argv[1]
node = "tests/unit/runtime/http/test_normative_evidence_intake.py::test_post_source_signature_advances_both_current_job_readers"
if mode == "head_attachment":
    ControlPlaneStore.get_normative_evidence_head = lambda self, job_id: None
elif mode == "owned_run_publication":
    ControlPlaneService._publish_generation_run = lambda self, **kwargs: "sha256:" + "0" * 64
elif mode == "head_binding":
    original = ControlPlaneService._current_normative_job_record
    tree = ast.parse(textwrap.dedent(inspect.getsource(original)))

    class RemoveBinding(ast.NodeTransformer):
        changed = 0

        def visit_If(self, value):
            if any(
                isinstance(item, ast.Constant)
                and item.value == "normative_head_source_binding_mismatch"
                for statement in value.body for item in ast.walk(statement)
            ) and any(isinstance(statement, ast.Raise) for statement in value.body):
                self.changed += 1
                value.test = ast.Constant(False)
                return value
            return self.generic_visit(value)

    transform = RemoveBinding()
    mutated = ast.fix_missing_locations(transform.visit(tree))
    assert transform.changed == 1
    namespace = dict(original.__globals__)
    exec(compile(mutated, inspect.getsourcefile(original), "exec"), namespace)
    ControlPlaneService._current_normative_job_record = namespace[original.__name__]
else:
    raise ValueError(mode)
print(json.dumps({
    "removal": mode,
    "mechanism": "Process-local owner replacement; head contract, signed producer, event append, markers and disk source remain intact",
    "node": node,
}), flush=True)
nodes = [node]
if mode == "head_binding":
    nodes.append("tests/unit/runtime/http/test_normative_evidence_intake.py::test_current_head_replays_all_source_bindings_and_preserves_refusal_frontier[job_id]")
raise SystemExit(pytest.main([*nodes, "-q"]))
