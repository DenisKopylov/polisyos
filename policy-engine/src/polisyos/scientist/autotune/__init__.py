"""Stable autotune facade for search-loop contracts, persistence, and optional runtimes.

Eager exports cover the registry-facing models and CAS helpers that planners and
promotion logic depend on directly. Runtime loaders and candidate generators are
lazy-loaded so importing this facade does not force heavyweight execution
dependencies or import-cycle-prone modules.
"""
from __future__ import annotations

import importlib
from typing import Any

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

_OPTIONAL_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "ChampionBackedRuntimeLoader": (
        "polisyos.scientist.autotune.runtime",
        "ChampionBackedRuntimeLoader",
    ),
    "PydanticMutationCodec": (
        "polisyos.scientist.autotune.runtime",
        "PydanticMutationCodec",
    ),
    "SequenceCandidateGenerator": (
        "polisyos.scientist.autotune.runtime",
        "SequenceCandidateGenerator",
    ),
    "SearchLoopRunner": (
        "polisyos.scientist.autotune.runtime",
        "SearchLoopRunner",
    ),
    "seed_loop_baseline": (
        "polisyos.scientist.autotune.runtime",
        "seed_loop_baseline",
    ),
    "CapabilityAwareExecutionPlanCandidateGenerator": (
        "polisyos.scientist.autotune.execution_plan",
        "CapabilityAwareExecutionPlanCandidateGenerator",
    ),
    "build_execution_plan_generation_context": (
        "polisyos.scientist.autotune.execution_plan",
        "build_execution_plan_generation_context",
    ),
    "suggest_execution_plan_topology_mutations": (
        "polisyos.scientist.autotune.execution_plan",
        "suggest_execution_plan_topology_mutations",
    ),
}


def __getattr__(name: str) -> Any:
    if name not in _OPTIONAL_LAZY_IMPORTS:
        raise AttributeError(f"module 'polisyos.scientist.autotune' has no attribute '{name}'")
    module_name, attr_name = _OPTIONAL_LAZY_IMPORTS[name]
    module = importlib.import_module(module_name)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value

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
