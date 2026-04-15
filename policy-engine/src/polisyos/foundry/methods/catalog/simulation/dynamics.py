"""Simulate system-dynamics, queue, compartmental, and agent-population mechanisms."""
from __future__ import annotations

from typing import Any, ClassVar, Mapping

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


def _result_slot() -> frozenset[SlotSpec]:
    return frozenset({SlotSpec("result", SlotType.SCALAR, Unit("result", "json"))})


def _vector(state: Mapping[str, Any], key: str) -> np.ndarray:
    arr = np.asarray(state[key], dtype=float)
    if arr.ndim != 1:
        raise ValueError(f"{key} must be a 1D vector")
    return arr


def _float(value: Any, default: float) -> float:
    if value is None:
        return float(default)
    return float(value)


def _runtime_fidelity(value: Any) -> Any:
    from polisyos.foundry.contracts.fidelity import FidelityLevel as RuntimeFidelityLevel

    return RuntimeFidelityLevel(str(value or RuntimeFidelityLevel.SURROGATE_FLUID.value))


def _agent_sim_vector(
    state: Mapping[str, Any],
    key: str,
    n_agents: int,
    *,
    default: float = 0.0,
) -> Any:
    import jax.numpy as jnp

    value = state.get(key)
    if value is None:
        return jnp.full((n_agents,), default, dtype=jnp.float32)
    arr = jnp.asarray(value, dtype=jnp.float32)
    if arr.shape == ():
        return jnp.full((n_agents,), arr, dtype=jnp.float32)
    if arr.shape != (n_agents,):
        raise ValueError(f"{key} must have shape ({n_agents},)")
    return arr


def _build_agent_sim_mechanism(name: str, cfg: Mapping[str, Any]) -> Any:
    normalized = str(name).strip().lower()
    if normalized == "taxation":
        from polisyos.foundry.agent_sim.mechanisms import TaxationMechanism

        return TaxationMechanism(progressive_factor=float(cfg.get("progressive_factor", 0.1)))
    if normalized == "aging":
        from polisyos.foundry.agent_sim.population_mechanisms import AgingMechanism

        return AgingMechanism(
            steps_per_year=int(cfg.get("steps_per_year", 12)),
            retirement_age=int(cfg.get("retirement_age", 65)),
        )
    if normalized == "birth":
        from polisyos.foundry.agent_sim.population_mechanisms import BirthMechanism

        return BirthMechanism(
            max_births_per_step=int(cfg.get("max_births_per_step", 32)),
            steps_per_year=int(cfg.get("steps_per_year", 12)),
        )
    if normalized == "death":
        from polisyos.foundry.agent_sim.population_mechanisms import DeathMechanism

        return DeathMechanism(
            base_mortality_rate=float(cfg.get("base_mortality_rate", 0.001)),
            steps_per_year=int(cfg.get("steps_per_year", 12)),
        )
    if normalized == "migration":
        from polisyos.foundry.agent_sim.population_mechanisms import MigrationMechanism

        return MigrationMechanism(
            immigration_rate=float(cfg.get("immigration_rate", 0.001)),
            emigration_rate=float(cfg.get("emigration_rate", 0.0005)),
            max_immigrants_per_step=int(cfg.get("max_immigrants_per_step", 32)),
            steps_per_year=int(cfg.get("steps_per_year", 12)),
        )
    if normalized == "social_influence":
        from polisyos.foundry.agent_sim.graph_mechanisms import SocialInfluenceMechanism

        return SocialInfluenceMechanism(
            influence_strength=float(cfg.get("influence_strength", 0.3)),
            aggregation=str(cfg.get("aggregation", "mean")),
        )
    if normalized == "information_diffusion":
        from polisyos.foundry.agent_sim.graph_mechanisms import InformationDiffusionMechanism

        return InformationDiffusionMechanism(
            diffusion_rate=float(cfg.get("diffusion_rate", 0.2)),
            decay_rate=float(cfg.get("decay_rate", 0.05)),
        )
    if normalized == "network_lending":
        from polisyos.foundry.agent_sim.graph_mechanisms import NetworkLendingMechanism

        return NetworkLendingMechanism(
            max_loan_fraction=float(cfg.get("max_loan_fraction", 0.1)),
            interest_rate=float(cfg.get("interest_rate", 0.05)),
        )
    if normalized == "labor_network":
        from polisyos.foundry.agent_sim.graph_mechanisms import LaborNetworkMechanism

        return LaborNetworkMechanism(
            referral_probability=float(cfg.get("referral_probability", 0.1)),
        )
    raise ValueError(f"Unsupported agent_sim mechanism '{name}'")


