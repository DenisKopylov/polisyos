"""Structured timing records for tool runs."""

from __future__ import annotations

import ast
import fcntl
import hashlib
import json
import math
import os
import sys
import time
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from inspect import signature
from pathlib import Path, PurePosixPath
from statistics import fmean

from .fs import atomic_write_text
from .runner import ToolSpec

DEFAULT_TIMING_LOG_ENV = "POLISYOS_TOOLS_TIMING_LOG"
DEFAULT_TIMING_RETENTION_ENV = "POLISYOS_TOOLS_TIMING_RETENTION"
DEFAULT_TIMING_REGIME_ENV = "POLISYOS_TOOLS_TIMING_REGIME"

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
    "candidate",
    "capture",
    "characterize",
    "check",
    "cold",
    "corrupt",
    "execute",
    "measure",
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
    #: The contention regime this duration was measured in, supplied by the executor through
    #: POLISYOS_TOOLS_TIMING_REGIME. Defaults to "unknown" rather than guessing: measured
    #: contention on this host is 1.6-2.0x, so a cap derived from a sample of unknown regime is
    #: not safe to apply as if it were serialized.
    regime: str = "unknown"


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


# A nearest-rank p95 over n samples picks index ceil(0.95*n) - 1. For every n <= 19 that index IS
# n - 1, so the "p95" is arithmetically the MAXIMUM of the samples and carries no tail information
# whatsoever. The two first separate at n = 20. Publishing a number computed from fewer samples
# under the name "p95" is an unmeasured number wearing a measured number's clothes -- the E14(a)
# failure inverted -- so below this count the honest label is `max_observed`, not a percentile.
# Measured 2026-08-17: 0 of the 22 committed catalog lanes reach this count, and all 22 currently
# store a "measured_p95_ms" that equals the maximum of at most 4 samples.
MIN_SAMPLES_FOR_P95 = 20

#: What a lane's published ceiling actually rests on. Never a synonym for confidence -- it names
#: the arithmetic, so a reader can tell a percentile from a maximum from a supplied number.
BUDGET_BASIS_P95 = "p95"
BUDGET_BASIS_MAX_OBSERVED = "max_observed"
BUDGET_BASIS_DECLARED = "declared"


def budget_basis_for(sample_count: int) -> str:
    """Name what a ceiling derived from ``sample_count`` admitted samples actually is."""

    if sample_count <= 0:
        return BUDGET_BASIS_DECLARED
    if sample_count < MIN_SAMPLES_FOR_P95:
        return BUDGET_BASIS_MAX_OBSERVED
    return BUDGET_BASIS_P95


PYTEST_WORKLOAD_SCHEMA_VERSION = "policyos.timing.pytest_workload.v1"
PYTEST_WORKLOAD_PREDICATE_PROVENANCE = "recomputed"


@dataclass(frozen=True)
class PytestWorkloadIdentity:
    """Content-bound identity of one exact path-selected pytest workload."""

    schema_version: str
    predicate_provenance: str
    test_paths: tuple[str, ...]
    source_digests: tuple[tuple[str, str], ...]
    pytest_version: str
    config_path: str
    config_digest: str
    node_map_digest: str


