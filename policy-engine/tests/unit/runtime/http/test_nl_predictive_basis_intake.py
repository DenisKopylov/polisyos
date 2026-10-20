"""Typed, immutable NL intake for selected predictive run inputs."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.contracts.control import (
    DataSourceBinding,
    NaturalLanguageRunRequest,
)
from polisyos.core.contracts.fabric import DataSnapshotRef
from polisyos.runtime.http.services.control.job_attempt_publication import (
    _NL_REQUEST_SNAPSHOT_DIGEST_PROFILE,
    _NL_REQUEST_SNAPSHOT_KEY,
    _NL_REQUEST_SNAPSHOT_NEW_FIELDS,
    _NL_REQUEST_SNAPSHOT_SCHEMA_V1,
    _NL_REQUEST_SNAPSHOT_SCHEMA_V2,
    _nl_request_body_bytes,
    _nl_request_snapshot_request_values,
    _nl_request_snapshot_schema,
    _validate_nl_request_snapshot,
)


def _reference(kind: str, digit: str) -> ArtifactRef:
    digest = "sha256:" + digit * 64
    return ArtifactRef(
        artifact_id=digest,
        kind=kind,
        media_type="application/json",
        manifest_profile_sha256=digest,
    )


def _predictive_request() -> NaturalLanguageRunRequest:
    snapshot_digest = "sha256:" + "a" * 64
    snapshot = DataSnapshotRef(
        artifact_id="sha256:" + "b" * 64,
        kind="fabric.data_snapshot",
        media_type="application/json",
        manifest_profile_sha256=snapshot_digest,
    )
    return NaturalLanguageRunRequest(
        request="Evaluate the selected candidate inputs.",
        llm_model="simulated-qwen",
        joint_interaction_candidate_intent="n4_unique_parent_source_members.v1",
        data_source=DataSourceBinding(data_snapshot_ref=snapshot),
        value_data_profile_ref=_reference("runtime.value_data_profile", "c"),
        value_data_unit_id="UA",
        model_spec_ref=_reference("ir.model_spec", "d"),
        policy_spec_ref=_reference("ir.policy_spec", "e"),
        calibration_rule_ref=_reference("ir.forecast_calibration_rule", "f"),
    )


def _payload_for_snapshot(request: NaturalLanguageRunRequest) -> dict[str, object]:
    schema_version = _nl_request_snapshot_schema(request)
    request_values = _nl_request_snapshot_request_values(
        request,
        schema_version=schema_version,
    )
    payload: dict[str, object] = {
        "request": request.request,
        "joint_interaction_candidate_intent": request.joint_interaction_candidate_intent,
        "context": dict(request.context),
        "domain_hint": request.domain_hint,
        "data_source": (
            request.data_source.model_dump(mode="json") if request.data_source is not None else None
        ),
        "target_world_scope_profile_id": request.target_world_scope_profile_id,
        "max_iterations": request.max_iterations,
        "llm_models": [request.llm_model or "simulated-qwen"],
        "max_parallel_models": request.max_parallel_models,
        "run_budget_usd": request.run_budget_usd,
        "per_model_budget_usd": request.per_model_budget_usd,
        "checkpoint_policy": request.checkpoint_policy,
        "execution_plan_ref": request.execution_plan_ref,
        "execution_plan": request.execution_plan,
        "stop_criteria": request.stop_criteria,
        "governance_constraints": request.governance_constraints,
        "expected_outputs": request.expected_outputs,
        _NL_REQUEST_SNAPSHOT_KEY: {
            "schema_version": schema_version,
            "digest_profile": _NL_REQUEST_SNAPSHOT_DIGEST_PROFILE,
            "request": request_values,
            "normalized_llm_models": [request.llm_model or "simulated-qwen"],
        },
    }
    for field_name in _NL_REQUEST_SNAPSHOT_NEW_FIELDS:
        if field_name not in request.model_fields_set:
            continue
        value = getattr(request, field_name)
        payload[field_name] = (
            value.model_dump(mode="json") if isinstance(value, ArtifactRef) else value
        )
    return payload


def test_profileless_v1_snapshot_and_idempotency_bytes_remain_legacy_exact() -> None:
    request = NaturalLanguageRunRequest(
        request="Keep the legacy profileless launch.",
        llm_model="simulated-qwen",
    )
    legacy_values = request.model_dump(mode="json")
    for field_name in _NL_REQUEST_SNAPSHOT_NEW_FIELDS:
        legacy_values.pop(field_name, None)
    expected_body = json.dumps(
        legacy_values,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")

    assert _nl_request_snapshot_schema(request) == _NL_REQUEST_SNAPSHOT_SCHEMA_V1
    assert _nl_request_body_bytes(request) == expected_body
    _validate_nl_request_snapshot(_payload_for_snapshot(request), None)


def test_complete_predictive_basis_is_bound_to_v2_payload_and_typed_roots() -> None:
    request = _predictive_request()
    payload = _payload_for_snapshot(request)

    assert _nl_request_snapshot_schema(request) == _NL_REQUEST_SNAPSHOT_SCHEMA_V2
    assert set(_NL_REQUEST_SNAPSHOT_NEW_FIELDS).issubset(
        payload[_NL_REQUEST_SNAPSHOT_KEY]["request"]  # type: ignore[index]
    )
    _validate_nl_request_snapshot(payload, None)

    changed_payload = dict(payload)
    changed_payload["model_spec_ref"] = _reference("ir.model_spec", "9").model_dump(mode="json")
    with pytest.raises(ValueError, match="nl_authorized_request_payload_mismatch"):
        _validate_nl_request_snapshot(changed_payload, None)


def test_v2_worker_payload_cannot_add_unbound_predictive_ref() -> None:
    request = NaturalLanguageRunRequest(
        request="Run N4 without a predictive basis.",
        llm_model="simulated-qwen",
        joint_interaction_candidate_intent="n4_unique_parent_source_members.v1",
    )
    payload = _payload_for_snapshot(request)
    payload["value_data_profile_ref"] = _reference("runtime.value_data_profile", "c").model_dump(
        mode="json"
    )

    with pytest.raises(ValueError, match="nl_authorized_request_payload_mismatch"):
        _validate_nl_request_snapshot(payload, None)


@pytest.mark.parametrize(
    ("field_name", "replacement"),
    [
        ("value_data_profile_ref", None),
        ("value_data_unit_id", None),
        ("model_spec_ref", None),
        ("policy_spec_ref", None),
        ("calibration_rule_ref", None),
        ("model_spec_ref", _reference("ir.policy_spec", "9")),
        (
            "policy_spec_ref",
            _reference("ir.policy_spec", "9").model_copy(update={"manifest_profile_sha256": None}),
        ),
    ],
)
def test_incomplete_or_malformed_predictive_basis_is_not_profileless(
    field_name: str,
    replacement: object,
) -> None:
    request = _predictive_request()
    payload = request.model_dump(mode="python")
    payload[field_name] = replacement

    with pytest.raises(ValidationError):
        NaturalLanguageRunRequest.model_validate(payload)


def test_predictive_basis_requires_selected_typed_snapshot_and_n4_intent() -> None:
    request = _predictive_request()
    payload = request.model_dump(mode="python")
    assert isinstance(payload["data_source"], dict)

    typed_snapshot = DataSnapshotRef(
        artifact_id="sha256:" + "b" * 64,
        kind="fabric.data_snapshot",
        media_type="application/json",
        manifest_profile_sha256="sha256:" + "a" * 64,
    ).model_dump(mode="python")
    payload["data_source"] = {"data_snapshot_ref": typed_snapshot}
    payload["joint_interaction_candidate_intent"] = None
    with pytest.raises(
        ValidationError,
        match="natural_language_predictive_input_requires_n4_snapshot",
    ):
        NaturalLanguageRunRequest.model_validate(payload)

    payload["joint_interaction_candidate_intent"] = "n4_unique_parent_source_members.v1"
    unprofiled_snapshot = DataSnapshotRef(
        artifact_id="sha256:" + "b" * 64,
        kind="fabric.data_snapshot",
        media_type="application/json",
        manifest_profile_sha256=None,
    ).model_dump(mode="python")
    payload["data_source"] = {"data_snapshot_ref": unprofiled_snapshot}
    with pytest.raises(ValidationError):
        NaturalLanguageRunRequest.model_validate(payload)

    payload["data_source"] = {"data_snapshot_ref": "sha256:" + "b" * 64}
    with pytest.raises(
        ValidationError,
        match="natural_language_predictive_input_requires_n4_snapshot",
    ):
        NaturalLanguageRunRequest.model_validate(payload)


def test_explicit_null_predictive_field_is_refused_instead_of_omitted() -> None:
    with pytest.raises(ValidationError, match="natural_language_predictive_input_explicit_null"):
        NaturalLanguageRunRequest.model_validate(
            {
                "request": "Legacy intent with an explicitly malformed field.",
                "value_data_profile_ref": None,
            }
        )
