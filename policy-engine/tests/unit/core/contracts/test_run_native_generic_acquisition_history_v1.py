"""Strict Core wire checks for historical Native Generic re-entry rows.

These DTO checks establish shape and selected-reference bindings only. They do
not replace the Native owner replay, current admission, or Runtime consumer.
"""

from __future__ import annotations

import json
from copy import deepcopy
from hashlib import sha256
from typing import Any

import pytest
from pydantic import ValidationError

from polisyos.core.canon import CanonSpec, to_canonical_bytes
from polisyos.core.contracts.runtime import (
    RunCandidateSimulationAcquisitionHistoryEntry,
    RunCandidateSimulationAcquisitionHistoryEntryV4,
    RunCandidateSimulationProjection,
    RunGenericCycleSimulationN5ResultBody,
    RunGenericCycleSimulationProjection,
    RunNativeGenericAcquisitionHistoryEntryV1,
    RunNativeGenericBlockedAcquisitionHistoryEntryV1,
)

_SCHEMA_VERSION = "policyos.runtime.run_native_generic_acquisition_history.v1"
_WORLD_HASH = "sha256:" + "a" * 64
_PROFILE_HASH = "sha256:" + "b" * 64

_REF_KINDS = {
    "route_receipt_ref": "runtime_quality.acquisition_route_loop_receipt",
    "reentry_receipt_ref": "runtime_quality.acquisition_overlay_reentry_receipt",
    "source_compiled_ref": "runtime.compiled_recursive_generation_cycle",
    "pending_action_phase_ref": "runtime_quality.acquisition_route_phase_receipt",
    "native_world_checkpoint_ref": "runtime_quality.acquisition_candidate_world_checkpoint",
    "native_input_collection_ref": "runtime_quality.native_derivation_input_checkpoint",
    "original_generic_input_ref": "runtime.quality.generic_cycle_simulation_n5_input",
    "original_profile_ref": "runtime.quality.generic_cycle_simulation_profile",
    "context_job_ref": "runtime.quality.cycle_substrate_context_job",
    "n4_source_ref": "runtime.generation_source_handoff",
    "n5_input_ref": "runtime.quality.generic_cycle_simulation_n5_input",
    "n5_execution_ref": "runtime.quality.generic_cycle_simulation_n5_execution",
    "n5_result_ref": "polisyos.runtime.joint_simulation_result",
    "prepared_checkpoint_ref": "runtime_quality.native_source_reentry_checkpoint",
    "n5_completed_checkpoint_ref": "runtime_quality.native_source_reentry_checkpoint",
    "cycle_completed_checkpoint_ref": "runtime_quality.native_source_reentry_checkpoint",
}


def _ref(kind: str, character: str) -> dict[str, str]:
    return {
        "artifact_id": f"sha256:{character * 64}",
        "kind": kind,
        "media_type": "application/json",
        "manifest_profile_sha256": f"sha256:{character * 64}",
    }


