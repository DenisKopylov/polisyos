"""Process-local semantic removal witnesses; production source bytes remain untouched."""
from __future__ import annotations

import ast
import inspect
import json
import sys
import textwrap
from types import SimpleNamespace

import pytest

from polisyos.runtime.http.services.control import generation_cycle as bridge
from polisyos.runtime.http.services.control import run_lifecycle
from polisyos.runtime.quality.design_axes import value_choice_provenance as s8

mode = sys.argv[1]
base = "tests/unit/runtime/http/test_normative_generation_bridge.py::"
if mode == "default_call":
    original = run_lifecycle.ControlPlaneService._process_control_job
    tree = ast.parse(textwrap.dedent(inspect.getsource(original)))
    class RemoveDefault(ast.NodeTransformer):
        changed = 0
        def visit_Call(self, node):
            if isinstance(node.func, ast.Attribute) and node.func.attr == "resolve_generation_value_choices":
                self.changed += 1
                return ast.copy_location(ast.Call(func=ast.Name(id="_removed_default", ctx=ast.Load()), args=[], keywords=[]), node)
            return self.generic_visit(node)
    transform = RemoveDefault()
    tree = ast.fix_missing_locations(transform.visit(tree))
    assert transform.changed == 1
    namespace = dict(original.__globals__)
    namespace["_removed_default"] = lambda: SimpleNamespace(disposition_ref=None, model_dump=lambda **kwargs: {})
    exec(compile(tree, inspect.getsourcefile(original), "exec"), namespace)
    run_lifecycle.ControlPlaneService._process_control_job = namespace[original.__name__]
    nodes = ["tests/unit/runtime/http/test_control_service_di.py::test_process_nl_job_enters_persisted_tenant_scope[missing]"]
elif mode == "composition_replay":
    def stored_only(*, store, owner, disposition_ref, compiled_run_ref, evaluated_at):
        del owner, compiled_run_ref, evaluated_at
        return bridge.NormativeRunDisposition.model_validate(
            bridge._read_normative_source(store, disposition_ref, kind=bridge.NORMATIVE_RUN_DISPOSITION_KIND)
        ).model_copy(update={"disposition_ref": disposition_ref})
    bridge.project_normative_run_disposition = stored_only
    nodes = [base + "test_current_permission_expiry_overrides_persisted_green", base + "test_same_display_ids_do_not_bind_another_current_compiled_source"]
elif mode == "leaf_replay":
    def leaf_stored_only(self, disposition_ref, *, evaluated_at):
        del evaluated_at
        return s8.NormativeGenerationDisposition.model_validate(self._read(
            disposition_ref, kind=s8.NORMATIVE_GENERATION_DISPOSITION_KIND,
            schema=s8.NORMATIVE_GENERATION_DISPOSITION_SCHEMA_VERSION,
        ))
    s8.NormativeValueScheduleOwner.project_generation_disposition = leaf_stored_only
    nodes = [base + "test_silent_default_cannot_cross_leaf_and_composition_emission"]
elif mode == "signature":
    s8.NormativeValueScheduleOwner._require_signature = staticmethod(lambda signature: None)
    nodes = [base + "test_current_signature_corruption_revokes_recommendation"]
else:
    raise ValueError(mode)
print(json.dumps({"removal": mode, "mechanism": "process-local actual owner mutation; disk source and marker fields retained", "nodes": nodes}), flush=True)
raise SystemExit(pytest.main([*nodes, "-q"]))
