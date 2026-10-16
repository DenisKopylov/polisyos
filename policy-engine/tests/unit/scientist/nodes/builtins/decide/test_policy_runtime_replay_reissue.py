from __future__ import annotations

import logging
from types import SimpleNamespace

import pytest

from polisyos.core.artifacts import (
    artifact_ref_identity_key,
    load_core_json_artifact,
)
from polisyos.core.artifacts.manifest import SchemaInfo, input_ref_from_artifact_ref
from polisyos.core.artifacts.store import PutOptions
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.ir.governance.policy_spec import PolicySpec
from polisyos.ir.governance.problem_frame import ProblemDomain, ProblemFrame
from polisyos.ir.model_layer.model_spec import ModelSpec
from polisyos.ir.trinity import TrinityBundle
from polisyos.scientist.methods.search.promotion_evidence import (
    PromotionEvidenceBundle,
    load_promotion_evidence_bundle,
    persist_promotion_evidence_bundle,
)
from polisyos.scientist.nodes.builtins.decide.policy_runtime_support import (
    persist_policy_evaluation_vector_to_store,
)
from polisyos.scientist.nodes.builtins.decide.run_policy_blueprint_runtime import (
    _policy_promotion_runner,
    _reissue_replay_verification_for_subject,
)
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_PROMOTION_EVIDENCE_BUNDLE_REF,
    ARTIFACT_REPLAYABLE_AUDIT_BUNDLE_REF,
)
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.policy_design.objectives import PolicyEvaluationVector
from polisyos.scientist.policy_design.output import (
    ReplayableAuditBundle,
    load_replayable_audit_bundle,
    persist_replayable_audit_bundle,
)
from polisyos.scientist.policy_design.schema import (
    PolicyCandidateSchema,
    persist_policy_candidate_schema,
)
from polisyos.scientist.replay.verification import (
    load_replay_verification_report,
    verify_and_persist_replay_bundle,
)


