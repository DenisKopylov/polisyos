"""Bounded bridge from the Economics plugin to the canonical native trainer.

The plugin API owns ``CompositeState`` and ``CompositeExecutor`` while the
canonical actor-critic trainer owns ``GlobalState`` and ``PureExecutor``.  This
module is deliberately narrow: it admits exactly one built-in Economics
domain, with no cross-domain interactions, and makes the native temporal
mechanism the policy-controlled seam.  The remaining Economics mechanisms are
still executed by the real ``CompositeExecutor`` after that policy action.

Unsupported composite profiles are rejected by the caller as
``bridge_pending``.  There is no duck-typed fallback and no second optimizer
loop here.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

import equinox as eqx
import jax
import jax.numpy as jnp

from polisyos.core.artifacts import ArtifactRef, ArtifactStore
from polisyos.foundry.agent_sim.actor_critic import ActorCritic
from polisyos.foundry.agent_sim.artifact import (
    AgentPolicyArtifact,
    TrainingProfileDescriptor,
    _NonFiniteTrainingMetricError,
    load_policy_artifact,
    store_policy_artifact,
)
from polisyos.foundry.agent_sim.distributions import (
    _GINI_POPULATION_STATUS_METRIC,
    GiniPopulationProfile,
    _active_gini_population_schema_supported,
    _GiniPopulationStatus,
    active_gini_population_supported,
)
from polisyos.foundry.agent_sim.executor import PureExecutor
from polisyos.foundry.agent_sim.jit_training import (
    _ActiveWealthTrajectoryValidationError,
    _NativeExecutionValidationError,
    _require_exact_bool_selector,
    _selected_profile_status_supported,
)
from polisyos.foundry.agent_sim.rewards import UtilityFunction
from polisyos.foundry.agent_sim.state import AgentState, GlobalState, compute_aggregates
from polisyos.foundry.agent_sim.temporal import build_temporal_observations
from polisyos.foundry.agent_sim.temporal_mechanisms import (
    TemporalConsumptionMechanism,
    _empty_temporal_consumption_metrics,
)
from polisyos.foundry.agent_sim.training import TrainingConfig, train_actor_critic_with_artifact
from polisyos.foundry.contracts.fidelity import FidelityLevel
from polisyos.foundry.plugins.composite import (
    CompositeExecutor,
    CompositeState,
    CompositeStateConfig,
    _tree_align_to_template,
)
from polisyos.foundry.plugins.core import DomainConfig
from polisyos.foundry.plugins.economics.plugin import EconomicsPlugin
from polisyos.foundry.plugins.economics.rewards import EconomicReward
from polisyos.foundry.plugins.economics.state import (
    EconomicAgentState,
    EconomicPolicyState,
    EconomicState,
)
from polisyos.foundry.runtime.fingerprint import DeterminismTier

ECONOMICS_DOMAIN = "economics"
_ECONOMICS_MECHANISMS = (
    "labor_market",
    "taxation",
    "transfers",
    "consumption",
    "savings",
)
_ECONOMICS_MECHANISM_SET = frozenset(_ECONOMICS_MECHANISMS)
_DEFAULT_WAGE_GROWTH_RATE = 0.02


class TrainingBridgeError(ValueError):
    """A supported profile could not produce a truthful training result."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class BridgeAssessment:
    """Machine-readable admission result for the bounded bridge."""

    code: str
    message: str


@dataclass(frozen=True)
class AdapterTrainingOutcome:
    """Training output kept separate from the public plugin result type."""

    trained_policy: ActorCritic
    loss_history: list[float]
    final_state: CompositeState
    artifact: AgentPolicyArtifact[ActorCritic]
    artifact_refs: tuple[ArtifactRef, ArtifactRef] | None


