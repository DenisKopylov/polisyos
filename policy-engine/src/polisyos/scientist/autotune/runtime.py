"""Public autotune runtime module API."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Generic, TypeVar, cast

from pydantic import BaseModel

from polisyos.core.artifacts.manifest import ArtifactRef, InputRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.scientist.search.controller import SearchConfig, SearchController, SearchResult
from polisyos.scientist.search.objective import BaseObjective, CompositeObjective, OptimizationDirection
from polisyos.scientist.search.stopping import MaxIterations

from .models import (
    BenchmarkEvaluation,
    BenchmarkSplit,
    ChampionPointer,
    MetricDirection,
    MutationArtifact,
    PromotionPolicy,
    SearchLoopSpec,
    default_store,
    load_model_artifact,
    persist_benchmark_evaluation,
    persist_mutation_artifact,
)
from .registry import ChampionRegistry

ModelT = TypeVar("ModelT", bound=MutationArtifact)


class PydanticMutationCodec(Generic[ModelT]):
    """Pydantic mutation codec public type."""
    def __init__(self, model_cls: type[ModelT]) -> None:
        self._model_cls = model_cls

    def encode(self, payload: MutationArtifact) -> MutationArtifact:
        return self._model_cls.model_validate(payload)

    def decode(self, payload: dict[str, Any]) -> MutationArtifact:
        return self._model_cls.model_validate(payload)


def seed_loop_baseline(
    *,
    loop_id: str,
    baseline: MutationArtifact,
    store: FileSystemCAS | None = None,
    registry: ChampionRegistry | None = None,
    suite_version: str = "1.0",
    metadata: dict[str, Any] | None = None,
) -> ChampionPointer:
    """Seed loop baseline helper."""
    active_store = store or default_store()
    active_registry = registry or ChampionRegistry(store=active_store)
    candidate_ref = persist_mutation_artifact(active_store, baseline)
    evaluation = BenchmarkEvaluation(
        loop_id=loop_id,
        suite_id=f"{loop_id}.baseline",
        suite_version=suite_version,
        candidate_ref=candidate_ref,
        promotable=True,
        status="seeded_baseline",
        notes=["seeded production baseline"],
        metadata={"seeded_baseline": True, **(metadata or {})},
    )
    evaluation_ref = persist_benchmark_evaluation(
        active_store,
        evaluation,
        inputs=[InputRef(artifact_id=candidate_ref.artifact_id, role="candidate")],
    )
    return active_registry.seed_baseline(
        loop_id,
        candidate_ref=candidate_ref,
        evaluation_ref=evaluation_ref,
        suite_version=suite_version,
        metadata=metadata,
    )


class ChampionBackedRuntimeLoader(Generic[ModelT]):
    """Champion backed runtime loader implementation."""
    def __init__(
        self,
        *,
        loop_id: str,
        model_cls: type[ModelT],
        baseline_factory: Any,
        store: FileSystemCAS | None = None,
        registry: ChampionRegistry | None = None,
        suite_version: str = "1.0",
    ) -> None:
        self._loop_id = loop_id
        self._model_cls = model_cls
        self._baseline_factory = baseline_factory
        self._store = store or default_store()
        self._registry = registry or ChampionRegistry(store=self._store)
        self._suite_version = suite_version

    def ensure_baseline(self, context: dict[str, Any] | None = None) -> ChampionPointer:
        baseline = self._baseline_factory(context or {})
        return seed_loop_baseline(
            loop_id=self._loop_id,
            baseline=baseline,
            store=self._store,
            registry=self._registry,
            suite_version=self._suite_version,
        )

    def load(self, context: dict[str, Any] | None = None) -> ModelT:
        champion = self._registry.get(self._loop_id)
        if champion is None:
            champion = self.ensure_baseline(context)
        payload = load_model_artifact(self._store, champion.candidate_ref, self._model_cls)
        return cast(ModelT, payload)


class _AutotuneObjective(BaseObjective):
    def __init__(self, policy: PromotionPolicy):
        super().__init__(weight=1.0)
        self._policy = policy

    @property
    def name(self) -> str:
        return self._policy.primary_metric

    @property
    def direction(self) -> OptimizationDirection:
        return OptimizationDirection.MINIMIZE

    def _extract_value(self, results: dict[str, Any]) -> float:
        metric = float(results.get(self._policy.primary_metric, 0.0))
        if self._policy.direction == MetricDirection.MAXIMIZE:
            return -metric
        return metric


@dataclass
class SearchRunArtifacts:
    """Search run artifacts public type."""
    candidate_ref: ArtifactRef
    evaluation_ref: ArtifactRef
    evaluation: BenchmarkEvaluation


class SequenceCandidateGenerator:
    """Sequence candidate generator implementation."""
    def __init__(self, candidates: list[dict[str, Any] | MutationArtifact]) -> None:
        self._candidates = list(candidates)
        self._index = 0

    def generate(
        self,
        history: list[Any],
        current_best: dict[str, Any] | None,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        del history, current_best, context
        if self._index >= len(self._candidates):
            return (
                self._candidates[-1].model_dump(mode="json")
                if isinstance(self._candidates[-1], BaseModel)
                else dict(self._candidates[-1])
            )
        candidate = self._candidates[self._index]
        self._index += 1
        if isinstance(candidate, BaseModel):
            return candidate.model_dump(mode="json")
        return dict(candidate)


class SearchLoopRunner:
    """Search loop runner public type."""
    def __init__(
        self,
        *,
        store: FileSystemCAS | None = None,
        registry: ChampionRegistry | None = None,
    ) -> None:
        self._store = store or default_store()
        self._registry = registry or ChampionRegistry(store=self._store)

    def run(
        self,
        spec: SearchLoopSpec,
        *,
        suite_ref: ArtifactRef,
        initial_candidate: MutationArtifact | dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
        max_iterations: int = 10,
        scheduler: Any | None = None,
        dedup: Any | None = None,
    ) -> SearchResult:
        del scheduler  # reserved for future Hyperband integration
        generator = spec.candidate_generator
        if generator is None:
            raise ValueError(f"Search loop '{spec.loop_id}' is missing a candidate generator")
        objective = CompositeObjective([_AutotuneObjective(spec.promotion_policy)])
        controller = SearchController(
            config=SearchConfig(
                stopping=MaxIterations(max_iterations),
                objective=objective,
                enable_stage_a=False,
            ),
            candidate_generator=generator,
            stage_a_evaluator=lambda candidate, ctx: (0.0, True),
            stage_b_evaluator=lambda candidate, ctx: self._evaluate_candidate(
                spec,
                suite_ref=suite_ref,
                candidate_payload=candidate,
                context=ctx,
            ),
        )
        initial_payload = (
            initial_candidate.model_dump(mode="json")
            if isinstance(initial_candidate, BaseModel)
            else initial_candidate
        )
        return controller.run(
            initial_context=dict(context or {}),
            initial_candidate=initial_payload,
        )

    def _evaluate_candidate(
        self,
        spec: SearchLoopSpec,
        *,
        suite_ref: ArtifactRef,
        candidate_payload: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        codec = spec.mutation_codec
        if codec is None:
            raise ValueError(f"Search loop '{spec.loop_id}' is missing a mutation codec")
        candidate = codec.decode(candidate_payload)
        candidate_ref = persist_mutation_artifact(
            self._store,
            cast(MutationArtifact, candidate),
            inputs=[InputRef(artifact_id=suite_ref.artifact_id, role="benchmark_suite")],
        )
        evaluation = spec.benchmark_evaluator.evaluate(
            candidate_ref,
            suite_ref,
            {
                **dict(context),
                "store": self._store,
                "registry": self._registry,
                "policy": spec.promotion_policy,
                "loop_id": spec.loop_id,
            },
        )
        evaluation_ref = persist_benchmark_evaluation(
            self._store,
            evaluation,
            inputs=[InputRef(artifact_id=suite_ref.artifact_id, role="benchmark_suite")],
        )
        decision = self._registry.consider_promotion(
            spec.loop_id,
            candidate_ref,
            evaluation_ref,
            spec.promotion_policy,
        )
        metrics = evaluation.metrics_for_split(spec.promotion_policy.compare_split)
        primary_value = metrics.get(spec.promotion_policy.primary_metric, 0.0)
        return {
            "simulation_results": {
                spec.promotion_policy.primary_metric: primary_value,
                "evaluation_ref": str(evaluation_ref.artifact_id),
                "candidate_ref": str(candidate_ref.artifact_id),
            },
            "feedback": {
                "verdict": "APPROVE" if evaluation.promotable else "REJECT",
                "promotion_decision": decision.model_dump(mode="json"),
                "guardrails": dict(evaluation.guardrails),
                "status": evaluation.status,
            },
        }


__all__ = [
    "ChampionBackedRuntimeLoader",
    "PydanticMutationCodec",
    "SequenceCandidateGenerator",
    "SearchLoopRunner",
    "SearchRunArtifacts",
    "seed_loop_baseline",
]
