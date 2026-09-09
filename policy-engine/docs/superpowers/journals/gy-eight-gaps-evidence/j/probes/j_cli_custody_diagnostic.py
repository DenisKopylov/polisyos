"""Run the one unchanged J regression with source custody and periodic stacks."""

from __future__ import annotations

import faulthandler
import hashlib
import importlib
import json
from pathlib import Path

NODE = (
    "tests/unit/runtime/quality/workspace/test_production_case_proof_custody.py::"
    "test_full_recorded_gx_is_replayed_and_failed_marker_cannot_disappear"
)
LOG = Path("_build/gy-gaps/j/cli-custody-correction-diagnostic-stacks.txt")


def main() -> int:
    root = Path.cwd()
    if not (root / "architecture/generated_artifacts.toml").is_file():
        raise ValueError("run_from_product_root")
    native = importlib.import_module(
        "docs.superpowers.journals.gy-eight-gaps-evidence.j.probes.j_native_wave"
    )
    before = native.source_fence()
    helper = Path(__file__)
    helper_hash = hashlib.sha256(helper.read_bytes()).hexdigest()
    with LOG.open("x", encoding="utf-8") as diagnostic:
        faulthandler.dump_traceback_later(180, repeat=True, file=diagnostic)
        outcomes = []
        collected = []

        class Recorder:
            def pytest_collection_finish(self, session):
                collected.extend(item.nodeid for item in session.items)
                if collected != [NODE]:
                    raise ValueError("selected_identity_changed")

            def pytest_runtest_logreport(self, report):
                row = {"nodeid": report.nodeid, "when": report.when, "outcome": report.outcome}
                outcomes.append(row)
                diagnostic.write("GY_J_CLI_TEST_PHASE " + json.dumps(row, sort_keys=True) + "\n")
                diagnostic.flush()

        try:
            import pytest

            result = int(pytest.main(
                ["-q", "-s", "-rA", "--show-capture=no", "--tb=short",
                 "-p", "no:faulthandler", NODE],
                plugins=[Recorder()],
            ))
        finally:
            faulthandler.cancel_dump_traceback_later()
    after = native.source_fence()
    frozen = before == after and hashlib.sha256(helper.read_bytes()).hexdigest() == helper_hash
    complete = collected == [NODE] and {row["when"] for row in outcomes} == {"setup", "call", "teardown"}
    final = result if frozen and complete else 2
    print("GY_J_CLI_DIAGNOSTIC_READBACK " + json.dumps({
        "collected": collected, "outcomes": outcomes,
        "complete_identity_readback": complete, "source_frozen": frozen,
        "source_before": native.fence_summary(before),
        "source_after": native.fence_summary(after),
        "executing_helper_sha256": helper_hash,
        "native_fence_helper_sha256": hashlib.sha256(Path(native.__file__).read_bytes()).hexdigest(),
        "diagnostic_log": LOG.as_posix(),
        "diagnostic_log_sha256": hashlib.sha256(LOG.read_bytes()).hexdigest(),
        "pytest_returncode": result, "returncode": final,
    }, sort_keys=True), flush=True)
    return final


if __name__ == "__main__":
    raise SystemExit(main())
