from __future__ import annotations

from dataclasses import replace
from unittest.mock import MagicMock

from polisyos.scientist.nodes.builtins.compile.compile_foundry import CompileFoundryNode
from polisyos.scientist.nodes.builtins.compile.formalize_verified_policy import (
    FormalizeVerifiedPolicyNode,
)
from polisyos.scientist.nodes.builtins.state_keys import (
    INPUT_TRINITY_BUNDLE_REF,
)
from polisyos.scientist.validation.policy_verified.models import (
    PolicyOption,
    PolicyOptionSet,
    PolicyRequestFrame,
)
from polisyos.scientist.validation.policy_verified.service import formalize_policy_option_set
from polisyos.scientist.validation.policy_verified.testing import (
    formalize_policy_option_set_for_contract_testing,
)


def test_missing_supplied_trinity_fails_typed_without_fixture(
    execution_context,
    minimal_state,
    artifact_ref_factory,
):
    """Missing real Trinity input refuses instead of synthesizing a mock policy."""
    request_ref = artifact_ref_factory(kind="scientist.policy_request_frame")
    option_ref = artifact_ref_factory(kind="scientist.policy_option_set")

    state = minimal_state.model_copy(deep=True)
    state.policy_request_ref = request_ref
    state.policy_option_set_ref = option_ref

    outcome = FormalizeVerifiedPolicyNode().execute(execution_context, state)

    assert outcome.status == "fail"
    assert outcome.error is not None
    assert outcome.error.code == "policy_verified_hardcoded_formalizer_strangled"
    assert outcome.error.details == {"required": [INPUT_TRINITY_BUNDLE_REF]}
    assert outcome.artifacts == []
    assert INPUT_TRINITY_BUNDLE_REF not in outcome.state.inputs
    assert "policy_trinity_generated" not in outcome.state.params


def test_production_formalizer_only_resolves_supplied_trinity(
    execution_context,
    minimal_state,
    artifact_ref_factory,
):
    frame = PolicyRequestFrame(request_id="request_production", policy_question="Real policy?")
    option_set = PolicyOptionSet(
        request_id="request_production",
        verified_options=[
            PolicyOption(
                option_id="option_production",
                title="Supplied only",
                summary="Must not be synthesized in production.",
            )
        ],
    )
    assert (
        formalize_policy_option_set(
            execution_context,
            minimal_state,
            frame,
            option_set,
        )
        is None
    )

    trinity_ref = artifact_ref_factory(kind="ir.trinity_bundle")
    state = minimal_state.model_copy(deep=True)
    state.inputs[INPUT_TRINITY_BUNDLE_REF] = trinity_ref

    resolved = formalize_policy_option_set(
        execution_context,
        state,
        frame,
        option_set,
    )

    assert resolved is not None
    assert resolved.model_dump(mode="json") == trinity_ref.model_dump(mode="json")


def test_formalize_missing_policy_option_set_ref(execution_context, minimal_state):
    """Missing request/option refs cannot bypass the required Trinity input."""
    outcome = FormalizeVerifiedPolicyNode().execute(execution_context, minimal_state)
    assert outcome.status == "fail"
    assert outcome.error is not None
    assert outcome.error.code == "policy_verified_hardcoded_formalizer_strangled"


def test_formalize_already_has_trinity(execution_context, minimal_state, artifact_ref_factory):
    """When trinity_bundle_ref is already in inputs, no-op."""
    trinity_ref = artifact_ref_factory(kind="ir.trinity_bundle")
    state = minimal_state.model_copy(deep=True)
    state.inputs[INPUT_TRINITY_BUNDLE_REF] = trinity_ref
    outcome = FormalizeVerifiedPolicyNode().execute(execution_context, state)
    assert outcome.status == "ok"
    assert outcome.state is state


def test_formalize_verified_policy_refusal_does_not_branch_or_write(
    execution_context,
    minimal_state,
):
    state = minimal_state.model_copy(deep=True)
    state.params["nested"] = {"baseline": True}
    outcome = FormalizeVerifiedPolicyNode().execute(execution_context, state)

    assert outcome.status == "fail"
    assert outcome.state is state
    assert INPUT_TRINITY_BUNDLE_REF not in state.inputs
    assert state.params["nested"] == {"baseline": True}
    assert "policy_trinity_generated" not in state.params


def test_contract_testing_fixture_is_stamped_and_compile_rejects_it(
    execution_context,
    minimal_state,
):
    fixture = formalize_policy_option_set_for_contract_testing(
        execution_context,
        PolicyRequestFrame(request_id="request_test", policy_question="Test policy?"),
        PolicyOptionSet(
            request_id="request_test",
            verified_options=[
                PolicyOption(
                    option_id="option_test",
                    title="Contract fixture",
                    summary="Contract fixture only.",
                )
            ],
        ),
    )

    assert fixture.authority_scope == "contract_testing"
    assert fixture.promotion_allowed is False
    assert fixture.non_promotable_reason == "policy_verified_contract_fixture_non_promotable"
    assert fixture.artifact_ref.kind == "ir.trinity_bundle.contract_testing"

    foundry = MagicMock()
    ctx = replace(execution_context, foundry=foundry)
    state = minimal_state.model_copy(deep=True)
    state.inputs[INPUT_TRINITY_BUNDLE_REF] = fixture.artifact_ref
    outcome = CompileFoundryNode().execute(ctx, state)

    assert outcome.status == "fail"
    assert outcome.error is not None
    assert outcome.error.code == "node.invalid_state"
    foundry.compile.assert_not_called()
