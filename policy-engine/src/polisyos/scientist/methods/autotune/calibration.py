"""Public autotune calibration module API."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from pydantic import ConfigDict, Field

from polisyos.core.artifacts import ArtifactRef
from polisyos.foundry.calibration.execution_basis import (
    read_calibration_report_source,
    replay_ordered_batch_report_projection,
)
from polisyos.foundry.calibration.report import CalibrationReport
from polisyos.ir.analytics.calibration import CalibrationConfig

from .models import (
    BenchmarkedEvaluator,
    BenchmarkEvaluation,
    BenchmarkSplit,
    BenchmarkSuite,
    MetricDirection,
    MutationArtifact,
    PromotionPolicy,
    SearchLoopSpec,
    load_model_artifact,
    read_split_manifest,
)
from .registry import ChampionRegistry
from .runtime import ChampionBackedRuntimeLoader, PydanticMutationCodec

CALIBRATION_LOOP_ID = "calibration_meta"


@dataclass(frozen=True)
class _CalibrationCase:
    report: CalibrationReport
    report_ref: ArtifactRef | None = None
    source_status: Literal["legacy_candidate", "matched", "mismatch", "not_established"] = (
        "legacy_candidate"
    )
    limitation_codes: tuple[str, ...] = ()

    def source_projection(self) -> dict[str, Any]:
        return {
            "report_schema_version": self.report.schema_version,
            "report_ref": None
            if self.report_ref is None
            else self.report_ref.model_dump(mode="json"),
            "metric_source_status": self.source_status,
            "limitation_codes": list(self.limitation_codes),
            "evidence_grade": "candidate",
            "inference_status": (
                "unavailable_generic_loss"
                if self.report.ordered_batch_execution is not None
                else "legacy_heuristic_not_requalified"
            ),
        }


class CalibrationMetaSearchConfig(MutationArtifact):
    """Calibration meta search config data model."""

    model_config = ConfigDict(extra="forbid")

    loop_id: str = CALIBRATION_LOOP_ID
    learning_rate: float | None = Field(default=None, gt=0.0)
    clip_grad_norm: float | None = Field(default=None, gt=0.0)
    early_stop_patience: int | None = Field(default=None, ge=0)
    early_stop_min_delta: float | None = Field(default=None, ge=0.0)
    early_stop_min_steps: int | None = Field(default=None, ge=0)
    seed_strategy: str | None = Field(default=None, pattern=r"^(fixed|step)$")
    grad_norm_enabled: bool | None = None
    grad_norm_alpha: float | None = Field(default=None, ge=0.0)
    grad_norm_lr: float | None = Field(default=None, ge=0.0)
    grad_norm_update_every: int | None = Field(default=None, ge=1)
    constraint_loss_weight: float | None = Field(default=None, ge=0.0)
    prior_loss_weight: float | None = Field(default=None, ge=0.0)

    def apply_to_config(self, base_config: CalibrationConfig) -> CalibrationConfig:
        updated = _clone_calibration_config(base_config)
        if self.learning_rate is not None:
            updated.learning_rate = self.learning_rate
        if self.clip_grad_norm is not None:
            updated.clip_grad_norm = self.clip_grad_norm
        if self.early_stop_patience is not None:
            updated.early_stop_patience = self.early_stop_patience
        if self.early_stop_min_delta is not None:
            updated.early_stop_min_delta = self.early_stop_min_delta
        if self.early_stop_min_steps is not None:
            updated.early_stop_min_steps = self.early_stop_min_steps
        if self.seed_strategy is not None:
            updated.seed_strategy = self.seed_strategy
        if self.grad_norm_enabled is not None:
            updated.grad_norm.enabled = self.grad_norm_enabled
        if self.grad_norm_alpha is not None:
            updated.grad_norm.alpha = self.grad_norm_alpha
        if self.grad_norm_lr is not None:
            updated.grad_norm.lr = self.grad_norm_lr
        if self.grad_norm_update_every is not None:
            updated.grad_norm.update_every = self.grad_norm_update_every
        if self.constraint_loss_weight is not None:
            updated.constraint_loss.weight = self.constraint_loss_weight
        if self.prior_loss_weight is not None:
            updated.prior_loss.weight = self.prior_loss_weight
        return updated


def _clone_calibration_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _clone_calibration_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_clone_calibration_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_clone_calibration_value(item) for item in value)
    if isinstance(value, set):
        return {_clone_calibration_value(item) for item in value}
    return value


def _clone_calibration_config(base_config: CalibrationConfig) -> CalibrationConfig:
    return base_config.model_copy(
        update={
            "targets": [
                target.model_copy(
                    update={
                        "fabric_query": _clone_calibration_value(target.fabric_query),
                        "align": target.align.model_copy(deep=False),
                        "loss": target.loss.model_copy(deep=False),
                        "trainables": [
                            trainable.model_copy(
                                update={"selector": _clone_calibration_value(trainable.selector)}
                            )
                            for trainable in target.trainables
                        ],
                    }
                )
                for target in base_config.targets
            ],
            "trainables": [
                trainable.model_copy(
                    update={"selector": _clone_calibration_value(trainable.selector)}
                )
                for trainable in base_config.trainables
            ],
            "time_axis": None if base_config.time_axis is None else list(base_config.time_axis),
            "grad_norm": base_config.grad_norm.model_copy(deep=False),
            "hessian": base_config.hessian.model_copy(deep=False),
            "multi_start": (
                None
                if base_config.multi_start is None
                else base_config.multi_start.model_copy(deep=False)
            ),
            "constraint_loss": base_config.constraint_loss.model_copy(deep=False),
            "prior_loss": base_config.prior_loss.model_copy(deep=False),
            "fidelity": base_config.fidelity.model_copy(deep=False),
            "constraint_values": _clone_calibration_value(base_config.constraint_values),
            "literature_priors": _clone_calibration_value(base_config.literature_priors),
        }
    )


def build_baseline_calibration_meta_config(
    _context: dict[str, Any] | None = None,
) -> CalibrationMetaSearchConfig:
    """Build baseline calibration meta config."""
    return CalibrationMetaSearchConfig()


def default_calibration_policy() -> PromotionPolicy:
    """Default calibration policy helper."""
    return PromotionPolicy(
        loop_id=CALIBRATION_LOOP_ID,
        primary_metric="aggregate_fit_quality",
        direction=MetricDirection.MAXIMIZE,
        compare_split=BenchmarkSplit.HOLDOUT,
        min_improvement=0.0,
        min_sample_count=1,
        required_guardrails=["no_divergence", "uncertainty_not_worse"],
    )


def apply_calibration_meta_overrides(
    base_config: CalibrationConfig,
    *,
    context: dict[str, Any] | None = None,
    loader: ChampionBackedRuntimeLoader[CalibrationMetaSearchConfig] | None = None,
) -> CalibrationConfig:
    """Apply calibration meta overrides helper."""
    active_loader = loader or CalibrationMetaRuntimeLoader()
    active_config = active_loader.load(context)
    return active_config.apply_to_config(base_config)


class CalibrationMetaEvaluator(BenchmarkedEvaluator):
    """Calibration meta evaluator public type."""

    def __init__(
        self,
        *,
        store: Any | None = None,
        registry: ChampionRegistry | None = None,
    ) -> None:
        self._store = store
        self._registry = registry

    def evaluate(self, candidate_ref, suite_ref, context: dict[str, Any]) -> BenchmarkEvaluation:
        store = context.get("store") or self._store
        if store is None:
            raise ValueError("CalibrationMetaEvaluator requires a CAS store")
        suite = load_model_artifact(store, suite_ref, BenchmarkSuite)
        config = load_model_artifact(store, candidate_ref, CalibrationMetaSearchConfig)
        if suite.dataset_path is None or suite.split_manifest_path is None:
            raise ValueError("Calibration meta suite requires dataset_path and split_manifest_path")
        runner = context.get("calibration_runner")
        if not callable(runner):
            raise ValueError("context['calibration_runner'] must be callable")
        rows = _read_jsonl(Path(suite.dataset_path))
        split_manifest = read_split_manifest(Path(suite.split_manifest_path))
        champion_uncertainty = self._champion_uncertainty_score(
            candidate_ref=candidate_ref,
            suite=suite,
            rows=rows,
            runner=runner,
            split_manifest=split_manifest,
            context=context,
        )
        selection_reports = _run_calibration_cases(
            config=config,
            rows=[
                row
                for row in rows
                if split_manifest.split_for(str(row["case_id"])) == BenchmarkSplit.SELECTION
            ],
            runner=runner,
            context=context,
            store=store,
        )
        holdout_reports = _run_calibration_cases(
            config=config,
            rows=[
                row
                for row in rows
                if split_manifest.split_for(str(row["case_id"])) == BenchmarkSplit.HOLDOUT
            ],
            runner=runner,
            context=context,
            store=store,
        )
        selection_metrics = _calibration_metrics(selection_reports)
        holdout_metrics = _calibration_metrics(holdout_reports)
        uncertainty_margin = float(context.get("uncertainty_regression_tolerance", 0.05) or 0.05)
        guardrails = {
            "no_divergence": float(holdout_metrics.get("divergence_rate", 1.0)) == 0.0,
            "uncertainty_not_worse": float(
                holdout_metrics.get("uncertainty_conditioning_score", 0.0)
            )
            >= (champion_uncertainty - uncertainty_margin)
            if champion_uncertainty is not None
            else False,
        }
        cases = [*selection_reports, *holdout_reports]
        new_profile = any(case.report.ordered_batch_execution is not None for case in cases)
        metric_sources_ready = all(
            case.source_status in {"legacy_candidate", "matched"} for case in cases
        )
        if new_profile:
            guardrails["calibration_metric_sources_ready"] = metric_sources_ready
        limitations = sorted({code for case in cases for code in case.limitation_codes})
        if champion_uncertainty is None:
            limitations.append("ordered_autotune_champion_metrics_not_established")
            metric_sources_ready = False
        return BenchmarkEvaluation(
            loop_id=CALIBRATION_LOOP_ID,
            suite_id=suite.suite_id,
            suite_version=suite.suite_version,
            candidate_ref=candidate_ref,
            selection_metrics=selection_metrics,
            holdout_metrics=holdout_metrics,
            sample_counts={
                BenchmarkSplit.SELECTION.value: int(selection_metrics.get("sample_count", 0.0)),
                BenchmarkSplit.HOLDOUT.value: int(holdout_metrics.get("sample_count", 0.0)),
            },
            guardrails=guardrails,
            promotable=all(guardrails.values()),
            status="ok" if metric_sources_ready else "limited",
            notes=limitations,
            metadata=(
                {
                    "calibration_metric_sources": {
                        "selection": [case.source_projection() for case in selection_reports],
                        "holdout": [case.source_projection() for case in holdout_reports],
                    }
                }
                if new_profile
                else {}
            ),
        )

    def _champion_uncertainty_score(
        self,
        *,
        candidate_ref,
        suite: BenchmarkSuite,
        rows: list[dict[str, Any]],
        runner: Any,
        split_manifest,
        context: dict[str, Any],
    ) -> float | None:
        registry = context.get("registry") or self._registry
        store = context.get("store") or self._store
        if registry is None or store is None:
            return 0.0
        champion = registry.get(CALIBRATION_LOOP_ID)
        if champion is None or champion.candidate_ref.artifact_id == candidate_ref.artifact_id:
            return 0.0
        cfg = load_model_artifact(store, champion.candidate_ref, CalibrationMetaSearchConfig)
        metrics = _calibration_metrics(
            _run_calibration_cases(
                config=cfg,
                rows=[
                    row
                    for row in rows
                    if split_manifest.split_for(str(row["case_id"])) == BenchmarkSplit.HOLDOUT
                ],
                runner=runner,
                context=context,
                store=store,
            )
        )
        value = metrics.get("uncertainty_conditioning_score")
        return None if value is None else float(value)


class CalibrationMetaRuntimeLoader(ChampionBackedRuntimeLoader[CalibrationMetaSearchConfig]):
    """Calibration meta runtime loader implementation."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(
            loop_id=CALIBRATION_LOOP_ID,
            model_cls=CalibrationMetaSearchConfig,
            baseline_factory=build_baseline_calibration_meta_config,
            suite_version="1.0",
            **kwargs,
        )