def _wire_row(*, request_profile_version: str = "v5") -> dict[str, Any]:
    refs = {
        name: _ref(kind, character)
        for (name, kind), character in zip(_REF_KINDS.items(), "0123456789abcdef", strict=True)
    }
    result_ref = deepcopy(refs["n5_result_ref"])
    return {
        "schema_version": _SCHEMA_VERSION,
        "source_job_id": "source-job-1",
        "action_job_id": "action-job-2",
        "candidate_id": "candidate-native-1",
        "route_id": "sha256:" + "c" * 64,
        "action_generation": 3,
        **refs,
        "source_cycle_index": 4,
        "continued_cycle_index": 5,
        "original_profile_selection_ref": "sha256:" + "d" * 64,
        "current_profile_selection_ref": "sha256:" + "e" * 64,
        "world_model_record_content_hash": _WORLD_HASH,
        "terminal_outcome": "reentry_completed",
        "n5_input_schema_version": "policyos.runtime.generic_cycle_simulation_n5_input.v2",
        "request_profile_schema_version": (
            f"policyos.runtime.generic_cycle_n5_request_profile.{request_profile_version}"
        ),
        "n5_execution_schema_version": (
            "policyos.runtime.generic_cycle_simulation_n5_execution.v3"
        ),
        "n5_owner_join_status": "resolved",
        "simulation_status": "joint_simulated",
        "simulation_authority_blockers": (),
        "simulation_result_body": {
            "schema_version": "policyos.runtime.run_generic_cycle_simulation_n5_result_body.v1",
            "artifact_ref": result_ref,
            "artifact_schema_name": "policyos.runtime.n5.joint_simulation_result",
            "artifact_schema_version": "5.0.0",
            "result_schema_version": "policyos.runtime.joint_simulation_horizon.v5",
            "selected_manifest_profile_sha256": result_ref["manifest_profile_sha256"],
            "world_model_record_ref": "world-model://native-history-test",
            "world_model_record_content_hash": _WORLD_HASH,
            "atom_ids": ["atom-configured"],
            "selected_outcomes": ["government.balance"],
            "horizon": {
                "start": 0,
                "end": 1,
                "step": 1,
                "valid_time_role": "policy_horizon",
                "transaction_time_role": "recorded_at",
                "scenario_branch_policy": "selected_branch_only",
            },
            "trajectories": [
                {
                    "run_level": "joint",
                    "atom_ids": ["atom-configured"],
                    "points": [
                        {
                            "step": 0,
                            "outcomes": {"government.balance": 0.25},
                            "effects": {"government.balance": 0.0},
                        },
                        {
                            "step": 1,
                            "outcomes": {"government.balance": 0.30},
                            "effects": {"government.balance": 0.05},
                        },
                    ],
                }
            ],
            "uncertainty_kind": "K_sim",
            "authority_purpose": "cycle_input_candidate_only",
            "candidate_status": "candidate_unverified",
            "currentness_status": "not_established",
            "publication_authority": False,
        },
        "limitations": [
            "simulation_only_k_sim_not_world_evidence",
            "historical_native_reentry_not_current_permission",
        ],
        "currentness_status": "not_established",
        "authority_purpose": "candidate_observation_only",
        "publication_authority": False,
    }


def _row(*, request_profile_version: str = "v5") -> RunNativeGenericAcquisitionHistoryEntryV1:
    return RunNativeGenericAcquisitionHistoryEntryV1.model_validate_json(
        json.dumps(_wire_row(request_profile_version=request_profile_version))
    )


def _blocked_wire_row() -> dict[str, Any]:
    wire = _wire_row()
    return {
        **{
            key: wire[key]
            for key in (
                "source_job_id",
                "action_job_id",
                "candidate_id",
                "route_id",
                "action_generation",
                "route_receipt_ref",
                "reentry_receipt_ref",
                "source_compiled_ref",
                "pending_action_phase_ref",
                "source_cycle_index",
                "continued_cycle_index",
            )
        },
        "schema_version": "policyos.runtime.run_native_generic_blocked_acquisition_history.v1",
        "blocker_code": "budget_exhausted_for_next_level",
    }


@pytest.mark.parametrize("mode", ["validation", "serialization"])
def test_native_history_schema_requires_every_exact_full_selected_json_ref(mode: str) -> None:
    schema = RunNativeGenericAcquisitionHistoryEntryV1.model_json_schema(mode=mode)

    for field, kind in _REF_KINDS.items():
        ref_schema = schema["properties"][field]
        assert field in schema["required"]
        assert "anyOf" not in ref_schema
        assert ref_schema["required"] == [
            "artifact_id",
            "kind",
            "media_type",
            "manifest_profile_sha256",
        ]
        assert ref_schema["properties"] == {
            "kind": {"const": kind},
            "media_type": {"const": "application/json"},
            "manifest_profile_sha256": {
                "type": "string",
                "pattern": "^sha256:[0-9a-f]{64}$",
            },
        }


