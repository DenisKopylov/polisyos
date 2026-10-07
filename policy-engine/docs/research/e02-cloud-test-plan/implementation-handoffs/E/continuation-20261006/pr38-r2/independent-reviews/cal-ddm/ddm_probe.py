"Independent actual DDM producer -> wire readers -> source rebind controls."

import copy
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
from pydantic import ValidationError

from polisyos.ddm.calibration.audit import build_calibration_audit
from polisyos.ddm.calibration.calibrate import (
    FpTarget,
    Period,
    StationarityRegime,
    calibrate_detector,
)
from polisyos.ddm.contracts.events import MetricDirection, PerformanceDegradationEvent
from polisyos.ddm.contracts.metric_budget import MetricBudgetPolicy
from polisyos.ddm.integration import model_registry as mr
from polisyos.ddm.integration import monitor as monitor_module


def _write_stdout(*values: object, flush: bool = False) -> None:
    "Emit the existing CLI text and optionally flush without logging side effects."
    sys.stdout.write(" ".join(str(value) for value in values) + "\n")
    if flush:
        sys.stdout.flush()


mode = sys.argv[1]
root = Path(sys.argv[2]).resolve()
if not (Path(mr.__file__).resolve().is_relative_to(root)):
    raise AssertionError
if mode == "quantity_guard_removed":
    mr._degradation_budget_binding_reason = lambda *_: None
if mode == "source_guard_removed":
    mr._registry_source_block_reason = lambda *_: None

now = datetime(2026, 4, 20, 12, tzinfo=UTC)
model = "independent-review-model"
version = "revision-7"
regime = StationarityRegime(
    id="independent-regime",
    model_id=model,
    model_version=version,
    reference_period=Period(start=now - timedelta(days=30), end=now - timedelta(days=20)),
    calibration_period=Period(start=now - timedelta(days=20), end=now - timedelta(days=10)),
    holdout_stationary_period=Period(start=now - timedelta(days=10), end=now),
    invalidation_triggers=["model_version_change"],
)
report = calibrate_detector(
    detector_id="independent-detector",
    stationarity_regime=regime,
    fp_target=FpTarget(horizon="30d", alpha=0.05),
    calibration_streams=[[0.15, 0.3, 0.45] for _ in range(100)],
    holdout_streams=[[0.005, 0.01, 0.015] for _ in range(100)],
    seed=23,
)
audit = build_calibration_audit(calibration_id="independent-calibration", report=report)
budget = MetricBudgetPolicy(
    model_id=model,
    model_version=version,
    metric="latency_ms",
    metric_direction=MetricDirection.LOWER_IS_BETTER,
    reference_value=100,
    maximum_acceptable_value=120,
)


def event(**changes: object) -> object:
    fields = {
        "event_id": "independent-degradation",
        "timestamp": now,
        "model_id": model,
        "model_version": version,
        "metric": "latency_ms",
        "metric_direction": MetricDirection.LOWER_IS_BETTER,
        "source": "realized_performance",
        "estimator": "independent-latency-estimate",
        "reference_value": 100,
        "maximum_acceptable_value": 120,
        "current_estimate": 101,
        "confidence_interval_95": (100, 104),
        "budget_used": 0.2,
        "calibration_id": "independent-calibration",
    }
    fields.update(changes)
    return PerformanceDegradationEvent(**fields)


def produce(degradation: object = None, **changes: object) -> object:
    fields = {
        "model_id": model,
        "model_version": version,
        "metric_budget": budget,
        "calibration_audit": audit,
        "_calibration_report": report,
        "_observed_invalidation_triggers": [],
        "timestamp": now,
        "degradation_event": degradation,
    }
    fields.update(changes)
    return monitor_module.DriftAndDegradationMonitor().evaluate_window(**fields)


result = produce(event())
record = result.registry_record
if not (record is not None):
    raise AssertionError
payload = record.model_dump(mode="json")
old = Draft202012Validator(
    json.loads((Path(__file__).parent / "authentic-v1.schema.json").read_text()),
    format_checker=FormatChecker(),
)
new = Draft202012Validator(
    json.loads((root / "polisyos/ddm/integration/model_registry_record.schema.json").read_text()),
    format_checker=FormatChecker(),
)
if not (old.schema["$id"] != new.schema["$id"]):
    raise AssertionError
if not (payload["schema_version"] == "2"):
    raise AssertionError
if not (result.degradation_event.budget_used == (104 - 100) / (120 - 100) == 0.2):
    raise AssertionError
old_errors = list(old.iter_errors(payload))
if not (len(old_errors) == 1 and old_errors[0].validator == "additionalProperties"):
    raise AssertionError
new.validate(payload)
path = Path(__file__).parent / "independent-v2-record.json"
path.write_text(json.dumps(payload, indent=2) + "\n")
fresh = mr.ModelRegistryReadinessRecord.model_validate_json(path.read_text())
if mr.evaluate_registry_gate(fresh).promotion_allowed:
    raise AssertionError


def rebind(record: object, **changes: object) -> object:
    fields = {
        "report": report,
        "calibration_audit": audit,
        "now": now,
        "observed_invalidation_triggers": [],
        "metric_budget": budget,
        "readiness_event": result.readiness_event,
        "shift_events": result.shift_risk_events,
        "last_degradation_event": result.degradation_event,
    }
    fields.update(changes)
    return mr.rebind_calibration_validity(record, **fields)


if not (mr.evaluate_registry_gate(rebind(fresh)).promotion_allowed):
    raise AssertionError
checks = [
    "actual_producer_v2_to_authentic_old_reader_rejected",
    "fresh_v2_candidate_requires_rebind",
    "exact_source_rebind_positive",
    "independent_lower_better_budget_0.2",
]

