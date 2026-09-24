"""Execute the explicitly bounded GY builders integration denominator.

The supported Runtime composition-root import precedes collection. This runner
names every test file or node; it never discovers a test directory recursively.
"""

from __future__ import annotations

import importlib
import signal
import sys
import time
from pathlib import Path

TESTS = (
    "tests/unit/fabric/test_ceiling_relations.py",
    "tests/unit/fabric/test_non_data_acquisition.py",
    "tests/unit/runtime/quality/test_adaptation_transition.py",
    "tests/unit/runtime/quality/test_operator_comprehension.py",
    "tests/unit/lex/knowledge/test_multilingual_assurance.py",
    "tests/unit/lex/knowledge/test_locale_census.py",
    "tests/repo_quality/tools/test_locale_census_independent.py",
    "tests/repo_quality/tools/test_multilingual_locale_census.py",
    "tests/unit/runtime/http/test_control_plane_store.py::"
    "test_control_plane_store_tracks_worker_leases_and_outbox",
    "tests/unit/runtime/quality/test_acquisition_planner.py::"
    "test_non_overridable_gate_blocks_even_when_voi_prefers_proxy",
    "tests/unit/runtime/quality/test_acquisition_planner.py::"
    "test_acquisition_planner_report_persists_as_first_class_artifact",
    "tests/unit/runtime/quality/test_runtime_event_log.py",
    "tests/unit/runtime/quality/test_diagnostic_event_contract.py",
)


def _deadline_expired(_signum: int, _frame: object) -> None:
    raise TimeoutError("600-second gate budget exceeded; prior cold owners measured about 120s")


def main() -> int:
    """Run the named proof wave and retain its measured elapsed time."""
    started = time.monotonic()
    signal.signal(signal.SIGALRM, _deadline_expired)
    signal.alarm(600)
    sys.stdout.write("EXPLICIT TEST DENOMINATOR\n" + "\n".join(TESTS) + "\n")
    package_file = Path(importlib.import_module("polisyos").__file__).resolve()
    expected = Path(__file__).resolve().parents[5] / "src/polisyos/__init__.py"
    if package_file != expected:
        raise RuntimeError(f"wrong_source_checkout:{package_file}")
    sys.stdout.write(f"imported_package_file={package_file}; executable={sys.executable}\n")
    sys.stdout.flush()
    importlib.import_module("polisyos.runtime.http.services.control")
    import pytest

    code = pytest.main([*TESTS, "-o", "addopts=", "-q", "-s"])
    signal.alarm(0)
    sys.stdout.write(f"elapsed_seconds={time.monotonic() - started:.3f}; exit_code={code}\n")
    sys.stdout.flush()
    return int(code)


if __name__ == "__main__":
    raise SystemExit(main())
