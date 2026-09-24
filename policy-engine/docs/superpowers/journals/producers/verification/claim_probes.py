"""Run one unchanged Claim witness with an optional in-memory source-property removal.

Run from policy-engine with uv run python PATH --probe none|binding|caller|append.
Each mutant lives only in this interpreter; repository source bytes are untouched.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import inspect
import sys
import textwrap
import time
from pathlib import Path

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT))

INTEGRATION = "tests/integration/scientist/governance/test_claim_lifecycle_orchestration.py"
OWNER = "tests/unit/scientist/governance/continuous/test_owner_event_producer.py"
TARGETS = {
    "binding": OWNER
    + "::test_owner_event_verification_rejects_present_but_unproven_evidence[fake_successor]",
    "caller": INTEGRATION
    + "::test_default_http_supersession_request_preserves_unappointed_owner_limit",
    "append": INTEGRATION
    + "::test_monitor_event_persists_claim_supersession_without_in_place_edit",
}


def install(probe: str) -> tuple[Path, str]:
    from polisyos.scientist.evidence.claims import owner_events
    from polisyos.scientist.governance.continuous import lifecycle_bridge

    if probe == "caller":
        module = lifecycle_bridge
        owner = module.EpochClaimLifecycleBridgeService
        original = owner.bridge_monitor_event
    else:
        module = owner_events
        owner = module
        original = (
            module._validate_candidate_content
            if probe == "binding"
            else module.apply_claim_supersession_owner_event
        )
    path = Path(inspect.getsourcefile(original))
    source_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    tree = ast.parse(textwrap.dedent(inspect.getsource(original)))
    function = tree.body[0]
    changed = 0
    if probe == "binding":
        for node in ast.walk(function):
            if isinstance(node, ast.BoolOp):
                previous = node.values
                node.values = [
                    value
                    for value in previous
                    if ast.unparse(value) != "successor.claim_id != event.successor_claim_id"
                ]
                changed += len(previous) - len(node.values)
    elif probe == "caller":
        for node in ast.walk(function):
            if (
                isinstance(node, ast.If)
                and ast.unparse(node.test) == "request is not None and (not candidates)"
            ):
                # Keep discovery/persistence, removing only producer call and its result handling.
                node.body = node.body[-1:]
                changed += 1
    else:
        for node in ast.walk(function):
            if (
                isinstance(node, ast.Return)
                and isinstance(node.value, ast.Call)
                and ast.unparse(node.value.func) == "append_lifecycle_event"
            ):
                node.value = ast.Name(id="ledger", ctx=ast.Load())
                changed += 1
    if changed != 1:
        raise RuntimeError(f"Expected exactly one property removal, got {changed}")
    ast.fix_missing_locations(tree)
    namespace = dict(module.__dict__)
    # Execute only this checked local source AST in an isolated verification process.
    exec(compile(tree, str(path) + "::<isolated-removal>", "exec"), namespace)  # noqa: S102
    setattr(owner, original.__name__, namespace[original.__name__])
    _write(f"PROBE={probe} SOURCE={path} SOURCE_SHA256={source_hash}")
    return path, source_hash


def _write(message: str) -> None:
    sys.stdout.write(message + "\n")
    sys.stdout.flush()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--probe", choices=("none", "binding", "caller", "append"), required=True)
    parser.add_argument("--node")
    args = parser.parse_args()
    evidence = None if args.probe == "none" else install(args.probe)
    node = args.node or TARGETS.get(args.probe)
    if not node:
        parser.error("--node is required for an unmodified run")
    import pytest

    _write(f"UNCHANGED_NODE={node}")
    started = time.monotonic()
    result = int(pytest.main([node, "-q"]))
    if evidence is not None:
        path, original_hash = evidence
        if hashlib.sha256(path.read_bytes()).hexdigest() != original_hash:
            raise RuntimeError("Probe mutated repository source bytes")
        _write("SOURCE_BYTES_UNCHANGED=true")
    _write(f"EXIT={result} WALL_SECONDS={time.monotonic() - started:.3f}")
    return result


if __name__ == "__main__":
    raise SystemExit(main())
