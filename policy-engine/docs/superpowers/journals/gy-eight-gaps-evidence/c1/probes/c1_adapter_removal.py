"""Remove C1 admission properties in memory while retaining tracked markers."""

import sys
from dataclasses import replace

import pytest

from polisyos.runtime.quality import adapter_contracts
from polisyos.runtime.quality.workspace import scientist_node_adapters

mode = sys.argv[1]
prefix = "tests/unit/runtime/quality/test_workspace_scientist_node_adapters.py::"
if mode == "preservation":
    original = adapter_contracts.validate_adapter_preservation

    def ignore_preservation_result(**kwargs):
        return replace(original(**kwargs), status="pass", blockers=())

    adapter_contracts.validate_adapter_preservation = ignore_preservation_result
    tests = ["test_conformance_consults_preservation_on_valid_cas_with_changed_payload"]
elif mode == "closure":
    scientist_node_adapters._reference_closure = lambda *args, **kwargs: []
    tests = [
        "test_conformance_refuses_dangling_input_before_node_execution",
        "test_conformance_refuses_dangling_output_ref_with_all_markers",
    ]
else:
    raise ValueError(mode)

raise SystemExit(pytest.main(["-q", "--tb=short", *(prefix + test for test in tests)]))
