"""Structured timing records for tool runs."""

from __future__ import annotations

import ast
import fcntl
import json
import math
import os
import sys
import time
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from inspect import signature
from pathlib import Path
from statistics import fmean

from .fs import atomic_write_text
from .runner import ToolSpec

DEFAULT_TIMING_LOG_ENV = "POLISYOS_TOOLS_TIMING_LOG"
DEFAULT_TIMING_RETENTION_ENV = "POLISYOS_TOOLS_TIMING_RETENTION"

# This log is diagnostic evidence, not scratch: it is the only thing that distinguishes a slow
# environment from a producer regression, and a budget derived without it is a guess paid for by
# a timeout. It previously defaulted under /tmp, where a reboot or a tmp sweep erases it -- which
# is exactly what happened, taking every accumulated sample with it. It now defaults inside the
# repository, which survives both. `.polisyos-tools/` is the location the repository already
# reserves for durable local tool state (ignored in both .gitignore files), so no new mechanism
# and no ignore-rule change is introduced here.
#
# Committed or ignored: IGNORED, deliberately. The contents are host-specific wall-clock
# measurements that would churn on every run and conflict across parallel lanes, so committing
# them is wrong. What protects the evidence instead is promotion, not the file's own persistence:
# a sample that justifies a budget is copied into `docs/superpowers/timing-evidence/` and cited
# from `source_refs` in `tools/quality/timing_budgets.json`, both of which are committed. The
# live log is a rolling buffer feeding that promotion; the committed catalog and evidence are the
# archive. "Ignored" was never the defect -- "ignored AND under /tmp" was.
#
# Note the log is per-worktree, because it is anchored to this file. Point several worktrees at
# one log with POLISYOS_TOOLS_TIMING_LOG when a wave should accumulate into a single history.
DEFAULT_TIMING_LOG_PATH = Path(__file__).resolve().parents[2] / ".polisyos-tools" / "timing.jsonl"

# Retention is a whole-file record count, so a busy lane evicts other lanes' samples. Measured
# 2026-08-17 there are 32 distinct known lanes (22 catalogued + 10 further lanes observed in the
# recovered log). At the previous default of 200 that is ~6 records per lane if runs were spread
# evenly -- and they are not, so one repeated wave could evict the only sample another lane ever
# recorded. 2000 holds ~60 runs per known lane at roughly 250 bytes each (~500 KB), enough for a
# p95 to survive a wave. The number is a measurement of the current lane count, not a constant:
# re-derive it if the lane count moves materially.
DEFAULT_TIMING_RETENTION = 2000
DEFAULT_TIMING_BUDGET_CATALOG_PATH = (
    Path(__file__).resolve().parents[1] / "quality" / "timing_budgets.json"
)
_DIRECT_ACTION_OPTION_PREFIXES = (
    "accept",
    "capture",
    "characterize",
    "check",
    "cold",
    "corrupt",
    "execute",
    "rederive",
    "reissue",
    "source-flip",
    "warm",
    "write",
)
DEFAULT_TIMING_BUDGETS_MS: dict[str, float] = {
    "workspace.bootstrap": 180_000.0,
    "workspace.doctor": 30_000.0,
    "workspace.verify": 420_000.0,
    "diagnostics.gen-schema": 30_000.0,
    "diagnostics.abi-diff": 15_000.0,
    "lint.lint-imports": 20_000.0,
}

TOOLS_ROOT = Path(__file__).resolve().parents[1]

# A lane's completed-work terminals are a per-lane contract fact owned by the tool module that
# returns them, never a global constant. Each tool module may declare a module-level mapping of
# ``mode -> healthy exit codes``; any mode it does not name falls back to the default below.
HEALTHY_TERMINAL_DECLARATION_NAME = "TIMING_HEALTHY_TERMINAL_EXIT_CODES"
DEFAULT_HEALTHY_TERMINAL_EXIT_CODES: tuple[int, ...] = (0,)

