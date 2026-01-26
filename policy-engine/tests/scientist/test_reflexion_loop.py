"""
Tests for the Reflexion loop and FailureCard system.
"""

from __future__ import annotations

import pytest

from polisyos.scientist.agent.failure_card import (
    ConstraintViolation,
    FailureCard,
    FailureSeverity,
    FailureSource,
    RemediationTarget,
    from_critic_feedback,
    from_governor_feedback,
    from_validation_error,
)
from polisyos.scientist.agent.reflexion import (
    ReflexionConfig,
    ReflexionDecision,
    ReflexionOrchestrator,
    add_failure_to_history,
    increment_retry_count,
)
from polisyos.scientist.orchestrator.state import (
    create_initial_state,
    get_retry_count,
    has_active_failure,
)


@pytest.fixture
def base_state():
    return create_initial_state(
        user_request="Create a tax policy for small businesses",
        run_id="test-run-001",
        budget={"max_llm_calls": 50.0, "max_sim_runs": 5.0},
    )


@pytest.fixture
def recoverable_failure_card():
    return FailureCard.generate(
        source_step=FailureSource.CRITIC,
        error_code="ALIGNMENT_MISMATCH",
        violation_summary="Generated IR does not fully capture user intent",
        remediation_advice="Revise the tax_rate parameter to match the 15% threshold",
        run_id="test-run-001",
        attempt_number=1,
        max_iterations=3,
        violations=[
            ConstraintViolation(
                constraint_id="alignment_001",
                constraint_type="alignment",
                field_path="interventions[0].params.rate",
                expected="0.15",
                actual="0.20",
                message="Tax rate does not match user specification",
            )
        ],
    )


@pytest.fixture
def fatal_failure_card():
    return FailureCard.generate(
        source_step=FailureSource.GOVERNOR_SAFETY,
        error_code="SAFETY_CRITICAL_VIOLATION",
        violation_summary="Policy violates safety constraints",
        remediation_advice="Cannot proceed - safety constraint violated",
        run_id="test-run-001",
        severity=FailureSeverity.FATAL,
    )


@pytest.fixture
def exhausted_failure_card():
    return FailureCard.generate(
        source_step=FailureSource.CRITIC,
        error_code="PERSISTENT_ERROR",
        violation_summary="Error persists after multiple attempts",
        remediation_advice="Consider manual intervention",
        run_id="test-run-001",
        attempt_number=3,
        max_iterations=3,
    )


class TestFailureCardSchema:
    def test_create_minimal_card(self):
        card = FailureCard.generate(
            source_step=FailureSource.VALIDATOR_SCHEMA,
            error_code="TEST_ERROR",
            violation_summary="Test violation",
            remediation_advice="Fix the test",
            run_id="test-001",
        )
        assert card.card_id is not None
        assert card.error_code == "TEST_ERROR"
        assert card.attempt_number == 1
        assert card.max_iterations == 3
        assert card.can_retry is True

    def test_can_retry_computation(self, recoverable_failure_card):
        assert recoverable_failure_card.can_retry is True
        card = FailureCard.generate(
            source_step=FailureSource.CRITIC,
            error_code="TEST",
            violation_summary="Test",
            remediation_advice="Test",
            run_id="test",
            attempt_number=3,
            max_iterations=3,
        )
        assert card.can_retry is False

    def test_fatal_severity_blocks_retry(self, fatal_failure_card):
        assert fatal_failure_card.severity == FailureSeverity.FATAL
        assert fatal_failure_card.can_retry is False

    def test_to_prompt_context_formatting(self, recoverable_failure_card):
        context = recoverable_failure_card.to_prompt_context()
        assert "## FAILURE CONTEXT (Attempt 1/3)" in context
        assert "ALIGNMENT_MISMATCH" in context
        assert "### How to Fix" in context

    def test_to_prompt_context_limits_violations(self):
        violations = [
            ConstraintViolation(
                constraint_id=f"v_{i}",
                constraint_type="test",
                message=f"Violation {i}",
            )
            for i in range(10)
        ]
        card = FailureCard.generate(
            source_step=FailureSource.VALIDATOR_SCHEMA,
            error_code="MANY_ERRORS",
            violation_summary="Multiple violations",
            remediation_advice="Fix all",
            run_id="test",
            violations=violations,
        )
        context = card.to_prompt_context()
        violation_count = sum(
            1 for line in context.split("\n") if line.strip().startswith(("1.", "2.", "3.", "4."))
        )
        assert violation_count <= 3

    def test_content_hash_deterministic(self, recoverable_failure_card):
        hash1 = recoverable_failure_card.content_hash
        hash2 = recoverable_failure_card.content_hash
        assert hash1 == hash2
        assert hash1.startswith("sha256:")

    def test_audit_entry_format(self, recoverable_failure_card):
        entry = recoverable_failure_card.to_audit_entry()
        assert entry["error_code"] == "ALIGNMENT_MISMATCH"
        assert entry["attempt"] == "1/3"


