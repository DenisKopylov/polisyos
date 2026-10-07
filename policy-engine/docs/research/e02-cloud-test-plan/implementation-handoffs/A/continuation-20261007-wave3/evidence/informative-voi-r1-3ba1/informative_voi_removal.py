"""R1 probe removing only the default scheduler's information-value ROI waiver."""

from __future__ import annotations

import hashlib
import inspect
import json
import subprocess
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

_PLUGIN_PATH = Path(__file__).resolve()
_POLICY_ENGINE = _PLUGIN_PATH.parents[3]
_REPO_ROOT = _POLICY_ENGINE.parent
_TARGET_NODEID = (
    "tests/integration/core_runtime/test_e02_informative_voi_execution.py::"
    "test_default_information_value_advance_executes_real_n5_and_budget_blocks_it"
)
_TARGET_FUNCTION = "test_default_information_value_advance_executes_real_n5_and_budget_blocks_it"
_CALLS: list[dict[str, Any]] = []
_REPORTS: list[dict[str, Any]] = []
_FAILURE_SNAPSHOT: dict[str, Any] | None = None
_ACTIVE_TARGET = False
_SIMPLE_SCHEDULER: type[Any] | None = None
_ORIGINAL_RECOMMENDED_ACTION: Any = None


def _git(*args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=_REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip()


def _value(obj: object, name: str) -> Any:
    return getattr(obj, name, None)


def _caller_inputs() -> dict[str, Any]:
    frame = inspect.currentframe()
    caller = frame.f_back if frame is not None else None
    caller = caller.f_back if caller is not None else None
    if caller is None or caller.f_code.co_name != "_prioritize_single":
        return {}
    inputs = caller.f_locals.get("inputs")
    return dict(inputs) if isinstance(inputs, dict) else {}


def _remove_information_waiver(self: object, **kwargs: Any) -> tuple[str, str]:
    """Call the real decision first, then remove only its positive-info waiver."""

    original = _ORIGINAL_RECOMMENDED_ACTION(self, **kwargs)
    if not _ACTIVE_TARGET:
        return original

    inputs = _caller_inputs()
    budget = kwargs.get("budget_remaining")
    estimated_cost = kwargs.get("estimated_cost")
    budget_fits = bool(
        budget is not None
        and estimated_cost is not None
        and not budget.would_exceed(getattr(self, "_budget_key", "run"), estimated_cost)
    )
    raw_proxy = inputs.get("expected_value_proxy")
    record = {
        "scheduler_type": f"{type(self).__module__}.{type(self).__qualname__}",
        "candidate_id": inputs.get("candidate_id"),
        "raw_proxy_score_from_scheduler_inputs": raw_proxy,
        "expected_information_gain": kwargs.get("expected_information_gain"),
        "expected_improvement_per_usd": kwargs.get("expected_improvement_per_usd"),
        "next_level": kwargs.get("next_level"),
        "estimated_cost": str(estimated_cost) if estimated_cost is not None else None,
        "budget_remaining": (
            str(budget.remaining(getattr(self, "_budget_key", "run")))
            if budget is not None
            else None
        ),
        "budget_fits": budget_fits,
        "original_action": original[0],
        "original_reason": original[1],
        "mutation_applied": False,
    }

    qualified = bool(
        type(self) is _SIMPLE_SCHEDULER
        and kwargs.get("next_level") == 3
        and raw_proxy == 0.0
        and kwargs.get("expected_information_gain") == 0.4
        and kwargs.get("expected_improvement_per_usd") == 0.0
        and estimated_cost == Decimal("0.5")
        and budget_fits
        and original == ("advance", "advance_by_information_value")
    )
    record["qualified_actual_information_advance"] = qualified
    if qualified:
        record["mutation_applied"] = True
        record["mutated_action"] = "reject"
        record["mutated_reason"] = "roi_below_threshold"
        _CALLS.append(record)
        return "reject", "roi_below_threshold"

    _CALLS.append(record)
    return original


def pytest_configure(config: pytest.Config) -> None:
    del config
    global _ORIGINAL_RECOMMENDED_ACTION, _SIMPLE_SCHEDULER
    from polisyos.scientist.methods.search.voi_scheduler import SimpleVOIScheduler

    _SIMPLE_SCHEDULER = SimpleVOIScheduler
    _ORIGINAL_RECOMMENDED_ACTION = SimpleVOIScheduler._recommended_action
    SimpleVOIScheduler._recommended_action = (  # type: ignore[method-assign]
        _remove_information_waiver
    )


def pytest_runtest_setup(item: pytest.Item) -> None:
    global _ACTIVE_TARGET
    _ACTIVE_TARGET = item.nodeid == _TARGET_NODEID


def pytest_runtest_teardown(item: pytest.Item, nextitem: pytest.Item | None) -> None:
    del nextitem
    global _ACTIVE_TARGET
    if item.nodeid == _TARGET_NODEID:
        _ACTIVE_TARGET = False


def pytest_runtest_logreport(report: pytest.TestReport) -> None:
    if report.nodeid != _TARGET_NODEID:
        return
    _REPORTS.append(
        {
            "nodeid": report.nodeid,
            "when": report.when,
            "outcome": report.outcome,
            "longrepr": str(report.longrepr) if report.longrepr is not None else None,
        }
    )


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo[Any]):
    global _FAILURE_SNAPSHOT
    outcome = yield
    outcome.get_result()
    if item.nodeid != _TARGET_NODEID or call.when != "call" or call.excinfo is None:
        return
    for entry in call.excinfo.traceback:
        frame = entry.frame
        frame_name = getattr(getattr(frame, "code", None), "name", None)
        if frame_name is None:
            raw_frame = getattr(frame, "raw", None)
            frame_name = getattr(getattr(raw_frame, "f_code", None), "co_name", None)
        if frame_name != _TARGET_FUNCTION:
            continue
        local = getattr(frame, "f_locals", {})
        cycle = local.get("positive_cycle")
        summary = local.get("positive_summary")
        applicability = _value(summary, "n5_applicability")
        voi = _value(cycle, "voi_decision")
        simulation = _value(cycle, "simulation")
        _FAILURE_SNAPSHOT = {
            "summary_proxy_score": _value(summary, "proxy_score"),
            "summary_information_estimate": _value(summary, "voi_estimate"),
            "preflight_status": _value(applicability, "status"),
            "scheduler_action": _value(voi, "scheduler_action"),
            "scheduler_reason": _value(voi, "scheduler_reason"),
            "simulation_status": _value(simulation, "status"),
            "simulation_result_ref": str(_value(simulation, "simulation_result_ref")),
            "observed_n5_calls": list(local.get("n5_calls", ())),
        }
        break


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    del session
    scheduler_path = (
        _POLICY_ENGINE / "src/polisyos/scientist/methods/search/voi_scheduler.py"
    )
    test_path = (
        _POLICY_ENGINE / "tests/integration/core_runtime/test_e02_informative_voi_execution.py"
    )
    call_report = next(
        (report for report in _REPORTS if report["when"] == "call"), None
    )
    longrepr = (call_report or {}).get("longrepr") or ""
    expected_assertion = bool(
        call_report is not None
        and call_report["outcome"] == "failed"
        and "positive_cycle.voi_decision.scheduler_action" in longrepr
        and "advance" in longrepr
    )
    qualified_original_decision = any(
        record.get("qualified_actual_information_advance") is True
        and record.get("original_action") == "advance"
        and record.get("original_reason") == "advance_by_information_value"
        and record.get("raw_proxy_score_from_scheduler_inputs") == 0.0
        and record.get("expected_information_gain") == 0.4
        and record.get("mutation_applied") is True
        for record in _CALLS
    )
    execution_blocked = bool(
        _FAILURE_SNAPSHOT is not None
        and _FAILURE_SNAPSHOT.get("preflight_status") == "eligible"
        and _FAILURE_SNAPSHOT.get("summary_proxy_score") == 0.0
        and _FAILURE_SNAPSHOT.get("summary_information_estimate") == 0.4
        and _FAILURE_SNAPSHOT.get("scheduler_action") == "reject"
        and _FAILURE_SNAPSHOT.get("scheduler_reason") == "roi_below_threshold"
        and _FAILURE_SNAPSHOT.get("simulation_status") == "simulation_blocked"
        and _FAILURE_SNAPSHOT.get("simulation_result_ref") == "None"
        and _FAILURE_SNAPSHOT.get("observed_n5_calls") == []
    )
    source_bytes = scheduler_path.read_bytes()
    test_bytes = test_path.read_bytes()
    evidence = {
        "schema": "policyos.e02.informative_voi_removal_r1.v1",
        "purpose": "source-property-removal witness; never a product PASS",
        "created_at_utc": datetime.now(UTC).isoformat(),
        "target_nodeid": _TARGET_NODEID,
        "pytest_exitstatus": int(exitstatus),
        "head": _git("rev-parse", "HEAD"),
        "head_tree": _git("rev-parse", "HEAD^{tree}"),
        "scheduler_path": str(scheduler_path),
        "scheduler_sha256": hashlib.sha256(source_bytes).hexdigest(),
        "scheduler_git_blob": _git(
            "rev-parse", "HEAD:policy-engine/src/polisyos/scientist/methods/search/voi_scheduler.py"
        ),
        "test_path": str(test_path),
        "test_sha256": hashlib.sha256(test_bytes).hexdigest(),
        "test_git_blob": _git(
            "rev-parse",
            "HEAD:policy-engine/tests/integration/core_runtime/"
            "test_e02_informative_voi_execution.py",
        ),
        "plugin_path": str(_PLUGIN_PATH),
        "plugin_sha256": hashlib.sha256(_PLUGIN_PATH.read_bytes()).hexdigest(),
        "target_reports": _REPORTS,
        "actual_scheduler_decisions": _CALLS,
        "failure_snapshot": _FAILURE_SNAPSHOT,
        "qualified_original_information_advance": qualified_original_decision,
        "expected_assertion_failure_observed": expected_assertion,
        "eligible_candidate_blocked_without_n5_execution": execution_blocked,
        "verdict": (
            "EXPECTED_FALSIFIER"
            if qualified_original_decision and expected_assertion and execution_blocked
            else "HARNESS_ERROR_OR_UNEXPECTED_RESULT"
        ),
        "interpretation": (
            "The plugin calls the actual default SimpleVOIScheduler decision method first, then "
            "changes only its eligible positive-information, zero-proxy, within-budget advance "
            "to an ROI rejection. A qualified failure with eligible preflight and zero real N5 "
            "port calls demonstrates that the information-value branch controls execution. "
            "Budget-priority deferrals and hard-feasibility checks are not removed. This probe "
            "does not establish monetary value or provider spend."
        ),
    }
    (_PLUGIN_PATH.parent / "r1_evidence.json").write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
