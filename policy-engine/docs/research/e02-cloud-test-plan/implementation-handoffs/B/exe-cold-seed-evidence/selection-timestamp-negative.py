"""Reproduce the prior test's CAS identity error across a real UTC second."""
import hashlib
import json
import os
import runpy
import subprocess
import tempfile
import time
from pathlib import Path

from pytest import MonkeyPatch

from polisyos.scientist.nodes.builtins.causal import resolve_parameters

source_root = Path(os.environ["E02_SELECTION_SOURCE_ROOT"])
fixture = source_root / "policy-engine/tests/unit/scientist/methods/causal/test_resolve_parameters_node.py"
tests = runpy.run_path(str(fixture))
original = resolve_parameters.ParameterSelector
calls = 0


def delayed_selector(*args, **kwargs):
    global calls
    calls += 1
    if calls == 2:
        time.sleep(1.01)
    return original(*args, **kwargs)


with tempfile.TemporaryDirectory(prefix="e02-selection-identity-") as directory:
    root = Path(directory)
    with MonkeyPatch.context() as patch:
        patch.setattr(resolve_parameters, "ParameterSelector", delayed_selector)
        try:
            tests["test_matching_source_unbound_bundle_reselects_configured_source"](root, patch)
        except AssertionError:
            failed = True
        else:
            failed = False
    bundles = []
    for blob in (root / "cas/artifacts").rglob("*.blob"):
        try:
            data = json.loads(blob.read_bytes())
        except (ValueError, UnicodeDecodeError):
            continue
        if isinstance(data, dict) and "selection_timestamp" in data:
            bundles.append(dict(artifact_id="sha256:" + hashlib.sha256(blob.read_bytes()).hexdigest(), payload=data))
    bundles.sort(key=lambda b: b["payload"]["selection_timestamp"])
    assert failed and calls == 2 and len(bundles) == 2
    first, second = (dict(bundle["payload"]) for bundle in bundles)
    first_time = first.pop("selection_timestamp")
    second_time = second.pop("selection_timestamp")
    assert first == second and first_time != second_time
    print(json.dumps(dict(
        source_sha=subprocess.check_output(["git", "-C", str(source_root), "rev-parse", "HEAD"], text=True).strip(),
        fixture=str(fixture), fixture_sha256=hashlib.sha256(fixture.read_bytes()).hexdigest(),
        original_assertion_failed=failed, actual_selector_calls=calls,
        full_actual_payloads=bundles, only_payload_difference="selection_timestamp",
        input="same real temporary SKG v12/graph/context; pause1.01s before second real selector construction; no source edit",
    ), indent=2))
