"""
Agent Protocol Conformance Tests
================================

Validates protocol conformance, runtime behavior, and backward compatibility.
"""

from __future__ import annotations

import asyncio
import inspect
from datetime import datetime

import pytest
from polisyos.scientist.agent.base import BaseAgent, MockAgent
from polisyos.scientist.agent.critic import MockCriticAgent
from polisyos.scientist.agent.drafter import MockDrafterAgent
from polisyos.scientist.agent.formalizer import MockFormalizerAgent, create_mock_draft
from polisyos.scientist.agent.pi import MockPIAgent
from polisyos.scientist.agent.protocols import (
    AGENT_PROTOCOLS,
    AgentRole,
    CriticAgent,
    CritiqueCategory,
    CritiqueIssue,
    CritiqueReport,
    CritiqueSeverity,
    DataNeedExtractorAgent,
    DelegationResult,
    DrafterAgent,
    DraftResult,
    FormalizerAgent,
    PIAgent,
    ProblemFrame,
    SubTask,
    TaskPriority,
    TaskStatus,
    get_protocol_for_role,
    is_valid_agent,
)


def run(coro):
    return asyncio.run(coro)


@pytest.fixture
def mock_pi() -> MockPIAgent:
    return MockPIAgent()


@pytest.fixture
def mock_drafter() -> MockDrafterAgent:
    return MockDrafterAgent()


@pytest.fixture
def mock_formalizer() -> MockFormalizerAgent:
    return MockFormalizerAgent()


@pytest.fixture
def mock_critic() -> MockCriticAgent:
    return MockCriticAgent()


@pytest.fixture
def sample_problem_frame() -> ProblemFrame:
    return ProblemFrame(
        frame_id="pf_test_001",
        domain="economic",
        problem_statement="Reduce poverty by implementing targeted social programs",
        actors=("government", "citizens", "businesses"),
        goals=("Reduce poverty rate by 20%", "Maintain budget balance"),
        constraints=("Budget deficit <= 3%", "No new debt"),
        success_criteria={
            "poverty_reduction": 0.2,
            "budget_balance": True,
        },
        assumptions=("Economic growth remains stable",),
        created_at=datetime.utcnow(),
    )


@pytest.fixture
def sample_draft(sample_problem_frame: ProblemFrame) -> DraftResult:
    return DraftResult(
        draft_id="draft_test_001",
        problem_frame_ref=sample_problem_frame.frame_id,
        narrative="Policy to reduce poverty through targeted subsidies and tax reforms",
        interventions=[
            {
                "kind": "tax_subsidy",
                "description": "Targeted subsidy for low-income groups",
                "target": {
                    "kind": "predicate",
                    "field": "income",
                    "operator": "<",
                    "value": "1000",
                },
                "params": {"rate": "0.15"},
            }
        ],
        rationale="This approach directly addresses poverty through income support",
        confidence=0.85,
        created_at=datetime.utcnow(),
    )


class TestProtocolConformance:
    def test_mock_pi_implements_protocol(self, mock_pi: MockPIAgent) -> None:
        assert isinstance(mock_pi, PIAgent)

    def test_mock_drafter_implements_protocol(self, mock_drafter: MockDrafterAgent) -> None:
        assert isinstance(mock_drafter, DrafterAgent)

    def test_mock_formalizer_implements_protocol(
        self, mock_formalizer: MockFormalizerAgent
    ) -> None:
        assert isinstance(mock_formalizer, FormalizerAgent)

    def test_mock_critic_implements_protocol(self, mock_critic: MockCriticAgent) -> None:
        assert isinstance(mock_critic, CriticAgent)

    def test_protocol_registry_completeness(self) -> None:
        expected_roles = {
            AgentRole.PI,
            AgentRole.DATA_NEED_EXTRACTOR,
            AgentRole.DRAFTER,
            AgentRole.FORMALIZER,
            AgentRole.CRITIC,
        }
        assert set(AGENT_PROTOCOLS.keys()) == expected_roles

    def test_get_protocol_for_role(self) -> None:
        assert get_protocol_for_role(AgentRole.PI) is PIAgent
        assert get_protocol_for_role(AgentRole.DATA_NEED_EXTRACTOR) is DataNeedExtractorAgent
        assert get_protocol_for_role(AgentRole.DRAFTER) is DrafterAgent
        assert get_protocol_for_role(AgentRole.FORMALIZER) is FormalizerAgent
        assert get_protocol_for_role(AgentRole.CRITIC) is CriticAgent

    def test_is_valid_agent_utility(
        self, mock_pi: MockPIAgent, mock_drafter: MockDrafterAgent
    ) -> None:
        assert is_valid_agent(mock_pi, AgentRole.PI)
        assert is_valid_agent(mock_drafter, AgentRole.DRAFTER)
        assert not is_valid_agent(mock_pi, AgentRole.DRAFTER)
        assert not is_valid_agent("not an agent", AgentRole.PI)


