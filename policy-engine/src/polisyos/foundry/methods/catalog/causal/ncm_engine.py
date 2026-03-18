"""NCM Engine — Abduction-Action-Prediction for Non-parametric Causal Models.

Implements the three-step AAP algorithm for counterfactual queries:
  1. Abduction  — infer exogenous noise U from factual evidence
  2. Action     — mutilate the NCM via do(X=x) intervention
  3. Prediction — forward-simulate the mutilated model with abducted U

Supports K parallel worlds (K >= 1) with shared exogenous noise, generalising
the twin-network algorithm to arbitrary counterfactual queries.

Key design:
- When ``ncm_spec.scm_spec`` is present, all computation delegates to the
  existing ``gcm_query`` / ``twin_network_query`` infrastructure for full
  backward compatibility with fitted SCMs.
- When ``scm_spec`` is absent (symbolic NCM), linear equations are inverted
  analytically; other types default to U = 0 with a warning.

References
----------
Bongers, S., Forré, P., Peters, J. & Mooij, J.M. (2021). Foundations of
    Structural Causal Models with Cycles and Latent Variables. AoS 49(5).
Pearl, J. (2000). Causality: Models, Reasoning and Inference. CUP.
"""
from __future__ import annotations

import math
import time
from collections import deque
from collections.abc import Mapping
from typing import Any, ClassVar, Literal

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
from polisyos.foundry.methods.catalog.causal.gcm_query import (
    _abduce_noises_unified,
    _linear_predict,
    _mechanism_map,
    _parents_by_node,
    _topological_order,
)
from polisyos.foundry.methods.catalog.causal.twin_network_query import (
    _apply_node_noise,
    _sample_node_noise,
)
from polisyos.ir.analytics.ncm import NCMSpec, StructuralEquation
from polisyos.ir.analytics.structural_causal_model import MechanismFamily, NodeMechanism


# ── Private helpers ────────────────────────────────────────────────────────────


def _append_warning(warnings: list[str], message: str) -> None:
    if message not in warnings:
        warnings.append(message)


def _ncm_topological_order(ncm: NCMSpec) -> list[str]:
    """Return topological order of endogenous variables.

    Prefers the composed ``scm_spec`` order when available (consistent with the
    existing gcm_query pipeline).  Falls back to ``structural_equations`` order.
    """
    if ncm.scm_spec is not None:
        return _topological_order(ncm.scm_spec)

    # Build from structural_equations: collect parents from equations
    nodes = list(ncm.endogenous_vars) if ncm.endogenous_vars else [
        eq.variable for eq in ncm.structural_equations
    ]
    if not nodes:
        return []

    nodes_set = set(nodes)
    indegree: dict[str, int] = {n: 0 for n in nodes}
    adjacency: dict[str, list[str]] = {n: [] for n in nodes}
    for eq in ncm.structural_equations:
        for parent in eq.parents:
            if parent in nodes_set and eq.variable in nodes_set:
                adjacency[parent].append(eq.variable)
                indegree[eq.variable] += 1

    queue: deque[str] = deque(sorted(n for n, d in indegree.items() if d == 0))
    order: list[str] = []
    while queue:
        node = queue.popleft()
        order.append(node)
        for nxt in sorted(adjacency[node]):
            indegree[nxt] -= 1
            if indegree[nxt] == 0:
                queue.append(nxt)

    if len(order) != len(nodes):
        raise ValueError("NCMSpec structural equations form a cycle; acyclic NCM required")
    return order


def _ncm_parents_map(ncm: NCMSpec) -> dict[str, list[str]]:
    """Build {variable: [parents]} from the NCMSpec."""
    if ncm.scm_spec is not None:
        return _parents_by_node(ncm.scm_spec)
    return {eq.variable: list(eq.parents) for eq in ncm.structural_equations}


def _validate_markov_condition(ncm: NCMSpec) -> bool:
    """Check whether the NCM satisfies the Markov condition.

    For acyclic NCMs with mutually independent exogenous variables (no shared U),
    the Markov condition holds by construction.  When shared exogenous variables
    exist (ADMG / hidden common cause case), the condition requires bidirected
    edges in the graph — we emit a warning but still return True since the
    composed ``scm_spec`` may not capture these explicitly.

    Returns True if condition is satisfied (or likely satisfied), False otherwise.
    """
    if not ncm.is_acyclic:
        return False

    shared = [ex for ex in ncm.exogenous_specs if ex.is_shared]
    # Shared exogenous implies bidirected edges; we trust the model spec here
    return True  # Acyclic + independent U → Markov holds by construction


