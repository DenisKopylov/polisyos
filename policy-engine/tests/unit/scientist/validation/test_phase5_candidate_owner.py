"""Candidate Phase-5 artifacts retain exact source profiles and role bindings."""

from __future__ import annotations

import pytest

from polisyos.core.artifacts import (
    FileSystemCAS,
    PutOptions,
    SchemaInfo,
    input_ref_from_artifact_ref,
)
from polisyos.core.contracts.scientist import GovernanceReportRef
from polisyos.scientist.governance.report import GovernanceReport
from polisyos.scientist.methods.search.judge_stack import (
    JudgeVerdict,
    persist_candidate_judge_verdict,
)
from polisyos.scientist.methods.search.judge_threshold_basis import capture_judge_threshold_basis
from polisyos.scientist.methods.search.judge_thresholds import JudgeThresholdRegistry
from polisyos.scientist.policy_design.schema import persist_policy_candidate_schema
from polisyos.scientist.validation.policy_verified import (
    VerifiedPolicyReport,
    persist_verified_policy_body,
)
from polisyos.scientist.validation.policy_verified.phase5_candidate import (
    Phase5CandidateAssessment,
    Phase5ThresholdUse,
    evaluate_phase5_candidate,
    load_phase5_candidate_assessment,
    persist_phase5_candidate_assessment,
)
from tests.unit.scientist.search.test_phase_b_policy_runtime import _candidate


def _assessment(store, tmp_path):
    refs = {
        role: store.put_json(
            {"role": role},
            PutOptions(kind=f"test.{role}", media_type="application/json"),
            return_selected_profile=True,
        )
        for role in (
            "selected_input",
            "selected_attempt",
        )
    }
    refs["body"] = persist_verified_policy_body(
        store, VerifiedPolicyReport(request_id="synthetic", executive_summary="Candidate body")
    )
    refs["candidate"] = persist_policy_candidate_schema(
        store, _candidate(), return_selected_profile=True
    )
    refs["governance"] = store.put_json(
        GovernanceReport(verdict="human_gate"),
        PutOptions(
            kind="scientist.governance_report",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.scientist.GovernanceReport", version="1.0"),
        ),
        return_selected_profile=True,
    )
    registry = JudgeThresholdRegistry(root=tmp_path / "thresholds")
    registry.record(registry.snapshot().entries[0])
    _frozen, refs["threshold_basis"] = capture_judge_threshold_basis(store, registry)
    refs["judge_verdict"] = persist_candidate_judge_verdict(
        store,
        JudgeVerdict(per_judge={}, composite_decision="defer_to_human"),
        inputs=[
            input_ref_from_artifact_ref(refs[key], role=role)
            for key, role in (
                ("body", "verified_body"),
                ("candidate", "policy_candidate"),
                ("governance", "governance_assessment"),
                ("threshold_basis", "threshold_basis"),
                ("selected_input", "selected_input"),
                ("selected_attempt", "selected_attempt"),
            )
        ],
    )
    return Phase5CandidateAssessment(
        run_id="synthetic-phase5-assessment",
        body_ref=refs["body"],
        candidate_ref=refs["candidate"],
        governance_ref=refs["governance"],
        threshold_basis_ref=refs["threshold_basis"],
        judge_verdict_ref=refs["judge_verdict"],
        selected_input_ref=refs["selected_input"],
        selected_attempt_ref=refs["selected_attempt"],
        limitation_codes=("option_program_correspondence_not_established",),
    )


