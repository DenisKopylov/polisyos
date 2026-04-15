"""Threshold registry models and helpers for judge stack evaluation."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from polisyos.scientist.autotune.models import default_search_registry_root

__all__ = [
    "JudgeThresholdEntry",
    "JudgeThresholdRegistry",
    "JudgeThresholdSnapshot",
    "ResolvedThresholdSet",
    "ThresholdViolation",
    "_check_threshold_violation",
    "_default_threshold_entries",
    "_is_looser_threshold",
    "_normalize_scope_value",
]


class JudgeThresholdEntry(BaseModel):
    """Versioned threshold entry with optional scope."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    judge_name: str
    metric_name: str
    threshold_value: float
    direction: Literal["max", "min"]
    rationale: str
    benchmark_source: str
    maturity: Literal["provisional", "benchmarked", "hardened"] = "provisional"
    version: int = 1
    last_updated: datetime = Field(default_factory=lambda: datetime.now(UTC))
    scope_family: str | None = None
    scope_query_type: str | None = None
    scope_estimator: str | None = None
    scope_readiness_target: str | None = None
    change_reason: str | None = None
    approved_by: str | None = None

    def scope_key(self) -> tuple[str | None, str | None, str | None, str | None]:
        return (
            self.scope_family,
            self.scope_query_type,
            self.scope_estimator,
            self.scope_readiness_target,
        )


class JudgeThresholdSnapshot(BaseModel):
    """Serializable snapshot of threshold registry contents."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(default="1.0", pattern=r"^\d+\.\d+$")
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    entries: list[JudgeThresholdEntry] = Field(default_factory=list)


class ThresholdViolation(BaseModel):
    """One threshold breach recorded by a judge."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    metric_name: str
    observed_value: float
    threshold_value: float
    threshold_direction: Literal["max", "min"]