def _training_gini_population_assessment(
    active: jnp.ndarray,
    wealth: jnp.ndarray,
    income: jnp.ndarray,
) -> BridgeAssessment | None:
    """Refuse active resources outside the bridge's classical-Gini profile."""

    if not bool(active_gini_population_supported(active, wealth, income)):
        return BridgeAssessment(
            "training_active_gini_profile_unsupported",
            "The selected Economics bridge materializes classical wealth and income Gini and "
            "admits only finite, nonnegative values on active rows. General signed-resource "
            "simulation remains available outside this selected training profile.",
        )
    return None


def _training_gini_profile_assessment(
    state: EconomicState,
) -> BridgeAssessment | None:
    """Check the selected EconomicState's active Gini population."""

    if type(state) is not EconomicState or type(state.agents) is not EconomicAgentState:
        return BridgeAssessment(
            "training_composite_profile_unsupported",
            "The selected Gini profile requires canonical Economics state and agent types.",
        )
    return _training_gini_population_assessment(
        state.agents.active,
        state.agents.wealth,
        state.agents.income,
    )


class _EconomicsTemporalConsumptionMechanism(TemporalConsumptionMechanism):
    """Run native policy consumption, then the real Economics transition.

    The subclass intentionally remains a ``TemporalConsumptionMechanism`` so
    the native trainer resolves the same PRNG salt for trajectory actions and
    executor actions.  It is one mechanism from the native scheduler's point
    of view, which avoids declaring a false read/write ordering between the
    policy's wealth write and the Economics mechanisms' wealth reads.
    """

    def __init__(
        self,
        *,
        actor_critic: ActorCritic,
        horizon: int,
        include_expectations: bool,
        bridge_executor: CompositeExecutor,
        bridge_config: CompositeStateConfig,
        n_agents: int,
        max_agents: int,
        wage_growth_rate: float,
    ) -> None:
        super().__init__(
            actor_critic=actor_critic,
            horizon=horizon,
            include_expectations=include_expectations,
        )
        object.__setattr__(self, "_bridge_executor", bridge_executor)
        object.__setattr__(self, "_bridge_config", bridge_config)
        object.__setattr__(self, "_n_agents", int(n_agents))
        object.__setattr__(self, "_max_agents", int(max_agents))
        object.__setattr__(self, "_wage_growth_rate", float(wage_growth_rate))

    def apply(self, state, rng_key, fidelity: FidelityLevel):
        def _status(supported: bool | jnp.ndarray) -> _GiniPopulationStatus:
            return _GiniPopulationStatus(
                profile=GiniPopulationProfile.ECONOMICS_ACTIVE_WEALTH_INCOME_V1,
                supported=jnp.asarray(supported, dtype=jnp.bool_),
            )

        def _empty_metrics() -> dict[str, jnp.ndarray | _GiniPopulationStatus]:
            return {
                **_empty_temporal_consumption_metrics(state),
                _GINI_POPULATION_STATUS_METRIC: _status(False),
            }

        def _refuse(_operand):
            return state, _empty_metrics()

        def _execute_supported(_operand):
            before = _native_to_composite(
                state,
                config=self._bridge_config,
                n_agents=self._n_agents,
                max_agents=self._max_agents,
                wage_growth_rate=self._wage_growth_rate,
            )
            policy_state, policy_metrics = TemporalConsumptionMechanism.apply(
                self,
                state,
                rng_key,
                fidelity,
            )
            policy_supported = active_gini_population_supported(
                policy_state.agents.active,
                policy_state.agents.wealth,
                policy_state.agents.income,
            )

            def _execute_policy_output(_inner_operand):
                after_policy = _native_to_composite(
                    policy_state,
                    config=self._bridge_config,
                    n_agents=self._n_agents,
                    max_agents=self._max_agents,
                    wage_growth_rate=self._wage_growth_rate,
                )
                _, bridge_key = jax.random.split(rng_key)
                after = self._bridge_executor.step(after_policy, bridge_key)

                def _accept(_final_operand):
                    native_state = _composite_to_native(after, policy_state)
                    native_state = native_state.replace(
                        agents=native_state.agents.replace(
                            utility_adjustment=_economic_reward_correction(
                                before,
                                after,
                                native_state,
                            )
                        )
                    )
                    native_state = _tree_align_to_template(
                        native_state,
                        state,
                        allow_float_dtype_change=True,
                    )
                    if native_state is None:
                        raise TrainingBridgeError(
                            "training_bridge_output_schema_unsupported",
                            "The selected Economics bridge produced a native state outside "
                            "the complete training carry shape and dtype schema.",
                        )
                    metrics = {
                        **policy_metrics,
                        _GINI_POPULATION_STATUS_METRIC: _status(True),
                    }
                    metrics = _tree_align_to_template(
                        metrics,
                        _empty_metrics(),
                        allow_float_dtype_change=True,
                    )
                    if metrics is None:
                        raise TrainingBridgeError(
                            "training_bridge_output_schema_unsupported",
                            "The selected Economics bridge produced metrics outside its "
                            "complete canonical metric schema.",
                        )
                    return native_state, metrics

                return jax.lax.cond(
                    after.gini_profile_supported,
                    _accept,
                    _refuse,
                    operand=None,
                )

            return jax.lax.cond(
                policy_supported,
                _execute_policy_output,
                _refuse,
                operand=None,
            )

        initial_supported = active_gini_population_supported(
            state.agents.active,
            state.agents.wealth,
            state.agents.income,
        )
        return jax.lax.cond(
            initial_supported,
            _execute_supported,
            _refuse,
            operand=None,
        )


