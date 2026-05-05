"""Integration tests simulating real workflows for observability."""

from __future__ import annotations

from polisyos.core.observability import get_metrics, get_tracer, traced


class TestIntegrationScenarios:
    """Integration tests simulating real workflows."""

    def test_full_workflow_trace(self, test_tracer_provider, in_memory_exporter):
        """Simulate a complete policy workflow with tracing."""

        @traced(phase="DRAFT", node="draft_ir", agent="drafter")
        def draft_ir(problem_frame: dict) -> dict:
            return {"version": "2.0.0", "mechanisms": []}

        @traced(phase="VALIDATE", node="validate", agent="governor")
        def validate(ir: dict) -> dict:
            return {"valid": True, "issues": []}

        @traced(phase="EXECUTE", node="run_sim")
        def run_simulation(ir: dict) -> dict:
            metrics = get_metrics()
            with metrics.time_simulation({"node": "run_sim"}):
                return {"gdp_growth": 0.02, "steps": 100}

        @traced(phase="DECIDE", node="decide")
        def decide(sim_results: dict) -> dict:
            return {"decision": "APPROVE", "confidence": 0.95}

        # Execute workflow
        tracer = get_tracer()

        with tracer.start_as_current_span(
            "workflow_run",
            attributes={"polisyos.run_id": "R_test_workflow"},
        ):
            ir = draft_ir({"objective": "maximize_gdp"})
            validation = validate(ir)
            results = run_simulation(ir)
            decision = decide(results)

        # Verify span hierarchy
        spans = in_memory_exporter.get_finished_spans()
        assert len(spans) == 5  # workflow + 4 nodes

        # All should have same trace_id
        trace_ids = {s.context.trace_id for s in spans}
        assert len(trace_ids) == 1

        # Verify phases
        phases = {
            s.attributes.get("polisyos.phase") for s in spans if "polisyos.phase" in s.attributes
        }
        assert phases == {"DRAFT", "VALIDATE", "EXECUTE", "DECIDE"}

        # Ensure values are used (avoid lint)
        assert validation["valid"] is True
        assert decision["decision"] == "APPROVE"
