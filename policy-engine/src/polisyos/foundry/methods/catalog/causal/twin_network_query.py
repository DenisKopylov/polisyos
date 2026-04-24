"""TwinNetworkQuery — Pearl's Abduction-Action-Prediction for twin networks.

A twin network duplicates the SCM into two parallel worlds that share the
same exogenous noise realisations (U).  This enables computing the *joint*
distribution P(Y(x₀), Y(x₁)) and per-unit Individual Treatment Effects (ITE).

The three-step algorithm:
  1. Abduction  — infer U from factual observations {X=x₀, Y=y₀, …}
  2. Action     — construct both worlds: world₀ with do(X=x₀), world₁ with do(X=x₁)
  3. Prediction — forward-simulate both worlds with the *same* U to get Y(x₀) and Y(x₁)

Key difference from ``GCMQuery``: GCMQuery runs one world at a time so it cannot
compute Corr(Y(x₀), Y(x₁)) or the ITE variance.  This method runs both worlds
inside the *same* Monte Carlo iteration, ensuring shared noise.
"""

from __future__ import annotations

import math
import time
from collections.abc import Mapping
from typing import Any, ClassVar

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
    _apply_intervention,
    _linear_predict,
    _mechanism_map,
    _parents_by_node,
    _percentile_ci,
    _topological_order,
)
from polisyos.foundry.methods.catalog.causal.protocols import TwinNetworkQueryData
from polisyos.ir.analytics.causal_queries import InterventionSpec, InterventionType
from polisyos.ir.analytics.structural_causal_model import (
    MechanismFamily,
    NodeMechanism,
    StructuralCausalModelSpec,
)
from polisyos.ir.analytics.twin_network import TwinNetworkResult
from polisyos.ir.analytics.uncertainty import (
    DistributionFamily,
    IntervalSemantics,
    PropagationMethod,
    UncertaintyEnvelope,
    UncertaintySource,
)

# ── Private helpers ────────────────────────────────────────────────────────────


def _sample_node_noise(
    mechanism: NodeMechanism | None,
    rng: np.random.Generator,
) -> float:
    """Pre-sample exogenous noise U for a single node.

    Returns the *residual* u such that node_value = f(parents) + u.
    This noise is then reused in both twin worlds (shared U realisation).
    """
    if mechanism is None:
        return float(rng.normal())

    if mechanism.family is MechanismFamily.LINEAR:
        params = mechanism.family_params
        try:
            std = float(params.get("noise_std", 0.0))
        except (TypeError, ValueError, ArithmeticError):
            std = 0.0
        if not math.isfinite(std) or std < 0.0:
            std = 0.0
        return float(rng.normal(scale=std)) if std > 0.0 else 0.0

    if mechanism.family is MechanismFamily.EMPIRICAL:
        std = float(mechanism.family_params.get("std", 1.0))
        if not math.isfinite(std) or std < 0.0:
            std = 1.0
        return float(rng.normal(scale=std)) if std > 0.0 else 0.0

    if mechanism.family is MechanismFamily.PARAMETRIC_PRIOR:
        std = float(mechanism.family_params.get("noise_std", 0.2))
        std = std if math.isfinite(std) and std > 0.0 else 0.2
        return float(rng.normal(scale=std))

    # ADDITIVE_NOISE, POST_NONLINEAR, CLASSIFIER: best-effort linear noise std
    try:
        std = float(mechanism.family_params.get("noise_std", 0.0))
    except (TypeError, ValueError, ArithmeticError):
        std = 0.0
    if not math.isfinite(std) or std < 0.0:
        std = 0.0
    return float(rng.normal(scale=std)) if std > 0.0 else 0.0


