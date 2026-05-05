"""Execution history store and runtime predictor for evidence-conditioned method selection.

Phase 5 of FOUNDRY_SOTA_PLAN: records method execution outcomes and uses them
to improve selection scoring via success rates, quality quantiles, and
predicted runtimes.
"""

from __future__ import annotations

import logging
import math
import threading
import time
from collections import defaultdict, deque
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

_log = logging.getLogger("foundry.selection_history")
ADVISOR_EXECUTION_CONTEXT_PARAM = "__advisor_execution_context__"


class MethodExecutionRecord(BaseModel):
    """Single method execution outcome for selection learning."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    method_fqn: str = Field(..., min_length=1)
    timestamp: float
    latency_ms: float = Field(ge=0.0)
    success: bool
    output_quality: float | None = Field(default=None, ge=0.0, le=1.0)
    data_characteristics: dict[str, Any] = Field(default_factory=dict)
    failure_type: str | None = None
    runtime_truthfulness_tier: str | None = None
    effective_truthfulness_tier: str | None = None
    truthfulness_scope: str | None = None
    truthfulness_status: str | None = None
    truthfulness_evidence_ref: str | None = None
    query_fingerprint: str | None = None
    loss_profile_id: str | None = None
    candidate_fqns: tuple[str, ...] = Field(default_factory=tuple)
    selected_rank: int | None = Field(default=None, ge=1)
    selection_propensity: float | None = Field(default=None, gt=0.0, le=1.0)
    advisor_score_vector: dict[str, float] = Field(default_factory=dict)
    realized_loss_components: dict[str, float] = Field(default_factory=dict)
    shadow_loss_estimates: dict[str, float] = Field(default_factory=dict)


class AdvisorExecutionContext(BaseModel):
    """Selection-time telemetry that should be preserved through execution."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    query_fingerprint: str = Field(..., min_length=1)
    loss_profile_id: str | None = None
    candidate_fqns: tuple[str, ...] = Field(default_factory=tuple)
    selected_rank: int | None = Field(default=None, ge=1)
    selection_propensity: float | None = Field(default=None, gt=0.0, le=1.0)
    advisor_score_vector: dict[str, float] = Field(default_factory=dict)
    shadow_loss_estimates: dict[str, float] = Field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class SelectionHistoryPersistenceIssue:
    """Bounded diagnostic record for append/export/import persistence failures."""

    operation: str
    path: str
    message: str
    timestamp: float


