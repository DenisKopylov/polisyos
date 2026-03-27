from __future__ import annotations

from .models import (
    BenchmarkEvaluation,
    BenchmarkSplit,
    BenchmarkSplitManifest,
    BenchmarkSuite,
    BenchmarkedEvaluator,
    ChampionPointer,
    MetricDirection,
    MutationArtifact,
    PromotionDecision,
    PromotionPolicy,
    RuntimeLoader,
    SearchLoopSpec,
    default_cas_root,
    default_search_registry_root,
    default_store,
    load_json_artifact,
    load_model_artifact,
    persist_benchmark_evaluation,
    persist_benchmark_suite,
    persist_mutation_artifact,
    persist_split_manifest,
    read_split_manifest,
    resolve_item_split,
)
from .registry import ChampionRegistry

__all__ = [
    "BenchmarkEvaluation",
    "BenchmarkSplit",
    "BenchmarkSplitManifest",
    "BenchmarkSuite",
    "BenchmarkedEvaluator",
    "ChampionPointer",
    "ChampionRegistry",
    "MetricDirection",
    "MutationArtifact",
    "PromotionDecision",
    "PromotionPolicy",
    "RuntimeLoader",
    "SearchLoopSpec",
    "default_cas_root",
    "default_search_registry_root",
    "default_store",
    "load_json_artifact",
    "load_model_artifact",
    "persist_benchmark_evaluation",
    "persist_benchmark_suite",
    "persist_mutation_artifact",
    "persist_split_manifest",
    "read_split_manifest",
    "resolve_item_split",
]

try:
    from .runtime import (
        ChampionBackedRuntimeLoader,
        PydanticMutationCodec,
        SequenceCandidateGenerator,
        SearchLoopRunner,
        seed_loop_baseline,
    )

    __all__.extend(
        [
            "ChampionBackedRuntimeLoader",
            "PydanticMutationCodec",
            "SequenceCandidateGenerator",
            "SearchLoopRunner",
            "seed_loop_baseline",
        ]
    )
except Exception:  # pragma: no cover - optional import guard for package init cycles
    pass

try:
    from .execution_plan import (
        CapabilityAwareExecutionPlanCandidateGenerator,
        build_execution_plan_generation_context,
        suggest_execution_plan_topology_mutations,
    )

    __all__.extend(
        [
            "CapabilityAwareExecutionPlanCandidateGenerator",
            "build_execution_plan_generation_context",
            "suggest_execution_plan_topology_mutations",
        ]
    )
except Exception:  # pragma: no cover - optional import guard for package init cycles
    pass
