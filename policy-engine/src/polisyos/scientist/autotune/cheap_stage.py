"""Public autotune cheap stage module API."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import ConfigDict, Field

from .models import (
    BenchmarkEvaluation,
    BenchmarkSplit,
    BenchmarkSplitManifest,
    BenchmarkSuite,
    BenchmarkedEvaluator,
    MetricDirection,
    MutationArtifact,
    PromotionPolicy,
    SearchLoopSpec,
    default_cas_root,
    load_model_artifact,
)
from .registry import ChampionRegistry
from .runtime import ChampionBackedRuntimeLoader, PydanticMutationCodec

CHEAP_STAGE_LOOP_ID = "cheap_stage"


class CheapStageTuningConfig(MutationArtifact):
    """Cheap stage tuning config data model."""
    model_config = ConfigDict(extra="forbid")

    loop_id: str = CHEAP_STAGE_LOOP_ID
    threshold: float = Field(default=0.5, ge=0.0, le=10.0)


def build_baseline_cheap_stage_config(_context: dict[str, Any] | None = None) -> CheapStageTuningConfig:
    """Build baseline cheap stage config."""
    return CheapStageTuningConfig()


def default_cheap_stage_policy() -> PromotionPolicy:
    """Default cheap stage policy helper."""
    return PromotionPolicy(
        loop_id=CHEAP_STAGE_LOOP_ID,
        primary_metric="false_positive_rate",
        direction=MetricDirection.MINIMIZE,
        compare_split=BenchmarkSplit.HOLDOUT,
        min_improvement=0.0,
        min_sample_count=0,
        required_guardrails=[
            "sample_count_sufficient",
            "true_positive_rate_floor",
            "stage_b_eval_rate_delta_ok",
        ],
    )


def load_cheap_stage_config(
    *,
    context: dict[str, Any] | None = None,
    loader: ChampionBackedRuntimeLoader[CheapStageTuningConfig] | None = None,
) -> CheapStageTuningConfig:
    """Load cheap stage config."""
    active_loader = loader or CheapStageRuntimeLoader()
    return active_loader.load(context)


def resolve_cheap_stage_threshold(
    threshold: float | None = None,
    *,
    context: dict[str, Any] | None = None,
    loader: ChampionBackedRuntimeLoader[CheapStageTuningConfig] | None = None,
) -> float:
    """Resolve cheap stage threshold."""
    if threshold is not None:
        return float(threshold)
    return float(load_cheap_stage_config(context=context, loader=loader).threshold)


class CheapStageBenchmarkEvaluator(BenchmarkedEvaluator):
    """Cheap stage benchmark evaluator public type."""
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
            raise ValueError("CheapStageBenchmarkEvaluator requires a CAS store")
        suite = load_model_artifact(store, suite_ref, BenchmarkSuite)
        candidate = load_model_artifact(store, candidate_ref, CheapStageTuningConfig)
        if suite.dataset_path is None or suite.split_manifest_path is None:
            raise ValueError("CheapStage benchmark suite requires dataset_path and split_manifest_path")
        records = _read_jsonl(Path(suite.dataset_path))
        split_manifest = BenchmarkSplitManifest.model_validate_json(
            Path(suite.split_manifest_path).read_text(encoding="utf-8")
        )
        champion_eval_rate = self._champion_stage_b_eval_rate(
            candidate_ref=candidate_ref,
            suite=suite,
            records=records,
            split_manifest=split_manifest,
            context=context,
        )
        selection_metrics = _cheap_stage_metrics(
            [row for row in records if split_manifest.split_for(str(row["candidate_hash"])) == BenchmarkSplit.SELECTION],
            threshold=float(candidate.threshold),
            champion_eval_rate=champion_eval_rate,
        )
        holdout_metrics = _cheap_stage_metrics(
            [row for row in records if split_manifest.split_for(str(row["candidate_hash"])) == BenchmarkSplit.HOLDOUT],
            threshold=float(candidate.threshold),
            champion_eval_rate=champion_eval_rate,
        )
        total_sample_count = float(selection_metrics.get("sample_count", 0.0)) + float(
            holdout_metrics.get("sample_count", 0.0)
        )
        guardrails = {
            "sample_count_sufficient": total_sample_count >= 200.0,
            "true_positive_rate_floor": float(holdout_metrics.get("true_positive_rate", 0.0)) >= 0.80,
            "stage_b_eval_rate_delta_ok": float(holdout_metrics.get("stage_b_eval_rate_delta", 0.0)) <= 0.15,
        }
        return BenchmarkEvaluation(
            loop_id=CHEAP_STAGE_LOOP_ID,
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
        )

    def _champion_stage_b_eval_rate(
        self,
        *,
        candidate_ref,
        suite: BenchmarkSuite,
        records: list[dict[str, Any]],
        split_manifest: BenchmarkSplitManifest,
        context: dict[str, Any],
    ) -> float:
        registry = context.get("registry") or self._registry
        store = context.get("store") or self._store
        if registry is None or store is None:
            return _cheap_stage_metrics(
                [row for row in records if split_manifest.split_for(str(row["candidate_hash"])) == BenchmarkSplit.HOLDOUT],
                threshold=0.5,
                champion_eval_rate=None,
            )["stage_b_eval_rate"]
        champion = registry.get(CHEAP_STAGE_LOOP_ID)
        if champion is None or champion.candidate_ref.artifact_id == candidate_ref.artifact_id:
            return _cheap_stage_metrics(
                [row for row in records if split_manifest.split_for(str(row["candidate_hash"])) == BenchmarkSplit.HOLDOUT],
                threshold=0.5,
                champion_eval_rate=None,
            )["stage_b_eval_rate"]
        cfg = load_model_artifact(store, champion.candidate_ref, CheapStageTuningConfig)
        return _cheap_stage_metrics(
            [row for row in records if split_manifest.split_for(str(row["candidate_hash"])) == BenchmarkSplit.HOLDOUT],
            threshold=float(cfg.threshold),
            champion_eval_rate=None,
        )["stage_b_eval_rate"]


class CheapStageRuntimeLoader(ChampionBackedRuntimeLoader[CheapStageTuningConfig]):
    """Cheap stage runtime loader implementation."""
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(
            loop_id=CHEAP_STAGE_LOOP_ID,
            model_cls=CheapStageTuningConfig,
            baseline_factory=build_baseline_cheap_stage_config,
            suite_version="1.0",
            **kwargs,
        )


def write_correlation_dataset(
    records: list[dict[str, Any]],
    *,
    output_dir: Path | None = None,
    suite_id: str = "cheap_stage_correlation",
    suite_version: str = "1.0",
    holdout_fraction: float = 0.2,
) -> BenchmarkSuite:
    """Write correlation dataset helper."""
    root = (output_dir or (default_cas_root() / "autotune" / CHEAP_STAGE_LOOP_ID / datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ"))).resolve()
    root.mkdir(parents=True, exist_ok=True)
    dataset_path = root / "correlation_records.jsonl"
    split_path = root / "split_manifest.json"
    with open(dataset_path, "w", encoding="utf-8") as fh:
        for row in records:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    total = len(records)
    holdout_count = max(1, int(round(total * holdout_fraction))) if total else 0
    selection_ids = [str(row["candidate_hash"]) for row in records[: max(0, total - holdout_count)]]
    holdout_ids = [str(row["candidate_hash"]) for row in records[max(0, total - holdout_count) :]]
    split_manifest = BenchmarkSplitManifest(
        suite_id=suite_id,
        suite_version=suite_version,
        id_field="candidate_hash",
        selection_ids=selection_ids,
        holdout_ids=holdout_ids,
    )
    split_path.write_text(split_manifest.model_dump_json(indent=2), encoding="utf-8")
    return BenchmarkSuite(
        suite_id=suite_id,
        suite_version=suite_version,
        kind="cheap_stage",
        dataset_path=str(dataset_path),
        split_manifest_path=str(split_path),
        metadata={"record_count": total},
    )


def cheap_stage_search_loop_spec(
    *,
    candidate_generator: Any | None = None,
    store: Any | None = None,
    registry: ChampionRegistry | None = None,
) -> SearchLoopSpec:
    """Cheap stage search loop spec helper."""
    return SearchLoopSpec(
        loop_id=CHEAP_STAGE_LOOP_ID,
        mutation_codec=PydanticMutationCodec(CheapStageTuningConfig),
        candidate_generator=candidate_generator,
        benchmark_evaluator=CheapStageBenchmarkEvaluator(store=store, registry=registry),
        promotion_policy=default_cheap_stage_policy(),
        runtime_loader=CheapStageRuntimeLoader(store=store, registry=registry),
    )


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _cheap_stage_metrics(
    records: list[dict[str, Any]],
    *,
    threshold: float,
    champion_eval_rate: float | None,
) -> dict[str, float]:
    if not records:
        return {
            "sample_count": 0.0,
            "false_positive_rate": 0.0,
            "true_positive_rate": 0.0,
            "spearman_correlation": 0.0,
            "stage_b_eval_rate": 0.0,
            "stage_b_eval_rate_delta": 0.0,
        }
    passed = [row for row in records if float(row.get("stage_a_score", 0.0)) < threshold]
    true_positives = sum(1 for row in passed if bool(row.get("stage_b_approved")))
    false_positives = sum(1 for row in passed if not bool(row.get("stage_b_approved")))
    fp_rate = false_positives / len(passed) if passed else 0.0
    tp_rate = true_positives / len(passed) if passed else 0.0
    stage_b_eval_rate = len(passed) / len(records)
    a_scores = [float(row.get("stage_a_score", 0.0)) for row in records]
    b_scores = [float(row.get("stage_b_score", 0.0)) for row in records]
    correlation = _spearman(a_scores, b_scores)
    baseline = champion_eval_rate if champion_eval_rate is not None else stage_b_eval_rate
    return {
        "sample_count": float(len(records)),
        "false_positive_rate": fp_rate,
        "true_positive_rate": tp_rate,
        "spearman_correlation": correlation,
        "stage_b_eval_rate": stage_b_eval_rate,
        "stage_b_eval_rate_delta": stage_b_eval_rate - baseline,
    }


def _spearman(x: list[float], y: list[float]) -> float:
    n = len(x)
    if n < 2:
        return 0.0

    def rank(values: list[float]) -> list[float]:
        sorted_idx = sorted(range(n), key=lambda idx: values[idx])
        ranks = [0.0] * n
        for rank_value, idx in enumerate(sorted_idx):
            ranks[idx] = rank_value + 1
        return ranks

    rx = rank(x)
    ry = rank(y)
    mean_x = sum(rx) / n
    mean_y = sum(ry) / n
    numerator = sum((rx[idx] - mean_x) * (ry[idx] - mean_y) for idx in range(n))
    den_x = sum((rx[idx] - mean_x) ** 2 for idx in range(n)) ** 0.5
    den_y = sum((ry[idx] - mean_y) ** 2 for idx in range(n)) ** 0.5
    if den_x * den_y == 0:
        return 0.0
    return numerator / (den_x * den_y)


__all__ = [
    "CHEAP_STAGE_LOOP_ID",
    "CheapStageBenchmarkEvaluator",
    "CheapStageRuntimeLoader",
    "CheapStageTuningConfig",
    "build_baseline_cheap_stage_config",
    "cheap_stage_search_loop_spec",
    "default_cheap_stage_policy",
    "load_cheap_stage_config",
    "resolve_cheap_stage_threshold",
    "write_correlation_dataset",
]