def _economic_reward_correction(
    before: CompositeState,
    after: CompositeState,
    native_after: GlobalState,
) -> jnp.ndarray:
    """Make the native reward equal the admitted Economics reward exactly."""

    economic_before = before.get_domain(ECONOMICS_DOMAIN)
    economic_after = after.get_domain(ECONOMICS_DOMAIN)
    target_reward = EconomicReward().compute(economic_before, economic_after)

    agents = native_after.agents
    native_utility = UtilityFunction.crra(agents.consumption, agents.risk_aversion)
    native_wealth_bonus = 0.01 * jnp.log(jnp.maximum(agents.wealth, 1.0))
    bankruptcy_penalty = -10.0 * (agents.wealth < 0.1).astype(jnp.float32)
    native_without_adjustment = native_utility + native_wealth_bonus + bankruptcy_penalty
    return jnp.where(
        agents.active,
        target_reward - native_without_adjustment,
        jnp.zeros_like(target_reward),
    )


def _native_to_composite(
    state: GlobalState,
    *,
    config: CompositeStateConfig,
    n_agents: int,
    max_agents: int,
    wage_growth_rate: float,
) -> CompositeState:
    """Project the complete native training state into EconomicState."""

    if type(state) is not GlobalState or type(state.agents) is not AgentState:
        raise TrainingBridgeError(
            "training_native_state_schema_unsupported",
            "The selected Economics bridge requires canonical native state and agent types.",
        )
    native_agents = state.agents
    if not _active_gini_population_schema_supported(
        native_agents.active,
        native_agents.wealth,
        native_agents.income,
    ):
        raise TrainingBridgeError(
            "training_native_state_schema_unsupported",
            "The selected Economics bridge requires matching real-valued resource vectors.",
        )
    # AgentState has no wage or hours_worked fields.  The bounded temporal
    # executor leaves savings_target and education_years untouched, so they
    # provide lossless per-agent transport slots for the Economics bridge.
    economic_agents = EconomicAgentState(
        active=native_agents.active,
        age=native_agents.age,
        skill_level=native_agents.skill_level,
        wealth=native_agents.wealth,
        income=native_agents.income,
        consumption=native_agents.consumption,
        savings=native_agents.savings,
        employed=native_agents.employed,
        wage=native_agents.savings_target,
        hours_worked=native_agents.education_years,
        discount_rate=native_agents.discount_factor,
        risk_aversion=native_agents.risk_aversion,
        consumption_preference=native_agents.consumption_target,
    )
    economic_policy = EconomicPolicyState(
        tax_rate=state.policy.tax_rate,
        transfer_rate=state.policy.transfer_rate,
        interest_rate=state.policy.interest_rate,
        unemployment_benefit=native_agents.debt[0],
        minimum_wage=native_agents.information_level[0],
    )
    economic_state = EconomicState(
        agents=economic_agents,
        policy=economic_policy,
        distributions=EconomicState._compute_distributions(economic_agents),
        aggregates=EconomicState._compute_aggregates(economic_agents),
        time_step=state.time_step,
        n_agents=n_agents,
        max_agents=max_agents,
    )
    del wage_growth_rate
    return CompositeState(
        domain_states={ECONOMICS_DOMAIN: economic_state},
        time_step=state.time_step,
        config=config,
    )