def _apply_node_noise(
    mechanism: NodeMechanism | None,
    parent_values: Mapping[str, float],
    noise: float,
    warnings: list[str],
) -> float:
    """Compute node value from parent values and a pre-sampled exogenous noise.

    This is the deterministic part of the forward simulation:
        node_value = f(parents) + noise

    Used in both worlds of the twin network with the *same* noise value.
    """
    if mechanism is None:
        # Treat noise as the full node value (standard normal fallback)
        return float(noise)

    if mechanism.family is MechanismFamily.LINEAR:
        mean = _linear_predict(mechanism, parent_values)
        return float(mean + noise)

    if mechanism.family is MechanismFamily.EMPIRICAL:
        mean = float(mechanism.family_params.get("mean", 0.0))
        if not math.isfinite(mean):
            mean = 0.0
        return float(mean + noise)

    if mechanism.family is MechanismFamily.PARAMETRIC_PRIOR:
        prior = mechanism.family_params.get("prior")
        if isinstance(prior, Mapping):
            intercept = float(prior.get("__intercept__", {}).get("mean", 0.0))
            val = intercept
            for parent in mechanism.parents:
                stats = prior.get(parent, {})
                if not isinstance(stats, Mapping):
                    stats = {}
                val += float(stats.get("mean", 0.0)) * parent_values[parent]
            return float(val + noise)
        mean = float(mechanism.family_params.get("mean", 0.0))
        if not math.isfinite(mean):
            mean = 0.0
        return float(mean + noise)

    # ADDITIVE_NOISE, POST_NONLINEAR, CLASSIFIER: linear fallback with warning
    if not any(
        w.startswith(f"twin-network: mechanism family '{mechanism.family.value}'") for w in warnings
    ):
        warnings.append(
            f"twin-network: mechanism family '{mechanism.family.value}' for node "
            f"'{mechanism.variable}' not fully supported; using linear fallback"
        )
    if mechanism.parents:
        mean = _linear_predict(mechanism, parent_values)
        return float(mean + noise)
    mean = float(mechanism.family_params.get("mean", 0.0))
    if not math.isfinite(mean):
        mean = 0.0
    return float(mean + noise)


def _twin_simulate_samples(
    *,
    scm_spec: StructuralCausalModelSpec,
    treatment_variable: str,
    outcome_variable: str,
    factual_intervention: InterventionSpec,
    counterfactual_intervention: InterventionSpec,
    abduced_noises: dict[str, float],
    n_samples: int,
    rng: np.random.Generator,
    warnings: list[str],
) -> tuple[np.ndarray, np.ndarray]:
    """Run both factual and counterfactual worlds with shared exogenous noise.

    For each Monte Carlo sample:
      1. Pre-sample noise U_node for every node
         (abducted nodes use inferred U from factual observation)
      2. Forward-simulate factual world:  do(X=x₀) + shared U  →  Y(x₀)
      3. Forward-simulate counter world:  do(X=x₁) + *same* U  →  Y(x₁)

    Returns two correlated arrays (po_factual, po_counter) of length n_samples.
    Correlation between them is what gives non-trivial ITE variance and po_correlation.
    """
    order = _topological_order(scm_spec)
    parents_map = _parents_by_node(scm_spec)
    mechanisms = _mechanism_map(scm_spec)

    po_factual = np.zeros(n_samples, dtype=float)
    po_counter = np.zeros(n_samples, dtype=float)

    for i in range(n_samples):
        # ── Step 1: pre-sample shared exogenous noise ──────────────────────────
        shared_noise: dict[str, float] = {}
        for node in order:
            if node in abduced_noises:
                shared_noise[node] = abduced_noises[node]
            else:
                shared_noise[node] = _sample_node_noise(mechanisms.get(node), rng)

        # ── Step 2: forward-simulate FACTUAL world (do(X=x₀)) ─────────────────
        factual: dict[str, float] = {}
        for node in order:
            parent_vals = {p: factual[p] for p in parents_map.get(node, [])}
            if node == treatment_variable:
                factual[node] = _apply_intervention(
                    current_value=float(factual_intervention.value or 0.0),
                    intervention_spec=factual_intervention,
                    fallback_treatment_value=factual_intervention.value,
                    rng=rng,
                    warnings=warnings,
                )
            else:
                factual[node] = _apply_node_noise(
                    mechanisms.get(node),
                    parent_vals,
                    shared_noise[node],
                    warnings,
                )

        # ── Step 3: forward-simulate COUNTERFACTUAL world (do(X=x₁)) ──────────
        counter: dict[str, float] = {}
        for node in order:
            parent_vals = {p: counter[p] for p in parents_map.get(node, [])}
            if node == treatment_variable:
                counter[node] = _apply_intervention(
                    current_value=float(counterfactual_intervention.value or 0.0),
                    intervention_spec=counterfactual_intervention,
                    fallback_treatment_value=counterfactual_intervention.value,
                    rng=rng,
                    warnings=warnings,
                )
            else:
                counter[node] = _apply_node_noise(
                    mechanisms.get(node),
                    parent_vals,
                    shared_noise[node],
                    warnings,
                )

        po_factual[i] = factual[outcome_variable]
        po_counter[i] = counter[outcome_variable]

    return po_factual, po_counter


# ── Foundry method ─────────────────────────────────────────────────────────────