@foundry_method(
    namespace="simulation.system_dynamics",
    version="1.0.0",
    tags={"simulation", "system-dynamics", "stock-flow", "structural"},
)
class StockFlowSystemDynamicsEstimator:
    """Simulate deterministic stock-flow trajectories under a linear flow matrix; avoid strongly nonlinear feedbacks not encoded in the matrix."""
    method_kind: ClassVar[MethodKind] = MethodKind.SIMULATION
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="stock_flow",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("initial_stocks", SlotType.VECTOR, Unit("stock", "level"), shape=("n_stocks",)),
                SlotSpec("flow_matrix", SlotType.MATRIX, Unit("flow", "rate"), shape=("n_stocks", "n_stocks")),
            }
        ),
        output_slots=_result_slot(),
        parameters=(
            ParameterSpec(name="n_steps", default=24),
            ParameterSpec(name="dt", default=1.0),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Generic stock-and-flow system dynamics simulator over a linear flow matrix.",
        tags=frozenset({"simulation", "system-dynamics", "stock-flow", "structural"}),
        when_to_use="System dynamics with stocks and flows; policy feedback loops; long-run equilibrium",
        citations=(
            "Forrester, J. (1961). Industrial Dynamics. MIT Press.",
            "Sterman, J. (2000). Business Dynamics: Systems Thinking and Modeling for a Complex World. McGraw-Hill.",
        ),
        output_interpretation="Stock trajectories. Equilibrium = dStock/dt = 0. Time to equilibrium.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        stocks = _vector(state, "initial_stocks")
        flow_matrix = np.asarray(state["flow_matrix"], dtype=float)
        if flow_matrix.ndim != 2 or flow_matrix.shape[0] != flow_matrix.shape[1]:
            raise ValueError("flow_matrix must be a square matrix")
        if flow_matrix.shape[0] != stocks.shape[0]:
            raise ValueError("flow_matrix dimension must match initial_stocks")
        dt = max(1e-6, float(params.get("dt", 1.0)))
        n_steps = max(1, int(params.get("n_steps", 24)))
        exogenous = np.asarray(state.get("exogenous_inflows", np.zeros_like(stocks)), dtype=float)
        if exogenous.shape != stocks.shape:
            raise ValueError("exogenous_inflows must match initial_stocks shape")

        trajectory = np.zeros((n_steps + 1, stocks.shape[0]), dtype=float)
        trajectory[0] = stocks
        current = stocks.copy()
        positive_flows = np.clip(flow_matrix, 0.0, None)
        for step in range(1, n_steps + 1):
            transfers = dt * positive_flows * current[:, None]
            outflow = transfers.sum(axis=1)
            inflow = transfers.sum(axis=0)
            current = np.maximum(current + inflow - outflow + dt * exogenous, 0.0)
            trajectory[step] = current

        return {
            "result": {
                "trajectory": trajectory.tolist(),
                "final_stocks": current.tolist(),
                "mass_balance": float(np.sum(current) - np.sum(trajectory[0])),
            }
        }


@foundry_method(
    namespace="simulation.discrete_event",
    version="1.0.0",
    tags={"simulation", "discrete-event", "queue", "structural"},
)
class QueueDiscreteEventEstimator:
    """Simulate queue evolution under arrival/service rates and optional capacity; avoid when per-job event logs are required."""
    method_kind: ClassVar[MethodKind] = MethodKind.SIMULATION
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("jax",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="queue",
        namespace="",
        version="0.0.0",
        input_slots=frozenset({SlotSpec("queue_length", SlotType.SCALAR, Unit("queue", "count"))}),
        output_slots=_result_slot(),
        parameters=(
            ParameterSpec(name="service_rate", default=1.0),
            ParameterSpec(name="arrival_rate", default=0.5),
            ParameterSpec(name="capacity", default=None),
            ParameterSpec(name="temperature", default=1.0),
            ParameterSpec(name="n_steps", default=20),
            ParameterSpec(name="fidelity", default="fluid"),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Queue simulation using the Foundry discrete-event runtime mechanism.",
        tags=frozenset({"simulation", "discrete-event", "queue", "structural"}),
        when_to_use="Service system modeling; waiting-time analysis; congestion and capacity policy analysis",
        citations=(
            "Banks, J. et al. (2005). Discrete-Event System Simulation. Prentice Hall.",
        ),
        output_interpretation="Final queue length after simulation. Compare to steady-state M/M/1 rho=lambda/mu. Capacity hit = queue grows unbounded.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        import jax
        import jax.numpy as jnp

        from polisyos.foundry.queue import QueueMechanism, QueueState, simulate_queue

        mechanism = QueueMechanism(
            service_rate=float(params.get("service_rate", 1.0)),
            arrival_rate=float(params.get("arrival_rate", 0.5)),
            capacity=params.get("capacity"),
            temperature=float(params.get("temperature", 1.0)),
            fidelity=_runtime_fidelity(params.get("fidelity")),
        )
        queue_state = QueueState(queue_length=jnp.asarray(state["queue_length"], dtype=jnp.float32))
        final_state = simulate_queue(
            mechanism,
            queue_state,
            jax.random.PRNGKey(int(params.get("__seed__", 0))),
            steps=max(1, int(params.get("n_steps", 20))),
        )
        return {
            "result": {
                "final_queue_length": float(final_state.queue_length),
                "initial_queue_length": float(queue_state.queue_length),
            }
        }


@foundry_method(
    namespace="simulation.compartmental",
    version="1.0.0",
    tags={"simulation", "compartmental", "sir", "structural"},
)
class SIRCompartmentalEstimator:
    """Simulate SIR epidemic dynamics under homogeneous mixing; avoid latent-incubation processes that need an exposed compartment."""
    method_kind: ClassVar[MethodKind] = MethodKind.SIMULATION
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="sir",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("susceptible", SlotType.SCALAR, Unit("population", "count")),
                SlotSpec("infected", SlotType.SCALAR, Unit("population", "count")),
                SlotSpec("recovered", SlotType.SCALAR, Unit("population", "count")),
            }
        ),
        output_slots=_result_slot(),
        parameters=(
            ParameterSpec(name="beta", default=0.35),
            ParameterSpec(name="gamma", default=0.1),
            ParameterSpec(name="n_steps", default=60),
            ParameterSpec(name="dt", default=1.0),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Classical SIR compartmental epidemic simulator.",
        tags=frozenset({"simulation", "compartmental", "sir", "structural"}),
        when_to_use="Epidemiological modeling; disease spread simulation; vaccination policy analysis",
        citations=(
            "Kermack, W. & McKendrick, A. (1927). A contribution to the mathematical theory of epidemics. Proceedings of the Royal Society A, 115(772), 700-721.",
        ),
        when_not_to_use="Non-infectious disease; no compartmental structure",
        output_interpretation="Time paths of S/I/R/E compartments. R0>1 = epidemic grows. Peak infection timing and size.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        beta = max(0.0, float(params.get("beta", 0.35)))
        gamma = max(0.0, float(params.get("gamma", 0.1)))
        dt = max(1e-6, float(params.get("dt", 1.0)))
        n_steps = max(1, int(params.get("n_steps", 60)))

        s = float(state["susceptible"])
        i = float(state["infected"])
        r = float(state["recovered"])
        population = max(s + i + r, 1e-12)
        trajectory = []
        for _ in range(n_steps):
            new_infections = dt * beta * s * i / population
            new_recoveries = dt * gamma * i
            new_infections = min(new_infections, s)
            new_recoveries = min(new_recoveries, i + new_infections)
            s = max(0.0, s - new_infections)
            i = max(0.0, i + new_infections - new_recoveries)
            r = max(0.0, r + new_recoveries)
            trajectory.append([s, i, r])

        peak_infected = max((item[1] for item in trajectory), default=i)
        return {
            "result": {
                "trajectory": trajectory,
                "peak_infected": float(peak_infected),
                "final_state": {"susceptible": s, "infected": i, "recovered": r},
            }
        }


@foundry_method(
    namespace="simulation.compartmental",
    version="1.0.0",
    tags={"simulation", "compartmental", "seir", "structural"},
)
class SEIRCompartmentalEstimator:
    """Simulate SEIR epidemic dynamics with an exposed compartment; avoid highly networked contact structure that violates homogeneous mixing."""
    method_kind: ClassVar[MethodKind] = MethodKind.SIMULATION
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="seir",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("susceptible", SlotType.SCALAR, Unit("population", "count")),
                SlotSpec("exposed", SlotType.SCALAR, Unit("population", "count")),
                SlotSpec("infected", SlotType.SCALAR, Unit("population", "count")),
                SlotSpec("recovered", SlotType.SCALAR, Unit("population", "count")),
            }
        ),
        output_slots=_result_slot(),
        parameters=(
            ParameterSpec(name="beta", default=0.35),
            ParameterSpec(name="sigma", default=0.2),
            ParameterSpec(name="gamma", default=0.1),
            ParameterSpec(name="n_steps", default=60),
            ParameterSpec(name="dt", default=1.0),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="SEIR compartmental epidemic simulator with exposed compartment.",
        tags=frozenset({"simulation", "compartmental", "seir", "structural"}),
        when_to_use="Epidemiological modeling; disease spread simulation; vaccination policy analysis",
        citations=(
            "Kermack, W. & McKendrick, A. (1927). A contribution to the mathematical theory of epidemics. Proceedings of the Royal Society A, 115(772), 700-721.",
            "Hethcote, H. (2000). The mathematics of infectious diseases. SIAM Review, 42(4), 599-653.",
        ),
        when_not_to_use="Non-infectious disease; no compartmental structure",
        output_interpretation="Time paths of S/I/R/E compartments. R0>1 = epidemic grows. Peak infection timing and size.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        beta = max(0.0, float(params.get("beta", 0.35)))
        sigma = max(0.0, float(params.get("sigma", 0.2)))
        gamma = max(0.0, float(params.get("gamma", 0.1)))
        dt = max(1e-6, float(params.get("dt", 1.0)))
        n_steps = max(1, int(params.get("n_steps", 60)))

        s = float(state["susceptible"])
        e = float(state["exposed"])
        i = float(state["infected"])
        r = float(state["recovered"])
        population = max(s + e + i + r, 1e-12)
        trajectory = []
        for _ in range(n_steps):
            new_exposed = min(dt * beta * s * i / population, s)
            new_infectious = min(dt * sigma * e, e + new_exposed)
            new_recoveries = min(dt * gamma * i, i + new_infectious)
            s = max(0.0, s - new_exposed)
            e = max(0.0, e + new_exposed - new_infectious)
            i = max(0.0, i + new_infectious - new_recoveries)
            r = max(0.0, r + new_recoveries)
            trajectory.append([s, e, i, r])

        peak_infected = max((item[2] for item in trajectory), default=i)
        return {
            "result": {
                "trajectory": trajectory,
                "peak_infected": float(peak_infected),
                "final_state": {"susceptible": s, "exposed": e, "infected": i, "recovered": r},
            }
        }


@foundry_method(
    namespace="simulation.agent_based",
    version="1.0.0",
    tags={"simulation", "agent-based", "agent-sim", "structural"},
)
class AgentPopulationSimulationEstimator:
    """Replay selected agent-sim mechanisms over synthetic microstate; avoid treating the output as observed data without a separate measurement layer."""
    method_kind: ClassVar[MethodKind] = MethodKind.SIMULATION
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STRICT_CPU
    runtime_stack: ClassVar[tuple[str, ...]] = ("jax",)
    method_family: ClassVar[str] = "simulation.agent_based"

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="population_dynamics",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("initial_wealth", SlotType.VECTOR, Unit("wealth", "amount"), shape=("n_agents",)),
                SlotSpec("initial_income", SlotType.VECTOR, Unit("income", "amount"), shape=("n_agents",)),
            }
        ),
        output_slots=_result_slot(),
        parameters=(
            ParameterSpec(name="n_steps", default=12, is_static=True),
            ParameterSpec(name="mechanism_names", default=("taxation", "aging"), is_static=True),
            ParameterSpec(name="mechanism_configs", default=None, is_static=True),
            ParameterSpec(name="fidelity", default="fluid", is_static=True),
            ParameterSpec(name="seed", default=0, is_static=True),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.JAX,
        supports_jit=True,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Run agent_sim population dynamics through the unified MethodRegistry.",
        tags=frozenset({"simulation", "agent-based", "agent-sim", "structural"}),
        when_to_use="Heterogeneous agents with local interactions; emergent phenomena; behavioral heterogeneity",
        citations=(
            "Bonabeau, E. (2002). Agent-based modeling: Methods and techniques for simulating human systems. PNAS, 99(suppl 3), 7280-7287.",
        ),
        when_not_to_use="Need analytical closed-form; computationally infeasible for required population size",
        output_interpretation="Ensemble statistics over simulation runs. Macro patterns emerging from micro rules.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        import jax.numpy as jnp

        from polisyos.foundry.agent_sim.executor import PureExecutor
        from polisyos.foundry.agent_sim.state import GlobalState as AgentSimGlobalState

        initial_wealth = jnp.asarray(state["initial_wealth"], dtype=jnp.float32)
        initial_income = jnp.asarray(state["initial_income"], dtype=jnp.float32)
        if initial_wealth.ndim != 1 or initial_income.ndim != 1:
            raise ValueError("initial_wealth and initial_income must be 1D vectors")
        if initial_wealth.shape != initial_income.shape:
            raise ValueError("initial_wealth and initial_income must have the same shape")
        n_agents = int(initial_wealth.shape[0])
        n_steps = max(1, int(params.get("n_steps", 12)))
        seed = int(params.get("seed", 0))
        mechanism_names = tuple(params.get("mechanism_names", ("taxation", "aging")))
        mechanism_configs = params.get("mechanism_configs") or {}
        if not isinstance(mechanism_configs, Mapping):
            raise ValueError("mechanism_configs must be a mapping of mechanism name to config")
        mechanisms = [
            _build_agent_sim_mechanism(name, mechanism_configs.get(name, {}))
            for name in mechanism_names
        ]

        initial_state = AgentSimGlobalState.empty(
            n_agents=n_agents,
            seed=seed,
            simulation_horizon=n_steps,
        )
        agents = initial_state.agents.replace(
            wealth=initial_wealth,
            income=initial_income,
            consumption=_agent_sim_vector(state, "initial_consumption", n_agents, default=5.0),
            active=jnp.asarray(state.get("active_mask", jnp.ones(n_agents, dtype=jnp.bool_)), dtype=jnp.bool_),
        )
        policy = initial_state.policy.replace(
            tax_rate=jnp.asarray(_float(state.get("tax_rate"), 0.2), dtype=jnp.float32),
            transfer_rate=jnp.asarray(_float(state.get("transfer_rate"), 0.0), dtype=jnp.float32),
            interest_rate=jnp.asarray(_float(state.get("interest_rate"), 0.01), dtype=jnp.float32),
            expected_interest_rate=jnp.asarray(_float(state.get("expected_interest_rate"), 0.01), dtype=jnp.float32),
        )
        initial_state = initial_state.replace(agents=agents, policy=policy)

        executor = PureExecutor(mechanisms, aggregate_every=1, compute_gini=True)
        final_state, metrics = executor.run(
            initial_state,
            n_steps,
            fidelity=_runtime_fidelity(params.get("fidelity")),
        )
        metric_means = {key: jnp.mean(value) for key, value in metrics.items()}
        return {
            "result": {
                "final_total_wealth": final_state.aggregates.total_wealth,
                "final_mean_consumption": final_state.aggregates.mean_consumption,
                "final_gini": final_state.distributions.gini_wealth,
                "final_active_agents": final_state.population_manager.n_active,
                "final_time_step": final_state.time_step,
                "mean_metrics": metric_means,
            }
        }


__all__ = [
    "AgentPopulationSimulationEstimator",
    "QueueDiscreteEventEstimator",
    "SEIRCompartmentalEstimator",
    "SIRCompartmentalEstimator",
    "StockFlowSystemDynamicsEstimator",
]
