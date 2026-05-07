"""Public search stages module API."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from polisyos.common.logger import get_logger
from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.scientist.orchestration.workflows.engine_base import WorkflowEngine

logger = get_logger(__name__)


@dataclass
class StageResult:
    """Result from a search stage evaluation."""

    policy_candidate: dict[str, Any]
    objective_value: float
    is_promising: bool

    stage_name: str
    duration_seconds: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    simulation_results: dict[str, Any] = field(default_factory=dict)
    feedback: dict[str, Any] = field(default_factory=dict)

    predicted_score: float | None = None
    actual_score: float | None = None


class SearchStage(ABC):
    """Abstract search stage for policy evaluation."""

    @property
    @abstractmethod
    def stage_name(self) -> str:
        """Unique identifier for this stage."""
        ...

    @abstractmethod
    def evaluate(
        self,
        candidate: dict[str, Any],
        context: dict[str, Any],
    ) -> StageResult:
        """
        Evaluate a policy candidate.

        Args:
            candidate: Policy IR or policy-like dict
            context: Additional context (user_request, etc.)

        Returns:
            StageResult with evaluation details
        """
        ...


class CheapStage(SearchStage):
    """
    Stage A: Fast, cheap evaluation using heuristics/surrogate.

    Purpose:
        Filter obviously bad candidates before expensive Foundry runs.
    """

    def __init__(
        self,
        threshold: float | None = None,
        enable_parameter_checks: bool = True,
        enable_structure_checks: bool = True,
    ):
        from polisyos.scientist.methods.autotune.cheap_stage import resolve_cheap_stage_threshold

        self._threshold = resolve_cheap_stage_threshold(threshold)
        self._param_checks = enable_parameter_checks
        self._struct_checks = enable_structure_checks

    @property
    def stage_name(self) -> str:
        return "cheap"

    def evaluate(
        self,
        candidate: dict[str, Any],
        context: dict[str, Any],
    ) -> StageResult:
        start = datetime.now(UTC)

        issues: list[str] = []
        score = 0.0

        semantic = candidate.get("semantic", {})
        interventions = semantic.get("interventions", [])

        if self._struct_checks:
            score += self._check_structure(candidate, issues)

        if self._param_checks:
            score += self._check_parameters(interventions, issues)

        duration = (datetime.now(UTC) - start).total_seconds()
        is_promising = score < self._threshold

        if not is_promising:
            logger.debug(
                f"CheapStage rejected candidate: score={score:.4f}, "
                f"threshold={self._threshold}, issues={issues}"
            )

        return StageResult(
            policy_candidate=candidate,
            objective_value=score,
            is_promising=is_promising,
            stage_name=self.stage_name,
            duration_seconds=duration,
            predicted_score=score,
        )

    def _check_structure(
        self,
        candidate: dict[str, Any],
        issues: list[str],
    ) -> float:
        """Check policy structure completeness."""
        score = 0.0

        if "semantic" not in candidate:
            issues.append("Missing 'semantic' layer")
            score += 0.3

        semantic = candidate.get("semantic", {})

        if not semantic.get("interventions"):
            issues.append("No interventions defined")
            score += 0.2

        if not semantic.get("objectives"):
            issues.append("No objectives defined")
            score += 0.1

        return score

    def _check_parameters(
        self,
        interventions: list[dict[str, Any]],
        issues: list[str],
    ) -> float:
        """Check parameter sanity."""
        score = 0.0

        for i, intervention in enumerate(interventions):
            params = intervention.get("parameters", {})

            for key, value in params.items():
                if not isinstance(value, (int, float)):
                    continue

                if value != value:
                    issues.append(f"Intervention {i}: NaN value for {key}")
                    score += 0.5

                if abs(value) == float("inf"):
                    issues.append(f"Intervention {i}: Infinite value for {key}")
                    score += 0.5

                if "rate" in key.lower() or "tax" in key.lower():
                    if value < 0 or value > 1:
                        issues.append(f"Intervention {i}: {key}={value} outside [0,1]")
                        score += 0.5

                if abs(value) > 1e6:
                    issues.append(f"Intervention {i}: Extreme value {key}={value}")
                    score += 0.1

        return score


class ExpensiveStage(SearchStage):
    """
    Stage B: Full Foundry simulation.

    Purpose:
        Run complete simulation workflow for accurate evaluation.
        Only executed for candidates that pass Stage A.
    """

    def __init__(self, workflow_engine: WorkflowEngine):
        self._engine = workflow_engine

    @property
    def stage_name(self) -> str:
        return "expensive"

    def evaluate(
        self,
        candidate: dict[str, Any],
        context: dict[str, Any],
    ) -> StageResult:
        start = datetime.now(UTC)

        initial_state = {
            "ir": candidate,
            "user_request": context.get("user_request", ""),
            "optimize": True,
            **{k: v for k, v in context.items() if k not in ("ir", "user_request")},
        }

        try:
            result = self._engine.run(initial_state)
        except Exception as exc:
            logger.error(f"ExpensiveStage workflow failed: {exc}")
            return StageResult(
                policy_candidate=candidate,
                objective_value=float("inf"),
                is_promising=False,
                stage_name=self.stage_name,
                duration_seconds=(datetime.now(UTC) - start).total_seconds(),
                feedback={"verdict": "REJECT", "issues": [{"message": str(exc)}]},
            )

        duration = (datetime.now(UTC) - start).total_seconds()

        sim_results = result.get("simulation_results", {})
        feedback = result.get("feedback", {})
        verdict = feedback.get("verdict", "UNKNOWN")

        objective = self._compute_default_objective(sim_results)

        is_promising = verdict == "APPROVE"

        return StageResult(
            policy_candidate=candidate,
            objective_value=objective,
            is_promising=is_promising,
            stage_name=self.stage_name,
            duration_seconds=duration,
            simulation_results=sim_results,
            feedback=feedback,
            actual_score=objective,
        )

    def _compute_default_objective(self, results: dict[str, Any]) -> float:
        """Compute simple objective from simulation results."""
        gdp = results.get("gdp_change", 0.0)
        deficit = abs(min(results.get("gov_balance", 0.0), 0))

        return -(gdp - 0.5 * deficit)


# ─────────────────────────────────────────────────────────────────────────────
# Correlation Tracking (Risk Mitigation B)
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class CorrelationRecord:
    """Record for tracking cheap-to-expensive calibration health."""

    candidate_hash: str
    stage_a_score: float
    stage_b_score: float
    stage_a_passed: bool
    stage_b_approved: bool
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    is_sentinel: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DriftAlert:
    """Structured calibration alert emitted by the tracker."""

    code: str
    severity: str
    message: str
    metrics: dict[str, Any] = field(default_factory=dict)
    recommended_action: str | None = None


class CorrelationRecordSnapshot(BaseModel):
    """Serializable snapshot record for correlation tracker persistence."""

    model_config = ConfigDict(extra="forbid")

    candidate_hash: str
    stage_a_score: float
    stage_b_score: float
    stage_a_passed: bool
    stage_b_approved: bool
    timestamp: datetime
    is_sentinel: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class CorrelationTrackerSnapshot(BaseModel):
    """Serializable tracker snapshot used by burn-in/reporting helpers."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(default="1.0", pattern=r"^\d+\.\d+$")
    max_records: int = Field(ge=1)
    drift_window_size: int = Field(ge=2)
    spearman_warning_threshold: float
    promotion_ban_threshold: float
    false_negative_ceiling: float
    sentinel_pass_floor: float
    records: list[CorrelationRecordSnapshot] = Field(default_factory=list)


