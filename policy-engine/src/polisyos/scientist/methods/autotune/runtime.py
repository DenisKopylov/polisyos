"""Public autotune runtime module API."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any, Generic, TypeVar

from polisyos.common.serialization import finite_real_scalar
from polisyos.core.artifacts.manifest import ArtifactRef, input_ref_from_artifact_ref
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
from polisyos.scientist.methods.search.run_state import _canonical_checkpoint_owner, checkpoint_json
from polisyos.scientist.methods.search.stopping import (
    CompositeStoppingCriterion,
    CostBudgetStopping,
    MaxIterations,
    StoppingCriterion,
)

from .dedup import TrialDeduplicator
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
    verified_artifact_snapshot,
)
from .registry import ChampionRegistry

if TYPE_CHECKING:
    from polisyos.core.artifacts.protocol import ArtifactStore
    from polisyos.scientist.methods.search.service import NativeSearchService
    from polisyos.scientist.orchestration.engine.budget_middleware import (
        BudgetMiddleware,
    )


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
        inputs=[input_ref_from_artifact_ref(candidate_ref, role="candidate")],
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
        payload = load_model_artifact(
            self._store, champion.candidate_ref, self._model_cls
        )
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
        metric = finite_real_scalar(results.get(self._policy.primary_metric))
        if metric is None:
            return float("nan")
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
        if not self._candidates:
            raise ValueError("sequence_generator_requires_nonempty_corpus")
        self._index = 0

    def get_state(self) -> dict[str, Any] | None:
        """Persist the real corpus/cursor, or expose a changed profile as live-only."""
        if not _canonical_checkpoint_owner(
            self, SequenceCandidateGenerator, absent_methods=("generate_batch",)
        ):
            return None
        return {
            "version": "sequence-generator.v1",
            "candidates": checkpoint_json(self._candidates),
            "index": self._index,
        }

    def validate_checkpoint_history(
        self, history: list[Any], state: dict[str, Any]
    ) -> None:
        """Admit the corpus/cursor of this history-independent scalar generator."""
        if not _canonical_checkpoint_owner(
            self, SequenceCandidateGenerator, absent_methods=("generate_batch",)
        ):
            raise ValueError("sequence_generator_checkpoint_history_profile_unsupported")
        del history  # The admitted actual generate() does not consume history.
        expected = self.get_state()
        if expected is None:
            raise ValueError("sequence_generator_checkpoint_history_profile_unsupported")
        if (
            set(state) != set(expected)
            or state["version"] != expected["version"]
            or state["candidates"] != expected["candidates"]
            or type(state["index"]) is not int
            or not 0 <= state["index"] <= len(self._candidates)
        ):
            raise ValueError("sequence_generator_checkpoint_mismatch")

    def set_state(self, state: dict[str, Any]) -> None:
        """Admit the same corpus before changing the next-candidate cursor."""
        SequenceCandidateGenerator.validate_checkpoint_history(self, [], state)
        self._index = state["index"]

    def generate(
        self,
        history: list[Any],
        current_best: dict[str, Any] | None,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        del history, current_best, context
        if not self._candidates:
            raise ValueError("sequence_generator_requires_nonempty_corpus")
        if self._index >= len(self._candidates):
            last = self._candidates[-1]
            return (
                last.model_dump(mode="json")
                if isinstance(last, MutationArtifact)
                else dict(last)
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
        budget_middleware: BudgetMiddleware | None = None,
        budget_key: str = "run",
        cost_budget_usd: float | None = None,
    ) -> None:
        if not isinstance(budget_key, str) or not budget_key.strip():
            raise ValueError("search_runner_budget_key_requires_nonblank_string")
        if budget_middleware is not None:
            from polisyos.scientist.orchestration.engine.budget_middleware import (
                BudgetMiddleware,
            )

            if not isinstance(budget_middleware, BudgetMiddleware):
                raise ValueError("search_runner_requires_canonical_budget_middleware")
        if cost_budget_usd is not None and budget_middleware is None:
            raise ValueError("search_runner_cost_budget_requires_canonical_owner")
        # Delegate the existing strict positive USD law once, without treating
        # a literal recorded zero as an absent measurement or inventing a limit.
        self._cost_budget_usd = (
            CostBudgetStopping(cost_budget_usd)._max_cost
            if cost_budget_usd is not None
            else None
        )
        self._budget_middleware = budget_middleware
        self._budget_key = budget_key
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
        dedup: TrialDeduplicator | None = None,
    ) -> SearchResult:
        del scheduler  # reserved for future Hyperband integration
        service = self.create_service(
            spec, suite_ref=suite_ref, max_iterations=max_iterations, dedup=dedup
        )
        initial_payload = (
            initial_candidate.model_dump(mode="json")
            if isinstance(initial_candidate, MutationArtifact)
            else initial_candidate
        )
        return service.run_search(
            initial_context=dict(context or {}), initial_candidate=initial_payload
        )

    def create_service(
        self,
        spec: SearchLoopSpec,
        *,
        suite_ref: ArtifactRef,
        max_iterations: int = 10,
        dedup: TrialDeduplicator | None = None,
    ) -> NativeSearchService:
        """Build the native persisted service with this runner's actual evaluator."""
        from polisyos.scientist.methods.search.service import NativeSearchService

        generator = spec.candidate_generator
        if generator is None:
            raise ValueError(
                f"Search loop '{spec.loop_id}' is missing a candidate generator"
            )
        generator, analysis = self._configured_generator(spec)
        spec = replace(spec, candidate_generator=generator)
        objective = CompositeObjective([_AutotuneObjective(spec.promotion_policy)])
        stopping: StoppingCriterion = MaxIterations(max_iterations)
        if self._cost_budget_usd is not None:
            stopping = CompositeStoppingCriterion(
                [CostBudgetStopping(self._cost_budget_usd), stopping]
            )
        controller = SearchController(
            config=SearchConfig(
                stopping=stopping,
                objective=objective,
                enable_stage_a=False,
                budget_middleware=self._budget_middleware,
                budget_key=self._budget_key,
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
        return NativeSearchService(
            controller,
            store=self._store,
            dedup=dedup,
            basis={
                "loop_id": spec.loop_id,
                "suite_ref": suite_ref.model_dump(mode="json"),
                "promotion_policy": spec.promotion_policy.model_dump(mode="json"),
                "evaluator_profile": benchmark_evaluator_profile(
                    spec.benchmark_evaluator
                ),
                "analysis_configuration": analysis,
            },
        )

    def _configured_generator(
        self, spec: SearchLoopSpec
    ) -> tuple[Any, dict[str, Any] | None]:
        """Activate a declared exploratory analysis before controller creation."""
        if not isinstance(spec.metadata, dict):
            raise ValueError("search_loop_metadata_requires_mapping")
        names = {"analysis_ref", "analysis_order_profile", "analysis_purpose"}
        present = names & spec.metadata.keys()
        generator = spec.candidate_generator
        if not present:
            return generator, None
        if (
            present != names
            or spec.metadata["analysis_order_profile"]
            != "exploratory_coordinate_order.v1"
            or spec.metadata["analysis_purpose"] != "exploratory"
        ):
            raise ValueError(
                "search_analysis_configuration_requires_known_exploratory_profile"
            )
        ref = ArtifactRef.model_validate(spec.metadata["analysis_ref"])
        if ref.manifest_profile_sha256 is None:
            raise ValueError("search_analysis_requires_selected_manifest_profile")
        from polisyos.scientist.methods.autotune.bayesian_generator import (
            BayesianCandidateGenerator,
        )
        from polisyos.scientist.methods.search.sensitivity_adapter import (
            SensitivityAwareCandidateGenerator,
        )

        base = (
            generator._base
            if type(generator) is SensitivityAwareCandidateGenerator
            else generator
        )
        if type(base) is not BayesianCandidateGenerator:
            raise ValueError("search_analysis_requires_canonical_native_generator")
        configured = SensitivityAwareCandidateGenerator.from_artifact(
            generator, self._store, ref
        )
        if configured.order_profile != spec.metadata["analysis_order_profile"]:
            raise ValueError("search_analysis_order_profile_unsupported_by_generator")
        configured_ref = configured.analysis_ref
        if configured_ref is None or configured_ref != ref:
            raise ValueError("search_analysis_artifact_ref_configuration_mismatch")
        return configured, {
            "analysis_ref": configured_ref.model_dump(mode="json"),
            "order_profile": configured.order_profile,
            "purpose": "exploratory",
        }

    @staticmethod
    def _codec_payload(spec: SearchLoopSpec, payload: dict[str, Any]) -> dict[str, Any]:
        """Project the canonical native technical envelope for a strict typed mutation."""
        if type(spec.mutation_codec) is not PydanticMutationCodec:
            return payload
        if type(spec.candidate_generator).__module__ not in {
            "polisyos.scientist.methods.autotune.bayesian_generator",
            "polisyos.scientist.methods.search.sensitivity_adapter",
            "polisyos.scientist.methods.search.strategies.adapter",
        }:
            return payload
        from polisyos.scientist.methods.autotune.bayesian_generator import (
            BayesianCandidateGenerator,
        )
        from polisyos.scientist.methods.search.sensitivity_adapter import (
            SensitivityAwareCandidateGenerator,
        )
        from polisyos.scientist.methods.search.strategies.adapter import StrategyAdapter

        generator = spec.candidate_generator
        adapter = (
            generator if type(generator) is SensitivityAwareCandidateGenerator else None
        )
        base = adapter._base if adapter is not None else generator
        if type(base) not in (BayesianCandidateGenerator, StrategyAdapter):
            return payload
        candidate = dict(payload)
        if "_sensitivity" in candidate:
            if (
                adapter is None
                or adapter.order_profile != "exploratory_coordinate_order.v1"
                or candidate["_sensitivity"] != adapter._metadata()
            ):
                raise ValueError("search_candidate_sensitivity_configuration_mismatch")
            candidate.pop("_sensitivity")
        elif adapter is not None:
            raise ValueError("search_candidate_sensitivity_metadata_missing")
        if "_strategy_metadata" in candidate:
            if not isinstance(candidate["_strategy_metadata"], dict):
                raise ValueError("search_candidate_native_metadata_requires_mapping")
            candidate.pop("_strategy_metadata")
            candidate.setdefault("loop_id", spec.loop_id)
        if (
            "semantic" not in spec.mutation_codec._model_cls.model_fields
            and candidate.get("semantic") == {"interventions": []}
        ):
            candidate.pop("semantic")
        return candidate

    def resume(
        self,
        spec: SearchLoopSpec,
        *,
        suite_ref: ArtifactRef,
        checkpoint_ref: ArtifactRef,
        context: dict[str, Any] | None = None,
        max_iterations: int = 10,
        dedup: TrialDeduplicator | None = None,
    ) -> SearchResult:
        """Reopen an exact checkpoint using a freshly configured native service."""
        service = self.create_service(
            spec, suite_ref=suite_ref, max_iterations=max_iterations, dedup=dedup
        )
        service.restore(checkpoint_ref, context=context)
        return service.resume_search(context=context)

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
            raise ValueError(
                f"Search loop '{spec.loop_id}' is missing a mutation codec"
            )
        candidate = codec.decode(self._codec_payload(spec, candidate_payload))
        inputs = [input_ref_from_artifact_ref(suite_ref, role="benchmark_suite")]
        generator = spec.candidate_generator
        if (
            type(generator).__module__
            == "polisyos.scientist.methods.search.sensitivity_adapter"
        ):
            from polisyos.scientist.methods.search.sensitivity_adapter import (
                SensitivityAwareCandidateGenerator,
            )

            if (
                type(generator) is SensitivityAwareCandidateGenerator
                and generator.analysis_ref
            ):
                verified_artifact_snapshot(self._store, generator.analysis_ref)
                inputs.append(
                    input_ref_from_artifact_ref(
                        generator.analysis_ref, role="sensitivity_analysis"
                    )
                )
        candidate_ref = persist_mutation_artifact(
            self._store,
            candidate,
            inputs=inputs,
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
            evaluation = evaluation.model_copy(
                update={"incumbent_evaluation_ref": incumbent_ref}
            )
        evaluation_ref = persist_benchmark_evaluation(
            self._store,
            evaluation,
            inputs=inputs,
        )
        decision = self._registry.consider_promotion(
            spec.loop_id,
            candidate_ref,
            evaluation_ref,
            spec.promotion_policy,
            suite_ref=suite_ref,
        )
        metrics = evaluation.metrics_for_split(spec.promotion_policy.compare_split)
        measured = finite_real_scalar(metrics.get(spec.promotion_policy.primary_metric))
        unavailable_reason = (
            "evaluation_status_not_comparable"
            if evaluation.status != "ok"
            else "primary_metric_missing"
            if spec.promotion_policy.primary_metric not in metrics
            else "primary_metric_invalid"
            if measured is None
            else None
        )
        primary_value = measured if unavailable_reason is None else None
        return {
            "simulation_results": {
                spec.promotion_policy.primary_metric: primary_value,
                "primary_metric_assessment": {
                    "status": "available"
                    if unavailable_reason is None
                    else "unavailable",
                    "metric": spec.promotion_policy.primary_metric,
                    "split": spec.promotion_policy.compare_split.value,
                    "direction": spec.promotion_policy.direction.value,
                    "unit": spec.promotion_policy.unit,
                    "reason": unavailable_reason,
                },
                "evaluation_ref": str(evaluation_ref.artifact_id),
                "candidate_ref": str(candidate_ref.artifact_id),
                "evaluation_artifact_ref": evaluation_ref.model_dump(mode="json"),
                "candidate_artifact_ref": candidate_ref.model_dump(mode="json"),
                "suite_artifact_ref": suite_ref.model_dump(mode="json"),
            },
            "feedback": {
                "verdict": "APPROVE"
                if evaluation.promotable and unavailable_reason is None
                else "REJECT",
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