def calibration_search_loop_spec(
    *,
    candidate_generator: Any | None = None,
    store: Any | None = None,
    registry: ChampionRegistry | None = None,
) -> SearchLoopSpec:
    """Calibration search loop spec helper."""
    return SearchLoopSpec(
        loop_id=CALIBRATION_LOOP_ID,
        mutation_codec=PydanticMutationCodec(CalibrationMetaSearchConfig),
        candidate_generator=candidate_generator,
        benchmark_evaluator=CalibrationMetaEvaluator(store=store, registry=registry),
        promotion_policy=default_calibration_policy(),
        runtime_loader=CalibrationMetaRuntimeLoader(store=store, registry=registry),
    )


def _ordered_metric_case(
    report: CalibrationReport,
    report_ref: ArtifactRef | None,
    *,
    store: Any | None,
) -> _CalibrationCase:
    """Admit new batch metrics only after a selected, fresh final-forward replay."""
    if report.ordered_batch_execution is None:
        return _CalibrationCase(report, report_ref)
    if store is None:
        return _CalibrationCase(
            report,
            report_ref,
            "not_established",
            ("ordered_autotune_metrics_require_selected_report_and_store",),
        )
    source = read_calibration_report_source(store, ref=report_ref)
    if source.status != "matched":
        return _CalibrationCase(
            report,
            report_ref,
            source.status,
            (source.code, "ordered_autotune_metrics_require_selected_report_and_store"),
        )
    selected = source.require_value()
    if selected.model_dump(mode="json") != report.model_dump(mode="json"):
        return _CalibrationCase(
            report,
            report_ref,
            "mismatch",
            ("ordered_autotune_returned_report_differs_from_selected",),
        )
    assert source.ref is not None
    status, limitations = replay_ordered_batch_report_projection(store, None, source.ref)
    return _CalibrationCase(selected, source.ref, status, limitations)


