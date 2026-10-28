"""NL cursor projection, strict schema, and legacy request regression witnesses."""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import UTC, datetime, timedelta, timezone
from typing import Any

import pytest
from pydantic import SerializerFunctionWrapHandler, ValidationError, model_serializer

from polisyos.core.contracts.control import NaturalLanguageRunRequest
from polisyos.core.contracts.runtime import TemporalScope
from polisyos.runtime.http.services.control.job_attempt_publication import (
    _NL_REQUEST_SNAPSHOT_KEY,
    _nl_request_body_bytes,
    _nl_request_snapshot_request_values,
    _nl_request_snapshot_schema,
    _validate_nl_request_snapshot,
)
from tests.unit.runtime.http.test_nl_predictive_basis_intake import (
    _payload_for_snapshot,
    _predictive_request,
)

_PREDICTIVE_FIELDS = (
    "value_data_profile_ref",
    "value_data_unit_id",
    "model_spec_ref",
    "policy_spec_ref",
    "calibration_rule_ref",
)
_LEGACY_BODY = (
    b'{"checkpoint_policy":"strict","context":{},"data_source":null,'
    b'"domain_hint":null,"execution_plan":null,"execution_plan_ref":null,'
    b'"execution_profile":null,"expected_outputs":[],"governance_constraints":[],'
    b'"joint_interaction_candidate_intent":null,"llm_model":"simulated-qwen",'
    b'"llm_models":null,"max_iterations":3,"max_parallel_models":1,'
    b'"per_model_budget_usd":null,"policy_flags":{"allow_mock_fallback":false},'
    b'"request":"legacy","run_budget_usd":null,"stop_criteria":{},'
    b'"target_world_scope_profile_id":null}'
)


def _request(scope: object = ...) -> NaturalLanguageRunRequest:
    values: dict[str, object] = {"request": "legacy", "llm_model": "simulated-qwen"}
    if scope is not ...:
        values["temporal_scope"] = scope
    return NaturalLanguageRunRequest.model_validate(values)


def _schema_contract(model: type[NaturalLanguageRunRequest], mode: str) -> None:
    schema = model.model_json_schema(mode=mode)  # type: ignore[arg-type]
    assert schema.get("type") == "object", "typed request object schema missing"
    assert schema.get("additionalProperties") is False, "typed request object schema missing"
    assert isinstance(schema.get("properties"), dict), "typed request object schema missing"
    properties = schema["properties"]
    assert set(properties) == set(model.model_fields)
    assert "request" in schema["required"]
    assert properties["request"]["type"] == "string"
    assert properties["request"]["minLength"] == 1
    assert properties["request"]["maxLength"] == 10_000
    assert "temporal_scope" in properties, "typed temporal cursor property missing"
    assert "temporal_scope" not in schema["required"]
    cursor = properties["temporal_scope"]
    assert cursor.get("type") != "null"
    assert not any(item.get("type") == "null" for item in cursor.get("anyOf", []))
    target = schema["$defs"][cursor["$ref"].rsplit("/", 1)[-1]]
    assert target["type"] == "object"
    assert target["additionalProperties"] is False
    assert set(target["properties"]) == set(TemporalScope.model_fields)
    for field_schema in target["properties"].values():
        assert any(item.get("type") == "null" for item in field_schema["anyOf"])


@pytest.mark.parametrize("mode", ["validation", "serialization"])
def test_temporal_source_schema_retains_complete_typed_request_in_both_modes(mode: str) -> None:
    """Collect on the old source and fail at its missing temporal property."""
    _schema_contract(NaturalLanguageRunRequest, mode)


def test_ordinary_legacy_dump_keeps_all_five_predictive_fields() -> None:
    """Pin the unrelated ordinary serializer contract independently of snapshot law."""
    request = _request()
    for values in (request.model_dump(), json.loads(request.model_dump_json())):
        assert "temporal_scope" not in values
        assert {name: values[name] for name in _PREDICTIVE_FIELDS} == dict.fromkeys(
            _PREDICTIVE_FIELDS
        )
    assert _nl_request_body_bytes(request) == _LEGACY_BODY
    assert _nl_request_snapshot_schema(request) == "polisyos.runtime.control_nl_request_snapshot.v1"
    _validate_nl_request_snapshot(_payload_for_snapshot(request), None)