class TestProtocolSignatures:
    def test_pi_signature(self) -> None:
        sig = inspect.signature(PIAgent.decompose_task)
        assert sig.parameters["context"].kind == inspect.Parameter.KEYWORD_ONLY
        assert sig.parameters["context"].default is None

        sig = inspect.signature(PIAgent.create_problem_frame)
        assert sig.parameters["domain_hint"].kind == inspect.Parameter.KEYWORD_ONLY
        assert sig.parameters["domain_hint"].default is None

    def test_drafter_signature(self) -> None:
        sig = inspect.signature(DrafterAgent.draft_policy)
        assert sig.parameters["hints"].kind == inspect.Parameter.KEYWORD_ONLY
        assert sig.parameters["prior_drafts"].kind == inspect.Parameter.KEYWORD_ONLY

        sig = inspect.signature(DrafterAgent.refine_draft)
        assert "draft" in sig.parameters
        assert "critique" in sig.parameters

    def test_formalizer_signature(self) -> None:
        sig = inspect.signature(FormalizerAgent.formalize)
        assert sig.parameters["schema_version"].kind == inspect.Parameter.KEYWORD_ONLY
        assert sig.parameters["schema_version"].default == "1.0"

        sig = inspect.signature(FormalizerAgent.repair_ir)
        assert sig.parameters["hint"].kind == inspect.Parameter.KEYWORD_ONLY

    def test_critic_signature(self) -> None:
        sig = inspect.signature(CriticAgent.critique)
        assert sig.parameters["depth"].kind == inspect.Parameter.KEYWORD_ONLY
        assert sig.parameters["depth"].default == "standard"


class TestPIAgentRuntime:
    def test_decompose_task_returns_subtasks(self, mock_pi: MockPIAgent) -> None:
        tasks = run(mock_pi.decompose_task("Reduce poverty by 20%"))
        assert isinstance(tasks, list)
        assert len(tasks) > 0
        assert all(isinstance(task, SubTask) for task in tasks)

    def test_decompose_task_subtask_structure(self, mock_pi: MockPIAgent) -> None:
        tasks = run(mock_pi.decompose_task("Test policy request"))
        for task in tasks:
            assert task.task_id
            assert task.description
            assert isinstance(task.target_agent, AgentRole)
            assert isinstance(task.priority, TaskPriority)
            assert isinstance(task.status, TaskStatus)

    def test_decompose_task_with_empty_request_raises(self, mock_pi: MockPIAgent) -> None:
        with pytest.raises(ValueError, match="[Rr]equest cannot be empty"):
            run(mock_pi.decompose_task(""))

        with pytest.raises(ValueError, match="[Rr]equest cannot be empty"):
            run(mock_pi.decompose_task("   "))

    def test_create_problem_frame(self, mock_pi: MockPIAgent) -> None:
        frame = run(mock_pi.create_problem_frame("Reduce poverty by 20%"))
        assert isinstance(frame, ProblemFrame)
        assert frame.frame_id
        assert frame.problem_statement == "Reduce poverty by 20%"
        assert frame.domain

    def test_create_problem_frame_with_domain_hint(self, mock_pi: MockPIAgent) -> None:
        frame = run(
            mock_pi.create_problem_frame("Improve healthcare access", domain_hint="healthcare")
        )
        assert frame.domain == "healthcare"

    def test_hold_and_retrieve_problem_frame(
        self,
        mock_pi: MockPIAgent,
        sample_problem_frame: ProblemFrame,
    ) -> None:
        assert mock_pi.current_problem_frame is None
        run(mock_pi.hold_problem_frame(sample_problem_frame))
        assert mock_pi.current_problem_frame is not None
        assert mock_pi.current_problem_frame.frame_id == sample_problem_frame.frame_id

    def test_delegate_returns_result(self, mock_pi: MockPIAgent) -> None:
        task = SubTask(
            task_id="test_task_001",
            description="Test delegation",
            target_agent=AgentRole.DRAFTER,
        )
        result = run(mock_pi.delegate(task, AgentRole.DRAFTER))
        assert isinstance(result, DelegationResult)
        assert result.task_id == task.task_id
        assert result.agent_role == AgentRole.DRAFTER
        assert result.success is True

    def test_delegate_invalid_role_raises(self, mock_pi: MockPIAgent) -> None:
        task = SubTask(
            task_id="test_task_002",
            description="Test invalid delegation",
            target_agent=AgentRole.PI,
        )
        with pytest.raises(ValueError):
            run(mock_pi.delegate(task, AgentRole.PI))


