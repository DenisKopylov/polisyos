"""Fresh-process DDM contract, compatibility, and consumer witnesses.

All inputs are synthetic and diagnostic. This module does not establish real
calibration, authority, promotion, a deployed model, or historical-writer bytes.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator, FormatChecker
from pydantic import ValidationError

from polisyos.ddm.contracts.events import (
    MetricDirection,
    ShiftDetectedEvent,
    ShiftRiskEvent,
)

PROJECT_ROOT = Path(__file__).parents[3]
SOURCE_ROOT = PROJECT_ROOT / "src"
SCHEMA_PATH = SOURCE_ROOT / "polisyos/ddm/integration/shift_event.schema.json"
EVENT_PICKLE_RECORD_ENV = "POLISYOS_DDM_EVENT_PICKLE_RECORD_JSON"


_CHILD_COMMON = r"""
import hashlib
import json
import os
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(os.environ["POLISYOS_TEST_PROJECT_ROOT"]).resolve()
FIRST_PARTY_ROOTS = tuple(
    (PROJECT_ROOT / relative).resolve()
    for relative in ("src", "tests", "tools")
)
FIRST_PARTY_PREFIXES = ("polisyos", "tests", "tools")


def _is_first_party_name(name):
    return any(name == prefix or name.startswith(prefix + ".")
               for prefix in FIRST_PARTY_PREFIXES)