class CorrelationTracker:
    """
    Tracks correlation between Stage A predictions and expensive-stage truth.

    Keeps the legacy CheapStage tuning API intact while adding drift alerts,
    rolling-window analysis, and optional sentinel monitoring for the funnel.
    """

    def __init__(
        self,
        max_records: int = 1000,
        *,
        drift_window_size: int = 20,
        spearman_warning_threshold: float = 0.6,
        promotion_ban_threshold: float = 0.5,
        false_negative_ceiling: float = 0.02,
        sentinel_pass_floor: float = 0.9,
    ):
        self._records: list[CorrelationRecord] = []
        self._max_records = max_records
        self._drift_window_size = max(2, int(drift_window_size))
        self._spearman_warning_threshold = float(spearman_warning_threshold)
        self._promotion_ban_threshold = float(promotion_ban_threshold)
        self._false_negative_ceiling = float(false_negative_ceiling)
        self._sentinel_pass_floor = float(sentinel_pass_floor)

    @property
    def record_count(self) -> int:
        return len(self._records)

    def record(
        self,
        stage_a_result: StageResult,
        stage_b_result: StageResult | None,
        candidate_hash: str,
        *,
        is_sentinel: bool = False,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Record a correlation data point."""
        if stage_b_result is None:
            return

        record = CorrelationRecord(
            candidate_hash=candidate_hash,
            stage_a_score=stage_a_result.predicted_score or stage_a_result.objective_value,
            stage_b_score=stage_b_result.actual_score or stage_b_result.objective_value,
            stage_a_passed=stage_a_result.is_promising,
            stage_b_approved=stage_b_result.is_promising,
            is_sentinel=bool(is_sentinel),
            metadata=dict(metadata or {}),
        )

        self._records.append(record)

        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]

    def false_negative_rate(
        self,
        *,
        window_size: int | None = None,
    ) -> float:
        records = self._window(window_size)
        rejected = [record for record in records if not record.stage_a_passed]
        if not rejected:
            return 0.0
        false_negatives = sum(1 for record in rejected if record.stage_b_approved)
        return false_negatives / len(rejected)

    def sentinel_pass_rate(
        self,
        *,
        window_size: int | None = None,
    ) -> float | None:
        records = [record for record in self._window(window_size) if record.is_sentinel]
        if not records:
            return None
        passed = sum(1 for record in records if record.stage_a_passed)
        return passed / len(records)

    def drift_alerts(
        self,
        *,
        window_size: int | None = None,
    ) -> list[DriftAlert]:
        records = self._window(window_size)
        metrics = self._metrics_for_records(records)
        sentinel_pass_rate = self.sentinel_pass_rate(window_size=len(records))
        alerts: list[DriftAlert] = []

        spearman = float(metrics.get("spearman_correlation", 0.0))
        if spearman < self._promotion_ban_threshold:
            alerts.append(
                DriftAlert(
                    code="PROMOTION_BAN",
                    severity="critical",
                    message="Cheap-to-expensive correlation dropped below promotion-ban threshold.",
                    metrics={"spearman_correlation": spearman},
                    recommended_action="Disable promotions and run calibration burn-in.",
                )
            )
        elif spearman < self._spearman_warning_threshold:
            alerts.append(
                DriftAlert(
                    code="CALIBRATION_DRIFT",
                    severity="warning",
                    message="Cheap-to-expensive correlation dropped below warning threshold.",
                    metrics={"spearman_correlation": spearman},
                    recommended_action=(
                        "Disable VOI and route survivors sequentially through medium fidelity."
                    ),
                )
            )

        false_negative_rate = float(metrics.get("false_negative_rate", 0.0))
        if false_negative_rate > self._false_negative_ceiling:
            alerts.append(
                DriftAlert(
                    code="FALSE_NEGATIVE_SPIKE",
                    severity="warning",
                    message="False-negative rate exceeded the configured ceiling.",
                    metrics={"false_negative_rate": false_negative_rate},
                    recommended_action="Recalibrate cheap-stage rejection thresholds.",
                )
            )

        if sentinel_pass_rate is not None and float(sentinel_pass_rate) < self._sentinel_pass_floor:
            alerts.append(
                DriftAlert(
                    code="SENTINEL_FAILURE",
                    severity="warning",
                    message="Sentinel pass rate dropped below the configured floor.",
                    metrics={"sentinel_pass_rate": sentinel_pass_rate},
                    recommended_action=(
                        "Inject calibration sentinels and inspect recent regressions."
                    ),
                )
            )

        return alerts

    def promotion_ban_active(self) -> bool:
        return any(alert.code == "PROMOTION_BAN" for alert in self.drift_alerts())

    def routing_mode(self) -> str:
        if self.promotion_ban_active():
            return "no_promotion"
        if self.drift_alerts():
            return "conservative_routing"
        return "normal"

    def compute_metrics(
        self,
        *,
        window_size: int | None = None,
    ) -> dict[str, Any]:
        """Compute legacy metrics plus drift-aware rolling-window fields."""
        if not self._records:
            return {
                "sample_count": 0,
                "false_positive_rate": 0.0,
                "true_positive_rate": 0.0,
                "spearman_correlation": 0.0,
                "false_negative_rate": 0.0,
                "rolling_window_size": 0,
                "rolling_sample_count": 0,
                "rolling_spearman_correlation": 0.0,
                "sentinel_pass_rate": None,
                "alert_count": 0,
                "promotion_ban_active": False,
                "routing_mode": "normal",
            }

        full_metrics = self._metrics_for_records(self._records)
        window_records = self._window(window_size)
        rolling_metrics = self._metrics_for_records(window_records)
        alerts = self.drift_alerts(window_size=len(window_records))
        sentinel_rate = self.sentinel_pass_rate(window_size=len(window_records))

        return {
            "sample_count": len(self._records),
            "false_positive_rate": full_metrics["false_positive_rate"],
            "true_positive_rate": full_metrics["true_positive_rate"],
            "spearman_correlation": full_metrics["spearman_correlation"],
            "false_negative_rate": rolling_metrics["false_negative_rate"],
            "rolling_window_size": self._drift_window_size,
            "rolling_sample_count": len(window_records),
            "rolling_spearman_correlation": rolling_metrics["spearman_correlation"],
            "sentinel_pass_rate": sentinel_rate,
            "alert_count": len(alerts),
            "promotion_ban_active": any(alert.code == "PROMOTION_BAN" for alert in alerts),
            "routing_mode": self.routing_mode(),
        }

    def records(self) -> list[CorrelationRecord]:
        return list(self._records)

    def to_snapshot(self) -> CorrelationTrackerSnapshot:
        """Serialize tracker state for CAS-backed reporting workflows."""
        return CorrelationTrackerSnapshot(
            max_records=self._max_records,
            drift_window_size=self._drift_window_size,
            spearman_warning_threshold=self._spearman_warning_threshold,
            promotion_ban_threshold=self._promotion_ban_threshold,
            false_negative_ceiling=self._false_negative_ceiling,
            sentinel_pass_floor=self._sentinel_pass_floor,
            records=[
                CorrelationRecordSnapshot(
                    candidate_hash=record.candidate_hash,
                    stage_a_score=record.stage_a_score,
                    stage_b_score=record.stage_b_score,
                    stage_a_passed=record.stage_a_passed,
                    stage_b_approved=record.stage_b_approved,
                    timestamp=record.timestamp,
                    is_sentinel=record.is_sentinel,
                    metadata=dict(record.metadata),
                )
                for record in self._records
            ],
        )

    @classmethod
    def from_snapshot(
        cls,
        snapshot: CorrelationTrackerSnapshot | dict[str, Any],
    ) -> CorrelationTracker:
        """Restore tracker state from a serialized snapshot."""
        payload = (
            snapshot
            if isinstance(snapshot, CorrelationTrackerSnapshot)
            else CorrelationTrackerSnapshot.model_validate(snapshot)
        )
        tracker = cls(
            max_records=payload.max_records,
            drift_window_size=payload.drift_window_size,
            spearman_warning_threshold=payload.spearman_warning_threshold,
            promotion_ban_threshold=payload.promotion_ban_threshold,
            false_negative_ceiling=payload.false_negative_ceiling,
            sentinel_pass_floor=payload.sentinel_pass_floor,
        )
        tracker._records = [
            CorrelationRecord(
                candidate_hash=record.candidate_hash,
                stage_a_score=record.stage_a_score,
                stage_b_score=record.stage_b_score,
                stage_a_passed=record.stage_a_passed,
                stage_b_approved=record.stage_b_approved,
                timestamp=record.timestamp,
                is_sentinel=record.is_sentinel,
                metadata=dict(record.metadata),
            )
            for record in payload.records
        ]
        return tracker

    def persist_snapshot(
        self,
        store: FileSystemCAS,
        *,
        inputs: list[InputRef] | None = None,
    ) -> ArtifactRef:
        """Persist the tracker snapshot to CAS."""
        return store.put_json(
            self.to_snapshot(),
            PutOptions(
                kind="scientist.search.correlation_tracker",
                media_type="application/json",
                schema=SchemaInfo(
                    name="polisyos.scientist.search.CorrelationTrackerSnapshot",
                    version="1.0",
                ),
                inputs=list(inputs or []),
            ),
            canon_spec=CanonSpec(forbid_floats=False),
        )

    @classmethod
    def load_snapshot(
        cls,
        store: FileSystemCAS,
        ref: ArtifactRef | str,
    ) -> CorrelationTracker:
        """Load tracker state from CAS snapshot."""
        artifact_id = ref.artifact_id if isinstance(ref, ArtifactRef) else ref
        snapshot = CorrelationTrackerSnapshot.model_validate(
            from_canonical_bytes(store.get_bytes(artifact_id))
        )
        return cls.from_snapshot(snapshot)

    def to_jsonl_rows(self) -> list[dict[str, Any]]:
        return [
            {
                "candidate_hash": record.candidate_hash,
                "stage_a_score": record.stage_a_score,
                "stage_b_score": record.stage_b_score,
                "stage_a_passed": record.stage_a_passed,
                "stage_b_approved": record.stage_b_approved,
                "timestamp": record.timestamp.isoformat(),
                "is_sentinel": record.is_sentinel,
                "metadata": record.metadata,
            }
            for record in self._records
        ]

    def write_dataset(
        self,
        *,
        output_dir: Path | None = None,
        suite_id: str = "cheap_stage_correlation",
        suite_version: str = "1.0",
        holdout_fraction: float = 0.2,
    ):
        from polisyos.scientist.methods.autotune.cheap_stage import write_correlation_dataset

        return write_correlation_dataset(
            self.to_jsonl_rows(),
            output_dir=output_dir,
            suite_id=suite_id,
            suite_version=suite_version,
            holdout_fraction=holdout_fraction,
        )

    def _window(self, window_size: int | None) -> list[CorrelationRecord]:
        resolved = self._drift_window_size if window_size is None else max(1, int(window_size))
        if len(self._records) <= resolved:
            return list(self._records)
        return self._records[-resolved:]

    def _metrics_for_records(self, records: list[CorrelationRecord]) -> dict[str, float]:
        if not records:
            return {
                "false_positive_rate": 0.0,
                "true_positive_rate": 0.0,
                "false_negative_rate": 0.0,
                "spearman_correlation": 0.0,
            }

        passed_a = [record for record in records if record.stage_a_passed]
        rejected_a = [record for record in records if not record.stage_a_passed]

        true_positives = sum(1 for record in passed_a if record.stage_b_approved)
        false_positives = sum(1 for record in passed_a if not record.stage_b_approved)
        false_negatives = sum(1 for record in rejected_a if record.stage_b_approved)

        fp_rate = false_positives / len(passed_a) if passed_a else 0.0
        tp_rate = true_positives / len(passed_a) if passed_a else 0.0
        fn_rate = false_negatives / len(rejected_a) if rejected_a else 0.0

        if len(records) > 2:
            a_scores = [record.stage_a_score for record in records]
            b_scores = [record.stage_b_score for record in records]
            correlation = self._spearman(a_scores, b_scores)
        else:
            correlation = 0.0

        return {
            "false_positive_rate": fp_rate,
            "true_positive_rate": tp_rate,
            "false_negative_rate": fn_rate,
            "spearman_correlation": correlation,
        }

    @staticmethod
    def _spearman(x: list[float], y: list[float]) -> float:
        """Compute Spearman rank correlation."""
        n = len(x)
        if n < 2:
            return 0.0

        def rank(values: list[float]) -> list[float]:
            sorted_idx = sorted(range(n), key=lambda i: values[i])
            ranks = [0.0] * n
            start = 0
            while start < n:
                end = start + 1
                while end < n and values[sorted_idx[end]] == values[sorted_idx[start]]:
                    end += 1
                avg_rank = (start + 1 + end) / 2.0
                for idx in sorted_idx[start:end]:
                    ranks[idx] = avg_rank
                start = end
            return ranks

        rx = rank(x)
        ry = rank(y)

        mean_x = sum(rx) / n
        mean_y = sum(ry) / n

        num = sum((rx[i] - mean_x) * (ry[i] - mean_y) for i in range(n))
        den_x = sum((rx[i] - mean_x) ** 2 for i in range(n)) ** 0.5
        den_y = sum((ry[i] - mean_y) ** 2 for i in range(n)) ** 0.5

        if den_x * den_y == 0:
            return 0.0

        return num / (den_x * den_y)
