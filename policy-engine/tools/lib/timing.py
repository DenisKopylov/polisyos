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
DEFAULT_TIMING_BUDGET_CATALOG_PATH = (
    Path(__file__).resolve().parents[1] / "quality" / "timing_budgets.json"
)
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


@dataclass(frozen=True)
class TimingBudgetLane:
    """A measured timeout recommendation for one exact tool and operational mode."""

    timing_key: str
    tool: str
    mode: str
    command: str
    samples_ms: tuple[float, ...]
    measured_p95_ms: float | None
    recommended_timeout_ms: float | None
    source_refs: tuple[str, ...]


@dataclass(frozen=True)
class TimingBudgetLaneSummary:
    """Catalog lane projected with locally persisted timing observations."""

    timing_key: str
    tool: str
    mode: str
    command: str
    measured_p95_ms: float | None
    recommended_timeout_ms: float | None
    source_refs: tuple[str, ...]
    state: str
    local_runs: int
    local_failures: int
    latest_duration_ms: float | None
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


def _required_string(payload: dict[str, object], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"timing budget lane requires a non-empty {field}")
    return value


def _optional_number(payload: dict[str, object], field: str) -> float | None:
    value = payload.get(field)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"timing budget lane {field} must be a number or null")
    return float(value)


def _timing_budget_lane_from_data(payload: object) -> TimingBudgetLane:
    if not isinstance(payload, dict):
        raise ValueError("timing budget lane must be an object")
    timing_key = _required_string(payload, "timing_key")
    tool = _required_string(payload, "tool")
    mode = _required_string(payload, "mode")
    if timing_key != f"{tool}:{mode}":
        raise ValueError("timing budget lane timing_key must equal tool:mode")
    samples_data = payload.get("samples_ms")
    if not isinstance(samples_data, list) or any(
        isinstance(value, bool) or not isinstance(value, int | float) or value < 0
        for value in samples_data
    ):
        raise ValueError("timing budget lane samples_ms must be non-negative numbers")
    samples_ms = tuple(float(value) for value in samples_data)
    measured_p95_ms = _optional_number(payload, "measured_p95_ms")
    recommended_timeout_ms = _optional_number(payload, "recommended_timeout_ms")
    expected_p95_ms = round(percentile_ms(list(samples_ms), 0.95), 3) if samples_ms else None
    if measured_p95_ms != expected_p95_ms:
        raise ValueError(
            "timing budget lane measured_p95_ms must equal the p95 recomputed from samples_ms"
        )
    expected_timeout_ms = measured_p95_ms * 2 if measured_p95_ms is not None else None
    if recommended_timeout_ms != expected_timeout_ms:
        raise ValueError(
            "timing budget lane recommended_timeout_ms must equal 2 * measured_p95_ms"
        )
    source_refs_data = payload.get("source_refs")
    if not isinstance(source_refs_data, list) or not source_refs_data or any(
        not isinstance(source_ref, str) or not source_ref.strip() for source_ref in source_refs_data
    ):
        raise ValueError("timing budget lane source_refs must be non-empty strings")
    return TimingBudgetLane(
        timing_key=timing_key,
        tool=tool,
        mode=mode,
        command=_required_string(payload, "command"),
        samples_ms=samples_ms,
        measured_p95_ms=measured_p95_ms,
        recommended_timeout_ms=recommended_timeout_ms,
        source_refs=tuple(source_refs_data),
    )


def load_timing_budget_catalog_data(payload: object) -> list[TimingBudgetLane]:
    """Validate a timing-budget catalog payload and return exact tool/mode lanes."""

    if not isinstance(payload, dict):
        raise ValueError("timing budget catalog must be an object")
    lanes_data = payload.get("lanes")
    if not isinstance(lanes_data, list):
        raise ValueError("timing budget catalog requires a lanes list")
    lanes = [_timing_budget_lane_from_data(lane) for lane in lanes_data]
    timing_keys = [lane.timing_key for lane in lanes]
    if len(timing_keys) != len(set(timing_keys)):
        raise ValueError("timing budget catalog contains duplicate timing_key values")
    return sorted(lanes, key=lambda lane: lane.timing_key)


def load_timing_budget_catalog(
    path: Path = DEFAULT_TIMING_BUDGET_CATALOG_PATH,
) -> list[TimingBudgetLane]:
    """Load and validate the repository's literal-sample timing budget catalog."""

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"could not read timing budget catalog: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"could not parse timing budget catalog: {path}") from exc
    return load_timing_budget_catalog_data(payload)


def summarize_timing_budget_lanes(
    records: list[ToolRunRecord],
    catalog: list[TimingBudgetLane],
) -> list[TimingBudgetLaneSummary]:
    """Project local records onto the separately named catalog tool/mode lanes."""

    records_by_lane: dict[tuple[str, str], list[ToolRunRecord]] = {}
    for record in records:
        records_by_lane.setdefault((record.tool, record.mode), []).append(record)
    summaries: list[TimingBudgetLaneSummary] = []
    for lane in catalog:
        local_records = sorted(
            records_by_lane.get((lane.tool, lane.mode), []), key=lambda record: record.started_at
        )
        completed_records = [
            record for record in local_records if record.status in {"ok", "failed"}
        ]
        over_budget_runs = sum(
            1
            for record in completed_records
            if lane.measured_p95_ms is not None and record.duration_ms > lane.measured_p95_ms
        )
        if not lane.samples_ms:
            state = "unmeasured"
        elif over_budget_runs:
            state = "over_budget"
        else:
            state = "measured"
        summaries.append(
            TimingBudgetLaneSummary(
                timing_key=lane.timing_key,
                tool=lane.tool,
                mode=lane.mode,
                command=lane.command,
                measured_p95_ms=lane.measured_p95_ms,
                recommended_timeout_ms=lane.recommended_timeout_ms,
                source_refs=lane.source_refs,
                state=state,
                local_runs=len(local_records),
                local_failures=sum(record.status == "failed" for record in local_records),
                latest_duration_ms=(local_records[-1].duration_ms if local_records else None),
                over_budget_runs=over_budget_runs,
            )
        )
    return summaries


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
