"""Structured timing records for tool runs."""

from __future__ import annotations

import json
import os
import sys
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from inspect import signature
from pathlib import Path
from statistics import fmean

from .fs import atomic_write_text
from .runner import ToolSpec

DEFAULT_TIMING_LOG_ENV = "POLISYOS_TOOLS_TIMING_LOG"
DEFAULT_TIMING_RETENTION_ENV = "POLISYOS_TOOLS_TIMING_RETENTION"
DEFAULT_TIMING_LOG_PATH = Path("/tmp/polisyos-tools/timing.jsonl")
DEFAULT_TIMING_RETENTION = 200
DEFAULT_TIMING_BUDGETS_MS: dict[str, float] = {
    "workspace.bootstrap": 180_000.0,
    "workspace.doctor": 30_000.0,
    "workspace.verify": 420_000.0,
    "diagnostics.gen-schema": 30_000.0,
    "diagnostics.abi-diff": 15_000.0,
    "lint.lint-imports": 20_000.0,
}


@dataclass(frozen=True)
class ToolRunRecord:
    tool: str
    category: str
    output_format: str
    status: str
    preflight_status: str
    started_at: str
    duration_ms: float
    exit_code: int
    mode: str = "default"


@dataclass(frozen=True)
class ToolTimingSummary:
    tool: str
    category: str
    latest_mode: str
    runs: int
    failures: int
    skipped: int
    latest_status: str
    latest_duration_ms: float
    average_duration_ms: float
    p95_duration_ms: float
    budget_ms: float | None
    over_budget_runs: int


@contextmanager
def timed_tool_run(spec: ToolSpec) -> Iterator[dict[str, object]]:
    started_at = datetime.now(UTC).isoformat()
    start = time.perf_counter()
    state: dict[str, object] = {
        "tool": spec.qualified_name,
        "category": spec.category,
        "status": "running",
        "preflight_status": "ok",
        "started_at": started_at,
        "exit_code": 0,
    }
    try:
        yield state
    finally:
        state["duration_ms"] = round((time.perf_counter() - start) * 1000.0, 3)


def make_timing_record(
    spec: ToolSpec,
    state: dict[str, object],
    *,
    exit_code: int,
    output_format: str,
) -> ToolRunRecord:
    return ToolRunRecord(
        tool=spec.qualified_name,
        category=spec.category,
        output_format=output_format,
        status=str(state.get("status") or ("ok" if exit_code == 0 else "failed")),
        preflight_status=str(state.get("preflight_status") or "ok"),
        started_at=str(state.get("started_at")),
        duration_ms=float(state.get("duration_ms") or 0.0),
        exit_code=exit_code,
        mode=str(state.get("mode") or "default"),
    )


def _retention_limit() -> int:
    raw = os.environ.get(DEFAULT_TIMING_RETENTION_ENV, "").strip()
    if not raw:
        return DEFAULT_TIMING_RETENTION
    try:
        parsed = int(raw)
    except ValueError:
        return DEFAULT_TIMING_RETENTION
    return max(parsed, 1)


def _coerce_record(payload: dict[str, object]) -> ToolRunRecord:
    tool = str(payload.get("tool") or "")
    category = str(payload.get("category") or tool.split(".", 1)[0] or "unknown")
    output_format = str(payload.get("output_format") or "text")
    return ToolRunRecord(
        tool=tool,
        category=category,
        output_format=output_format,
        status=str(payload.get("status") or "unknown"),
        preflight_status=str(payload.get("preflight_status") or "ok"),
        started_at=str(payload.get("started_at") or ""),
        duration_ms=float(payload.get("duration_ms") or 0.0),
        exit_code=int(payload.get("exit_code") or 0),
        mode=str(payload.get("mode") or "default"),
    )


def read_timing_records(path: Path) -> list[ToolRunRecord]:
    if not path.exists():
        return []
    records: list[ToolRunRecord] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        rendered = line.strip()
        if not rendered:
            continue
        try:
            payload = json.loads(rendered)
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        try:
            records.append(_coerce_record(payload))
        except (TypeError, ValueError):
            continue
    return records


def append_timing_record(path: Path, record: ToolRunRecord) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    records = read_timing_records(path)
    limit = _retention_limit()
    retained = [*records[-max(limit - 1, 0) :], record]
    payload = "".join(json.dumps(asdict(item), sort_keys=True) + "\n" for item in retained)
    atomic_write_text(path, payload)


def default_timing_log_path() -> Path:
    return DEFAULT_TIMING_LOG_PATH


def percentile_ms(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int(round((len(ordered) - 1) * percentile))))
    return ordered[index]