class TestDrafterAgentRuntime:
    def test_draft_policy_returns_draft_result(
        self,
        mock_drafter: MockDrafterAgent,
        sample_problem_frame: ProblemFrame,
    ) -> None:
        draft = run(mock_drafter.draft_policy(sample_problem_frame))
        assert isinstance(draft, DraftResult)
        assert draft.draft_id
        assert draft.problem_frame_ref == sample_problem_frame.frame_id
        assert draft.narrative

    def test_draft_policy_with_hints(
        self,
        mock_drafter: MockDrafterAgent,
        sample_problem_frame: ProblemFrame,
    ) -> None:
        hints = ["Consider progressive taxation", "Add budget constraints"]
        draft = run(mock_drafter.draft_policy(sample_problem_frame, hints=hints))
        assert isinstance(draft, DraftResult)
        assert draft.confidence > 0.7

    def test_refine_draft(self, mock_drafter: MockDrafterAgent, sample_draft: DraftResult) -> None:
        critique = CritiqueReport(
            report_id="critique_001",
            ir_ref="ir_test",
            problem_frame_ref=sample_draft.problem_frame_ref,
            verdict="NEEDS_REVISION",
            issues=[
                CritiqueIssue(
                    issue_id="issue_001",
                    category=CritiqueCategory.COMPLETENESS,
                    severity=CritiqueSeverity.WARNING,
                    message="Missing budget constraint",
                    suggestion="Add explicit budget limit",
                )
            ],
            reflexion_hint="Consider adding budget constraints to the policy",
        )

        refined = run(mock_drafter.refine_draft(sample_draft, critique))
        assert isinstance(refined, DraftResult)
        assert refined.draft_id != sample_draft.draft_id
        assert "refined" in refined.draft_id.lower()


class TestFormalizerAgentRuntime:
    def test_formalize_returns_trinity_bundle(
        self,
        mock_formalizer: MockFormalizerAgent,
        sample_draft: DraftResult,
    ) -> None:
        from polisyos.ir.trinity import TrinityBundle

        ir = run(mock_formalizer.formalize(sample_draft))
        assert isinstance(ir, TrinityBundle)
        assert ir.schema_version == "1.0"
        assert ir.policy_spec is not None

    def test_formalize_preserves_interventions(
        self,
        mock_formalizer: MockFormalizerAgent,
        sample_draft: DraftResult,
    ) -> None:
        ir = run(mock_formalizer.formalize(sample_draft))
        assert ir.policy_spec.interventions
        assert len(ir.policy_spec.interventions) > 0

    def test_validate_structure(self, mock_formalizer: MockFormalizerAgent) -> None:
        draft = create_mock_draft()
        ir = run(mock_formalizer.formalize(draft))
        is_valid, errors = run(mock_formalizer.validate_structure(ir))
        assert is_valid is True
        assert len(errors) == 0

    def test_repair_ir(self, mock_formalizer: MockFormalizerAgent) -> None:
        draft = create_mock_draft()
        ir = run(mock_formalizer.formalize(draft))
        repaired = run(
            mock_formalizer.repair_ir(
                ir,
                errors=["Missing time_semantics"],
                hint="Add time semantics",
            )
        )
        assert repaired is not None

    def test_formalize_schema_version_override(self, mock_formalizer: MockFormalizerAgent) -> None:
        draft = create_mock_draft()
        ir = run(mock_formalizer.formalize(draft, schema_version="1.0"))
        assert ir.schema_version == "1.0"


