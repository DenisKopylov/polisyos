from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest


def test_contract_only_import_does_not_load_ddm_orchestration() -> None:
    """A neutral contract import must not enter DDM orchestration imports."""

    project_root = Path(__file__).parents[3]
    probe = """
import builtins
import importlib
import sys

blocked = {
    "polisyos.ddm.integration.incident",
    "polisyos.ddm.integration.model_registry",
    "polisyos.ddm.integration.monitor",
}
real_import = builtins.__import__

def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
    if name in blocked:
        raise AssertionError(f"contract import entered orchestration: {name}")
    return real_import(name, globals, locals, fromlist, level)

builtins.__import__ = guarded_import
contracts = importlib.import_module("polisyos.ddm.contracts.events")
assert not blocked.intersection(sys.modules)
integration = importlib.import_module("polisyos.ddm.integration")
assert integration.MonitoringWindow is contracts.MonitoringWindow
assert integration.ShiftDetectedEvent is contracts.ShiftDetectedEvent
assert not blocked.intersection(sys.modules)
print("contract-only")
"""
    result = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    assert result.stdout.strip().endswith("contract-only")


def test_root_and_integration_facades_forward_one_event_contract_owner() -> None:
    """Legacy and public facades must expose the same event model objects."""

    import polisyos.ddm as ddm
    import polisyos.ddm.integration as integration
    from polisyos.ddm.contracts import events as canonical
    from polisyos.ddm.integration import events as legacy

    contract_names = (
        "AffectedFeature",
        "AffectedSlice",
        "CalibrationAudit",
        "DataQualitySignal",
        "IncidentPayload",
        "MetricDirection",
        "MonitoringWindow",
        "PerformanceDegradationEvent",
        "ReadinessState",
        "ReadinessStateEvent",
        "RootCauseBundle",
        "ShiftDetectedEvent",
        "ShiftRiskEvent",
    )

    for name in contract_names:
        owner = getattr(canonical, name)
        assert getattr(legacy, name) is owner
        assert getattr(integration, name) is owner
        assert getattr(ddm, name) is owner

    assert ddm.DriftAndDegradationMonitor.__module__.startswith("polisyos.ddm.")


def test_event_contract_preserves_validators_and_json_aliases() -> None:
    """Moved event models retain cross-field guards and wire aliases."""

    from datetime import UTC, datetime

    from polisyos.ddm.contracts.events import CalibrationAudit, MonitoringWindow

    with pytest.raises(ValueError, match="window end must not be before start"):
        MonitoringWindow(
            start=datetime(2026, 4, 2, tzinfo=UTC),
            end=datetime(2026, 4, 1, tzinfo=UTC),
            n=1,
        )

    audit = CalibrationAudit.model_validate(
        {
            "calibration_id": "calib-1",
            "detector_id": "detector-1",
            "stationarity_regime_id": "SR-1",
            "horizon": "30d",
            "alpha": 0.05,
            "ert": 10000,
            "empirical_fp_rate": 0.001,
            "empirical_fp_upper_95": 0.01,
            "pass": True,
        }
    )

    assert audit.pass_ is True
    assert audit.model_dump(mode="json", by_alias=True)["pass"] is True


def test_ddm_facade_imports_canonical_package() -> None:
    import polisyos.ddm as ddm

    assert ddm.DriftAndDegradationMonitor.__module__.startswith("polisyos.ddm.")
    assert "DriftAndDegradationMonitor" in ddm.__all__
