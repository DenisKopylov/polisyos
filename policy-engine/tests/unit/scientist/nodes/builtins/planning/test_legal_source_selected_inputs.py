from __future__ import annotations

from types import SimpleNamespace
from typing import cast

import pytest

from polisyos.core.artifacts import FileSystemCAS, input_ref_from_artifact_ref
from polisyos.scientist.nodes.builtins.planning.assemble_legal_candidate_pack import (
    AssembleLegalCandidatePackNode,
)
from polisyos.scientist.nodes.builtins.planning.expand_legal_source_pack import (
    ExpandLegalSourcePackNode,
)
from polisyos.scientist.nodes.builtins.planning.run_source_gap_review import RunSourceGapReviewNode
from polisyos.scientist.nodes.builtins.planning.run_source_verification import (
    RunSourceVerificationNode,
)
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_LEGAL_CANDIDATE_PACK_REF,
    ARTIFACT_LEGAL_SOURCE_PACK_REF,
    ARTIFACT_POLICY_REQUEST_FRAME_REF,
    ARTIFACT_SOURCE_VERIFICATION_REPORT_REF,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.validation.policy_verified.models import (
    LegalCandidatePack,
    LegalSourcePack,
    PolicyRequestFrame,
    SourceVerificationReport,
    load_legal_candidate_pack,
    load_legal_source_pack,
    persist_legal_candidate_pack,
    persist_legal_source_pack,
    persist_policy_request_frame,
    persist_source_verification_report,
)


@pytest.fixture(autouse=True)
def _offline_verifier(monkeypatch: pytest.MonkeyPatch) -> None:
    import polisyos.scientist.validation.policy_verified.service as service

    monkeypatch.setattr(service, "create_traced_gateway_client", lambda **_kwargs: None)


def _case(tmp_path, *, candidate_request: str = "synthetic", source_request: str = "synthetic"):
    store = FileSystemCAS(tmp_path / "cas")
    request_ref = persist_policy_request_frame(
        store,
        PolicyRequestFrame(
            schema_version="1.1",
            request_id="synthetic",
            policy_question="Synthetic?",
            jurisdiction="synthetic",
            jurisdiction_source="policy_request_jurisdiction",
        ),
    )
    candidate_ref = persist_legal_candidate_pack(
        store, LegalCandidatePack(request_id=candidate_request)
    )
    source_ref = persist_legal_source_pack(store, LegalSourcePack(request_id=source_request))
    state = ExperimentState(
        run_id="synthetic-source-chain",
        policy_request_ref=request_ref,
        legal_candidate_pack_ref=candidate_ref,
        legal_source_pack_ref=source_ref,
        artifacts_index={
            ARTIFACT_POLICY_REQUEST_FRAME_REF: request_ref,
            ARTIFACT_LEGAL_CANDIDATE_PACK_REF: candidate_ref,
            ARTIFACT_LEGAL_SOURCE_PACK_REF: source_ref,
        },
    )
    return (
        state,
        cast("ExecutionContext", SimpleNamespace(store=store)),
        request_ref,
        candidate_ref,
        source_ref,
    )