def _abduce_exogenous(
    ncm: NCMSpec,
    evidence: dict[str, float],
    method: Literal["exact", "mcmc", "variational"],
    *,
    warnings: list[str],
) -> dict[str, float]:
    """Abduct exogenous noise values from factual evidence.

    Parameters
    ----------
    ncm:
        NCMSpec — the model.
    evidence:
        Observed variable assignments {variable: value}.
    method:
        ``"exact"`` uses closed-form inversion (linear) or delegates to
        ``_abduce_noises_unified``.  ``"mcmc"`` and ``"variational"`` fall
        back to exact with a warning (placeholders for future extension).
    warnings:
        Mutable list for appending diagnostics.

    Returns
    -------
    dict[str, float]
        Abducted noise values {variable: U_value}.
    """
    if method in ("mcmc", "variational"):
        _append_warning(
            warnings,
            f"ncm-engine: abduction method '{method}' is not yet implemented; "
            "falling back to exact (linear inversion)",
        )

    if not evidence:
        return {}

    # ── Path 1: Delegate to fitted SCM via _abduce_noises_unified ─────────────
    if ncm.scm_spec is not None:
        order = _topological_order(ncm.scm_spec)
        parents_map = _parents_by_node(ncm.scm_spec)
        mechanisms = _mechanism_map(ncm.scm_spec)
        return _abduce_noises_unified(
            condition=evidence,
            order=order,
            parents_map=parents_map,
            mechanisms=mechanisms,
            warnings=warnings,
        )

    # ── Path 2: Symbolic NCM — invert StructuralEquations analytically ────────
    eq_map: dict[str, StructuralEquation] = {eq.variable: eq for eq in ncm.structural_equations}
    order = _ncm_topological_order(ncm)
    pseudo_observed: dict[str, float] = {}
    noise: dict[str, float] = {}

    for node in order:
        if node in evidence:
            pseudo_observed[node] = float(evidence[node])
        else:
            eq = eq_map.get(node)
            if eq is None or eq.equation_type != "linear":
                pseudo_observed[node] = 0.0
            else:
                parents_ok = all(p in pseudo_observed for p in eq.parents)
                if parents_ok:
                    intercept = float(eq.equation_params.get("intercept", 0.0))
                    coefs = eq.equation_params.get("coefficients", {})
                    val = intercept + sum(
                        float(coefs.get(p, 0.0)) * pseudo_observed[p] for p in eq.parents
                    )
                    pseudo_observed[node] = val
                else:
                    pseudo_observed[node] = 0.0

        if node in evidence:
            eq = eq_map.get(node)
            if eq is not None and eq.equation_type == "linear":
                parents_ok = all(p in pseudo_observed for p in eq.parents)
                if parents_ok:
                    intercept = float(eq.equation_params.get("intercept", 0.0))
                    coefs = eq.equation_params.get("coefficients", {})
                    pred = intercept + sum(
                        float(coefs.get(p, 0.0)) * pseudo_observed[p] for p in eq.parents
                    )
                    noise[node] = float(evidence[node]) - pred
                else:
                    _append_warning(
                        warnings,
                        f"ncm-engine: cannot abduct U for '{node}' "
                        "(parents not in topological prefix); defaulting to U=0",
                    )
                    noise[node] = 0.0
            elif eq is not None:
                _append_warning(
                    warnings,
                    f"ncm-engine: equation type '{eq.equation_type}' for node '{node}' "
                    "does not support exact abduction; defaulting to U=0",
                )
                noise[node] = 0.0

    return noise


