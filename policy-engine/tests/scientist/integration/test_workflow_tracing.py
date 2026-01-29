"""Integration test for end-to-end workflow tracing."""
from __future__ import annotations

import os

import pytest

from polisyos.scientist import run_experiment


pytestmark = pytest.mark.integration

if os.getenv("POLISYOS_RUN_INTEGRATION") != "1":
    pytest.skip("Set POLISYOS_RUN_INTEGRATION=1 to run integration tracing", allow_module_level=True)


def test_full_workflow_trace_consistency(in_memory_exporter):
    initial_state = {
        "run_id": "R_integration_test",
        "user_request": "Create a policy to increase GDP by 5%",
        "llm_client": None,
        "budget": {
            "max_llm_calls": 10,
            "max_sim_runs": 1,
            "wall_time_s": 60,
        },
    }

    final_state = run_experiment(initial_state)

    spans = in_memory_exporter.get_finished_spans()
    trace_ids = {s.context.trace_id for s in spans}
    assert len(trace_ids) == 1, "All spans must share same trace_id"

    phases = {
        s.attributes.get("polisyos.phase")
        for s in spans
        if s.attributes.get("polisyos.phase")
    }
    expected_phases = {"FRAME", "DRAFT", "VALIDATE", "EXECUTE", "DECIDE"}
    assert phases & expected_phases

    run_ids = {
        s.attributes.get("polisyos.run_id")
        for s in spans
        if s.attributes.get("polisyos.run_id")
    }
    assert run_ids == {"R_integration_test"}
