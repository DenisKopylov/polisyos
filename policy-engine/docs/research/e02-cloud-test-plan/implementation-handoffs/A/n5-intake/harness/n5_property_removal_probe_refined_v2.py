"""Re-run the real N5/N8 test with one runtime property bypassed in memory.

Each run imports the candidate source from ``--project-root`` through a temporary
``sitecustomize`` hook. The hook changes only an AST condition in memory, keeps
its source markers, and is inherited by the producer/consumer subprocesses. It
never edits the checkout. Run one property per process so every regression is
attributed to a single removal.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


_PROPERTY_CHOICES = (
    "engine_selection",
    "sibling_receipt_hash",
    "explicit_empty_atoms",
    "point_outcome_distribution",
    "absent_atom_fallback",
    "casless_digest",
)

_SITE_CUSTOMIZE = r'''from __future__ import annotations

import ast
import os
import subprocess
import sys
from importlib.abc import Loader, MetaPathFinder
from importlib.machinery import PathFinder
from pathlib import Path

_PROPERTY = os.environ.get("N5_REMOVAL_PROPERTY", "")
_PROJECT_ROOT = Path(os.environ["N5_REMOVAL_PROJECT_ROOT"]).resolve()
_EXPECTED_SOURCE = (
    _PROJECT_ROOT / "src/polisyos/runtime/quality/generation_cycle.py"
).resolve()
_REAL_RUN = subprocess.run


def _inherit_hook(*args, **kwargs):
    env = dict(kwargs.get("env") or os.environ)
    hook_dir = os.environ.get("N5_REMOVAL_HOOK_DIR")
    if hook_dir:
        existing = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = os.pathsep.join(
            part for part in (hook_dir, existing) if part
        )
        env["N5_REMOVAL_PROPERTY"] = _PROPERTY
        env["N5_REMOVAL_PROJECT_ROOT"] = str(_PROJECT_ROOT)
        env["N5_REMOVAL_HOOK_DIR"] = hook_dir
    kwargs["env"] = env
    return _REAL_RUN(*args, **kwargs)


subprocess.run = _inherit_hook


def _has_code(node, code):
    return any(
        isinstance(part, ast.Constant) and part.value == code
        for part in ast.walk(node)
    )


def _bypass_keep_markers(node):
    node.test = ast.BoolOp(op=ast.And(), values=[ast.Constant(value=False), node.test])
    return node


def _allow_multiple_selected_but_retain_zero_guard(node):
    test = node.test
    if not (
        isinstance(test, ast.Compare)
        and isinstance(test.left, ast.Call)
        and isinstance(test.left.func, ast.Name)
        and test.left.func.id == "len"
        and len(test.left.args) == 1
        and isinstance(test.left.args[0], ast.Name)
        and test.left.args[0].id == "selected_decisions"
        and len(test.ops) == 1
        and isinstance(test.ops[0], ast.NotEq)
        and len(test.comparators) == 1
        and isinstance(test.comparators[0], ast.Constant)
        and test.comparators[0].value == 1
    ):
        raise AssertionError("selected-decision uniqueness guard AST changed")
    node.test = ast.Compare(
        left=ast.Call(
            func=ast.Name(id="len", ctx=ast.Load()),
            args=[ast.Name(id="selected_decisions", ctx=ast.Load())],
            keywords=[],
        ),
        ops=[ast.Eq()],
        comparators=[ast.Constant(value=0)],
    )
    return node


def _drop_empty_atom_term(node):
    test = node.test
    if not isinstance(test, ast.BoolOp) or not isinstance(test.op, ast.Or):
        raise AssertionError("expected the explicit-empty atom guard to be an OR")
    remaining = [
        value
        for value in test.values
        if not (
            isinstance(value, ast.UnaryOp)
            and isinstance(value.op, ast.Not)
            and isinstance(value.operand, ast.Name)
            and value.operand.id == "atom_ids"
        )
    ]
    if len(remaining) == len(test.values):
        raise AssertionError("explicit-empty atom term was not found")
    node.test = ast.BoolOp(op=ast.Or(), values=remaining)
    return node


def _allow_empty_expected_atom_set(node):
    node.test = ast.BoolOp(
        op=ast.And(),
        values=[node.test, ast.Call(func=ast.Name(id="bool", ctx=ast.Load()), args=[ast.Name(id="expected_atom_ids", ctx=ast.Load())], keywords=[])],
    )
    return node


class _Removal(ast.NodeTransformer):
    def __init__(self, property_name):
        self.property_name = property_name
        self.function = None
        self.hits = 0

    def visit_FunctionDef(self, node):
        previous = self.function
        self.function = node.name
        updated = self.generic_visit(node)
        self.function = previous
        return updated

    def visit_If(self, node):
        node = self.generic_visit(node)
        if self.property_name == "engine_selection" and (
            self.function == "_validate_loaded_joint_simulation_result"
            and _has_code(node, "selected_engine_decision_not_unique")
        ):
            self.hits += 1
            return _allow_multiple_selected_but_retain_zero_guard(node)
        if self.property_name == "sibling_receipt_hash" and (
            self.function == "load_joint_simulation_result"
            and _has_code(node, "receipt_payload_hash_binding_mismatch")
        ):
            self.hits += 1
            return _bypass_keep_markers(node)
        if self.property_name == "point_outcome_distribution" and (
            self.function == "_validate_loaded_joint_simulation_result"
            and _contains_name(node.test, "selected_outcomes")
            and _contains_name(node.test, "point")
            and _contains_attribute(node.test, "outcomes")
            and not _contains_attribute(node.test, "effect")
        ):
            self.hits += 1
            return _bypass_keep_markers(node)
        if self.property_name == "explicit_empty_atoms":
            if (
                self.function == "_conditional_simulation_value_observation"
                and _has_code(node, "joint_simulation_result_atom_or_outcome_binding_missing")
            ):
                self.hits += 1
                return _drop_empty_atom_term(node)
            if (
                self.function == "_validate_loaded_joint_simulation_result"
                and isinstance(node.test, ast.BoolOp)
                and isinstance(node.test.op, ast.And)
                and _contains_name(node.test, "expected_atom_ids")
                and _contains_attribute(node.test, "atom_ids")
            ):
                self.hits += 1
                return _allow_empty_expected_atom_set(node)
        if self.property_name == "absent_atom_fallback" and (
            self.function == "_conditional_simulation_value_observation"
            and isinstance(node.test, ast.Compare)
            and _contains_name(node.test, "raw_atoms")
        ):
            self.hits += 1
            return _bypass_keep_markers(node)
        if self.property_name == "casless_digest" and (
            self.function == "simulation_evaluation_input_ref"
            and isinstance(node.test, ast.Compare)
            and _contains_name(node.test, "simulation_result_ref")
        ):
            self.hits += 1
            return _bypass_keep_markers(node)
        return node


def _contains_name(node, name):
    return any(
        isinstance(part, ast.Name) and part.id == name
        for part in ast.walk(node)
    )


def _contains_attribute(node, name):
    return any(
        isinstance(part, ast.Attribute) and part.attr == name
        for part in ast.walk(node)
    )


class _MutatingLoader(Loader):
    def __init__(self, wrapped, fullname):
        self.wrapped = wrapped
        self.fullname = fullname

    def create_module(self, spec):
        create = getattr(self.wrapped, "create_module", None)
        return create(spec) if create is not None else None

    def exec_module(self, module):
        self.wrapped.exec_module(module)
        source_path = Path(module.__file__).resolve()
        if source_path != _EXPECTED_SOURCE:
            raise AssertionError(f"wrong_runtime_source:{source_path}")
        source = Path(source_path).read_text()
        tree = ast.parse(source, filename=str(source_path))
        removal = _Removal(_PROPERTY)
        mutated = removal.visit(tree)
        if removal.hits != _expected_hits(_PROPERTY):
            raise AssertionError(
                f"removed_property_keep_markers:unexpected_mutation_hits:"
                f"{_PROPERTY}:{removal.hits}"
            )
        target_names = _target_function_names(_PROPERTY)
        functions = [
            node
            for node in mutated.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name in target_names
        ]
        if len(functions) != len(target_names):
            raise AssertionError(
                f"removed_property_keep_markers:target_function_missing:{target_names}"
            )
        replacement = ast.Module(body=functions, type_ignores=[])
        ast.fix_missing_locations(replacement)
        exec(compile(replacement, str(source_path), "exec"), module.__dict__)
        os.environ["N5_REMOVAL_HIT"] = "yes"


def _expected_hits(property_name):
    return 2 if property_name == "explicit_empty_atoms" else 1


def _target_function_names(property_name):
    if property_name == "engine_selection":
        return {"_validate_loaded_joint_simulation_result"}
    if property_name == "sibling_receipt_hash":
        return {"load_joint_simulation_result"}
    if property_name == "point_outcome_distribution":
        return {"_validate_loaded_joint_simulation_result"}
    if property_name == "explicit_empty_atoms":
        return {
            "_conditional_simulation_value_observation",
            "_validate_loaded_joint_simulation_result",
        }
    if property_name == "absent_atom_fallback":
        return {"_conditional_simulation_value_observation"}
    if property_name == "casless_digest":
        return {"simulation_evaluation_input_ref"}
    raise AssertionError(f"unknown_property:{property_name}")


class _Finder(MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname != "polisyos.runtime.quality.generation_cycle":
            return None
        spec = PathFinder.find_spec(fullname, path)
        if spec is not None and spec.loader is not None:
            spec.loader = _MutatingLoader(spec.loader, fullname)
        return spec


sys.meta_path.insert(0, _Finder())
'''

_WORKER = r'''import os
import pytest
import sys

if os.environ.get("N5_REMOVAL_PROPERTY") != sys.argv[1]:
    raise SystemExit("removed_property_keep_markers:property_not_propagated")
exit_code = pytest.main([
    "-q",
    "-s",
    "tests/unit/remediation/test_cyc_02.py::test_n5_fresh_process_readback_binds_default_n8_to_cas_identity",
])
if os.environ.get("N5_REMOVAL_HIT") != "yes":
    raise SystemExit("removed_property_keep_markers:source_mutant_not_applied")
raise SystemExit(int(exit_code))
'''


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--property", choices=_PROPERTY_CHOICES, required=True)
    args = parser.parse_args()

    project_root = args.project_root.resolve()
    test_file = project_root / "tests/unit/remediation/test_cyc_02.py"
    source_file = project_root / "src/polisyos/runtime/quality/generation_cycle.py"
    if not test_file.is_file() or not source_file.is_file():
        parser.error("project root must be a policy-engine checkout with source and tests")

    scratch = Path(__file__).resolve().parent
    hook_dir = scratch / f"hook-{args.property}"
    hook_dir.mkdir(parents=True, exist_ok=True)
    (hook_dir / "sitecustomize.py").write_text(_SITE_CUSTOMIZE)

    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        str(path)
        for path in (hook_dir, project_root / "src", project_root)
    )
    env["N5_REMOVAL_PROPERTY"] = args.property
    env["N5_REMOVAL_PROJECT_ROOT"] = str(project_root)
    env["N5_REMOVAL_HOOK_DIR"] = str(hook_dir)
    command = [sys.executable, "-c", _WORKER, args.property]
    completed = subprocess.run(
        command,
        cwd=project_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    output = completed.stdout + completed.stderr
    sys.stdout.write(output)
    expected_label = "removed_property_keep_markers:"
    if completed.returncode != 1 or expected_label not in output:
        print(
            f"REMOVAL_PROBE=NO-GO property={args.property} "
            f"exit={completed.returncode} expected_failure_label={expected_label!r}",
            file=sys.stderr,
        )
        return 2
    print(
        f"REMOVAL_PROBE=PASS property={args.property} "
        "behavioral_test_red_with_markers_retained"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