def test_native_history_round_trips_through_candidate_and_generic_projection_unions() -> None:
    row = _row()
    restored_row = RunNativeGenericAcquisitionHistoryEntryV1.model_validate_json(
        row.model_dump_json()
    )
    assert restored_row == row
    assert isinstance(restored_row.simulation_result_body, RunGenericCycleSimulationN5ResultBody)
    assert restored_row.simulation_result_body.artifact_ref == restored_row.n5_result_ref
    assert (
        restored_row.simulation_result_body.world_model_record_content_hash
        == restored_row.world_model_record_content_hash
    )
    assert restored_row.currentness_status == "not_established"
    assert restored_row.authority_purpose == "candidate_observation_only"
    assert restored_row.publication_authority is False
    assert restored_row.simulation_authority_blockers == ()
    assert set(restored_row.limitations) == {
        "simulation_only_k_sim_not_world_evidence",
        "historical_native_reentry_not_current_permission",
    }
    blocked = RunNativeGenericBlockedAcquisitionHistoryEntryV1.model_validate(_blocked_wire_row())
    mixed_history = (restored_row, blocked)
    for version in ("v4", "v5"):
        assert _row(request_profile_version=version).request_profile_schema_version.endswith(
            f".{version}"
        )

    candidate = RunCandidateSimulationProjection.model_validate(
        {
            "run_id": "candidate-run",
            "artifact_status": "resolved",
            "source_ref": _ref("runtime.compiled_recursive_generation_cycle", "a"),
            "source_content_hash": _WORLD_HASH,
            "acquisition_history": mixed_history,
        }
    )
    candidate_round_trip = RunCandidateSimulationProjection.model_validate_json(
        candidate.model_dump_json()
    )
    assert type(candidate_round_trip.acquisition_history[0]) is (
        RunNativeGenericAcquisitionHistoryEntryV1
    )
    assert candidate_round_trip.acquisition_history == mixed_history

    generic = RunGenericCycleSimulationProjection.model_validate(
        {
            "run_id": "generic-run",
            "artifact_status": "resolved",
            "source_ref": _ref("runtime.compiled_recursive_generation_cycle", "a"),
            "source_content_hash": _WORLD_HASH,
            "child_profile_status": "not_attempted",
            "acquisition_history": mixed_history,
        }
    )
    generic_round_trip = RunGenericCycleSimulationProjection.model_validate_json(
        generic.model_dump_json()
    )
    assert generic_round_trip.acquisition_history is not None
    assert type(generic_round_trip.acquisition_history[0]) is (
        RunNativeGenericAcquisitionHistoryEntryV1
    )
    assert generic_round_trip.acquisition_history == mixed_history


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        (
            "pending_action_phase_ref",
            _ref("runtime.quality.generic_cycle_simulation_n5_input", "a"),
        ),
        ("continued_cycle_index", 6),
        ("blocker_code", "provider_unavailable"),
        ("publication_authority", True),
        ("currentness_status", "current"),
        ("numerical_result_status", "resolved"),
        ("n5_result_ref", _ref("polisyos.runtime.joint_simulation_result", "f")),
        ("simulation_result_body", _wire_row()["simulation_result_body"]),
    ],
)
def test_blocked_native_history_refuses_authority_or_numerical_claims(field, replacement) -> None:
    wire = _blocked_wire_row()
    wire[field] = replacement
    with pytest.raises(ValidationError):
        RunNativeGenericBlockedAcquisitionHistoryEntryV1.model_validate(wire)


def test_blocked_native_history_requires_exact_selected_reference() -> None:
    wire = _blocked_wire_row()
    del wire["pending_action_phase_ref"]["manifest_profile_sha256"]
    with pytest.raises(ValidationError, match="native_generic_history_selected_ref_invalid"):
        RunNativeGenericBlockedAcquisitionHistoryEntryV1.model_validate(wire)


@pytest.mark.parametrize("field", tuple(_REF_KINDS))
def test_native_history_refs_require_exact_kind_json_media_and_full_profile(field: str) -> None:
    valid = _wire_row()
    ref = valid[field]
    for replacement in (
        None,
        {**ref, "kind": "foreign.artifact"},
        {**ref, "media_type": "application/octet-stream"},
        {**ref, "manifest_profile_sha256": None},
    ):
        payload = deepcopy(valid)
        payload[field] = replacement
        with pytest.raises(ValidationError):
            RunNativeGenericAcquisitionHistoryEntryV1.model_validate_json(json.dumps(payload))


