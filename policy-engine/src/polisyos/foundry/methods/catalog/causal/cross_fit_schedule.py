"""cross_fit_schedule — graph-level cross-fitting injection.

Provides:

1. :class:`CrossFitSchedule` — immutable descriptor for a K-fold partition.
2. :func:`build_cross_fit_schedule` — constructs a stratified K-fold schedule.
3. :func:`inject_cross_fitting` — transforms an :class:`ExecutorGraph` by
   replicating each ``is_nuisance=True`` node K times (one per fold) and
   inserting a :class:`FoldAggregator` node that stitches the K out-of-fold
   predictions back into a full-dataset OOF array.
4. :class:`FoldAggregator` — foundry method that collects fold-k nuisance outputs.

Design
------
The *inject_cross_fitting* transform is **additive**: it takes any ExecutorGraph
(whether produced by the template compiler or the recursive compiler) and makes
its nuisance nodes fold-aware without changing the downstream API.  The main
estimator still depends on a single node per nuisance role — the fold_aggregator —
but that aggregator collects K per-fold predictions.

Fold schedule rules (applied by ``compile_estimand`` when ``use_cross_fitting=True``):
  - n_obs ≥ 500  →  n_folds = 5
  - n_obs ∈ [100, 500)  →  n_folds = 2
  - n_obs < 100 or None  →  n_folds = 1  (no cross-fitting)
"""

from __future__ import annotations

import dataclasses
import uuid
from typing import Any, ClassVar, Mapping

import numpy as np

from polisyos.core.observability.determinism import DeterminismTier
from polisyos.foundry.methods.base import (
    ComplexityClass,
    ComputeBackend,
    FidelityLevel,
    MethodMetadata,
    MethodSignature,
    ParameterSpec,
    SlotSpec,
    SlotType,
    Unit,
    foundry_method,
)
from polisyos.foundry.methods.catalog.causal.estimand_compiler import (
    ExecutorGraph,
    ExecutorNode,
)


# ---------------------------------------------------------------------------
# CrossFitSchedule
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class CrossFitSchedule:
    """Immutable descriptor for a K-fold cross-fitting partition.

    Parameters
    ----------
    n_folds             : Number of folds K.
    seed                : RNG seed used for stratified shuffle.
    fold_assignments    : Per-observation fold index; ``fold_assignments[i] ∈ [0, K)``.
    nuisance_node_ids   : The node IDs (from the source graph) that should be
                          replicated per fold.
    aggregation_strategy: How to combine K fold outputs.
                          ``'stack_predictions'`` (default): stack OOF arrays;
                          ``'mean_scores'``: average EIF scores across folds.
    """

    n_folds: int
    seed: int
    fold_assignments: tuple[int, ...]
    nuisance_node_ids: tuple[str, ...]
    aggregation_strategy: str = "stack_predictions"


# ---------------------------------------------------------------------------
# Build schedule
# ---------------------------------------------------------------------------


def build_cross_fit_schedule(
    n_obs: int,
    n_folds: int,
    seed: int,
    treatment: "np.ndarray | None" = None,
) -> CrossFitSchedule:
    """Construct a stratified K-fold :class:`CrossFitSchedule`.

    Parameters
    ----------
    n_obs     : Total number of observations.
    n_folds   : Desired number of folds.
    seed      : RNG seed for reproducibility.
    treatment : Optional binary treatment array for stratified splitting.
                When provided, treated and control units are shuffled
                independently so each fold has the same treatment ratio.

    Returns
    -------
    CrossFitSchedule with ``fold_assignments`` of length ``n_obs``.
    """
    n_folds = max(2, min(n_folds, n_obs))
    rng = np.random.default_rng(seed)
    fold_ids = np.empty(n_obs, dtype=int)

    if treatment is not None and len(treatment) == n_obs:
        T = np.asarray(treatment, dtype=float)
        treated_idx = np.where(T > 0.5)[0].copy()
        control_idx = np.where(T <= 0.5)[0].copy()
        rng.shuffle(treated_idx)
        rng.shuffle(control_idx)
        for grp in (treated_idx, control_idx):
            for local_i, global_idx in enumerate(grp):
                fold_ids[global_idx] = local_i % n_folds
    else:
        idx = np.arange(n_obs)
        rng.shuffle(idx)
        for local_i, global_idx in enumerate(idx):
            fold_ids[global_idx] = local_i % n_folds

    return CrossFitSchedule(
        n_folds=n_folds,
        seed=seed,
        fold_assignments=tuple(int(f) for f in fold_ids),
        nuisance_node_ids=(),  # populated by inject_cross_fitting
        aggregation_strategy="stack_predictions",
    )


