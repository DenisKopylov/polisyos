"""Selected-CAS tests for the candidate-only reuse occurrence owner."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from polisyos.core.artifacts import (
    ArtifactRef,
    CanonInfo,
    FileSystemCAS,
    InputRef,
    ProducerInfo,
    PutOptions,
    SchemaInfo,
    load_core_json_artifact,
)
from polisyos.core.canon import CanonSpec
from polisyos.runtime.quality.acquisition_route_loop import (
    AcquisitionCandidateExperimentPhaseReceipt,
)
from polisyos.runtime.quality.agent_action_authority import (
    AGENT_ACTION_AUTHORITY_SCHEMA_VERSION,
    AGENT_ACTION_DECISION_ARTIFACT_KIND,
)
from polisyos.runtime.quality.candidate_experiment_reuse import (
    CandidateExperimentReuseActionSelection,
    _candidate_experiment_reuse_job_id,
)
from polisyos.runtime.quality.candidate_experiment_reuse_occurrence import (
    CANDIDATE_EXPERIMENT_REUSE_OCCURRENCE_KIND,
    CANDIDATE_EXPERIMENT_REUSE_OCCURRENCE_PRODUCER,
    CANDIDATE_EXPERIMENT_REUSE_OCCURRENCE_PRODUCER_VERSION,
    CANDIDATE_EXPERIMENT_REUSE_OCCURRENCE_SCHEMA_NAME,
    CANDIDATE_EXPERIMENT_REUSE_OCCURRENCE_SCHEMA_VERSION,
    OCCURRENCE_WIRE_TO_MANIFEST_SCHEMA,
    persist_candidate_experiment_reuse_occurrence,
    read_candidate_experiment_reuse_occurrence,
)
from polisyos.runtime.quality.generation_cycle import LoopVOIDecision
from tests.unit.runtime.quality.test_candidate_experiment_reuse import (
    _reuse_action_selection,
)

_FIXTURE_CANON = CanonSpec(forbid_floats=False)
_FIXTURE_PRODUCER = "tests.unit.runtime.quality.candidate_experiment_reuse_occurrence"
_FIXTURE_SCHEMA = SchemaInfo(name="test.fixture", version="1.0")
_FIXED_TIME = datetime(2026, 11, 8, tzinfo=UTC)


def _put_fixture_ref(
    store: FileSystemCAS,
    *,
    kind: str,
    marker: str,
    schema: SchemaInfo | None = None,
    producer_version: str = "1.0",
    payload: object | None = None,
) -> ArtifactRef:
    ref = store.put_json(
        payload if payload is not None else {"marker": marker},
        PutOptions(
            kind=kind,
            media_type="application/json",
            schema=schema or _FIXTURE_SCHEMA,
            producer=ProducerInfo(component=_FIXTURE_PRODUCER, version=producer_version),
            canon=CanonInfo.from_spec(_FIXTURE_CANON),
        ),
        canon_spec=_FIXTURE_CANON,
        return_selected_profile=True,
    )
    assert ref.manifest_profile_sha256 is not None
    return ref


def _selection_with_persisted_refs(store: FileSystemCAS) -> CandidateExperimentReuseActionSelection:
    base = _reuse_action_selection()
    kinds = {
        "predecessor_terminal_ref": "runtime_quality.acquisition_route_loop_receipt",
        "predecessor_action_ref": "runtime_quality.acquisition_candidate_action_receipt",
        "source_ref": "runtime.quality.candidate_acquisition_source",
        "n5_input_ref": "runtime.quality.candidate_simulation_n5_input",
        "n5_execution_ref": "runtime.quality.candidate_simulation_execution",
        "n5_result_ref": "polisyos.runtime.joint_simulation_result",
        "policy_ref": "runtime_quality.candidate_unpriced_acquisition_policy",
        "compiled_ref": "runtime.compiled_recursive_generation_cycle",
        "planner_report_ref": "runtime.acquisition_planner_report",
        "compiler_report_ref": "runtime.data_requirement_compilation_report",
        "configured_port_source_ref": "runtime.quality.n7_configured_candidate_port_source",
    }
    refs = {name: _put_fixture_ref(store, kind=kind, marker=name) for name, kind in kinds.items()}
    scope = base.policy_scope.model_copy(
        update={
            name: refs[name]
            for name in (
                "compiled_ref",
                "planner_report_ref",
                "compiler_report_ref",
                "configured_port_source_ref",
            )
        }
    )
    request = base.request.model_copy(
        update={
            name: refs[name]
            for name in (
                "predecessor_terminal_ref",
                "predecessor_action_ref",
                "source_ref",
                "n5_input_ref",
                "n5_execution_ref",
                "n5_result_ref",
                "policy_ref",
            )
        }
    )
    fields: dict[str, object] = {
        name: refs[name]
        for name in kinds
        if name in CandidateExperimentReuseActionSelection.model_fields
    }
    fields.update(policy_scope=scope, request=request)
    fields["action_job_id"] = _candidate_experiment_reuse_job_id(
        tenant_id=base.tenant_id,
        cell_id=base.cell_id,
        run_id=base.run_id,
        source_job_id=base.source_job_id,
        source_payload_ref=base.source_payload_ref,
        request_content_hash=base.request_content_hash,
        route_id=base.route_id,
        predecessor_action_generation=base.predecessor_action_generation,
        action_generation=base.action_generation,
        policy_ref=refs["policy_ref"],
        policy_scope=scope,
        request=request,
        authority_provision_content_sha256=base.authority_provision_content_sha256,
        catalog_source_selection_basis=base.catalog_source_selection_basis,
        catalog_source_content_ref=base.catalog_source_content_ref,
    )
    return CandidateExperimentReuseActionSelection.model_validate(
        {**base.model_dump(mode="python"), **fields}
    )


def _persisted_action_context(
    store: FileSystemCAS,
) -> tuple[CandidateExperimentReuseActionSelection, ArtifactRef, ArtifactRef, ArtifactRef]:
    selection = _selection_with_persisted_refs(store)
    decision_ref = _put_fixture_ref(
        store,
        kind=AGENT_ACTION_DECISION_ARTIFACT_KIND,
        marker="pa2-decision",
        schema=SchemaInfo(
            name="polisyos.runtime.AgentActionAuthorityDecision",
            version=AGENT_ACTION_AUTHORITY_SCHEMA_VERSION,
        ),
    )
    control_payload_ref = _put_fixture_ref(
        store,
        kind="runtime.control_job_payload.acquisition",
        marker="control-payload",
        schema=SchemaInfo(name="polisyos.runtime.ControlJobPayload", version="1.0"),
        payload={"fixture": "immutable-selected-payload"},
    )
    phase = AcquisitionCandidateExperimentPhaseReceipt(
        receipt_id=f"{selection.action_job_id}.executing",
        tenant_id=selection.tenant_id,
        cell_id=selection.cell_id,
        run_id=selection.run_id,
        source_job_id=selection.source_job_id,
        route_id=selection.route_id,
        action_generation=selection.action_generation,
        job_id=selection.action_job_id,
        source_payload_ref=selection.source_payload_ref,
        capability_manifest_ref=selection.policy_scope.planner_report_hash,
        request_content_hash=selection.request_content_hash,
        policy_scope=selection.policy_scope,
        policy_ref=selection.policy_ref,
        authority_decision_ref=decision_ref,
        voi_decision=LoopVOIDecision(
            candidate_id=selection.policy_scope.candidate_id,
            terminal_kind="human_decision_required",
            scheduler_action="reject",
            scheduler_reason="roi_below_threshold",
            priority=0.0,
            next_action="escalate",
            reason="roi_below_threshold",
        ),
        coarse_phase="executing",
        receipt_phase="executing",
        recovery_state="none",
        predecessor_receipt_ref=str(selection.predecessor_terminal_ref.artifact_id),
        generated_at=_FIXED_TIME,
    )
    phase_ref = _put_fixture_ref(
        store,
        kind="runtime_quality.acquisition_candidate_experiment_phase_receipt",
        marker="executing-phase",
        schema=SchemaInfo(
            name="polisyos.runtime.AcquisitionCandidateExperimentPhaseReceipt",
            version="1.0",
        ),
        payload=phase.model_dump(mode="json"),
    )
    return selection, phase_ref, control_payload_ref, decision_ref


def _write_profile_variant(
    store: FileSystemCAS,
    base_ref: ArtifactRef,
    *,
    inputs: list[InputRef] | None = None,
    producer: ProducerInfo | None = None,
) -> ArtifactRef:
    manifest = store.get_manifest(base_ref)
    ref = store.put_bytes(
        store.get_bytes(base_ref),
        PutOptions(
            kind=manifest.kind,
            media_type=manifest.media_type,
            schema=manifest.artifact_schema,
            producer=producer or manifest.producer,
            env=manifest.env,
            inputs=inputs if inputs is not None else manifest.inputs,
            canon=manifest.canon,
            governance=manifest.governance,
            tenant_context=manifest.tenant_context,
            same_input_closure=manifest.same_input_closure,
            authority=manifest.authority,
            warnings=manifest.warnings,
        ),
        return_selected_profile=True,
    )
    assert ref.manifest_profile_sha256 is not None
    return ref


def _occurrence(
    store: FileSystemCAS,
) -> tuple[CandidateExperimentReuseActionSelection, ArtifactRef, ArtifactRef]:
    selection, phase_ref, payload_ref, decision_ref = _persisted_action_context(store)
    occurrence_ref = persist_candidate_experiment_reuse_occurrence(
        store,
        selection=selection,
        executing_phase_ref=phase_ref,
        control_payload_ref=payload_ref,
        pa2_decision_ref=decision_ref,
    )
    assert occurrence_ref.manifest_profile_sha256 is not None
    return selection, occurrence_ref, phase_ref


def test_reuse_occurrence_reads_selected_cas_profile_and_role_closure_from_fresh_store(
    tmp_path: Path,
) -> None:
    root = tmp_path / "cas"
    store = FileSystemCAS(root)
    selection, occurrence_ref, phase_ref = _occurrence(store)

    fresh_store = FileSystemCAS(root)
    occurrence = read_candidate_experiment_reuse_occurrence(
        fresh_store,
        occurrence_ref=occurrence_ref,
        expected_selection=selection,
        expected_executing_phase_ref=phase_ref,
    )
    manifest = fresh_store.get_manifest(occurrence_ref)

    assert occurrence.selection == selection
    assert occurrence.executing_phase_ref == phase_ref
    assert occurrence.schema_version == "CandidateExperimentReuseOccurrence@1.0"
    assert manifest.kind == CANDIDATE_EXPERIMENT_REUSE_OCCURRENCE_KIND
    assert manifest.artifact_schema == SchemaInfo(
        name=CANDIDATE_EXPERIMENT_REUSE_OCCURRENCE_SCHEMA_NAME,
        version=CANDIDATE_EXPERIMENT_REUSE_OCCURRENCE_SCHEMA_VERSION,
    )
    assert manifest.producer == ProducerInfo(
        component=CANDIDATE_EXPERIMENT_REUSE_OCCURRENCE_PRODUCER,
        version=CANDIDATE_EXPERIMENT_REUSE_OCCURRENCE_PRODUCER_VERSION,
    )
    assert {item.role for item in manifest.inputs} == {
        "selected_executing_phase",
        "control_job_payload",
        "pa2_decision",
        "predecessor_terminal",
        "predecessor_action",
        "predecessor_source",
        "predecessor_n5_input",
        "predecessor_n5_execution",
        "predecessor_n5_result",
        "reuse_policy",
        "compiled_source",
        "planner_report",
        "compiler_report",
        "configured_candidate_port_source",
    }
    assert occurrence.source_currentness == "source_currentness_not_established"
    assert occurrence.observed_data_authority is False
    assert occurrence.publication_authority is False
    assert "acquisition_attempt" not in type(occurrence).model_fields
    assert "budget_spend" not in type(occurrence).model_fields
    assert "physical_work" not in type(occurrence).model_fields
    assert OCCURRENCE_WIRE_TO_MANIFEST_SCHEMA[occurrence.schema_version] == (
        CANDIDATE_EXPERIMENT_REUSE_OCCURRENCE_SCHEMA_NAME,
        CANDIDATE_EXPERIMENT_REUSE_OCCURRENCE_SCHEMA_VERSION,
    )


def test_reuse_occurrence_rejects_same_bytes_dependency_under_alternate_profile(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    selection, occurrence_ref, _phase_ref = _occurrence(store)
    source_ref = selection.n5_result_ref
    alternate_source_ref = _write_profile_variant(
        store,
        source_ref,
        producer=ProducerInfo(component=_FIXTURE_PRODUCER, version="alternate-profile"),
    )
    assert alternate_source_ref.artifact_id == source_ref.artifact_id
    assert alternate_source_ref.manifest_profile_sha256 != source_ref.manifest_profile_sha256

    manifest = store.get_manifest(occurrence_ref)
    wrong_inputs = [
        item.model_copy(
            update={"manifest_profile_sha256": alternate_source_ref.manifest_profile_sha256}
        )
        if item.role == "predecessor_n5_result"
        else item
        for item in manifest.inputs
    ]
    alternate_occurrence_ref = _write_profile_variant(
        store,
        occurrence_ref,
        inputs=wrong_inputs,
    )
    assert alternate_occurrence_ref.artifact_id == occurrence_ref.artifact_id
    assert (
        alternate_occurrence_ref.manifest_profile_sha256 != occurrence_ref.manifest_profile_sha256
    )
    assert store.get_bytes(alternate_occurrence_ref) == store.get_bytes(occurrence_ref)

    with pytest.raises(
        ValueError,
        match="candidate_experiment_reuse_occurrence_manifest_closure_mismatch",
    ):
        read_candidate_experiment_reuse_occurrence(
            store,
            occurrence_ref=alternate_occurrence_ref,
            expected_selection=selection,
        )


def test_reuse_occurrence_rejects_missing_role_edge_even_when_payload_bytes_match(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    selection, occurrence_ref, _phase_ref = _occurrence(store)
    manifest = store.get_manifest(occurrence_ref)
    missing_edge_inputs = [
        item for item in manifest.inputs if item.role != "predecessor_n5_execution"
    ]
    alternate_occurrence_ref = _write_profile_variant(
        store,
        occurrence_ref,
        inputs=missing_edge_inputs,
    )
    assert alternate_occurrence_ref.artifact_id == occurrence_ref.artifact_id
    assert store.get_bytes(alternate_occurrence_ref) == store.get_bytes(occurrence_ref)

    with pytest.raises(
        ValueError,
        match="candidate_experiment_reuse_occurrence_manifest_closure_mismatch",
    ):
        read_candidate_experiment_reuse_occurrence(
            store,
            occurrence_ref=alternate_occurrence_ref,
            expected_selection=selection,
        )


def test_reuse_occurrence_requires_selected_executing_phase_to_match_action_identity(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    selection, phase_ref, payload_ref, decision_ref = _persisted_action_context(store)
    phase = AcquisitionCandidateExperimentPhaseReceipt.model_validate(
        load_core_json_artifact(store, phase_ref)
    )
    wrong_phase = phase.model_copy(update={"job_id": "another-action-job"})
    wrong_phase_ref = _put_fixture_ref(
        store,
        kind="runtime_quality.acquisition_candidate_experiment_phase_receipt",
        marker="wrong-phase",
        schema=SchemaInfo(
            name="polisyos.runtime.AcquisitionCandidateExperimentPhaseReceipt",
            version="1.0",
        ),
        payload=wrong_phase.model_dump(mode="json"),
    )

    with pytest.raises(
        ValueError,
        match="candidate_experiment_reuse_occurrence_phase_selection_mismatch",
    ):
        persist_candidate_experiment_reuse_occurrence(
            store,
            selection=selection,
            executing_phase_ref=wrong_phase_ref,
            control_payload_ref=payload_ref,
            pa2_decision_ref=decision_ref,
        )
