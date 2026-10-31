from __future__ import annotations

from unittest.mock import patch

from polisyos.scientist.nodes.builtins.planning.plan_policy_request import PlanPolicyRequestNode
from polisyos.scientist.nodes.builtins.state_keys import ARTIFACT_POLICY_REQUEST_FRAME_REF
from polisyos.scientist.orchestration.engine.state_branching import (
    branch_state as real_branch_state,
)
from polisyos.scientist.validation.policy_verified import PolicyRequestFrame


def test_plan_policy_request_success(execution_context, minimal_state, artifact_ref_factory):
    """Successfully creates a policy request frame."""
    frame_ref = artifact_ref_factory(kind="scientist.policy_request_frame")
    mock_frame = PolicyRequestFrame(
        schema_version="1.1",
        request_id="req-001",
        policy_question="What is the effect?",
        jurisdiction="US",
        jurisdiction_source="policy_request_jurisdiction",
    )
    with (
        patch(
            "polisyos.scientist.nodes.builtins.planning.plan_policy_request.build_policy_request_frame",
            return_value=mock_frame,
        ),
        patch(
            "polisyos.scientist.nodes.builtins.planning.plan_policy_request.persist_policy_request_frame",
            return_value=frame_ref,
        ),
    ):
        state = minimal_state.model_copy(
            update={"params": {"policy_question": "What is the effect?"}}
        )
        outcome = PlanPolicyRequestNode().execute(execution_context, state)
    assert outcome.status == "ok"
    assert outcome.state.policy_request_ref is not None
    assert ARTIFACT_POLICY_REQUEST_FRAME_REF in outcome.state.artifacts_index


def test_plan_policy_request_reissues_existing_projection(
    execution_context, minimal_state, artifact_ref_factory
):
    """A cached reference is not a current request receipt."""
    ref = artifact_ref_factory(kind="scientist.policy_request_frame")
    state = minimal_state.model_copy(deep=True)
    state.policy_request_ref = ref
    state.artifacts_index[ARTIFACT_POLICY_REQUEST_FRAME_REF] = ref
    state.params.update({"policy_question": "Synthetic new question?", "jurisdiction": "synthetic"})
    outcome = PlanPolicyRequestNode().execute(execution_context, state)
    assert outcome.status == "ok"
    assert outcome.state is not state
    assert outcome.state.policy_request_ref != ref
    assert state.policy_request_ref == ref


def test_plan_policy_request_error(execution_context, minimal_state):
    """When build_policy_request_frame raises, the exception propagates."""
    with patch(
        "polisyos.scientist.nodes.builtins.planning.plan_policy_request.build_policy_request_frame",
        side_effect=ValueError("bad question"),
    ):
        try:
            PlanPolicyRequestNode().execute(execution_context, minimal_state)
            raised = False
        except (ValueError, Exception):
            raised = True
    assert raised


def test_plan_policy_request_uses_branch_state_for_declared_outputs(
    execution_context, minimal_state, artifact_ref_factory
):
    frame_ref = artifact_ref_factory(kind="scientist.policy_request_frame")
    mock_frame = PolicyRequestFrame(
        schema_version="1.1",
        request_id="req-branch",
        policy_question="What is the effect?",
        jurisdiction="US",
        jurisdiction_source="policy_request_jurisdiction",
    )
    state = minimal_state.model_copy(deep=True)
    state.params["nested"] = {"baseline": True}
    observed: dict[str, tuple[str, ...]] = {}

    def _spy_branch(base_state, *, write_paths=()):
        observed["write_paths"] = tuple(write_paths)
        return real_branch_state(base_state, write_paths=write_paths)

    with (
        patch(
            "polisyos.scientist.nodes.builtins.planning.plan_policy_request.branch_state",
            _spy_branch,
        ),
        patch(
            "polisyos.scientist.nodes.builtins.planning.plan_policy_request.build_policy_request_frame",
            return_value=mock_frame,
        ),
        patch(
            "polisyos.scientist.nodes.builtins.planning.plan_policy_request.persist_policy_request_frame",
            return_value=frame_ref,
        ),
    ):
        outcome = PlanPolicyRequestNode().execute(execution_context, state)

    assert outcome.status == "ok"
    assert observed["write_paths"] == (
        "policy_request_ref",
        "artifacts_index.policy_request_frame_ref",
        "params.policy_answer_mode",
        "execution_profile",
    )
    assert state.params["nested"] == {"baseline": True}
    assert ARTIFACT_POLICY_REQUEST_FRAME_REF not in state.artifacts_index
    assert outcome.state.policy_request_ref == frame_ref