def summarize_timing_records(
    records: list[ToolRunRecord],
    *,
    budgets_ms: dict[str, float] | None = None,
) -> list[ToolTimingSummary]:
    budgets = budgets_ms or DEFAULT_TIMING_BUDGETS_MS
    grouped: dict[str, list[ToolRunRecord]] = {}
    for record in records:
        grouped.setdefault(record.tool, []).append(record)

    summaries: list[ToolTimingSummary] = []
    for tool in sorted(grouped):
        tool_records = sorted(grouped[tool], key=lambda record: record.started_at)
        durations = [record.duration_ms for record in tool_records]
        latest = tool_records[-1]
        budget_ms = budgets.get(tool)
        over_budget_runs = (
            sum(1 for duration in durations if budget_ms is not None and duration > budget_ms)
            if budget_ms is not None
            else 0
        )
        summaries.append(
            ToolTimingSummary(
                tool=tool,
                category=latest.category,
                latest_mode=latest.mode,
                runs=len(tool_records),
                failures=sum(1 for record in tool_records if record.status == "failed"),
                skipped=sum(1 for record in tool_records if record.status == "skipped"),
                latest_status=latest.status,
                latest_duration_ms=latest.duration_ms,
                average_duration_ms=round(fmean(durations), 3),
                p95_duration_ms=round(percentile_ms(durations, 0.95), 3),
                budget_ms=budget_ms,
                over_budget_runs=over_budget_runs,
            )
        )
    return summaries


def timing_log_from_env() -> Path | None:
    raw = os.environ.get(DEFAULT_TIMING_LOG_ENV, "").strip()
    if not raw:
        return default_timing_log_path()
    return Path(raw)


def _exit_code_from_system_exit(exc: SystemExit) -> int:
    """Return the process status implied by a ``SystemExit`` instance."""

    if isinstance(exc.code, int):
        return exc.code
    return 0 if exc.code is None else 1


def _append_timing_record_best_effort(record: ToolRunRecord) -> None:
    """Persist telemetry without allowing telemetry storage to alter command semantics."""

    timing_log = timing_log_from_env()
    if timing_log is None:
        return
    try:
        append_timing_record(timing_log, record)
    except Exception as exc:  # pragma: no cover - defensive telemetry boundary.
        print(f"warning: could not persist tool timing telemetry: {exc}", file=sys.stderr)


def run_timed_operation(
    operation: Callable[[], int],
    *,
    tool: str,
    category: str,
    mode: str = "default",
    output_format: str = "text",
) -> int:
    """Run an operation and append one best-effort timing record without changing its outcome."""

    started_at = datetime.now(UTC).isoformat()
    started = time.perf_counter()
    exit_code = 1
    status = "failed"
    try:
        exit_code = operation()
        status = "ok" if exit_code == 0 else "failed"
        return exit_code
    except SystemExit as exc:
        exit_code = _exit_code_from_system_exit(exc)
        status = "ok" if exit_code == 0 else "failed"
        raise
    except BaseException:
        raise
    finally:
        record = ToolRunRecord(
            tool=tool,
            category=category,
            output_format=output_format,
            status=status,
            preflight_status="ok",
            started_at=started_at,
            duration_ms=round((time.perf_counter() - started) * 1000.0, 3),
            exit_code=exit_code,
            mode=mode,
        )
        _append_timing_record_best_effort(record)


def _entrypoint_accepts_argv(entrypoint: Callable[..., int]) -> bool:
    """Return whether the existing direct entrypoint accepts one positional argument."""

    return bool(signature(entrypoint).parameters)


def _timing_key_for_script(script_path: str | Path) -> str:
    """Derive a stable timing key from a repository tool script path."""

    path = Path(script_path).with_suffix("")
    parts = path.parts
    try:
        tools_index = parts.index("tools")
    except ValueError:
        return path.name
    return ".".join(parts[tools_index + 1 :])


def _mode_from_argv(argv: list[str]) -> str:
    """Return the first long option as the direct command's operational mode."""

    for argument in argv:
        if argument.startswith("--") and len(argument) > 2:
            return argument[2:].split("=", 1)[0]
    return "default"


def run_timed_entrypoint(
    entrypoint: Callable[..., int],
    *,
    script_path: str | Path,
    argv: list[str],
) -> int:
    """Run a legacy direct entrypoint through the shared timing emission path."""

    arguments = list(argv)

    def _operation() -> int:
        if _entrypoint_accepts_argv(entrypoint):
            return entrypoint(arguments)
        return entrypoint()

    return run_timed_operation(
        _operation,
        tool=_timing_key_for_script(script_path),
        category="quality",
        mode=_mode_from_argv(arguments),
    )
