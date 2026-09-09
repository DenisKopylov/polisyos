"""Run only the complete native GY-L node population, with identity readback."""

from __future__ import annotations

import ast
import argparse
import hashlib
import json
import re
from pathlib import Path

import pytest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--failed-from", type=Path)
    args = parser.parse_args()
    path = Path("tests/repo_quality/architecture/test_layer3_gy_artifact_lifecycle.py")
    raw = path.read_bytes()
    source = raw.decode("utf-8")
    parsed = [
        node.name for node in ast.parse(source).body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith("test_gy_l_")
    ]
    independent = re.findall(r"^def (test_gy_l_[A-Za-z0-9_]+)\(", source, re.M)
    assert parsed == independent
    assert len(parsed) == len(set(parsed)) and parsed
    nodes = [f"{path.as_posix()}::{name}" for name in parsed]
    if args.failed_from:
        receipt = json.loads(args.failed_from.read_text())
        previous = [json.loads(line.removeprefix("GY_L_NATIVE_READBACK "))
                    for line in receipt["stdout"].splitlines()
                    if line.startswith("GY_L_NATIVE_READBACK ")]
        assert len(previous) == 1
        failed = {row["nodeid"] for row in previous[0]["outcomes"] if row["outcome"] != "passed"}
        assert failed and failed <= set(previous[0]["collected"])
        nodes = [node for node in nodes if any(identity == node or identity.startswith(node + "[")
                                               for identity in failed)]
        assert {identity.split("[", 1)[0] for identity in failed} == set(nodes)
    collected = []
    outcomes = []

    class Recorder:
        def pytest_collection_finish(self, session):
            collected.extend(item.nodeid for item in session.items)

        def pytest_runtest_logreport(self, report):
            if report.when == "call" or report.failed or report.skipped:
                outcomes.append({"nodeid": report.nodeid, "when": report.when,
                                 "outcome": report.outcome})

    print("GY_L_NATIVE_POPULATION " + json.dumps({
        "source": path.as_posix(), "source_sha256": hashlib.sha256(raw).hexdigest(),
        "definition_denominator": len(parsed), "independent_denominator": len(independent),
        "nodes": nodes,
        "failed_from": str(args.failed_from) if args.failed_from else None,
    }, sort_keys=True))
    result = pytest.main(["-q", "-s", "-rA", "--show-capture=no", "--tb=short", *nodes],
                         plugins=[Recorder()])
    assert path.read_bytes() == raw, "native test source changed during wave"
    emitted = {row["nodeid"] for row in outcomes}
    assert emitted == set(collected), {"unreported": sorted(set(collected) - emitted),
                                      "uncollected": sorted(emitted - set(collected))}
    assert len(collected) == len(set(collected))
    print("GY_L_NATIVE_READBACK " + json.dumps({
        "collected": collected, "outcomes": outcomes,
        "collected_denominator": len(collected), "reported_denominator": len(emitted),
        "returncode": int(result),
    }, sort_keys=True))
    return int(result)


if __name__ == "__main__":
    raise SystemExit(main())
