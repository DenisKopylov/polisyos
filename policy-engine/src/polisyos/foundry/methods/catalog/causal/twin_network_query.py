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

from polisyos.core.observability import DeterminismTier
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
    _AbductionDiagnostic,
    _apply_intervention,
    _compatible_joint_root_indices,
    _draw_linear_gaussian_noises,
    _empirical_root_location_scale,
    _empirical_structural_residuals,
    _joint_root_sample_index,
    _linear_noise_std,
    _LinearGaussianPosterior,
    _mechanism_map,
    _mechanism_predict,
    _observed_root_samples,
    _parametric_prior_noise_std,
    _parents_by_node,
    _percentile_ci,
    _prepare_linear_gaussian_abduction,
    _prepared_scm_query_spec,
    _query_relevance_plan,
    _topological_order,
)
from polisyos.foundry.methods.catalog.causal.protocols import TwinNetworkQueryData
from polisyos.ir.analytics.causal_queries import (
    CausalResultKind,
    InterventionSpec,
    InterventionType,
)
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
    *,
    observed_root_value: float | None = None,
    warnings: list[str] | None = None,
    allow_declared_hypothesis: bool = False,
    declared_root_hypotheses: set[str] | None = None,
) -> float:
    """Pre-sample exogenous noise U for a single node.

    Returns the *residual* u such that node_value = f(parents) + u.
    This noise is then reused in both twin worlds (shared U realisation).
    """
    if mechanism is None:
        if observed_root_value is not None:
            return float(observed_root_value)
        return float(rng.normal())

    if mechanism.family in {MechanismFamily.LINEAR, MechanismFamily.ADDITIVE_NOISE}:
        residuals = _empirical_structural_residuals(mechanism)
        if residuals is not None:
            return float(rng.choice(residuals))
        std = _linear_noise_std(mechanism)
        return float(rng.normal(scale=std)) if std > 0.0 else 0.0

    if mechanism.family is MechanismFamily.EMPIRICAL:
        if observed_root_value is not None:
            # An aligned empirical root row is already the whole root value.
            return float(observed_root_value)
        _mean, std = _empirical_root_location_scale(mechanism)
        if not allow_declared_hypothesis:
            raise ValueError(
                f"empirical root '{mechanism.variable}' has no observed rows; explicitly enable "
                "allow_declared_root_hypothesis to use a limited location-scale hypothesis"
            )
        if declared_root_hypotheses is not None:
            declared_root_hypotheses.add(mechanism.variable)
        if warnings is not None:
            message = (
                f"empirical root '{mechanism.variable}' has no observed rows; "
                "its location-scale sampler is a declared hypothesis, not an established law"
            )
            if message not in warnings:
                warnings.append(message)
        return float(rng.normal(scale=std)) if std > 0.0 else 0.0

    if mechanism.family is MechanismFamily.PARAMETRIC_PRIOR:
        std = _parametric_prior_noise_std(mechanism)
        return float(rng.normal(scale=std)) if std > 0.0 else 0.0

    # ADDITIVE_NOISE, POST_NONLINEAR, CLASSIFIER: use the declared noise scale.
    std = _linear_noise_std(mechanism)
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
        mean = _mechanism_predict(mechanism, parent_values)
        return float(mean + noise)

    if mechanism.family is MechanismFamily.EMPIRICAL:
        if not mechanism.parents and "observed_samples" in mechanism.family_params:
            return float(noise)
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

    if mechanism.family is MechanismFamily.ADDITIVE_NOISE:
        mean = _mechanism_predict(mechanism, parent_values)
        return float(mean + noise)

    # POST_NONLINEAR, CLASSIFIER: linear fallback with warning
    if not any(
        w.startswith(f"twin-network: mechanism family '{mechanism.family.value}'") for w in warnings
    ):
        warnings.append(
            f"twin-network: mechanism family '{mechanism.family.value}' for node "
            f"'{mechanism.variable}' not fully supported; using linear fallback"
        )
    if mechanism.parents:
        mean = _mechanism_predict(mechanism, parent_values)
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
    abduction_posterior: _LinearGaussianPosterior | None = None,
    n_samples: int,
    rng: np.random.Generator,
    warnings: list[str],
    allow_declared_hypothesis: bool = False,
    declared_root_hypotheses: set[str] | None = None,
    active_nodes: set[str] | None = None,
    factual_condition: Mapping[str, float] | None = None,
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
    full_order = _topological_order(scm_spec)
    order = [node for node in full_order if active_nodes is None or node in active_nodes]
    parents_map = _parents_by_node(scm_spec)
    mechanisms = _mechanism_map(scm_spec)
    observed_root_samples = {
        node: values for node, values in _observed_root_samples(mechanisms).items() if node in order
    }
    compatible_root_indices = _compatible_joint_root_indices(
        observed_root_samples, factual_condition or {}
    )

    po_factual = np.zeros(n_samples, dtype=float)
    po_counter = np.zeros(n_samples, dtype=float)

    for i in range(n_samples):
        # ── Step 1: pre-sample shared exogenous noise ──────────────────────────
        shared_noise: dict[str, float] = {}
        sampled_abduced_noises = (
            _draw_linear_gaussian_noises(abduction_posterior, rng)
            if abduction_posterior is not None
            else abduced_noises
        )
        root_sample_index = _joint_root_sample_index(
            observed_root_samples, rng, compatible_indices=compatible_root_indices
        )
        for node in order:
            if node == treatment_variable:
                # Both public twin arms are atomic and replace this mechanism.
                # A factual posterior has already used its natural law where
                # required; neither forward world samples it again.
                shared_noise[node] = 0.0
                continue
            mechanism = mechanisms.get(node)
            if (
                node in (factual_condition or {})
                and mechanism is not None
                and mechanism.family is MechanismFamily.EMPIRICAL
                and not mechanism.parents
                and node not in observed_root_samples
            ):
                # A directly observed root is known even when its population
                # law is not. Its support limitation is carried by abduction.
                mean, _std = _empirical_root_location_scale(mechanism)
                shared_noise[node] = float(factual_condition[node]) - mean
                continue
            if node in sampled_abduced_noises:
                shared_noise[node] = sampled_abduced_noises[node]
            else:
                if mechanism is None:
                    if node != treatment_variable and not allow_declared_hypothesis:
                        raise ValueError(
                            f"missing mechanism for node '{node}'; provide a fitted root "
                            "carrier or explicitly enable the declared root hypothesis"
                        )
                    if node != treatment_variable:
                        message = (
                            f"twin-network: missing mechanism for node '{node}'; using a declared "
                            "hypothesis only (standard normal root sampler is not a fitted law)"
                        )
                        if message not in warnings:
                            warnings.append(message)
                observed_root_value: float | None = None
                if (
                    mechanism is not None
                    and not mechanism.parents
                    and root_sample_index is not None
                    and mechanism.variable in observed_root_samples
                ):
                    values = observed_root_samples[mechanism.variable]
                    if values:
                        observed_root_value = float(values[root_sample_index % len(values)])
                shared_noise[node] = _sample_node_noise(
                    mechanism,
                    rng,
                    observed_root_value=observed_root_value,
                    warnings=warnings,
                    allow_declared_hypothesis=allow_declared_hypothesis,
                    declared_root_hypotheses=declared_root_hypotheses,
                )

        # ── Step 2: forward-simulate FACTUAL world (do(X=x₀)) ─────────────────
        factual: dict[str, float] = {}
        for node in order:
            if node == treatment_variable:
                factual[node] = _apply_intervention(
                    current_value=float(factual_intervention.value or 0.0),
                    intervention_spec=factual_intervention,
                    fallback_treatment_value=factual_intervention.value,
                    rng=rng,
                    warnings=warnings,
                )
            else:
                parent_vals = {p: factual[p] for p in parents_map.get(node, [])}
                factual[node] = _apply_node_noise(
                    mechanisms.get(node),
                    parent_vals,
                    shared_noise[node],
                    warnings,
                )

        # ── Step 3: forward-simulate COUNTERFACTUAL world (do(X=x₁)) ──────────
        counter: dict[str, float] = {}
        for node in order:
            if node == treatment_variable:
                counter[node] = _apply_intervention(
                    current_value=float(counterfactual_intervention.value or 0.0),
                    intervention_spec=counterfactual_intervention,
                    fallback_treatment_value=counterfactual_intervention.value,
                    rng=rng,
                    warnings=warnings,
                )
            else:
                parent_vals = {p: counter[p] for p in parents_map.get(node, [])}
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
            ParameterSpec(name="allow_declared_root_hypothesis", default=False),
            ParameterSpec(name="bootstrap_replicates", default=0),
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
        state: TwinNetworkQueryData | Mapping[str, Any],
        params: Mapping[str, Any],
    ) -> dict[str, Any]:
        payload = (
            state
            if isinstance(state, TwinNetworkQueryData)
            else TwinNetworkQueryData.model_validate(state)
        )

        scm_spec = _prepared_scm_query_spec(payload.scm_spec)
        n_samples = payload.n_samples
        confidence_level = float(params.get("confidence_level", 0.95))
        if not (0.0 < confidence_level < 1.0):
            raise ValueError("confidence_level must be in (0, 1)")
        store_distribution = params.get("store_distribution", True) is not False
        allow_declared_hypothesis = params.get("allow_declared_root_hypothesis", False) is True

        seed = int(params.get("__seed__", 0) or 0)
        rng_param = params.get("__rng__")
        rng: np.random.Generator = (
            rng_param if isinstance(rng_param, np.random.Generator) else np.random.default_rng(seed)
        )

        warnings: list[str] = []
        started_at = time.perf_counter()

        # The same query-local relevance plan governs admission and both worlds.
        factual_intervention = InterventionSpec(
            type=InterventionType.ATOMIC, value=payload.factual_treatment_value
        )
        counterfactual_intervention = InterventionSpec(
            type=InterventionType.ATOMIC, value=payload.counterfactual_treatment_value
        )
        active_nodes, natural_nodes = _query_relevance_plan(
            scm_spec,
            treatment_variable=payload.treatment_variable,
            outcome_variable=payload.outcome_variable,
            interventions=[factual_intervention, counterfactual_intervention],
            condition=payload.factual_condition,
        )
        order = [node for node in _topological_order(scm_spec) if node in active_nodes]
        parents_map = _parents_by_node(scm_spec)
        mechanisms = _mechanism_map(scm_spec)
        missing_root_nodes = sorted(
            node for node in natural_nodes if not parents_map.get(node) and node not in mechanisms
        )
        if missing_root_nodes and not allow_declared_hypothesis:
            raise ValueError(
                "missing mechanism for required root node(s): "
                f"{missing_root_nodes}; provide fitted carriers or explicitly enable "
                "allow_declared_root_hypothesis"
            )
        if missing_root_nodes:
            warnings.append(
                "declared root hypothesis used for missing node(s): "
                f"{missing_root_nodes}; result is limited and not gate eligible"
            )
        declared_root_hypotheses = set(missing_root_nodes)

        observed_roots = {
            node: values
            for node, values in _observed_root_samples(mechanisms).items()
            if node in active_nodes
        }
        _compatible_joint_root_indices(observed_roots, payload.factual_condition)
        abduced_noises: dict[str, float] = {}
        abduction_posterior: _LinearGaussianPosterior | None = None
        abduction_diagnostic = _AbductionDiagnostic(profile="not_requested")
        if payload.factual_condition:
            abduction_posterior, abduction_diagnostic = _prepare_linear_gaussian_abduction(
                condition=payload.factual_condition,
                order=order,
                parents_map=parents_map,
                mechanisms=mechanisms,
                treatment_variable=payload.treatment_variable,
                allow_observed_empirical_roots=True,
            )
            if abduction_posterior is None:
                abduced_noises = _abduce_noises_unified(
                    condition=payload.factual_condition,
                    order=order,
                    parents_map=parents_map,
                    mechanisms=mechanisms,
                    warnings=warnings,
                    conditioned_empirical_roots=frozenset(observed_roots).intersection(
                        payload.factual_condition
                    ),
                )
                abduction_diagnostic = abduction_diagnostic.with_noise_nodes(abduced_noises)
            if abduction_diagnostic.limitation is not None:
                warnings.append(f"limited abduction: {abduction_diagnostic.limitation}")

        # ── PREDICTION: dual-world Monte Carlo with shared noise ───────────────
        po_factual, po_counter = _twin_simulate_samples(
            scm_spec=scm_spec,
            treatment_variable=payload.treatment_variable,
            outcome_variable=payload.outcome_variable,
            factual_intervention=factual_intervention,
            counterfactual_intervention=counterfactual_intervention,
            abduced_noises=abduced_noises,
            abduction_posterior=abduction_posterior,
            n_samples=n_samples,
            rng=rng,
            warnings=warnings,
            allow_declared_hypothesis=allow_declared_hypothesis,
            declared_root_hypotheses=declared_root_hypotheses,
            active_nodes=active_nodes,
            factual_condition=payload.factual_condition,
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

        from polisyos.foundry.methods.catalog.causal.gcm_query import _refit_bootstrap_interval
        from polisyos.ir.analytics.causal_queries import (
            CausalContrastSpec,
            CausalQuery,
            CausalRegime,
            QueryType,
        )

        replicate_count = params.get("bootstrap_replicates", 0)
        if type(replicate_count) is not int:
            raise ValueError("bootstrap_replicates must be an integer")
        estimator_query = CausalQuery(
            query_type=QueryType.ATTRIBUTION,
            treatment_variable=payload.treatment_variable,
            outcome_variable=payload.outcome_variable,
            condition=payload.factual_condition,
            n_samples=n_samples,
            contrast=CausalContrastSpec(
                target=counterfactual_intervention,
                comparator=CausalRegime(kind="interventional", intervention=factual_intervention),
            ),
        )
        estimator_interval = (
            _refit_bootstrap_interval(
                scm_spec,
                estimator_query,
                seed=seed,
                confidence_level=confidence_level,
                replicate_count=replicate_count,
            )
            if replicate_count != 0
            else None
        )

        result = TwinNetworkResult(
            outcome_variable=payload.outcome_variable,
            result_kind=(
                CausalResultKind.POSTERIOR_CREDIBLE_INTERVAL
                if abduction_diagnostic.profile == "linear_gaussian_posterior"
                else CausalResultKind.ITE_DISTRIBUTION
            ),
            interval_level=confidence_level,
            estimator_interval=estimator_interval,
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
                "sampling_profile": "relevant_twin_shared_noise_v1",
                "n_abduced_nodes": len(abduction_diagnostic.noise_nodes),
                "factual_treatment_value": payload.factual_treatment_value,
                "counterfactual_treatment_value": payload.counterfactual_treatment_value,
                "declared_root_hypothesis": sorted(declared_root_hypotheses),
                **abduction_diagnostic.as_metadata(),
            },
        )

        envelope = result.to_uncertainty_envelope()
        if declared_root_hypotheses or not abduction_diagnostic.gate_eligible:
            envelope = envelope.model_copy(update={"gate_eligible": False})

        return {
            "twin_network_result": result,
            "envelope": envelope,
            "estimator_envelope": result.to_estimator_uncertainty_envelope(),
            "warnings": warnings,
            "__determinism_tier__": DeterminismTier.STATISTICAL,
        }


__all__ = [
    "TwinNetworkQuery",
    "_apply_node_noise",
    "_sample_node_noise",
    "_twin_simulate_samples",
]
