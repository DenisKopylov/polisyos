"""Directional registry wire compatibility and fresh source-bound replay."""

from __future__ import annotations

import copy
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker
from pydantic import ValidationError

from polisyos.ddm.calibration.audit import build_calibration_audit
from polisyos.ddm.calibration.calibrate import (
    FpTarget,
    Period,
    StationarityRegime,
    calibrate_detector,
)
from polisyos.ddm.contracts.events import MetricDirection
from polisyos.ddm.contracts.metric_budget import MetricBudgetPolicy
from polisyos.ddm.integration.model_registry import (
    ModelRegistryReadinessRecord,
    evaluate_registry_gate,
    rebind_calibration_validity,
)
from polisyos.ddm.integration.monitor import DriftAndDegradationMonitor

NOW = datetime(2026, 4, 26, tzinfo=UTC)
SCHEMA_ROOT = Path(__file__).parents[3] / "src/polisyos/ddm/integration"
SOURCE_FIELDS = (
    "readiness_event_id",
    "readiness_effective_at",
    "readiness_expires_at",
    "source_binding_digest",
)


def _validator(filename: str) -> Draft202012Validator:
    schema = json.loads((SCHEMA_ROOT / filename).read_text())
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


@pytest.fixture
def context():
    """Produce a real calibration/monitor record on a bounded synthetic stream."""

    regime = StationarityRegime(
        id="regime-1",
        model_id="model-1",
        model_version="v1",
        reference_period=Period(start=NOW - timedelta(days=30), end=NOW - timedelta(days=20)),
        calibration_period=Period(start=NOW - timedelta(days=20), end=NOW - timedelta(days=10)),
        holdout_stationary_period=Period(start=NOW - timedelta(days=10), end=NOW),
        invalidation_triggers=["model_version_change"],
    )
    report = calibrate_detector(
        detector_id="detector-1",
        stationarity_regime=regime,
        fp_target=FpTarget(horizon="30d", alpha=0.05),
        calibration_streams=[[0.1, 0.2, 0.3] for _ in range(100)],
        holdout_streams=[[0.01, 0.02, 0.03] for _ in range(100)],
        seed=7,
    )
    audit = build_calibration_audit(calibration_id="calibration-1", report=report)
    budget = MetricBudgetPolicy(
        model_id="model-1",
        model_version="v1",
        metric="accuracy",
        metric_direction=MetricDirection.HIGHER_IS_BETTER,
        reference_value=0.9,
        minimum_acceptable_value=0.8,
    )
    result = DriftAndDegradationMonitor().evaluate_window(
        model_id="model-1",
        model_version="v1",
        metric_budget=budget,
        calibration_audit=audit,
        _calibration_report=report,
        _observed_invalidation_triggers=[],
        timestamp=NOW,
    )
    assert result.registry_record is not None
    return report, audit, budget, result


def _rebind(record, context, **changes):
    report, audit, budget, result = context
    arguments = {
        "report": report,
        "calibration_audit": audit,
        "now": NOW,
        "observed_invalidation_triggers": [],
        "metric_budget": budget,
        "readiness_event": result.readiness_event,
        "shift_events": result.shift_risk_events,
        "last_degradation_event": result.degradation_event,
    }
    arguments.update(changes)
    return rebind_calibration_validity(record, **arguments)


def test_native_new_producer_requires_distinct_v2_reader(context, tmp_path):
    """The actual producer's persisted output is explicitly new-to-old breaking."""

    record = context[3].registry_record
    path = tmp_path / "registry.json"
    path.write_text(record.model_dump_json())
    payload = json.loads(path.read_text())
    old = _validator("model_registry_record.v1.schema.json")
    new = _validator("model_registry_record.schema.json")
    assert old.schema["$id"] != new.schema["$id"]
    assert payload["schema_version"] == "2"
    assert all(payload[field] is not None for field in SOURCE_FIELDS)
    old_errors = list(old.iter_errors(payload))
    assert len(old_errors) == 1
    assert old_errors[0].validator == "additionalProperties"
    new.validate(payload)
    reopened = ModelRegistryReadinessRecord.model_validate_json(path.read_text())
    assert not evaluate_registry_gate(reopened).promotion_allowed
    rebound = _rebind(reopened, context)
    assert evaluate_registry_gate(rebound).promotion_allowed


