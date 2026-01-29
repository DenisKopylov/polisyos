"""Phase 2 instrumentation tests for Scientist workflow."""
from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

from polisyos.core.observability import get_tracer
from polisyos.scientist.orchestrator import flow_nodes
from polisyos.scientist.orchestrator.state import ExperimentState


@pytest.fixture
def minimal_state() -> ExperimentState:
    return {
        "run_id": "R_test_001",
        "user_request": "Create a policy to reduce poverty",
        "ir": None,
        "feedback": None,
        "llm_client": None,
        "budget": {"max_llm_calls": 5},
        "budget_usage": {},
        "audit_trail": [],
        "pruned": False,
    }


class TestFlowNodeInstrumentation:
    def test_drafter_node_creates_span(self, in_memory_exporter, minimal_state, monkeypatch):
        monkeypatch.setattr(flow_nodes, "_ensure_run", lambda s: s)
        monkeypatch.setattr(flow_nodes, "_check_budget", lambda s, k: s)

        minimal_state["problem_frame"] = {
            "frame_id": "F_001",
            "problem_statement": "Test problem",
            "domain": "economics",
            "actors": [],
            "goals": ["goal1"],
            "constraints": [],
            "success_criteria": {},
            "assumptions": [],
        }

        result = flow_nodes.drafter_node(minimal_state)

        spans = in_memory_exporter.get_finished_spans()
        drafter_span = next((s for s in spans if s.name == "drafter_node"), None)
        assert drafter_span is not None

        attrs = dict(drafter_span.attributes)
        assert attrs.get("polisyos.phase") == "DRAFT"
        assert attrs.get("polisyos.agent.name") == "drafter"
        assert attrs.get("polisyos.run_id") == "R_test_001"

        assert result.get("draft_result") is not None

    def test_validate_ir_node_records_issues(
        self, in_memory_exporter, minimal_state, monkeypatch
    ):
        monkeypatch.setattr(flow_nodes, "_ensure_run", lambda s: s)

        def _fake_validate(state: ExperimentState) -> ExperimentState:
            feedback = {
                "verdict": "REJECT",
                "issues": [
                    {"severity": "warning", "error_type": "schema", "code": "X001"}
                ],
            }
            return {**state, "feedback": feedback}

        monkeypatch.setattr(flow_nodes, "_validate_ir_node_impl", _fake_validate)

        result = flow_nodes.validate_ir_node(minimal_state)

        spans = in_memory_exporter.get_finished_spans()
        validate_span = next((s for s in spans if s.name == "validate_ir_node"), None)
        assert validate_span is not None

        attrs = dict(validate_span.attributes)
        assert attrs.get("polisyos.validation.issue_count") == 1
        assert attrs.get("polisyos.verdict") == "REJECT"

        assert result.get("feedback") is not None

    def test_trace_id_consistency_across_workflow(
        self, in_memory_exporter, minimal_state, monkeypatch
    ):
        monkeypatch.setattr(flow_nodes, "_ensure_run", lambda s: s)
        monkeypatch.setattr(flow_nodes, "_check_budget", lambda s, k: s)

        minimal_state["problem_frame"] = {
            "frame_id": "F_001",
            "problem_statement": "Test",
            "domain": "economic",
            "actors": [],
            "goals": [],
            "constraints": [],
            "success_criteria": {},
            "assumptions": [],
        }

        tracer = get_tracer()
        with tracer.start_as_current_span("test_workflow"):
            state1 = flow_nodes.drafter_node(minimal_state)
            _ = flow_nodes.formalize_node(state1)

        spans = in_memory_exporter.get_finished_spans()
        trace_ids = {span.context.trace_id for span in spans}
        assert len(trace_ids) == 1, f"Expected 1 trace ID, got {len(trace_ids)}"


