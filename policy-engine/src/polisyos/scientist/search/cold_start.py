"""Cold-start burn-in orchestration for the multi-fidelity funnel."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.scientist.autotune.cheap_stage import write_correlation_dataset
from polisyos.scientist.autotune.models import BenchmarkSuite, load_model_artifact
from polisyos.scientist.search.funnel import (
    FunnelOrchestrator,
    Level0StaticValidator,
    Level1CheapHeuristic,
    Level2CausalPlausibility,
    Level3MediumFidelity,
    Level4FullFidelity,
    Level5RefutationGovernanceStage,
    Level6PromotionStage,
)
from polisyos.scientist.search.lessons import LessonRegistry
from polisyos.scientist.search.sentinels import (
    SentinelInjector,
    SentinelObservation,
    SentinelSet,
    extract_sentinel_metadata,
    load_sentinel_set,
    strip_internal_candidate_metadata,
)
from polisyos.scientist.search.stages import CorrelationTracker

_BURN_IN_REPORT_KIND = "scientist.search.burn_in_report"
_BURN_IN_REPORT_SCHEMA = SchemaInfo(
    name="polisyos.scientist.search.BurnInRunReport",
    version="1.0",
)


class BurnInCohort(str, Enum):
    """Burn in cohort public type."""

    CALIBRATION = "calibration"
    LESSON_SEEDING = "lesson_seeding"


class BurnInConfig(BaseModel):
    """Deterministic burn-in config using explicit candidate lists."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(default="1.0", pattern=r"^\d+\.\d+$")
    run_id: str = Field(default="burn_in", min_length=1)
    regular_candidates: list[dict[str, Any]] = Field(default_factory=list)
    dumb_candidates: list[dict[str, Any]] = Field(default_factory=list)
    sentinel_set_ref: str | None = None
    correlation_dataset_output_dir: str | None = None