#: Identifies which rule admitted a duration sample, so a widened predicate is visible rather than
#: silent. Catalog rows carrying an older identifier were admitted under an older rule.
SAMPLE_ADMISSION_PREDICATE_ID = "declared_healthy_terminal:v1"
MANUAL_SAMPLE_ADMISSION_PREDICATE_ID = "manual_journal_excerpt:v1"
SAMPLE_ADMISSION_PREDICATE_IDS = frozenset(
    {SAMPLE_ADMISSION_PREDICATE_ID, MANUAL_SAMPLE_ADMISSION_PREDICATE_ID}
)

#: Regimes a sample can be measured in. A cap derived from a ``serialized`` sample manufactures
#: false cap non-receipts on a host that runs lanes in parallel, so the regime travels with the
#: sample rather than being assumed at the point of use.
SAMPLE_REGIMES = frozenset({"serialized", "contended", "unknown"})

SKIP_EXIT_CODE = 78

# Statuses that mean the run never reached its own terminal decision. No declaration can widen
# these: a killed run's duration measures the cap, not the lane.
_NO_TERMINAL_STATUSES = frozenset({"running", "killed", "timeout", "terminated", "cancelled"})


@dataclass(frozen=True)
class SampleAdmission:
    """Whether one record's duration may be used as a timing sample, and under which rule."""

    admitted: bool
    reason: str
    predicate_id: str = SAMPLE_ADMISSION_PREDICATE_ID


def admit_duration_sample(
    record: ToolRunRecord,
    *,
    healthy_terminal_exit_codes: tuple[int, ...] = DEFAULT_HEALTHY_TERMINAL_EXIT_CODES,
) -> SampleAdmission:
    """Admit a duration iff the run reached a terminal its own lane declares completed work.

    Admission is completion, not success. ``exit_code == 0`` is only the *default* declaration:
    lanes exist whose contract makes exit ``1`` the completed outcome and exit ``0`` the defect,
    so the exit code alone carries no health meaning without the lane's declaration. Harness
    termination, signal death, skips and malformed records stay inadmissible under every
    declaration, because their duration measures something other than the lane's work.
    """

    if not record.tool or not record.started_at:
        return SampleAdmission(False, "malformed_record")
    if not math.isfinite(record.duration_ms):
        return SampleAdmission(False, "malformed_record")
    if record.status in _NO_TERMINAL_STATUSES:
        return SampleAdmission(False, f"no_terminal_decision:{record.status}")
    if record.status == "skipped" or record.exit_code == SKIP_EXIT_CODE:
        return SampleAdmission(False, "skipped")
    if record.preflight_status != "ok":
        return SampleAdmission(False, f"preflight_{record.preflight_status}")
    if record.exit_code < 0:
        return SampleAdmission(False, "signal_death")
    if record.duration_ms <= 0:
        return SampleAdmission(False, "zero_duration")
    if record.exit_code not in healthy_terminal_exit_codes:
        return SampleAdmission(False, "terminal_not_declared_healthy")
    return SampleAdmission(True, "declared_healthy_terminal")


