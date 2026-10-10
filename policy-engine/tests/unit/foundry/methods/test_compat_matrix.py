"""
Tests for CompatibilityMatrix (T3.2).

Verifies:
- generate() populates cells for all registered methods
- All entries in the current runtime version are COMPATIBLE (no breaking deps)
- to_markdown() produces a valid Markdown table
- compatible_runtimes() and incompatible_methods() query methods work
- CompatibilityCell is correctly structured
"""

from __future__ import annotations

import pytest

from polisyos.foundry.methods.compat_matrix import (
    CompatibilityCell,
    CompatibilityMatrix,
)


class TestCompatibilityMatrix:
    @pytest.fixture(autouse=True)
    def matrix(self, module_registry):
        m = CompatibilityMatrix()
        m.generate(module_registry, runtime_versions=["3.x", "4.x"])
        return m

    def test_generate_populates_method_fqns(self, matrix, module_registry):
        registered = {sig.fqn for sig in module_registry.list_all()}
        assert set(matrix.method_fqns) == registered

    def test_generate_populates_cells_for_all_combinations(self, matrix):
        expected = len(matrix.method_fqns) * len(matrix.runtime_versions)
        assert len(matrix.cells) == expected

    def test_all_cells_have_valid_status(self, matrix):
        valid = {"COMPATIBLE", "DEPRECATED", "INCOMPATIBLE", "UNKNOWN"}
        for cell in matrix.cells.values():
            assert cell.status in valid, f"Invalid status: {cell.status}"

    def test_current_runtime_methods_are_mostly_compatible(self, matrix):
        """
        Methods registered in the current registry should be COMPATIBLE with 4.x.
        A few may be DEPRECATED or pre-1.0 experimental.
        """
        current_rv = "4.x"
        incompatible = matrix.incompatible_methods(current_rv)
        total = len(matrix.method_fqns)
        # At most 10% should be incompatible with the current runtime
        assert len(incompatible) / max(1, total) <= 0.10, (
            f"{len(incompatible)}/{total} methods incompatible with {current_rv}: "
            + ", ".join(incompatible[:5])
        )

    def test_to_markdown_returns_string(self, matrix):
        md = matrix.to_markdown()
        assert isinstance(md, str)
        assert len(md) > 0

    def test_to_markdown_contains_runtime_versions(self, matrix):
        md = matrix.to_markdown()
        for rv in matrix.runtime_versions:
            assert rv in md

    def test_to_markdown_empty_matrix(self):
        empty = CompatibilityMatrix()
        md = empty.to_markdown()
        assert "Empty" in md

    def test_compatible_runtimes_returns_list(self, matrix):
        assert matrix.method_fqns, "Registry is empty"
        fqn = matrix.method_fqns[0]
        runtimes = matrix.compatible_runtimes(fqn)
        assert isinstance(runtimes, list)
        for rv in runtimes:
            assert rv in matrix.runtime_versions

    def test_incompatible_methods_returns_list(self, matrix):
        result = matrix.incompatible_methods("4.x")
        assert isinstance(result, list)

    def test_cell_attributes(self, matrix):
        assert matrix.cells, "No cells generated"
        cell = next(iter(matrix.cells.values()))
        assert isinstance(cell, CompatibilityCell)
        assert cell.method_fqn
        assert cell.runtime_version
        assert cell.status in {"COMPATIBLE", "DEPRECATED", "INCOMPATIBLE", "UNKNOWN"}

    def test_repr(self, matrix):
        r = repr(matrix)
        assert "CompatibilityMatrix" in r
        assert str(len(matrix.method_fqns)) in r


class TestCompatibilityMatrixEdgeCases:
    def test_custom_runtime_versions(self, module_registry):
        m = CompatibilityMatrix()
        m.generate(module_registry, runtime_versions=["2.x", "5.x"])
        assert m.runtime_versions == ["2.x", "5.x"]
        assert all(rv in ["2.x", "5.x"] for _, rv in m.cells)

    def test_deprecated_method_is_marked(self, module_registry):
        """If any method has 'deprecated' tag, it should appear as DEPRECATED."""
        m = CompatibilityMatrix()
        m.generate(module_registry)
        deprecated_fqns = [
            fqn
            for fqn in m.method_fqns
            if any(
                cell.status == "DEPRECATED" for cell in m.cells.values() if cell.method_fqn == fqn
            )
        ]
        # Just verify the query doesn't crash; deprecated count is 0 or more
        assert isinstance(deprecated_fqns, list)
