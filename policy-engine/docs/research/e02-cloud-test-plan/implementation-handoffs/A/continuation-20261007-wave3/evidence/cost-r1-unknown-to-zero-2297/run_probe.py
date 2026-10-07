"""Run the ignored R1 unknown-cost-to-zero removal falsifier.

This harness is prepared but intentionally unexecuted. The target test's normal
assertion is expected to fail only after the first simulated variant has
produced positive token usage with unknown cost and the second queued variant
has actually completed under the removed guard.
"""

from __future__ import annotations

import ast
import json
import math
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

import pytest

if TYPE_CHECKING:
    from collections.abc import Generator

TARGET_TEST = "test_nl_pipeline_simulated_multimodel_honors_run_budget_guard_without_network"
TARGET_NODE_SUFFIX = f"test_nl_pipeline_materialization.py::{TARGET_TEST}"
EXPECTED_ASSERTION = 'assert variants[1]["status"] == "skipped_budget_guard"'


class HookOutcome(Protocol):
    """Minimal hook-wrapper result interface used by pytest."""

    def get_result(self) -> pytest.TestReport: ...


class UnknownCostToZeroRemovalProbe:
    """Remove only the fail-closed unknown-cost branch and classify its witness."""

    def __init__(self, test_file: Path, result_file: Path) -> None:
        self.test_file = test_file
        self.result_file = result_file
        self.original_advance: Any = None
        self.pipeline_module: Any = None
        self.expected_line = self._expected_assertion_line()
        self.counters: dict[str, Any] = {
            "target_collected": 0,
            "mutation_installed": 0,
            "first_completed_observed": 0,
            "first_positive_tokens_observed": 0,
            "first_unknown_cost_observed": 0,
            "second_completed_observed": 0,
            "expected_guard_assertion_observed": 0,
            "unexpected_target_failures": 0,
            "unexpected_target_passes": 0,
            "pytest_exit_code": None,
            "probe_status": "not_run",
        }

    def _expected_assertion_line(self) -> int:
        tree = ast.parse(self.test_file.read_text(encoding="utf-8"))
        target = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == TARGET_TEST
        )
        lines = self.test_file.read_text(encoding="utf-8").splitlines()
        return next(
            node.lineno
            for node in ast.walk(target)
            if isinstance(node, ast.Assert)
            and lines[node.lineno - 1].strip() == EXPECTED_ASSERTION
        )

    def pytest_runtest_call(self, item: pytest.Item) -> None:
        if not item.nodeid.endswith(TARGET_NODE_SUFFIX):
            return
        self.counters["target_collected"] += 1
        from polisyos.runtime.http.services.control import nl_pipeline

        self.pipeline_module = nl_pipeline
        self.original_advance = nl_pipeline._advance_run_budget

        def unknown_cost_is_zero(
            *, spent: float, budget: float | None, variant: dict[str, Any]
        ) -> tuple[float, bool]:
            if budget is None:
                return spent, False
            amount = nl_pipeline._budget_cost_amount(variant)
            if (
                amount is None
                and variant.get("cost_usd") is None
                and variant.get("cost_status") == "missing"
                and variant.get("cost_origin") == "unknown"
            ):
                amount = 0.0
            if amount is None:
                return spent, True
            updated = spent + amount
            if not math.isfinite(updated):
                return spent, True
            return updated, updated >= budget

        nl_pipeline._advance_run_budget = unknown_cost_is_zero
        self.counters["mutation_installed"] += 1

    def pytest_runtest_teardown(self, item: pytest.Item) -> None:
        if item.nodeid.endswith(TARGET_NODE_SUFFIX) and self.original_advance is not None:
            self.pipeline_module._advance_run_budget = self.original_advance
            self.original_advance = None

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_makereport(
        self, item: pytest.Item, call: pytest.CallInfo[None]
    ) -> Generator[HookOutcome]:
        outcome = yield
        report = outcome.get_result()
        if not item.nodeid.endswith(TARGET_NODE_SUFFIX) or report.when != "call":
            return
        if not report.failed or call.excinfo is None:
            self.counters["unexpected_target_passes"] += 1
            return

        tb = call.excinfo.value.__traceback__
        target_locals: dict[str, Any] | None = None
        target_line: int | None = None
        target_file = self.test_file.resolve()
        while tb is not None:
            frame = tb.tb_frame
            try:
                frame_path = Path(frame.f_code.co_filename).resolve()
            except OSError:
                frame_path = Path(frame.f_code.co_filename)
            if frame_path == target_file and frame.f_code.co_name == TARGET_TEST:
                target_locals = frame.f_locals
                target_line = tb.tb_lineno
            tb = tb.tb_next

        variants = target_locals.get("variants") if target_locals is not None else None
        if isinstance(variants, list) and len(variants) >= 2:
            first, second = variants[0], variants[1]
            if isinstance(first, dict) and first.get("status") == "completed":
                self.counters["first_completed_observed"] += 1
            if (
                isinstance(first, dict)
                and int(first.get("prompt_tokens") or 0) > 0
                and int(first.get("completion_tokens") or 0) > 0
            ):
                self.counters["first_positive_tokens_observed"] += 1
            if (
                isinstance(first, dict)
                and first.get("cost_usd") is None
                and first.get("cost_status") == "missing"
                and first.get("cost_origin") == "unknown"
            ):
                self.counters["first_unknown_cost_observed"] += 1
            if isinstance(second, dict) and second.get("status") == "completed":
                self.counters["second_completed_observed"] += 1

        witness_complete = all(
            self.counters[key] == 1
            for key in (
                "target_collected",
                "mutation_installed",
                "first_completed_observed",
                "first_positive_tokens_observed",
                "first_unknown_cost_observed",
                "second_completed_observed",
            )
        )
        if witness_complete and target_line == self.expected_line:
            self.counters["expected_guard_assertion_observed"] += 1
            report.outcome = "skipped"
            report.wasxfail = (
                "R1 removal falsified: unknown spend became zero and the queued variant started"
            )
            report.longrepr = report.wasxfail
            return

        self.counters["unexpected_target_failures"] += 1

    def pytest_sessionfinish(self, session: pytest.Session, exitstatus: int) -> None:
        self.counters["pytest_exit_code"] = int(exitstatus)
        if (
            self.counters["expected_guard_assertion_observed"] == 1
            and self.counters["unexpected_target_failures"] == 0
            and self.counters["unexpected_target_passes"] == 0
            and exitstatus == pytest.ExitCode.OK
        ):
            self.counters["probe_status"] = "expected_failure_observed"
        else:
            self.counters["probe_status"] = "inconclusive_or_unexpected"
            session.exitstatus = pytest.ExitCode.TESTS_FAILED
        self.result_file.write_text(
            json.dumps(self.counters, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


def main() -> int:
    policy_engine_root = Path(__file__).resolve().parents[3]
    test_file = (
        policy_engine_root
        / "tests/unit/runtime/http/test_nl_pipeline_materialization.py"
    )
    result_file = Path(__file__).with_name("result.json")
    sys.path.insert(0, str(policy_engine_root / "src"))
    os.chdir(policy_engine_root)
    probe = UnknownCostToZeroRemovalProbe(test_file, result_file)
    return int(
        pytest.main(
            [f"{test_file}::{TARGET_TEST}", "-q", "--tb=short"],
            plugins=[probe],
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