def test_selected_candidate_assessment_fresh_reader_refuses_changed_source_edges(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    assessment = _assessment(store, tmp_path)
    selected = persist_phase5_candidate_assessment(store, assessment)
    fresh = FileSystemCAS(tmp_path / "cas")
    reopened = load_phase5_candidate_assessment(fresh, selected)
    assert reopened == assessment
    assert reopened.status == "candidate_diagnostic" and reopened.publishable is False
    assert reopened.option_program_correspondence == "not_established"
    manifest = fresh.get_manifest(selected)
    inputs = list(manifest.inputs)
    inputs[0] = input_ref_from_artifact_ref(assessment.candidate_ref, role="verified_body")
    foreign = fresh.put_bytes(
        fresh.get_bytes(selected),
        PutOptions(
            kind=manifest.kind,
            media_type=manifest.media_type,
            schema=manifest.artifact_schema,
            canon=manifest.canon,
            inputs=inputs,
        ),
        return_selected_profile=True,
    )
    assert foreign.artifact_id == selected.artifact_id
    assert foreign.manifest_profile_sha256 != selected.manifest_profile_sha256
    with pytest.raises(ValueError, match="phase5_candidate_source_edges_mismatch"):
        load_phase5_candidate_assessment(fresh, foreign)


def test_profileless_or_forged_publishable_assessment_is_refused(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    assessment = _assessment(store, tmp_path)
    invalid = assessment.model_copy(
        update={
            "body_ref": assessment.body_ref.model_copy(update={"manifest_profile_sha256": None})
        }
    )
    with pytest.raises(ValueError, match="phase5_candidate_source_profile_not_established"):
        persist_phase5_candidate_assessment(store, invalid)
    forged = assessment.model_copy(update={"publishable": True})
    with pytest.raises(ValueError):
        persist_phase5_candidate_assessment(store, forged)


def test_nullable_threshold_use_survives_fresh_assessment_readback(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    assessment = _assessment(store, tmp_path).model_copy(
        update={
            "threshold_uses": (
                Phase5ThresholdUse(
                    judge_name="statistical",
                    metric_name="synthetic_threshold",
                    threshold_tier="blocker",
                    scope=(("family", None),),
                    source="missing",
                    selected_entry=None,
                    fallback_rule=None,
                    fallback_value=None,
                    observed_value=1.0,
                ),
            )
        }
    )
    selected = persist_phase5_candidate_assessment(store, assessment)
    reopened = load_phase5_candidate_assessment(FileSystemCAS(tmp_path / "cas"), selected)
    assert reopened == assessment
    assert reopened.threshold_uses[0].fallback_rule is None
    assert reopened.threshold_uses[0].fallback_value is None


def test_real_judge_threshold_and_profiles_survive_fresh_assessment_readback(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("POLISYOS_SEARCH_REGISTRY_ROOT", str(tmp_path / "live-thresholds"))
    registry = JudgeThresholdRegistry()
    registry.record(registry.snapshot().entries[0])
    store = FileSystemCAS(tmp_path / "cas")
    evaluation = evaluate_phase5_candidate(
        store,
        candidate=_candidate(),
        governance_report=GovernanceReport(verdict="human_gate"),
        run_id="synthetic-threshold-readback",
    )
    assert evaluation.verdict is not None
    assert evaluation.threshold_uses and evaluation.validation_profiles
    assessment = _assessment(store, tmp_path).model_copy(
        update={
            "threshold_uses": evaluation.threshold_uses,
            "validation_profiles": evaluation.validation_profiles,
        }
    )
    selected = persist_phase5_candidate_assessment(store, assessment)
    assert load_phase5_candidate_assessment(FileSystemCAS(tmp_path / "cas"), selected) == assessment


def test_selected_governance_ref_subclass_roundtrips_without_changing_identity(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    assessment = _assessment(store, tmp_path)
    selected_governance = GovernanceReportRef.model_validate(
        assessment.governance_ref.model_dump(mode="json")
    )
    payload = assessment.model_dump(mode="python")
    payload["governance_ref"] = selected_governance
    assessment = Phase5CandidateAssessment.model_validate(payload)
    selected = persist_phase5_candidate_assessment(store, assessment)
    reopened = load_phase5_candidate_assessment(FileSystemCAS(tmp_path / "cas"), selected)
    assert reopened == assessment
    assert reopened.governance_ref.model_dump(mode="json") == selected_governance.model_dump(
        mode="json"
    )


def test_candidate_verdict_with_foreign_schema_is_refused_before_persistence(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    assessment = _assessment(store, tmp_path)
    judge = assessment.judge_verdict_ref
    manifest = store.get_manifest(judge)
    foreign = store.put_bytes(
        store.get_bytes(judge),
        PutOptions(
            kind=manifest.kind,
            media_type=manifest.media_type,
            schema=SchemaInfo(name="test.ForeignJudge", version="1.0"),
            canon=manifest.canon,
        ),
        return_selected_profile=True,
    )
    assert foreign.artifact_id == judge.artifact_id
    assert foreign.manifest_profile_sha256 != judge.manifest_profile_sha256
    before = store.iter_artifact_ids()
    with pytest.raises(ValueError):
        persist_phase5_candidate_assessment(
            store, assessment.model_copy(update={"judge_verdict_ref": foreign})
        )
    assert store.iter_artifact_ids() == before


def test_candidate_verdict_from_another_attempt_is_refused_before_persistence(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    assessment = _assessment(store, tmp_path)
    other_attempt = store.put_json(
        {"role": "selected_attempt", "other": True},
        PutOptions(kind="test.selected_attempt", media_type="application/json"),
        return_selected_profile=True,
    )
    verdict = assessment.judge_verdict_ref
    manifest = store.get_manifest(verdict)
    inputs = list(manifest.inputs)
    inputs[-1] = input_ref_from_artifact_ref(other_attempt, role="selected_attempt")
    foreign = store.put_bytes(
        store.get_bytes(verdict),
        PutOptions(
            kind=manifest.kind,
            media_type=manifest.media_type,
            schema=manifest.artifact_schema,
            canon=manifest.canon,
            inputs=inputs,
        ),
        return_selected_profile=True,
    )
    assert foreign.artifact_id == verdict.artifact_id
    assert foreign.manifest_profile_sha256 != verdict.manifest_profile_sha256
    before = store.iter_artifact_ids()
    with pytest.raises(ValueError, match="phase5_candidate_verdict_source_edges_mismatch"):
        persist_phase5_candidate_assessment(
            store, assessment.model_copy(update={"judge_verdict_ref": foreign})
        )
    assert store.iter_artifact_ids() == before