class ResolvedThresholdSet(BaseModel):
    """Resolved threshold entries for one judge and one scope."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    judge_name: str
    scope: dict[str, str | None]
    entries: dict[str, JudgeThresholdEntry] = Field(default_factory=dict)
    registry_version: int | None = None

    def threshold_value(self, metric_name: str) -> float | None:
        entry = self.entries.get(metric_name)
        return None if entry is None else float(entry.threshold_value)


class JudgeThresholdRegistry:
    """Versioned runtime authority for judge thresholds."""

    def __init__(self, root: Path | None = None) -> None:
        self._root = (root or default_search_registry_root() / "judge_thresholds").resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    def seed_defaults(self) -> JudgeThresholdSnapshot:
        snapshot = self._load_snapshot()
        if snapshot.entries:
            return snapshot
        seeded = JudgeThresholdSnapshot(entries=_default_threshold_entries())
        self._write_snapshot(seeded)
        return seeded

    def record(
        self,
        entry: JudgeThresholdEntry,
        *,
        allow_loosen: bool = False,
        change_reason: str | None = None,
        approved_by: str | None = None,
    ) -> None:
        snapshot = self._load_snapshot()
        entries = list(snapshot.entries)
        existing = [
            item
            for item in entries
            if item.judge_name == entry.judge_name
            and item.metric_name == entry.metric_name
            and item.scope_key() == entry.scope_key()
        ]
        if existing:
            latest = max(existing, key=lambda item: item.version)
            if not allow_loosen and _is_looser_threshold(entry, latest):
                raise ValueError(
                    "JudgeThresholdRegistry refuses to loosen a threshold without explicit override."
                )
            next_version = latest.version + 1
        else:
            next_version = 1
        entries = [
            item
            for item in entries
            if not (
                item.judge_name == entry.judge_name
                and item.metric_name == entry.metric_name
                and item.scope_key() == entry.scope_key()
            )
        ]
        entries.append(
            entry.model_copy(
                update={
                    "version": next_version,
                    "last_updated": datetime.now(UTC),
                    "change_reason": change_reason or entry.change_reason,
                    "approved_by": approved_by or entry.approved_by,
                }
            )
        )
        self._write_snapshot(
            snapshot.model_copy(
                update={
                    "updated_at": datetime.now(UTC),
                    "entries": entries,
                }
            )
        )

    def resolve(
        self,
        judge_name: str,
        *,
        family: str | None = None,
        query_type: str | None = None,
        estimator: str | None = None,
        readiness_target: str | None = None,
    ) -> ResolvedThresholdSet:
        snapshot = self._load_snapshot()
        scope = {
            "family": _normalize_scope_value(family),
            "query_type": _normalize_scope_value(query_type),
            "estimator": _normalize_scope_value(estimator),
            "readiness_target": _normalize_scope_value(readiness_target),
        }
        resolved: dict[str, JudgeThresholdEntry] = {}
        for metric_name in {
            item.metric_name for item in snapshot.entries if item.judge_name == judge_name
        }:
            entry = self._resolve_one(
                snapshot.entries,
                judge_name=judge_name,
                metric_name=metric_name,
                scope=scope,
            )
            if entry is not None:
                resolved[metric_name] = entry
        return ResolvedThresholdSet(
            judge_name=judge_name,
            scope=scope,
            entries=resolved,
            registry_version=max((item.version for item in resolved.values()), default=None),
        )

    def snapshot(self) -> JudgeThresholdSnapshot:
        return self._load_snapshot()

    def _snapshot_path(self) -> Path:
        return self._root / "judge_threshold_registry.json"

    def _load_snapshot(self) -> JudgeThresholdSnapshot:
        path = self._snapshot_path()
        if not path.exists():
            return JudgeThresholdSnapshot(entries=_default_threshold_entries())
        return JudgeThresholdSnapshot.model_validate_json(path.read_text(encoding="utf-8"))

    def _write_snapshot(self, snapshot: JudgeThresholdSnapshot) -> None:
        path = self._snapshot_path()
        payload = snapshot.model_dump_json(indent=2)
        with NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=path.parent,
            delete=False,
        ) as tmp:
            tmp.write(payload)
            temp_path = Path(tmp.name)
        temp_path.replace(path)

    def _resolve_one(
        self,
        entries: list[JudgeThresholdEntry],
        *,
        judge_name: str,
        metric_name: str,
        scope: dict[str, str | None],
    ) -> JudgeThresholdEntry | None:
        candidates = [
            item
            for item in entries
            if item.judge_name == judge_name and item.metric_name == metric_name
        ]
        family = scope.get("family")
        query_type = scope.get("query_type")
        estimator = scope.get("estimator")
        readiness_target = scope.get("readiness_target")
        resolution_order = [
            (
                family,
                query_type,
                estimator,
                readiness_target,
            ),
            (family, query_type, estimator, None),
            (family, query_type, None, None),
            (family, None, None, None),
            (None, None, None, None),
        ]
        for family, query_type, estimator, readiness_target in resolution_order:
            scoped = [
                item
                for item in candidates
                if item.scope_family == family
                and item.scope_query_type == query_type
                and item.scope_estimator == estimator
                and item.scope_readiness_target == readiness_target
            ]
            if scoped:
                return max(scoped, key=lambda item: item.version)
        return None


def _default_threshold_entries() -> list[JudgeThresholdEntry]:
    return [
        JudgeThresholdEntry(
            judge_name="structural",
            metric_name="proof_precondition_coverage",
            threshold_value=1.0,
            direction="min",
            rationale="Promotion-safe proof artifacts must cover all required preconditions.",
            benchmark_source="phase_a_seed_defaults",
            maturity="benchmarked",
        ),
        JudgeThresholdEntry(
            judge_name="structural",
            metric_name="bounds_consistency_gap",
            threshold_value=0.0,
            direction="max",
            rationale="Lower/upper bounds must remain internally consistent.",
            benchmark_source="phase_a_seed_defaults",
            maturity="benchmarked",
        ),
        JudgeThresholdEntry(
            judge_name="statistical",
            metric_name="statistical_uncertainty_level",
            threshold_value=0.50,
            direction="max",
            rationale="Promotion-safe statistical uncertainty must remain below 0.50.",
            benchmark_source="phase_a_seed_defaults",
            maturity="benchmarked",
        ),
        JudgeThresholdEntry(
            judge_name="robustness",
            metric_name="hidden_holdout_degradation",
            threshold_value=0.10,
            direction="max",
            rationale="Hidden holdout degradation above 10% is not promotion-safe.",
            benchmark_source="phase_a_seed_defaults",
            maturity="benchmarked",
        ),
        JudgeThresholdEntry(
            judge_name="reproducibility",
            metric_name="replay_match",
            threshold_value=0.999,
            direction="min",
            rationale="Promotion-grade replay requires near-perfect deterministic similarity.",
            benchmark_source="phase_a_seed_defaults",
            maturity="benchmarked",
        ),
        JudgeThresholdEntry(
            judge_name="compute",
            metric_name="timeout_risk",
            threshold_value=0.70,
            direction="max",
            rationale="Timeout risk above 0.70 requires compute-side escalation.",
            benchmark_source="phase_a_seed_defaults",
            maturity="benchmarked",
        ),
        JudgeThresholdEntry(
            judge_name="compute",
            metric_name="cost_efficiency",
            threshold_value=1.00,
            direction="min",
            rationale="Expected improvement per USD should stay above 1.0.",
            benchmark_source="phase_a_seed_defaults",
            maturity="benchmarked",
        ),
        JudgeThresholdEntry(
            judge_name="compute",
            metric_name="replay_cost_ratio",
            threshold_value=1.25,
            direction="max",
            rationale="Replay cost should stay within 1.25x of evaluation cost.",
            benchmark_source="phase_a_seed_defaults",
            maturity="benchmarked",
        ),
    ]


def _is_looser_threshold(
    candidate: JudgeThresholdEntry,
    baseline: JudgeThresholdEntry,
) -> bool:
    if candidate.direction != baseline.direction:
        return False
    if candidate.direction == "max":
        return float(candidate.threshold_value) > float(baseline.threshold_value)
    return float(candidate.threshold_value) < float(baseline.threshold_value)


def _check_threshold_violation(
    resolved: ResolvedThresholdSet | None,
    *,
    metric_name: str,
    observed_value: float,
) -> ThresholdViolation | None:
    if resolved is None:
        return None
    entry = resolved.entries.get(metric_name)
    if entry is None:
        return None
    observed = float(observed_value)
    threshold = float(entry.threshold_value)
    violated = (
        observed > threshold
        if entry.direction == "max"
        else observed < threshold
    )
    if not violated:
        return None
    return ThresholdViolation(
        metric_name=metric_name,
        observed_value=observed,
        threshold_value=threshold,
        threshold_direction=entry.direction,
    )


def _normalize_scope_value(value: str | None) -> str | None:
    text = str(value or "").strip()
    return text or None