class TestCriticAgentRuntime:
    def test_critique_returns_report(
        self,
        mock_critic: MockCriticAgent,
        mock_formalizer: MockFormalizerAgent,
        sample_problem_frame: ProblemFrame,
        sample_draft: DraftResult,
    ) -> None:
        ir = run(mock_formalizer.formalize(sample_draft))
        report = run(mock_critic.critique(ir, sample_problem_frame))
        assert isinstance(report, CritiqueReport)
        assert report.report_id
        assert report.verdict in ("APPROVE", "NEEDS_REVISION", "REJECT")
        assert 0.0 <= report.alignment_score <= 1.0
        assert 0.0 <= report.completeness_score <= 1.0

    def test_critique_with_depth_levels(
        self,
        mock_critic: MockCriticAgent,
        mock_formalizer: MockFormalizerAgent,
        sample_problem_frame: ProblemFrame,
        sample_draft: DraftResult,
    ) -> None:
        ir = run(mock_formalizer.formalize(sample_draft))
        for depth in ("quick", "standard", "deep"):
            report = run(mock_critic.critique(ir, sample_problem_frame, depth=depth))
            assert report.metadata["depth"] == depth

    def test_generate_hint_from_issues(self, mock_critic: MockCriticAgent) -> None:
        issues = [
            CritiqueIssue(
                issue_id="issue_001",
                category=CritiqueCategory.COMPLETENESS,
                severity=CritiqueSeverity.BLOCKER,
                message="No interventions defined",
                suggestion="Add at least one intervention",
            ),
            CritiqueIssue(
                issue_id="issue_002",
                category=CritiqueCategory.ALIGNMENT,
                severity=CritiqueSeverity.WARNING,
                message="Low alignment score",
                suggestion="Review goals",
            ),
        ]
        hint = run(mock_critic.generate_hint(issues))
        assert isinstance(hint, str)
        assert "intervention" in hint.lower()
        assert len(hint) > 0

    def test_check_alignment(
        self,
        mock_critic: MockCriticAgent,
        mock_formalizer: MockFormalizerAgent,
        sample_problem_frame: ProblemFrame,
        sample_draft: DraftResult,
    ) -> None:
        ir = run(mock_formalizer.formalize(sample_draft))
        score = run(mock_critic.check_alignment(ir, sample_problem_frame))
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0