def pytest_node_map_digest(node_ids_by_path: Mapping[str, Sequence[str]]) -> str:
    """Hash a complete ordered path-to-pytest-node map without a scalar denominator."""

    canonical = {
        path: list(node_ids_by_path[path]) for path in sorted(node_ids_by_path)
    }
    encoded = json.dumps(
        canonical,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _validate_pytest_workload_identity(identity: PytestWorkloadIdentity) -> None:
    """Enforce the complete v1 identity contract for loader and direct callers."""

    if identity.schema_version != PYTEST_WORKLOAD_SCHEMA_VERSION:
        raise ValueError("pytest workload identity has an unsupported schema version")
    if identity.predicate_provenance != PYTEST_WORKLOAD_PREDICATE_PROVENANCE:
        raise ValueError("pytest workload identity predicate must be recomputed")
    expected_paths = identity.test_paths
    if (
        not expected_paths
        or any(
            not _is_safe_relative_path(path) or not path.endswith(".py")
            for path in expected_paths
        )
        or len(expected_paths) != len(set(expected_paths))
    ):
        raise ValueError("pytest workload identity test_paths must be unique relative Python paths")
    source_digest_entries = identity.source_digests
    if any(
        not isinstance(entry, tuple)
        or len(entry) != 2
        or not isinstance(entry[0], str)
        or not _is_sha256_digest(entry[1])
        for entry in source_digest_entries
    ):
        raise ValueError("pytest workload identity must digest every selected source exactly once")
    source_digest_paths = tuple(path for path, _ in source_digest_entries)
    if (
        len(source_digest_paths) != len(set(source_digest_paths))
        or set(source_digest_paths) != set(expected_paths)
    ):
        raise ValueError("pytest workload identity must digest every selected source exactly once")
    if not isinstance(identity.pytest_version, str) or not identity.pytest_version.strip():
        raise ValueError("pytest workload identity requires a collector version")
    if not _is_safe_relative_path(identity.config_path):
        raise ValueError("pytest workload identity requires a safe config path")
    if not _is_sha256_digest(identity.config_digest):
        raise ValueError("pytest workload identity requires a config digest")
    if not _is_sha256_digest(identity.node_map_digest):
        raise ValueError("pytest workload identity requires a node-map digest")


def verify_pytest_workload_identity(
    identity: PytestWorkloadIdentity,
    *,
    command_test_paths: Sequence[str],
    source_bytes: Mapping[str, bytes],
    node_ids_by_path: Mapping[str, Sequence[str]],
    pytest_version: str,
    config_path: str,
    config_bytes: bytes,
) -> None:
    """Recompute a pytest workload identity from selection bytes and real node IDs."""

    _validate_pytest_workload_identity(identity)
    expected_paths = identity.test_paths
    if tuple(command_test_paths) != expected_paths:
        raise ValueError("pytest workload command test paths differ from the receipt")
    if set(source_bytes) != set(expected_paths):
        raise ValueError("pytest workload source set differs from the receipt")
    expected_source_digests = dict(identity.source_digests)
    for path in expected_paths:
        digest = "sha256:" + hashlib.sha256(source_bytes[path]).hexdigest()
        if expected_source_digests.get(path) != digest:
            raise ValueError("pytest workload source digest differs from the receipt")
    if pytest_version != identity.pytest_version:
        raise ValueError("pytest workload collector version differs from the receipt")
    if config_path != identity.config_path:
        raise ValueError("pytest workload config path differs from the receipt")
    config_digest = "sha256:" + hashlib.sha256(config_bytes).hexdigest()
    if config_digest != identity.config_digest:
        raise ValueError("pytest workload config digest differs from the receipt")
    if set(node_ids_by_path) != set(expected_paths):
        raise ValueError("pytest workload node-map paths differ from the receipt")
    all_node_ids: list[str] = []
    for path in expected_paths:
        node_ids = tuple(node_ids_by_path[path])
        if not node_ids or any(
            not isinstance(node_id, str) or not node_id.startswith(f"{path}::")
            for node_id in node_ids
        ):
            raise ValueError("pytest workload node map contains an invalid node ID")
        all_node_ids.extend(node_ids)
    if len(all_node_ids) != len(set(all_node_ids)):
        raise ValueError("pytest workload node map contains duplicate node IDs")
    if pytest_node_map_digest(node_ids_by_path) != identity.node_map_digest:
        raise ValueError("pytest workload node map digest differs from the receipt")


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
    #: Exact source/collector/node-map receipt when the lane selects a pytest workload.
    workload_identity: PytestWorkloadIdentity | None = None
    #: Which rule admitted these samples, so a widened predicate is visible rather than silent.
    sample_admission_predicate: str = MANUAL_SAMPLE_ADMISSION_PREDICATE_ID
    #: The contention regime the samples were measured in. A cap from a ``serialized`` sample
    #: applied on a host running lanes in parallel manufactures false cap non-receipts.
    regime: str = "unknown"
    #: True when this lane has no admitted sample of its own and its ceiling was supplied rather
    #: than measured. A lane in this state never inherits a sibling lane's cap.
    ceiling_is_declared: bool = False

    @property
    def budget_basis(self) -> str:
        """Whether this lane's ceiling is a real percentile, a maximum, or a supplied number."""

        return budget_basis_for(len(self.samples_ms))

    @property
    def published_p95_ms(self) -> float | None:
        """The p95 only when the sample count can support one; otherwise nothing is published."""

        return self.measured_p95_ms if self.budget_basis == BUDGET_BASIS_P95 else None

    @property
    def max_observed_ms(self) -> float | None:
        """The largest admitted sample, which is what a sub-threshold ceiling actually rests on."""

        return max(self.samples_ms) if self.samples_ms else None


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
    #: What the catalogued ceiling rests on: a real percentile, a maximum, or a supplied number.
    budget_basis: str = BUDGET_BASIS_DECLARED
    #: Populated only when the lane clears MIN_SAMPLES_FOR_P95; otherwise no p95 is published.
    published_p95_ms: float | None = None
    max_observed_ms: float | None = None
    catalog_sample_count: int = 0


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
        regime=str(state.get("regime") or regime_from_env()),
    )


