"""Behavioral compatibility checks for the relocated DDM contracts."""

from __future__ import annotations

import importlib
import json
import pickle
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator, FormatChecker
from pydantic import ValidationError

from polisyos.ddm.contracts.events import MetricDirection, ShiftDetectedEvent
from polisyos.ddm.contracts.metric_budget import MetricBudgetPolicy


def _manual_shift_schema() -> dict[str, Any]:
    project_root = Path(__file__).parents[3]
    schema_path = project_root / "src/polisyos/ddm/integration/shift_event.schema.json"
    return json.loads(schema_path.read_text(encoding="utf-8"))


def _shift_payload(case: str) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "event_type": "ml.track_2_2.shift_detected.v1",
        "event_id": "shift-1",
        "timestamp": "2026-04-26T00:00:00Z",
        "model_id": "model",
        "model_version": "v1",
        "detector_id": "input_mmd_global_v3",
        "detector_family": "online_mmd",
        "signal": "input_shift",
        "representation": "feature_embedding_v2",
        "reference_window": {
            "start": "2026-04-01T00:00:00Z",
            "end": "2026-04-02T00:00:00Z",
            "n": 100,
        },
        "current_window": {
            "start": "2026-04-01T00:00:00Z",
            "end": "2026-04-02T00:00:00Z",
            "n": 100,
        },
        "stationarity_regime_id": "SR-1-model-v1",
        "calibration_id": "calib-1",
        "test_statistic": 0.2,
        "empirical_fp_rate": 0.001,
        "shift_severity": 0.44,
        "diagnostic_only": False,
    }

    if case == "p-only":
        payload["p_value"] = 0.05
    elif case == "e-only":
        payload["e_value"] = 3.0
    elif case == "ert-only":
        payload["ert"] = 10_000.0
    elif case == "no-evidence":
        pass
    elif case == "all-evidence-null":
        payload.update(p_value=None, e_value=None, ert=None)
    elif case == "missing-empirical-rate":
        payload["ert"] = 10_000.0
        del payload["empirical_fp_rate"]
    elif case == "p-out-of-range":
        payload["p_value"] = 1.01
    elif case == "severity-out-of-range":
        payload["ert"] = 10_000.0
        payload["shift_severity"] = 1.01
    elif case == "bad-date-time":
        payload["ert"] = 10_000.0
        payload["timestamp"] = "not-a-date-time"
    elif case == "unknown-property":
        payload["ert"] = 10_000.0
        payload["unrecognized"] = "extra"
    else:
        raise AssertionError(f"unknown shift payload case: {case}")

    return payload


@pytest.mark.parametrize(
    ("case", "expected_valid"),
    [
        ("p-only", True),
        ("e-only", True),
        ("ert-only", True),
        ("no-evidence", False),
        ("all-evidence-null", False),
        ("missing-empirical-rate", False),
        ("p-out-of-range", False),
        ("severity-out-of-range", False),
        ("bad-date-time", False),
        ("unknown-property", False),
    ],
)
def test_manual_schema_and_model_validate_evidence_cases(
    case: str,
    expected_valid: bool,
) -> None:
    """Evidence cases with wire-required defaults explicit agree across validators."""

    schema = _manual_shift_schema()
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    payload = _shift_payload(case)
    schema_errors = list(validator.iter_errors(payload))

    if expected_valid:
        assert not schema_errors, f"{case}: {schema_errors}"
        event = ShiftDetectedEvent.model_validate(payload)
        assert event.event_id == payload["event_id"]
        assert event.model_dump(mode="json", by_alias=True, exclude_unset=True) == payload
    else:
        assert schema_errors, f"manual schema accepted {case}"
        with pytest.raises(ValidationError):
            ShiftDetectedEvent.model_validate(payload)


def test_manual_wire_requires_fields_that_domain_model_defaults() -> None:
    """Wire validation requires defaults that domain input validation supplies."""

    schema = _manual_shift_schema()
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    payload = _shift_payload("p-only")
    del payload["event_type"]
    del payload["diagnostic_only"]

    assert not validator.is_valid(payload)

    event = ShiftDetectedEvent.model_validate(payload)
    assert event.event_type == "ml.track_2_2.shift_detected.v1"
    assert event.diagnostic_only is False
    assert {"event_type", "diagnostic_only"}.isdisjoint(event.model_fields_set)
    assert validator.is_valid(event.model_dump(mode="json", by_alias=True))


def test_manual_schema_evidence_branch_is_load_bearing() -> None:
    """Removing the p-value branch rejects its p-only witness despite field markers."""

    schema = _manual_shift_schema()
    Draft202012Validator.check_schema(schema)
    branch_indexes = [
        index
        for index, branch in enumerate(schema.get("anyOf", []))
        if "p_value" in branch.get("properties", {})
    ]
    assert len(branch_indexes) == 1

    p_only = _shift_payload("p-only")
    original_validator = Draft202012Validator(schema, format_checker=FormatChecker())
    assert original_validator.is_valid(p_only)
    assert ShiftDetectedEvent.model_validate(p_only).p_value == 0.05

    weakened_schema = deepcopy(schema)
    del weakened_schema["anyOf"][branch_indexes[0]]
    weakened_validator = Draft202012Validator(
        weakened_schema,
        format_checker=FormatChecker(),
    )
    assert not weakened_validator.is_valid(p_only)