class TestAgentPipeline:
    def test_full_pipeline_flow(
        self,
        mock_pi: MockPIAgent,
        mock_drafter: MockDrafterAgent,
        mock_formalizer: MockFormalizerAgent,
        mock_critic: MockCriticAgent,
    ) -> None:
        from polisyos.ir.trinity import TrinityBundle

        user_request = "Reduce poverty by 20% through targeted subsidies"
        tasks = run(mock_pi.decompose_task(user_request))
        problem_frame = run(mock_pi.create_problem_frame(user_request))

        assert len(tasks) > 0
        assert problem_frame.frame_id

        draft = run(mock_drafter.draft_policy(problem_frame))
        assert draft.problem_frame_ref == problem_frame.frame_id

        ir = run(mock_formalizer.formalize(draft))
        assert isinstance(ir, TrinityBundle)
        is_valid, errors = run(mock_formalizer.validate_structure(ir))
        assert is_valid, f"IR validation failed: {errors}"

        report = run(mock_critic.critique(ir, problem_frame))
        assert report.verdict in ("APPROVE", "NEEDS_REVISION", "REJECT")

        if report.verdict == "NEEDS_REVISION":
            hint = run(mock_critic.generate_hint(report.issues))
            assert hint
            refined_draft = run(mock_drafter.refine_draft(draft, report))
            assert refined_draft.draft_id != draft.draft_id

    def test_reflexion_loop_convergence(
        self,
        mock_drafter: MockDrafterAgent,
        mock_formalizer: MockFormalizerAgent,
        mock_critic: MockCriticAgent,
        sample_problem_frame: ProblemFrame,
    ) -> None:
        max_iterations = 5
        current_draft = run(mock_drafter.draft_policy(sample_problem_frame))

        for iteration in range(max_iterations):
            ir = run(mock_formalizer.formalize(current_draft))
            report = run(mock_critic.critique(ir, sample_problem_frame))
            if report.verdict == "APPROVE":
                break
            current_draft = run(mock_drafter.refine_draft(current_draft, report))

        assert iteration < max_iterations or report.verdict == "APPROVE"


class TestBackwardCompatibility:
    def test_legacy_mock_agent_still_works(self) -> None:
        import pandas as pd
        from polisyos.ir.trinity import TrinityBundle

        agent = MockAgent()
        context_df = pd.DataFrame(
            {
                "unemployment_rate": [0.05, 0.06],
                "budget_balance": [1000, 500],
            }
        )

        ir = agent.decide(step=1, context_df=context_df)
        assert isinstance(ir, TrinityBundle)

    def test_legacy_base_agent_is_abstract(self) -> None:
        with pytest.raises(TypeError):
            BaseAgent()  # type: ignore[abstract]

    def test_drafter_node_function_exists(self) -> None:
        from polisyos.scientist.agent import drafter_node

        assert callable(drafter_node)


class TestDataTypes:
    def test_problem_frame_immutability(self) -> None:
        frame = ProblemFrame(
            frame_id="pf_immutable_test", domain="economic", problem_statement="Test"
        )
        with pytest.raises((AttributeError, TypeError)):
            frame.domain = "changed"  # type: ignore[misc]

    def test_subtask_immutability(self) -> None:
        task = SubTask(
            task_id="task_immutable_test",
            description="Test",
            target_agent=AgentRole.DRAFTER,
        )
        with pytest.raises((AttributeError, TypeError)):
            task.description = "changed"  # type: ignore[misc]

    def test_critique_report_properties(self) -> None:
        report = CritiqueReport(
            report_id="report_test",
            ir_ref="ir_test",
            problem_frame_ref="pf_test",
            verdict="NEEDS_REVISION",
            issues=[
                CritiqueIssue(
                    issue_id="i1",
                    category=CritiqueCategory.COMPLETENESS,
                    severity=CritiqueSeverity.BLOCKER,
                    message="Blocker issue",
                ),
                CritiqueIssue(
                    issue_id="i2",
                    category=CritiqueCategory.ALIGNMENT,
                    severity=CritiqueSeverity.WARNING,
                    message="Warning issue",
                ),
                CritiqueIssue(
                    issue_id="i3",
                    category=CritiqueCategory.ALIGNMENT,
                    severity=CritiqueSeverity.WARNING,
                    message="Another warning",
                ),
            ],
        )

        assert report.has_blockers is True
        assert report.blocker_count == 1
        assert report.warning_count == 2

    def test_draft_result_mutable(self) -> None:
        draft = DraftResult(
            draft_id="draft_mutable_test",
            problem_frame_ref="pf_test",
            narrative="Original",
        )

        draft.narrative = "Updated"
        assert draft.narrative == "Updated"

    def test_enum_values(self) -> None:
        assert AgentRole.PI.value == "pi"
        assert TaskPriority.CRITICAL.value == "critical"
        assert TaskStatus.PENDING.value == "pending"
        assert CritiqueSeverity.BLOCKER.value == "blocker"
        assert CritiqueCategory.ALIGNMENT.value == "alignment"
