"""Public autotune reflexion module API."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from polisyos.common import serialization
from polisyos.scientist.agent.failure_card import FailureCard, FailureSeverity, FailureSource

from .models import (
    BenchmarkedEvaluator,
    BenchmarkEvaluation,
    BenchmarkSplit,
    BenchmarkSplitManifest,
    BenchmarkSuite,
    MetricDirection,
    MutationArtifact,
    PromotionPolicy,
    SearchLoopSpec,
    default_cas_root,
    load_model_artifact,
    read_split_manifest,
)
from .registry import ChampionRegistry
from .runtime import ChampionBackedRuntimeLoader, PydanticMutationCodec

REFLEXION_LOOP_ID = "reflexion_routing"


class RecoverableRoutingDecision(str, Enum):
    """Recoverable routing decision public type."""

    RETURN_TO_FORMALIZER = "return_to_formalizer"
    RETURN_TO_DRAFTER = "return_to_drafter"
    ESCALATE_TO_HUMAN = "escalate_to_human"


class ReflexionRoutingRule(BaseModel):
    """Reflexion routing rule data model."""

    model_config = ConfigDict(extra="forbid")

    error_codes: list[str] = Field(default_factory=list)
    source_steps: list[FailureSource] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    decision: RecoverableRoutingDecision


class ReflexionRoutingConfig(MutationArtifact):
    """Reflexion routing config data model."""

    model_config = ConfigDict(extra="forbid")

    loop_id: str = REFLEXION_LOOP_ID
    rules: list[ReflexionRoutingRule] = Field(default_factory=list)


def build_baseline_reflexion_routing_config(
    _context: dict[str, Any] | None = None,
) -> ReflexionRoutingConfig:
    """Build baseline reflexion routing config."""
    return ReflexionRoutingConfig()


def default_reflexion_policy() -> PromotionPolicy:
    """Default reflexion policy helper."""
    return PromotionPolicy(
        loop_id=REFLEXION_LOOP_ID,
        primary_metric="retry_success_rate",
        direction=MetricDirection.MAXIMIZE,
        compare_split=BenchmarkSplit.HOLDOUT,
        min_improvement=0.0,
        min_sample_count=1,
        required_guardrails=["unsafe_nonhuman_route_rate_zero"],
    )


def route_recoverable_failure(
    card: FailureCard,
    *,
    config: ReflexionRoutingConfig,
) -> str | None:
    """Route recoverable failure helper."""
    if card.severity != FailureSeverity.RECOVERABLE:
        return None
    summary = f"{card.error_code}\n{card.violation_summary}\n{card.remediation_advice}".lower()
    for rule in config.rules:
        if rule.error_codes and card.error_code not in rule.error_codes:
            continue
        if rule.source_steps and card.source_step not in rule.source_steps:
            continue
        if rule.keywords and not any(keyword.lower() in summary for keyword in rule.keywords):
            continue
        return rule.decision.value
    return None


def load_reflexion_routing_config(
    *,
    context: dict[str, Any] | None = None,
    loader: ChampionBackedRuntimeLoader[ReflexionRoutingConfig] | None = None,
) -> ReflexionRoutingConfig:
    """Load reflexion routing config."""
    active_loader = loader or ReflexionRoutingRuntimeLoader()
    return active_loader.load(context)


class ReflexionRoutingEvaluator(BenchmarkedEvaluator):
    """Reflexion routing evaluator public type."""

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
            raise ValueError("ReflexionRoutingEvaluator requires a CAS store")
        suite = load_model_artifact(store, suite_ref, BenchmarkSuite)
        config = load_model_artifact(store, candidate_ref, ReflexionRoutingConfig)
        if suite.dataset_path is None or suite.split_manifest_path is None:
            raise ValueError(
                "Reflexion benchmark suite requires dataset_path and split_manifest_path"
            )
        rows = _read_jsonl(Path(suite.dataset_path))
        split_manifest = read_split_manifest(Path(suite.split_manifest_path))
        selection_metrics = _reflexion_metrics(
            config=config,
            rows=[
                row
                for row in rows
                if split_manifest.split_for(str(row["case_id"])) == BenchmarkSplit.SELECTION
            ],
        )
        holdout_metrics = _reflexion_metrics(
            config=config,
            rows=[
                row
                for row in rows
                if split_manifest.split_for(str(row["case_id"])) == BenchmarkSplit.HOLDOUT
            ],
        )
        guardrails = {
            "unsafe_nonhuman_route_rate_zero": float(
                holdout_metrics.get("unsafe_nonhuman_route_rate", 1.0)
            )
            == 0.0,
        }
        return BenchmarkEvaluation(
            loop_id=REFLEXION_LOOP_ID,
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


class ReflexionRoutingRuntimeLoader(ChampionBackedRuntimeLoader[ReflexionRoutingConfig]):
    """Reflexion routing runtime loader implementation."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(
            loop_id=REFLEXION_LOOP_ID,
            model_cls=ReflexionRoutingConfig,
            baseline_factory=build_baseline_reflexion_routing_config,
            suite_version="1.0",
            **kwargs,
        )