def test_actual_source_verification_and_gap_review_keep_selected_edges(
    tmp_path, monkeypatch
) -> None:
    """Real local producers preserve source profiles, with no external verifier call."""
    import polisyos.scientist.validation.policy_verified.service as service

    monkeypatch.setattr(service, "create_traced_gateway_client", lambda **_kwargs: None)
    state, ctx, request_ref, candidate_ref, source_ref = _case(tmp_path)
    assert source_ref.manifest_profile_sha256 is not None
    verified = RunSourceVerificationNode().execute(ctx, state)
    assert verified.status == "ok"
    report_ref = verified.state.source_verification_report_ref
    assert report_ref is not None and report_ref.manifest_profile_sha256 is not None
    assert ctx.store.get_manifest(report_ref).inputs == [
        input_ref_from_artifact_ref(request_ref, role="policy_request_frame"),
        input_ref_from_artifact_ref(candidate_ref, role="legal_candidate_pack"),
        input_ref_from_artifact_ref(source_ref, role="legal_source_pack"),
    ]

    reviewed = RunSourceGapReviewNode().execute(ctx, verified.state)
    assert reviewed.status == "ok"
    updated_candidate = reviewed.state.legal_candidate_pack_ref
    updated_source = reviewed.state.legal_source_pack_ref
    updated_report = reviewed.state.source_verification_report_ref
    assert (
        updated_candidate is not None and updated_source is not None and updated_report is not None
    )
    prior_inputs = [
        input_ref_from_artifact_ref(request_ref, role="policy_request_frame"),
        input_ref_from_artifact_ref(candidate_ref, role="prior_legal_candidate_pack"),
        input_ref_from_artifact_ref(source_ref, role="prior_legal_source_pack"),
        input_ref_from_artifact_ref(report_ref, role="prior_source_verification_report"),
    ]
    assert ctx.store.get_manifest(updated_candidate).inputs == prior_inputs
    assert ctx.store.get_manifest(updated_source).inputs == [
        *prior_inputs,
        input_ref_from_artifact_ref(updated_candidate, role="legal_candidate_pack"),
    ]
    assert ctx.store.get_manifest(updated_report).inputs == [
        *prior_inputs,
        input_ref_from_artifact_ref(updated_candidate, role="legal_candidate_pack"),
        input_ref_from_artifact_ref(updated_source, role="legal_source_pack"),
    ]


@pytest.mark.parametrize("foreign", ["candidate", "source"])
def test_source_verification_refuses_foreign_request(tmp_path, foreign: str) -> None:
    """A resolved legal pack for another request cannot establish this source report."""
    state, ctx, *_ = _case(
        tmp_path,
        candidate_request="foreign" if foreign == "candidate" else "synthetic",
        source_request="foreign" if foreign == "source" else "synthetic",
    )
    outcome = RunSourceVerificationNode().execute(ctx, state)
    assert outcome.status == "fail"
    assert outcome.error is not None and outcome.error.code == "policy_request_source_mismatch"
    assert outcome.state.source_verification_report_ref is None


@pytest.mark.parametrize("foreign", ["candidate", "source", "report"])
def test_gap_review_refuses_a_foreign_request(tmp_path, foreign: str) -> None:
    state, ctx, *_ = _case(
        tmp_path,
        candidate_request="foreign" if foreign == "candidate" else "synthetic",
        source_request="foreign" if foreign == "source" else "synthetic",
    )
    report = persist_source_verification_report(
        ctx.store,
        SourceVerificationReport(request_id="foreign" if foreign == "report" else "synthetic"),
    )
    state.source_verification_report_ref = report
    state.artifacts_index[ARTIFACT_SOURCE_VERIFICATION_REPORT_REF] = report
    outcome = RunSourceGapReviewNode().execute(ctx, state)
    assert outcome.status == "fail"
    assert outcome.error is not None and outcome.error.code == "policy_request_source_mismatch"


@pytest.mark.parametrize("role", ["request", "candidate", "source"])
def test_source_verification_refuses_conflicting_source_selection(tmp_path, role: str) -> None:
    state, ctx, *_ = _case(tmp_path)
    if role == "request":
        key = ARTIFACT_POLICY_REQUEST_FRAME_REF
        alternate = persist_policy_request_frame(
            ctx.store,
            PolicyRequestFrame(
                request_id="synthetic", policy_question="Different?", jurisdiction="synthetic"
            ),
        )
    elif role == "candidate":
        key = ARTIFACT_LEGAL_CANDIDATE_PACK_REF
        alternate = persist_legal_candidate_pack(
            ctx.store, LegalCandidatePack(request_id="synthetic", queries=["different"])
        )
    else:
        key = ARTIFACT_LEGAL_SOURCE_PACK_REF
        alternate = persist_legal_source_pack(
            ctx.store, LegalSourcePack(request_id="synthetic", notes=["different"])
        )
    state.artifacts_index[key] = alternate
    outcome = RunSourceVerificationNode().execute(ctx, state)
    assert outcome.status == "fail"
    assert outcome.error is not None and outcome.error.code == "policy_source_selection_conflict"