def test_old_record_new_reader_preserves_legacy_wire_and_stays_non_gating(context):
    """New readers accept old closed wire bytes without reconstructing sources."""

    payload = context[3].registry_record.model_dump(mode="json")
    for field in ("schema_version", *SOURCE_FIELDS):
        payload.pop(field)
    old = _validator("model_registry_record.v1.schema.json")
    old.validate(payload)
    reopened = ModelRegistryReadinessRecord.model_validate_json(json.dumps(payload))
    assert reopened.schema_version == "1"
    assert reopened.model_dump(mode="json") == payload
    old.validate(reopened.model_dump(mode="json"))
    assert not evaluate_registry_gate(reopened).promotion_allowed
    assert not evaluate_registry_gate(_rebind(reopened, context)).promotion_allowed
    assert list(_validator("model_registry_record.schema.json").iter_errors(payload))
    with pytest.raises(ValueError, match="explicit rebuild"):
        ModelRegistryReadinessRecord.migrate_unversioned_source_record(payload)


def test_prerelease_enriched_record_requires_explicit_migration_and_rebind(context):
    """Migration creates distinct bytes and restores no private permission."""

    payload = context[3].registry_record.model_dump(mode="json")
    payload.pop("schema_version")
    original = copy.deepcopy(payload)
    with pytest.raises(ValidationError, match="require schema_version"):
        ModelRegistryReadinessRecord.model_validate(payload)
    migrated = ModelRegistryReadinessRecord.migrate_unversioned_source_record(payload)
    assert payload == original
    assert migrated.schema_version == "2"
    _validator("model_registry_record.schema.json").validate(migrated.model_dump(mode="json"))
    assert not evaluate_registry_gate(migrated).promotion_allowed
    assert evaluate_registry_gate(_rebind(migrated, context)).promotion_allowed
    with pytest.raises(ValueError, match="requires an unversioned"):
        ModelRegistryReadinessRecord.migrate_unversioned_source_record(
            migrated.model_dump(mode="json")
        )


def test_fresh_v2_rebind_retains_persisted_veto(context):
    """Version and valid sources cannot lift a separately persisted restriction."""

    payload = context[3].registry_record.model_dump(mode="json")
    payload["promotion_allowed"] = False
    reopened = ModelRegistryReadinessRecord.model_validate_json(json.dumps(payload))
    rebound = _rebind(reopened, context)
    for signoff in (False, True):
        gate = evaluate_registry_gate(rebound, owner_signoff=signoff)
        assert not gate.promotion_allowed
        assert gate.reason == "persisted_readiness_veto"


@pytest.mark.parametrize("schema_version", ["0", "3", 2, True, None])
def test_unknown_or_ill_typed_schema_version_refuses(context, schema_version):
    payload = context[3].registry_record.model_dump(mode="json")
    payload["schema_version"] = schema_version
    with pytest.raises(ValidationError):
        ModelRegistryReadinessRecord.model_validate(payload)
    assert list(_validator("model_registry_record.schema.json").iter_errors(payload))


def test_integrity_valid_v2_source_digest_forgery_does_not_rebind(context):
    payload = context[3].registry_record.model_dump(mode="json")
    payload["source_binding_digest"] = "0" * 64
    _validator("model_registry_record.schema.json").validate(payload)
    record = ModelRegistryReadinessRecord.model_validate_json(json.dumps(payload))
    gate = evaluate_registry_gate(_rebind(record, context))
    assert not gate.promotion_allowed
    assert gate.reason == "registry_source_binding_not_established"


def test_v2_format_does_not_make_unavailable_trigger_observation_valid(context):
    record = ModelRegistryReadinessRecord.model_validate_json(
        context[3].registry_record.model_dump_json()
    )
    rebound = _rebind(record, context, observed_invalidation_triggers=None)
    assert rebound.calibration_validity.observation_status == "unavailable"
    assert not evaluate_registry_gate(rebound).promotion_allowed
