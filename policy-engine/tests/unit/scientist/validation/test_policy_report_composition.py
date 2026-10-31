"""Limited report declarations retain exact source edges without granting authority."""

from __future__ import annotations

import logging

import pytest
from pydantic import ValidationError

from polisyos.core.artifacts import (
    ArtifactRef,
    FileSystemCAS,
    PutOptions,
    SchemaInfo,
    input_ref_from_artifact_ref,
)
from polisyos.core.artifacts.manifest import ProducerInfo
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.core.contracts.scientist import VerifiedPolicyReportRef
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.validation.policy_verified.currentness import (
    resolve_current_verified_policy_report,
)
from polisyos.scientist.validation.policy_verified.models import (
    PolicyReportCompositionBinding,
    VerifiedPolicyReport,
    _compose_limited_policy_report,
    load_verified_policy_body,
    load_verified_policy_report,
    persist_verified_policy_body,
    persist_verified_policy_report,
)


def _source(store: FileSystemCAS, kind: str, label: str) -> ArtifactRef:
    """Write a synthetic profiled occurrence; it does not claim an owner attempt."""
    return store.put_json(
        {"label": label},
        PutOptions(
            kind=kind,
            media_type="application/json",
            schema=SchemaInfo(name="test.PolicyCompositionSource", version="1.0"),
        ),
        return_selected_profile=True,
    )


def _binding(store: FileSystemCAS) -> PolicyReportCompositionBinding:
    body = VerifiedPolicyReport(
        request_id="synthetic-request",
        executive_summary="Candidate options remain limited pending verification.",
        needs_expert_review=True,
    )
    return PolicyReportCompositionBinding(
        run_id="synthetic-composition",
        body_ref=persist_verified_policy_body(store, body),
        candidate_ref=_source(store, "scientist.policy_design.candidate", "candidate"),
        phase5_assessment_ref=_source(
            store, "scientist.policy_phase5_candidate_assessment", "phase5"
        ),
        initial_governance_ref=_source(store, "scientist.governance_report", "initial"),
        final_governance_ref=_source(store, "scientist.governance_report", "final"),
        selected_input_ref=_source(store, "scientist.experiment_state", "input"),
        selected_attempt_ref=_source(store, "core.run_invocation_attempt", "attempt"),
    )


def _report(store: FileSystemCAS, binding: PolicyReportCompositionBinding) -> VerifiedPolicyReport:
    return _compose_limited_policy_report(
        load_verified_policy_body(store, binding.body_ref), binding
    )


def test_limited_report_round_trips_exact_edges_but_does_not_establish_completion(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    report = _report(store, _binding(store))
    ref = persist_verified_policy_report(store, report)
    assert ref.manifest_profile_sha256 is not None
    reopened = FileSystemCAS(store.root)
    assert load_verified_policy_report(reopened, ref) == report
    edges = reopened.get_manifest(ref).inputs
    assert [edge.role for edge in edges] == [
        "verified_body",
        "policy_candidate",
        "phase5_candidate_assessment",
        "initial_governance_assessment",
        "final_governance_report",
        "selected_input",
        "selected_attempt",
    ]
    assert all(edge.manifest_profile_sha256 for edge in edges)

    assert report.composition is not None
    assert report.composition.requirement_authority == "not_established"
    assert report.composition.publishable is False
    assert "Applicable requirement authority is not established." in report.missing_evidence
    assert "Independent legal claim verification is not established." in report.missing_evidence
    registry_ref = build_default_registry_bundle(store, return_selected_profile=True).bundle_ref
    run = RunContext.start(
        store=store, registry_bundle=registry_ref, run_id=report.composition.run_id
    )
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger(__name__))
    state = ExperimentState(
        run_id=report.composition.run_id,
        verified_policy_report_ref=ref,
        artifacts_index={"verified_policy_report_ref": ref},
    )
    try:
        admission = resolve_current_verified_policy_report(ctx, state, ref)
        assert not admission.is_current
        assert admission.status == "not_established"
    finally:
        run.suspend_for_resume()