def regime_from_env() -> str:
    """The regime the executor declares it launched under; never inferred from timings."""

    raw = os.environ.get(DEFAULT_TIMING_REGIME_ENV, "").strip()
    return raw if raw in SAMPLE_REGIMES else "unknown"


def _retention_limit() -> int:
    raw = os.environ.get(DEFAULT_TIMING_RETENTION_ENV, "").strip()
    if not raw:
        return DEFAULT_TIMING_RETENTION
    try:
        parsed = int(raw)
    except ValueError:
        return DEFAULT_TIMING_RETENTION
    return max(parsed, 1)


def _record_string(
    payload: dict[str, object],
    field: str,
    *,
    default: str | None = None,
) -> str:
    """Read a required non-blank timing-record string without coercion."""

    value = payload.get(field, default)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"timing record requires a non-empty {field}")
    return value


def _coerce_record(payload: dict[str, object]) -> ToolRunRecord:
    """Read one persisted record without manufacturing fields from malformed telemetry."""

    tool = _record_string(payload, "tool")
    category = _record_string(
        payload,
        "category",
        default=tool.split(".", 1)[0] or "unknown",
    )
    duration = payload.get("duration_ms")
    if (
        isinstance(duration, bool)
        or not isinstance(duration, int | float)
        or not math.isfinite(duration)
        or duration < 0
    ):
        raise ValueError("timing record requires a finite non-negative duration_ms")
    exit_code = payload.get("exit_code")
    if isinstance(exit_code, bool) or not isinstance(exit_code, int):
        raise ValueError("timing record requires an integer exit_code")
    started_at = _record_string(payload, "started_at")
    try:
        datetime.fromisoformat(started_at)
    except ValueError as exc:
        raise ValueError("timing record requires an ISO-8601 started_at") from exc
    regime = _record_string(payload, "regime", default="unknown")
    if regime not in SAMPLE_REGIMES:
        raise ValueError("timing record requires a known regime")
    return ToolRunRecord(
        tool=tool,
        category=category,
        output_format=_record_string(payload, "output_format", default="text"),
        status=_record_string(payload, "status"),
        preflight_status=_record_string(payload, "preflight_status", default="ok"),
        started_at=started_at,
        duration_ms=float(duration),
        exit_code=exit_code,
        mode=_record_string(payload, "mode", default="default"),
        regime=regime,
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
            payload = "".join(serialize_tool_run_record(item) + "\n" for item in retained)
            atomic_write_text(path, payload)
        finally:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)


def serialize_tool_run_record(record: ToolRunRecord) -> str:
    """Serialize one timing record canonically for logs and bound execution receipts."""

    return json.dumps(asdict(record), sort_keys=True)


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


