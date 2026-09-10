"""Remove value comparison in memory while keeping every receipt and marker."""

import ast
import inspect

import pytest

from polisyos.runtime.quality import data_forge_binding as owner


tree = ast.parse(inspect.getsource(owner.verify_recorded_panel_method_input))
removed = 0
for node in ast.walk(tree):
    if (
        isinstance(node, ast.If)
        and isinstance(node.test, ast.Compare)
        and isinstance(node.test.left, ast.Name)
        and node.test.left.id == "actual_payload"
    ):
        node.test = ast.Constant(value=False)
        removed += 1
assert removed == 1
exec(compile(ast.fix_missing_locations(tree), "<value-comparison-removal>", "exec"), vars(owner))
print("REMOVAL: actual extracted-value comparison disabled; receipts and markers preserved")
raise SystemExit(pytest.main([
    "-q",
    "tests/unit/runtime/quality/test_data_forge_binding.py::"
    "test_recorded_panel_method_input_roundtrips_measured_and_assumed_fields",
    "tests/unit/runtime/quality/test_data_forge_binding.py::"
    "test_recorded_panel_fabricated_values_are_refused_with_all_markers",
]))
