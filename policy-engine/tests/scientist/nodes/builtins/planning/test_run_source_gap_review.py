from __future__ import annotations

from unittest.mock import MagicMock, patch

from polisyos.scientist.engine.state_branching import branch_state as real_branch_state
from polisyos.scientist.nodes.builtins.planning.run_source_gap_review import RunSourceGapReviewNode
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_LEGAL_CANDIDATE_PACK_REF,
    ARTIFACT_LEGAL_SOURCE_PACK_REF,
    ARTIFACT_SOURCE_VERIFICATION_REPORT_REF,
)


def test_no_gaps_skip_when_missing_refs(execution_context, minimal_state):
    """When required refs are missing, node skips."""
    outcome = RunSourceGapReviewNode().execute(execution_context, minimal_state)
    assert outcome.status == "skip"


def test_gaps_found_success(execution_context, minimal_state, artifact_ref_factory):
    """When all refs present, gap review runs and produces updated artifacts."""
    request_ref = artifact_ref_factory(kind="scientist.policy_request_frame")
    candidate_ref = artifact_ref_factory(kind="scientist.legal_candidate_pack")
    source_ref = artifact_ref_factory(kind="scientist.legal_source_pack")
    report_ref = artifact_ref_factory(kind="scientist.source_verification_report")

    state = minimal_state.model_copy(deep=True)
    state.policy_request_ref = request_ref
    state.legal_candidate_pack_ref = candidate_ref
    state.legal_source_pack_ref = source_ref
    state.source_verification_report_ref = report_ref

    mock_frame = MagicMock()
    mock_candidate_pack = MagicMock()
    mock_source_pack = MagicMock()
    mock_report = MagicMock()

    updated_candidate = MagicMock()
    updated_source = MagicMock()
    updated_report = MagicMock()
    updated_report.unresolved_critical_gaps = []
    updated_report.needs_expert_review = False
    updated_report.verification_cycles_completed = 1

    updated_candidate_ref = artifact_ref_factory(kind="scientist.legal_candidate_pack")
    updated_source_ref = artifact_ref_factory(kind="scientist.legal_source_pack")
    updated_report_ref = artifact_ref_factory(kind="scientist.source_verification_report")

    with (
        patch(
            "polisyos.scientist.nodes.builtins.planning.run_source_gap_review.load_policy_request_frame",
            return_value=mock_frame,
        ),
        patch(
            "polisyos.scientist.nodes.builtins.planning.run_source_gap_review.load_legal_candidate_pack",
            return_value=mock_candidate_pack,
        ),
        patch(
            "polisyos.scientist.nodes.builtins.planning.run_source_gap_review.load_legal_source_pack",
            return_value=mock_source_pack,
        ),
        patch(
            "polisyos.scientist.nodes.builtins.planning.run_source_gap_review.load_source_verification_report",
            return_value=mock_report,
        ),
        patch(
            "polisyos.scientist.nodes.builtins.planning.run_source_gap_review.recover_source_gaps",
            return_value=(updated_candidate, updated_source, updated_report),
        ),
        patch(
            "polisyos.scientist.nodes.builtins.planning.run_source_gap_review.persist_legal_candidate_pack",
            return_value=updated_candidate_ref,
        ),
        patch(
            "polisyos.scientist.nodes.builtins.planning.run_source_gap_review.persist_legal_source_pack",
            return_value=updated_source_ref,
        ),
        patch(
            "polisyos.scientist.nodes.builtins.planning.run_source_gap_review.persist_source_verification_report",
            return_value=updated_report_ref,
        ),
    ):
        outcome = RunSourceGapReviewNode().execute(execution_context, state)

    assert outcome.status == "ok"
    assert ARTIFACT_LEGAL_CANDIDATE_PACK_REF in outcome.state.artifacts_index
    assert ARTIFACT_LEGAL_SOURCE_PACK_REF in outcome.state.artifacts_index
    assert ARTIFACT_SOURCE_VERIFICATION_REPORT_REF in outcome.state.artifacts_index
    assert outcome.state.params.get("needs_expert_review") is False
    assert outcome.state.params.get("verification_cycles_completed") == 1


