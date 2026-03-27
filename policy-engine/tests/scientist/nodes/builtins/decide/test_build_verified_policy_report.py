from __future__ import annotations

from unittest.mock import MagicMock, patch

from polisyos.scientist.nodes.builtins.decide.build_verified_policy_report import (
    BuildVerifiedPolicyReportNode,
)
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_VERIFIED_POLICY_REPORT_REF,
)


def test_report_success(execution_context, minimal_state, artifact_ref_factory):
    """Successfully builds a verified policy report."""
    request_ref = artifact_ref_factory(kind="scientist.policy_request_frame")
    option_ref = artifact_ref_factory(kind="scientist.policy_option_set")
    report_ref = artifact_ref_factory(kind="scientist.source_verification_report")
    payload_ref = artifact_ref_factory(kind="scientist.verified_policy_report")

    mock_frame = MagicMock()
    mock_option_set = MagicMock()
    mock_verification = MagicMock()
    mock_payload = MagicMock()
    mock_payload.verified_findings = [MagicMock()]
    mock_payload.needs_expert_review = False

    state = minimal_state.model_copy(deep=True)
    state.policy_request_ref = request_ref
    state.policy_option_set_ref = option_ref
    state.source_verification_report_ref = report_ref

    with (
        patch(
            "polisyos.scientist.nodes.builtins.decide.build_verified_policy_report.load_policy_request_frame",
            return_value=mock_frame,
        ),
        patch(
            "polisyos.scientist.nodes.builtins.decide.build_verified_policy_report.load_policy_option_set",
            return_value=mock_option_set,
        ),
        patch(
            "polisyos.scientist.nodes.builtins.decide.build_verified_policy_report.load_source_verification_report",
            return_value=mock_verification,
        ),
        patch(
            "polisyos.scientist.nodes.builtins.decide.build_verified_policy_report.build_verified_policy_report",
            return_value=mock_payload,
        ),
        patch(
            "polisyos.scientist.nodes.builtins.decide.build_verified_policy_report.persist_verified_policy_report",
            return_value=payload_ref,
        ),
    ):
        outcome = BuildVerifiedPolicyReportNode().execute(execution_context, state)

    assert outcome.status == "ok"
    assert ARTIFACT_VERIFIED_POLICY_REPORT_REF in outcome.state.artifacts_index
    assert outcome.state.verified_policy_report_ref == payload_ref


def test_report_missing_inputs(execution_context, minimal_state):
    """When required refs are missing, returns skip."""
    outcome = BuildVerifiedPolicyReportNode().execute(execution_context, minimal_state)
    assert outcome.status == "skip"


def test_report_already_exists(execution_context, minimal_state, artifact_ref_factory):
    """When verified_policy_report_ref is already set, no-op."""
    ref = artifact_ref_factory(kind="scientist.verified_policy_report")
    state = minimal_state.model_copy(deep=True)
    state.verified_policy_report_ref = ref
    state.artifacts_index[ARTIFACT_VERIFIED_POLICY_REPORT_REF] = ref
    outcome = BuildVerifiedPolicyReportNode().execute(execution_context, state)
    assert outcome.status == "ok"
    assert outcome.state is state