def _run_calibration_cases(
    *,
    config: CalibrationMetaSearchConfig,
    rows: list[dict[str, Any]],
    runner: Any,
    context: dict[str, Any],
    store: Any | None = None,
) -> list[_CalibrationCase]:
    reports: list[_CalibrationCase] = []
    for row in rows:
        result = runner(row, config, context)
        report_ref = None
        if isinstance(result, tuple) and len(result) == 2:
            result, report_ref = result
            if not isinstance(report_ref, ArtifactRef):
                raise TypeError("calibration_runner tuple must contain a typed selected report ref")
        if isinstance(result, CalibrationReport):
            report = CalibrationReport.model_validate(result.model_dump(mode="python"))
        elif isinstance(result, dict):
            report = CalibrationReport.model_validate(result)
        else:
            raise TypeError(
                "calibration_runner must return CalibrationReport, dict, or (report, ref)"
            )
        reports.append(_ordered_metric_case(report, report_ref, store=store))
    return reports


def _calibration_metrics(reports: list[_CalibrationCase]) -> dict[str, float]:
    if not reports:
        return {
            "sample_count": 0.0,
            "aggregate_fit_quality": 0.0,
            "runtime_cost_score": 0.0,
            "uncertainty_conditioning_score": 0.0,
            "divergence_rate": 1.0,
        }
    if any(case.source_status not in {"legacy_candidate", "matched"} for case in reports):
        # An unavailable required source is not a measured zero or an omitted row
        # in an otherwise qualified score. Withhold this split's objective.
        return {"sample_count": 0.0, "divergence_rate": 1.0}
    fit_scores = []
    runtime_scores = []
    uncertainty_scores = []
    divergence = 0
    for case in reports:
        report = case.report
        fit_scores.append(_fit_quality_score(report))
        runtime_scores.append(_runtime_score(report))
        uncertainty_scores.append(_uncertainty_score(report))
        if _has_divergence(report):
            divergence += 1
    composite = (
        (_avg(fit_scores) * 0.7) + (_avg(runtime_scores) * 0.15) + (_avg(uncertainty_scores) * 0.15)
    )
    return {
        "sample_count": float(len(reports)),
        "aggregate_fit_quality": composite,
        "runtime_cost_score": _avg(runtime_scores),
        "uncertainty_conditioning_score": _avg(uncertainty_scores),
        "divergence_rate": divergence / len(reports),
    }


