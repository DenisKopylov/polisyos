"""Core DTO and CAS tests for candidate-only ProgramGraph actuation selections.

These tests establish typed persistence and schema compatibility only. The
lowered-IR group resolver and public execute path are tested by their owners.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from polisyos.core.artifacts.canonical_profile import (
    CoreJsonReadLimits,
    read_core_json_artifact_bounded,
    validate_core_model_bounded_read,
)
from polisyos.core.artifacts.manifest import ArtifactRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.core.contracts.foundry import (
    ExecPlanRef,
    ExecuteRequest,
    FoundryExecutionInputBasis,
    FoundryInputBindingsRef,
    ProgramGraphActuationSelection,
    ProgramGraphActuationSelectionRef,
)

_PROFILE = "sha256:" + "f" * 64
_READ_LIMITS = CoreJsonReadLimits(
    max_bytes=256 * 1024,
    max_depth=40,
    max_elements=16384,
    max_manifest_bytes=64 * 1024,
)


def _artifact_ref(kind: str, fill: str) -> dict[str, str]:
    return {
        "artifact_id": "sha256:" + fill * 64,
        "kind": kind,
        "media_type": "application/json",
        "manifest_profile_sha256": _PROFILE,
    }


def _selection_payload(*, selected_ids: tuple[str, ...]) -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "authority_purpose": "candidate_simulation_actuation_only",
        "program_graph_ref": _artifact_ref("foundry.program_graph", "1"),
        "exec_plan_ref": _artifact_ref("foundry.exec_plan", "2"),
        "lowered_ir_ref": _artifact_ref("foundry.lowered_ir", "3"),
        "selected_intervention_ids": selected_ids,
    }


def _registry_members(fill: str) -> dict[str, object]:
    return {
        key: _artifact_ref(f"foundry.{key}", fill)
        for key in ("slot_registry", "merge_registry", "constraint_registry", "mechanism_registry")
    }


def _basis_payload(
    *,
    schema_version: str,
    actuation_ref: ProgramGraphActuationSelectionRef | None = None,
    request_schema_version: str = "1.0",
    request_actuation_ref: ProgramGraphActuationSelectionRef | None = None,
) -> dict[str, object]:
    request: dict[str, object] = {
        "schema_version": request_schema_version,
        "exec_plan_ref": _artifact_ref("foundry.exec_plan", "4"),
        "input_bindings_ref": _artifact_ref("foundry.input_bindings", "5"),
    }
    if request_actuation_ref is not None:
        request["actuation_selection_ref"] = request_actuation_ref
    return {
        "schema_version": schema_version,
        "execution_mode": "single_step",
        "request": request,
        "exec_plan_ref": _artifact_ref("foundry.exec_plan", "4"),
        "program_graph_ref": _artifact_ref("foundry.program_graph", "6"),
        "trinity_bundle_ref": _artifact_ref("foundry.trinity_bundle", "7"),
        "candidate_ref": _artifact_ref("foundry.candidate", "8"),
        "candidate_data_snapshot_ref": _artifact_ref("foundry.data_snapshot", "9"),
        "candidate_registry_bundle_ref": _artifact_ref("foundry.registry_bundle", "a"),
        "input_bindings_ref": _artifact_ref("foundry.input_bindings", "5"),
        "data_snapshot_ref": _artifact_ref("foundry.data_snapshot", "b"),
        "bound_state_snapshot_ref": _artifact_ref("foundry.state_snapshot", "c"),
        "binding_registry_ref": _artifact_ref("foundry.binding_registry", "d"),
        "compile_registry_ref": _artifact_ref("foundry.compile_registry", "e"),
        "runtime_registry_ref": _artifact_ref("foundry.runtime_registry", "f"),
        "binding_registry_members": _registry_members("1"),
        "compile_registry_members": _registry_members("2"),
        "runtime_registry_members": _registry_members("3"),
        "base_state_snapshot_ref": _artifact_ref("foundry.state_snapshot", "4"),
        "effective_step": 0,
        "effective_seed": 17,
        "effective_seed_source": "request",
        "effective_mode": "dev",
        "effective_nan_guard_enabled": True,
        "effective_jit": False,
        "effective_capture_env": False,
        **({"actuation_selection_ref": actuation_ref} if actuation_ref is not None else {}),
    }


def test_selection_requires_sorted_unique_ids_but_accepts_explicit_baseline() -> None:
    selection = ProgramGraphActuationSelection.model_validate(
        _selection_payload(selected_ids=("action.a", "action.b"))
    )
    baseline = ProgramGraphActuationSelection.model_validate(_selection_payload(selected_ids=()))

    assert selection.selected_intervention_ids == ("action.a", "action.b")
    assert baseline.selected_intervention_ids == ()
    unicode_id = ProgramGraphActuationSelection.model_validate(
        _selection_payload(selected_ids=("policy.action.α",))
    )
    assert unicode_id.selected_intervention_ids == ("policy.action.α",)
    maximum_length = ProgramGraphActuationSelection.model_validate(
        _selection_payload(selected_ids=("x" * 256,))
    )
    assert len(maximum_length.selected_intervention_ids[0]) == 256
    maximum_count = ProgramGraphActuationSelection.model_validate(
        _selection_payload(selected_ids=tuple(f"id.{index:03}" for index in range(256)))
    )
    assert len(maximum_count.selected_intervention_ids) == 256

    for selected_ids in (("action.b", "action.a"), ("action.a", "action.a")):
        with pytest.raises(ValidationError):
            ProgramGraphActuationSelection.model_validate(
                _selection_payload(selected_ids=selected_ids)
            )
    for invalid_ids in (
        ("",),
        (" action.a",),
        ("action.a ",),
        ("x" * 257,),
        tuple(f"id.{index:03}" for index in range(257)),
    ):
        with pytest.raises(ValidationError):
            ProgramGraphActuationSelection.model_validate(
                _selection_payload(selected_ids=invalid_ids)
            )
    absent_ids = _selection_payload(selected_ids=())
    absent_ids.pop("selected_intervention_ids")
    with pytest.raises(ValidationError):
        ProgramGraphActuationSelection.model_validate(absent_ids)
    null_ids = _selection_payload(selected_ids=())
    null_ids["selected_intervention_ids"] = None
    with pytest.raises(ValidationError):
        ProgramGraphActuationSelection.model_validate(null_ids)

    wrong_kind = _selection_payload(selected_ids=("action.a",))
    wrong_kind["program_graph_ref"] = _artifact_ref("foundry.exec_plan", "4")
    with pytest.raises(ValidationError):
        ProgramGraphActuationSelection.model_validate(wrong_kind)

    missing_profile = _selection_payload(selected_ids=("action.a",))
    missing_profile["lowered_ir_ref"] = {
        **_artifact_ref("foundry.lowered_ir", "5"),
        "manifest_profile_sha256": None,
    }
    with pytest.raises(ValidationError):
        ProgramGraphActuationSelection.model_validate(missing_profile)


def test_actuation_request_v1_1_is_explicit_and_old_versions_keep_their_scope() -> None:
    selection_ref = ProgramGraphActuationSelectionRef.model_validate(
        {
            "artifact_id": "sha256:" + "a" * 64,
            "kind": "foundry.program_graph_actuation_selection",
            "media_type": "application/json",
            "manifest_profile_sha256": _PROFILE,
        }
    )
    base = {
        "exec_plan_ref": _artifact_ref("foundry.exec_plan", "1"),
        "input_bindings_ref": _artifact_ref("foundry.input_bindings", "2"),
    }
    explicit = ExecuteRequest(**base, schema_version="1.1", actuation_selection_ref=selection_ref)
    assert explicit.schema_version == "1.1"
    assert explicit.actuation_selection_ref == selection_ref

    with pytest.raises(ValidationError):
        ExecuteRequest(**base, schema_version="1.1")
    with pytest.raises(ValidationError):
        ExecuteRequest(**base, actuation_selection_ref=selection_ref)

    old_unversioned = ExecuteRequest(**base, schema_version="9.7")
    assert old_unversioned.schema_version == "9.7"
    old_unversioned.validate_actuation_profile()

    feedback_ref = _artifact_ref("foundry.feedback_config", "6")
    legacy_feedback = ExecuteRequest(
        **base,
        feedback_config_ref=feedback_ref,
    )
    assert legacy_feedback.feedback_config_ref is not None
    assert "actuation_selection_ref" not in legacy_feedback.model_dump(mode="json")

    with pytest.raises(
        ValidationError, match="program_graph_actuation_feedback_profile_not_established"
    ):
        ExecuteRequest(
            **base,
            schema_version="1.1",
            actuation_selection_ref=selection_ref,
            feedback_config_ref=feedback_ref,
        )

    missing_selector_copy = explicit.model_copy(update={"actuation_selection_ref": None})
    with pytest.raises(
        ValueError, match="execute_request_actuation_selection_schema_version_mismatch"
    ):
        missing_selector_copy.validate_actuation_profile()

    legacy_schema_copy = explicit.model_copy(update={"schema_version": "1.0"})
    with pytest.raises(
        ValueError, match="execute_request_actuation_selection_schema_version_mismatch"
    ):
        legacy_schema_copy.validate_actuation_profile()

    feedback_copy = explicit.model_copy(update={"feedback_config_ref": feedback_ref})
    with pytest.raises(
        ValueError, match="program_graph_actuation_feedback_profile_not_established"
    ):
        feedback_copy.validate_actuation_profile()


def test_selection_and_basis_round_trip_from_profiled_core_cas(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    canon_spec = CanonSpec(forbid_floats=False)
    selection = ProgramGraphActuationSelection.model_validate(
        _selection_payload(selected_ids=("action.tax",))
    )
    selection_ref = store.put_json(
        selection,
        PutOptions(
            kind=ProgramGraphActuationSelection.ARTIFACT_KIND,
            media_type=ProgramGraphActuationSelection.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=ProgramGraphActuationSelection.ARTIFACT_SCHEMA_NAME,
                version=ProgramGraphActuationSelection.ARTIFACT_SCHEMA_VERSION,
            ),
        ),
        canon_spec=canon_spec,
        return_selected_profile=True,
    )
    selected_ref = ProgramGraphActuationSelectionRef.model_validate(
        selection_ref.model_dump(mode="json")
    )
    selected_artifact_ref = ArtifactRef.model_validate(selected_ref.model_dump(mode="json"))
    reopened_selection = validate_core_model_bounded_read(
        ProgramGraphActuationSelection,
        read_core_json_artifact_bounded(store, selected_artifact_ref, limits=_READ_LIMITS),
    )
    assert reopened_selection == selection

    basis_payload = _basis_payload(
        schema_version="1.4",
        actuation_ref=selected_ref,
        request_schema_version="1.1",
        request_actuation_ref=selected_ref,
    )
    basis_payload["semantic_horizon_step"] = {
        "obligation_set_ref": _artifact_ref("runtime.quality.model_input_obligation_set", "5"),
        "steps": (0, 2),
        "step_index": 1,
        "replication_seed": 17,
        "previous_result_ref": _artifact_ref("foundry.simulation_result", "6"),
    }
    basis_payload["effective_step"] = 2
    basis_payload["effective_seed"] = 19
    basis = FoundryExecutionInputBasis.model_validate(basis_payload)
    basis_ref = store.put_json(
        basis,
        PutOptions(
            kind=FoundryExecutionInputBasis.ARTIFACT_KIND,
            media_type=FoundryExecutionInputBasis.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=FoundryExecutionInputBasis.ARTIFACT_SCHEMA_NAME,
                version="1.4",
            ),
        ),
        canon_spec=canon_spec,
        return_selected_profile=True,
    )
    reopened_basis = validate_core_model_bounded_read(
        FoundryExecutionInputBasis,
        read_core_json_artifact_bounded(store, basis_ref, limits=_READ_LIMITS),
    )
    assert reopened_basis.schema_version == "1.4"
    assert reopened_basis.actuation_selection_ref == selected_ref
    assert reopened_basis.request.actuation_selection_ref == selected_ref
    assert reopened_basis.semantic_horizon_step is not None
    assert reopened_basis.semantic_horizon_step.effective_step == 2


def test_request_and_basis_keep_legacy_selector_fields_omitted() -> None:
    request = ExecuteRequest(
        exec_plan_ref=ExecPlanRef.model_validate(_artifact_ref("foundry.exec_plan", "1")),
        input_bindings_ref=FoundryInputBindingsRef.model_validate(
            _artifact_ref("foundry.input_bindings", "2")
        ),
    )
    request_payload = request.model_dump(mode="json", exclude_unset=True)
    assert request.schema_version == "1.0"
    assert "actuation_selection_ref" not in request_payload
    permissive_legacy_request = ExecuteRequest(
        schema_version="9.7",
        exec_plan_ref=ExecPlanRef.model_validate(_artifact_ref("foundry.exec_plan", "3")),
        input_bindings_ref=FoundryInputBindingsRef.model_validate(
            _artifact_ref("foundry.input_bindings", "4")
        ),
    )
    assert permissive_legacy_request.schema_version == "9.7"

    legacy_basis = FoundryExecutionInputBasis.model_validate(_basis_payload(schema_version="1.0"))
    legacy_payload = legacy_basis.model_dump(mode="json")
    assert "actuation_selection_ref" not in legacy_payload
    assert "actuation_selection_ref" not in legacy_payload["request"]


def test_old_basis_rejects_actuation_and_new_basis_requires_exact_request_join() -> None:
    selected_ref = ProgramGraphActuationSelectionRef.model_validate(
        {
            "artifact_id": "sha256:" + "a" * 64,
            "kind": "foundry.program_graph_actuation_selection",
            "media_type": "application/json",
            "manifest_profile_sha256": _PROFILE,
        }
    )
    old_schema = _basis_payload(
        schema_version="1.2",
        actuation_ref=selected_ref,
        request_schema_version="1.1",
        request_actuation_ref=selected_ref,
    )
    old_schema["semantic_horizon_step"] = {
        "obligation_set_ref": _artifact_ref("runtime.quality.model_input_obligation_set", "5"),
        "steps": (0,),
        "step_index": 0,
        "replication_seed": 17,
    }
    with pytest.raises(ValidationError):
        FoundryExecutionInputBasis.model_validate(old_schema)

    missing_request_selection = _basis_payload(
        schema_version="1.4",
        actuation_ref=selected_ref,
        request_schema_version="1.0",
    )
    with pytest.raises(ValidationError):
        FoundryExecutionInputBasis.model_validate(missing_request_selection)

    mismatched = _basis_payload(
        schema_version="1.4",
        actuation_ref=selected_ref,
        request_schema_version="1.1",
        request_actuation_ref=ProgramGraphActuationSelectionRef.model_validate(
            {
                "artifact_id": "sha256:" + "b" * 64,
                "kind": "foundry.program_graph_actuation_selection",
                "media_type": "application/json",
                "manifest_profile_sha256": _PROFILE,
            }
        ),
    )
    with pytest.raises(ValidationError):
        FoundryExecutionInputBasis.model_validate(mismatched)

    forbidden_sql_horizon = _basis_payload(
        schema_version="1.4",
        actuation_ref=selected_ref,
        request_schema_version="1.1",
        request_actuation_ref=selected_ref,
    )
    forbidden_sql_horizon["registered_sql_admission_ref"] = _artifact_ref(
        "fabric.registered_sql_admission_binding", "c"
    )
    forbidden_sql_horizon["semantic_horizon_step"] = {
        "obligation_set_ref": _artifact_ref("runtime.quality.model_input_obligation_set", "d"),
        "steps": (0,),
        "step_index": 0,
        "replication_seed": 17,
    }
    with pytest.raises(ValidationError):
        FoundryExecutionInputBasis.model_validate(forbidden_sql_horizon)

    feedback_basis = _basis_payload(
        schema_version="1.4",
        actuation_ref=selected_ref,
        request_schema_version="1.1",
        request_actuation_ref=selected_ref,
    )
    feedback_basis["execution_mode"] = "feedback"
    feedback_basis["request"]["feedback_config_ref"] = _artifact_ref("foundry.feedback_config", "e")
    with pytest.raises(ValidationError):
        FoundryExecutionInputBasis.model_validate(feedback_basis)