def _composite_to_native(state: CompositeState, template: GlobalState) -> GlobalState:
    """Project Economics output back without losing native trainer fields."""

    economic_state = state.get_domain(ECONOMICS_DOMAIN)
    economic_agents = economic_state.agents
    native_agents = template.agents.replace(
        active=economic_agents.active,
        age=economic_agents.age,
        skill_level=economic_agents.skill_level,
        wealth=economic_agents.wealth,
        income=economic_agents.income,
        consumption=economic_agents.consumption,
        savings=economic_agents.savings,
        employed=economic_agents.employed,
        discount_factor=economic_agents.discount_rate,
        risk_aversion=economic_agents.risk_aversion,
        consumption_target=economic_agents.consumption_preference,
        education_years=economic_agents.hours_worked,
        savings_target=economic_agents.wage,
    )
    native_policy = template.policy.replace(
        tax_rate=economic_state.policy.tax_rate,
        transfer_rate=economic_state.policy.transfer_rate,
        interest_rate=economic_state.policy.interest_rate,
        expected_interest_rate=economic_state.policy.interest_rate,
    )
    native_agents = native_agents.replace(
        debt=jnp.full_like(native_agents.debt, economic_state.policy.unemployment_benefit),
        information_level=jnp.full_like(
            native_agents.information_level,
            economic_state.policy.minimum_wage,
        ),
    )
    return template.replace(
        agents=native_agents,
        policy=native_policy,
        aggregates=compute_aggregates(native_agents),
    )