def _fit_quality_score(report: CalibrationReport) -> float:
    aggregate = None if report.fit_quality is None else report.fit_quality.aggregate
    if aggregate is None:
        return 0.0
    rmse = float(aggregate.rmse)
    mae = float(aggregate.mae)
    r2_penalty = 0.0
    if aggregate.r2 is not None:
        r2_penalty = max(0.0, 1.0 - float(aggregate.r2))
    return max(0.0, min(1.0, 1.0 / (1.0 + rmse + mae + r2_penalty)))


def _runtime_score(report: CalibrationReport) -> float:
    runtime_seconds = float(report.execution_context.get("runtime_seconds", 0.0) or 0.0)
    step_count = len(report.loss_history)
    return max(0.0, min(1.0, 1.0 / (1.0 + runtime_seconds + (step_count / 100.0))))


def _uncertainty_score(report: CalibrationReport) -> float:
    if report.uncertainties is None or report.uncertainties.hessian_condition is None:
        return 1.0
    condition = max(float(report.uncertainties.hessian_condition), 1.0)
    return max(0.0, min(1.0, 1.0 / (1.0 + math.log10(condition))))


def _has_divergence(report: CalibrationReport) -> bool:
    diagnostic_text = " ".join(report.diagnostics).lower()
    if "non-finite" in diagnostic_text or "nan" in diagnostic_text or "diverg" in diagnostic_text:
        return True
    return any(not math.isfinite(value) for value in report.loss_history)


def _avg(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


__all__ = [
    "CALIBRATION_LOOP_ID",
    "CalibrationMetaEvaluator",
    "CalibrationMetaRuntimeLoader",
    "CalibrationMetaSearchConfig",
    "apply_calibration_meta_overrides",
    "build_baseline_calibration_meta_config",
    "calibration_search_loop_spec",
    "default_calibration_policy",
]