def _inside(path, root):
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _origin_snapshot():
    modules = {}
    foreign = []
    snapshot_errors = []
    for name, module in sorted(sys.modules.items()):
        raw_origin = getattr(module, "__file__", None)
        path_snapshot_error = None
        try:
            raw_locations = list(getattr(module, "__path__", ()) or ())
        except Exception as exc:
            raw_locations = []
            path_snapshot_error = {
                "type": type(exc).__name__,
                "message": str(exc),
            }
        origin = os.path.realpath(raw_origin) if raw_origin else None
        locations = sorted(os.path.realpath(item) for item in raw_locations)
        paths = ([origin] if origin else []) + locations
        has_first_party_origin = any(
            any(_inside(Path(path), root) for root in FIRST_PARTY_ROOTS)
            for path in paths
        )
        if not _is_first_party_name(name) and not has_first_party_origin:
            continue
        allowed = bool(paths) and all(
            any(_inside(Path(path), root) for root in FIRST_PARTY_ROOTS)
            for path in paths
        )
        source = None
        if origin and Path(origin).is_file():
            raw = Path(origin).read_bytes()
            source = {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
        modules[name] = {
            "origin": origin,
            "locations": locations,
            "source_bytes": source,
            "allowed_origin": allowed,
        }
        if path_snapshot_error is not None:
            modules[name]["origin_snapshot_error"] = path_snapshot_error
            snapshot_errors.append({"name": name, **path_snapshot_error})
        if not allowed and paths:
            foreign.append({"name": name, "origin": origin, "locations": locations})
        elif not allowed and path_snapshot_error is None:
            snapshot_errors.append({
                "name": name,
                "type": "missing-origin",
                "message": "first-party module has no file or package path",
            })
    return modules, foreign, snapshot_errors


def _base_record(before):
    modules, foreign, snapshot_errors = _origin_snapshot()
    return {
        "before_first_party_modules": before,
        "first_party_modules": modules,
        "foreign_first_party_origins": foreign,
        "first_party_origin_snapshot_errors": snapshot_errors,
        "first_party_roots": [str(path) for path in FIRST_PARTY_ROOTS],
        "pid": os.getpid(),
        "ppid": os.getppid(),
        "observed_at_ns": time.time_ns(),
        "executable": os.path.realpath(sys.executable),
        "dont_write_bytecode": sys.flags.dont_write_bytecode,
        "pycache_prefix": sys.pycache_prefix,
        "argv": list(sys.argv),
        "sys_path": list(sys.path),
        "env_profile": {
            key: os.environ.get(key)
            for key in (
                "PATH",
                "HOME",
                "TMPDIR",
                "TEMP",
                "LANG",
                "LC_ALL",
                "LC_CTYPE",
                "PYTHONPATH",
                "POLISYOS_TEST_PROJECT_ROOT",
                "PYTHONHASHSEED",
                "PYTHONUTF8",
                "PYTHONIOENCODING",
                "PYTHONDONTWRITEBYTECODE",
            )
        },
        "env_key_names": sorted(os.environ),
    }
"""


_IMPORT_CHILD = (
    _CHILD_COMMON
    + r"""
import importlib
import importlib.abc
import traceback

before = sorted(name for name in sys.modules if _is_first_party_name(name))
forbidden_prefixes = (
    "polisyos.ddm.integration.monitor",
    "polisyos.ddm.integration.incident",
    "polisyos.ddm.integration.model_registry",
)
attempts = []


class LiveImportTrap(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if any(
            fullname == prefix or fullname.startswith(prefix + ".")
            for prefix in forbidden_prefixes
        ):
            attempts.append(fullname)
            raise RuntimeError("LIVE_DDM_IMPORT_TRAP:" + fullname)
        return None


sys.meta_path.insert(0, LiveImportTrap())
mode, target = sys.argv[1:3]
report = {"mode": mode, "target": target, "attempts": attempts, "error": None}

try:
    if mode == "neutral":
        module = importlib.import_module(target)
        if target.endswith(".events"):
            value = module.ShiftDetectedEvent.model_validate({
                "event_type": "ml.track_2_2.shift_detected.v1",
                "event_id": "neutral-child-event",
                "timestamp": "2026-04-26T00:00:00Z",
                "model_id": "synthetic-model",
                "model_version": "v7",
                "detector_id": "synthetic-detector",
                "detector_family": "online_mmd",
                "signal": "input_shift",
                "representation": "feature_embedding_v2",
                "reference_window": {
                    "start": "2026-04-01T00:00:00Z",
                    "end": "2026-04-02T00:00:00Z",
                    "n": 100,
                },
                "current_window": {
                    "start": "2026-04-03T00:00:00Z",
                    "end": "2026-04-04T00:00:00Z",
                    "n": 100,
                },
                "stationarity_regime_id": "SR-synthetic-neutral",
                "calibration_id": "synthetic-diagnostic-only",
                "test_statistic": 0.2,
                "p_value": 0.05,
                "empirical_fp_rate": 0.001,
                "shift_severity": 0.44,
                "diagnostic_only": True,
            })
            report["contract"] = {
                "type_module": type(value).__module__,
                "type_qualname": type(value).__qualname__,
                "event_type": value.event_type,
                "fields_set": sorted(value.model_fields_set),
                "wire": value.model_dump(mode="json", by_alias=True),
                "diagnostic_only": value.diagnostic_only,
            }
        else:
            events = importlib.import_module("polisyos.ddm.contracts.events")
            policy = module.MetricBudgetPolicy(
                model_id="neutral-budget-model",
                model_version="v7",
                metric="synthetic-f1",
                metric_direction=events.MetricDirection.HIGHER_IS_BETTER,
                reference_value=0.913,
                minimum_acceptable_value=0.742,
            )
            report["contract"] = {
                "type_module": type(policy).__module__,
                "type_qualname": type(policy).__qualname__,
                "direction": policy.metric_direction.value,
                "full_wire": policy.model_dump(mode="json", by_alias=True),
                "explicit_wire": policy.model_dump(
                    mode="json", by_alias=True, exclude_unset=True
                ),
                "fields_set": sorted(policy.model_fields_set),
            }
        forbidden_loaded = sorted(
            name for name in sys.modules
            if any(
                name == prefix or name.startswith(prefix + ".")
                for prefix in forbidden_prefixes
            )
        )
        report["forbidden_loaded"] = forbidden_loaded
        report["outcome"] = "neutral-child-used-real-value"
    elif mode == "monitor-trap":
        try:
            importlib.import_module(target)
        except RuntimeError as exc:
            if not str(exc).startswith("LIVE_DDM_IMPORT_TRAP:"):
                raise
            report["outcome"] = "live-trap-fired"
            report["trapped_name"] = str(exc).partition(":")[2]
        else:
            report["outcome"] = "live-trap-missed"
    else:
        raise ValueError("unsupported import probe mode")
except BaseException as exc:
    report["outcome"] = "probe-error"
    report["error"] = {
        "type": type(exc).__name__,
        "message": str(exc),
        "traceback": traceback.format_exc(),
    }

report.update(_base_record(before))
report["attempts"] = attempts
print(json.dumps(report, sort_keys=True, separators=(",", ":")))
"""
)


_MONITOR_CHILD = (
    _CHILD_COMMON
    + r"""
import traceback
from datetime import UTC, datetime

before = sorted(name for name in sys.modules if _is_first_party_name(name))
report = {"outcome": None, "error": None}

try:
    from polisyos.ddm import DriftAndDegradationMonitor

    monitor = DriftAndDegradationMonitor()
    timestamp = datetime(2026, 4, 26, tzinfo=UTC)
    baseline = monitor.evaluate_window(
        model_id="synthetic-model",
        model_version="v7",
        shift_events=[],
        timestamp=timestamp,
    )
    event = {
        "event_type": "ml.track_2_2.shift_detected.v1",
        "event_id": "synthetic-monitor-shift",
        "timestamp": "2026-04-26T00:00:00Z",
        "model_id": "synthetic-model",
        "model_version": "v7",
        "detector_id": "synthetic-detector",
        "detector_family": "online_mmd",
        "signal": "input_shift",
        "representation": "feature_embedding_v2",
        "reference_window": {
            "start": "2026-04-01T00:00:00Z",
            "end": "2026-04-02T00:00:00Z",
            "n": 100,
        },
        "current_window": {
            "start": "2026-04-03T00:00:00Z",
            "end": "2026-04-04T00:00:00Z",
            "n": 100,
        },
        "stationarity_regime_id": "SR-synthetic-monitor",
        "calibration_id": "synthetic-diagnostic-only",
        "test_statistic": 0.2,
        "p_value": 0.05,
        "empirical_fp_rate": 0.001,
        "shift_severity": 0.44,
        "diagnostic_only": True,
    }
    observed = monitor.evaluate_window(
        model_id="synthetic-model",
        model_version="v7",
        shift_events=[event],
        timestamp=timestamp,
    )
    report["outcome"] = "monitor-called-and-returned"
    report["consumer"] = {
        "monitor_module": DriftAndDegradationMonitor.__module__,
        "baseline_readiness": {
            "state": baseline.readiness_event.readiness_state.value,
            "score": baseline.readiness_event.readiness_score,
            "active_signals": baseline.readiness_event.active_signals,
        },
        "observed_shift": [
            {
                "event_type": risk.event_type,
                "shift_event_id": risk.shift_event_id,
                "evidence_kind": risk.evidence_kind,
                "risk_score": risk.risk_score,
                "risk_level": risk.risk_level,
                "diagnostic_only": risk.diagnostic_only,
            }
            for risk in observed.shift_risk_events
        ],
        "observed_readiness": {
            "state": observed.readiness_event.readiness_state.value,
            "score": observed.readiness_event.readiness_score,
            "active_signals": observed.readiness_event.active_signals,
        },
        "root_cause_shift_ids": observed.root_cause_bundle.shift_event_ids,
        "incident_model_id": observed.incident_payload.model_id,
        "registry_record_is_none": observed.registry_record is None,
    }
except BaseException as exc:
    report["outcome"] = "monitor-probe-error"
    report["error"] = {
        "type": type(exc).__name__,
        "message": str(exc),
        "traceback": traceback.format_exc(),
    }

report.update(_base_record(before))
print(json.dumps(report, sort_keys=True, separators=(",", ":")))
"""
)


_PICKLE_WRITER = (
    _CHILD_COMMON
    + r"""
import base64
import importlib
import json
import pickle
import traceback

before = sorted(name for name in sys.modules if _is_first_party_name(name))
kind = sys.argv[1]
payload = json.loads(sys.argv[2])
report = {"kind": kind, "error": None}

try:
    if kind == "event":
        from polisyos.ddm.contracts.events import ShiftDetectedEvent

        value = ShiftDetectedEvent.model_validate(payload)
        legacy_name = "polisyos.ddm.integration.events"
    elif kind == "budget":
        from polisyos.ddm.contracts.events import MetricDirection
        from polisyos.ddm.contracts.metric_budget import MetricBudgetPolicy

        payload["metric_direction"] = MetricDirection(payload["metric_direction"])
        value = MetricBudgetPolicy.model_validate(payload)
        legacy_name = "polisyos.ddm.readiness.readiness_mapper"
    else:
        raise ValueError("unknown pickle model kind")

    owner = type(value)
    legacy_module = importlib.import_module(legacy_name)
    if getattr(legacy_module, owner.__name__) is not owner:
        raise AssertionError("legacy module does not export canonical type")
    original_module = owner.__module__
    try:
        owner.__module__ = legacy_name
        raw = pickle.dumps(value, protocol=pickle.HIGHEST_PROTOCOL)
    finally:
        owner.__module__ = original_module
    report.update({
        "outcome": "synthetic-legacy-global-written",
        "legacy_global": legacy_name + "." + owner.__name__,
        "canonical_module_after_restore": owner.__module__,
        "writer_values": value.model_dump(mode="json", by_alias=True),
        "writer_explicit_values": value.model_dump(
            mode="json", by_alias=True, exclude_unset=True
        ),
        "fields_set": sorted(value.model_fields_set),
        "pickle_bytes_base64": base64.b64encode(raw).decode("ascii"),
        "pickle_bytes": len(raw),
        "pickle_sha256": hashlib.sha256(raw).hexdigest(),
    })
except BaseException as exc:
    report["outcome"] = "writer-error"
    report["error"] = {
        "type": type(exc).__name__,
        "message": str(exc),
        "traceback": traceback.format_exc(),
    }

report.update(_base_record(before))
print(json.dumps(report, sort_keys=True, separators=(",", ":")))
"""
)


_PICKLE_READER = (
    _CHILD_COMMON
    + r"""
import base64
import io
import json
import pickle
import traceback

before = sorted(name for name in sys.modules if _is_first_party_name(name))
kind, raw_b64, expected_json = sys.argv[1:4]
expected = json.loads(expected_json)
raw = base64.b64decode(raw_b64, validate=True)
seen_globals = []
report = {
    "kind": kind,
    "error": None,
    "input_pickle_bytes": len(raw),
    "input_pickle_sha256": hashlib.sha256(raw).hexdigest(),
    "seen_globals": seen_globals,
}

class TracingUnpickler(pickle.Unpickler):
    def find_class(self, module, name):
        seen_globals.append(module + "." + name)
        return super().find_class(module, name)


try:
    loaded = TracingUnpickler(io.BytesIO(raw)).load()
    if kind == "event":
        from polisyos.ddm.contracts.events import ShiftDetectedEvent as Canonical

        enum_identity = None
    elif kind == "budget":
        from polisyos.ddm.contracts.events import MetricDirection
        from polisyos.ddm.contracts.metric_budget import MetricBudgetPolicy as Canonical

        enum_identity = loaded.metric_direction is MetricDirection.HIGHER_IS_BETTER
    else:
        raise ValueError("unknown pickle model kind")
    if type(loaded) is not Canonical:
        raise AssertionError("cold reader did not resolve the canonical class object")
    full = loaded.model_dump(mode="json", by_alias=True)
    explicit = loaded.model_dump(mode="json", by_alias=True, exclude_unset=True)
    actual_fields = sorted(Canonical.model_fields)
    actual_fields_set = sorted(loaded.model_fields_set)
    if actual_fields != expected["all_fields"]:
        raise AssertionError("canonical field set differs from independent expected oracle")
    if actual_fields_set != expected["fields_set"]:
        raise AssertionError("field set differs from independent expected oracle")
    if full != expected["full"]:
        raise AssertionError("full JSON wire projection differs from independent oracle")
    if explicit != expected["explicit"]:
        raise AssertionError("explicit JSON wire projection differs from independent oracle")
    if kind == "budget" and enum_identity is not True:
        raise AssertionError("cold budget enum is not the canonical enum member")
    report.update({
        "outcome": "cold-reader-resolved-and-matched-independent-oracle",
        "class_module": Canonical.__module__,
        "class_qualname": Canonical.__qualname__,
        "all_model_fields": actual_fields,
        "fields_set": actual_fields_set,
        "full_wire": full,
        "explicit_wire": explicit,
        "enum_identity_is_canonical": enum_identity,
    })
except BaseException as exc:
    report["outcome"] = "reader-error"
    report["error"] = {
        "type": type(exc).__name__,
        "message": str(exc),
        "traceback": traceback.format_exc(),
    }

report.update(_base_record(before))
print(json.dumps(report, sort_keys=True, separators=(",", ":")))
"""
)


def _run_fresh(label: str, script: str, *arguments: str) -> dict[str, Any]:
    """Run one controlled child and emit both streams before caller assertions."""

    env = {
        key: os.environ[key]
        for key in ("PATH", "HOME", "TMPDIR", "TEMP", "LANG", "LC_ALL", "LC_CTYPE")
        if key in os.environ
    }
    for key in ("PYTHONHASHSEED", "PYTHONUTF8", "PYTHONIOENCODING"):
        if key in os.environ:
            env[key] = os.environ[key]
    env["PYTHONPATH"] = str(SOURCE_ROOT)
    env["POLISYOS_TEST_PROJECT_ROOT"] = str(PROJECT_ROOT)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    with tempfile.TemporaryDirectory(prefix="ddm-cold-pycache-") as cache_prefix:
        cache_path = Path(cache_prefix)
        cache_initial_entries = sorted(path.name for path in cache_path.iterdir())
        command = [
            sys.executable,
            "-B",
            "-X",
            f"pycache_prefix={cache_prefix}",
            "-c",
            script,
            *arguments,
        ]
        process = subprocess.Popen(
            command,
            cwd=PROJECT_ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        stdout_bytes, stderr_bytes = process.communicate()
        cache_final_entries = sorted(path.name for path in cache_path.iterdir())
    record = {
        "label": label,
        "argv": command,
        "cwd": str(PROJECT_ROOT),
        "parent_pid": os.getpid(),
        "pid_from_parent": process.pid,
        "returncode": process.returncode,
        "pycache_prefix": cache_prefix,
        "cache_initial_entries": cache_initial_entries,
        "cache_final_entries": cache_final_entries,
        "env_profile": {
            key: env.get(key)
            for key in (
                "PATH",
                "HOME",
                "TMPDIR",
                "TEMP",
                "LANG",
                "LC_ALL",
                "LC_CTYPE",
                "PYTHONPATH",
                "POLISYOS_TEST_PROJECT_ROOT",
                "PYTHONHASHSEED",
                "PYTHONUTF8",
                "PYTHONIOENCODING",
                "PYTHONDONTWRITEBYTECODE",
            )
        },
        "env_key_names": sorted(env),
        "stdout_base64": base64.b64encode(stdout_bytes).decode("ascii"),
        "stderr_base64": base64.b64encode(stderr_bytes).decode("ascii"),
        "stdout_utf8": stdout_bytes.decode("utf-8", errors="replace"),
        "stderr_utf8": stderr_bytes.decode("utf-8", errors="replace"),
    }
    print(
        "DDM_COMPLETE_CHILD " + json.dumps(record, sort_keys=True, separators=(",", ":")),
        flush=True,
    )
    return {
        "label": label,
        "parent_pid": os.getpid(),
        "pid_from_parent": process.pid,
        "returncode": process.returncode,
        "pycache_prefix": cache_prefix,
        "cache_initial_entries": cache_initial_entries,
        "cache_final_entries": cache_final_entries,
        "stdout": stdout_bytes.decode("utf-8", errors="replace"),
        "stderr": stderr_bytes.decode("utf-8", errors="replace"),
        "stdout_base64": record["stdout_base64"],
        "stderr_base64": record["stderr_base64"],
    }


def _child_observation(child: dict[str, Any]) -> dict[str, Any]:
    """Parse the child's sole JSON observation after its complete streams were emitted."""

    assert child["returncode"] == 0, (
        f"{child['label']} exit={child['returncode']}; "
        f"stdout={child['stdout']!r}; stderr={child['stderr']!r}"
    )
    observation = json.loads(child["stdout"])
    assert observation["ppid"] == child["parent_pid"]
    assert child["pid_from_parent"] == observation["pid"]
    assert child["cache_initial_entries"] == []
    assert child["cache_final_entries"] == []
    assert observation["pycache_prefix"] == child["pycache_prefix"]
    return observation


def _assert_local_origins(observation: dict[str, Any]) -> None:
    """Reject first-party imports resolving outside this checkout's source roots."""

    assert observation["foreign_first_party_origins"] == []
    assert observation["first_party_origin_snapshot_errors"] == []
    roots = [Path(path).resolve() for path in observation["first_party_roots"]]
    for details in observation["first_party_modules"].values():
        locations = list(details["locations"])
        if details["origin"]:
            locations.append(details["origin"])
        assert details["allowed_origin"] is True
        assert all(
            any(Path(location).resolve().is_relative_to(root) for root in roots)
            for location in locations
        )
        if details["source_bytes"] is not None:
            assert details["source_bytes"]["bytes"] > 0
            assert len(details["source_bytes"]["sha256"]) == 64


def _shift_payload(channel: str = "p_value") -> dict[str, Any]:
    """Return one explicitly synthetic and diagnostic-only shift wire value."""

    payload: dict[str, Any] = {
        "event_type": "ml.track_2_2.shift_detected.v1",
        "event_id": "synthetic-shift-1",
        "timestamp": "2026-04-26T00:00:00Z",
        "model_id": "synthetic-model",
        "model_version": "v7",
        "detector_id": "synthetic-detector",
        "detector_family": "online_mmd",
        "signal": "input_shift",
        "representation": "feature_embedding_v2",
        "reference_window": {
            "start": "2026-04-01T00:00:00Z",
            "end": "2026-04-02T00:00:00Z",
            "n": 100,
        },
        "current_window": {
            "start": "2026-04-03T00:00:00Z",
            "end": "2026-04-04T00:00:00Z",
            "n": 90,
        },
        "stationarity_regime_id": "SR-synthetic-v7",
        "calibration_id": "synthetic-diagnostic-only",
        "test_statistic": 0.2,
        "empirical_fp_rate": 0.001,
        "shift_severity": 0.44,
        "diagnostic_only": True,
    }
    channels = {
        "p_value": 0.05,
        "e_value": 3.0,
        "ert": 10_000.0,
    }
    if channel != "none":
        payload[channel] = channels[channel]
    return payload


@pytest.mark.parametrize(
    "target",
    [
        "polisyos.ddm.contracts.events",
        "polisyos.ddm.contracts.metric_budget",
        "polisyos.ddm.integration.events",
    ],
)
def test_neutral_contract_entrypoints_are_independent_cold_processes(target: str) -> None:
    """Each neutral entrypoint is imported and used first in its own child."""

    child = _run_fresh("neutral:" + target, _IMPORT_CHILD, "neutral", target)
    observation = _child_observation(child)

    assert child["pid_from_parent"] == observation["pid"]
    assert observation["before_first_party_modules"] == []
    assert observation["error"] is None
    assert observation["outcome"] == "neutral-child-used-real-value"
    assert observation["attempts"] == []
    assert observation["forbidden_loaded"] == []
    assert observation["dont_write_bytecode"] == 1
    assert observation["pid"] != observation["ppid"]
    _assert_local_origins(observation)
    if target.endswith(".events"):
        assert observation["contract"]["type_module"] == "polisyos.ddm.contracts.events"
        assert observation["contract"]["wire"]["event_type"] == ("ml.track_2_2.shift_detected.v1")
        assert observation["contract"]["diagnostic_only"] is True
    else:
        assert observation["contract"]["direction"] == "higher_is_better"
        assert observation["contract"]["full_wire"]["reference_value"] == 0.913
        assert observation["contract"]["explicit_wire"]["minimum_acceptable_value"] == 0.742
        assert observation["contract"]["fields_set"]


def test_same_live_trap_catches_actual_monitor_import_in_a_fresh_process() -> None:
    """The same finder reaches the real monitor import rather than a test marker."""

    target = "polisyos.ddm.integration.monitor"
    child = _run_fresh("live-monitor-trap", _IMPORT_CHILD, "monitor-trap", target)
    observation = _child_observation(child)

    assert observation["before_first_party_modules"] == []
    assert observation["error"] is None
    assert observation["outcome"] == "live-trap-fired"
    assert observation["attempts"] == [target]
    assert observation["trapped_name"] == target
    _assert_local_origins(observation)


def test_untrapped_fresh_public_monitor_runs_real_numeric_consumer() -> None:
    """The public monitor returns a typed risk while diagnostic evidence stays nonbinding."""

    child = _run_fresh("untrapped-monitor-consumer", _MONITOR_CHILD)
    observation = _child_observation(child)

    assert observation["before_first_party_modules"] == []
    assert observation["error"] is None
    assert observation["outcome"] == "monitor-called-and-returned"
    assert observation["dont_write_bytecode"] == 1
    assert observation["pid"] != observation["ppid"]
    _assert_local_origins(observation)
    consumer = observation["consumer"]
    assert consumer["monitor_module"] == "polisyos.ddm.integration.monitor"
    assert consumer["baseline_readiness"]["state"] == "R4"
    assert consumer["baseline_readiness"]["score"] == 100
    assert consumer["observed_shift"] == [
        {
            "event_type": "ml.problem_15_7.shift_risk.v1",
            "shift_event_id": "synthetic-monitor-shift",
            "evidence_kind": "p_value",
            "risk_score": 0.44,
            "risk_level": "watch",
            "diagnostic_only": True,
        }
    ]
    assert consumer["observed_readiness"] == {
        "state": "R4",
        "score": 100,
        "active_signals": [],
    }
    assert consumer["root_cause_shift_ids"] == ["synthetic-monitor-shift"]
    assert consumer["incident_model_id"] == "synthetic-model"
    assert consumer["registry_record_is_none"] is True


_EVENT_PICKLE_INPUT = {
    "event_type": "ml.track_2_2.shift_detected.v1",
    "event_id": "synthetic-pickle-event-47",
    "timestamp": "2026-04-26T00:00:00Z",
    "model_id": "pickle-model-17",
    "model_version": "v17",
    "detector_id": "pickle-detector",
    "detector_family": "online_mmd",
    "signal": "feature_shift",
    "representation": "feature_embedding_v3",
    "reference_window": {
        "start": "2026-04-01T00:00:00Z",
        "end": "2026-04-02T00:00:00Z",
        "n": 177,
    },
    "current_window": {
        "start": "2026-04-03T00:00:00Z",
        "end": "2026-04-04T00:00:00Z",
        "n": 154,
    },
    "stationarity_regime_id": "SR-pickle-17",
    "calibration_id": "synthetic-pickle-diagnostic",
    "test_statistic": 0.275,
    "p_value": 0.037,
    "threshold": 0.011,
    "empirical_fp_rate": 0.002,
    "shift_severity": 0.63,
    "affected_features": [{"feature": "income", "score": 0.71, "direction": "increase"}],
    "affected_slices": [{"slice": "north", "score": 0.58}],
    "diagnostic_only": True,
}

_EVENT_EXPECTED_EXPLICIT = {
    "event_type": "ml.track_2_2.shift_detected.v1",
    "event_id": "synthetic-pickle-event-47",
    "timestamp": "2026-04-26T00:00:00Z",
    "model_id": "pickle-model-17",
    "model_version": "v17",
    "detector_id": "pickle-detector",
    "detector_family": "online_mmd",
    "signal": "feature_shift",
    "representation": "feature_embedding_v3",
    "reference_window": {
        "start": "2026-04-01T00:00:00Z",
        "end": "2026-04-02T00:00:00Z",
        "n": 177,
    },
    "current_window": {
        "start": "2026-04-03T00:00:00Z",
        "end": "2026-04-04T00:00:00Z",
        "n": 154,
    },
    "stationarity_regime_id": "SR-pickle-17",
    "calibration_id": "synthetic-pickle-diagnostic",
    "test_statistic": 0.275,
    "p_value": 0.037,
    "threshold": 0.011,
    "empirical_fp_rate": 0.002,
    "shift_severity": 0.63,
    "affected_features": [{"feature": "income", "score": 0.71, "direction": "increase"}],
    "affected_slices": [{"slice": "north", "score": 0.58}],
    "diagnostic_only": True,
}

_EVENT_EXPECTED_FULL = {
    "event_type": "ml.track_2_2.shift_detected.v1",
    "event_id": "synthetic-pickle-event-47",
    "timestamp": "2026-04-26T00:00:00Z",
    "model_id": "pickle-model-17",
    "model_version": "v17",
    "detector_id": "pickle-detector",
    "detector_family": "online_mmd",
    "signal": "feature_shift",
    "representation": "feature_embedding_v3",
    "reference_window": {
        "start": "2026-04-01T00:00:00Z",
        "end": "2026-04-02T00:00:00Z",
        "n": 177,
    },
    "current_window": {
        "start": "2026-04-03T00:00:00Z",
        "end": "2026-04-04T00:00:00Z",
        "n": 154,
    },
    "stationarity_regime_id": "SR-pickle-17",
    "calibration_id": "synthetic-pickle-diagnostic",
    "test_statistic": 0.275,
    "p_value": 0.037,
    "e_value": None,
    "ert": None,
    "threshold": 0.011,
    "empirical_fp_rate": 0.002,
    "shift_severity": 0.63,
    "affected_features": [{"feature": "income", "score": 0.71, "direction": "increase"}],
    "affected_slices": [{"slice": "north", "score": 0.58}],
    "diagnostic_only": True,
}

_BUDGET_PICKLE_INPUT = {
    "model_id": "synthetic-budget-model-83",
    "model_version": "release-17",
    "metric": "macro_f1",
    "metric_direction": "higher_is_better",
    "reference_value": 0.913,
    "minimum_acceptable_value": 0.742,
}

_BUDGET_EXPECTED_EXPLICIT = {
    "model_id": "synthetic-budget-model-83",
    "model_version": "release-17",
    "metric": "macro_f1",
    "metric_direction": "higher_is_better",
    "reference_value": 0.913,
    "minimum_acceptable_value": 0.742,
}

_BUDGET_EXPECTED_FULL = {
    "model_id": "synthetic-budget-model-83",
    "model_version": "release-17",
    "metric": "macro_f1",
    "metric_direction": "higher_is_better",
    "reference_value": 0.913,
    "minimum_acceptable_value": 0.742,
    "maximum_acceptable_value": None,
}

_PICKLE_ORACLES = {
    "event": {
        "all_fields": sorted(_EVENT_EXPECTED_FULL),
        "fields_set": sorted(_EVENT_EXPECTED_EXPLICIT),
        "full": _EVENT_EXPECTED_FULL,
        "explicit": _EVENT_EXPECTED_EXPLICIT,
    },
    "budget": {
        "all_fields": sorted(_BUDGET_EXPECTED_FULL),
        "fields_set": sorted(_BUDGET_EXPECTED_EXPLICIT),
        "full": _BUDGET_EXPECTED_FULL,
        "explicit": _BUDGET_EXPECTED_EXPLICIT,
    },
}

_LEGACY_GLOBALS = {
    "event": "polisyos.ddm.integration.events.ShiftDetectedEvent",
    "budget": "polisyos.ddm.readiness.readiness_mapper.MetricBudgetPolicy",
}


@pytest.mark.parametrize("kind", ["event", "budget"], ids=("event", "budget"))
def test_synthetic_legacy_pickle_resolves_in_distinct_cold_reader(kind: str) -> None:
    """Synthetic old-FQN bytes resolve in a new process against an independent full oracle."""

    if kind == "event":
        payload = deepcopy(_EVENT_PICKLE_INPUT)
        oracle = _PICKLE_ORACLES[kind]
        legacy_global = _LEGACY_GLOBALS[kind]
        supplied_record = os.environ.get(EVENT_PICKLE_RECORD_ENV)
    else:
        payload = deepcopy(_BUDGET_PICKLE_INPUT)
        oracle = _PICKLE_ORACLES[kind]
        legacy_global = _LEGACY_GLOBALS[kind]
        supplied_record = None

    writer_record: dict[str, Any]
    baseline_writer_executed = supplied_record is None
    if supplied_record is None:
        writer = _run_fresh(
            "synthetic-" + kind + "-legacy-writer",
            _PICKLE_WRITER,
            kind,
            json.dumps(payload, sort_keys=True),
        )
        writer_observation = _child_observation(writer)
        assert writer_observation["error"] is None
        assert writer_observation["outcome"] == "synthetic-legacy-global-written"
        writer_record = writer_observation
    else:
        writer_record = json.loads(supplied_record)
        print(
            "DDM_REUSED_BASELINE_WRITER_RECORD "
            + json.dumps(writer_record, sort_keys=True, separators=(",", ":")),
            flush=True,
        )

    assert writer_record["legacy_global"] == legacy_global
    raw_b64 = writer_record["pickle_bytes_base64"]
    raw = base64.b64decode(raw_b64, validate=True)
    assert len(raw) == writer_record["pickle_bytes"]
    assert hashlib.sha256(raw).hexdigest() == writer_record["pickle_sha256"]

    reader = _run_fresh(
        "synthetic-" + kind + "-cold-legacy-reader",
        _PICKLE_READER,
        kind,
        raw_b64,
        json.dumps(oracle, sort_keys=True),
    )
    reader_observation = _child_observation(reader)

    assert reader_observation["error"] is None
    assert reader_observation["outcome"] == "cold-reader-resolved-and-matched-independent-oracle"
    assert reader_observation["before_first_party_modules"] == []
    assert reader_observation["dont_write_bytecode"] == 1
    assert reader_observation["input_pickle_sha256"] == writer_record["pickle_sha256"]
    assert reader_observation["input_pickle_bytes"] == writer_record["pickle_bytes"]
    assert legacy_global in reader_observation["seen_globals"]
    assert reader_observation["all_model_fields"] == oracle["all_fields"]
    assert reader_observation["fields_set"] == oracle["fields_set"]
    assert reader_observation["full_wire"] == oracle["full"]
    assert reader_observation["explicit_wire"] == oracle["explicit"]
    assert reader_observation["pid"] != os.getpid()
    if baseline_writer_executed:
        assert reader_observation["pid"] != writer_record["pid"]
    if kind == "budget":
        assert reader_observation["enum_identity_is_canonical"] is True
    _assert_local_origins(reader_observation)


def test_manual_schema_and_real_adapter_enforce_channel_guard() -> None:
    """All three evidence channels work; missing and null-only evidence fail both boundaries."""

    from polisyos.ddm.detectors.track_2_2_shift_adapter import adapt_shift_event

    raw_schema = SCHEMA_PATH.read_bytes()
    print(
        "DDM_SCHEMA_INPUT "
        + json.dumps(
            {
                "path": str(SCHEMA_PATH),
                "bytes": len(raw_schema),
                "sha256": hashlib.sha256(raw_schema).hexdigest(),
            },
            sort_keys=True,
            separators=(",", ":"),
        ),
        flush=True,
    )
    schema = json.loads(raw_schema)
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())

    for channel, expected_kind in (
        ("p_value", "p_value"),
        ("e_value", "e_value"),
        ("ert", "ert"),
    ):
        payload = _shift_payload(channel)
        assert validator.is_valid(payload), f"manual schema rejected valid {channel} input"
        risk = adapt_shift_event(payload)
        assert type(risk) is ShiftRiskEvent
        assert risk.shift_event_id == payload["event_id"]
        assert risk.evidence_kind == expected_kind
        assert risk.risk_score == 0.44
        assert risk.risk_level == "watch"
        assert risk.diagnostic_only is True

    missing = _shift_payload("none")
    all_null = {**missing, "p_value": None, "e_value": None, "ert": None}
    for payload in (missing, all_null):
        assert payload["empirical_fp_rate"] == 0.001
        assert not validator.is_valid(payload), "manual schema accepted absent evidence"
        with pytest.raises(ValidationError, match="p_value, e_value, or ert"):
            adapt_shift_event(payload)


def test_manual_schema_and_model_reject_malformed_inputs_at_their_boundaries() -> None:
    """Wire-only checks and model cross-field checks are tested independently."""

    from polisyos.ddm.detectors.track_2_2_shift_adapter import adapt_shift_event

    raw_schema = SCHEMA_PATH.read_bytes()
    print(
        "DDM_SCHEMA_INPUT "
        + json.dumps(
            {
                "path": str(SCHEMA_PATH),
                "bytes": len(raw_schema),
                "sha256": hashlib.sha256(raw_schema).hexdigest(),
            },
            sort_keys=True,
            separators=(",", ":"),
        ),
        flush=True,
    )
    schema = json.loads(raw_schema)
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    valid = _shift_payload("ert")

    malformed: list[dict[str, Any]] = []
    bad_date = deepcopy(valid)
    bad_date["timestamp"] = "not-a-date-time"
    malformed.append(bad_date)
    foreign = deepcopy(valid)
    foreign["unrecognized"] = True
    malformed.append(foreign)
    out_of_range = deepcopy(valid)
    out_of_range["ert"] = -1.0
    malformed.append(out_of_range)
    invalid_rate = deepcopy(valid)
    invalid_rate["empirical_fp_rate"] = 1.1
    malformed.append(invalid_rate)
    missing_rate = deepcopy(valid)
    del missing_rate["empirical_fp_rate"]
    malformed.append(missing_rate)

    for payload in malformed:
        assert not validator.is_valid(payload)
        with pytest.raises(ValidationError):
            adapt_shift_event(payload)

    reversed_window = deepcopy(valid)
    reversed_window["current_window"]["start"] = "2026-04-05T00:00:00Z"
    assert validator.is_valid(reversed_window)
    with pytest.raises(ValidationError, match="window end must not be before start"):
        adapt_shift_event(reversed_window)

    model_default_wire_fields = deepcopy(valid)
    del model_default_wire_fields["event_type"]
    del model_default_wire_fields["diagnostic_only"]
    assert not validator.is_valid(model_default_wire_fields)
    event = ShiftDetectedEvent.model_validate(model_default_wire_fields)
    assert event.event_type == "ml.track_2_2.shift_detected.v1"
    assert event.diagnostic_only is False
    assert {"event_type", "diagnostic_only"}.isdisjoint(event.model_fields_set)


def test_metric_budget_owner_keeps_directional_boundaries() -> None:
    """The canonical budget owner still requires its direction-specific bound."""

    from polisyos.ddm.contracts.metric_budget import MetricBudgetPolicy

    higher = MetricBudgetPolicy(
        model_id="synthetic-budget-model",
        model_version="v7",
        metric="macro_f1",
        metric_direction=MetricDirection.HIGHER_IS_BETTER,
        reference_value=0.913,
        minimum_acceptable_value=0.742,
    )
    assert higher.minimum_acceptable_value == 0.742
    with pytest.raises(ValidationError, match="requires minimum_acceptable_value"):
        MetricBudgetPolicy(
            model_id="synthetic-budget-model",
            model_version="v7",
            metric="macro_f1",
            metric_direction=MetricDirection.HIGHER_IS_BETTER,
            reference_value=0.913,
        )
    with pytest.raises(ValidationError, match="reference_value must be above"):
        MetricBudgetPolicy(
            model_id="synthetic-budget-model",
            model_version="v7",
            metric="macro_f1",
            metric_direction=MetricDirection.HIGHER_IS_BETTER,
            reference_value=0.742,
            minimum_acceptable_value=0.742,
        )

    lower = MetricBudgetPolicy(
        model_id="synthetic-budget-model",
        model_version="v7",
        metric="loss",
        metric_direction=MetricDirection.LOWER_IS_BETTER,
        reference_value=0.087,
        maximum_acceptable_value=0.258,
    )
    assert lower.maximum_acceptable_value == 0.258
    with pytest.raises(ValidationError, match="requires maximum_acceptable_value"):
        MetricBudgetPolicy(
            model_id="synthetic-budget-model",
            model_version="v7",
            metric="loss",
            metric_direction=MetricDirection.LOWER_IS_BETTER,
            reference_value=0.087,
        )
    with pytest.raises(ValidationError, match="reference_value must be below"):
        MetricBudgetPolicy(
            model_id="synthetic-budget-model",
            model_version="v7",
            metric="loss",
            metric_direction=MetricDirection.LOWER_IS_BETTER,
            reference_value=0.258,
            maximum_acceptable_value=0.258,
        )


def test_forwarded_contract_identity_and_calibration_audit_wire_alias() -> None:
    """Supported facades preserve one owner and a synthetic nonpassing audit's alias."""

    import polisyos.ddm as root
    from polisyos.ddm.contracts import events as canonical
    from polisyos.ddm.integration import events as integration

    excluded = {
        "DDMWindowResult",
        "DriftAndDegradationMonitor",
        "ModelRegistryReadinessRecord",
        "RegistryGateDecision",
    }
    for surface in (root, integration):
        for name in surface.__all__:
            if hasattr(canonical, name) and name not in excluded:
                assert getattr(surface, name) is getattr(canonical, name)

    audit_wire = {
        "model_id": "synthetic-model",
        "model_version": "v7",
        "calibration_id": "synthetic-diagnostic-calibration",
        "detector_id": "synthetic-detector",
        "stationarity_regime_id": "SR-synthetic-audit",
        "horizon": "synthetic-horizon",
        "alpha": 0.05,
        "ert": 1_000.0,
        "empirical_fp_rate": 0.001,
        "empirical_fp_upper_95": 0.004,
        "pass": False,
    }
    audit = integration.CalibrationAudit.model_validate(audit_wire)
    assert audit.pass_ is False
    assert audit.model_dump(mode="json", by_alias=True) == audit_wire
    assert integration.CalibrationAudit is canonical.CalibrationAudit
    assert integration.CalibrationAudit.__module__ == "polisyos.ddm.contracts.events"