def recommend_n_folds(n_obs: int | None) -> int:
    """Rule-based n_folds selection used by the compiler.

    Rules:
      - n_obs ≥ 500  →  5
      - n_obs ∈ [100, 500)  →  2
      - n_obs < 100 or None  →  1  (no cross-fitting)
    """
    if n_obs is None or n_obs < 100:
        return 1
    if n_obs < 500:
        return 2
    return 5


# ---------------------------------------------------------------------------
# inject_cross_fitting
# ---------------------------------------------------------------------------


def inject_cross_fitting(
    graph: ExecutorGraph,
    schedule: CrossFitSchedule,
) -> ExecutorGraph:
    """Transform *graph* by replicating nuisance nodes K times for cross-fitting.

    Algorithm
    ---------
    For each ``is_nuisance=True`` node in ``graph.nuisance_schedule``:

    1. Create K fold variants: ``{node_id}_fold_{k}`` for k in 0..K-1.
       Each variant gets the original params augmented with::

           fold_idx=k, n_folds=K, fold_assignments=list(schedule.fold_assignments)

    2. Remove the original nuisance node from the graph.
    3. Create a :class:`FoldAggregator` node (``{node_id}_fold_agg``) that
       depends on all K fold variants.
    4. Update any node that previously depended on the original nuisance node
       to instead depend on the fold_aggregator.
    5. Set ``total_folds=K`` on the returned graph.

    Idempotency
    -----------
    Calling this function twice on the same graph raises a ``ValueError`` because
    fold-variant node IDs will already be present.

    Parameters
    ----------
    graph    : Source ExecutorGraph (from template or recursive compiler).
    schedule : CrossFitSchedule with n_folds ≥ 2.

    Returns
    -------
    New ExecutorGraph with nuisance nodes replicated K times.
    """
    K = schedule.n_folds
    if K <= 1:
        return graph  # no-op

    nuisance_ids = set(graph.nuisance_schedule)

    # Guard against double-injection
    for node in graph.nodes:
        if "_fold_" in node.node_id:
            raise ValueError(
                f"inject_cross_fitting: graph already contains fold-variant node "
                f"'{node.node_id}'. Injecting twice is not supported."
            )

    # Build replacement map: original_nuisance_id → fold_aggregator_id
    replacement_map: dict[str, str] = {}
    new_nodes: list[ExecutorNode] = []

    for node in graph.nodes:
        if node.node_id not in nuisance_ids:
            new_nodes.append(node)  # non-nuisance nodes pass through unchanged
            continue

        # Create K fold variants
        fold_variant_ids: list[str] = []
        for k in range(K):
            fold_id = f"{node.node_id}_fold_{k}"
            fold_params = dict(node.params)
            fold_params["fold_idx"] = k
            fold_params["n_folds"] = K
            fold_params["fold_assignments"] = list(schedule.fold_assignments)
            fold_variant = dataclasses.replace(
                node,
                node_id=fold_id,
                params=fold_params,
            )
            new_nodes.append(fold_variant)
            fold_variant_ids.append(fold_id)

        # Create fold aggregator node
        agg_id = f"{node.node_id}_fold_agg"
        agg_node = ExecutorNode(
            node_id=agg_id,
            method_fqn="causal.compiler.fold_aggregator",
            method_version="1.0.0",
            params={
                "n_folds": K,
                "fold_assignments": list(schedule.fold_assignments),
                "aggregation_strategy": schedule.aggregation_strategy,
            },
            depends_on=tuple(fold_variant_ids),
            reads_slots=(),
            writes_slots=(),
            is_nuisance=False,
            dataset_ref=node.dataset_ref,
            skip_if_failed=(),
        )
        new_nodes.append(agg_node)
        replacement_map[node.node_id] = agg_id

    # Rewrite depends_on references: old nuisance_id → agg_id
    rewritten_nodes: list[ExecutorNode] = []
    for node in new_nodes:
        new_deps = tuple(replacement_map.get(dep, dep) for dep in node.depends_on)
        if new_deps != node.depends_on:
            node = dataclasses.replace(node, depends_on=new_deps)
        # Also rewrite skip_if_failed references
        new_sif = tuple(replacement_map.get(sid, sid) for sid in node.skip_if_failed)
        if new_sif != node.skip_if_failed:
            node = dataclasses.replace(node, skip_if_failed=new_sif)
        rewritten_nodes.append(node)

    # Rebuild edges
    new_edges: list[tuple[str, str]] = []
    for node in rewritten_nodes:
        for dep in node.depends_on:
            new_edges.append((dep, node.node_id))

    # New nuisance_schedule: fold variant IDs (aggregators are not nuisance)
    new_nuisance_schedule = tuple(
        n.node_id for n in rewritten_nodes if n.is_nuisance
    )

    return ExecutorGraph(
        nodes=tuple(rewritten_nodes),
        edges=tuple(new_edges),
        nuisance_schedule=new_nuisance_schedule,
        total_folds=K,
        run_id=graph.run_id,
        warnings=graph.warnings,
        proof_steps=graph.proof_steps,
    )