def _is_sha256_digest(value: object) -> bool:
    if not isinstance(value, str) or not value.startswith("sha256:"):
        return False
    encoded = value.removeprefix("sha256:")
    return len(encoded) == 64 and all(character in "0123456789abcdef" for character in encoded)


def _is_safe_relative_path(value: object) -> bool:
    if not isinstance(value, str) or not value.strip() or "\\" in value:
        return False
    path = PurePosixPath(value)
    return not path.is_absolute() and ".." not in path.parts and value == path.as_posix()


def _pytest_workload_identity_from_data(payload: object) -> PytestWorkloadIdentity | None:
    if payload is None:
        return None
    expected_fields = {
        "schema_version",
        "predicate_provenance",
        "test_paths",
        "source_digests",
        "pytest_version",
        "config_path",
        "config_digest",
        "node_map_digest",
    }
    if not isinstance(payload, dict) or set(payload) != expected_fields:
        raise ValueError("pytest workload identity must contain exactly the v1 fields")
    if payload["schema_version"] != PYTEST_WORKLOAD_SCHEMA_VERSION:
        raise ValueError("pytest workload identity has an unsupported schema version")
    if payload["predicate_provenance"] != PYTEST_WORKLOAD_PREDICATE_PROVENANCE:
        raise ValueError("pytest workload identity predicate must be recomputed")
    test_paths = payload["test_paths"]
    if (
        not isinstance(test_paths, list)
        or not test_paths
        or any(not _is_safe_relative_path(path) or not path.endswith(".py") for path in test_paths)
        or len(test_paths) != len(set(test_paths))
    ):
        raise ValueError("pytest workload identity test_paths must be unique relative Python paths")
    source_digests = payload["source_digests"]
    if (
        not isinstance(source_digests, dict)
        or set(source_digests) != set(test_paths)
        or any(not _is_sha256_digest(digest) for digest in source_digests.values())
    ):
        raise ValueError("pytest workload identity must digest every selected source exactly once")
    pytest_version = payload["pytest_version"]
    if not isinstance(pytest_version, str) or not pytest_version.strip():
        raise ValueError("pytest workload identity requires a collector version")
    config_path = payload["config_path"]
    if not _is_safe_relative_path(config_path):
        raise ValueError("pytest workload identity requires a safe config path")
    if not _is_sha256_digest(payload["config_digest"]):
        raise ValueError("pytest workload identity requires a config digest")
    if not _is_sha256_digest(payload["node_map_digest"]):
        raise ValueError("pytest workload identity requires a node-map digest")
    identity = PytestWorkloadIdentity(
        schema_version=payload["schema_version"],
        predicate_provenance=payload["predicate_provenance"],
        test_paths=tuple(test_paths),
        source_digests=tuple((path, source_digests[path]) for path in test_paths),
        pytest_version=pytest_version,
        config_path=config_path,
        config_digest=payload["config_digest"],
        node_map_digest=payload["node_map_digest"],
    )
    _validate_pytest_workload_identity(identity)
    return identity


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
        raise ValueError("timing budget lane recommended_timeout_ms must equal 2 * measured_p95_ms")
    source_refs_data = payload.get("source_refs")
    if (
        not isinstance(source_refs_data, list)
        or not source_refs_data
        or any(
            not isinstance(source_ref, str) or not source_ref.strip()
            for source_ref in source_refs_data
        )
    ):
        raise ValueError("timing budget lane source_refs must be non-empty strings")
    predicate = _required_string(payload, "sample_admission_predicate")
    if predicate not in SAMPLE_ADMISSION_PREDICATE_IDS:
        raise ValueError(
            "timing budget lane sample_admission_predicate must name a known admission rule"
        )
    regime = _required_string(payload, "regime")
    if regime not in SAMPLE_REGIMES:
        raise ValueError("timing budget lane regime must be one of serialized/contended/unknown")
    return TimingBudgetLane(
        timing_key=timing_key,
        tool=tool,
        mode=mode,
        command=_required_string(payload, "command"),
        samples_ms=samples_ms,
        measured_p95_ms=measured_p95_ms,
        recommended_timeout_ms=recommended_timeout_ms,
        source_refs=tuple(source_refs_data),
        workload_identity=_pytest_workload_identity_from_data(
            payload.get("workload_identity")
        ),
        sample_admission_predicate=predicate,
        regime=regime,
        ceiling_is_declared=not samples_ms,
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


def derive_timing_budget_lanes(
    records: list[ToolRunRecord],
    *,
    declarations: Mapping[str, Mapping[str, tuple[int, ...]]] | None = None,
    source_ref: str = "recorded timing log",
) -> list[TimingBudgetLane]:
    """Build budget lanes from what the log actually recorded, not from a requested list.

    The join is the one the catalog already enforces: a record's ``tool`` and ``mode`` compose
    the catalog's ``timing_key`` as ``f"{tool}:{mode}"``. No other correspondence is invented.

    A lane with no admitted sample of its own yields no measured cap. It is returned with empty
    samples and ``ceiling_is_declared`` set, so the caller must supply a ceiling and record it as
    supplied. It never inherits a sibling lane's number -- that substitution is the original
    GY-DI2 defect reappearing one level up.
    """

    resolved = load_healthy_terminal_declarations() if declarations is None else declarations
    grouped: dict[tuple[str, str], list[ToolRunRecord]] = {}
    for record in records:
        grouped.setdefault((record.tool, record.mode), []).append(record)

    lanes: list[TimingBudgetLane] = []
    for (tool, mode), lane_records in grouped.items():
        terminals = healthy_terminal_exit_codes_for(tool, mode, resolved)
        admitted = [
            record
            for record in lane_records
            if admit_duration_sample(record, healthy_terminal_exit_codes=terminals).admitted
        ]
        samples = tuple(sorted(record.duration_ms for record in admitted))
        measured_p95 = round(percentile_ms(list(samples), 0.95), 3) if samples else None
        regimes = {record.regime for record in admitted} or {"unknown"}
        lanes.append(
            TimingBudgetLane(
                timing_key=timing_key_for(tool, mode),
                tool=tool,
                mode=mode,
                command="",
                samples_ms=samples,
                measured_p95_ms=measured_p95,
                recommended_timeout_ms=(measured_p95 * 2 if measured_p95 is not None else None),
                source_refs=(source_ref,),
                sample_admission_predicate=SAMPLE_ADMISSION_PREDICATE_ID,
                regime=regimes.pop() if len(regimes) == 1 else "unknown",
                ceiling_is_declared=not samples,
            )
        )
    return sorted(lanes, key=lambda lane: lane.timing_key)


def uncatalogued_timing_lanes(
    records: list[ToolRunRecord],
    catalog: list[TimingBudgetLane],
    *,
    declarations: Mapping[str, Mapping[str, tuple[int, ...]]] | None = None,
) -> list[TimingBudgetLane]:
    """Lanes the log has seen that the committed catalog does not name.

    This is the point-of-use surface: an executor must be able to learn that its lane is
    unbudgeted BEFORE it spends a run discovering the duration by hitting a timeout.
    """

    catalogued = {lane.timing_key for lane in catalog}
    return [
        lane
        for lane in derive_timing_budget_lanes(records, declarations=declarations)
        if lane.timing_key not in catalogued
    ]


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
            if admit_duration_sample(record, healthy_terminal_exit_codes=healthy_terminals).admitted
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
                budget_basis=lane.budget_basis,
                published_p95_ms=lane.published_p95_ms,
                max_observed_ms=lane.max_observed_ms,
                catalog_sample_count=len(lane.samples_ms),
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
    record_sink: Callable[[ToolRunRecord], None] | None = None,
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
            regime=regime_from_env(),
        )
        if record_sink is not None:
            try:
                record_sink(record)
            except Exception as exc:  # pragma: no cover - defensive telemetry boundary.
                print(f"warning: timing record sink failed: {exc}", file=sys.stderr)
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