class ReflexionReplayRecorder:
    """Reflexion replay recorder public type."""

    def __init__(self) -> None:
        self._records: list[dict[str, Any]] = []

    def record_case(
        self,
        *,
        case_id: str,
        card: FailureCard,
        decision_outcomes: dict[str, bool],
        unsafe_for_nonhuman: bool = False,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self._records.append(
            {
                "case_id": case_id,
                "failure_card": {
                    key: value
                    for key, value in serialization.artifact_self_identity_projection(card).items()
                    if key != "can_retry"
                },
                "decision_outcomes": {
                    str(key): bool(value) for key, value in decision_outcomes.items()
                },
                "unsafe_for_nonhuman": bool(unsafe_for_nonhuman),
                "metadata": dict(metadata or {}),
            }
        )

    def records(self) -> list[dict[str, Any]]:
        return list(self._records)

    def write_dataset(
        self,
        *,
        output_dir: Path | None = None,
        suite_id: str = "reflexion_replay",
        suite_version: str = "1.0",
        holdout_fraction: float = 0.2,
    ) -> BenchmarkSuite:
        root = (
            output_dir
            or (
                default_cas_root()
                / "autotune"
                / REFLEXION_LOOP_ID
                / datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
            )
        ).resolve()
        root.mkdir(parents=True, exist_ok=True)
        dataset_path = root / "replay_cases.jsonl"
        split_path = root / "split_manifest.json"
        with open(dataset_path, "w", encoding="utf-8") as fh:
            for row in self._records:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        total = len(self._records)
        holdout_count = max(1, int(round(total * holdout_fraction))) if total else 0
        split_manifest = BenchmarkSplitManifest(
            suite_id=suite_id,
            suite_version=suite_version,
            id_field="case_id",
            selection_ids=[
                str(row["case_id"]) for row in self._records[: max(0, total - holdout_count)]
            ],
            holdout_ids=[
                str(row["case_id"]) for row in self._records[max(0, total - holdout_count) :]
            ],
        )
        split_path.write_text(split_manifest.model_dump_json(indent=2), encoding="utf-8")
        return BenchmarkSuite(
            suite_id=suite_id,
            suite_version=suite_version,
            kind="reflexion_routing",
            dataset_path=str(dataset_path),
            split_manifest_path=str(split_path),
            metadata={"record_count": total},
        )


def reflexion_search_loop_spec(
    *,
    candidate_generator: Any | None = None,
    store: Any | None = None,
    registry: ChampionRegistry | None = None,
) -> SearchLoopSpec:
    """Reflexion search loop spec helper."""
    return SearchLoopSpec(
        loop_id=REFLEXION_LOOP_ID,
        mutation_codec=PydanticMutationCodec(ReflexionRoutingConfig),
        candidate_generator=candidate_generator,
        benchmark_evaluator=ReflexionRoutingEvaluator(store=store, registry=registry),
        promotion_policy=default_reflexion_policy(),
        runtime_loader=ReflexionRoutingRuntimeLoader(store=store, registry=registry),
    )


def _reflexion_metrics(
    *,
    config: ReflexionRoutingConfig,
    rows: list[dict[str, Any]],
) -> dict[str, float]:
    if not rows:
        return {
            "sample_count": 0.0,
            "retry_success_rate": 0.0,
            "wasted_retry_rate": 0.0,
            "unsafe_nonhuman_route_rate": 0.0,
        }
    success_count = 0
    wasted_count = 0
    unsafe_count = 0
    for row in rows:
        card = FailureCard.model_validate(row["failure_card"])
        chosen = route_recoverable_failure(card, config=config)
        if chosen is None:
            chosen = _default_recoverable_route(card)
        outcomes = {
            str(key): bool(value) for key, value in dict(row.get("decision_outcomes") or {}).items()
        }
        success = bool(outcomes.get(chosen, False))
        if success:
            success_count += 1
        if not success and any(value for value in outcomes.values()):
            wasted_count += 1
        if (
            bool(row.get("unsafe_for_nonhuman"))
            and chosen != RecoverableRoutingDecision.ESCALATE_TO_HUMAN.value
        ):
            unsafe_count += 1
    total = len(rows)
    return {
        "sample_count": float(total),
        "retry_success_rate": success_count / total,
        "wasted_retry_rate": wasted_count / total,
        "unsafe_nonhuman_route_rate": unsafe_count / total,
    }


def _default_recoverable_route(card: FailureCard) -> str:
    if card.remediation_target.value == "drafter":
        return RecoverableRoutingDecision.RETURN_TO_DRAFTER.value
    if card.remediation_target.value == "human":
        return RecoverableRoutingDecision.ESCALATE_TO_HUMAN.value
    return RecoverableRoutingDecision.RETURN_TO_FORMALIZER.value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


__all__ = [
    "REFLEXION_LOOP_ID",
    "RecoverableRoutingDecision",
    "ReflexionReplayRecorder",
    "ReflexionRoutingConfig",
    "ReflexionRoutingEvaluator",
    "ReflexionRoutingRule",
    "ReflexionRoutingRuntimeLoader",
    "build_baseline_reflexion_routing_config",
    "default_reflexion_policy",
    "load_reflexion_routing_config",
    "reflexion_search_loop_spec",
    "route_recoverable_failure",
]