class SelectionHistoryStore:
    """
    Thread-safe store for method execution history.

    In-memory state and optional JSONL persistence are synchronized
    independently so concurrent writers cannot interleave partial file appends.
    """

    _MAX_PERSISTENCE_ISSUES = 64

    def __init__(
        self,
        *,
        persist_path: Path | str | None = None,
        auto_persist: bool = False,
    ) -> None:
        self._by_fqn: dict[str, list[MethodExecutionRecord]] = defaultdict(list)
        self._lock = threading.Lock()
        self._persist_lock = threading.Lock()
        self._persist_path = Path(persist_path) if persist_path is not None else None
        self._auto_persist = auto_persist
        self._persistence_issues: deque[SelectionHistoryPersistenceIssue] = deque(
            maxlen=self._MAX_PERSISTENCE_ISSUES
        )

    def record(self, rec: MethodExecutionRecord) -> None:
        """Append an execution record."""
        with self._lock:
            self._by_fqn[rec.method_fqn].append(rec)
        if self._auto_persist and self._persist_path is not None:
            self._append_jsonl(rec, self._persist_path)

    def success_rate(self, fqn: str, *, window_hours: float = 168) -> float | None:
        """Return success rate in [0, 1] within time window, or None if no records."""
        cutoff = time.time() - window_hours * 3600
        with self._lock:
            records = [r for r in self._by_fqn.get(fqn, []) if r.timestamp >= cutoff]
        if not records:
            return None
        return sum(1 for r in records if r.success) / len(records)

    def mean_latency_ms(self, fqn: str) -> float | None:
        """Return mean latency across all records for *fqn*, or None if no records."""
        with self._lock:
            records = list(self._by_fqn.get(fqn, []))
        if not records:
            return None
        return sum(r.latency_ms for r in records) / len(records)

    def quality_quantiles(self, fqn: str) -> tuple[float, float, float] | None:
        """Return (p25, p50, p75) of output_quality, or None if < 3 records have quality."""
        with self._lock:
            values = [
                r.output_quality for r in self._by_fqn.get(fqn, []) if r.output_quality is not None
            ]
        if len(values) < 3:
            return None
        values.sort()
        n = len(values)

        def _percentile(data: list[float], p: float) -> float:
            k = (n - 1) * p
            f = int(k)
            c = f + 1
            if c >= n:
                return data[-1]
            return data[f] + (k - f) * (data[c] - data[f])

        return (_percentile(values, 0.25), _percentile(values, 0.50), _percentile(values, 0.75))

    def records_for(self, fqn: str) -> list[MethodExecutionRecord]:
        """Return a copy of all records for *fqn*."""
        with self._lock:
            return list(self._by_fqn.get(fqn, []))

    def latest_record_for(self, fqn: str) -> MethodExecutionRecord | None:
        """Return the most recent record for *fqn*, or None when absent."""
        with self._lock:
            records = self._by_fqn.get(fqn, [])
            if not records:
                return None
            return max(records, key=lambda item: item.timestamp)

    def all_records(self) -> list[MethodExecutionRecord]:
        """Return a flat copy of all records across all FQNs."""
        with self._lock:
            return [r for records in self._by_fqn.values() for r in records]

    def clear(self) -> None:
        """Remove all records."""
        with self._lock:
            self._by_fqn.clear()

    def persistence_issues(self) -> list[SelectionHistoryPersistenceIssue]:
        """Return a bounded history of JSONL persistence failures."""
        with self._persist_lock:
            return list(self._persistence_issues)

    @property
    def persist_path(self) -> Path | None:
        """Return the configured JSONL persistence path, if any."""
        return self._persist_path

    def export_jsonl(self, path: Path | str | None = None) -> Path:
        """Write all records to a JSONL file and return the resolved path."""
        target = Path(path) if path is not None else self._require_persist_path()
        records = self.all_records()
        try:
            with self._persist_lock:
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open("w", encoding="utf-8") as fh:
                    for record in records:
                        fh.write(record.model_dump_json())
                        fh.write("\n")
        except OSError as exc:
            self._record_persistence_issue("export", target, exc)
            raise
        return target

    def import_jsonl(
        self,
        path: Path | str | None = None,
        *,
        clear_existing: bool = False,
    ) -> int:
        """Load records from a JSONL file. Returns the number of imported rows."""
        target = Path(path) if path is not None else self._require_persist_path()
        if not target.exists():
            return 0
        if clear_existing:
            self.clear()
        imported = 0
        try:
            with self._persist_lock, target.open("r", encoding="utf-8") as fh:
                for line in fh:
                    payload = line.strip()
                    if not payload:
                        continue
                    record = MethodExecutionRecord.model_validate_json(payload)
                    with self._lock:
                        self._by_fqn[record.method_fqn].append(record)
                    imported += 1
        except OSError as exc:
            self._record_persistence_issue("import", target, exc)
            raise
        return imported

    def __len__(self) -> int:
        with self._lock:
            return sum(len(v) for v in self._by_fqn.values())

    def _require_persist_path(self) -> Path:
        if self._persist_path is None:
            raise ValueError("SelectionHistoryStore has no persistence path configured")
        return self._persist_path

    def _append_jsonl(self, record: MethodExecutionRecord, path: Path) -> None:
        try:
            with self._persist_lock:
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open("a", encoding="utf-8") as fh:
                    fh.write(record.model_dump_json())
                    fh.write("\n")
        except OSError as exc:
            self._record_persistence_issue("append", path, exc)

    def _record_persistence_issue(
        self,
        operation: str,
        path: Path,
        exc: OSError,
    ) -> None:
        issue = SelectionHistoryPersistenceIssue(
            operation=operation,
            path=str(path),
            message=str(exc),
            timestamp=time.time(),
        )
        with self._persist_lock:
            self._persistence_issues.append(issue)
        _log.warning(
            "selection_history_persist_failed op=%s path=%s exc=%s",
            operation,
            path,
            type(exc).__name__,
        )


_MIN_FIT_RECORDS = 5
_MIN_METHOD_RESIDUAL_RECORDS = 3


