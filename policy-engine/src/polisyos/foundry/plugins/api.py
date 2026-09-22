"""Public plugins api module API."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Literal

import jax
import jax.numpy as jnp

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.foundry.agent_sim.actor_critic import ActorCritic
from polisyos.foundry.agent_sim.artifact import AgentPolicyArtifact
from polisyos.foundry.agent_sim.training import TrainingConfig
from polisyos.foundry.plugins.composite import (
    CompositeExecutor,
    CompositeObjective,
    CompositeState,
    CompositeStateConfig,
    CrossDomainInteraction,
)
from polisyos.foundry.plugins.core import DomainConfig, PluginRegistry, get_registry
from polisyos.foundry.plugins.discovery import auto_register_plugins
from polisyos.foundry.plugins.training_adapter import (
    EconomicsTrainingAdapter,
    TrainingBridgeError,
)


@dataclass
class SimulationConfig:
    """High-level simulation configuration."""

    domains: dict[str, DomainConfig] = field(default_factory=dict)
    n_steps: int = 256
    n_episodes: int = 100
    seed: int = 42
    agent_learning: bool = True
    policy_learning: bool = False
    learning_rate: float = 3e-4
    objectives: dict[str, tuple[str, str, float]] = field(default_factory=dict)
    output_dir: Path = Path("./output")
    save_checkpoints: bool = True
    checkpoint_frequency: int = 10


class PolisySimulator:
    """High-level API for running policy simulations."""

    def __init__(
        self,
        registry: PluginRegistry | None = None,
        auto_discover: bool = True,
    ):
        self.registry = registry or get_registry()
        if auto_discover:
            auto_register_plugins(self.registry)

        self.domains: dict[str, DomainConfig] = {}
        self.interactions: list[dict[str, Any]] = []
        self.objectives: dict[str, tuple[str, str, float]] = {}
        self._state: CompositeState | None = None
        self._executor: CompositeExecutor | None = None
        self._agent_policy: ActorCritic | None = None
        self._training_config: TrainingConfig | None = None

    def add_domain(
        self,
        name: str,
        config: DomainConfig | None = None,
        **kwargs,
    ) -> PolisySimulator:
        available = [p.name for p in self.registry.list_plugins()]
        if name not in available:
            raise ValueError(f"Unknown domain '{name}'. Available: {available}")

        if config is None:
            config = DomainConfig(**kwargs)

        self.domains[name] = config
        return self

    def add_interaction(
        self,
        source_domain: str,
        target_domain: str,
        source_field: str,
        target_field: str,
        transform: Callable[[jnp.ndarray], jnp.ndarray] | None = None,
        weight: float = 1.0,
    ) -> PolisySimulator:
        self.interactions.append(
            {
                "source_domain": source_domain,
                "target_domain": target_domain,
                "source_field": source_field,
                "target_field": target_field,
                "transform": transform or (lambda x: x),
                "weight": weight,
            }
        )
        return self

    def set_objective(
        self,
        name: str,
        domain: str,
        objective_name: str,
        weight: float = 1.0,
    ) -> PolisySimulator:
        self.objectives[name] = (domain, objective_name, weight)
        return self

    def initialize(self, seed: int = 42) -> PolisySimulator:
        interactions = [CrossDomainInteraction(**item) for item in self.interactions]

        config = CompositeStateConfig(
            domains=self.domains,
            interactions=interactions,
            global_seed=seed,
        )

        self._state = CompositeState.create(config, self.registry)
        self._executor = CompositeExecutor(list(self.domains.keys()), self.registry)
        self._agent_policy = None
        self._training_config = None

        return self

    def run(
        self,
        n_steps: int = 256,
        seed: int | None = None,
        collect_trajectory: bool = True,
    ) -> SimulationResult:
        if self._state is None:
            self.initialize(seed if seed is not None else 42)

        actual_seed = seed if seed is not None else 42
        adapter = self._training_adapter()
        if self._agent_policy is not None and adapter is not None:
            config = self._training_config or TrainingConfig(
                n_episodes=1,
                steps_per_episode=1,
            )
            final_state, trajectory = adapter.run(
                self._agent_policy,
                config,
                seed=actual_seed,
                state=self._state,
                n_steps=n_steps,
            )
            if not collect_trajectory:
                trajectory = None
            if self.objectives:
                objective = CompositeObjective(self.objectives, self.registry)
                objective_values = objective.evaluate(final_state)
            else:
                objective_values = {}
            self._state = final_state
            return SimulationResult(
                final_state=final_state,
                trajectory=trajectory,
                objectives=objective_values,
                n_steps=n_steps,
            )

        rng = jax.random.PRNGKey(actual_seed)

        if collect_trajectory:
            final_state, trajectory = self._executor.run(self._state, n_steps, rng)
        else:
            state = self._state
            for _ in range(n_steps):
                rng, subkey = jax.random.split(rng)
                state = self._executor.step(state, subkey)
            final_state = state
            trajectory = None

        if self.objectives:
            objective = CompositeObjective(self.objectives, self.registry)
            objective_values = objective.evaluate(final_state)
        else:
            objective_values = {}

        self._state = final_state

        return SimulationResult(
            final_state=final_state,
            trajectory=trajectory,
            objectives=objective_values,
            n_steps=n_steps,
        )

    def train(
        self,
        n_episodes: int = 100,
        training_config: TrainingConfig | None = None,
        seed: int = 42,
        output_dir: Path | None = None,
    ) -> TrainingResult:
        if self._state is None:
            self.initialize(seed)

        adapter = self._training_adapter()
        if adapter is None:
            assessment = EconomicsTrainingAdapter.assess(self._state, self._executor)
            assert self._state is not None
            return TrainingResult(
                trained_policy=None,
                loss_history=[],
                final_state=self._state,
                status="bridge_pending",
                reason=TrainingCapabilityReason(
                    code=(
                        assessment.code
                        if assessment is not None
                        else "training_execution_adapter_missing"
                    ),
                    status="bridge_pending",
                    message=(
                        assessment.message
                        if assessment is not None
                        else "Training bridge is pending."
                    ),
                ),
            )

        if training_config is None:
            training_config = TrainingConfig(
                n_episodes=n_episodes,
                learning_rate=3e-4,
            )
        obs_dim = adapter.observation_dim(training_config)

        policy = self._agent_policy
        if policy is None:
            policy = ActorCritic(
                jax.random.PRNGKey(seed),
                obs_dim=obs_dim,
                hidden_dims=(64, 64),
                action_dim=1,
            )

        try:
            outcome = adapter.train(
                policy,
                training_config,
                seed=seed,
                output_dir=output_dir,
            )
        except TrainingBridgeError as exc:
            assert self._state is not None
            return TrainingResult(
                trained_policy=None,
                loss_history=[],
                final_state=self._state,
                status="bridge_pending",
                reason=TrainingCapabilityReason(
                    code=exc.code,
                    status="bridge_pending",
                    message=str(exc),
                ),
            )

        self._agent_policy = outcome.trained_policy
        self._training_config = replace(training_config)
        self._state = outcome.final_state

        return TrainingResult(
            trained_policy=outcome.trained_policy,
            loss_history=outcome.loss_history,
            final_state=outcome.final_state,
            artifact=outcome.artifact,
            artifact_refs=outcome.artifact_refs,
        )

    def _training_adapter(self) -> EconomicsTrainingAdapter | None:
        """Return the checked bridge for the current composite profile."""

        return EconomicsTrainingAdapter.from_composite(self._state, self._executor)

    def get_state(self) -> CompositeState:
        if self._state is None:
            raise RuntimeError("Simulation not initialized. Call initialize() first.")
        return self._state

    def set_policy(self, domain: str, policy_params: dict[str, Any]) -> PolisySimulator:
        if self._state is None:
            raise RuntimeError("Simulation not initialized")

        domain_state = self._state.get_domain(domain)

        if hasattr(domain_state, "policy"):
            policy = domain_state.policy
            updates: dict[str, Any] = {}
            for key, value in policy_params.items():
                if hasattr(policy, key):
                    updates[key] = jnp.array(value)
            if updates:
                policy = policy.replace(**updates)
                domain_state = domain_state.replace(policy=policy)
                self._state = self._state.update_domain(domain, domain_state)

        return self

    def visualize(
        self,
        domain: str | None = None,
        visualization: str = "default",
        save_path: str | None = None,
    ):
        if self._state is None:
            raise RuntimeError("No state to visualize")

        if domain is None:
            domain = list(self.domains.keys())[0]

        plugin = self.registry.get(domain)
        visualizations = plugin.get_visualizations()

        if visualizations and visualization in visualizations:
            viz_fn = visualizations[visualization]
            return viz_fn(self._state.get_domain(domain))

        from polisyos.foundry.agent_sim.visualization import TrainingVisualizer

        viz = TrainingVisualizer()
        domain_state = self._state.get_domain(domain)
        if hasattr(domain_state, "agents") and hasattr(domain_state.agents, "wealth"):
            return viz.plot_wealth_distribution(
                domain_state.agents.wealth,
                domain_state.agents.active,
                save_path=save_path,
            )
        return None


@dataclass
class SimulationResult:
    """Result of a simulation run."""

    final_state: CompositeState
    trajectory: list[CompositeState] | None
    objectives: dict[str, jnp.ndarray]
    n_steps: int

    def get_metric(self, domain: str, metric: str) -> Any:
        domain_state = self.final_state.get_domain(domain)

        if hasattr(domain_state, "aggregates"):
            if hasattr(domain_state.aggregates, metric):
                return getattr(domain_state.aggregates, metric)

        if hasattr(domain_state, "distributions"):
            if hasattr(domain_state.distributions, metric):
                return getattr(domain_state.distributions, metric)

        raise KeyError(f"Metric '{metric}' not found in domain '{domain}'")


@dataclass(frozen=True)
class TrainingCapabilityReason:
    """Typed reason for a training capability that remains unavailable."""

    code: str
    status: Literal["bridge_pending"]
    message: str


@dataclass
class TrainingResult:
    """Result of training."""

    trained_policy: ActorCritic | None
    loss_history: list[float]
    final_state: CompositeState
    status: Literal["trained", "bridge_pending"] = "trained"
    reason: TrainingCapabilityReason | None = None
    artifact: AgentPolicyArtifact[ActorCritic] | None = None
    artifact_refs: tuple[ArtifactRef, ArtifactRef] | None = None

    def plot_losses(self, save_path: str | None = None):
        from polisyos.foundry.agent_sim.visualization import TrainingVisualizer

        viz = TrainingVisualizer()
        return viz.plot_training_curves(jnp.array(self.loss_history), save_path=save_path)