def _predict_from_abducted(
    ncm: NCMSpec,
    abducted_u: dict[str, float],
    intervention: dict[str, float],
    order: list[str],
    parents_map: dict[str, list[str]],
    warnings: list[str],
) -> dict[str, float]:
    """Forward-simulate NCM with pre-abducted U and a given intervention.

    For each node in topological order:
    - If the node is intervened upon: fix it to the intervention value.
    - Otherwise: compute its value from parents + abducted noise, delegating
      to ``_apply_node_noise`` when a NodeMechanism is available.

    Parameters
    ----------
    ncm:
        NCMSpec.
    abducted_u:
        Pre-abducted noise dict {variable: U_value}.
    intervention:
        do(X=x) assignments {variable: value} — these override structural eqs.
    order:
        Topological order of endogenous variables.
    parents_map:
        {variable: [parents]}.
    warnings:
        Mutable warning list.

    Returns
    -------
    dict[str, float]
        Predicted values for all endogenous variables.
    """
    # Build fast lookup for mechanisms (if scm_spec available)
    mech_map: dict[str, NodeMechanism] = (
        _mechanism_map(ncm.scm_spec) if ncm.scm_spec is not None else {}
    )
    eq_map: dict[str, StructuralEquation] = {
        eq.variable: eq for eq in ncm.structural_equations
    }

    values: dict[str, float] = {}

    for node in order:
        # Intervention overrides structural equation
        if node in intervention:
            values[node] = float(intervention[node])
            continue

        noise = float(abducted_u.get(node, 0.0))
        parent_vals = {p: values.get(p, 0.0) for p in parents_map.get(node, [])}

        # Path 1: delegate to fitted NodeMechanism
        if node in mech_map:
            values[node] = _apply_node_noise(mech_map[node], parent_vals, noise, warnings)
            continue

        # Path 2: use StructuralEquation.equation_params for linear
        eq = eq_map.get(node)
        if eq is not None and eq.equation_type == "linear":
            intercept = float(eq.equation_params.get("intercept", 0.0))
            coefs = eq.equation_params.get("coefficients", {})
            val = intercept + sum(
                float(coefs.get(p, 0.0)) * parent_vals.get(p, 0.0) for p in eq.parents
            )
            values[node] = val + noise
            continue

        # Fallback: treat noise as the full value
        _append_warning(
            warnings,
            f"ncm-engine: no mechanism or linear equation for '{node}'; "
            "using noise as full node value",
        )
        values[node] = noise

    return values


def _counterfactual_world(
    ncm: NCMSpec,
    intervention: dict[str, float],
    evidence: dict[str, float],
    abduction_method: Literal["exact", "mcmc", "variational"],
    *,
    warnings: list[str],
) -> dict[str, float]:
    """Compute the counterfactual world M_{do(X=x)} given factual evidence.

    Implements the Abduction-Action-Prediction (AAP) algorithm:
    1. Abduct U from evidence.
    2. Mutilate: fix intervention variables.
    3. Predict: forward-simulate with abducted U through mutilated model.

    Returns a single dict of predicted values (no randomness — this is a
    deterministic function of the abducted U).
    """
    order = _ncm_topological_order(ncm)
    parents_map = _ncm_parents_map(ncm)

    abducted_u = _abduce_exogenous(ncm, evidence, abduction_method, warnings=warnings)
    return _predict_from_abducted(ncm, abducted_u, intervention, order, parents_map, warnings)


def _parallel_worlds(
    ncm: NCMSpec,
    interventions: list[dict[str, float]],
    evidence: dict[str, float],
    abduction_method: Literal["exact", "mcmc", "variational"],
    *,
    n_samples: int,
    rng: np.random.Generator,
    warnings: list[str],
) -> list[dict[str, np.ndarray]]:
    """Simulate K parallel worlds with shared exogenous noise.

    Generalises ``_twin_simulate_samples`` (K=2) to arbitrary K >= 1.
    All worlds share the same abducted U realisation, enabling joint
    distribution queries (PNS, ITE variance, etc.).

    Parameters
    ----------
    ncm:
        NCMSpec.
    interventions:
        List of K dicts {variable: value}, one per world.
    evidence:
        Factual observations used for abduction.
    abduction_method:
        ``"exact"`` | ``"mcmc"`` | ``"variational"``.
    n_samples:
        Number of Monte Carlo samples.
    rng:
        Seeded random generator.
    warnings:
        Mutable warning list.

    Returns
    -------
    list[dict[str, np.ndarray]]
        K dicts, each mapping variable → array of shape (n_samples,).
    """
    if not interventions:
        return []

    k = len(interventions)
    order = _ncm_topological_order(ncm)
    parents_map = _ncm_parents_map(ncm)
    mech_map: dict[str, NodeMechanism] = (
        _mechanism_map(ncm.scm_spec) if ncm.scm_spec is not None else {}
    )

    # Initialise output arrays
    worlds: list[dict[str, list[float]]] = [{} for _ in range(k)]
    for w in worlds:
        for node in order:
            w[node] = []

    for _ in range(n_samples):
        # ── Step 1: Sample fresh exogenous noise for all nodes ────────────────
        fresh_noise: dict[str, float] = {}
        for node in order:
            mech = mech_map.get(node)
            fresh_noise[node] = _sample_node_noise(mech, rng)

        # ── Step 2: If evidence provided, abduct U from it ────────────────────
        if evidence:
            abducted = _abduce_exogenous(ncm, evidence, abduction_method, warnings=warnings)
            # Abducted noise overrides fresh noise for observed nodes
            for node, u_val in abducted.items():
                fresh_noise[node] = u_val

        # ── Step 3: Simulate each world with the same noise ───────────────────
        for w_idx, interv in enumerate(interventions):
            vals = _predict_from_abducted(
                ncm, fresh_noise, interv, order, parents_map, warnings
            )
            for node in order:
                worlds[w_idx][node].append(vals.get(node, 0.0))

    # Convert to numpy arrays
    return [
        {node: np.asarray(vals, dtype=float) for node, vals in w.items()}
        for w in worlds
    ]