class BurnInRunReport(BaseModel):
    """Summary of a burn-in run and acceptance checks."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(default="1.0", pattern=r"^\d+\.\d+$")
    run_id: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    cohort_sizes: dict[str, int] = Field(default_factory=dict)
    baseline_level4_candidates: int = Field(ge=0)
    actual_level4_candidates: int = Field(ge=0)
    level4_execution_rate: float = Field(ge=0.0, le=1.0)
    expensive_stage_load_reduction: float = Field(ge=0.0, le=1.0)
    false_negative_rate: float = Field(ge=0.0, le=1.0)
    spearman_correlation: float = Field(ge=-1.0, le=1.0)
    sentinel_pass_rate: float | None = Field(default=None, ge=0.0, le=1.0)
    degradation_mode: str = Field(default="normal", min_length=1)
    lesson_card_refs: list[ArtifactRef] = Field(default_factory=list)
    lessons_snapshot_ref: ArtifactRef | None = None
    correlation_dataset_suite: BenchmarkSuite | None = None
    sentinel_observations: list[SentinelObservation] = Field(default_factory=list)
    acceptance_criteria: dict[str, bool | None] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class _EmbeddedResultsWorkflowEngine:
    """Deterministic workflow engine used by the burn-in CLI path."""

    def run(self, initial_state: dict[str, Any]) -> dict[str, Any]:
        candidate = initial_state.get("ir", {})
        fidelity_level = int(initial_state.get("_fidelity_level", 4) or 4)
        if fidelity_level >= 4:
            payload = candidate.get("expected_stage4") or {}
        else:
            payload = candidate.get("expected_stage3") or candidate.get("expected_stage4") or {}

        if isinstance(payload, dict) and ("simulation_results" in payload or "feedback" in payload):
            return {
                "simulation_results": dict(payload.get("simulation_results", {})),
                "feedback": dict(payload.get("feedback", {"verdict": "APPROVE"})),
            }

        numeric_values = list(_iter_numeric_values(strip_internal_candidate_metadata(candidate)))
        gdp_change = sum(numeric_values) / len(numeric_values) if numeric_values else 0.25
        gov_balance = -abs(gdp_change) * 0.3
        verdict = "APPROVE" if gdp_change >= -0.2 else "REJECT"
        return {
            "simulation_results": {
                "gdp_change": gdp_change,
                "gov_balance": gov_balance,
                "ate": gdp_change,
                "bootstrap": {"ci_width": max(0.05, abs(gdp_change) * 0.2)},
            },
            "feedback": {"verdict": verdict},
        }


def build_default_burn_in_orchestrator(
    *,
    correlation_tracker: CorrelationTracker | None = None,
    lesson_registry: LessonRegistry | None = None,
) -> FunnelOrchestrator:
    """Build a deterministic stage stack for the burn-in CLI path."""

    engine = _EmbeddedResultsWorkflowEngine()
    return FunnelOrchestrator(
        [
            Level0StaticValidator(),
            Level1CheapHeuristic(),
            Level2CausalPlausibility(),
            Level3MediumFidelity(workflow_engine=engine),
            Level4FullFidelity(workflow_engine=engine),
            Level5RefutationGovernanceStage(require_hidden_holdout=False),
            Level6PromotionStage(allow_noop_complete=True),
        ],
        correlation_tracker=correlation_tracker,
        lesson_registry=lesson_registry,
    )


def persist_burn_in_report(
    store: FileSystemCAS,
    report: BurnInRunReport,
    *,
    inputs: list[InputRef] | None = None,
) -> ArtifactRef:
    """Persist burn in report helper."""
    return store.put_json(
        report,
        PutOptions(
            kind=_BURN_IN_REPORT_KIND,
            media_type="application/json",
            schema=_BURN_IN_REPORT_SCHEMA,
            inputs=list(inputs or []),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )


def run_burn_in(
    *,
    orchestrator: FunnelOrchestrator,
    config: BurnInConfig,
    correlation_tracker: CorrelationTracker | None = None,
    lesson_registry: LessonRegistry | None = None,
    sentinel_set: SentinelSet | None = None,
    store: FileSystemCAS | None = None,
) -> BurnInRunReport:
    """Run calibration and lesson-seeding cohorts through the funnel."""

    tracker = (
        correlation_tracker
        or getattr(orchestrator, "_correlation_tracker", None)
        or CorrelationTracker()
    )
    registry = lesson_registry or getattr(orchestrator, "_lesson_registry", None)
    active_sentinel_set = sentinel_set
    if active_sentinel_set is None and config.sentinel_set_ref and store is not None:
        active_sentinel_set = load_sentinel_set(store, config.sentinel_set_ref)

    injector = SentinelInjector(active_sentinel_set) if active_sentinel_set else None
    calibration_candidates = list(config.regular_candidates)
    if injector is not None:
        calibration_candidates = injector.inject_batch(calibration_candidates)

    actual_level4_candidates = 0
    baseline_level4_candidates = len(calibration_candidates) + len(config.dumb_candidates)
    lesson_refs: list[ArtifactRef] = []
    sentinel_observations: list[SentinelObservation] = []
    manual_tracker = getattr(orchestrator, "_correlation_tracker", None) is not tracker

    for candidate in calibration_candidates:
        outcome = orchestrator.advance(
            orchestrator.submit(
                candidate,
                {"source_run_id": config.run_id, "burn_in_cohort": BurnInCohort.CALIBRATION.value},
            ),
            policy="burn_in",
        )
        actual_level4_candidates += int(4 in outcome.stage_results)
        lesson_refs.extend(getattr(outcome, "lesson_refs", []))
        sentinel_meta = extract_sentinel_metadata(candidate)
        if sentinel_meta is not None and active_sentinel_set is not None:
            sentinel = next(
                (
                    item
                    for item in active_sentinel_set.sentinels
                    if item.sentinel_id == sentinel_meta.get("sentinel_id")
                ),
                None,
            )
            if sentinel is not None:
                sentinel_observations.append(SentinelObservation.from_outcome(sentinel, outcome))
        if manual_tracker:
            _record_outcome_for_correlation(tracker, outcome, is_sentinel=sentinel_meta is not None)

    for candidate in config.dumb_candidates:
        outcome = orchestrator.advance(
            orchestrator.submit(
                candidate,
                {
                    "source_run_id": config.run_id,
                    "burn_in_cohort": BurnInCohort.LESSON_SEEDING.value,
                },
            ),
            policy="full",
        )
        actual_level4_candidates += int(4 in outcome.stage_results)
        lesson_refs.extend(getattr(outcome, "lesson_refs", []))
        if manual_tracker:
            _record_outcome_for_correlation(tracker, outcome, is_sentinel=False)

    dataset_suite = None
    if config.correlation_dataset_output_dir:
        dataset_suite = write_correlation_dataset(
            tracker.to_jsonl_rows(),
            output_dir=Path(config.correlation_dataset_output_dir),
        )

    metrics = tracker.compute_metrics()
    sentinel_pass_rate = metrics.get("sentinel_pass_rate")
    if sentinel_pass_rate is None and sentinel_observations:
        sentinel_pass_rate = sum(1 for obs in sentinel_observations if obs.stage_a_passed) / len(
            sentinel_observations
        )

    level4_execution_rate = (
        actual_level4_candidates / baseline_level4_candidates if baseline_level4_candidates else 0.0
    )
    expensive_stage_load_reduction = (
        1.0 - level4_execution_rate if baseline_level4_candidates else 0.0
    )
    acceptance_criteria = {
        "false_negative_rate_lt_2pct": float(metrics.get("false_negative_rate", 0.0)) < 0.02,
        "spearman_gt_0_6": float(metrics.get("spearman_correlation", 0.0)) > 0.6,
        "expensive_stage_load_reduction_gt_50pct": expensive_stage_load_reduction > 0.5,
        "sentinel_pass_rate_gt_95pct": (
            None if sentinel_pass_rate is None else float(sentinel_pass_rate) > 0.95
        ),
    }

    return BurnInRunReport(
        run_id=config.run_id,
        cohort_sizes={
            BurnInCohort.CALIBRATION.value: len(calibration_candidates),
            BurnInCohort.LESSON_SEEDING.value: len(config.dumb_candidates),
        },
        baseline_level4_candidates=baseline_level4_candidates,
        actual_level4_candidates=actual_level4_candidates,
        level4_execution_rate=level4_execution_rate,
        expensive_stage_load_reduction=expensive_stage_load_reduction,
        false_negative_rate=float(metrics.get("false_negative_rate", 0.0)),
        spearman_correlation=float(metrics.get("spearman_correlation", 0.0)),
        sentinel_pass_rate=None if sentinel_pass_rate is None else float(sentinel_pass_rate),
        degradation_mode=str(metrics.get("routing_mode", "normal")),
        lesson_card_refs=_dedupe_refs(lesson_refs),
        lessons_snapshot_ref=registry.snapshot_ref() if registry is not None else None,
        correlation_dataset_suite=dataset_suite,
        sentinel_observations=sentinel_observations,
        acceptance_criteria=acceptance_criteria,
        metadata={
            "record_count": len(tracker.records()),
            "rolling_sample_count": metrics.get("rolling_sample_count", 0),
        },
    )


def load_burn_in_report(store: FileSystemCAS, ref: ArtifactRef | str) -> BurnInRunReport:
    """Load burn in report."""
    return load_model_artifact(store, ref, BurnInRunReport)


def _record_outcome_for_correlation(
    tracker: CorrelationTracker,
    outcome: Any,
    *,
    is_sentinel: bool,
) -> None:
    stage_results = getattr(outcome, "stage_results", {}) or {}
    gate_result = stage_results.get(2)
    if gate_result is None:
        lower_levels = [level for level in stage_results if level < 4]
        if lower_levels:
            gate_result = stage_results[max(lower_levels)]
    truth_result = stage_results.get(4)
    if truth_result is None:
        truth_levels = [level for level in stage_results if level >= 4]
        if truth_levels:
            truth_result = stage_results[max(truth_levels)]
    if gate_result is None or truth_result is None:
        return
    tracker.record(
        gate_result,
        truth_result,
        str(getattr(outcome, "candidate_hash", "unknown")),
        is_sentinel=is_sentinel,
    )


def _dedupe_refs(refs: list[ArtifactRef]) -> list[ArtifactRef]:
    seen: set[str] = set()
    deduped: list[ArtifactRef] = []
    for ref in refs:
        key = str(ref.artifact_id)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(ref)
    return deduped


def _iter_numeric_values(payload: Any):
    if isinstance(payload, (int, float)) and not isinstance(payload, bool):
        yield float(payload)
        return
    if isinstance(payload, dict):
        for value in payload.values():
            yield from _iter_numeric_values(value)
        return
    if isinstance(payload, list):
        for item in payload:
            yield from _iter_numeric_values(item)


__all__ = [
    "BurnInCohort",
    "BurnInConfig",
    "BurnInRunReport",
    "build_default_burn_in_orchestrator",
    "load_burn_in_report",
    "persist_burn_in_report",
    "run_burn_in",
]