def _number_branch(schema_property: dict[str, Any]) -> dict[str, Any]:
    if schema_property.get("type") == "number":
        return schema_property
    for branch in schema_property.get("anyOf", []):
        if branch.get("type") == "number":
            return branch
    raise AssertionError(f"no numeric branch in schema property: {schema_property}")


def test_canonical_model_schemas_preserve_fields_defaults_and_constraints() -> None:
    """Generated schemas expose the canonical field and numeric constraints."""

    event_fields = ShiftDetectedEvent.model_fields
    event_schema = ShiftDetectedEvent.model_json_schema()
    event_properties = event_schema["properties"]

    assert event_schema["additionalProperties"] is False
    assert set(event_properties) == set(event_fields)
    assert set(event_schema["required"]) == {
        name for name, field in event_fields.items() if field.is_required()
    }
    assert event_properties["event_type"]["const"] == event_fields["event_type"].default
    assert event_properties["event_type"]["default"] == event_fields["event_type"].default
    assert event_properties["diagnostic_only"]["default"] is False
    assert event_fields["diagnostic_only"].default is False
    assert event_fields["p_value"].default is None
    assert event_properties["p_value"]["default"] is None
    assert _number_branch(event_properties["p_value"])["minimum"] == 0.0
    assert _number_branch(event_properties["p_value"])["maximum"] == 1.0
    assert event_fields["e_value"].default is None
    assert _number_branch(event_properties["e_value"])["minimum"] == 0.0
    assert event_fields["ert"].default is None
    assert _number_branch(event_properties["ert"])["exclusiveMinimum"] == 0.0
    assert event_fields["empirical_fp_rate"].default is None
    assert _number_branch(event_properties["empirical_fp_rate"])["minimum"] == 0.0
    assert _number_branch(event_properties["empirical_fp_rate"])["maximum"] == 1.0
    assert event_properties["shift_severity"]["minimum"] == 0.0
    assert event_properties["shift_severity"]["maximum"] == 1.0
    assert event_properties["timestamp"]["format"] == "date-time"
    assert event_schema["$defs"]["MonitoringWindow"]["additionalProperties"] is False
    assert event_schema["$defs"]["MonitoringWindow"]["properties"]["n"]["minimum"] == 0

    budget_fields = MetricBudgetPolicy.model_fields
    budget_schema = MetricBudgetPolicy.model_json_schema()
    budget_properties = budget_schema["properties"]

    assert budget_schema["additionalProperties"] is False
    assert set(budget_properties) == set(budget_fields)
    assert set(budget_schema["required"]) == {
        name for name, field in budget_fields.items() if field.is_required()
    }
    assert budget_properties["model_id"]["minLength"] == 1
    assert budget_properties["model_version"]["minLength"] == 1
    assert budget_properties["metric"]["minLength"] == 1
    assert budget_properties["reference_value"]["type"] == "number"
    for name in ("minimum_acceptable_value", "maximum_acceptable_value"):
        assert budget_fields[name].default is None
        assert budget_properties[name]["default"] is None
        assert _number_branch(budget_properties[name])["type"] == "number"
    direction_schema = budget_schema["$defs"]["MetricDirection"]
    assert set(direction_schema["enum"]) == {direction.value for direction in MetricDirection}


def _pickle_round_trip_with_legacy_global(instance: Any, legacy_module_name: str) -> Any:
    """Write a pickle carrying the legacy global, then read it after restoration."""

    canonical_type = type(instance)
    legacy_module = importlib.import_module(legacy_module_name)
    assert getattr(legacy_module, canonical_type.__name__) is canonical_type

    original_module = canonical_type.__module__
    try:
        canonical_type.__module__ = legacy_module_name
        payload = pickle.dumps(instance, protocol=pickle.HIGHEST_PROTOCOL)
    finally:
        canonical_type.__module__ = original_module

    assert canonical_type.__module__ == original_module
    assert legacy_module_name.encode() in payload
    assert canonical_type.__qualname__.encode() in payload
    return pickle.loads(payload)  # noqa: S301 -- bytes are generated from the local model above.


def _assert_model_pickle_preserved(loaded: Any, expected: Any, canonical_type: type[Any]) -> None:
    assert type(loaded) is canonical_type
    assert loaded.model_dump(mode="python") == expected.model_dump(mode="python")
    assert loaded.model_fields_set == expected.model_fields_set
    assert loaded.__dict__ == expected.__dict__


def test_shift_event_pickle_loads_from_legacy_integration_fqn() -> None:
    """Pickles with the old integration global resolve to the canonical event class."""

    expected = ShiftDetectedEvent.model_validate(_shift_payload("p-only"))
    loaded = _pickle_round_trip_with_legacy_global(
        expected,
        "polisyos.ddm.integration.events",
    )

    _assert_model_pickle_preserved(loaded, expected, ShiftDetectedEvent)


def test_metric_budget_pickle_loads_from_legacy_mapper_fqn() -> None:
    """Pickles with the old mapper global resolve to the canonical budget class."""

    expected = MetricBudgetPolicy(
        model_id="model",
        model_version="v1",
        metric="accuracy",
        metric_direction=MetricDirection.HIGHER_IS_BETTER,
        reference_value=0.9,
        minimum_acceptable_value=0.8,
    )
    loaded = _pickle_round_trip_with_legacy_global(
        expected,
        "polisyos.ddm.readiness.readiness_mapper",
    )

    _assert_model_pickle_preserved(loaded, expected, MetricBudgetPolicy)