class RuntimePredictor:
    """Predict method execution time from data characteristics.

    Model: ``log(latency_ms) ~ intercept + slope_obs * log(n_obs) + slope_feat * log(n_features)``

    When not fitted (or insufficient data), returns estimates using sensible defaults.
    """

    _DEFAULT_INTERCEPT: float = 2.0  # ~exp(2) ≈ 7.4 ms baseline
    _DEFAULT_SLOPE_OBS: float = 0.7
    _DEFAULT_SLOPE_FEAT: float = 0.3

    def __init__(self) -> None:
        self._intercept: float = self._DEFAULT_INTERCEPT
        self._slope_obs: float = self._DEFAULT_SLOPE_OBS
        self._slope_feat: float = self._DEFAULT_SLOPE_FEAT
        self._fitted: bool = False
        self._method_intercepts: dict[str, float] = {}
        self._backend_intercepts: dict[str, float] = {}
        self._method_backend_intercepts: dict[tuple[str, str], float] = {}

    def predict_ms(
        self,
        fqn: str,
        n_obs: int,
        n_features: int = 1,
        *,
        backend: str | None = None,
    ) -> float:
        """Predict runtime in milliseconds. Always returns a positive finite value."""
        log_latency = (
            self._intercept
            + self._slope_obs * math.log(max(n_obs, 1))
            + self._slope_feat * math.log(max(n_features, 1))
            + self._method_intercepts.get(fqn, 0.0)
        )
        if backend is not None:
            normalized_backend = str(backend).strip().lower()
            log_latency += self._backend_intercepts.get(normalized_backend, 0.0)
            log_latency += self._method_backend_intercepts.get(
                (fqn, normalized_backend),
                0.0,
            )
        return math.exp(log_latency)

    def fit(self, history: SelectionHistoryStore) -> None:
        """Fit coefficients via OLS on log-transformed data.

        Requires >= ``_MIN_FIT_RECORDS`` records with ``n_obs`` in
        ``data_characteristics``; otherwise keeps defaults.
        """
        all_records = history.all_records()
        rows: list[tuple[str, str | None, float, float, float]] = []
        for rec in all_records:
            n_obs = rec.data_characteristics.get("n_obs")
            if n_obs is None or n_obs < 1 or rec.latency_ms <= 0:
                continue
            n_features = max(rec.data_characteristics.get("n_features", 1), 1)
            backend = rec.data_characteristics.get("backend")
            backend_name = (
                str(backend).strip().lower()
                if backend is not None and str(backend).strip()
                else None
            )
            rows.append(
                (
                    rec.method_fqn,
                    backend_name,
                    math.log(n_obs),
                    math.log(n_features),
                    math.log(rec.latency_ms),
                )
            )

        if len(rows) < _MIN_FIT_RECORDS:
            self._fitted = False
            self._method_intercepts.clear()
            self._backend_intercepts.clear()
            self._method_backend_intercepts.clear()
            return

        X = np.array([[1.0, r[2], r[3]] for r in rows])
        y = np.array([r[4] for r in rows])
        coeffs, *_ = np.linalg.lstsq(X, y, rcond=None)
        self._intercept = float(coeffs[0])
        self._slope_obs = float(coeffs[1])
        self._slope_feat = float(coeffs[2])
        residuals_by_fqn: dict[str, list[float]] = defaultdict(list)
        residuals_by_backend: dict[str, list[float]] = defaultdict(list)
        residuals_by_method_backend: dict[tuple[str, str], list[float]] = defaultdict(list)
        for fqn, backend, log_n_obs, log_n_features, log_latency in rows:
            baseline = (
                self._intercept + self._slope_obs * log_n_obs + self._slope_feat * log_n_features
            )
            residual = log_latency - baseline
            residuals_by_fqn[fqn].append(residual)
            if backend is not None:
                residuals_by_backend[backend].append(residual)
                residuals_by_method_backend[(fqn, backend)].append(residual)
        self._method_intercepts = {
            fqn: float(np.mean(residuals))
            for fqn, residuals in residuals_by_fqn.items()
            if len(residuals) >= _MIN_METHOD_RESIDUAL_RECORDS
        }
        self._backend_intercepts = {
            backend: float(np.mean(residuals))
            for backend, residuals in residuals_by_backend.items()
            if len(residuals) >= _MIN_METHOD_RESIDUAL_RECORDS
        }
        self._method_backend_intercepts = {
            key: float(np.mean(residuals))
            for key, residuals in residuals_by_method_backend.items()
            if len(residuals) >= _MIN_METHOD_RESIDUAL_RECORDS
        }
        self._fitted = True

    @property
    def is_fitted(self) -> bool:
        return self._fitted


_DEFAULT_HISTORY_PATH = (
    Path(__file__).resolve().parents[4]
    / "_build"
    / "benchmark-results"
    / "foundry"
    / "selection_history"
    / "executions.jsonl"
)
_GLOBAL_HISTORY_LOCK = threading.Lock()
_GLOBAL_HISTORY: SelectionHistoryStore | None = None


def get_global_selection_history() -> SelectionHistoryStore:
    """Return the process-global execution history store."""
    global _GLOBAL_HISTORY
    with _GLOBAL_HISTORY_LOCK:
        if _GLOBAL_HISTORY is None:
            _GLOBAL_HISTORY = SelectionHistoryStore(
                persist_path=_DEFAULT_HISTORY_PATH,
                auto_persist=True,
            )
    return _GLOBAL_HISTORY


def fit_runtime_predictor_from_history(
    history: SelectionHistoryStore | None = None,
) -> RuntimePredictor:
    """Fit a predictor from the provided history or the global store."""
    predictor = RuntimePredictor()
    predictor.fit(get_global_selection_history() if history is None else history)
    return predictor


def split_advisor_execution_params(
    params: Mapping[str, Any] | None,
) -> tuple[dict[str, Any], AdvisorExecutionContext | None]:
    """Split advisor-only execution context from regular method params."""

    payload = dict(params or {})
    raw_context = payload.pop(ADVISOR_EXECUTION_CONTEXT_PARAM, None)
    if raw_context is None:
        return payload, None
    if isinstance(raw_context, AdvisorExecutionContext):
        return payload, raw_context
    return payload, AdvisorExecutionContext.model_validate(raw_context)


__all__ = [
    "ADVISOR_EXECUTION_CONTEXT_PARAM",
    "AdvisorExecutionContext",
    "MethodExecutionRecord",
    "RuntimePredictor",
    "SelectionHistoryPersistenceIssue",
    "SelectionHistoryStore",
    "fit_runtime_predictor_from_history",
    "get_global_selection_history",
    "split_advisor_execution_params",
]
