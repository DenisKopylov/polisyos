"""Independent actual DDM producer -> wire readers -> source rebind controls."""

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
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
    """Emit the existing CLI text and optionally flush without logging side effects."""
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
errors = list(old.iter_errors(payload))
origins = {
    n: str(Path(m.__file__).resolve())
    for n, m in sys.modules.items()
    if n.startswith("polisyos.") and getattr(m, "__file__", None)
}
if not (all(Path(p).is_relative_to(root) for p in origins.values())):
    raise AssertionError
_write_stdout(
    json.dumps(
        {
            "schema_errors": [{"validator": e.validator, "message": e.message} for e in errors],
            "actual_old_producer": payload,
            "module_origins": origins,
        },
        sort_keys=True,
    ),
    flush=True,
)
if errors:
    raise AssertionError("actual frozen producer violates authentic old strict-reader contract")