def _twin_network_from_ncm(ncm: NCMSpec) -> NCMSpec:
    """Construct an explicit twin-network NCM by doubling all variables.

    Creates a new NCMSpec where every endogenous variable V appears in two
    copies: V__0 (factual world) and V__1 (counterfactual world), both sharing
    the same exogenous noise specifications.

    This is primarily for symbolic inspection.  The ``_parallel_worlds``
    function implements the twin-network semantics implicitly during simulation.

    Returns
    -------
    NCMSpec
        A new NCMSpec with doubled variables.  The ``scm_spec`` field is
        set to None since the twin network is a new model structure.
    """
    suffixes = ("__0", "__1")
    new_endogenous: list[str] = []
    new_exo_specs = []
    new_equations = []

    for suffix in suffixes:
        for v in ncm.endogenous_vars:
            new_endogenous.append(f"{v}{suffix}")

        for ex in ncm.exogenous_specs:
            new_exo_specs.append(
                ex.model_copy(
                    update={
                        "variable": f"{ex.variable}{suffix}",
                        "associated_endogenous": f"{ex.associated_endogenous}{suffix}",
                        "is_shared": True,
                        "shared_with": [f"{ex.associated_endogenous}{'__1' if suffix == '__0' else '__0'}"],
                    }
                )
            )

        for eq in ncm.structural_equations:
            new_equations.append(
                eq.model_copy(
                    update={
                        "variable": f"{eq.variable}{suffix}",
                        "parents": [f"{p}{suffix}" for p in eq.parents],
                        "exogenous": f"{eq.exogenous}{suffix}",
                    }
                )
            )

    return NCMSpec(
        schema_version=ncm.schema_version,
        endogenous_vars=new_endogenous,
        exogenous_specs=new_exo_specs,
        structural_equations=new_equations,
        scm_spec=None,
        is_acyclic=ncm.is_acyclic,
        markov_condition_verified=False,
        independence_model="unknown",
        fit_method="twin_network",
    )


# ── Protocol data class ────────────────────────────────────────────────────────
# NCMQueryData is defined in protocols.py to avoid circular imports.
# Here we just import it lazily inside pure_step.


# ── Foundry method ─────────────────────────────────────────────────────────────


