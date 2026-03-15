from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from polisyos.common.logger import get_logger
from polisyos.scientist.workflows.engine_base import WorkflowEngine

logger = get_logger(__name__)


@dataclass
class StageResult:
    """Result from a search stage evaluation."""

    policy_candidate: Dict[str, Any]
    objective_value: float
    is_promising: bool

    stage_name: str
    duration_seconds: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)

    simulation_results: Dict[str, Any] = field(default_factory=dict)
    feedback: Dict[str, Any] = field(default_factory=dict)

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
        candidate: Dict[str, Any],
        context: Dict[str, Any],
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
        from polisyos.scientist.autotune.cheap_stage import resolve_cheap_stage_threshold

        self._threshold = resolve_cheap_stage_threshold(threshold)
        self._param_checks = enable_parameter_checks
        self._struct_checks = enable_structure_checks

    @property
    def stage_name(self) -> str:
        return "cheap"

    def evaluate(
        self,
        candidate: Dict[str, Any],
        context: Dict[str, Any],
    ) -> StageResult:
        start = datetime.utcnow()

        issues: List[str] = []
        score = 0.0

        semantic = candidate.get("semantic", {})
        interventions = semantic.get("interventions", [])

        if self._struct_checks:
            score += self._check_structure(candidate, issues)

        if self._param_checks:
            score += self._check_parameters(interventions, issues)

        duration = (datetime.utcnow() - start).total_seconds()
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
        candidate: Dict[str, Any],
        issues: List[str],
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
        interventions: List[Dict[str, Any]],
        issues: List[str],
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
                        issues.append(
                            f"Intervention {i}: {key}={value} outside [0,1]"
                        )
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
        candidate: Dict[str, Any],
        context: Dict[str, Any],
    ) -> StageResult:
        start = datetime.utcnow()

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
                duration_seconds=(datetime.utcnow() - start).total_seconds(),
                feedback={"verdict": "REJECT", "issues": [{"message": str(exc)}]},
            )

        duration = (datetime.utcnow() - start).total_seconds()

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

    def _compute_default_objective(self, results: Dict[str, Any]) -> float:
        """Compute simple objective from simulation results."""
        gdp = results.get("gdp_change", 0.0)
        deficit = abs(min(results.get("gov_balance", 0.0), 0))

        return -(gdp - 0.5 * deficit)


# ─────────────────────────────────────────────────────────────────────────────
# Correlation Tracking (Risk Mitigation B)
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class CorrelationRecord:
    """Record for tracking Stage A vs Stage B correlation."""

    candidate_hash: str
    stage_a_score: float
    stage_b_score: float
    stage_a_passed: bool
    stage_b_approved: bool
    timestamp: datetime = field(default_factory=datetime.utcnow)


class CorrelationTracker:
    """
    Tracks correlation between Stage A predictions and Stage B results.

    Purpose:
        Enable tuning of CheapStage threshold based on empirical data.
    """

    def __init__(self, max_records: int = 1000):
        self._records: List[CorrelationRecord] = []
        self._max_records = max_records

    def record(
        self,
        stage_a_result: StageResult,
        stage_b_result: StageResult | None,
        candidate_hash: str,
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
        )

        self._records.append(record)

        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]

    def compute_metrics(self) -> Dict[str, float]:
        """Compute correlation metrics."""
        if not self._records:
            return {
                "sample_count": 0,
                "false_positive_rate": 0.0,
                "true_positive_rate": 0.0,
            }

        passed_a = [r for r in self._records if r.stage_a_passed]

        true_positives = sum(1 for r in passed_a if r.stage_b_approved)
        false_positives = sum(1 for r in passed_a if not r.stage_b_approved)

        fp_rate = false_positives / len(passed_a) if passed_a else 0.0
        tp_rate = true_positives / len(passed_a) if passed_a else 0.0

        if len(self._records) > 2:
            a_scores = [r.stage_a_score for r in self._records]
            b_scores = [r.stage_b_score for r in self._records]
            correlation = self._spearman(a_scores, b_scores)
        else:
            correlation = 0.0

        return {
            "sample_count": len(self._records),
            "false_positive_rate": fp_rate,
            "true_positive_rate": tp_rate,
            "spearman_correlation": correlation,
        }

    def records(self) -> List[CorrelationRecord]:
        return list(self._records)

    def to_jsonl_rows(self) -> List[Dict[str, Any]]:
        return [
            {
                "candidate_hash": record.candidate_hash,
                "stage_a_score": record.stage_a_score,
                "stage_b_score": record.stage_b_score,
                "stage_a_passed": record.stage_a_passed,
                "stage_b_approved": record.stage_b_approved,
                "timestamp": record.timestamp.isoformat(),
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
        from polisyos.scientist.autotune.cheap_stage import write_correlation_dataset

        return write_correlation_dataset(
            self.to_jsonl_rows(),
            output_dir=output_dir,
            suite_id=suite_id,
            suite_version=suite_version,
            holdout_fraction=holdout_fraction,
        )

    @staticmethod
    def _spearman(x: List[float], y: List[float]) -> float:
        """Compute Spearman rank correlation."""
        n = len(x)
        if n < 2:
            return 0.0

        def rank(values: List[float]) -> List[float]:
            sorted_idx = sorted(range(n), key=lambda i: values[i])
            ranks = [0.0] * n
            for rank_val, idx in enumerate(sorted_idx):
                ranks[idx] = rank_val + 1
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