class EconomicsTrainingAdapter:
    """Admit and execute the one-domain Economics training profile."""

    def __init__(self, state: CompositeState, executor: CompositeExecutor) -> None:
        self.state = state
        self.executor = executor
        self.domain_config: DomainConfig = state.config.domains[ECONOMICS_DOMAIN]
        economic_state = state.get_domain(ECONOMICS_DOMAIN)
        self.n_agents = int(economic_state.n_agents)
        self.max_agents = int(economic_state.max_agents)
        self.wage_growth_rate = float(
            self.domain_config.mechanism_configs.get("labor_market", {}).get(
                "wage_growth_rate",
                _DEFAULT_WAGE_GROWTH_RATE,
            )
        )

        bridge_domain_config = replace(
            self.domain_config,
            enabled_mechanisms=tuple(
                name for name in _ECONOMICS_MECHANISMS if name != "consumption"
            ),
        )
        bridge_domains = dict(state.config.domains)
        bridge_domains[ECONOMICS_DOMAIN] = bridge_domain_config
        self.bridge_config = replace(state.config, domains=bridge_domains)
        self.bridge_executor = CompositeExecutor(
            executor.execution_order,
            executor.registry,
            gini_population_profile=GiniPopulationProfile.ECONOMICS_ACTIVE_WEALTH_INCOME_V1,
        )

    @classmethod
    def assess(
        cls,
        state: CompositeState | None,
        executor: CompositeExecutor | None,
        *,
        require_supported_active_wealth: bool = False,
    ) -> BridgeAssessment | None:
        """Return a typed rejection reason, or ``None`` when profile is valid.

        The legacy flag name preserves existing plugin call sites. When enabled,
        it validates both active wealth and active income because this bridge's
        selected projection materializes classical Gini for both resources.
        """

        _require_exact_bool_selector(
            require_supported_active_wealth, "require_supported_active_wealth"
        )
        if type(state) is not CompositeState or type(executor) is not CompositeExecutor:
            return BridgeAssessment(
                "training_execution_adapter_missing",
                "Training requires the real CompositeState and CompositeExecutor.",
            )
        if set(state.domain_states) != {ECONOMICS_DOMAIN}:
            return BridgeAssessment(
                "training_composite_profile_unsupported",
                "The bounded bridge admits exactly one Economics domain.",
            )
        if executor.execution_order != (ECONOMICS_DOMAIN,):
            return BridgeAssessment(
                "training_composite_profile_unsupported",
                "The bounded bridge requires one Economics execution order.",
            )
        if state.config.interactions:
            return BridgeAssessment(
                "training_composite_profile_unsupported",
                "Cross-domain interactions are not admitted by this bridge.",
            )
        domain_config = state.config.domains.get(ECONOMICS_DOMAIN)
        if domain_config is None:
            return BridgeAssessment(
                "training_composite_profile_unsupported",
                "Economics domain configuration is missing.",
            )
        configured = set(domain_config.enabled_mechanisms)
        if configured and configured != _ECONOMICS_MECHANISM_SET:
            return BridgeAssessment(
                "training_composite_profile_unsupported",
                "All built-in Economics mechanisms must remain enabled for training.",
            )
        if not set(domain_config.mechanism_configs).issubset(_ECONOMICS_MECHANISM_SET):
            return BridgeAssessment(
                "training_composite_profile_unsupported",
                "Unknown Economics mechanism configuration cannot be bridged.",
            )
        economic_state = state.get_domain(ECONOMICS_DOMAIN)
        if (
            type(economic_state) is not EconomicState
            or type(economic_state.agents) is not EconomicAgentState
        ):
            return BridgeAssessment(
                "training_composite_profile_unsupported",
                "Only canonical Economics state and agent types have a checked projection.",
            )
        if type(executor.registry.get(ECONOMICS_DOMAIN)) is not EconomicsPlugin:
            return BridgeAssessment(
                "training_composite_profile_unsupported",
                "Only the built-in EconomicsPlugin has a checked projection.",
            )
        if require_supported_active_wealth:
            gini_assessment = _training_gini_profile_assessment(state.get_domain(ECONOMICS_DOMAIN))
            if gini_assessment is not None:
                return gini_assessment
        return None

    @classmethod
    def from_composite(
        cls,
        state: CompositeState | None,
        executor: CompositeExecutor | None,
        *,
        require_supported_active_wealth: bool = False,
    ) -> EconomicsTrainingAdapter | None:
        """Build the adapter only after all profile predicates pass."""

        if (
            cls.assess(
                state,
                executor,
                require_supported_active_wealth=require_supported_active_wealth,
            )
            is not None
        ):
            return None
        assert state is not None
        assert executor is not None
        return cls(state, executor)

    def to_native_state(
        self,
        *,
        seed: int,
        state: CompositeState | None = None,
    ) -> GlobalState:
        """Project a composite snapshot into the native trainer state."""

        source = state or self.state
        native = GlobalState.empty(
            n_agents=self.n_agents,
            max_agents=self.max_agents,
            seed=seed,
            simulation_horizon=self.domain_config.time_horizon,
        )
        economic_state = source.get_domain(ECONOMICS_DOMAIN)
        native_agents = native.agents.replace(
            active=economic_state.agents.active,
            age=economic_state.agents.age,
            skill_level=economic_state.agents.skill_level,
            wealth=economic_state.agents.wealth,
            income=economic_state.agents.income,
            consumption=economic_state.agents.consumption,
            savings=economic_state.agents.savings,
            employed=economic_state.agents.employed,
            discount_factor=economic_state.agents.discount_rate,
            risk_aversion=economic_state.agents.risk_aversion,
            consumption_target=economic_state.agents.consumption_preference,
            education_years=economic_state.agents.hours_worked,
            savings_target=economic_state.agents.wage,
            expected_income_growth=jnp.full_like(
                native.agents.expected_income_growth,
                self.wage_growth_rate,
            ),
            debt=jnp.full_like(native.agents.debt, economic_state.policy.unemployment_benefit),
            information_level=jnp.full_like(
                native.agents.information_level,
                economic_state.policy.minimum_wage,
            ),
        )
        native_policy = native.policy.replace(
            tax_rate=economic_state.policy.tax_rate,
            transfer_rate=economic_state.policy.transfer_rate,
            interest_rate=economic_state.policy.interest_rate,
            expected_interest_rate=economic_state.policy.interest_rate,
        )
        return native.replace(
            agents=native_agents,
            policy=native_policy,
            aggregates=compute_aggregates(native_agents),
            time_step=source.time_step,
        )

    def make_executor(self, actor: ActorCritic, config: TrainingConfig) -> PureExecutor:
        """Create the canonical PureExecutor with the checked bridge seam."""

        mechanism = _EconomicsTemporalConsumptionMechanism(
            actor_critic=actor,
            horizon=config.horizon,
            include_expectations=config.include_expectations,
            bridge_executor=self.bridge_executor,
            bridge_config=self.bridge_config,
            n_agents=self.n_agents,
            max_agents=self.max_agents,
            wage_growth_rate=self.wage_growth_rate,
        )
        return PureExecutor([mechanism], prng_config={mechanism.spec.name: 0})

    def observation_dim(self, config: TrainingConfig) -> int:
        """Return the native temporal observation width for this profile."""

        native_state = self.to_native_state(seed=0)
        observations = build_temporal_observations(
            native_state,
            horizon=config.horizon,
            include_expectations=config.include_expectations,
        )
        return int(observations.shape[-1])

    def run(
        self,
        actor: ActorCritic,
        config: TrainingConfig,
        *,
        seed: int,
        state: CompositeState | None = None,
        n_steps: int | None = None,
    ) -> tuple[CompositeState, list[CompositeState]]:
        """Run a deterministic evaluation/continuation using the trained actor."""

        source = state or self.state
        if not bool(source.gini_profile_supported):
            raise TrainingBridgeError(
                "training_active_gini_trajectory_unsupported",
                "The supplied composite state already carries a terminal Gini-profile refusal.",
            )
        initial_assessment = _training_gini_profile_assessment(source.get_domain(ECONOMICS_DOMAIN))
        if initial_assessment is not None:
            raise TrainingBridgeError(initial_assessment.code, initial_assessment.message)

        native_state = self.to_native_state(seed=seed, state=source)
        executor = self.make_executor(actor, config)
        states = [source]
        for _ in range(config.steps_per_episode if n_steps is None else int(n_steps)):
            native_state, step_metrics = executor.step(native_state, fidelity=config.fidelity)
            profile_supported = _selected_profile_status_supported(
                step_metrics,
                GiniPopulationProfile.ECONOMICS_ACTIVE_WEALTH_INCOME_V1,
            )
            if not bool(profile_supported):
                raise TrainingBridgeError(
                    "training_active_gini_trajectory_unsupported",
                    "A transition left the selected active-resource Gini profile before its "
                    "next state could be projected.",
                )
            assessment = _training_gini_population_assessment(
                native_state.agents.active,
                native_state.agents.wealth,
                native_state.agents.income,
            )
            if assessment is not None:
                raise TrainingBridgeError(
                    "training_active_gini_trajectory_unsupported",
                    assessment.message,
                )
            states.append(
                _native_to_composite(
                    native_state,
                    config=source.config,
                    n_agents=self.n_agents,
                    max_agents=self.max_agents,
                    wage_growth_rate=self.wage_growth_rate,
                )
            )
        return states[-1], states

    def train(
        self,
        actor: ActorCritic,
        config: TrainingConfig,
        *,
        seed: int,
        artifact_store: ArtifactStore | None = None,
    ) -> AdapterTrainingOutcome:
        """Run the existing native optimizer and persist/read back its artifact."""

        gini_assessment = _training_gini_profile_assessment(self.state.get_domain(ECONOMICS_DOMAIN))
        if not bool(self.state.gini_profile_supported):
            gini_assessment = BridgeAssessment(
                "training_active_gini_profile_unsupported",
                "The supplied composite state already carries a terminal Gini-profile refusal.",
            )
        if gini_assessment is not None:
            raise TrainingBridgeError(gini_assessment.code, gini_assessment.message)

        if config.utility_type != "crra":
            raise TrainingBridgeError(
                "training_utility_profile_unsupported",
                "The Economics reward bridge is admitted only for CRRA training.",
            )
        selected_profile = GiniPopulationProfile.ECONOMICS_ACTIVE_WEALTH_INCOME_V1
        if (
            config.gini_population_profile is not None
            and config.gini_population_profile is not selected_profile
        ):
            raise TrainingBridgeError(
                "training_composite_profile_unsupported",
                "The Economics adapter only admits its source-defined active wealth and income profile.",
            )
        selected_config = replace(config, gini_population_profile=selected_profile)
        if config.n_episodes <= 0 or config.steps_per_episode <= 0 or config.ppo_epochs <= 0:
            raise TrainingBridgeError(
                "training_update_not_observed",
                "Training requires positive episodes, rollout steps, and PPO epochs.",
            )

        initial_state = self.to_native_state(seed=seed)
        try:
            trained_policy, metrics, artifact = train_actor_critic_with_artifact(
                actor,
                initial_state,
                selected_config,
                make_executor=lambda current_actor: self.make_executor(
                    current_actor, selected_config
                ),
                run_id=f"plugins-{ECONOMICS_DOMAIN}-{seed}",
                tier=DeterminismTier.STRICT_CPU,
                seed=seed,
                track_active_wealth=True,
            )
        except _ActiveWealthTrajectoryValidationError as exc:
            raise TrainingBridgeError(exc.code, str(exc)) from exc
        except _NativeExecutionValidationError as exc:
            raise TrainingBridgeError(
                exc.code,
                "Native training stopped at an Equinox validation guard before a policy artifact "
                "was produced; the native guard's predicate is not classified by this bridge.",
            ) from exc
        parameter_delta = _parameter_delta(actor, trained_policy)
        action_delta = _action_delta(actor, trained_policy, initial_state, config)
        if not jnp.isfinite(parameter_delta) or float(parameter_delta) <= 0.0:
            raise TrainingBridgeError(
                "training_update_not_observed",
                "Native optimizer completed without an observable parameter update.",
            )
        if not jnp.isfinite(action_delta) or float(action_delta) <= 0.0:
            raise TrainingBridgeError(
                "training_action_effect_not_observed",
                "Native policy update did not change the next action.",
            )

        trained_policy = artifact.load_weights(actor)
        try:
            final_state, final_states = self.run(
                trained_policy,
                selected_config,
                seed=seed,
                n_steps=config.steps_per_episode,
            )
        except eqx.EquinoxRuntimeError as exc:
            raise TrainingBridgeError(
                "native_execution_validation_refused",
                "Native evaluation stopped at an Equinox validation guard before artifact "
                "persistence; the native guard's predicate is not classified by this bridge.",
            ) from exc
        self._require_supported_evaluation_trajectory(final_states, config)

        profile_descriptor = TrainingProfileDescriptor()
        if artifact.schema_version != "1.1" or artifact.training_profile != profile_descriptor:
            raise TrainingBridgeError(
                "training_artifact_profile_readback_mismatch",
                "The native artifact producer did not retain the selected Economics profile.",
            )

        artifact_refs: tuple[ArtifactRef, ArtifactRef] | None = None
        if artifact_store is not None:
            try:
                artifact_refs = store_policy_artifact(artifact_store, artifact)
            except _NonFiniteTrainingMetricError as exc:
                raise TrainingBridgeError(
                    "training_artifact_metric_nonfinite",
                    "Training artifact metrics must be finite before canonical persistence.",
                ) from exc
            self._require_training_profile_readback(
                artifact_store,
                artifact_refs[1],
                profile_descriptor,
            )
            trained_policy, _ = load_policy_artifact(
                artifact_store,
                artifact_refs[1],
                actor,
                DeterminismTier.STRICT_CPU,
                seed,
                strict=True,
            )
        losses = [float(value) for value in jnp.asarray(metrics["loss_history"])]
        return AdapterTrainingOutcome(
            trained_policy=trained_policy,
            loss_history=losses,
            final_state=final_state,
            artifact=artifact,
            artifact_refs=artifact_refs,
        )

    @staticmethod
    def _require_supported_evaluation_trajectory(
        states: list[CompositeState],
        config: TrainingConfig,
    ) -> None:
        """Validate every state in the deterministic post-training replay."""

        expected_states = int(config.steps_per_episode) + 1
        if len(states) != expected_states:
            raise TrainingBridgeError(
                "training_active_wealth_evaluation_incomplete",
                "The deterministic post-training replay did not return every requested state.",
            )
        for state in states:
            if not bool(state.gini_profile_supported):
                raise TrainingBridgeError(
                    "training_active_gini_trajectory_unsupported",
                    "The selected Gini profile already carries a terminal refusal status.",
                )
            assessment = _training_gini_profile_assessment(state.get_domain(ECONOMICS_DOMAIN))
            if assessment is not None:
                raise TrainingBridgeError(
                    "training_active_gini_trajectory_unsupported",
                    assessment.message,
                )

    @staticmethod
    def _require_training_profile_readback(
        artifact_store: ArtifactStore,
        manifest_ref: ArtifactRef,
        profile_descriptor: TrainingProfileDescriptor,
    ) -> None:
        """Verify the selected descriptor survives the typed CAS write/read path."""
        from polisyos.core.artifacts import load_core_json_artifact

        manifest = artifact_store.get_manifest(manifest_ref)
        schema = manifest.artifact_schema
        if (
            manifest.kind != "foundry.agent_policy_manifest"
            or manifest.media_type != "application/json"
            or schema is None
            or schema.name != "polisyos.foundry.AgentPolicyArtifact"
            or schema.version != "1.1"
        ):
            raise TrainingBridgeError(
                "training_artifact_profile_readback_mismatch",
                "The stored Economics policy manifest did not retain its selected profile schema.",
            )
        payload = load_core_json_artifact(artifact_store, manifest_ref)
        if (
            not isinstance(payload, dict)
            or payload.get("schema_version") != "1.1"
            or payload.get("training_profile") != profile_descriptor.to_manifest_dict()
        ):
            raise TrainingBridgeError(
                "training_artifact_profile_readback_mismatch",
                "The stored Economics policy payload did not retain its selected profile descriptor.",
            )


def _parameter_delta(before: ActorCritic, after: ActorCritic) -> jnp.ndarray:
    """Sum absolute changes over all trainable actor parameters."""

    before_params = eqx.filter(before, eqx.is_inexact_array)
    after_params = eqx.filter(after, eqx.is_inexact_array)
    deltas = jax.tree_util.tree_leaves(
        jax.tree_util.tree_map(
            lambda left, right: jnp.sum(jnp.abs(left - right)),
            before_params,
            after_params,
        )
    )
    return jnp.sum(jnp.stack(deltas))


def _action_delta(
    before: ActorCritic,
    after: ActorCritic,
    initial_state: GlobalState,
    config: TrainingConfig,
) -> jnp.ndarray:
    """Measure whether the learned actor changes the next native action."""

    obs = build_temporal_observations(
        initial_state,
        horizon=config.horizon,
        include_expectations=config.include_expectations,
    )
    before_action, _ = before(obs, deterministic=True)
    after_action, _ = after(obs, deterministic=True)
    return jnp.max(jnp.abs(after_action - before_action))


__all__ = [
    "AdapterTrainingOutcome",
    "BridgeAssessment",
    "EconomicsTrainingAdapter",
    "TrainingBridgeError",
]
