"""Threshold registry models and helpers for judge stack evaluation."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from polisyos.foundry.calibration.dp_ci import (
    CITestThresholdPolicy,
    DPContext,
    bucket_dp_delta,
    bucket_dp_epsilon,
    coerce_dp_context,
    normalize_ci_scope_value,
)
from polisyos.foundry.methods.catalog.causal.algebraic_calibration import (
    tetrad_threshold_recommendations,
)
from polisyos.scientist.methods.autotune.models import default_search_registry_root

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
    "bucket_dp_delta",
    "bucket_dp_epsilon",
]


class JudgeThresholdEntry(BaseModel):
    """Versioned threshold entry with optional scope."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    judge_name: str
    metric_name: str
    threshold_value: float
    direction: Literal["max", "min"]
    threshold_tier: Literal["warning", "blocker"] = "blocker"
    rationale: str
    benchmark_source: str
    maturity: Literal["provisional", "benchmarked", "hardened"] = "provisional"
    version: int = 1
    last_updated: datetime = Field(default_factory=lambda: datetime.now(UTC))
    scope_family: str | None = None
    scope_query_type: str | None = None
    scope_estimator: str | None = None
    scope_readiness_target: str | None = None
    scope_dp_mechanism: str | None = None
    scope_dp_epsilon_bucket: str | None = None
    scope_dp_delta_bucket: str | None = None
    change_reason: str | None = None
    approved_by: str | None = None

    def scope_key(
        self,
    ) -> tuple[
        str | None,
        str | None,
        str | None,
        str | None,
        str | None,
        str | None,
        str | None,
        str,
    ]:
        return (
            self.scope_family,
            self.scope_query_type,
            self.scope_estimator,
            self.scope_readiness_target,
            self.scope_dp_mechanism,
            self.scope_dp_epsilon_bucket,
            self.scope_dp_delta_bucket,
            self.threshold_tier,
        )

    def resolved_key(self) -> str:
        if self.threshold_tier == "blocker":
            return self.metric_name
        return f"{self.metric_name}:{self.threshold_tier}"


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

    def threshold_value(
        self,
        metric_name: str,
        *,
        threshold_tier: Literal["warning", "blocker"] = "blocker",
    ) -> float | None:
        key = metric_name if threshold_tier == "blocker" else f"{metric_name}:{threshold_tier}"
        entry = self.entries.get(key)
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
                    "JudgeThresholdRegistry refuses to loosen a threshold "
                    "without explicit override."
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
        dp_mechanism: str | None = None,
        dp_epsilon: float | str | None = None,
        dp_delta: float | str | None = None,
    ) -> ResolvedThresholdSet:
        snapshot = self._load_snapshot()
        scope = {
            "family": _normalize_scope_value(family),
            "query_type": _normalize_scope_value(query_type),
            "estimator": _normalize_scope_value(estimator),
            "readiness_target": _normalize_scope_value(readiness_target),
            "dp_mechanism": _normalize_scope_value(dp_mechanism),
            "dp_epsilon_bucket": bucket_dp_epsilon(dp_epsilon),
            "dp_delta_bucket": bucket_dp_delta(dp_delta),
        }
        resolved: dict[str, JudgeThresholdEntry] = {}
        for metric_name, threshold_tier in {
            (item.metric_name, item.threshold_tier)
            for item in snapshot.entries
            if item.judge_name == judge_name
        }:
            entry = self._resolve_one(
                snapshot.entries,
                judge_name=judge_name,
                metric_name=metric_name,
                threshold_tier=threshold_tier,
                scope=scope,
            )
            if entry is not None:
                resolved[entry.resolved_key()] = entry
        return ResolvedThresholdSet(
            judge_name=judge_name,
            scope=scope,
            entries=resolved,
            registry_version=max((item.version for item in resolved.values()), default=None),
        )

    def resolve_ci_test_policy(
        self,
        *,
        family: Literal["kernel_ci", "categorical_ci"],
        query_type: str,
        estimator: str,
        dp_context: DPContext | Mapping[str, object] | None = None,
        alpha: float = 0.05,
        n_bootstrap: int = 299,
        readiness_target: str = "diagnostic",
    ) -> CITestThresholdPolicy:
        """Resolve one CI policy above Foundry's execution boundary."""

        context = coerce_dp_context(dp_context)
        default_policy = CITestThresholdPolicy(
            alpha_base=float(alpha),
            mc_bootstrap_B=int(n_bootstrap),
        )
        resolved = self.resolve(
            "ci_tests",
            family=family,
            query_type=query_type,
            estimator=estimator,
            readiness_target=readiness_target,
            dp_mechanism=None if context is None else context.mechanism,
            dp_epsilon=None if context is None else context.epsilon,
            dp_delta=None if context is None else context.delta,
        )
        alpha_base = resolved.threshold_value("alpha_base")
        mc_bootstrap_B = resolved.threshold_value("mc_bootstrap_B")
        min_n_rule_constant = resolved.threshold_value("min_n_rule_constant")
        naive_fpr_bound_rho = resolved.threshold_value("naive_fpr_bound_rho")
        return CITestThresholdPolicy(
            alpha_base=float(alpha_base if alpha_base is not None else alpha),
            mc_bootstrap_B=int(
                round(mc_bootstrap_B if mc_bootstrap_B is not None else n_bootstrap)
            ),
            min_n_rule_constant=float(
                min_n_rule_constant
                if min_n_rule_constant is not None
                else default_policy.min_n_rule_constant
            ),
            naive_fpr_bound_rho=float(
                naive_fpr_bound_rho
                if naive_fpr_bound_rho is not None
                else default_policy.naive_fpr_bound_rho
            ),
            threshold_scope=dict(resolved.scope),
            threshold_registry_version=resolved.registry_version,
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
        threshold_tier: Literal["warning", "blocker"],
        scope: dict[str, str | None],
    ) -> JudgeThresholdEntry | None:
        candidates = [
            item
            for item in entries
            if item.judge_name == judge_name
            and item.metric_name == metric_name
            and item.threshold_tier == threshold_tier
        ]
        ranked: list[tuple[int, int, JudgeThresholdEntry]] = []
        for item in candidates:
            score = _scope_match_score(item, scope)
            if score is None:
                continue
            ranked.append((score, item.version, item))
        if not ranked:
            return None
        ranked.sort(key=lambda payload: (payload[0], payload[1]), reverse=True)
        return ranked[0][2]


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
        *_default_algebraic_tetrad_threshold_entries(),
        *_default_ci_threshold_entries(),
    ]


