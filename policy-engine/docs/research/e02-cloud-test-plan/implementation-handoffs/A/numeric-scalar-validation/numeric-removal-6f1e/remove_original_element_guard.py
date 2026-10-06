"""Pytest mutation plugin: disable the original-element validation guard.

Use only against a source candidate that defines
``_contains_invalid_original_numeric_element``. The plugin replaces that
helper with an unconditional False result while preserving the downstream
validator, consumer code, tests, and their markers.

To execute after review, put this directory on PYTHONPATH and pass
``-p remove_original_element_guard`` to pytest for the four numeric scalar
nodes. The process must fail the mixed-original-Boolean semantic assertions;
zero guard invocations or zero mixed-Boolean invocations make the harness fail
closed with exit code 2.
"""

from __future__ import annotations

import importlib
import json
import sys
from collections.abc import Mapping, Sequence
from typing import Protocol

import numpy as np

_TARGET_MODULE = "polisyos.runtime.quality.joint_simulation_horizon"


class _PytestConfig(Protocol):
    """Small config surface used by this standalone plugin."""

    _numeric_original_element_guard_removal_counts: dict[str, int] | None


class _PytestSession(Protocol):
    """Small session surface used by this standalone plugin."""

    config: _PytestConfig
    exitstatus: int


def _contains_original_boolean(value: object) -> bool:
    """Observe whether an input still contains a bool before NumPy coercion."""

    pending: list[object] = [value]
    visited: set[int] = set()
    while pending:
        item = pending.pop()
        if isinstance(item, (bool, np.bool_)):
            return True
        if isinstance(item, np.ndarray):
            identity = id(item)
            if identity not in visited:
                visited.add(identity)
                pending.extend(item.flat)
            continue
        if isinstance(item, Mapping):
            identity = id(item)
            if identity not in visited:
                visited.add(identity)
                pending.extend(item.values())
            continue
        if isinstance(item, Sequence) and not isinstance(item, (str, bytes, bytearray)):
            identity = id(item)
            if identity not in visited:
                visited.add(identity)
                pending.extend(item)
    return False


def pytest_configure(config: object) -> None:
    """Disable only the shared source-element guard and count target inputs."""

    module = importlib.import_module(_TARGET_MODULE)
    original_guard = getattr(module, "_contains_invalid_original_numeric_element", None)
    if not callable(original_guard):
        raise RuntimeError("source mutant unavailable: shared original-element guard missing")

    counters = {"guard_invocations": 0, "mixed_boolean_invocations": 0}

    def removed_guard(value: object) -> bool:
        counters["guard_invocations"] += 1
        if _contains_original_boolean(value):
            counters["mixed_boolean_invocations"] += 1
        return False

    module._contains_invalid_original_numeric_element = removed_guard
    config._numeric_original_element_guard_removal_counts = counters


def pytest_sessionfinish(session: object, exitstatus: int) -> None:
    """Emit mutation hit counts and reject a probe that never exercised them."""

    counters = session.config._numeric_original_element_guard_removal_counts
    if counters is None:
        sys.stdout.write("PROPERTY_REMOVAL_RECEIPT=" + json.dumps({"mutant_applied": False}) + "\n")
        session.exitstatus = 2
        return
    receipt = {
        "mutant_applied": True,
        "mutation": "_contains_invalid_original_numeric_element returns False",
        **counters,
        "pytest_exitstatus_before_harness_check": exitstatus,
    }
    sys.stdout.write("PROPERTY_REMOVAL_RECEIPT=" + json.dumps(receipt, sort_keys=True) + "\n")
    if counters["guard_invocations"] == 0 or counters["mixed_boolean_invocations"] == 0:
        sys.stdout.write(
            "PROPERTY_REMOVAL_HARNESS_ERROR=mutated guard saw no original Boolean case\n"
        )
        session.exitstatus = 2