def _healthy_terminal_declaration_from_source(
    source: str, filename: str
) -> dict[str, tuple[int, ...]]:
    """Read a module's healthy-terminal declaration without importing the module."""

    tree = ast.parse(source, filename=filename)
    for node in tree.body:
        targets = (
            node.targets
            if isinstance(node, ast.Assign)
            else [node.target]
            if isinstance(node, ast.AnnAssign) and node.value is not None
            else []
        )
        if not any(
            isinstance(target, ast.Name) and target.id == HEALTHY_TERMINAL_DECLARATION_NAME
            for target in targets
        ):
            continue
        value = node.value
        if value is None:
            continue
        try:
            declared = ast.literal_eval(value)
        except ValueError as exc:
            raise ValueError(
                f"{filename}: {HEALTHY_TERMINAL_DECLARATION_NAME} must be a literal mapping"
            ) from exc
        if not isinstance(declared, Mapping):
            raise ValueError(
                f"{filename}: {HEALTHY_TERMINAL_DECLARATION_NAME} must be a mapping of"
                " mode to exit codes"
            )
        resolved: dict[str, tuple[int, ...]] = {}
        for mode, codes in declared.items():
            if not isinstance(mode, str) or not mode.strip():
                raise ValueError(
                    f"{filename}: healthy-terminal mode names must be non-empty strings"
                )
            if isinstance(codes, bool) or not isinstance(codes, list | tuple | set):
                raise ValueError(
                    f"{filename}: healthy-terminal exit codes for {mode!r} must be a sequence"
                )
            if not codes or any(
                isinstance(code, bool) or not isinstance(code, int) for code in codes
            ):
                raise ValueError(
                    f"{filename}: healthy-terminal exit codes for {mode!r} must be non-empty ints"
                )
            entries = tuple(sorted(set(codes)))
            if any(code < 0 for code in entries):
                raise ValueError(
                    f"{filename}: healthy-terminal exit codes for {mode!r} must not"
                    " include signal deaths"
                )
            if SKIP_EXIT_CODE in entries:
                raise ValueError(
                    f"{filename}: exit {SKIP_EXIT_CODE} is a skip and can never be a"
                    " completed terminal"
                )
            resolved[mode] = entries
        return resolved
    return {}


def _timing_keys_for_module(path: Path, root: Path) -> tuple[str, ...]:
    """Return every timing-log ``tool`` name one tool module can be recorded under.

    Two namespaces reach the same module. Direct entrypoints derive their key from the script
    path (``quality.validation.check_x``); registry dispatch records ``category.command-name``
    (``validation.check-x``). Both are indexed so a declaration is found whichever path ran.
    """

    relative = path.relative_to(root).with_suffix("")
    parts = relative.parts
    direct_key = ".".join(parts)
    category = parts[-2] if len(parts) > 1 else parts[0]
    command = parts[-1].replace("_", "-")
    return tuple(dict.fromkeys((direct_key, f"{category}.{command}")))


def load_healthy_terminal_declarations(
    root: Path = TOOLS_ROOT,
) -> dict[str, dict[str, tuple[int, ...]]]:
    """Index every tool module's declared healthy terminals by the tool names it records under."""

    declarations: dict[str, dict[str, tuple[int, ...]]] = {}
    for path in sorted(root.rglob("*.py")):
        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if HEALTHY_TERMINAL_DECLARATION_NAME not in source:
            continue
        declared = _healthy_terminal_declaration_from_source(source, str(path))
        if not declared:
            continue
        for key in _timing_keys_for_module(path, root):
            declarations[key] = declared
    return declarations


def healthy_terminal_exit_codes_for(
    tool: str,
    mode: str,
    declarations: Mapping[str, Mapping[str, tuple[int, ...]]],
) -> tuple[int, ...]:
    """Resolve one lane's declared completed-work terminals, defaulting to ``{0}``."""

    return tuple(declarations.get(tool, {}).get(mode, DEFAULT_HEALTHY_TERMINAL_EXIT_CODES))


def timing_key_for(tool: str, mode: str) -> str:
    """The catalog join rule: log records carry ``tool`` and ``mode``; the catalog keys on both."""

    return f"{tool}:{mode}"


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
    #: Runs whose duration the lane's declared terminal set admits as a sample. ``local_failures``
    #: is retained for continuity but counts the harness's exit-code proxy, not lane health.
    admitted_runs: int = 0
    inadmissible_runs: int = 0


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
    lock_path = path.with_name(f".{path.name}.lock")
    with lock_path.open("a+b") as lock_handle:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
        try:
            records = read_timing_records(path)
            limit = _retention_limit()
            prior_limit = limit - 1
            retained = [*(records[-prior_limit:] if prior_limit else []), record]
            payload = "".join(
                json.dumps(asdict(item), sort_keys=True) + "\n" for item in retained
            )
            atomic_write_text(path, payload)
        finally:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)