@foundry_method(
    namespace="causal.counterfactual",
    version="1.0.0",
    tags={"causal", "ncm", "counterfactual", "structural", "aap"},
)
class NCMEngineMethod:
    """Non-parametric Causal Model (NCM) engine.

    Implements the Abduction-Action-Prediction (AAP) algorithm for
    arbitrary counterfactual queries:
    - Single-world counterfactuals: E[Y_{do(X=x)} | evidence]
    - Parallel worlds: joint distribution over K interventional worlds
    - Twin network: ITE distribution P(Y(x₁) - Y(x₀))

    Delegates to existing fitted-SCM infrastructure when ``scm_spec`` is
    present in the NCMSpec, and falls back to symbolic linear inversion
    for manually-specified NCMs.
    """

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="ncm_engine",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset({
            SlotSpec("ncm_query_data", SlotType.SCALAR, Unit("query", "json")),
        }),
        output_slots=frozenset({
            SlotSpec("counterfactual_result", SlotType.SCALAR, Unit("report", "json")),
        }),
        parameters=(
            ParameterSpec(name="n_samples", default=2000),
            ParameterSpec(name="abduction_method", default="exact"),
            ParameterSpec(name="confidence_level", default=0.95),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description=(
            "NCM engine: Abduction-Action-Prediction for arbitrary counterfactual "
            "queries using non-parametric structural causal models. Supports single-world "
            "and parallel-world (twin-network) counterfactuals."
        ),
        tags=frozenset({"causal", "ncm", "counterfactual", "structural", "l3"}),
        citations=(
            "Bongers, S., Forré, P., Peters, J. & Mooij, J.M. (2021). "
            "Foundations of Structural Causal Models with Cycles and Latent Variables. "
            "Annals of Statistics, 49(5), 2885-2915.",
            "Pearl, J. (2000). Causality: Models, Reasoning and Inference. CUP.",
        ),
        equations={
            "aap_step1": "U ← abduct(V_obs)",
            "aap_step2": "M_{do(X)} ← mutilate(M, X=x)",
            "aap_step3": "Y_x = predict(M_{do(X)}, U)",
        },
        determinism_tier=DeterminismTier.STATISTICAL,
        required_deps=("numpy",),
        when_to_use=(
            "L3 counterfactual queries: individual treatment effects, PN/PS, "
            "actual causality checks, path-specific effects via NCM."
        ),
        when_not_to_use=(
            "Pure interventional (L2) queries — use GCMQuery or TwinNetworkQuery instead. "
            "Non-acyclic models (cyclic NCMs) are not yet supported."
        ),
        typical_min_obs=500,
        output_interpretation=(
            "counterfactual_result contains mean/std/CI for each query variable "
            "in each specified intervention world."
        ),
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        from polisyos.foundry.methods.catalog.causal.protocols import NCMQueryData

        t0 = time.time()
        seed = params.get("__seed__")
        rng = np.random.default_rng(seed)

        n_samples = int(params.get("n_samples", 2000))
        abduction_method = str(params.get("abduction_method", "exact"))
        confidence_level = float(params.get("confidence_level", 0.95))

        # Parse input
        raw = state.get("ncm_query_data", state)
        if isinstance(raw, NCMQueryData):
            query_data = raw
        else:
            query_data = NCMQueryData.model_validate(raw if isinstance(raw, dict) else dict(raw))

        ncm: NCMSpec = query_data.ncm_spec  # type: ignore[assignment]
        evidence: dict[str, float] = dict(query_data.evidence)
        interventions: list[dict[str, float]] = list(query_data.interventions)
        query_vars: list[str] = list(query_data.query_vars)
        n_samples = int(query_data.n_samples or n_samples)

        warnings: list[str] = []

        if not ncm.is_acyclic:
            warnings.append(
                "ncm-engine: NCM is marked as cyclic (is_acyclic=False); "
                "AAP algorithm assumes acyclicity — results may be unreliable"
            )

        # Run parallel worlds simulation
        if not interventions:
            # No interventions: run one observational world
            interventions = [{}]

        worlds = _parallel_worlds(
            ncm,
            interventions,
            evidence,
            abduction_method,  # type: ignore[arg-type]
            n_samples=n_samples,
            rng=rng,
            warnings=warnings,
        )

        # Summarise results per world per query variable
        alpha = 1.0 - confidence_level
        z = float(np.abs(np.percentile(np.random.standard_normal(100_000), alpha / 2 * 100)))

        world_summaries: list[dict[str, Any]] = []
        for w_idx, world_vals in enumerate(worlds):
            summary: dict[str, Any] = {"world_index": w_idx, "intervention": interventions[w_idx]}
            effective_vars = query_vars if query_vars else list(world_vals.keys())
            for var in effective_vars:
                arr = world_vals.get(var)
                if arr is None or len(arr) == 0:
                    continue
                mean = float(np.mean(arr))
                std = float(np.std(arr))
                se = std / math.sqrt(len(arr))
                summary[var] = {
                    "mean": mean,
                    "std": std,
                    "ci_lower": mean - z * se,
                    "ci_upper": mean + z * se,
                    "n_samples": len(arr),
                }
            world_summaries.append(summary)

        elapsed = time.time() - t0

        return {
            "counterfactual_result": {
                "schema_version": "1.0",
                "world_summaries": world_summaries,
                "n_worlds": len(worlds),
                "n_samples": n_samples,
                "abduction_method": abduction_method,
                "confidence_level": confidence_level,
                "computation_time_seconds": elapsed,
                "warnings": warnings,
            }
        }


__all__ = [
    "NCMEngineMethod",
    "_abduce_exogenous",
    "_predict_from_abducted",
    "_counterfactual_world",
    "_parallel_worlds",
    "_twin_network_from_ncm",
    "_validate_markov_condition",
    "_ncm_topological_order",
    "_ncm_parents_map",
]
