from __future__ import annotations

import os
import pickle
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "module_name",
    [
        "polisyos.ddm.contracts.events",
        "polisyos.ddm.contracts.metric_budget",
        "polisyos.ddm.integration.events",
    ],
)
def test_contract_only_import_does_not_load_ddm_orchestration(
    module_name: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A neutral contract import must not enter DDM orchestration imports."""

    project_root = Path(__file__).parents[3]
    # A linked editable venv can point to another checkout. Bind the child to
    # this worktree even when its inherited PYTHONPATH names a foreign source.
    foreign_source = tmp_path / "foreign-source"
    foreign_package = foreign_source / "polisyos"
    foreign_package.mkdir(parents=True)
    (foreign_package / "__init__.py").write_text(
        'raise AssertionError("foreign editable source entered")\n'
    )
    monkeypatch.setenv("PYTHONPATH", str(foreign_source))
    source_root = project_root / "src"
    probe = """
import importlib
import importlib.abc
import sys
from pathlib import Path

blocked = {
    "polisyos.ddm.integration.incident",
    "polisyos.ddm.integration.model_registry",
    "polisyos.ddm.integration.monitor",
}
class OrchestrationTrap(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname in blocked:
            raise AssertionError(f"contract import entered orchestration: {fullname}")

sys.meta_path.insert(0, OrchestrationTrap())
imported = importlib.import_module(sys.argv[1])
contracts = importlib.import_module("polisyos.ddm.contracts.events")
expected_source = Path(sys.argv[2]).resolve()
assert Path(imported.__file__).resolve().is_relative_to(expected_source)
assert Path(contracts.__file__).resolve().is_relative_to(expected_source)
assert not blocked.intersection(sys.modules)
integration = importlib.import_module("polisyos.ddm.integration")
assert integration.MonitoringWindow is contracts.MonitoringWindow
assert integration.ShiftDetectedEvent is contracts.ShiftDetectedEvent
assert not blocked.intersection(sys.modules)
# The trap must intercept importlib too, not only builtins.__import__.
try:
    importlib.import_module("polisyos.ddm.integration.monitor")
except AssertionError as exc:
    assert "contract import entered orchestration" in str(exc)
else:
    raise AssertionError("orchestration trap did not intercept its negative control")
print("contract-only")
"""
    result = subprocess.run(
        [sys.executable, "-c", probe, module_name, str(source_root)],
        cwd=project_root,
        env={**os.environ, "PYTHONPATH": str(source_root)},
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

    contract_names = {
        name
        for name, value in vars(canonical).items()
        if isinstance(value, type) and value.__module__ == canonical.__name__
    }
    assert set(legacy.__all__) == contract_names

    for name in contract_names:
        owner = getattr(canonical, name)
        assert getattr(legacy, name) is owner
        assert getattr(integration, name) is owner
        if name in ddm.__all__:
            assert getattr(ddm, name) is owner

    assert ddm.DriftAndDegradationMonitor.__module__.startswith("polisyos.ddm.")


def test_contract_class_references_preserve_legacy_pickle_resolution() -> None:
    """Persisted old module references resolve to the sole current owner."""

    from polisyos.ddm.contracts import events as canonical
    from polisyos.ddm.contracts.metric_budget import MetricBudgetPolicy
    from polisyos.ddm.integration import events as legacy

    for name in legacy.__all__:
        owner = getattr(canonical, name)
        assert pickle.loads(pickle.dumps(owner)) is owner  # noqa: S301 - trusted class fixture
        # Protocol 0 GLOBAL reproduces a persisted pre-relocation class FQN.
        old_reference = f"cpolisyos.ddm.integration.events\n{name}\n.".encode("ascii")
        assert pickle.loads(old_reference) is owner  # noqa: S301 - trusted class fixture

    assert (
        pickle.loads(pickle.dumps(MetricBudgetPolicy))  # noqa: S301 - trusted class fixture
        is MetricBudgetPolicy
    )
    assert (
        pickle.loads(  # noqa: S301 - trusted pre-relocation class fixture
            b"cpolisyos.ddm.readiness.readiness_mapper\nMetricBudgetPolicy\n."
        )
        is MetricBudgetPolicy
    )


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
