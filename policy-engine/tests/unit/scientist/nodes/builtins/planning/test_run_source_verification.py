from __future__ import annotations

from unittest.mock import MagicMock, patch

from polisyos.scientist.orchestration.engine.state_branching import branch_state as real_branch_state
from polisyos.scientist.nodes.builtins.planning.run_source_verification import (
    RunSourceVerificationNode,
)
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_SOURCE_VERIFICATION_REPORT_REF,
)


def test_source_verification_uses_branch_state_for_declared_outputs(
    execution_context, minimal_state, artifact_ref_factory
):
    request_ref = artifact_ref_factory(kind="scientist.policy_request_frame")
    candidate_ref = artifact_ref_factory(kind="scientist.legal_candidate_pack")
    source_ref = artifact_ref_factory(kind="scientist.legal_source_pack")
    report_ref = artifact_ref_factory(kind="scientist.source_verification_report")
    mock_report = MagicMock()
    mock_report.verified_claims = []
    mock_report.unresolved_critical_gaps = []
    mock_report.verification_cycles_completed = 1

    state = minimal_state.model_copy(deep=True)
    state.policy_request_ref = request_ref
    state.legal_candidate_pack_ref = candidate_ref
    state.legal_source_pack_ref = source_ref
    state.params["nested"] = {"baseline": True}
    observed: dict[str, tuple[str, ...]] = {}

    def _spy_branch(base_state, *, write_paths=()):
        observed["write_paths"] = tuple(write_paths)
        return real_branch_state(base_state, write_paths=write_paths)

    with (
        patch(
            "polisyos.scientist.nodes.builtins.planning.run_source_verification.branch_state",
            _spy_branch,
        ),
        patch(
            "polisyos.scientist.nodes.builtins.planning.run_source_verification.load_policy_request_frame",
            return_value=MagicMock(),
        ),
        patch(
            "polisyos.scientist.nodes.builtins.planning.run_source_verification.load_legal_candidate_pack",
            return_value=MagicMock(),
        ),
        patch(
            "polisyos.scientist.nodes.builtins.planning.run_source_verification.load_legal_source_pack",
            return_value=MagicMock(),
        ),
        patch(
            "polisyos.scientist.nodes.builtins.planning.run_source_verification.verify_source_pack",
            return_value=mock_report,
        ),
        patch(
            "polisyos.scientist.nodes.builtins.planning.run_source_verification.persist_source_verification_report",
            return_value=report_ref,
        ),
    ):
        outcome = RunSourceVerificationNode().execute(execution_context, state)

    assert outcome.status == "ok"
    assert observed["write_paths"] == (
        "source_verification_report_ref",
        "artifacts_index.source_verification_report_ref",
        "params.verification_cycles_completed",
    )
    assert state.params["nested"] == {"baseline": True}
    assert ARTIFACT_SOURCE_VERIFICATION_REPORT_REF not in state.artifacts_index
    assert outcome.state.source_verification_report_ref == report_ref
