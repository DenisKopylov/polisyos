"""Report the exact evidence difference from the actual Foundry consumer replay."""

from __future__ import annotations

import json
import sys

import pytest

from polisyos.core.canon import from_canonical_bytes
from polisyos.runtime.quality.workspace import scientist_node_adapters as adapter

original = adapter._read_binding
snapshots = {}
missing = object()


def differences(left, right, path=""):
    if isinstance(left, dict) and isinstance(right, dict):
        for key in sorted(set(left) | set(right)):
            yield from differences(left.get(key, missing), right.get(key, missing), path + "/" + key)
    elif isinstance(left, list) and isinstance(right, list):
        for index in range(max(len(left), len(right))):
            yield from differences(
                left[index] if index < len(left) else missing,
                right[index] if index < len(right) else missing,
                path + "/" + str(index),
            )
    elif type(left) is not type(right) or left != right:
        yield {"path": path, "left_present": left is not missing,
               "right_present": right is not missing,
               "left": None if left is missing else left,
               "right": None if right is missing else right}


def read_binding(store, ref, slot):
    result = original(store, ref, slot)
    if slot == "method_evidence":
        snapshots[slot] = result[1]
    if slot == "replay_evidence":
        before = from_canonical_bytes(snapshots["method_evidence"])
        after = from_canonical_bytes(result[1])
        delta = list(differences(before, after))
        print(json.dumps({"complete_evidence_field_delta": delta}, default=str), file=sys.stderr)
    return result


adapter._read_binding = read_binding
raise SystemExit(pytest.main([
    "-q", "-s", "--tb=short",
    "tests/unit/runtime/quality/test_workspace_foundry_consumption.py::"
    "test_foundry_consumer_replays_actual_method_owner_and_preserves_raw_byte_custody",
]))