class TestFailureCardConverters:
    def test_from_critic_feedback(self):
        critique = {
            "verdict": "NEEDS_REVISION",
            "summary": "Policy does not cover all edge cases",
            "issues": [
                {
                    "issue_id": "align_0",
                    "category": "alignment",
                    "severity": "warning",
                    "message": "Missing rural areas consideration",
                    "location": "semantic.interventions",
                    "suggestion": "Add rural area exception",
                }
            ],
            "reflexion_hint": "Specify implementation timeline",
        }
        card = from_critic_feedback(critique, run_id="test-001")
        assert card.source_step == FailureSource.CRITIC
        assert card.remediation_target == RemediationTarget.DRAFTER
        assert len(card.violations) == 1

    def test_from_validation_error(self):
        report = {
            "issues": [
                {
                    "loc": ["interventions", 0, "params", "rate"],
                    "message": "value must be between 0 and 1",
                    "error_type": "validation",
                },
                {
                    "loc": ["semantic", "context_snapshot_ref"],
                    "message": "field required",
                    "error_type": "validation",
                },
            ]
        }
        card = from_validation_error(report, run_id="test-001")
        assert card.source_step == FailureSource.VALIDATOR_SCHEMA
        assert len(card.violations) == 2

    def test_from_governor_feedback_needs_revision(self):
        feedback = {
            "verdict": "NEEDS_REVISION",
            "issues": [
                {
                    "constraint_id": "budget_limit",
                    "error_type": "governance",
                    "message": "Policy exceeds budget threshold",
                }
            ],
            "advice": "Reduce scope to fit within budget",
        }
        card = from_governor_feedback(feedback, run_id="test-001")
        assert card.source_step == FailureSource.GOVERNOR_POLICY
        assert card.severity == FailureSeverity.RECOVERABLE
        assert card.governor_advice == "Reduce scope to fit within budget"

    def test_from_governor_feedback_reject(self):
        feedback = {
            "verdict": "REJECT",
            "issues": [
                {
                    "constraint_id": "safety_check",
                    "error_type": "safety",
                    "message": "Policy fails safety review",
                }
            ],
        }
        card = from_governor_feedback(feedback, run_id="test-001")
        assert card.source_step == FailureSource.GOVERNOR_SAFETY
        assert card.severity == FailureSeverity.NEEDS_HUMAN