def _default_algebraic_tetrad_threshold_entries() -> list[JudgeThresholdEntry]:
    source = "stage_8_2_tetrad_finite_sample_research"
    family = "algebraic_tetrad"
    return [
        *(
            JudgeThresholdEntry(
                judge_name="statistical",
                metric_name=recommendation.metric_name,
                threshold_value=float(recommendation.threshold_value),
                direction=recommendation.direction,
                threshold_tier=recommendation.threshold_tier,
                rationale=recommendation.rationale,
                benchmark_source=source,
                maturity="provisional",
                scope_family=family,
            )
            for recommendation in tetrad_threshold_recommendations()
        ),
    ]


def _default_ci_threshold_entries() -> list[JudgeThresholdEntry]:
    source = "stage_15_2_dp_ci_research"
    return [
        JudgeThresholdEntry(
            judge_name="ci_tests",
            metric_name="alpha_base",
            threshold_value=0.05,
            direction="max",
            rationale="Default CI alpha for kernel-family diagnostics.",
            benchmark_source=source,
            maturity="provisional",
            scope_family="kernel_ci",
        ),
        JudgeThresholdEntry(
            judge_name="ci_tests",
            metric_name="mc_bootstrap_B",
            threshold_value=299,
            direction="min",
            rationale="Kernel CI permutation nulls should use at least 299 draws by default.",
            benchmark_source=source,
            maturity="provisional",
            scope_family="kernel_ci",
        ),
        JudgeThresholdEntry(
            judge_name="ci_tests",
            metric_name="min_n_rule_constant",
            threshold_value=4.0,
            direction="min",
            rationale="Kernel DP sample-size rules use a conservative constant of 4.0.",
            benchmark_source=source,
            maturity="provisional",
            scope_family="kernel_ci",
        ),
        JudgeThresholdEntry(
            judge_name="ci_tests",
            metric_name="naive_fpr_bound_rho",
            threshold_value=0.01,
            direction="max",
            rationale="Naive kernel-DP FPR inflation bounds allocate 1% residual tail mass.",
            benchmark_source=source,
            maturity="provisional",
            scope_family="kernel_ci",
        ),
        JudgeThresholdEntry(
            judge_name="ci_tests",
            metric_name="alpha_base",
            threshold_value=0.05,
            direction="max",
            rationale="Default CI alpha for categorical G²/χ² diagnostics.",
            benchmark_source=source,
            maturity="provisional",
            scope_family="categorical_ci",
        ),
        JudgeThresholdEntry(
            judge_name="ci_tests",
            metric_name="mc_bootstrap_B",
            threshold_value=2000,
            direction="min",
            rationale="Categorical DP Monte Carlo calibration uses at least 2000 null draws.",
            benchmark_source=source,
            maturity="provisional",
            scope_family="categorical_ci",
        ),
        JudgeThresholdEntry(
            judge_name="ci_tests",
            metric_name="mc_bootstrap_B",
            threshold_value=4000,
            direction="min",
            rationale="Laplace-count releases need a larger Monte Carlo null to stabilize CI thresholds.",
            benchmark_source=source,
            maturity="provisional",
            scope_family="categorical_ci",
            scope_dp_mechanism="laplace_counts",
        ),
        JudgeThresholdEntry(
            judge_name="ci_tests",
            metric_name="min_n_rule_constant",
            threshold_value=4.0,
            direction="min",
            rationale="Categorical DP sample-size rules use a conservative constant of 4.0.",
            benchmark_source=source,
            maturity="provisional",
            scope_family="categorical_ci",
        ),
        JudgeThresholdEntry(
            judge_name="ci_tests",
            metric_name="naive_fpr_bound_rho",
            threshold_value=0.01,
            direction="max",
            rationale="Naive categorical-DP FPR inflation bounds allocate 1% residual tail mass.",
            benchmark_source=source,
            maturity="provisional",
            scope_family="categorical_ci",
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
    threshold_tier: Literal["warning", "blocker"] = "blocker",
) -> ThresholdViolation | None:
    if resolved is None:
        return None
    key = metric_name if threshold_tier == "blocker" else f"{metric_name}:{threshold_tier}"
    entry = resolved.entries.get(key)
    if entry is None:
        return None
    observed = float(observed_value)
    threshold = float(entry.threshold_value)
    violated = observed > threshold if entry.direction == "max" else observed < threshold
    if not violated:
        return None
    return ThresholdViolation(
        metric_name=metric_name,
        observed_value=observed,
        threshold_value=threshold,
        threshold_direction=entry.direction,
    )


_normalize_scope_value = normalize_ci_scope_value


def _scope_match_score(
    entry: JudgeThresholdEntry,
    scope: dict[str, str | None],
) -> int | None:
    fields = (
        ("family", entry.scope_family, 64),
        ("query_type", entry.scope_query_type, 32),
        ("estimator", entry.scope_estimator, 16),
        ("readiness_target", entry.scope_readiness_target, 8),
        ("dp_mechanism", entry.scope_dp_mechanism, 4),
        ("dp_epsilon_bucket", entry.scope_dp_epsilon_bucket, 2),
        ("dp_delta_bucket", entry.scope_dp_delta_bucket, 1),
    )
    score = 0
    for scope_name, entry_value, weight in fields:
        requested = scope.get(scope_name)
        if entry_value is None:
            continue
        if entry_value != requested:
            return None
        score += weight
    return score