def test_level4_reissue_keeps_old_report_upstream_and_recomputes_current_subject(
    cas_store,
) -> None:
    """A selection-bound report cannot be relabeled for the current L4 evaluation."""
    run_id = "run-l4-reissue"
    candidate_ref = cas_store.put_json(
        {"candidate_id": "candidate-l4-reissue"},
        PutOptions(
            kind="scientist.policy_design.candidate",
            media_type="application/json",
            schema=SchemaInfo(name="tests.PolicyCandidate", version="1.0"),
        ),
        return_selected_profile=True,
    )
    selection_ref = persist_policy_evaluation_vector_to_store(
        cas_store,
        candidate_ref=candidate_ref,
        evaluation_vector=PolicyEvaluationVector(
            candidate_id="candidate-l4-reissue",
            feasible=True,
            metadata={"evaluation_view": "selection"},
        ),
    )
    runtime_input_ref = cas_store.put_json(
        {"decision_packet": "controlled replay input"},
        PutOptions(kind="scientist.runtime_input", media_type="application/json"),
        return_selected_profile=True,
    )
    source_bundle = ReplayableAuditBundle(
        run_id=run_id,
        candidate_ref=candidate_ref,
        evaluation_ref=selection_ref,
        workflow_id="policy_design",
        execution_profile="full",
        runtime_input_refs={"decision_packet": runtime_input_ref},
        runtime_params_snapshot={"workflow_id": "policy_design"},
    )
    source_bundle_ref = persist_replayable_audit_bundle(cas_store, source_bundle)
    source_report_ref = verify_and_persist_replay_bundle(
        cas_store,
        run_id=run_id,
        replay_bundle_ref=source_bundle_ref,
        candidate_ref=candidate_ref,
        evaluation_ref=selection_ref,
    )

    level4_ref = persist_policy_evaluation_vector_to_store(
        cas_store,
        candidate_ref=candidate_ref,
        evaluation_vector=PolicyEvaluationVector(
            candidate_id="candidate-l4-reissue",
            feasible=True,
            metadata={"evaluation_view": "level4"},
        ),
    )
    with pytest.raises(ValueError, match="replay_verification_evaluation_context_mismatch"):
        load_replay_verification_report(
            cas_store,
            source_report_ref,
            expected_run_id=run_id,
            expected_replay_bundle_ref=source_bundle_ref,
            expected_candidate_ref=candidate_ref,
            expected_evaluation_ref=level4_ref,
        )

    current_bundle_ref, current_report_ref = _reissue_replay_verification_for_subject(
        _execution_context(cas_store),
        run_id=run_id,
        candidate_ref=candidate_ref,
        evaluation_ref=level4_ref,
        replay_bundle_ref=source_bundle_ref,
        replay_verification_ref=source_report_ref,
    )

    assert current_bundle_ref is not None
    assert current_report_ref is not None
    assert artifact_ref_identity_key(current_bundle_ref) != artifact_ref_identity_key(
        source_bundle_ref
    )
    assert current_bundle_ref.manifest_profile_sha256 is not None
    assert current_report_ref.manifest_profile_sha256 is not None
    current_bundle = load_replayable_audit_bundle(cas_store, current_bundle_ref)
    assert current_bundle.candidate_ref is not None
    assert current_bundle.evaluation_ref is not None
    assert artifact_ref_identity_key(current_bundle.candidate_ref) == artifact_ref_identity_key(
        candidate_ref
    )
    assert artifact_ref_identity_key(current_bundle.evaluation_ref) == artifact_ref_identity_key(
        level4_ref
    )
    assert [artifact_ref_identity_key(ref) for ref in current_bundle.upstream_audit_refs] == [
        artifact_ref_identity_key(source_bundle_ref),
        artifact_ref_identity_key(source_report_ref),
    ]
    report = load_replay_verification_report(
        cas_store,
        current_report_ref,
        expected_run_id=run_id,
        expected_replay_bundle_ref=current_bundle_ref,
        expected_candidate_ref=candidate_ref,
        expected_evaluation_ref=level4_ref,
    )
    assert artifact_ref_identity_key(report.replay_bundle_ref) == artifact_ref_identity_key(
        current_bundle_ref
    )
    assert not report.passed
    assert "replay_execution_failed" in report.reason_codes

    source_body = load_core_json_artifact(cas_store, source_bundle_ref)
    assert source_body["evaluation_ref"] == selection_ref.model_dump(mode="json")
    source_report = load_replay_verification_report(cas_store, source_report_ref)
    assert artifact_ref_identity_key(source_report.replay_bundle_ref) == artifact_ref_identity_key(
        source_bundle_ref
    )


