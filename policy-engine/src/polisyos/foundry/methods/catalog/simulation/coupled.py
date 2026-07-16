"""Coupled DES/ABM simulation methods."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, ClassVar

import numpy as np

from polisyos.core.observability.determinism import DeterminismTier
from polisyos.foundry.methods.base import (
    ComplexityClass,
    ComputeBackend,
    FidelityLevel,
    MethodKind,
    MethodMetadata,
    MethodSignature,
    ParameterSpec,
    SlotSpec,
    SlotType,
    Unit,
    foundry_method,
)
from polisyos.foundry.methods.catalog.simulation.dynamics import (
    build_content_bound_abm_result,
)


def _result_slot() -> frozenset[SlotSpec]:
    return frozenset({SlotSpec("result", SlotType.SCALAR, Unit("result", "json"))})


def _vector(
    state: Mapping[str, Any],
    key: str,
    *,
    n_agents: int | None = None,
    default: float | None = None,
) -> np.ndarray:
    if key not in state:
        if n_agents is None or default is None:
            raise ValueError(f"{key} is required")
        return np.full((n_agents,), default, dtype=float)
    arr = np.asarray(state[key], dtype=float)
    if arr.ndim != 1:
        raise ValueError(f"{key} must be a 1D vector")
    if n_agents is not None and arr.shape != (n_agents,):
        raise ValueError(f"{key} must have shape ({n_agents},)")
    return arr


def _metric_names(params: Mapping[str, Any], default: tuple[str, ...]) -> tuple[str, ...]:
    raw = params.get("metric_names", default)
    if isinstance(raw, str):
        return tuple(item.strip() for item in raw.split(",") if item.strip())
    return tuple(str(item) for item in raw)


def _run_coupled_policy(
    state: Mapping[str, Any],
    params: Mapping[str, Any],
    *,
    seed: int | None = None,
    service_rate: float | None = None,
    benefit_amount: float | None = None,
) -> dict[str, Any]:
    import jax
    import jax.numpy as jnp

    from polisyos.foundry.contracts.state import GlobalState, QueueRuntimeState
    from polisyos.foundry.coupling.abm_kernel import UnemploymentClaimABMKernel
    from polisyos.foundry.coupling.coupler import DefaultPolicyCoupler
    from polisyos.foundry.coupling.des_kernel import QueueDESKernel
    from polisyos.foundry.coupling.estimation import extract_coupled_summary
    from polisyos.foundry.coupling.executor import (
        CoupledContractsExecutor,
        CoupledRuntimeState,
    )

    income = _vector(state, "initial_income")
    n_agents = int(income.shape[0])
    savings = _vector(state, "initial_savings", n_agents=n_agents, default=0.0)
    employed = _vector(state, "is_employed", n_agents=n_agents, default=0.0) > 0.5
    risk = _vector(state, "risk_aversion", n_agents=n_agents, default=0.5)

    base_state = GlobalState.empty(n_agents=n_agents, n_firms=1)
    global_state = base_state.replace(
        agents=base_state.agents.replace(
            income=jnp.asarray(income, dtype=jnp.float32),
            reported_income=jnp.asarray(income, dtype=jnp.float32),
            savings=jnp.asarray(savings, dtype=jnp.float32),
            risk_aversion=jnp.asarray(risk, dtype=jnp.float32),
            is_employed=jnp.asarray(employed, dtype=jnp.bool_),
        )
    )
    capacity_raw = params.get("capacity")
    capacity = None if capacity_raw is None else float(capacity_raw)
    resolved_service_rate = float(
        params.get("service_rate", 1.0) if service_rate is None else service_rate
    )
    resolved_benefit = float(
        params.get("benefit_amount", 0.0) if benefit_amount is None else benefit_amount
    )
    queue_state = QueueRuntimeState.empty(
        n_agents,
        capacity=capacity,
        queue_length=float(params.get("initial_queue_length", 0.0)),
        n_events=int(params.get("n_events", max(n_agents * 2, 1))),
    )
    executor = CoupledContractsExecutor(
        des_kernel=QueueDESKernel(
            service_rate=resolved_service_rate,
            capacity=capacity,
            time_step=float(params.get("delta_a_max", 1.0)),
        ),
        abm_kernel=UnemploymentClaimABMKernel(),
        coupler=DefaultPolicyCoupler(benefit_amount=resolved_benefit),
        delta_a_max=float(params.get("delta_a_max", 1.0)),
    )
    runtime = CoupledRuntimeState.initialize(
        global_state,
        queue_state=queue_state,
        rng_key=jax.random.PRNGKey(int(params.get("seed", 0) if seed is None else seed)),
    )
    final_runtime, metrics = executor.run(runtime, max(1, int(params.get("n_steps", 12))))
    final_state = final_runtime.global_state
    final_queue = final_runtime.queue_state
    queue_trajectory = [float(item["queue/queue_length"]) for item in metrics]
    summary = extract_coupled_summary(final_runtime, metrics)
    result = {
        "final_queue_length": float(np.asarray(final_queue.queue_length).item()),
        "admitted_count": int(np.asarray(final_queue.admitted_count).item()),
        "completed_count": int(np.asarray(final_queue.completed_count).item()),
        "rejected_count": int(np.asarray(final_queue.rejected_count).item()),
        "queue_length_trajectory": queue_trajectory,
        "final_savings": np.asarray(final_state.agents.savings).astype(float).tolist(),
        "final_income": np.asarray(final_state.agents.income).astype(float).tolist(),
        "final_step": int(np.asarray(final_state.step).item()),
        "summary": summary,
        "metrics": metrics,
    }
    horizon = max(1, int(params.get("n_steps", 12)))
    diagnostics = {
        "method_id": "simulation.coupled_policy.des_abm",
        "horizon": horizon,
        "diagnostic_source": "CoupledPolicySimulationEstimator.pure_step",
        "summary_keys": (
            sorted(str(key) for key in summary)
            if isinstance(summary, Mapping)
            else []
        ),
    }
    abm_result = build_content_bound_abm_result(
        method_id="simulation.coupled_policy.des_abm",
        horizon=horizon,
        payload=result,
        diagnostics=diagnostics,
    )
    result["abm_result"] = abm_result.model_dump(mode="json")
    return result


@foundry_method(
    namespace="simulation.coupled_policy",
    version="1.0.0",
    tags={"simulation", "discrete-event", "agent-based", "structural", "coupled"},
)
class CoupledPolicySimulationEstimator:
    """Run a typed DES+ABM policy simulation over canonical Foundry state."""

    method_kind: ClassVar[MethodKind] = MethodKind.SIMULATION
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STRICT_CPU
    runtime_stack: ClassVar[tuple[str, ...]] = ("jax", "numpy")
    method_family: ClassVar[str] = "simulation.coupled_policy"

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="des_abm",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    "initial_income",
                    SlotType.VECTOR,
                    Unit("income", "amount"),
                    shape=("n_agents",),
                ),
                SlotSpec(
                    "initial_savings",
                    SlotType.VECTOR,
                    Unit("wealth", "amount"),
                    shape=("n_agents",),
                ),
                SlotSpec(
                    "is_employed",
                    SlotType.VECTOR,
                    Unit("employment", "indicator"),
                    shape=("n_agents",),
                ),
            }
        ),
        output_slots=_result_slot(),
        parameters=(
            ParameterSpec(name="n_steps", default=12, is_static=True),
            ParameterSpec(name="service_rate", default=1.0),
            ParameterSpec(name="capacity", default=None),
            ParameterSpec(name="delta_a_max", default=1.0),
            ParameterSpec(name="benefit_amount", default=0.0),
            ParameterSpec(name="initial_queue_length", default=0.0),
            ParameterSpec(name="seed", default=0, is_static=True),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N,
        backend=ComputeBackend.JAX,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Typed coupled DES+ABM simulation with queue lifecycle messages.",
        tags=frozenset({"simulation", "discrete-event", "agent-based", "structural", "coupled"}),
        assumptions={
            "joint_simulation_engine_kind": "coupled_des_abm",
            "joint_simulation_policy_domains": "unemployment_claims_benefit",
            "joint_simulation_required_structure": (
                "unemployment_claims,benefit_queue,service_queue"
            ),
        },
        when_to_use=(
            "Policy simulations where a service queue and heterogeneous agent "
            "decisions form a feedback loop."
        ),
        citations=(
            "Banks, J. et al. (2005). Discrete-Event System Simulation. Prentice Hall.",
            "Bonabeau, E. (2002). Agent-based modeling: Methods and techniques for simulating human systems. PNAS.",
        ),
        output_interpretation=(
            "Queue lifecycle metrics plus final canonical microstate projections. "
            "Use paired seeds for policy comparisons."
        ),
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        result = _run_coupled_policy(state, params)
        return {"result": result}


@foundry_method(
    namespace="simulation.coupled_policy",
    version="1.0.0",
    tags={"simulation", "inference", "discrete-event", "structural", "coupled"},
)
class CoupledQueueMLEEstimator:
    """Estimate local DES arrival/service/routing rates from queue event logs."""

    method_kind: ClassVar[MethodKind] = MethodKind.SIMULATION
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STRICT_CPU
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)
    method_family: ClassVar[str] = "simulation.coupled_policy"

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="queue_mle",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    "event_times", SlotType.VECTOR, Unit("time", "period"), shape=("n_events",)
                ),
                SlotSpec(
                    "event_kind_codes",
                    SlotType.VECTOR,
                    Unit("event_kind", "code"),
                    shape=("n_events",),
                ),
            }
        ),
        output_slots=_result_slot(),
        parameters=(
            ParameterSpec(name="arrival_code", default=1, is_static=True),
            ParameterSpec(name="service_start_code", default=2, is_static=True),
            ParameterSpec(name="service_complete_code", default=3, is_static=True),
            ParameterSpec(name="abandonment_code", default=4, is_static=True),
        ),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_N,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Local MLE/partial-likelihood adapter for queue-side DES parameters.",
        tags=frozenset({"simulation", "inference", "discrete-event", "structural", "coupled"}),
        when_to_use="Administrative event logs expose arrival, service, abandonment, or route events.",
        output_interpretation="Rates are per observed time window; routing probabilities are empirical shares.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        from polisyos.foundry.coupling.estimation import estimate_queue_mle

        times = _vector(state, "event_times")
        kinds = _vector(state, "event_kind_codes", n_agents=int(times.shape[0]))
        entities = np.asarray(state.get("event_entity_codes", np.arange(times.shape[0])), dtype=int)
        routes = np.asarray(state.get("route_codes", np.full(times.shape[0], -1)), dtype=int)
        if entities.shape != times.shape or routes.shape != times.shape:
            raise ValueError("event_entity_codes and route_codes must match event_times shape")

        kind_map = {
            int(params.get("arrival_code", 1)): "arrival",
            int(params.get("service_start_code", 2)): "service_start",
            int(params.get("service_complete_code", 3)): "service_complete",
            int(params.get("abandonment_code", 4)): "abandon",
        }
        event_log = [
            {
                "time": float(time),
                "kind": kind_map.get(int(kind), "other"),
                "entity_id": f"agent-{int(entity)}",
                "route": str(int(route)) if int(route) >= 0 else None,
            }
            for time, kind, entity, route in zip(times, kinds, entities, routes, strict=True)
        ]
        estimate = estimate_queue_mle(event_log)
        return {
            "result": {
                "arrival_rate": estimate.arrival_rate,
                "service_rate": estimate.service_rate,
                "abandonment_rate": estimate.abandonment_rate,
                "observation_window": estimate.observation_window,
                "n_arrivals": estimate.n_arrivals,
                "n_service_completions": estimate.n_service_completions,
                "n_abandonments": estimate.n_abandonments,
                "routing_probabilities": estimate.routing_probabilities,
            }
        }


@foundry_method(
    namespace="simulation.coupled_policy",
    version="1.0.0",
    tags={"simulation", "inference", "smm", "structural", "coupled"},
)
class CoupledSMMEstimator:
    """Grid-search SMM adapter for coupled DES/ABM summaries."""

    method_kind: ClassVar[MethodKind] = MethodKind.SIMULATION
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STRICT_CPU
    runtime_stack: ClassVar[tuple[str, ...]] = ("jax", "numpy")
    method_family: ClassVar[str] = "simulation.coupled_policy"

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="smm",
        namespace="",
        version="0.0.0",
        input_slots=CoupledPolicySimulationEstimator.signature.input_slots
        | frozenset(
            {
                SlotSpec(
                    "observed_moments",
                    SlotType.VECTOR,
                    Unit("moment", "value"),
                    shape=("n_moments",),
                ),
            }
        ),
        output_slots=_result_slot(),
        parameters=(
            ParameterSpec(
                name="moment_names",
                default=("completed_count", "final_queue_length"),
                is_static=True,
            ),
            ParameterSpec(name="service_rate_grid", default=(0.5, 1.0, 2.0), is_static=True),
            ParameterSpec(name="benefit_amount_grid", default=(0.0,), is_static=True),
            ParameterSpec(name="seeds", default=(0,), is_static=True),
            ParameterSpec(name="n_steps", default=12, is_static=True),
            ParameterSpec(name="capacity", default=None),
            ParameterSpec(name="delta_a_max", default=1.0),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.JAX,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Summary-based SMM/indirect-inference adapter for coupled DES+ABM outputs.",
        tags=frozenset({"simulation", "inference", "smm", "structural", "coupled"}),
        when_to_use="Behavioral and operational channels are jointly calibrated from moments.",
        citations=(
            "McFadden, D. (1989). A method of simulated moments for estimation of discrete response models without numerical integration. Econometrica.",
            "Gourieroux, C., Monfort, A., and Renault, E. (1993). Indirect inference. Journal of Applied Econometrics.",
        ),
        output_interpretation="Best grid point, fitted moments, loss, and the evaluated surface.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        from polisyos.foundry.coupling.estimation import calibrate_coupled_smm

        moment_names = _metric_names(
            params,
            ("completed_count", "final_queue_length"),
        )
        observed_values = _vector(state, "observed_moments")
        if observed_values.shape[0] != len(moment_names):
            raise ValueError("observed_moments length must match moment_names")
        observed = dict(zip(moment_names, (float(item) for item in observed_values), strict=True))
        seeds = tuple(int(seed) for seed in params.get("seeds", (0,)))
        grid = {
            "service_rate": tuple(float(item) for item in params.get("service_rate_grid", (1.0,))),
            "benefit_amount": tuple(
                float(item) for item in params.get("benefit_amount_grid", (0.0,))
            ),
        }

        def runner(candidate: Mapping[str, float], seed: int | None) -> Mapping[str, float]:
            run_params = {
                **dict(params),
                "service_rate": candidate["service_rate"],
                "benefit_amount": candidate["benefit_amount"],
                "seed": 0 if seed is None else int(seed),
            }
            result = _run_coupled_policy(state, run_params)
            return {
                **result["summary"],
                **{key: float(result[key]) for key in observed if key in result},
            }

        result = calibrate_coupled_smm(grid, runner, observed, seeds=seeds)
        return {
            "result": {
                "best_params": result.best_params,
                "best_loss": result.best_loss,
                "fitted_summary": result.fitted_summary,
                "observed_summary": result.observed_summary,
                "evaluated": list(result.evaluated),
            }
        }


@foundry_method(
    namespace="simulation.coupled_policy",
    version="1.0.0",
    tags={"simulation", "filtering", "particle-filter", "structural", "coupled"},
)
class CoupledQueueParticleFilterEstimator:
    """Sequential hidden queue-length filter for coupled DES/ABM monitoring."""

    method_kind: ClassVar[MethodKind] = MethodKind.SIMULATION
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)
    method_family: ClassVar[str] = "simulation.coupled_policy"

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="particle_filter",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    "observed_queue_lengths",
                    SlotType.VECTOR,
                    Unit("queue", "count"),
                    shape=("n_periods",),
                ),
            }
        ),
        output_slots=_result_slot(),
        parameters=(
            ParameterSpec(name="arrival_rate", default=1.0),
            ParameterSpec(name="service_rate", default=1.0),
            ParameterSpec(name="observation_std", default=1.0),
            ParameterSpec(name="n_particles", default=256, is_static=True),
            ParameterSpec(name="seed", default=0, is_static=True),
        ),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Bootstrap particle filter for latent queue pressure under noisy observations.",
        tags=frozenset({"simulation", "filtering", "particle-filter", "structural", "coupled"}),
        when_to_use="Streaming queue counts are noisy or partially observed.",
        output_interpretation="Filtered mean/std and effective sample size per period.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        from polisyos.foundry.coupling.estimation import filter_queue_counts

        result = filter_queue_counts(
            _vector(state, "observed_queue_lengths"),
            arrival_rate=float(params.get("arrival_rate", 1.0)),
            service_rate=float(params.get("service_rate", 1.0)),
            observation_std=float(params.get("observation_std", 1.0)),
            n_particles=int(params.get("n_particles", 256)),
            seed=int(params.get("seed", 0)),
        )
        return {
            "result": {
                "filtered_mean": list(result.filtered_mean),
                "filtered_std": list(result.filtered_std),
                "effective_sample_size": list(result.effective_sample_size),
                "log_likelihood": result.log_likelihood,
            }
        }


@foundry_method(
    namespace="simulation.coupled_policy",
    version="1.0.0",
    tags={"simulation", "monte-carlo", "policy-effect", "structural", "coupled"},
)
class CoupledPairedMonteCarloEstimator:
    """Common-random-number policy effect adapter for coupled simulations."""

    method_kind: ClassVar[MethodKind] = MethodKind.SIMULATION
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("jax", "numpy")
    method_family: ClassVar[str] = "simulation.coupled_policy"

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="paired_mc",
        namespace="",
        version="0.0.0",
        input_slots=CoupledPolicySimulationEstimator.signature.input_slots,
        output_slots=_result_slot(),
        parameters=(
            ParameterSpec(
                name="metric_names",
                default=("completed_count", "final_queue_length"),
                is_static=True,
            ),
            ParameterSpec(name="n_replications", default=16, is_static=True),
            ParameterSpec(name="seed", default=0, is_static=True),
            ParameterSpec(name="baseline_benefit_amount", default=0.0),
            ParameterSpec(name="policy_benefit_amount", default=0.0),
            ParameterSpec(name="service_rate", default=1.0),
            ParameterSpec(name="capacity", default=None),
            ParameterSpec(name="n_steps", default=12, is_static=True),
            ParameterSpec(name="delta_a_max", default=1.0),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.JAX,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Paired Monte Carlo policy-effect estimates for coupled DES+ABM outputs.",
        tags=frozenset({"simulation", "monte-carlo", "policy-effect", "structural", "coupled"}),
        when_to_use="Compare policy scenarios while holding simulator random streams fixed.",
        citations=(
            "Glasserman, P. (2004). Monte Carlo Methods in Financial Engineering. Springer.",
            "Asmussen, S. and Glynn, P. W. (2007). Stochastic Simulation: Algorithms and Analysis. Springer.",
        ),
        output_interpretation="Mean paired differences and standard errors for requested metrics.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        from polisyos.foundry.coupling.estimation import paired_monte_carlo_effect

        metric_names = _metric_names(
            params,
            ("completed_count", "final_queue_length"),
        )
        n_replications = max(int(params.get("n_replications", 16)), 1)
        seed0 = int(params.get("seed", 0))
        seeds = tuple(seed0 + idx for idx in range(n_replications))

        def metric_projection(result: Mapping[str, Any]) -> dict[str, float]:
            summary = result.get("summary", {})
            projected: dict[str, float] = {}
            for name in metric_names:
                if name in result:
                    projected[name] = float(result[name])
                elif isinstance(summary, Mapping) and name in summary:
                    projected[name] = float(summary[name])
            return projected

        baseline_benefit = float(params.get("baseline_benefit_amount", 0.0))
        policy_benefit = float(params.get("policy_benefit_amount", 0.0))
        result = paired_monte_carlo_effect(
            lambda seed: metric_projection(
                _run_coupled_policy(state, params, seed=seed, benefit_amount=baseline_benefit)
            ),
            lambda seed: metric_projection(
                _run_coupled_policy(state, params, seed=seed, benefit_amount=policy_benefit)
            ),
            seeds=seeds,
            metric_names=metric_names,
        )
        return {
            "result": {
                "mean_effects": result.mean_effects,
                "standard_errors": result.standard_errors,
                "paired_differences": list(result.paired_differences),
                "n_replications": result.n_replications,
            }
        }


__all__ = [
    "CoupledPairedMonteCarloEstimator",
    "CoupledPolicySimulationEstimator",
    "CoupledQueueMLEEstimator",
    "CoupledQueueParticleFilterEstimator",
    "CoupledSMMEstimator",
]