def default_timing_log_path() -> Path:
    return DEFAULT_TIMING_LOG_PATH


def percentile_ms(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, math.ceil(percentile * len(ordered)) - 1))
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
    *,
    declarations: Mapping[str, Mapping[str, tuple[int, ...]]] | None = None,
) -> list[TimingBudgetLaneSummary]:
    """Project local records onto the separately named catalog tool/mode lanes."""

    resolved_declarations = (
        load_healthy_terminal_declarations() if declarations is None else declarations
    )
    records_by_lane: dict[tuple[str, str], list[ToolRunRecord]] = {}
    for record in records:
        records_by_lane.setdefault((record.tool, record.mode), []).append(record)
    summaries: list[TimingBudgetLaneSummary] = []
    for lane in catalog:
        local_records = sorted(
            records_by_lane.get((lane.tool, lane.mode), []), key=lambda record: record.started_at
        )
        healthy_terminals = healthy_terminal_exit_codes_for(
            lane.tool, lane.mode, resolved_declarations
        )
        completed_records = [
            record
            for record in local_records
            if admit_duration_sample(
                record, healthy_terminal_exit_codes=healthy_terminals
            ).admitted
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
                admitted_runs=len(completed_records),
                inadmissible_runs=len(local_records) - len(completed_records),
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
    started_perf_counter: float | None = None,
) -> int:
    """Run an operation and append one best-effort timing record without changing its outcome."""

    observed_start = time.perf_counter()
    started = (
        min(started_perf_counter, observed_start)
        if started_perf_counter is not None
        else observed_start
    )
    started_at = (datetime.now(UTC) - timedelta(seconds=observed_start - started)).isoformat()
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


def _long_options_from_argv(argv: list[str]) -> list[tuple[str, str | None]]:
    """Return long options and their syntactically attached values before ``--``."""

    options: list[tuple[str, str | None]] = []
    index = 0
    while index < len(argv):
        argument = argv[index]
        if argument == "--":
            break
        if not argument.startswith("--") or len(argument) <= 2:
            index += 1
            continue
        rendered = argument[2:]
        if "=" in rendered:
            name, value = rendered.split("=", 1)
            options.append((name, value))
            index += 1
            continue
        value: str | None = None
        if index + 1 < len(argv) and not argv[index + 1].startswith("--"):
            value = argv[index + 1]
            index += 1
        options.append((rendered, value))
        index += 1
    return options


def _mode_and_output_format_from_argv(argv: list[str]) -> tuple[str, str]:
    """Classify action mode and presentation format without treating values as actions."""

    options = _long_options_from_argv(argv)
    output_format = "text"
    for name, value in options:
        if name == "output-format" and value:
            output_format = value
        elif name == "json" and value is None:
            output_format = "json"

    action_options = [
        name
        for name, _value in options
        if any(
            name == prefix or name.startswith(f"{prefix}-")
            for prefix in _DIRECT_ACTION_OPTION_PREFIXES
        )
    ]
    if action_options:
        return action_options[0], output_format
    return "default", output_format


def run_timed_entrypoint(
    entrypoint: Callable[..., int],
    *,
    script_path: str | Path,
    argv: list[str],
    started_perf_counter: float | None = None,
) -> int:
    """Run a legacy direct entrypoint through the shared timing emission path."""

    arguments = list(argv)

    def _operation() -> int:
        if _entrypoint_accepts_argv(entrypoint):
            return entrypoint(arguments)
        return entrypoint()

    mode, output_format = _mode_and_output_format_from_argv(arguments)
    return run_timed_operation(
        _operation,
        tool=_timing_key_for_script(script_path),
        category="quality",
        mode=mode,
        output_format=output_format,
        started_perf_counter=started_perf_counter,
    )
