"""Remove exact aggregation only; keep current recipe/schema/producer markers."""
from __future__ import annotations
import sys
from functools import reduce
from operator import add
import pytest
from polisyos.runtime.quality import data_forge_binding as owner


def main():
    original = owner._sum_recorded_values
    markers = (owner.WORKSPACE_RECORDED_PANEL_SCHEMA_VERSION, owner.RECORDED_PANEL_BINDING_SCHEMA_VERSION, owner.RecordedPanelRecipe().aggregation)
    owner._sum_recorded_values = lambda values: round(reduce(add, values, 0.0), 6)
    try:
        status = pytest.main(["-q", "-s", "--tb=short", "tests/unit/runtime/quality/test_data_forge_binding.py::test_recorded_extraction_preserves_exact_sum_across_all_row_permutations"])
        assert markers == (owner.WORKSPACE_RECORDED_PANEL_SCHEMA_VERSION, owner.RECORDED_PANEL_BINDING_SCHEMA_VERSION, owner.RecordedPanelRecipe().aggregation)
        print({"mutation": "exact aggregation removed only", "markers": markers, "actual_pytest_status": int(status)}, flush=True)
        return int(status)
    finally:
        owner._sum_recorded_values = original

if __name__ == "__main__": sys.exit(main())