if mode in ("native", "source_guard_removed"):
    forged = copy.deepcopy(payload)
    forged["source_binding_digest"] = "a" * 64
    new.validate(forged)
    decision = mr.evaluate_registry_gate(
        rebind(mr.ModelRegistryReadinessRecord.model_validate_json(json.dumps(forged)))
    )
    _write_stdout(
        json.dumps({"control": "forged_digest", "decision": decision.model_dump(mode="json")}),
        flush=True,
    )
    if not (
        not decision.promotion_allowed
        and decision.reason == "registry_source_binding_not_established"
    ):
        raise AssertionError(decision)
    checks.append("well_typed_forged_digest_refused")
if mode in ("native", "quantity_guard_removed"):
    try:
        produce(event(budget_used=0.0))
        refusal = None
    except ValueError as exc:
        refusal = str(exc)
    _write_stdout(
        json.dumps(
            {"control": "validshape_false_budget_marker", "refusal": refusal, "oracle": 0.2}
        ),
        flush=True,
    )
    if not (refusal is not None and "budget_used_mismatch" in refusal):
        raise AssertionError(refusal)
    checks.append("well_typed_forged_budget_marker_refused")

if mode == "native":
    legacy = copy.deepcopy(payload)
    for key in [
        "schema_version",
        "readiness_event_id",
        "readiness_effective_at",
        "readiness_expires_at",
        "source_binding_digest",
    ]:
        legacy.pop(key)
    old.validate(legacy)
    historical = mr.ModelRegistryReadinessRecord.model_validate_json(json.dumps(legacy))
    if not (historical.schema_version == "1" and historical.model_dump(mode="json") == legacy):
        raise AssertionError
    if mr.evaluate_registry_gate(rebind(historical)).promotion_allowed:
        raise AssertionError
    try:
        mr.ModelRegistryReadinessRecord.migrate_unversioned_source_record(legacy)
        raise AssertionError("legacy upgraded without source rebuild")
    except ValueError as exc:
        if "explicit rebuild" not in str(exc):
            raise AssertionError from None
    prerelease = copy.deepcopy(payload)
    prerelease.pop("schema_version")
    original = copy.deepcopy(prerelease)
    try:
        mr.ModelRegistryReadinessRecord.model_validate(prerelease)
        raise AssertionError("enriched unversioned implicitly admitted")
    except ValidationError:
        pass
    migrated = mr.ModelRegistryReadinessRecord.migrate_unversioned_source_record(prerelease)
    if not (
        prerelease == original
        and migrated.schema_version == "2"
        and not mr.evaluate_registry_gate(migrated).promotion_allowed
    ):
        raise AssertionError
    if not (mr.evaluate_registry_gate(rebind(migrated)).promotion_allowed):
        raise AssertionError
    veto = copy.deepcopy(payload)
    veto["promotion_allowed"] = False
    rebound = rebind(mr.ModelRegistryReadinessRecord.model_validate(veto))
    for signoff in [False, True]:
        decision = mr.evaluate_registry_gate(rebound, owner_signoff=signoff)
        if not (not decision.promotion_allowed and decision.reason == "persisted_readiness_veto"):
            raise AssertionError
    for version in [True, 2, "unknown", None]:
        invalid = copy.deepcopy(payload)
        invalid["schema_version"] = version
        try:
            mr.ModelRegistryReadinessRecord.model_validate(invalid)
            raise AssertionError("invalid version admitted")
        except ValidationError:
            pass
        if not (list(new.iter_errors(invalid))):
            raise AssertionError
    unavailable = rebind(fresh, observed_invalidation_triggers=None)
    if not (
        unavailable.calibration_validity.observation_status == "unavailable"
        and not mr.evaluate_registry_gate(unavailable).promotion_allowed
    ):
        raise AssertionError
    invalidated = rebind(fresh, observed_invalidation_triggers=["model_version_change"])
    if mr.evaluate_registry_gate(invalidated).promotion_allowed:
        raise AssertionError
    expired = rebind(fresh, now=now + timedelta(days=365))
    if mr.evaluate_registry_gate(expired).promotion_allowed:
        raise AssertionError
    late = rebind(fresh, now=now + timedelta(days=8))
    if mr.evaluate_registry_gate(late).promotion_allowed:
        raise AssertionError
    if not (mr.evaluate_registry_gate(late).reason == "readiness_expired"):
        raise AssertionError
    checks.extend(
        [
            "old_record_new_reader_preserves_wire_non_gating",
            "unversioned_enriched_requires_explicit_migration",
            "migration_no_mutation_no_authority",
            "fresh_rebind_persisted_veto_with_and_without_signoff",
            "unknown_typed_version_refused",
            "unavailable_feed_refused",
            "invalidation_refused",
            "calibration_expiry_refused",
            "readiness_ttl_not_renewed",
        ]
    )
origins = {
    n: str(Path(m.__file__).resolve())
    for n, m in sys.modules.items()
    if n.startswith("polisyos.") and getattr(m, "__file__", None)
}
if not (all(Path(p).is_relative_to(root) for p in origins.values())):
    raise AssertionError(origins)
_write_stdout(
    json.dumps(
        {
            "mode": mode,
            "checks": checks,
            "module_origins": origins,
            "actual_record": payload,
            "institutional_authority": (
                "not_established: explicit synthetic observed[] and no human signoff receipt"
            ),
            "inputs": {
                "seed": 23,
                "calibration_streams": "100 repetitions [.15,.3,.45]",
                "holdout_streams": "100 repetitions [.005,.01,.015]",
                "now": now.isoformat(),
                "budget": budget.model_dump(mode="json"),
            },
        },
        sort_keys=True,
    ),
    flush=True,
)