def test_native_history_blockers_allow_empty_tuple_but_reject_empty_entries() -> None:
    assert _row().simulation_authority_blockers == ()
    payload = _wire_row()
    payload["simulation_authority_blockers"] = [""]

    with pytest.raises(ValidationError):
        RunNativeGenericAcquisitionHistoryEntryV1.model_validate_json(json.dumps(payload))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("source_cycle_index", -1),
        ("continued_cycle_index", 4),
        ("continued_cycle_index", 3),
        ("action_generation", True),
        ("terminal_outcome", "candidate_reentry_completed"),
        ("n5_owner_join_status", "not_established"),
        ("simulation_status", "simulation_blocked"),
        ("n5_input_schema_version", "policyos.runtime.generic_cycle_simulation_n5_input.v1"),
        ("request_profile_schema_version", "policyos.runtime.generic_cycle_n5_request_profile.v3"),
        (
            "n5_execution_schema_version",
            "policyos.runtime.generic_cycle_simulation_n5_execution.v4",
        ),
        ("currentness_status", "current"),
        ("authority_purpose", "publication"),
        ("publication_authority", True),
        ("current_admission", True),
    ],
)
def test_native_history_rejects_wrong_epoch_versions_authority_and_cycle_order(
    field: str, value: Any
) -> None:
    payload = _wire_row()
    payload[field] = value
    with pytest.raises(ValidationError):
        RunNativeGenericAcquisitionHistoryEntryV1.model_validate_json(json.dumps(payload))


@pytest.mark.parametrize(
    "corruption",
    [
        "result_artifact",
        "result_profile",
        "world_hash",
        "missing_limitation",
        "duplicate_limitation",
    ],
)
def test_native_history_rejects_result_body_grafts_and_incomplete_limits(corruption: str) -> None:
    payload = _wire_row()
    if corruption == "result_artifact":
        payload["simulation_result_body"]["artifact_ref"]["artifact_id"] = "sha256:" + "f" * 64
    elif corruption == "result_profile":
        payload["simulation_result_body"]["artifact_ref"]["manifest_profile_sha256"] = (
            "sha256:" + "f" * 64
        )
        payload["simulation_result_body"]["selected_manifest_profile_sha256"] = "sha256:" + "f" * 64
    elif corruption == "world_hash":
        payload["simulation_result_body"]["world_model_record_content_hash"] = "sha256:" + "f" * 64
    elif corruption == "missing_limitation":
        payload["limitations"] = ["simulation_only_k_sim_not_world_evidence"]
    else:
        payload["limitations"] = [
            "simulation_only_k_sim_not_world_evidence",
            "simulation_only_k_sim_not_world_evidence",
        ]
    with pytest.raises(ValidationError):
        RunNativeGenericAcquisitionHistoryEntryV1.model_validate_json(json.dumps(payload))


def test_native_history_is_distinct_from_ncm_v4_and_legacy_ncm_wire_is_unchanged() -> None:
    with pytest.raises(ValidationError):
        RunCandidateSimulationAcquisitionHistoryEntryV4.model_validate(_wire_row())

    legacy_route_ref = _ref("runtime_quality.acquisition_route_loop_receipt", "a")
    legacy_route_ref.pop("manifest_profile_sha256")
    legacy = RunCandidateSimulationAcquisitionHistoryEntry(
        route_receipt_ref=legacy_route_ref,
        route_id="sha256:" + "c" * 64,
        action_generation=1,
        terminal_outcome="quarantined_no_growth",
    )
    legacy_payload = legacy.model_dump(mode="json")
    assert sha256(to_canonical_bytes(legacy_payload, CanonSpec())).hexdigest() == (
        "5653a6c02bb60dcf1b45eeff11aa4d09ad1b405c103fc7f7123b4df0987e8cf3"
    )