@foundry_method(
    namespace="causal.structural",
    version="1.0.0",
    tags={"causal", "structural", "twin_network", "counterfactual"},
)
class TwinNetworkQuery:
    """Twin-network counterfactual query using Pearl's Abduction-Action-Prediction.

    Computes the joint distribution P(Y(x₀), Y(x₁)) by:
      1. **Abduction** — inferring latent noise U from factual observations
      2. **Action**    — constructing two mutilated SCMs: do(X=x₀) and do(X=x₁)
      3. **Prediction** — forward-simulating both worlds with the *same* U

    Unlike ``GCMQuery`` which runs one world per call, this method runs both worlds
    inside the same Monte Carlo iteration so the resulting potential-outcome arrays
    are properly correlated.  This enables:

    - **ITE distribution**: Y(x₁) − Y(x₀) per unit
    - **po_correlation**: Corr(Y(x₀), Y(x₁)) — key diagnostic for ITE heterogeneity
    - **E[Y(x)]** for both arms with calibrated uncertainty

    Input: ``TwinNetworkQueryData`` (from ``protocols.py``)
    Output: ``TwinNetworkResult`` (from ``ir/analytics/twin_network.py``)
    """

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="twin_network_query",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    name="twin_network_query_data",
                    slot_type=SlotType.SCALAR,
                    unit=Unit("query", "json"),
                )
            }
        ),
        output_slots=frozenset(
            {
                SlotSpec(
                    name="twin_network_result",
                    slot_type=SlotType.SCALAR,
                    unit=Unit("report", "json"),
                ),
            }
        ),
        parameters=(
            ParameterSpec(name="confidence_level", default=0.95),
            ParameterSpec(name="store_distribution", default=True),
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
            "Compute joint counterfactual distribution P(Y(x₀), Y(x₁)) via Pearl's "
            "twin-network: abduction of latent noise from factual observation, then "
            "dual forward simulation with shared noise to quantify ITE variance."
        ),
        tags=frozenset({"causal", "structural", "twin_network", "counterfactual"}),
        assumptions={
            "acyclic_graph": "SCM graph must be acyclic for topological sampling.",
            "additive_noise": (
                "Abduction is exact for LINEAR and ADDITIVE_NOISE mechanisms.  "
                "EMPIRICAL/CLASSIFIER nodes use noise=0 approximation during abduction."
            ),
            "atomic_interventions": (
                "TwinNetworkQueryData specifies treatment values as plain floats; "
                "both interventions are ATOMIC do(X=x)."
            ),
        },
        citations=(
            "Balke, A. & Pearl, J. (1994). Counterfactual probabilities: Computational methods, bounds and applications. Proceedings of UAI.",
            "Pearl, J. (2009). Causality: Models, Reasoning, and Inference. Cambridge University Press.",
        ),
        when_to_use=(
            "After fitting an SCM with HybridSCMFit; computing individual treatment "
            "effects, ITE variance, or counterfactual outcomes for a specific unit."
        ),
        when_not_to_use=(
            "SCM has not been fitted; graph is non-acyclic; "
            "mechanisms are all EMPIRICAL/CLASSIFIER (abduction is approximate)."
        ),
        typical_min_obs=1,
        output_interpretation=(
            "twin_network_result.ite_mean = E[Y(x₁)−Y(x₀)] (unit-level ATE under abduction). "
            "twin_network_result.po_correlation: near 1 → homogeneous individual effects; "
            "near 0 → highly heterogeneous effects across units."
        ),
    )

    @staticmethod
    def pure_step(
        state: TwinNetworkQueryData,
        params: Mapping[str, Any],
    ) -> dict[str, Any]:
        payload = (
            state
            if isinstance(state, TwinNetworkQueryData)
            else TwinNetworkQueryData.model_validate(state)
        )

        scm_spec = payload.scm_spec
        n_samples = payload.n_samples
        confidence_level = float(params.get("confidence_level", 0.95))
        if not (0.0 < confidence_level < 1.0):
            raise ValueError("confidence_level must be in (0, 1)")
        store_distribution = params.get("store_distribution", True) is not False

        seed = int(params.get("__seed__", 0) or 0)
        rng_param = params.get("__rng__")
        rng: np.random.Generator = (
            rng_param if isinstance(rng_param, np.random.Generator) else np.random.default_rng(seed)
        )

        warnings: list[str] = []
        started_at = time.perf_counter()

        # ── ABDUCTION ─────────────────────────────────────────────────────────
        order = _topological_order(scm_spec)
        parents_map = _parents_by_node(scm_spec)
        mechanisms = _mechanism_map(scm_spec)

        abduced_noises: dict[str, float] = {}
        if payload.factual_condition:
            abduced_noises = _abduce_noises_unified(
                condition=payload.factual_condition,
                order=order,
                parents_map=parents_map,
                mechanisms=mechanisms,
                warnings=warnings,
            )

        # ── ACTION: build ATOMIC InterventionSpecs ────────────────────────────
        factual_intervention = InterventionSpec(
            type=InterventionType.ATOMIC,
            value=payload.factual_treatment_value,
        )
        counterfactual_intervention = InterventionSpec(
            type=InterventionType.ATOMIC,
            value=payload.counterfactual_treatment_value,
        )

        # ── PREDICTION: dual-world Monte Carlo with shared noise ───────────────
        po_factual, po_counter = _twin_simulate_samples(
            scm_spec=scm_spec,
            treatment_variable=payload.treatment_variable,
            outcome_variable=payload.outcome_variable,
            factual_intervention=factual_intervention,
            counterfactual_intervention=counterfactual_intervention,
            abduced_noises=abduced_noises,
            n_samples=n_samples,
            rng=rng,
            warnings=warnings,
        )

        # ── STATISTICS ────────────────────────────────────────────────────────
        ite_samples = po_counter - po_factual

        ite_mean = float(np.mean(ite_samples))
        ite_std = float(np.std(ite_samples))
        po_factual_mean = float(np.mean(po_factual))
        po_factual_std = float(np.std(po_factual))
        po_counter_mean = float(np.mean(po_counter))
        po_counter_std = float(np.std(po_counter))

        ite_ci = _percentile_ci(ite_samples, confidence_level)
        ci_lo, ci_hi = ite_ci
        if ite_mean < ci_lo:
            ci_lo = ite_mean
        if ite_mean > ci_hi:
            ci_hi = ite_mean
        ite_ci = (ci_lo, ci_hi)

        # po_correlation: well-defined only when both distributions have variance
        if po_factual_std > 0.0 and po_counter_std > 0.0:
            corr_matrix = np.corrcoef(po_factual, po_counter)
            po_correlation = float(np.clip(corr_matrix[0, 1], -1.0, 1.0))
        else:
            po_correlation = 1.0  # deterministic → perfect correlation

        elapsed = float(time.perf_counter() - started_at)

        result = TwinNetworkResult(
            outcome_variable=payload.outcome_variable,
            factual_intervention=factual_intervention,
            counterfactual_intervention=counterfactual_intervention,
            po_factual_mean=po_factual_mean,
            po_factual_std=po_factual_std,
            po_counter_mean=po_counter_mean,
            po_counter_std=po_counter_std,
            ite_mean=ite_mean,
            ite_std=ite_std,
            ite_ci=ite_ci,
            po_correlation=po_correlation,
            ite_distribution=ite_samples.tolist() if store_distribution else None,
            po_factual_distribution=po_factual.tolist() if store_distribution else None,
            po_counter_distribution=po_counter.tolist() if store_distribution else None,
            computation_time_seconds=elapsed,
            abduction_warnings=warnings,
            metadata={
                "n_samples": n_samples,
                "confidence_level": confidence_level,
                "n_abduced_nodes": len(abduced_noises),
                "factual_treatment_value": payload.factual_treatment_value,
                "counterfactual_treatment_value": payload.counterfactual_treatment_value,
            },
        )

        ci_lo, ci_hi = result.ite_ci
        envelope = UncertaintyEnvelope(
            point_estimate=float(result.ite_mean),
            confidence_interval=(float(ci_lo), float(ci_hi)),
            confidence_level=confidence_level,
            distribution_family=DistributionFamily.BOOTSTRAP,
            source=UncertaintySource.CAUSAL,
            propagation_method=PropagationMethod.MONTE_CARLO,
            interval_semantics=IntervalSemantics.CONFIDENCE_INTERVAL,
            sample_size=n_samples,
            is_heuristic_ci=False,
            gate_eligible=True,
            metadata={
                "query_type": "twin_network",
                "outcome_variable": payload.outcome_variable,
                "ite_std": result.ite_std,
                "po_correlation": result.po_correlation,
            },
        )

        return {
            "twin_network_result": result,
            "envelope": envelope,
            "warnings": warnings,
            "__determinism_tier__": DeterminismTier.STATISTICAL,
        }


__all__ = [
    "TwinNetworkQuery",
    "_apply_node_noise",
    "_sample_node_noise",
    "_twin_simulate_samples",
]
