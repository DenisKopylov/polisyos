"""Remove only the persisted-width integrity property for a pytest probe.

This plugin intentionally turns the B28 tampered-width negative control green.
The test's DID NOT RAISE failure, plus the counter below, witnesses that it
exercises the persisted-width property rather than only its error marker.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

import pytest

from polisyos.core.contracts.value_outer_set import (
    ValueOuterSet,
    _coerce_interval_values,
    _derive_interval_widths,
)


_TARGET_NODEID = (
    "tests/unit/runtime/quality/test_e02_candidate_occurrence_readback.py::"
    "test_latest_candidate_occurrence_survives_cas_replay_and_pre_n9_readback"
)
_ORIGINAL_LOADER = ValueOuterSet.from_persisted_payload
_STATE: dict[str, Any] = {
    "removed_width_rejections": 0,
    "invalid_width_inputs": [],
    "target_did_not_raise": False,
}
_MISSING = object()


def _would_width_gate_reject(payload: Mapping[str, Any]) -> bool:
    """Independently identify a missing, malformed, or non-derived checksum."""

    raw = payload.get("width", _MISSING)
    if raw is _MISSING or not isinstance(raw, (list, tuple)):
        return True
    items = tuple(raw)
    if any(isinstance(item, bool) for item in items):
        return True
    try:
        supplied = tuple(float(item) for item in items)
        if any(not math.isfinite(item) for item in supplied):
            return True
        expected = _derive_interval_widths(
            _coerce_interval_values(payload.get("lower")),
            _coerce_interval_values(payload.get("upper")),
        )
    except (TypeError, ValueError, OverflowError):
        return True
    return supplied != expected


def _without_persisted_width_gate(cls: type[ValueOuterSet], payload: object) -> ValueOuterSet:
    """Drop only width before ordinary strict model validation."""

    if not isinstance(payload, Mapping):
        return _ORIGINAL_LOADER(payload)  # type: ignore[arg-type]
    if _would_width_gate_reject(payload):
        _STATE["removed_width_rejections"] += 1
        _STATE["invalid_width_inputs"].append(payload.get("width", "<missing>"))
    model_payload = dict(payload)
    model_payload.pop("width", None)
    return cls.model_validate(model_payload)


def pytest_configure(config: pytest.Config) -> None:
    """Install the in-memory mutation before test collection."""

    del config
    ValueOuterSet.from_persisted_payload = classmethod(_without_persisted_width_gate)


def pytest_runtest_logreport(report: pytest.TestReport) -> None:
    """Record that the target negative control reached its expected mutation red."""

    if (
        report.nodeid == _TARGET_NODEID
        and report.when == "call"
        and report.failed
        and "DID NOT RAISE" in str(report.longrepr)
    ):
        _STATE["target_did_not_raise"] = True


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """Assert both the mutation counter and target negative control were hit."""

    removed = int(_STATE["removed_width_rejections"])
    did_not_raise = bool(_STATE["target_did_not_raise"])
    print(
        "\nWIDTH_PROPERTY_REMOVAL_PROBE "
        f"removed_width_rejections={removed} "
        f"target_did_not_raise={did_not_raise} "
        f"invalid_width_inputs={_STATE['invalid_width_inputs']!r}"
    )
    if removed < 1 or not did_not_raise:
        session.exitstatus = pytest.ExitCode.INTERNAL_ERROR
    else:
        session.exitstatus = exitstatus