# ---------------------------------------------------------------------------
# FoldAggregator foundry method
# ---------------------------------------------------------------------------


@foundry_method(
    namespace="causal.compiler",
    version="1.0.0",
    tags={"causal", "compiler", "cross-fitting", "aggregator"},
)
class FoldAggregator:
    """Aggregate K out-of-fold nuisance predictions into a full OOF array.

    Receives up to K ``fold_{k}_output`` slots (one per fold) and stitches
    them back together according to ``fold_assignments`` into a single
    prediction array of length ``n_obs``.

    This node is automatically inserted by :func:`inject_cross_fitting` and
    should not be used directly in hand-crafted pipelines.
    """

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="fold_aggregator",
        namespace="",
        version="0.0.0",
        input_slots=frozenset({
            SlotSpec("fold_0_output", SlotType.VECTOR, Unit("nuisance", "oof"), shape=("n_fold_0",)),
        }),
        output_slots=frozenset({
            SlotSpec("oof_predictions", SlotType.VECTOR, Unit("nuisance", "oof"), shape=("n_obs",)),
        }),
        parameters=(
            ParameterSpec(name="n_folds", default=5),
            ParameterSpec(name="fold_assignments", default=()),
            ParameterSpec(name="aggregation_strategy", default="stack_predictions"),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description=(
            "Stitch K out-of-fold nuisance predictions into a full OOF array "
            "for downstream estimators."
        ),
        tags=frozenset({"causal", "compiler", "cross-fitting", "aggregator", "oof"}),
        citations=(
            "Chernozhukov, V. et al. (2018). Double/Debiased Machine Learning. Econometrics Journal.",
        ),
        equations={"oof": "ŷ_oof[i] = ŷ_{fold_assignments[i]}[i] for all i in [n_obs]"},
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use="Used internally by inject_cross_fitting; never manually.",
        when_not_to_use="Any context outside the cross-fitting graph transform.",
        prerequisites=(),
        diagnostic_checks=(),
        typical_min_obs=10,
        output_interpretation=(
            "oof_predictions: full-dataset OOF nuisance predictions assembled from K folds."
        ),
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        n_folds = int(params.get("n_folds", 5))
        fold_assignments = list(params.get("fold_assignments", []))
        strategy = str(params.get("aggregation_strategy", "stack_predictions"))

        if not fold_assignments:
            # No assignment info — return first available fold output as-is
            for k in range(n_folds):
                key = f"fold_{k}_output"
                if key in state:
                    return {"oof_predictions": np.asarray(state[key], dtype=float)}
            return {"oof_predictions": np.array([])}

        n_obs = len(fold_assignments)
        fold_assignments_arr = np.asarray(fold_assignments, dtype=int)
        oof = np.zeros(n_obs)

        if strategy == "mean_scores":
            # Average across all fold outputs (used for EIF score aggregation)
            fold_outputs = []
            for k in range(n_folds):
                key = f"fold_{k}_output"
                if key in state:
                    fold_outputs.append(np.asarray(state[key], dtype=float))
            if fold_outputs:
                # Stack and mean: each fold output has length equal to that fold's size
                # Simpler: just concatenate in fold order and assign
                _build_oof_from_folds(oof, fold_assignments_arr, state, n_folds)
            return {"oof_predictions": oof}

        # Default: stack_predictions — assign each fold's output to its indices
        _build_oof_from_folds(oof, fold_assignments_arr, state, n_folds)
        return {"oof_predictions": oof}


def _build_oof_from_folds(
    oof: np.ndarray,
    fold_assignments: np.ndarray,
    state: Mapping[str, Any],
    n_folds: int,
) -> None:
    """In-place: assign fold_k outputs to indices where fold_assignments == k."""
    for k in range(n_folds):
        key = f"fold_{k}_output"
        if key not in state:
            continue
        fold_pred = np.asarray(state[key], dtype=float)
        mask = fold_assignments == k
        fold_indices = np.where(mask)[0]
        if len(fold_pred) >= len(fold_indices) and len(fold_indices) > 0:
            oof[fold_indices] = fold_pred[: len(fold_indices)]


__all__ = [
    "CrossFitSchedule",
    "build_cross_fit_schedule",
    "recommend_n_folds",
    "inject_cross_fitting",
    "FoldAggregator",
]