class TestReflexionOrchestrator:
    def test_evaluate_recoverable_routes_to_drafter(
        self,
        recoverable_failure_card,
        base_state,
    ):
        orchestrator = ReflexionOrchestrator(ReflexionConfig())
        decision = orchestrator.evaluate_failure(recoverable_failure_card, base_state)
        assert decision == ReflexionDecision.RETURN_TO_DRAFTER

    def test_evaluate_fatal_aborts(self, fatal_failure_card, base_state):
        orchestrator = ReflexionOrchestrator(ReflexionConfig())
        decision = orchestrator.evaluate_failure(fatal_failure_card, base_state)
        assert decision == ReflexionDecision.ABORT_WITH_REPORT

    def test_evaluate_budget_exhausted_aborts(self, exhausted_failure_card, base_state):
        orchestrator = ReflexionOrchestrator(ReflexionConfig())
        decision = orchestrator.evaluate_failure(exhausted_failure_card, base_state)
        assert decision == ReflexionDecision.ABORT_WITH_REPORT

    def test_evaluate_llm_budget_exhausted(self, recoverable_failure_card, base_state):
        orchestrator = ReflexionOrchestrator(ReflexionConfig())
        state_exhausted = {
            **base_state,
            "budget": {"max_llm_calls": 1},
            "budget_usage": {"llm_calls": 1},
        }
        decision = orchestrator.evaluate_failure(recoverable_failure_card, state_exhausted)
        assert decision == ReflexionDecision.ABORT_WITH_REPORT

    def test_evaluate_drafter_target_routes_to_drafter(self, base_state):
        orchestrator = ReflexionOrchestrator(ReflexionConfig())
        card = FailureCard.generate(
            source_step=FailureSource.CRITIC,
            error_code="ALIGNMENT_INTENT_MISMATCH",
            violation_summary="Intent not captured",
            remediation_advice="Rethink approach",
            run_id="test",
            remediation_target=RemediationTarget.DRAFTER,
        )
        decision = orchestrator.evaluate_failure(card, base_state)
        assert decision == ReflexionDecision.RETURN_TO_DRAFTER

    def test_evaluate_needs_human_escalates(self, base_state):
        orchestrator = ReflexionOrchestrator(ReflexionConfig())
        card = FailureCard.generate(
            source_step=FailureSource.GOVERNOR_POLICY,
            error_code="POLICY_CONFLICT",
            violation_summary="Conflicting requirements",
            remediation_advice="Human decision needed",
            run_id="test",
            severity=FailureSeverity.NEEDS_HUMAN,
        )
        decision = orchestrator.evaluate_failure(card, base_state)
        assert decision == ReflexionDecision.ESCALATE_TO_HUMAN

    def test_prepare_retry_context(self, recoverable_failure_card, base_state):
        orchestrator = ReflexionOrchestrator(ReflexionConfig())
        context = orchestrator.prepare_retry_context(recoverable_failure_card, base_state)
        assert context["attempt_number"] == 2
        assert context["remaining_attempts"] == 2
        assert "original_request" in context

    def test_decision_log_populated(self, recoverable_failure_card, base_state):
        orchestrator = ReflexionOrchestrator(ReflexionConfig())
        orchestrator.reset_decision_log()
        orchestrator.evaluate_failure(recoverable_failure_card, base_state)
        log = orchestrator.get_decision_log()
        assert len(log) == 1
        assert log[0]["error_code"] == "ALIGNMENT_MISMATCH"

    def test_backoff_delay_config(self):
        config = ReflexionConfig(base_delay_seconds=0.1, backoff_multiplier=2.0, max_delay_seconds=0.5)
        assert config.get_delay(1) == 0.1
        assert config.get_delay(2) == 0.2
        assert config.get_delay(3) == 0.4
        assert config.get_delay(10) == 0.5


class TestStateManagement:
    def test_increment_retry_count(self, base_state):
        assert get_retry_count(base_state) == 0
        new_state = increment_retry_count(base_state)
        assert get_retry_count(new_state) == 1

    def test_add_failure_to_history(self, base_state, recoverable_failure_card):
        new_state = add_failure_to_history(base_state, recoverable_failure_card)
        history = new_state.get("failure_history", [])
        assert len(history) == 1
        assert history[0]["error_code"] == "ALIGNMENT_MISMATCH"

    def test_has_active_failure(self, base_state, recoverable_failure_card):
        assert has_active_failure(base_state) is False
        state_with_failure = {
            **base_state,
            "current_failure_card": recoverable_failure_card.model_dump(),
        }
        assert has_active_failure(state_with_failure) is True


class TestReflexionIntegration:
    def test_scenario_success_after_one_retry(self, base_state):
        orchestrator = ReflexionOrchestrator(ReflexionConfig(max_iterations=3))
        card_1 = FailureCard.generate(
            source_step=FailureSource.CRITIC,
            error_code="SCHEMA_ERROR",
            violation_summary="Missing required field",
            remediation_advice="Add the missing field",
            run_id=base_state["run_id"],
            attempt_number=1,
            max_iterations=3,
        )
        decision_1 = orchestrator.evaluate_failure(card_1, base_state)
        assert decision_1 in {
            ReflexionDecision.RETURN_TO_FORMALIZER,
            ReflexionDecision.RETURN_TO_DRAFTER,
        }
        state_after_retry = increment_retry_count(base_state)
        state_after_retry = add_failure_to_history(state_after_retry, card_1)
        assert get_retry_count(state_after_retry) == 1

    def test_scenario_budget_exhaustion(self, base_state):
        orchestrator = ReflexionOrchestrator(ReflexionConfig(max_iterations=3))
        state = base_state.copy()
        for attempt in range(1, 4):
            card = FailureCard.generate(
                source_step=FailureSource.CRITIC,
                error_code=f"PERSISTENT_ERROR_{attempt}",
                violation_summary=f"Error on attempt {attempt}",
                remediation_advice="Try again",
                run_id=state["run_id"],
                attempt_number=attempt,
                max_iterations=3,
            )
            decision = orchestrator.evaluate_failure(card, state)
            if attempt < 3:
                assert decision in {
                    ReflexionDecision.RETURN_TO_FORMALIZER,
                    ReflexionDecision.RETURN_TO_DRAFTER,
                }
                state = increment_retry_count(state)
                state = add_failure_to_history(state, card)
            else:
                assert decision == ReflexionDecision.ABORT_WITH_REPORT
                assert card.can_retry is False