@pytest.mark.parametrize(
    "missing_runtime_blob",
    [True, False],
    ids=["missing-selected-blob", "present-selected-blob-control"],
)
def test_level4_promotion_reissue_persists_selected_bundle_and_branches_current_refs(
    cas_store,
    monkeypatch,
    missing_runtime_blob: bool,
) -> None:
    run_id = "run-l4-promotion-state"
    candidate = PolicyCandidateSchema.from_trinity_bundle(
        TrinityBundle(
            problem_frame=ProblemFrame(
                problem_id="problem_l4_promotion_state",
                domain=ProblemDomain.FISCAL,
            ),
            policy_spec=PolicySpec(policy_id="policy_l4_promotion_state"),
            model_spec=ModelSpec(
                model_id="model_l4_promotion_state",
                data_snapshot_ref="sha256:" + "3" * 64,
            ),
        ),
        candidate_id="candidate-l4-promotion-state",
    )
    candidate_ref = persist_policy_candidate_schema(
        cas_store,
        candidate,
        return_selected_profile=True,
    )
    runtime_material_ref = cas_store.put_json(
        {"run_id": run_id, "material": "present until the current reissue"},
        PutOptions(kind="scientist.runtime_input", media_type="application/json"),
        return_selected_profile=True,
    )
    assert runtime_material_ref.manifest_profile_sha256 is not None
    assert cas_store.verify(runtime_material_ref).ok is True
    selection_ref = persist_policy_evaluation_vector_to_store(
        cas_store,
        candidate_ref=candidate_ref,
        evaluation_vector=PolicyEvaluationVector(
            candidate_id="candidate-l4-promotion-state",
            feasible=True,
            metadata={"evaluation_view": "selection"},
        ),
    )
    source_bundle = ReplayableAuditBundle(
        run_id=run_id,
        candidate_ref=candidate_ref,
        evaluation_ref=selection_ref,
        workflow_id="policy_design",
        execution_profile="full",
        runtime_input_refs={"required_runtime_material": runtime_material_ref},
        runtime_params_snapshot={"workflow_id": "policy_design"},
    )
    source_bundle_ref = persist_replayable_audit_bundle(cas_store, source_bundle)
    source_bundle_inputs = {
        item.role: item for item in cas_store.get_manifest(source_bundle_ref).inputs
    }
    assert source_bundle_inputs["runtime_input:required_runtime_material"] == (
        input_ref_from_artifact_ref(
            runtime_material_ref,
            role="runtime_input:required_runtime_material",
        )
    )
    source_report_ref = verify_and_persist_replay_bundle(
        cas_store,
        run_id=run_id,
        replay_bundle_ref=source_bundle_ref,
        candidate_ref=candidate_ref,
        evaluation_ref=selection_ref,
    )
    source_report = load_replay_verification_report(cas_store, source_report_ref)
    assert source_report.passed is False
    assert source_report.reason_codes == ["replay_execution_failed"]
    source_promotion_evidence = PromotionEvidenceBundle(
        run_id=run_id,
        produced_by_run_id=run_id,
        candidate_ref=candidate_ref,
        evaluation_ref=selection_ref,
        replay_bundle_ref=source_bundle_ref,
        replay_verification_ref=source_report_ref,
    )
    source_promotion_evidence_ref = persist_promotion_evidence_bundle(
        cas_store,
        source_promotion_evidence,
    )
    state = ExperimentState(
        run_id=run_id,
        params={
            "promotion_evidence_bundle_ref": source_promotion_evidence_ref.model_dump(mode="json"),
            "replay_bundle_ref": source_bundle_ref.model_dump(mode="json"),
            "replay_verification_ref": source_report_ref.model_dump(mode="json"),
            "policy_evaluation_ref": selection_ref.model_dump(mode="json"),
        },
        artifacts_index={
            ARTIFACT_PROMOTION_EVIDENCE_BUNDLE_REF: source_promotion_evidence_ref,
            ARTIFACT_REPLAYABLE_AUDIT_BUNDLE_REF: source_bundle_ref,
        },
    )
    context = {
        "promotion_evidence_bundle_ref": source_promotion_evidence_ref,
        "policy_candidate_ref": candidate_ref,
        "promotion_write_allowed": True,
        "funnel_degradation_mode": "normal",
        "_funnel_L4_result": SimpleNamespace(
            feedback={
                "policy_runtime_fidelity": "full",
                "policy_evaluation": {
                    "candidate_id": "candidate-l4-promotion-state",
                    "feasible": True,
                    "metadata": {"evaluation_view": "level4"},
                },
                "policy_runtime_promotable_source": True,
            }
        ),
    }
    observed: dict[str, object] = {}

    captured_promotion_calls: list[dict[str, object]] = []

    def capture_promotion_inputs(**kwargs):
        observed.update(kwargs)
        captured_promotion_calls.append(kwargs)
        return {"decision": "reject", "reason": "controlled consumer boundary"}

    monkeypatch.setattr(
        "polisyos.scientist.nodes.builtins.decide.run_policy_blueprint_runtime.run_promotion_with_evidence",
        capture_promotion_inputs,
    )
    blob_path, _manifest_path = cas_store._paths(runtime_material_ref.artifact_id)
    held_blob_path = blob_path.with_name(f"{blob_path.name}.held-{run_id}")
    assert not held_blob_path.exists()
    if missing_runtime_blob:
        # Rename the real CAS blob so verification sees the selected edge but cannot resolve bytes.
        blob_path.replace(held_blob_path)
    current_report = None
    try:
        result = _policy_promotion_runner(
            _execution_context(cas_store, run_id),
            state,
            candidate,
            candidate_ref,
            context,
        )
        assert cas_store.verify(runtime_material_ref).ok is (not missing_runtime_blob)
        current_bundle_during_mutation = observed["evidence_bundle"]
        assert isinstance(current_bundle_during_mutation, PromotionEvidenceBundle)
        level4_ref_during_mutation = current_bundle_during_mutation.evaluation_ref
        current_bundle_ref_during_mutation = current_bundle_during_mutation.replay_bundle_ref
        current_report_ref_during_mutation = current_bundle_during_mutation.replay_verification_ref
        assert level4_ref_during_mutation is not None
        assert current_bundle_ref_during_mutation is not None
        assert current_report_ref_during_mutation is not None
        # Read the report before restoration, while its missing-blob outcome is current.
        current_report = load_replay_verification_report(
            cas_store,
            current_report_ref_during_mutation,
            expected_run_id=run_id,
            expected_replay_bundle_ref=current_bundle_ref_during_mutation,
            expected_candidate_ref=candidate_ref,
            expected_evaluation_ref=level4_ref_during_mutation,
        )
    finally:
        if missing_runtime_blob and held_blob_path.exists():
            held_blob_path.replace(blob_path)
    assert cas_store.verify(runtime_material_ref).ok is True

    assert result == {"decision": "reject", "reason": "controlled consumer boundary"}
    current_bundle = observed["evidence_bundle"]
    current_ref = context["promotion_evidence_bundle_ref"]
    promotion_state = observed["state"]
    promotion_context = observed["promotion_context"]
    assert isinstance(current_bundle, PromotionEvidenceBundle)
    assert isinstance(current_ref, type(source_promotion_evidence_ref))
    assert isinstance(promotion_state, ExperimentState)
    assert isinstance(promotion_context, dict)
    assert current_ref.manifest_profile_sha256 is not None
    assert current_bundle.evaluation_ref is not None
    level4_ref = current_bundle.evaluation_ref
    current_bundle_ref = current_bundle.replay_bundle_ref
    current_report_ref = current_bundle.replay_verification_ref
    assert current_bundle_ref is not None
    assert current_report_ref is not None
    assert current_bundle_ref.manifest_profile_sha256 is not None
    assert current_report_ref.manifest_profile_sha256 is not None

    assert current_ref.manifest_profile_sha256 is not None
    assert current_bundle.evaluation_ref == level4_ref
    assert current_bundle.replay_bundle_ref == current_bundle_ref
    assert current_bundle.replay_verification_ref == current_report_ref
    assert load_promotion_evidence_bundle(cas_store, current_ref) == current_bundle
    current_inputs = {item.role: item for item in cas_store.get_manifest(current_ref).inputs}
    assert current_inputs["candidate"] == input_ref_from_artifact_ref(
        candidate_ref, role="candidate"
    )
    assert current_inputs["evaluation"] == input_ref_from_artifact_ref(
        level4_ref, role="evaluation"
    )
    assert current_inputs["replay_bundle"] == input_ref_from_artifact_ref(
        current_bundle_ref, role="replay_bundle"
    )
    assert current_inputs["replay_verification"] == input_ref_from_artifact_ref(
        current_report_ref, role="replay_verification"
    )
    assert current_inputs["source_promotion_evidence_bundle"] == input_ref_from_artifact_ref(
        source_promotion_evidence_ref,
        role="source_promotion_evidence_bundle",
    )
    assert promotion_state.artifacts_index[ARTIFACT_PROMOTION_EVIDENCE_BUNDLE_REF] == current_ref
    assert artifact_ref_identity_key(
        promotion_state.artifacts_index[ARTIFACT_REPLAYABLE_AUDIT_BUNDLE_REF]
    ) == artifact_ref_identity_key(current_bundle_ref)
    assert promotion_state.params["policy_evaluation_ref"] == level4_ref.model_dump(mode="json")
    assert promotion_state.params["promotion_evidence_bundle_ref"] == current_ref.model_dump(
        mode="json"
    )
    assert promotion_state.params["replay_bundle_ref"] == current_bundle_ref.model_dump(mode="json")
    assert promotion_state.params["replay_verification_ref"] == current_report_ref.model_dump(
        mode="json"
    )
    assert promotion_context["promotion_evidence_bundle_ref"] == current_ref
    assert state.artifacts_index[ARTIFACT_REPLAYABLE_AUDIT_BUNDLE_REF] == source_bundle_ref
    assert state.artifacts_index[ARTIFACT_PROMOTION_EVIDENCE_BUNDLE_REF] == (
        source_promotion_evidence_ref
    )
    assert state.params[
        "promotion_evidence_bundle_ref"
    ] == source_promotion_evidence_ref.model_dump(mode="json")
    assert state.params["replay_bundle_ref"] == source_bundle_ref.model_dump(mode="json")
    assert state.params["replay_verification_ref"] == source_report_ref.model_dump(mode="json")
    assert current_report is not None
    assert current_report.passed is False
    if missing_runtime_blob:
        assert current_report.reason_codes == ["bundle_dependency_integrity_failed"]

        profileless_runtime_ref = runtime_material_ref.model_copy(
            update={"manifest_profile_sha256": None}
        )
        profileless_run_id = f"{run_id}-profileless-control"
        profileless_bundle = source_bundle.model_copy(
            update={
                "run_id": profileless_run_id,
                "runtime_input_refs": {"required_runtime_material": profileless_runtime_ref},
            }
        )
        profileless_bundle_ref = persist_replayable_audit_bundle(cas_store, profileless_bundle)
        profileless_bundle_inputs = {
            item.role: item for item in cas_store.get_manifest(profileless_bundle_ref).inputs
        }
        assert (
            profileless_bundle_inputs[
                "runtime_input:required_runtime_material"
            ].manifest_profile_sha256
            is None
        )
        profileless_evidence = PromotionEvidenceBundle(
            run_id=profileless_run_id,
            produced_by_run_id=profileless_run_id,
            candidate_ref=candidate_ref,
            evaluation_ref=selection_ref,
            replay_bundle_ref=profileless_bundle_ref,
        )
        profileless_evidence_ref = persist_promotion_evidence_bundle(
            cas_store, profileless_evidence
        )
        profileless_state = ExperimentState(
            run_id=profileless_run_id,
            params={
                "promotion_evidence_bundle_ref": profileless_evidence_ref.model_dump(mode="json"),
                "replay_bundle_ref": profileless_bundle_ref.model_dump(mode="json"),
                "policy_evaluation_ref": selection_ref.model_dump(mode="json"),
            },
            artifacts_index={
                ARTIFACT_PROMOTION_EVIDENCE_BUNDLE_REF: profileless_evidence_ref,
                ARTIFACT_REPLAYABLE_AUDIT_BUNDLE_REF: profileless_bundle_ref,
            },
        )
        profileless_context = {
            "promotion_evidence_bundle_ref": profileless_evidence_ref,
            "policy_candidate_ref": candidate_ref,
            "promotion_write_allowed": True,
            "funnel_degradation_mode": "normal",
            "_funnel_L4_result": context["_funnel_L4_result"],
        }
        monkeypatch.setattr(
            "polisyos.scientist.nodes.builtins.decide.run_policy_blueprint_runtime.run_promotion_with_evidence",
            lambda **_kwargs: pytest.fail("profileless replay material reached promotion"),
        )
        profileless_result = _policy_promotion_runner(
            _execution_context(cas_store, profileless_run_id),
            profileless_state,
            candidate,
            candidate_ref,
            profileless_context,
        )
        assert profileless_result == {
            "decision": "reject",
            "reason": "replay_bundle_runtime_input:required_runtime_material_selected_profile_required",
        }
        assert len(captured_promotion_calls) == 1
        assert profileless_state.artifacts_index[ARTIFACT_REPLAYABLE_AUDIT_BUNDLE_REF] == (
            profileless_bundle_ref
        )
        assert profileless_state.artifacts_index[ARTIFACT_PROMOTION_EVIDENCE_BUNDLE_REF] == (
            profileless_evidence_ref
        )
        assert profileless_context["promotion_evidence_bundle_ref"] == profileless_evidence_ref
    else:
        assert current_report.reason_codes == ["replay_execution_failed"]


def _execution_context(store, run_id: str = "run-l4-reissue"):
    from polisyos.scientist.orchestration.engine.context import ExecutionContext

    registry_ref = build_default_registry_bundle(store).bundle_ref
    return ExecutionContext(
        store=store,
        run=RunContext.start(
            store=store,
            registry_bundle=registry_ref,
            run_id=run_id,
        ),
        logger=logging.getLogger("test.replay-reissue"),
    )
