from __future__ import annotations

import pytest

import polisyos.scientist.policy_design.output as policy_design_output
import polisyos.scientist.replay.deterministic as canonical_replay
import polisyos.scientist.replay.verification as replay_verification
from polisyos.core.artifacts import ArtifactStore, artifact_ref_identity_key
from polisyos.core.artifacts.manifest import ArtifactRef, SchemaInfo, input_ref_from_artifact_ref
from polisyos.core.artifacts.store import PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.scientist.methods.search.judge_stack import (
    JudgeInputBundle,
    JudgeName,
    JudgeStack,
)
from polisyos.scientist.methods.search.promotion_evidence import PromotionEvidenceBundle
from polisyos.scientist.policy_design.output import (
    ReplayableAuditBundle,
    persist_replayable_audit_bundle,
)
from polisyos.scientist.policy_design.schema import (
    persist_policy_candidate_schema,
)
from polisyos.scientist.replay.verification import (
    REPLAY_VERIFICATION_REPORT_SCHEMA_NAME,
    ReplayVerificationReport,
    load_replay_verification_report,
    persist_replay_verification_report,
    verify_and_persist_replay_bundle,
)
from tests.unit.scientist.search.test_phase_b_policy_runtime import _candidate


@pytest.fixture
def store(tmp_path):
    from polisyos.core.artifacts.store import FileSystemCAS

    return FileSystemCAS(tmp_path / "cas")


def _persist_replay_bundle(
    store, *, run_id: str, candidate_ref: ArtifactRef, evaluation_ref: ArtifactRef
):
    return persist_replayable_audit_bundle(
        store,
        ReplayableAuditBundle(
            run_id=run_id,
            candidate_ref=candidate_ref,
            evaluation_ref=evaluation_ref,
        ),
    )


def _foreign_schema_report_ref(store, source_ref: ArtifactRef) -> ArtifactRef:
    return store.put_bytes(
        store.get_bytes(source_ref),
        PutOptions(
            kind="scientist.replay_verification_report",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.UnrelatedPassReport", version="9.9"),
        ),
        return_selected_profile=True,
    )


def _same_id_foreign_profile_ref(
    store, source_ref: ArtifactRef, *, schema_name: str
) -> ArtifactRef:
    """Return another selected manifest view over identical bytes."""
    ref = store.put_bytes(
        store.get_bytes(source_ref),
        PutOptions(
            kind=source_ref.kind,
            media_type=source_ref.media_type,
            schema=SchemaInfo(name=schema_name, version="9.9"),
        ),
        return_selected_profile=True,
    )
    assert ref.artifact_id == source_ref.artifact_id
    assert ref.manifest_profile_sha256 != source_ref.manifest_profile_sha256
    return ref


