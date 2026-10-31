from __future__ import annotations

from types import SimpleNamespace
from typing import cast

import pytest

from polisyos.core.artifacts import FileSystemCAS, input_ref_from_artifact_ref
from polisyos.scientist.nodes.builtins.planning.draft_policy_options import DraftPolicyOptionsNode
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_POLICY_OPTION_SET_REF,
    ARTIFACT_POLICY_REQUEST_FRAME_REF,
    ARTIFACT_SOURCE_VERIFICATION_REPORT_REF,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.validation.policy_verified.models import (
    PolicyOptionSet,
    PolicyRequestFrame,
    SourceVerificationReport,
    persist_policy_option_set,
    persist_policy_request_frame,
    persist_source_verification_report,
)


def _state_and_context(tmp_path, *, source_request_id: str = "synthetic-request"):
    store = FileSystemCAS(tmp_path / "cas")
    request_ref = persist_policy_request_frame(
        store,
        PolicyRequestFrame(
            request_id="synthetic-request",
            policy_question="Synthetic option draft?",
            jurisdiction="synthetic",
        ),
    )
    source_ref = persist_source_verification_report(
        store,
        SourceVerificationReport(request_id=source_request_id, needs_expert_review=True),
    )
    state = ExperimentState(
        run_id="synthetic-options",
        policy_request_ref=request_ref,
        source_verification_report_ref=source_ref,
        artifacts_index={
            ARTIFACT_POLICY_REQUEST_FRAME_REF: request_ref,
            ARTIFACT_SOURCE_VERIFICATION_REPORT_REF: source_ref,
        },
    )
    return state, cast("ExecutionContext", SimpleNamespace(store=store)), request_ref, source_ref


def test_option_producer_persists_exact_selected_source_profiles(tmp_path) -> None:
    """The actual option producer keeps both selected profiles on its source edges."""
    state, ctx, request_ref, source_ref = _state_and_context(tmp_path)
    outcome = DraftPolicyOptionsNode().execute(ctx, state)

    assert outcome.status == "ok"
    option_ref = outcome.state.policy_option_set_ref
    assert option_ref is not None and option_ref.manifest_profile_sha256 is not None
    assert ctx.store.verify(option_ref).ok
    assert ctx.store.get_manifest(option_ref).inputs == [
        input_ref_from_artifact_ref(request_ref, role="policy_request_frame"),
        input_ref_from_artifact_ref(source_ref, role="source_verification_report"),
    ]


def test_option_producer_refuses_verification_for_a_different_request(tmp_path) -> None:
    """A real owner-readable report for another request is not this request's source."""
    state, ctx, _, _ = _state_and_context(tmp_path, source_request_id="other-synthetic-request")
    outcome = DraftPolicyOptionsNode().execute(ctx, state)

    assert outcome.status == "fail"
    assert outcome.error is not None
    assert outcome.error.code == "policy_request_source_mismatch"
    assert outcome.state.policy_option_set_ref is None


@pytest.mark.parametrize("role", ["request", "source"])
def test_option_producer_refuses_conflicting_current_source_selections(tmp_path, role: str) -> None:
    """Current state and index cannot silently select different sources."""
    state, ctx, *_ = _state_and_context(tmp_path)
    if role == "request":
        key = ARTIFACT_POLICY_REQUEST_FRAME_REF
        other = persist_policy_request_frame(
            ctx.store,
            PolicyRequestFrame(
                request_id="synthetic-request",
                policy_question="A different synthetic question?",
                jurisdiction="synthetic",
            ),
        )
    else:
        key = ARTIFACT_SOURCE_VERIFICATION_REPORT_REF
        other = persist_source_verification_report(
            ctx.store, SourceVerificationReport(request_id="synthetic-request", notes=["different"])
        )
    state.artifacts_index[key] = other
    outcome = DraftPolicyOptionsNode().execute(ctx, state)
    assert outcome.status == "fail"
    assert outcome.error is not None and outcome.error.code == "policy_source_selection_conflict"
    assert outcome.state.policy_option_set_ref is None


def test_option_producer_does_not_reuse_a_foreign_cached_option(tmp_path) -> None:
    """An existing selected option cannot replace current producer input evidence."""
    state, ctx, request_ref, source_ref = _state_and_context(tmp_path)
    old_ref = persist_policy_option_set(ctx.store, PolicyOptionSet(request_id="foreign-request"))
    state.policy_option_set_ref = old_ref
    state.artifacts_index[ARTIFACT_POLICY_OPTION_SET_REF] = old_ref

    outcome = DraftPolicyOptionsNode().execute(ctx, state)
    assert outcome.status == "ok"
    new_ref = outcome.state.policy_option_set_ref
    assert new_ref is not None and new_ref != old_ref
    assert ctx.store.get_manifest(new_ref).inputs == [
        input_ref_from_artifact_ref(request_ref, role="policy_request_frame"),
        input_ref_from_artifact_ref(source_ref, role="source_verification_report"),
    ]
