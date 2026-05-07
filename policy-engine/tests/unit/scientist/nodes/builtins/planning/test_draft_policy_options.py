from __future__ import annotations

from unittest.mock import MagicMock, patch

from polisyos.scientist.orchestration.engine.state_branching import branch_state as real_branch_state
from polisyos.scientist.nodes.builtins.planning.draft_policy_options import DraftPolicyOptionsNode
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_POLICY_OPTION_SET_REF,
)


def test_draft_success(execution_context, minimal_state, artifact_ref_factory):
    """Successfully drafts policy options from request frame + verification report."""
    request_ref = artifact_ref_factory(kind="scientist.policy_request_frame")
    report_ref = artifact_ref_factory(kind="scientist.source_verification_report")
    option_ref = artifact_ref_factory(kind="scientist.policy_option_set")
    mock_frame = MagicMock()
    mock_report = MagicMock()
    mock_option_set = MagicMock()
    mock_option_set.verified_options = [MagicMock()]
    mock_option_set.hypothesis_options = []
    state = minimal_state.model_copy(deep=True)
    state.policy_request_ref = request_ref
    state.source_verification_report_ref = report_ref
    with (
        patch(
            "polisyos.scientist.nodes.builtins.planning.draft_policy_options.load_policy_request_frame",
            return_value=mock_frame,
        ),
        patch(
            "polisyos.scientist.nodes.builtins.planning.draft_policy_options.load_source_verification_report",
            return_value=mock_report,
        ),
        patch(
            "polisyos.scientist.nodes.builtins.planning.draft_policy_options.draft_policy_option_set",
            return_value=mock_option_set,
        ),
        patch(
            "polisyos.scientist.nodes.builtins.planning.draft_policy_options.persist_policy_option_set",
            return_value=option_ref,
        ),
    ):
        outcome = DraftPolicyOptionsNode().execute(execution_context, state)
    assert outcome.status == "ok"
    assert ARTIFACT_POLICY_OPTION_SET_REF in outcome.state.artifacts_index
    assert outcome.state.policy_option_set_ref == option_ref


def test_draft_no_options_missing_refs(execution_context, minimal_state):
    """When request or report refs are missing, returns skip."""
    outcome = DraftPolicyOptionsNode().execute(execution_context, minimal_state)
    assert outcome.status == "skip"


def test_draft_already_exists(execution_context, minimal_state, artifact_ref_factory):
    """When policy_option_set_ref is already set, no-op."""
    ref = artifact_ref_factory(kind="scientist.policy_option_set")
    state = minimal_state.model_copy(deep=True)
    state.policy_option_set_ref = ref
    state.artifacts_index[ARTIFACT_POLICY_OPTION_SET_REF] = ref
    outcome = DraftPolicyOptionsNode().execute(execution_context, state)
    assert outcome.status == "ok"
    assert outcome.state is state


def test_draft_policy_options_uses_branch_state_for_declared_outputs(
    execution_context, minimal_state, artifact_ref_factory
):
    request_ref = artifact_ref_factory(kind="scientist.policy_request_frame")
    report_ref = artifact_ref_factory(kind="scientist.source_verification_report")
    option_ref = artifact_ref_factory(kind="scientist.policy_option_set")
    mock_option_set = MagicMock()
    mock_option_set.verified_options = []
    mock_option_set.hypothesis_options = []
    state = minimal_state.model_copy(deep=True)
    state.policy_request_ref = request_ref
    state.source_verification_report_ref = report_ref
    state.params["nested"] = {"baseline": True}
    observed: dict[str, tuple[str, ...]] = {}

    def _spy_branch(base_state, *, write_paths=()):
        observed["write_paths"] = tuple(write_paths)
        return real_branch_state(base_state, write_paths=write_paths)

    with (
        patch(
            "polisyos.scientist.nodes.builtins.planning.draft_policy_options.branch_state",
            _spy_branch,
        ),
        patch(
            "polisyos.scientist.nodes.builtins.planning.draft_policy_options.load_policy_request_frame",
            return_value=MagicMock(),
        ),
        patch(
            "polisyos.scientist.nodes.builtins.planning.draft_policy_options.load_source_verification_report",
            return_value=MagicMock(),
        ),
        patch(
            "polisyos.scientist.nodes.builtins.planning.draft_policy_options.draft_policy_option_set",
            return_value=mock_option_set,
        ),
        patch(
            "polisyos.scientist.nodes.builtins.planning.draft_policy_options.persist_policy_option_set",
            return_value=option_ref,
        ),
    ):
        outcome = DraftPolicyOptionsNode().execute(execution_context, state)

    assert outcome.status == "ok"
    assert observed["write_paths"] == (
        "policy_option_set_ref",
        "artifacts_index.policy_option_set_ref",
    )
    assert state.params["nested"] == {"baseline": True}
    assert ARTIFACT_POLICY_OPTION_SET_REF not in state.artifacts_index
    assert outcome.state.policy_option_set_ref == option_ref