class TestLLMClientInstrumentation:
    def test_traced_llm_client_records_tokens(self, in_memory_exporter):
        from polisyos.scientist.llm.traced_client import TracedLLMClient

        mock_response = MagicMock()
        mock_response.usage.prompt_tokens = 100
        mock_response.usage.completion_tokens = 50

        mock_client = MagicMock()
        mock_client.invoke.return_value = mock_response

        traced = TracedLLMClient(mock_client, model_name="gpt-4-test")
        traced.invoke("Test prompt")

        spans = in_memory_exporter.get_finished_spans()
        llm_span = next((s for s in spans if "llm.invoke" in s.name), None)
        assert llm_span is not None

        attrs = dict(llm_span.attributes)
        assert attrs.get("polisyos.llm.model") == "gpt-4-test"
        assert attrs.get("polisyos.llm.tokens.prompt") == 100
        assert attrs.get("polisyos.llm.tokens.completion") == 50

    def test_traced_llm_client_handles_missing_usage(self, in_memory_exporter):
        from polisyos.scientist.llm.traced_client import TracedLLMClient

        mock_client = MagicMock()
        mock_client.invoke.return_value = "Plain text response"

        traced = TracedLLMClient(mock_client, model_name="mock")
        traced.invoke("Test prompt")

        spans = in_memory_exporter.get_finished_spans()
        assert len(spans) >= 1
        llm_span = spans[-1]
        attrs = dict(llm_span.attributes)
        assert attrs.get("polisyos.llm.tokens.prompt", 0) == 0

    def test_traced_llm_client_generate(self, in_memory_exporter):
        from polisyos.scientist.llm.traced_client import TracedLLMClient

        mock_response = MagicMock()
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 5

        async def _generate(**kwargs):
            return mock_response

        mock_client = MagicMock()
        mock_client.generate.side_effect = _generate

        traced = TracedLLMClient(mock_client, model_name="gpt-4-gen")
        asyncio.run(traced.generate(system="sys", user="user"))

        spans = in_memory_exporter.get_finished_spans()
        llm_span = next((s for s in spans if "llm.generate" in s.name), None)
        assert llm_span is not None
        attrs = dict(llm_span.attributes)
        assert attrs.get("polisyos.llm.tokens.prompt") == 10
        assert attrs.get("polisyos.llm.tokens.completion") == 5


class TestGovernanceInstrumentation:
    def test_validation_pipeline_creates_spans_per_pass(self, in_memory_exporter):
        from polisyos.scientist.governance.pipeline import ValidationPipeline
        from polisyos.scientist.governance.profiles import ValidationProfile, ProfileLevel
        from polisyos.scientist.governance.passes.base import (
            ComplianceIssue,
            IssueSeverity,
            PassContext,
            ValidatorPass,
        )

        class AlwaysIssuePass(ValidatorPass):
            @property
            def pass_id(self) -> str:
                return "test_always_issue"

            def validate(self, ctx: PassContext):
                return [
                    ComplianceIssue(
                        pass_id=self.pass_id,
                        path=["test"],
                        message="Test issue",
                        severity=IssueSeverity.WARNING,
                        code="TEST_001",
                    )
                ]

        profile = ValidationProfile(
            level=ProfileLevel.FAST,
            pass_ids=frozenset({'test_always_issue'}),
            thresholds={},
            short_circuit_on_blocker=False,
        )
        pipeline = ValidationPipeline([AlwaysIssuePass()])

        ctx = PassContext(
            ir=None,
            state={"budget": {"max_sim_runs": 5}},
            registry_bundle=None,
            profile=profile,
            run_id="R_test_pipeline",
        )

        issues, _trace = pipeline.validate(ctx, profile)

        spans = in_memory_exporter.get_finished_spans()
        pipeline_span = next((s for s in spans if "validation_pipeline" in s.name), None)
        assert pipeline_span is not None

        pass_spans = [s for s in spans if "governance.pass" in s.name]
        assert len(pass_spans) >= 1
        assert len(issues) == 1