def test_actual_legal_assembly_and_expansion_keep_selected_source_edges(tmp_path) -> None:
    """Real local candidate/expansion producers bind the selected preceding profiles."""
    _, ctx, request_ref, *_ = _case(tmp_path)
    state = ExperimentState(
        run_id="synthetic-legal-chain",
        policy_request_ref=request_ref,
        artifacts_index={ARTIFACT_POLICY_REQUEST_FRAME_REF: request_ref},
    )
    assembled = AssembleLegalCandidatePackNode().execute(ctx, state)
    assert assembled.status == "ok"
    candidate_ref = assembled.state.legal_candidate_pack_ref
    assert candidate_ref is not None and candidate_ref.manifest_profile_sha256 is not None
    assert ctx.store.get_manifest(candidate_ref).inputs == [
        input_ref_from_artifact_ref(request_ref, role="policy_request_frame")
    ]
    expanded = ExpandLegalSourcePackNode().execute(ctx, assembled.state)
    assert expanded.status == "ok"
    source_ref = expanded.state.legal_source_pack_ref
    assert source_ref is not None and source_ref.manifest_profile_sha256 is not None
    assert ctx.store.get_manifest(source_ref).inputs == [
        input_ref_from_artifact_ref(candidate_ref, role="legal_candidate_pack")
    ]


def test_cached_assembly_cannot_hide_conflicting_request_selection(tmp_path) -> None:
    state, ctx, request, candidate, _ = _case(tmp_path)
    alternate = persist_policy_request_frame(
        ctx.store,
        PolicyRequestFrame(
            request_id="synthetic", policy_question="Different?", jurisdiction="synthetic"
        ),
    )
    state.artifacts_index[ARTIFACT_POLICY_REQUEST_FRAME_REF] = alternate
    assert state.policy_request_ref == request
    assert state.legal_candidate_pack_ref == candidate
    outcome = AssembleLegalCandidatePackNode().execute(ctx, state)
    assert outcome.status == "fail"
    assert outcome.error is not None and outcome.error.code == "policy_source_selection_conflict"


def test_cached_expansion_cannot_hide_conflicting_candidate_selection(tmp_path) -> None:
    state, ctx, _request, candidate, _ = _case(tmp_path)
    alternate = persist_legal_candidate_pack(
        ctx.store, LegalCandidatePack(request_id="synthetic", queries=["different"])
    )
    state.artifacts_index[ARTIFACT_LEGAL_CANDIDATE_PACK_REF] = alternate
    assert state.legal_candidate_pack_ref == candidate
    outcome = ExpandLegalSourcePackNode().execute(ctx, state)
    assert outcome.status == "fail"
    assert outcome.error is not None and outcome.error.code == "policy_source_selection_conflict"


def test_cached_legal_candidate_is_reissued_from_current_request(tmp_path) -> None:
    state, ctx, _request, previous, _ = _case(tmp_path, candidate_request="foreign")
    outcome = AssembleLegalCandidatePackNode().execute(ctx, state)
    assert outcome.status == "ok"
    selected = outcome.state.legal_candidate_pack_ref
    assert selected is not None and selected != previous
    assert load_legal_candidate_pack(ctx.store, selected).request_id == "synthetic"


def test_cached_legal_source_is_reissued_from_current_candidate(tmp_path) -> None:
    state, ctx, _request, _candidate, previous = _case(tmp_path, source_request="foreign")
    outcome = ExpandLegalSourcePackNode().execute(ctx, state)
    assert outcome.status == "ok"
    selected = outcome.state.legal_source_pack_ref
    assert selected is not None and selected != previous
    assert load_legal_source_pack(ctx.store, selected).request_id == "synthetic"