@pytest.mark.parametrize("scope", [{"snapshot_id": "s-1"}, {"branch": "main", "tx_at": None}])
def test_partial_temporal_dump_and_admitted_roundtrip_preserve_inner_presence(scope) -> None:
    request = _request(scope)
    ordinary = request.model_dump(mode="json")
    assert ordinary["temporal_scope"] == scope
    assert json.loads(request.model_dump_json())["temporal_scope"] == scope
    assert {name: ordinary[name] for name in _PREDICTIVE_FIELDS} == dict.fromkeys(
        _PREDICTIVE_FIELDS
    )
    snapshot_values = _nl_request_snapshot_request_values(request)
    replayed = NaturalLanguageRunRequest.model_validate(snapshot_values)
    assert replayed.model_dump(mode="json")["temporal_scope"] == scope
    assert replayed.temporal_scope.model_fields_set == set(scope)


def test_temporal_presence_projection_respects_nested_include_and_exclude() -> None:
    request = _request({"valid_at": "2026-01-01T00:00:00Z", "tx_at": None})
    assert request.model_dump(mode="json", include={"temporal_scope": {"tx_at"}}) == {
        "temporal_scope": {"tx_at": None}
    }
    assert request.model_dump(mode="json", exclude={"temporal_scope": {"valid_at"}})[
        "temporal_scope"
    ] == {"tx_at": None}
    assert "temporal_scope" not in request.model_dump(exclude={"temporal_scope"})
    assert _request().model_dump(include={"temporal_scope"}) == {}


def test_schema_return_annotation_removal_control_preserves_values_but_breaks_contract() -> None:
    """Reintroduce only the generic return schema while retaining the real handler."""

    class GenericReturnRequest(NaturalLanguageRunRequest):
        @model_serializer(mode="wrap")
        def _omit_unselected_temporal_scope(
            self, handler: SerializerFunctionWrapHandler
        ) -> dict[str, Any]:
            return super()._omit_unselected_temporal_scope(handler)

    values = {"request": "legacy", "temporal_scope": {"branch": "main", "tx_at": None}}
    assert GenericReturnRequest.model_validate(values).model_dump(mode="json") == (
        NaturalLanguageRunRequest.model_validate(values).model_dump(mode="json")
    )
    _schema_contract(GenericReturnRequest, "validation")
    with pytest.raises(AssertionError, match="typed request object schema missing"):
        _schema_contract(GenericReturnRequest, "serialization")


@pytest.mark.parametrize(
    "timestamp",
    [
        "0001-01-01T00:00:00+14:00",
        "9999-12-31T23:59:59-14:00",
        datetime(1, 1, 1, tzinfo=timezone(timedelta(hours=14))),
        datetime(9999, 12, 31, 23, 59, 59, tzinfo=timezone(-timedelta(hours=14))),
    ],
)
def test_temporal_utc_overflow_refuses_before_queue(timestamp: object) -> None:
    with pytest.raises(ValidationError, match="natural_language_temporal_scope_timestamp_invalid"):
        _request({"valid_at": timestamp})


@pytest.mark.parametrize(
    "scope",
    [None, {}, {"valid_at": None}, {"branch": " \t"}, {"branch": 1}, {"unknown_axis": "x"}],
)
def test_invalid_temporal_selection_is_not_an_implicit_default(scope: object) -> None:
    with pytest.raises(ValidationError, match="natural_language_temporal_scope"):
        _request(scope)


@pytest.mark.parametrize(
    "timestamp",
    [
        "2026-01-01",
        "2026-01-01T00:00:00",
        "2026-01-01T00:00:60Z",
        "2026-01-01T00:00:00.1234567Z",
        1_767_225_600,
        datetime(2026, 1, 1),
    ],
)
def test_temporal_timestamp_coercion_and_lost_precision_are_refused(timestamp: object) -> None:
    with pytest.raises(ValidationError, match="natural_language_temporal_scope_timestamp"):
        _request({"valid_at": timestamp})