def test_replay_verification_writer_returns_selected_profile_and_preserves_input_profiles(
    store: ArtifactStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    candidate_ref = store.put_json(
        {"candidate_id": "candidate-owner-profile"},
        PutOptions(
            kind="scientist.policy_candidate_schema",
            media_type="application/json",
            schema=SchemaInfo(name="tests.PolicyCandidate", version="1.0"),
        ),
        return_selected_profile=True,
    )
    evaluation_ref = store.put_json(
        {"score": 1},
        PutOptions(
            kind="scientist.policy_evaluation_vector",
            media_type="application/json",
            schema=SchemaInfo(name="tests.PolicyEvaluationVector", version="1.0"),
        ),
        return_selected_profile=True,
    )
    replay_ref = _persist_replay_bundle(
        store,
        run_id="run-owner-profile",
        candidate_ref=candidate_ref,
        evaluation_ref=evaluation_ref,
    )

    admission_calls: list[
        tuple[ArtifactStore, ArtifactRef, policy_design_output._ReplayableAuditBasisAdmission]
    ] = []
    measurement_calls: list[
        tuple[
            ArtifactStore,
            ArtifactRef,
            ReplayableAuditBundle | None,
            policy_design_output._ReplayableAuditBasisAdmission,
        ]
    ] = []
    measurements: list[canonical_replay.ReplayBundleMeasurement] = []
    original_admit = policy_design_output._admit_replayable_audit_bundle_basis
    canonical_measure = canonical_replay._measure_replayable_audit_bundle_admission

    def _capture_admission(
        store_arg: ArtifactStore, bundle_ref: ArtifactRef
    ) -> policy_design_output._ReplayableAuditBasisAdmission:
        admission = original_admit(store_arg, bundle_ref)
        admission_calls.append((store_arg, bundle_ref, admission))
        return admission

    def _capture_measurement(
        store_arg: ArtifactStore,
        bundle_ref: ArtifactRef,
        bundle: ReplayableAuditBundle | None,
        admission: policy_design_output._ReplayableAuditBasisAdmission,
    ) -> canonical_replay.ReplayBundleMeasurement:
        measurement_calls.append((store_arg, bundle_ref, bundle, admission))
        measurement = canonical_measure(store_arg, bundle_ref, bundle, admission)
        measurements.append(measurement)
        return measurement

    monkeypatch.setattr(
        policy_design_output,
        "_admit_replayable_audit_bundle_basis",
        _capture_admission,
    )
    monkeypatch.setattr(
        replay_verification,
        "_measure_replayable_audit_bundle_admission",
        _capture_measurement,
    )

    verification_ref = verify_and_persist_replay_bundle(
        store,
        run_id="run-owner-profile",
        replay_bundle_ref=replay_ref,
        candidate_ref=candidate_ref,
        evaluation_ref=evaluation_ref,
    )
    assert len(admission_calls) == 1
    assert len(measurement_calls) == 1
    assert len(measurements) == 1
    admitted_store, admitted_ref, admitted_basis = admission_calls[0]
    measured_store, measured_ref, measured_bundle, measured_basis = measurement_calls[0]
    measurement = measurements[0]
    assert admitted_store is store
    assert measured_store is admitted_store
    assert admitted_ref is replay_ref
    assert measured_ref is admitted_ref
    assert admitted_basis.root.ref is admitted_ref
    assert measured_bundle is admitted_basis.bundle
    assert measured_basis is admitted_basis
    assert measurement.replay_bundle_ref is replay_ref
    manifest = store.get_manifest(verification_ref)
    report = load_replay_verification_report(store, verification_ref)

    assert verification_ref.manifest_profile_sha256 is not None
    assert manifest.kind == "scientist.replay_verification_report"
    assert manifest.media_type == "application/json"
    assert manifest.artifact_schema == SchemaInfo(
        name=REPLAY_VERIFICATION_REPORT_SCHEMA_NAME,
        version="1.0",
    )
    assert report.schema_version == "1.0"
    assert report.run_id == "run-owner-profile"
    assert report.verification_mode == measurement.verification_mode == "artifact_snapshot"
    assert report.completeness_level == measurement.completeness.level.value
    assert report.passed is measurement.passed is True
    assert report.overall_similarity == measurement.overall_similarity
    assert report.reason_codes == measurement.reason_codes
    assert replay_ref.manifest_profile_sha256 is not None
    assert artifact_ref_identity_key(report.replay_bundle_ref) == artifact_ref_identity_key(
        replay_ref
    )
    manifest_inputs = {item.role: item for item in manifest.inputs}
    assert manifest_inputs["replay_bundle"] == input_ref_from_artifact_ref(
        replay_ref, role="replay_bundle"
    )
    assert manifest_inputs["candidate"].manifest_profile_sha256 == (
        candidate_ref.manifest_profile_sha256
    )
    assert manifest_inputs["evaluation"].manifest_profile_sha256 == (
        evaluation_ref.manifest_profile_sha256
    )
    legacy_profileless_ref = store.put_json(
        report,
        PutOptions(
            kind="scientist.replay_verification_report",
            media_type="application/json",
            schema=SchemaInfo(name=REPLAY_VERIFICATION_REPORT_SCHEMA_NAME, version="1.0"),
            inputs=list(manifest.inputs),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    assert legacy_profileless_ref.manifest_profile_sha256 is None
    assert load_replay_verification_report(store, legacy_profileless_ref) == report
    with pytest.raises(ValueError, match="selected"):
        load_replay_verification_report(
            store,
            legacy_profileless_ref,
            expected_run_id="run-owner-profile",
            expected_replay_bundle_ref=replay_ref,
            expected_candidate_ref=candidate_ref,
            expected_evaluation_ref=evaluation_ref,
        )


def test_replay_bundle_and_report_project_every_nested_artifact_reference(store) -> None:
    candidate_ref = store.put_json(
        {"candidate_id": "candidate-context-projection"},
        PutOptions(kind="scientist.policy_candidate_schema", media_type="application/json"),
        return_selected_profile=True,
    )
    evaluation_ref = store.put_json(
        {"score": 1},
        PutOptions(kind="scientist.policy_evaluation_vector", media_type="application/json"),
        return_selected_profile=True,
    )
    readiness_ref = store.put_json(
        {"status": "ready"},
        PutOptions(kind="scientist.readiness_report", media_type="application/json"),
        return_selected_profile=True,
    )
    refs = {
        "runtime-input": store.put_json(
            {"input": 1},
            PutOptions(kind="scientist.runtime_input", media_type="application/json"),
            return_selected_profile=True,
        ),
        "runtime-artifact": store.put_json(
            {"artifact": 1},
            PutOptions(kind="scientist.runtime_artifact", media_type="application/json"),
            return_selected_profile=True,
        ),
        "runtime-report": store.put_json(
            {"report": 1},
            PutOptions(kind="scientist.runtime_report", media_type="application/json"),
            return_selected_profile=True,
        ),
        "upstream": store.put_json(
            {"audit": 1},
            PutOptions(kind="scientist.audit", media_type="application/json"),
            return_selected_profile=True,
        ),
        "side-info": store.put_json(
            {"side_info": 1},
            PutOptions(kind="scientist.side_information", media_type="application/json"),
            return_selected_profile=True,
        ),
        "artifact-ref": store.put_json(
            {"extra": 1},
            PutOptions(kind="scientist.extra_artifact", media_type="application/json"),
            return_selected_profile=True,
        ),
    }
    replay_ref = persist_replayable_audit_bundle(
        store,
        ReplayableAuditBundle(
            run_id="run-context-projection",
            candidate_ref=candidate_ref,
            evaluation_ref=evaluation_ref,
            readiness_ref=readiness_ref,
            workflow_id="policy_design",
            execution_profile="selected-local",
            runtime_input_refs={"decision_packet": refs["runtime-input"]},
            runtime_artifacts_index={"output": refs["runtime-artifact"]},
            runtime_reports_index={"summary": refs["runtime-report"]},
            runtime_params_snapshot={"workflow_id": "policy_design"},
            upstream_audit_refs=[refs["upstream"]],
            actionable_side_information_refs=[refs["side-info"]],
            artifact_refs={"extra": refs["artifact-ref"]},
        ),
    )

    verification_ref = verify_and_persist_replay_bundle(
        store,
        run_id="run-context-projection",
        replay_bundle_ref=replay_ref,
    )
    bundle_inputs = store.get_manifest(replay_ref).inputs
    report_inputs = store.get_manifest(verification_ref).inputs

    expected_roles = {
        "candidate",
        "evaluation",
        "readiness",
        "runtime_input:decision_packet",
        "runtime_artifact:output",
        "runtime_report:summary",
        "upstream_audit_ref:0",
        "actionable_side_information_ref:0",
        "artifact_ref:extra",
    }
    assert {item.role for item in bundle_inputs} == expected_roles
    assert {item.role for item in report_inputs} == expected_roles | {"replay_bundle"}
    expected_by_role = {item.role: item for item in bundle_inputs}
    report_by_role = {item.role: item for item in report_inputs}
    assert all(report_by_role[role] == expected for role, expected in expected_by_role.items())
    assert report_by_role["replay_bundle"].manifest_profile_sha256 == (
        replay_ref.manifest_profile_sha256
    )


def test_replay_report_writer_rejects_caller_candidate_or_evaluation_substitution(store) -> None:
    candidate_ref = store.put_json(
        {"candidate_id": "same-bytes"},
        PutOptions(kind="scientist.policy_candidate_schema", media_type="application/json"),
        return_selected_profile=True,
    )
    evaluation_ref = store.put_json(
        {"score": 1},
        PutOptions(kind="scientist.policy_evaluation_vector", media_type="application/json"),
        return_selected_profile=True,
    )
    replay_ref = _persist_replay_bundle(
        store,
        run_id="run-context-substitution",
        candidate_ref=candidate_ref,
        evaluation_ref=evaluation_ref,
    )
    foreign_candidate_ref = _same_id_foreign_profile_ref(
        store,
        candidate_ref,
        schema_name="tests.ForeignCandidateView",
    )
    foreign_evaluation_ref = _same_id_foreign_profile_ref(
        store,
        evaluation_ref,
        schema_name="tests.ForeignEvaluationView",
    )

    with pytest.raises(ValueError, match="candidate.*mismatch"):
        verify_and_persist_replay_bundle(
            store,
            run_id="run-context-substitution",
            replay_bundle_ref=replay_ref,
            candidate_ref=foreign_candidate_ref,
            evaluation_ref=evaluation_ref,
        )
    with pytest.raises(ValueError, match="evaluation.*mismatch"):
        verify_and_persist_replay_bundle(
            store,
            run_id="run-context-substitution",
            replay_bundle_ref=replay_ref,
            candidate_ref=candidate_ref,
            evaluation_ref=foreign_evaluation_ref,
        )


def test_replay_verification_writer_requires_nonblank_exact_source_run(store) -> None:
    candidate_ref = store.put_json(
        {"candidate_id": "candidate-run-context"},
        PutOptions(kind="scientist.policy_candidate_schema", media_type="application/json"),
    )
    evaluation_ref = store.put_json(
        {"score": 1},
        PutOptions(kind="scientist.policy_evaluation_vector", media_type="application/json"),
    )
    replay_ref = _persist_replay_bundle(
        store,
        run_id="source-run",
        candidate_ref=candidate_ref,
        evaluation_ref=evaluation_ref,
    )

    with pytest.raises(ValueError, match="run"):
        persist_replayable_audit_bundle(
            store,
            ReplayableAuditBundle(
                run_id=" \t",
                candidate_ref=candidate_ref,
                evaluation_ref=evaluation_ref,
            ),
        )

    with pytest.raises(ValueError, match="run"):
        verify_and_persist_replay_bundle(
            store,
            run_id="different-run",
            replay_bundle_ref=replay_ref,
        )
    with pytest.raises(ValueError, match="run"):
        verify_and_persist_replay_bundle(
            store,
            run_id="   ",
            replay_bundle_ref=replay_ref,
        )


def test_replay_verification_persister_rejects_self_authored_measurement(store) -> None:
    candidate_ref = store.put_json(
        {"candidate_id": "candidate-counterfeit"},
        PutOptions(kind="scientist.policy_candidate_schema", media_type="application/json"),
        return_selected_profile=True,
    )
    evaluation_ref = store.put_json(
        {"score": 1},
        PutOptions(kind="scientist.policy_evaluation_vector", media_type="application/json"),
        return_selected_profile=True,
    )
    replay_ref = _persist_replay_bundle(
        store,
        run_id="counterfeit-run",
        candidate_ref=candidate_ref,
        evaluation_ref=evaluation_ref,
    )
    genuine_ref = verify_and_persist_replay_bundle(
        store,
        run_id="counterfeit-run",
        replay_bundle_ref=replay_ref,
    )
    genuine = load_replay_verification_report(store, genuine_ref)
    counterfeit = genuine.model_copy(
        update={
            "overall_similarity": 1.0 if genuine.overall_similarity != 1.0 else 0.0,
            "passed": not genuine.passed,
        }
    )

    with pytest.raises(ValueError, match="recomputed"):
        persist_replay_verification_report(
            store,
            counterfeit,
            inputs=list(store.get_manifest(genuine_ref).inputs),
        )
    with pytest.raises(ValueError, match="input"):
        persist_replay_verification_report(
            store,
            genuine,
            inputs=[],
        )


def test_replay_verification_refuses_foreign_schema_at_both_promotion_consumers(store) -> None:
    candidate = _candidate()
    candidate_ref = persist_policy_candidate_schema(store, candidate, return_selected_profile=True)
    evaluation_ref = store.put_json(
        {"candidate_id": str(candidate_ref.artifact_id), "score": 1},
        PutOptions(
            kind="scientist.policy_evaluation_vector",
            media_type="application/json",
            schema=SchemaInfo(name="tests.PolicyEvaluationVector", version="1.0"),
            inputs=[input_ref_from_artifact_ref(candidate_ref, role="candidate")],
        ),
        return_selected_profile=True,
    )
    replay_ref = _persist_replay_bundle(
        store,
        run_id="run-replay-owner",
        candidate_ref=candidate_ref,
        evaluation_ref=evaluation_ref,
    )
    genuine_ref = verify_and_persist_replay_bundle(
        store,
        run_id="run-replay-owner",
        replay_bundle_ref=replay_ref,
        candidate_ref=candidate_ref,
        evaluation_ref=evaluation_ref,
    )
    genuine_report = load_replay_verification_report(store, genuine_ref)

    promotion_evidence = PromotionEvidenceBundle(
        run_id="run-replay-owner",
        produced_by_run_id="run-replay-owner",
        candidate_ref=candidate_ref,
        evaluation_ref=evaluation_ref,
        replay_bundle_ref=replay_ref,
        replay_verification_ref=genuine_ref,
    )
    promotion_evidence.assert_runtime_compatible(run_id="run-replay-owner", store=store)

    genuine_judge_input = JudgeInputBundle(
        candidate=candidate,
        replay_bundle_ref=replay_ref,
        replay_verification_ref=genuine_ref,
        candidate_ref=candidate_ref,
        evaluation_ref=evaluation_ref,
        state={"audit_lineage_complete": True, "checkpoints": ["checkpoint-1"]},
        run_id="run-replay-owner",
    )
    genuine_judge = JudgeStack(store=store).evaluate(
        genuine_judge_input,
        active_judges={JudgeName.REPRODUCIBILITY},
    )
    assert (
        genuine_judge.per_judge[JudgeName.REPRODUCIBILITY.value].metrics["replay_match"]
        == genuine_report.overall_similarity
    )

    counterfeit_ref = _foreign_schema_report_ref(store, genuine_ref)
    assert counterfeit_ref.artifact_id == genuine_ref.artifact_id

    promotion_evidence = PromotionEvidenceBundle(
        run_id="run-replay-owner",
        produced_by_run_id="run-replay-owner",
        candidate_ref=candidate_ref,
        evaluation_ref=evaluation_ref,
        replay_bundle_ref=replay_ref,
        replay_verification_ref=counterfeit_ref,
    )
    with pytest.raises(ValueError):
        promotion_evidence.assert_runtime_compatible(run_id="run-replay-owner", store=store)

    judge_input = JudgeInputBundle(
        candidate=candidate,
        replay_bundle_ref=replay_ref,
        replay_verification_ref=counterfeit_ref,
        candidate_ref=candidate_ref,
        evaluation_ref=evaluation_ref,
        state={
            "audit_lineage_complete": True,
            "checkpoints": ["checkpoint-1"],
        },
        run_id="run-replay-owner",
    )
    with pytest.raises(ValueError):
        JudgeStack(store=store).evaluate(
            judge_input,
            active_judges={JudgeName.REPRODUCIBILITY},
        )


def test_replay_verification_writer_refuses_unsupported_self_declared_schema(store) -> None:
    replay_ref = _persist_replay_bundle(
        store,
        run_id="run-replay-version",
        candidate_ref=store.put_json(
            {"candidate_id": "candidate"},
            PutOptions(kind="scientist.policy_candidate_schema", media_type="application/json"),
        ),
        evaluation_ref=store.put_json(
            {"score": 1},
            PutOptions(kind="scientist.policy_evaluation_vector", media_type="application/json"),
        ),
    )
    unsupported = ReplayVerificationReport(
        schema_version="9.9",
        run_id="run-replay-version",
        replay_bundle_ref=replay_ref,
        verification_mode="artifact_snapshot",
        completeness_level="complete",
        passed=True,
        overall_similarity=1.0,
    )

    with pytest.raises(ValueError, match="schema_version_unsupported"):
        persist_replay_verification_report(store, unsupported)
