"""Actual marker-retaining removal at the original run/sentinel transition owner."""

import ast
import inspect
import os
import textwrap


class _Remove(ast.NodeTransformer):
    def __init__(self, profile):
        self.profile = profile
        self.count = 0

    def visit_Assign(self, node):
        target = node.targets[0] if len(node.targets) == 1 else None
        if (
            self.profile == "run_reset"
            and isinstance(target, ast.Attribute)
            and isinstance(target.value, ast.Name)
            and target.value.id == "self"
            and target.attr == "_run_state"
            and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Name)
            and node.value.func.id == "SearchRunState"
        ):
            self.count += 1
            # Retain fresh declared run/status markers and all actual warm,
            # resource and stopping owner calls, but remove owned per-run state.
            return ast.parse(
                "self._run_state.search_id = search_id\n"
                "self._run_state.status = SearchStatus.RUNNING\n"
            ).body
        if (
            self.profile == "sentinel"
            and isinstance(target, ast.Name)
            and target.id == "is_sentinel"
            and isinstance(node.value, ast.Compare)
            and isinstance(node.value.left, ast.Call)
            and isinstance(node.value.left.func, ast.Name)
            and node.value.left.func.id == "extract_sentinel_metadata"
        ):
            self.count += 1
            node.value = ast.Constant(value=False)
        return self.generic_visit(node)


def pytest_runtest_setup(item):
    if item.originalname != (
        "test_two_paid_runs_on_same_controller_match_fresh_controllers_with_scoped_sentinels"
    ):
        return
    from polisyos.scientist.methods.search.controller import SearchController

    profile = os.environ["E02_CONTROLLER_REMOVAL_PROFILE"]
    assert profile in {"run_reset", "sentinel"}
    name = "_begin_native_run" if profile == "run_reset" else "_accept_tell"
    original = getattr(SearchController, name)
    tree = ast.parse(textwrap.dedent(inspect.getsource(original)))
    edit = _Remove(profile)
    tree = ast.fix_missing_locations(edit.visit(tree))
    assert edit.count == 1, (profile, edit.count)
    scope = {}
    exec(compile(tree, original.__code__.co_filename, "exec"), original.__globals__, scope)
    changed = scope[name]
    changed.__module__ = original.__module__
    changed.__qualname__ = original.__qualname__
    setattr(SearchController, name, changed)
    print("actual_controller_transition_removal", profile, edit.count)
