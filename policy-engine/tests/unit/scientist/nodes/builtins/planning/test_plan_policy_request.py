from __future__ import annotations

from unittest.mock import MagicMock, patch

from polisyos.scientist.orchestration.engine.state_branching import branch_state as real_branch_state
from polisyos.scientist.nodes.builtins.planning.plan_policy_request import PlanPolicyRequestNode
from polisyos.scientist.nodes.builtins.state_keys import ARTIFACT_POLICY_REQUEST_FRAME_REF


def test_plan_policy_request_success(execution_context, minimal_state, artifact_ref_factory):
    """Successfully creates a policy request frame."""
    frame_ref = artifact_ref_factory(kind="scientist.policy_request_frame")
    mock_frame = MagicMock()
    mock_frame.jurisdiction = "US"
    mock_frame.request_id = "req-001"
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


def test_plan_policy_request_already_exists(execution_context, minimal_state, artifact_ref_factory):
    """When policy_request_ref is already set, the node is a no-op."""
    ref = artifact_ref_factory(kind="scientist.policy_request_frame")
    state = minimal_state.model_copy(deep=True)
    state.policy_request_ref = ref
    state.artifacts_index[ARTIFACT_POLICY_REQUEST_FRAME_REF] = ref
    outcome = PlanPolicyRequestNode().execute(execution_context, state)
    assert outcome.status == "ok"
    # State unchanged (same object)
    assert outcome.state is state


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
    mock_frame = MagicMock()
    mock_frame.jurisdiction = "US"
    mock_frame.request_id = "req-branch"
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