def test_same_report_bytes_with_wrong_edges_do_not_reopen_as_composition(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    report = _report(store, _binding(store))
    selected = persist_verified_policy_report(store, report)
    edges = store.get_manifest(selected).inputs
    foreign = store.put_json(
        report,
        PutOptions(
            kind="scientist.verified_policy_report",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.scientist.VerifiedPolicyReport", version="1.1"),
            inputs=list(reversed(edges)),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    assert foreign.artifact_id == selected.artifact_id
    assert foreign.manifest_profile_sha256 != selected.manifest_profile_sha256
    with pytest.raises(ValueError, match="policy_composition_source_edges_mismatch"):
        load_verified_policy_report(
            store, VerifiedPolicyReportRef.model_validate(foreign.model_dump())
        )


def test_fresh_reader_rejects_changed_report_content_with_original_source_edges(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    report = _report(store, _binding(store))
    selected = persist_verified_policy_report(store, report)
    forged = store.put_json(
        report.model_copy(update={"executive_summary": "Changed conclusion."}),
        PutOptions(
            kind="scientist.verified_policy_report",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.scientist.VerifiedPolicyReport", version="1.1"),
            inputs=store.get_manifest(selected).inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    with pytest.raises(ValueError, match="policy_composition_body_content_mismatch"):
        load_verified_policy_report(
            store, VerifiedPolicyReportRef.model_validate(forged.model_dump())
        )


def test_same_body_bytes_under_foreign_profile_do_not_rebind_report(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    report = _report(store, _binding(store))
    selected = persist_verified_policy_report(store, report)
    assert report.composition is not None
    body_ref = report.composition.body_ref
    body_manifest = store.get_manifest(body_ref)
    foreign_body = store.put_bytes(
        store.get_bytes(body_ref),
        PutOptions(
            kind=body_manifest.kind,
            media_type=body_manifest.media_type,
            schema=body_manifest.artifact_schema,
            canon=body_manifest.canon,
            producer=ProducerInfo(component="test.foreign_body", version="1.0.0"),
        ),
        return_selected_profile=True,
    )
    assert foreign_body.artifact_id == body_ref.artifact_id
    assert foreign_body.manifest_profile_sha256 != body_ref.manifest_profile_sha256
    edges = list(store.get_manifest(selected).inputs)
    edges[0] = input_ref_from_artifact_ref(foreign_body, role="verified_body")
    foreign_report = store.put_json(
        report,
        PutOptions(
            kind="scientist.verified_policy_report",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.scientist.VerifiedPolicyReport", version="1.1"),
            inputs=edges,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    assert foreign_report.artifact_id == selected.artifact_id
    with pytest.raises(ValueError, match="policy_composition_source_edges_mismatch"):
        load_verified_policy_report(
            store, VerifiedPolicyReportRef.model_validate(foreign_report.model_dump())
        )


def test_legacy_report_stays_unbound_and_new_version_requires_binding(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    legacy = VerifiedPolicyReport(request_id="legacy", executive_summary="Historical.")
    assert "composition" not in legacy.model_dump(mode="json")
    legacy_ref = persist_verified_policy_report(store, legacy)
    assert "composition" not in from_canonical_bytes(store.get_bytes(legacy_ref))
    assert load_verified_policy_report(store, legacy_ref) == legacy
    with pytest.raises(ValidationError, match="policy_report_composition_schema_mismatch"):
        VerifiedPolicyReport(schema_version="1.1", request_id="x", executive_summary="x")
    with pytest.raises(ValidationError, match="policy_report_composition_schema_mismatch"):
        VerifiedPolicyReport(request_id="x", executive_summary="x", composition=_binding(store))


@pytest.mark.parametrize(
    "corruption",
    [
        "missing_profile",
        "wrong_kind",
        "same_governance",
        "false_integer",
        "promote",
        "invent_authority",
    ],
)
def test_composition_rejects_invalid_role_or_governance_selection(
    tmp_path, corruption: str
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    binding = _binding(store)
    payload = binding.model_dump(mode="python")
    if corruption == "missing_profile":
        payload["body_ref"]["manifest_profile_sha256"] = None
    elif corruption == "wrong_kind":
        payload["candidate_ref"]["kind"] = "scientist.verified_policy_body"
    elif corruption == "same_governance":
        payload["final_governance_ref"] = payload["initial_governance_ref"]
    elif corruption == "false_integer":
        payload["publishable"] = 0
    elif corruption == "invent_authority":
        payload["requirement_authority"] = "recomputed"
    else:
        payload["result_status"] = "admissible"
    with pytest.raises(ValidationError):
        PolicyReportCompositionBinding.model_validate(payload)


def test_writer_revalidates_forged_limited_report_and_caller_edges(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    report = _report(store, _binding(store))
    forged = report.model_copy(update={"needs_expert_review": False})
    with pytest.raises(
        ValidationError, match="limited_policy_report_legal_authority_not_established"
    ):
        persist_verified_policy_report(store, forged)
    with pytest.raises(ValueError, match="policy_composition_source_edges_mismatch"):
        persist_verified_policy_report(store, report, inputs=[])
    changed_body = report.model_copy(update={"executive_summary": "Changed conclusion."})
    with pytest.raises(ValueError, match="policy_composition_body_content_mismatch"):
        persist_verified_policy_report(store, changed_body)
