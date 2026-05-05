from __future__ import annotations

from unittest.mock import MagicMock, patch

from polisyos.scientist.engine.state_branching import branch_state as real_branch_state
from polisyos.scientist.nodes.builtins.compile.formalize_verified_policy import (
    FormalizeVerifiedPolicyNode,
)
from polisyos.scientist.nodes.builtins.state_keys import (
    INPUT_TRINITY_BUNDLE_REF,
)


def test_formalize_success(execution_context, minimal_state, artifact_ref_factory):
    """Formalizes policy options into a Trinity bundle."""
    request_ref = artifact_ref_factory(kind="scientist.policy_request_frame")
    option_ref = artifact_ref_factory(kind="scientist.policy_option_set")
    trinity_ref = artifact_ref_factory(kind="ir.trinity_bundle")

    mock_frame = MagicMock()
    mock_option_set = MagicMock()

    state = minimal_state.model_copy(deep=True)
    state.policy_request_ref = request_ref
    state.policy_option_set_ref = option_ref

    with (
        patch(
            "polisyos.scientist.nodes.builtins.compile.formalize_verified_policy.load_policy_request_frame",
            return_value=mock_frame,
        ),
        patch(
            "polisyos.scientist.nodes.builtins.compile.formalize_verified_policy.load_policy_option_set",
            return_value=mock_option_set,
        ),
        patch(
            "polisyos.scientist.nodes.builtins.compile.formalize_verified_policy.formalize_policy_option_set",
            return_value=trinity_ref,
        ),
    ):
        outcome = FormalizeVerifiedPolicyNode().execute(execution_context, state)

    assert outcome.status == "ok"
    assert outcome.state.inputs.get(INPUT_TRINITY_BUNDLE_REF) == trinity_ref
    assert outcome.state.params.get("policy_trinity_generated") is True


def test_formalize_missing_policy_option_set_ref(execution_context, minimal_state):
    """When both request and option refs are missing, returns skip."""
    outcome = FormalizeVerifiedPolicyNode().execute(execution_context, minimal_state)
    assert outcome.status == "skip"


def test_formalize_already_has_trinity(execution_context, minimal_state, artifact_ref_factory):
    """When trinity_bundle_ref is already in inputs, no-op."""
    trinity_ref = artifact_ref_factory(kind="ir.trinity_bundle")
    state = minimal_state.model_copy(deep=True)
    state.inputs[INPUT_TRINITY_BUNDLE_REF] = trinity_ref
    outcome = FormalizeVerifiedPolicyNode().execute(execution_context, state)
    assert outcome.status == "ok"
    assert outcome.state is state


def test_formalize_verified_policy_uses_branch_state_for_inputs_and_params(
    execution_context,
    minimal_state,
    artifact_ref_factory,
):
    request_ref = artifact_ref_factory(kind="scientist.policy_request_frame")
    option_ref = artifact_ref_factory(kind="scientist.policy_option_set")
    trinity_ref = artifact_ref_factory(kind="ir.trinity_bundle")

    state = minimal_state.model_copy(deep=True)
    state.policy_request_ref = request_ref
    state.policy_option_set_ref = option_ref
    state.params["nested"] = {"baseline": True}
    observed: dict[str, tuple[str, ...]] = {}

    def _spy_branch(base_state, *, write_paths=()):
        observed["write_paths"] = tuple(write_paths)
        return real_branch_state(base_state, write_paths=write_paths)

    with (
        patch(
            "polisyos.scientist.nodes.builtins.compile.formalize_verified_policy.branch_state",
            _spy_branch,
        ),
        patch(
            "polisyos.scientist.nodes.builtins.compile.formalize_verified_policy.load_policy_request_frame",
            return_value=MagicMock(),
        ),
        patch(
            "polisyos.scientist.nodes.builtins.compile.formalize_verified_policy.load_policy_option_set",
            return_value=MagicMock(),
        ),
        patch(
            "polisyos.scientist.nodes.builtins.compile.formalize_verified_policy.formalize_policy_option_set",
            return_value=trinity_ref,
        ),
    ):
        outcome = FormalizeVerifiedPolicyNode().execute(execution_context, state)

    assert outcome.status == "ok"
    assert observed["write_paths"] == (
        "inputs.trinity_bundle_ref",
        "params.policy_trinity_generated",
    )
    assert INPUT_TRINITY_BUNDLE_REF not in state.inputs
    assert state.params["nested"] == {"baseline": True}
    assert outcome.state.inputs[INPUT_TRINITY_BUNDLE_REF] == trinity_ref
    assert outcome.state.params["policy_trinity_generated"] is True