def test_temporal_axes_normalize_independently_without_losing_microseconds() -> None:
    request = _request(
        {
            "valid_at": "2030-02-03T04:05:06.123456+05:30",
            "tx_at": datetime(2025, 1, 2, 3, 4, 5, 654321, tzinfo=timezone(timedelta(hours=-4))),
            "scenario_id": "  scenario identity  ",
            "branch": None,
        }
    )
    assert request.temporal_scope.valid_at == datetime(2030, 2, 2, 22, 35, 6, 123456, tzinfo=UTC)
    assert request.model_dump(mode="json")["temporal_scope"] == {
        "valid_at": "2030-02-02T22:35:06.123456Z",
        "tx_at": "2025-01-02T07:04:05.654321Z",
        "scenario_id": "  scenario identity  ",
        "branch": None,
    }


@pytest.mark.parametrize("mutation", ["remove", "drop_null", "insert_null", "extra_axis"])
def test_temporal_snapshot_rejects_queue_presence_drift(mutation: str) -> None:
    request = _request({"branch": "main", "tx_at": None})
    payload = _payload_for_snapshot(request)
    payload["temporal_scope"] = {"branch": "main", "tx_at": None}
    _validate_nl_request_snapshot(payload, None)
    changed = deepcopy(payload)
    if mutation == "remove":
        changed.pop("temporal_scope")
    elif mutation == "drop_null":
        changed["temporal_scope"].pop("tx_at")
    elif mutation == "insert_null":
        changed["temporal_scope"]["valid_at"] = None
    else:
        changed["temporal_scope"]["unknown_axis"] = "x"
    with pytest.raises(ValueError, match="nl_authorized_request_payload_mismatch"):
        _validate_nl_request_snapshot(changed, None)


def test_mixed_legacy_and_predictive_requests_keep_their_snapshot_versions_and_bytes() -> None:
    legacy = _request()
    predictive = _predictive_request()
    predictive_before = _nl_request_body_bytes(predictive)
    expected = json.loads(_LEGACY_BODY)
    expected.update(
        {
            "request": "Evaluate the selected candidate inputs.",
            "joint_interaction_candidate_intent": "n4_unique_parent_source_members.v1",
            "data_source": {
                "data_snapshot_ref": {
                    "artifact_id": "sha256:" + "b" * 64,
                    "kind": "fabric.data_snapshot",
                    "media_type": "application/json",
                    "manifest_profile_sha256": "sha256:" + "a" * 64,
                },
                "input_bindings_ref": None,
                "data_view_request_ref": None,
            },
            "value_data_unit_id": "UA",
        }
    )
    for name, kind, digit in (
        ("value_data_profile_ref", "runtime.value_data_profile", "c"),
        ("model_spec_ref", "ir.model_spec", "d"),
        ("policy_spec_ref", "ir.policy_spec", "e"),
        ("calibration_rule_ref", "ir.forecast_calibration_rule", "f"),
    ):
        expected[name] = {
            "artifact_id": "sha256:" + digit * 64,
            "kind": kind,
            "media_type": "application/json",
            "manifest_profile_sha256": "sha256:" + digit * 64,
        }
    assert (
        predictive_before
        == json.dumps(expected, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    )
    _request({"snapshot_id": "selected-later"})
    assert _nl_request_body_bytes(legacy) == _LEGACY_BODY
    assert _nl_request_body_bytes(predictive) == predictive_before
    assert (
        _nl_request_snapshot_schema(predictive) == "polisyos.runtime.control_nl_request_snapshot.v2"
    )
    for request in (legacy, predictive):
        payload = _payload_for_snapshot(request)
        assert "temporal_scope" not in payload[_NL_REQUEST_SNAPSHOT_KEY]["request"]
        _validate_nl_request_snapshot(payload, None)
