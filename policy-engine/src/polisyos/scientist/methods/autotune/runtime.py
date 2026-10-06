"""Public autotune runtime module API."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Generic, TypeVar

from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, input_ref_from_artifact_ref
from polisyos.scientist.methods.search.controller import (
    SearchConfig,
    SearchController,
    SearchResult,
)
from polisyos.scientist.methods.search.objective import (
    BaseObjective,
    CompositeObjective,
    OptimizationDirection,
)
from polisyos.scientist.methods.search.stopping import MaxIterations

from .models import (
    BenchmarkComparisonBasis,
    BenchmarkEvaluation,
    ChampionPointer,
    MetricDirection,
    MutationArtifact,
    PromotionPolicy,
    SearchLoopSpec,
    benchmark_comparison_basis,
    benchmark_evaluator_profile,
    default_store,
    load_model_artifact,
    persist_benchmark_evaluation,
    persist_mutation_artifact,
)
from .registry import ChampionRegistry

if TYPE_CHECKING:
    from polisyos.core.artifacts.protocol import ArtifactStore


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
    store: ArtifactStore | None = None,
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
        store: ArtifactStore | None = None,
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
        return payload


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
            last = self._candidates[-1]
            return (
                last.model_dump(mode="json") if isinstance(last, MutationArtifact) else dict(last)
            )
        candidate = self._candidates[self._index]
        self._index += 1
        if isinstance(candidate, MutationArtifact):
            return candidate.model_dump(mode="json")
        return dict(candidate)


class SearchLoopRunner:
    """Search loop runner public type."""

    def __init__(
        self,
        *,
        store: ArtifactStore | None = None,
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
            if isinstance(initial_candidate, MutationArtifact)
            else initial_candidate
        )
        from polisyos.scientist.methods.search.service import _NativeSearchServiceDriver

        return _NativeSearchServiceDriver(controller).run_search(
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
            candidate,
            inputs=[input_ref_from_artifact_ref(suite_ref, role="benchmark_suite")],
        )
        basis = benchmark_comparison_basis(
            self._store,
            suite_ref,
            spec.promotion_policy,
            benchmark_evaluator_profile(spec.benchmark_evaluator),
        )
        current = self._registry.get(spec.loop_id)
        evaluation_context = {
            **dict(context),
            "store": self._store,
            "registry": self._registry,
            "policy": spec.promotion_policy,
            "loop_id": spec.loop_id,
            "benchmark_comparison_incumbent": current.model_copy(deep=True)
            if current is not None
            else None,
        }
        evaluation = spec.benchmark_evaluator.evaluate(
            candidate_ref,
            suite_ref,
            evaluation_context,
        )
        evaluation = self._bind_comparison(evaluation, basis)
        incumbent_ref = None
        if current is not None:
            # The module build identity does not bind context callbacks or
            # their state. Execute the incumbent under this same active context
            # even when the persisted suite and evaluator module are unchanged.
            incumbent = spec.benchmark_evaluator.evaluate(
                current.candidate_ref, suite_ref, evaluation_context
            )
            incumbent = self._bind_comparison(incumbent, basis)
            incumbent_ref = persist_benchmark_evaluation(self._store, incumbent)
            evaluation = evaluation.model_copy(update={"incumbent_evaluation_ref": incumbent_ref})
        evaluation_ref = persist_benchmark_evaluation(
            self._store,
            evaluation,
            inputs=[input_ref_from_artifact_ref(suite_ref, role="benchmark_suite")],
        )
        decision = self._registry.consider_promotion(
            spec.loop_id,
            candidate_ref,
            evaluation_ref,
            spec.promotion_policy,
            suite_ref=suite_ref,
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

    @staticmethod
    def _bind_comparison(
        evaluation: BenchmarkEvaluation, basis: BenchmarkComparisonBasis
    ) -> BenchmarkEvaluation:
        """Retain producer input binding; candidate-only evaluators have no external data."""
        if evaluation.incumbent_evaluation_ref is not None:
            raise ValueError("benchmark_evaluator_supplied_comparison_incumbent")
        if evaluation.comparison_basis is None:
            if basis.data_basis != "candidate_only":
                raise ValueError("benchmark_evaluator_did_not_bind_consumed_inputs")
            return evaluation.model_copy(update={"comparison_basis": basis})
        if evaluation.comparison_basis != basis:
            raise ValueError("benchmark_evaluator_comparison_basis_mismatch")
        return evaluation


__all__ = [
    "ChampionBackedRuntimeLoader",
    "PydanticMutationCodec",
    "SearchLoopRunner",
    "SearchRunArtifacts",
    "SequenceCandidateGenerator",
    "seed_loop_baseline",
]