def test_gaps_error_propagates(execution_context, minimal_state, artifact_ref_factory):
    """When recover_source_gaps raises, the exception propagates."""
    request_ref = artifact_ref_factory(kind="scientist.policy_request_frame")
    candidate_ref = artifact_ref_factory(kind="scientist.legal_candidate_pack")
    source_ref = artifact_ref_factory(kind="scientist.legal_source_pack")
    report_ref = artifact_ref_factory(kind="scientist.source_verification_report")

    state = minimal_state.model_copy(deep=True)
    state.policy_request_ref = request_ref
    state.legal_candidate_pack_ref = candidate_ref
    state.legal_source_pack_ref = source_ref
    state.source_verification_report_ref = report_ref

    with (
        patch(
            "polisyos.scientist.nodes.builtins.planning.run_source_gap_review.load_policy_request_frame",
            return_value=MagicMock(),
        ),
        patch(
            "polisyos.scientist.nodes.builtins.planning.run_source_gap_review.load_legal_candidate_pack",
            return_value=MagicMock(),
        ),
        patch(
            "polisyos.scientist.nodes.builtins.planning.run_source_gap_review.load_legal_source_pack",
            return_value=MagicMock(),
        ),
        patch(
            "polisyos.scientist.nodes.builtins.planning.run_source_gap_review.load_source_verification_report",
            return_value=MagicMock(),
        ),
        patch(
            "polisyos.scientist.nodes.builtins.planning.run_source_gap_review.recover_source_gaps",
            side_effect=RuntimeError("gap recovery failed"),
        ),
    ):
        try:
            RunSourceGapReviewNode().execute(execution_context, state)
            raised = False
        except RuntimeError:
            raised = True
    assert raised


def test_gap_review_uses_branch_state_for_declared_outputs(
    execution_context, minimal_state, artifact_ref_factory
):
    request_ref = artifact_ref_factory(kind="scientist.policy_request_frame")
    candidate_ref = artifact_ref_factory(kind="scientist.legal_candidate_pack")
    source_ref = artifact_ref_factory(kind="scientist.legal_source_pack")
    report_ref = artifact_ref_factory(kind="scientist.source_verification_report")
    updated_candidate_ref = artifact_ref_factory(kind="scientist.legal_candidate_pack")
    updated_source_ref = artifact_ref_factory(kind="scientist.legal_source_pack")
    updated_report_ref = artifact_ref_factory(kind="scientist.source_verification_report")

    state = minimal_state.model_copy(deep=True)
    state.policy_request_ref = request_ref
    state.legal_candidate_pack_ref = candidate_ref
    state.legal_source_pack_ref = source_ref
    state.source_verification_report_ref = report_ref
    state.params["nested"] = {"baseline": True}
    observed: dict[str, tuple[str, ...]] = {}

    updated_report = MagicMock()
    updated_report.unresolved_critical_gaps = []
    updated_report.needs_expert_review = False
    updated_report.verification_cycles_completed = 2

    def _spy_branch(base_state, *, write_paths=()):
        observed["write_paths"] = tuple(write_paths)
        return real_branch_state(base_state, write_paths=write_paths)

    with (
        patch(
            "polisyos.scientist.nodes.builtins.planning.run_source_gap_review.branch_state",
            _spy_branch,
        ),
        patch(
            "polisyos.scientist.nodes.builtins.planning.run_source_gap_review.load_policy_request_frame",
            return_value=MagicMock(),
        ),
        patch(
            "polisyos.scientist.nodes.builtins.planning.run_source_gap_review.load_legal_candidate_pack",
            return_value=MagicMock(),
        ),
        patch(
            "polisyos.scientist.nodes.builtins.planning.run_source_gap_review.load_legal_source_pack",
            return_value=MagicMock(),
        ),
        patch(
            "polisyos.scientist.nodes.builtins.planning.run_source_gap_review.load_source_verification_report",
            return_value=MagicMock(),
        ),
        patch(
            "polisyos.scientist.nodes.builtins.planning.run_source_gap_review.recover_source_gaps",
            return_value=(MagicMock(), MagicMock(), updated_report),
        ),
        patch(
            "polisyos.scientist.nodes.builtins.planning.run_source_gap_review.persist_legal_candidate_pack",
            return_value=updated_candidate_ref,
        ),
        patch(
            "polisyos.scientist.nodes.builtins.planning.run_source_gap_review.persist_legal_source_pack",
            return_value=updated_source_ref,
        ),
        patch(
            "polisyos.scientist.nodes.builtins.planning.run_source_gap_review.persist_source_verification_report",
            return_value=updated_report_ref,
        ),
    ):
        outcome = RunSourceGapReviewNode().execute(execution_context, state)

    assert outcome.status == "ok"
    assert observed["write_paths"] == (
        "legal_candidate_pack_ref",
        "artifacts_index.legal_candidate_pack_ref",
        "legal_source_pack_ref",
        "artifacts_index.legal_source_pack_ref",
        "source_verification_report_ref",
        "artifacts_index.source_verification_report_ref",
        "params.needs_expert_review",
        "params.verification_cycles_completed",
    )
    assert state.params["nested"] == {"baseline": True}
    assert outcome.state.params["verification_cycles_completed"] == 2
