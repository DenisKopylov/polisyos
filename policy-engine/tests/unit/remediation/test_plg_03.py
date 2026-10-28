"""PLG-03 witnesses for the bounded Economics-to-native training bridge."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
from dataclasses import replace as dataclass_replace
from decimal import Decimal
from pathlib import Path

import equinox as eqx
import jax
import jax.numpy as jnp
import optax
import pytest

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.ownership import ArtifactOwnershipError
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.security.tenant_context import tenant_scope
from polisyos.foundry.agent_sim import (
    ActorCritic,
    TrainingConfig,
    active_gini_population_supported,
    build_temporal_observations,
)
from polisyos.foundry.agent_sim.artifact import (
    AgentPolicyArtifact,
    TrainingProfileDescriptor,
    load_policy_artifact,
    store_policy_artifact,
)
from polisyos.foundry.agent_sim.executor import PureExecutor
from polisyos.foundry.agent_sim.mechanism import Mechanism, MechanismSpec
from polisyos.foundry.agent_sim.state import GlobalState
from polisyos.foundry.plugins.api import PolisySimulator, TrainingResult
from polisyos.foundry.plugins.cli import cmd_train
from polisyos.foundry.plugins.composite import CompositeState
from polisyos.foundry.plugins.core import DomainConfig, PluginRegistry
from polisyos.foundry.plugins.economics import EconomicsPlugin
from polisyos.foundry.plugins.economics.mechanisms import TaxationMechanism
from polisyos.foundry.plugins.training_adapter import (
    EconomicsTrainingAdapter,
    TrainingBridgeError,
)
from polisyos.foundry.runtime.fingerprint import DeterminismTier, EnvironmentFingerprint


@pytest.fixture
def simulator() -> PolisySimulator:
    """Build the only composite profile admitted by PLG-03."""

    registry = PluginRegistry()
    registry.clear()
    registry.register(EconomicsPlugin())
    return PolisySimulator(registry, auto_discover=False).add_domain(
        "economics",
        DomainConfig(n_agents=10, max_agents=10),
    )


def _small_config() -> TrainingConfig:
    return TrainingConfig(
        n_episodes=1,
        steps_per_episode=2,
        horizon=12,
        ppo_epochs=1,
        learning_rate=1e-2,
    )


def _assert_tree_schema_matches(candidate: object, template: object) -> None:
    """Ask JAX's real conditional tracer to compare the complete output carries."""
    jax.eval_shape(
        lambda predicate: jax.lax.cond(
            predicate,
            lambda _: candidate,
            lambda _: template,
            operand=None,
        ),
        jnp.asarray(True, dtype=jnp.bool_),
    )


def _set_supported_nonnegative_active_wealth(simulator: PolisySimulator, wealth: float) -> None:
    """Set active wealth to a supported profile with enough stock for tax debits."""

    state = simulator.get_state()
    domain = state.get_domain("economics")
    agents = domain.agents
    active_wealth = jnp.full_like(agents.wealth, wealth)
    agents = agents.replace(wealth=jnp.where(agents.active, active_wealth, agents.wealth))
    domain = domain.replace(agents=agents).update_aggregates()
    assert domain.validate()
    simulator._state = state.update_domain("economics", domain)


def test_typed_economics_profile_widens_legacy_wealth_monitor_without_redefining_it() -> None:
    """The selected Economics profile checks income while the generic flag remains wealth-only."""
    from polisyos.foundry.agent_sim.distributions import (
        GiniPopulationProfile,
        _GiniPopulationStatus,
    )
    from polisyos.foundry.agent_sim.jit_training import (
        _active_wealth_supported,
        _selected_profile_status_supported,
        _tracked_population_supported,
    )
    from polisyos.foundry.agent_sim.training import train_actor_critic

    state = GlobalState.empty(2, seed=29)
    active = state.agents.active
    negative_income = state.replace(
        agents=state.agents.replace(
            income=jnp.where(active, -1.0, state.agents.income),
        ),
    )
    profile = GiniPopulationProfile.ECONOMICS_ACTIVE_WEALTH_INCOME_V1

    assert bool(_active_wealth_supported(negative_income))
    assert not bool(_tracked_population_supported(negative_income, profile))
    assert not bool(_selected_profile_status_supported({}, profile))
    assert not bool(
        _selected_profile_status_supported(
            {"temporal_consumption/active_gini_population_status": True},
            profile,
        )
    )

    valid_status = _GiniPopulationStatus(profile=profile, supported=jnp.asarray(True))
    metrics = {"temporal_consumption/active_gini_population_status": valid_status}
    assert bool(_selected_profile_status_supported(metrics, profile))
    assert not bool(_selected_profile_status_supported(metrics, None))
    # A true transport status does not override the independently recomputed state.
    assert not bool(_tracked_population_supported(negative_income, profile))

    inactive_nan = state.replace(
        agents=state.agents.replace(
            active=active.at[-1].set(False),
            income=state.agents.income.at[-1].set(jnp.nan),
        ),
    )
    assert bool(_tracked_population_supported(inactive_nan, profile))
    with pytest.raises(ValueError, match="selected Gini profiles require train_actor_critic_jit"):
        train_actor_critic(None, None, TrainingConfig(gini_population_profile=profile))


def _tree_delta(before: object, after: object) -> float:
    leaves = jax.tree_util.tree_leaves(
        jax.tree_util.tree_map(
            lambda left, right: jnp.sum(jnp.abs(left - right)),
            before,
            after,
        )
    )
    return float(jnp.sum(jnp.stack(leaves)))


def test_native_projection_preserves_economics_wage_and_hours(
    simulator: PolisySimulator,
) -> None:
    """The bounded bridge carries Economics-only fields through native state slots."""

    simulator.initialize(seed=7)
    adapter = EconomicsTrainingAdapter.from_composite(
        simulator.get_state(),
        simulator._executor,
    )
    assert adapter is not None

    native_state = adapter.to_native_state(seed=7)
    economic_state = simulator.get_state().get_domain("economics")

    assert jnp.array_equal(native_state.agents.savings_target, economic_state.agents.wage)
    assert jnp.array_equal(native_state.agents.education_years, economic_state.agents.hours_worked)


@pytest.mark.parametrize("x64_enabled", [False, True], ids=["x64-off", "x64-on"])
def test_economics_conditional_outputs_match_complete_native_pytree_abi(
    simulator: PolisySimulator,
    x64_enabled: bool,
) -> None:
    """Accepted and refused selected transitions preserve the actual native tree schema."""
    with jax.enable_x64(x64_enabled):
        simulator.initialize(seed=67)
        _set_supported_nonnegative_active_wealth(simulator, 1_000_000.0)
        assert simulator._executor is not None
        adapter = EconomicsTrainingAdapter.from_composite(
            simulator.get_state(),
            simulator._executor,
        )
        assert adapter is not None
        native_state = adapter.to_native_state(seed=67)
        if x64_enabled:
            native_state = native_state.replace(
                agents=native_state.agents.replace(
                    wealth=native_state.agents.wealth.astype(jnp.float64),
                ),
            )
        observations = build_temporal_observations(
            native_state,
            horizon=_small_config().horizon,
            include_expectations=_small_config().include_expectations,
        )
        actor = ActorCritic(
            jax.random.PRNGKey(67),
            obs_dim=observations.shape[-1],
            hidden_dims=(8, 4),
            action_dim=1,
        )
        executor = adapter.make_executor(actor, _small_config())
        supported_state, supported_metrics = executor.step(
            native_state,
            fidelity=_small_config().fidelity,
        )
        invalid_state = native_state.replace(
            agents=native_state.agents.replace(
                income=jnp.where(
                    native_state.agents.active,
                    jnp.asarray(jnp.nan, dtype=native_state.agents.income.dtype),
                    native_state.agents.income,
                ),
            ),
        )
        refused_state, refused_metrics = executor.step(
            invalid_state,
            fidelity=_small_config().fidelity,
        )

        _assert_tree_schema_matches(supported_state, native_state)
        _assert_tree_schema_matches(refused_state, invalid_state)
        _assert_tree_schema_matches(refused_metrics, supported_metrics)
        status_key = "temporal_consumption/active_gini_population_status"
        assert bool(supported_metrics[status_key].supported)
        assert bool(
            active_gini_population_supported(
                supported_state.agents.active,
                supported_state.agents.wealth,
                supported_state.agents.income,
            )
        )
        assert not bool(refused_metrics[status_key].supported)
        for key, value in refused_metrics.items():
            if key != status_key:
                assert jnp.all(value == 0.0)
        assert jnp.all(jnp.isnan(refused_state.agents.income[invalid_state.agents.active]))


def test_economics_training_updates_policy_and_produces_readable_artifact(
    simulator: PolisySimulator,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The bridge must use the native optimizer and expose a learned artifact."""

    simulator.initialize(seed=7)
    _set_supported_nonnegative_active_wealth(simulator, 1_000_000.0)
    initial_composite = simulator.get_state()
    config = _small_config()
    adapter = EconomicsTrainingAdapter.from_composite(
        simulator.get_state(),
        simulator._executor,
    )
    assert adapter is not None
    initial_state = adapter.to_native_state(seed=7)
    obs = build_temporal_observations(initial_state, horizon=12, include_expectations=True)
    initial_policy = ActorCritic(
        jax.random.PRNGKey(7),
        obs_dim=obs.shape[-1],
        hidden_dims=(64, 64),
        action_dim=1,
    )

    # Observe real, pre-clipping gradients at the existing optimizer boundary.
    # The wrapper delegates the actual update unchanged; the same-seed replay
    # below runs without it and checks that the observer did not alter results.
    gradient_norms: list[float] = []
    native_chain = optax.chain

    def observing_chain(*transforms):
        native_optimizer = native_chain(*transforms)

        def observing_update(gradients, state, params=None):
            jax.debug.callback(
                lambda value: gradient_norms.append(float(value)),
                optax.global_norm(gradients),
                ordered=True,
            )
            return native_optimizer.update(gradients, state, params)

        return optax.GradientTransformation(native_optimizer.init, observing_update)

    with monkeypatch.context() as observing:
        observing.setattr(optax, "chain", observing_chain)
        result = simulator.train(
            n_episodes=config.n_episodes,
            training_config=config,
            seed=7,
            output_dir=tmp_path / "training-output",
        )

    assert gradient_norms, "the executing native optimizer did not emit a raw gradient"
    assert all(math.isfinite(value) for value in gradient_norms)
    assert any(value > 0.0 for value in gradient_norms)
    assert isinstance(result, TrainingResult)
    assert result.status == "trained"
    assert result.trained_policy is not None
    assert result.artifact is not None
    assert result.artifact_refs is not None
    assert result.artifact.schema_version == "1.1"
    assert result.artifact.training_profile == TrainingProfileDescriptor()
    assert len(result.loss_history) == config.n_episodes
    loss_values = jnp.asarray(result.loss_history)
    assert bool(jnp.all(jnp.isfinite(loss_values)))
    assert _tree_delta(initial_policy, result.trained_policy) > 0.0
    assert result.artifact.metrics.training_steps == config.n_episodes * config.steps_per_episode
    assert result.artifact.metrics.total_episodes == config.n_episodes
    assert result.artifact.metrics.final_loss == float(loss_values[-1])
    assert result.artifact.metrics.best_loss == float(jnp.min(loss_values))
    assert result.artifact.metrics.learning_rate == config.learning_rate
    assert result.artifact.metrics.ppo_epochs == config.ppo_epochs

    manifest_payload = from_canonical_bytes(
        FileSystemCAS(tmp_path / "training-output" / "artifacts").get_bytes(
            result.artifact_refs[1].artifact_id
        )
    )
    assert isinstance(manifest_payload, dict)
    assert isinstance(manifest_payload["metrics"]["final_loss"], Decimal)
    assert manifest_payload["schema_version"] == "1.1"
    assert manifest_payload["training_profile"] == TrainingProfileDescriptor().to_manifest_dict()
    manifest_metrics = manifest_payload["metrics"]
    assert manifest_metrics["training_steps"] == config.n_episodes * config.steps_per_episode
    assert manifest_metrics["total_episodes"] == config.n_episodes
    assert manifest_metrics["final_loss"] == Decimal(str(result.artifact.metrics.final_loss))
    assert manifest_metrics["best_loss"] == Decimal(str(result.artifact.metrics.best_loss))
    assert manifest_metrics["learning_rate"] == Decimal(str(config.learning_rate))
    assert manifest_metrics["ppo_epochs"] == config.ppo_epochs
    manifest = FileSystemCAS(tmp_path / "training-output" / "artifacts").get_manifest(
        result.artifact_refs[1]
    )
    assert manifest.kind == "foundry.agent_policy_manifest"
    assert manifest.media_type == "application/json"
    assert manifest.artifact_schema is not None
    assert manifest.artifact_schema.name == "polisyos.foundry.AgentPolicyArtifact"
    assert manifest.artifact_schema.version == "1.1"
    assert isinstance(manifest_payload["metrics"]["learning_rate"], Decimal)

    initial_action, _ = initial_policy(obs, deterministic=True)

    # Reopen the CAS and reconstruct the model independently rather than using
    # either policy object retained by the producer.  This is the consumer
    # oracle: a success-shaped result cannot satisfy it with in-memory weights.
    fresh_store = FileSystemCAS(tmp_path / "training-output" / "artifacts")
    fresh_skeleton = ActorCritic(
        jax.random.PRNGKey(7),
        obs_dim=obs.shape[-1],
        hidden_dims=(64, 64),
        action_dim=1,
    )
    fresh_policy, fresh_warnings = load_policy_artifact(
        fresh_store,
        result.artifact_refs[1],
        fresh_skeleton,
        DeterminismTier.STRICT_CPU,
        7,
        strict=True,
    )
    assert fresh_warnings == []
    assert _tree_delta(fresh_skeleton, fresh_policy) > 0.0
    assert _tree_delta(result.trained_policy, fresh_policy) == 0.0

    trained_action, _ = fresh_policy(obs, deterministic=True)
    assert bool(jnp.all(jnp.isfinite(trained_action)))
    assert float(jnp.max(jnp.abs(trained_action - initial_action))) > 0.0

    # Exercise the real policy-bearing executor at the same state.  The
    # persisted learned action must be consumed by a real next transition.
    initial_next, _ = adapter.make_executor(initial_policy, config).step(initial_state)
    learned_next, _ = adapter.make_executor(fresh_policy, config).step(initial_state)
    assert (
        float(jnp.max(jnp.abs(initial_next.agents.consumption - learned_next.agents.consumption)))
        > 0.0
    )
    assert result.artifact.load_weights(result.trained_policy) is not None

    # The persisted actor must be consumed by the public continuation at an
    # actual post-training state.  Compare against the native executor directly
    # from that same state/key, then against the untrained actor on that state.
    final_state = simulator.get_state()
    assert int(final_state.time_step) > int(initial_composite.time_step)
    later_native = adapter.to_native_state(seed=7, state=final_state)
    later_obs = build_temporal_observations(
        later_native,
        horizon=config.horizon,
        include_expectations=config.include_expectations,
    )
    old_later_action, _ = initial_policy(later_obs, deterministic=True)
    new_later_action, _ = fresh_policy(later_obs, deterministic=True)
    assert float(jnp.max(jnp.abs(new_later_action - old_later_action))) > 0.0
    expected_learned, _ = adapter.make_executor(fresh_policy, config).step(
        later_native, fidelity=config.fidelity
    )
    expected_initial, _ = adapter.make_executor(initial_policy, config).step(
        later_native, fidelity=config.fidelity
    )
    assert (
        float(
            jnp.max(
                jnp.abs(expected_learned.agents.consumption - expected_initial.agents.consumption)
            )
        )
        > 0.0
    )

    # A changed seed must affect the stochastic path, with every non-RNG
    # native-state leaf, source state, actor, and configuration held fixed.
    alternate_native = adapter.to_native_state(seed=19, state=final_state)
    first_leaves, first_structure = jax.tree_util.tree_flatten(
        later_native.replace(rng_key=alternate_native.rng_key)
    )
    alternate_leaves, alternate_structure = jax.tree_util.tree_flatten(alternate_native)
    assert first_structure == alternate_structure
    for first_leaf, alternate_leaf in zip(first_leaves, alternate_leaves, strict=True):
        assert bool(jnp.array_equal(jnp.asarray(first_leaf), jnp.asarray(alternate_leaf)))
    assert not bool(jnp.array_equal(later_native.rng_key, alternate_native.rng_key))

    from polisyos.foundry.plugins import training_adapter as training_adapter_module

    cas_root = tmp_path / "training-output" / "artifacts"

    def cas_snapshot() -> dict[str, str]:
        return {
            str(path.relative_to(cas_root)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in cas_root.rglob("*")
            if path.is_file()
        }

    def unexpected_training_or_store(*_args, **_kwargs):
        raise AssertionError("public evaluation invoked the training or policy-storage owner")

    before_evaluation = cas_snapshot()
    with monkeypatch.context() as evaluating:
        evaluating.setattr(
            training_adapter_module,
            "train_actor_critic_with_artifact",
            unexpected_training_or_store,
        )
        evaluating.setattr(
            training_adapter_module, "store_policy_artifact", unexpected_training_or_store
        )
        simulator._state = final_state
        simulator._agent_policy = fresh_policy
        learned_run = simulator.run(n_steps=1, seed=7)
        assert simulator._agent_policy is fresh_policy
        assert _tree_delta(result.trained_policy, simulator._agent_policy) == 0.0

        simulator._state = final_state
        simulator._agent_policy = initial_policy
        initial_run = simulator.run(n_steps=1, seed=7)

        simulator._state = final_state
        simulator._agent_policy = fresh_policy
        repeat_run = simulator.run(n_steps=1, seed=7)

        simulator._state = final_state
        simulator._agent_policy = fresh_policy
        changed_seed_run = simulator.run(n_steps=1, seed=19)

    assert cas_snapshot() == before_evaluation
    learned_consumption = learned_run.final_state.get_domain("economics").agents.consumption
    initial_consumption = initial_run.final_state.get_domain("economics").agents.consumption
    repeat_consumption = repeat_run.final_state.get_domain("economics").agents.consumption
    changed_seed_consumption = changed_seed_run.final_state.get_domain(
        "economics"
    ).agents.consumption
    assert int(learned_run.final_state.time_step) == int(final_state.time_step) + 1
    assert int(initial_run.final_state.time_step) == int(final_state.time_step) + 1
    assert bool(jnp.array_equal(learned_consumption, expected_learned.agents.consumption))
    assert bool(jnp.array_equal(initial_consumption, expected_initial.agents.consumption))
    assert float(jnp.max(jnp.abs(learned_consumption - initial_consumption))) > 0.0
    assert bool(jnp.array_equal(learned_consumption, repeat_consumption))
    assert float(jnp.max(jnp.abs(learned_consumption - changed_seed_consumption))) > 0.0

    # A fresh reader must not silently reuse the producer's in-memory actor if
    # the separately persisted weight blob is missing in an isolated CAS copy.
    copied_cas_root = tmp_path / "missing-weights-cas"
    shutil.copytree(cas_root, copied_cas_root)
    weight_id = result.artifact_refs[0].artifact_id
    copied_weight_blobs = list(copied_cas_root.rglob(f"{weight_id.hex}.blob"))
    assert len(copied_weight_blobs) == 1
    copied_weight_blobs[0].unlink()
    with pytest.raises(FileNotFoundError):
        load_policy_artifact(
            FileSystemCAS(copied_cas_root),
            result.artifact_refs[1],
            fresh_skeleton,
            DeterminismTier.STRICT_CPU,
            7,
            strict=True,
        )
    intact_policy, _ = load_policy_artifact(
        FileSystemCAS(cas_root),
        result.artifact_refs[1],
        fresh_skeleton,
        DeterminismTier.STRICT_CPU,
        7,
        strict=True,
    )
    assert _tree_delta(fresh_policy, intact_policy) == 0.0

    simulator.initialize(seed=7)
    assert simulator._agent_policy is None
    assert simulator._training_config is None
    _set_supported_nonnegative_active_wealth(simulator, 1_000_000.0)
    reset_domain = simulator.get_state().get_domain("economics")
    original_domain = initial_composite.get_domain("economics")
    assert int(simulator.get_state().time_step) == int(initial_composite.time_step)
    for field in ("active", "age", "income", "wealth", "wage"):
        assert bool(
            jnp.array_equal(
                getattr(reset_domain.agents, field), getattr(original_domain.agents, field)
            )
        )
    reset_result = simulator.train(
        n_episodes=config.n_episodes,
        training_config=config,
        seed=7,
    )
    assert reset_result.status == "trained"
    assert reset_result.trained_policy is not None
    assert _tree_delta(result.trained_policy, reset_result.trained_policy) == 0.0
    assert reset_result.loss_history == result.loss_history
    assert simulator.get_state() is reset_result.final_state

    reset_step = int(reset_result.final_state.time_step)
    continuation = simulator.run(n_steps=1, seed=7)
    assert continuation.n_steps == 1
    assert int(continuation.final_state.time_step) > reset_step
    assert simulator.get_state() is continuation.final_state
    assert simulator._agent_policy is reset_result.trained_policy


@pytest.mark.parametrize("signal", ["parameters", "action"], ids=["parameters", "action"])
def test_fresh_policy_independent_oracle_rejects_success_shaped_no_update(
    simulator: PolisySimulator,
    tmp_path: Path,
    signal: str,
) -> None:
    """Each selector detects an unchanged persisted actor before checking status."""
    simulator.initialize(seed=7)
    _set_supported_nonnegative_active_wealth(simulator, 1_000_000.0)
    config = _small_config()
    adapter = EconomicsTrainingAdapter.from_composite(simulator.get_state(), simulator._executor)
    assert adapter is not None
    initial_state = adapter.to_native_state(seed=7)
    initial_obs = build_temporal_observations(
        initial_state,
        horizon=config.horizon,
        include_expectations=config.include_expectations,
    )
    initial_actor = ActorCritic(
        jax.random.PRNGKey(7),
        obs_dim=initial_obs.shape[-1],
        hidden_dims=(64, 64),
        action_dim=1,
    )
    cas_root = tmp_path / "independent-policy-cas"
    result = simulator.train(
        n_episodes=config.n_episodes,
        training_config=config,
        seed=7,
        artifact_store=FileSystemCAS(cas_root),
    )
    # Required to reach the actual fresh-reader assertion; status is checked
    # only after the independent numerical signal has been evaluated.
    assert result.artifact_refs is not None, "the fresh-reader branch was not reached"
    fresh_actor, warnings = load_policy_artifact(
        FileSystemCAS(cas_root),
        result.artifact_refs[1],
        initial_actor,
        DeterminismTier.STRICT_CPU,
        7,
        strict=True,
    )
    assert warnings == []
    if signal == "parameters":
        assert _tree_delta(initial_actor, fresh_actor) > 0.0, "fresh parameters did not change"
    else:
        later_state = adapter.to_native_state(seed=7, state=result.final_state)
        assert int(later_state.time_step) > int(initial_state.time_step)
        later_obs = build_temporal_observations(
            later_state,
            horizon=config.horizon,
            include_expectations=config.include_expectations,
        )
        old_action, _ = initial_actor(later_obs, deterministic=True)
        new_action, _ = fresh_actor(later_obs, deterministic=True)
        assert bool(jnp.all(jnp.isfinite(new_action)))
        assert float(jnp.max(jnp.abs(new_action - old_action))) > 0.0, "fresh action did not change"
    assert result.status == "trained"


def test_economics_training_supports_nonnegative_active_wealth_profile(
    simulator: PolisySimulator,
    tmp_path: Path,
) -> None:
    """A valid nonnegative active-wealth profile completes the real bridge path."""

    simulator.initialize(seed=7)
    _set_supported_nonnegative_active_wealth(simulator, 1_000_000.0)
    initial_domain = simulator.get_state().get_domain("economics")
    assert jnp.all(initial_domain.agents.wealth[initial_domain.agents.active] >= 0.0)

    result = simulator.train(
        n_episodes=1,
        training_config=_small_config(),
        seed=7,
        output_dir=tmp_path / "nonnegative-training-output",
    )

    assert isinstance(result, TrainingResult)
    assert result.status == "trained"
    assert result.trained_policy is not None
    assert result.artifact is not None
    assert result.artifact_refs is not None
    assert result.loss_history
    assert all(jnp.isfinite(jnp.asarray(result.loss_history)))

    manifest_payload = from_canonical_bytes(
        FileSystemCAS(tmp_path / "nonnegative-training-output" / "artifacts").get_bytes(
            result.artifact_refs[1].artifact_id
        )
    )
    assert isinstance(manifest_payload, dict)
    assert isinstance(manifest_payload["metrics"]["final_loss"], Decimal)

    final_domain = result.final_state.get_domain("economics")
    active = final_domain.agents.active
    assert jnp.all(final_domain.agents.wealth[active] >= 0.0)
    assert jnp.isfinite(final_domain.distributions.gini_wealth)


def test_zero_effective_gradient_is_typed_pending_without_policy_or_cas_persistence(
    simulator: PolisySimulator,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Gradient clipping can yield no-op weights, but the bridge must not call them trained."""

    from polisyos.foundry.plugins import training_adapter as training_adapter_module

    simulator.initialize(seed=19)
    _set_supported_nonnegative_active_wealth(simulator, 1_000_000.0)
    source_state = simulator.get_state()
    config = dataclass_replace(_small_config(), max_grad_norm=0.0)
    native_outputs: list[tuple[object, object, dict[str, object], AgentPolicyArtifact]] = []
    train_native = training_adapter_module.train_actor_critic_with_artifact

    def capture_native_output(*args, **kwargs):
        outcome = train_native(*args, **kwargs)
        native_outputs.append((args[0], outcome[0], outcome[1], outcome[2]))
        return outcome

    monkeypatch.setattr(
        training_adapter_module,
        "train_actor_critic_with_artifact",
        capture_native_output,
    )
    cas_root = tmp_path / "zero-gradient-cas"
    store = FileSystemCAS(cas_root)
    result = simulator.train(
        n_episodes=config.n_episodes,
        training_config=config,
        seed=19,
        artifact_store=store,
    )

    assert len(native_outputs) == 1
    initial_policy, optimizer_policy, native_metrics, native_artifact = native_outputs[0]
    assert _tree_delta(initial_policy, optimizer_policy) == 0.0
    assert bool(jnp.all(jnp.isfinite(jnp.asarray(native_metrics["loss_history"]))))
    assert native_artifact.schema_version == "1.1"
    assert native_artifact.training_profile == TrainingProfileDescriptor()
    assert result.status == "bridge_pending"
    assert result.reason is not None
    assert result.reason.code == "training_update_not_observed"
    assert result.trained_policy is None
    assert result.artifact is None
    assert result.artifact_refs is None
    assert result.loss_history == []
    assert simulator.get_state() is source_state
    assert simulator._agent_policy is None
    assert not list(cas_root.rglob("*.blob"))
    assert not list(cas_root.rglob("*.manifest.json"))


def test_policy_artifact_reads_legacy_schema_and_rejects_profile_fallbacks() -> None:
    """Legacy 1.0 remains readable while malformed 1.1/1.0 descriptors fail closed."""

    legacy = AgentPolicyArtifact.from_manifest_dict(
        {"schema_version": "1.0", "weights_hash": "legacy-weights"},
        weights_bytes=b"legacy",
    )
    assert legacy.schema_version == "1.0"
    assert legacy.training_profile is None

    with pytest.raises(TypeError, match="source-defined TrainingProfileDescriptor"):
        dataclass_replace(
            legacy,
            schema_version="1.1",
            training_profile={"profile_id": "caller-supplied"},
        )

    with pytest.raises(ValueError, match="require a training profile"):
        AgentPolicyArtifact.from_manifest_dict(
            {"schema_version": "1.1", "weights_hash": "selected-weights"},
            weights_bytes=b"selected",
        )

    with pytest.raises(ValueError, match="Unsupported agent policy training profile"):
        AgentPolicyArtifact.from_manifest_dict(
            {
                "schema_version": "1.1",
                "weights_hash": "selected-weights",
                "training_profile": {"profile_id": "caller-supplied"},
            },
            weights_bytes=b"selected",
        )

    with pytest.raises(ValueError, match="cannot carry a training profile"):
        AgentPolicyArtifact.from_manifest_dict(
            {
                "schema_version": "1.0",
                "weights_hash": "legacy-weights",
                "training_profile": TrainingProfileDescriptor().to_manifest_dict(),
            },
            weights_bytes=b"legacy",
        )


def test_profileless_schema_1_0_artifact_round_trips_through_cas_loader(
    tmp_path: Path,
) -> None:
    """The stored legacy schema loads its weights through the production CAS reader."""

    seed = 23
    actor = ActorCritic(
        jax.random.PRNGKey(seed),
        obs_dim=7,
        hidden_dims=(8,),
        action_dim=1,
    )
    fingerprint = EnvironmentFingerprint.capture(DeterminismTier.STRICT_CPU, seed=seed)
    legacy_artifact = AgentPolicyArtifact.from_trained_policy(
        actor,
        run_id="legacy-cas-roundtrip",
        steps=4,
        loss=0.25,
        fingerprint=fingerprint,
        best_loss=0.20,
        extended_metrics={"total_episodes": 2, "learning_rate": 1e-2, "ppo_epochs": 1},
    )
    assert legacy_artifact.schema_version == "1.0"
    assert legacy_artifact.training_profile is None

    store = FileSystemCAS(tmp_path / "legacy-cas")
    weights_ref, manifest_ref = store_policy_artifact(store, legacy_artifact)
    assert store.has(weights_ref)
    assert store.has(manifest_ref)
    cas_manifest = store.get_manifest(manifest_ref)
    assert cas_manifest.kind == "foundry.agent_policy_manifest"
    assert cas_manifest.artifact_schema is not None
    assert cas_manifest.artifact_schema.name == "polisyos.foundry.AgentPolicyArtifact"
    assert cas_manifest.artifact_schema.version == "1.0"
    stored_payload = from_canonical_bytes(store.get_bytes(manifest_ref))
    assert isinstance(stored_payload, dict)
    assert stored_payload["schema_version"] == "1.0"
    assert "training_profile" not in stored_payload

    skeleton = ActorCritic(
        jax.random.PRNGKey(seed + 1),
        obs_dim=7,
        hidden_dims=(8,),
        action_dim=1,
    )
    loaded, _ = load_policy_artifact(
        store,
        manifest_ref,
        skeleton,
        DeterminismTier.STRICT_CPU,
        seed,
        strict=True,
    )
    assert _tree_delta(actor, loaded) == 0.0


def test_signed_active_wealth_is_typed_before_training_or_output_creation(
    simulator: PolisySimulator,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A real signed-tax input declines before observation, training, or CAS output."""

    from polisyos.foundry.plugins import api as api_module
    from polisyos.foundry.plugins import training_adapter as training_adapter_module

    simulator.initialize(seed=31)
    assert simulator._executor is not None
    valid_adapter = EconomicsTrainingAdapter.from_composite(
        simulator.get_state(),
        simulator._executor,
    )
    assert valid_adapter is not None
    config = _small_config()
    obs_dim = valid_adapter.observation_dim(config)
    actor = ActorCritic(jax.random.PRNGKey(31), obs_dim=obs_dim, hidden_dims=(8, 4))

    state = simulator.get_state()
    domain = state.get_domain("economics")
    income = jnp.zeros_like(domain.agents.income)
    income = income.at[0].set(25_000.0).at[1].set(50_000.0)
    agents = domain.agents.replace(
        active=jnp.ones_like(domain.agents.active),
        income=income,
        wealth=jnp.zeros_like(domain.agents.wealth),
    )
    taxed = TaxationMechanism().apply(domain.replace(agents=agents))
    assert jnp.array_equal(taxed.agents.wealth[:2], jnp.asarray([-3_250.0, -7_700.0]))
    assert not taxed.validate()
    simulator._state = state.update_domain("economics", taxed)

    training_calls: list[str] = []
    observation_calls: list[str] = []
    store_build_calls: list[str] = []

    def unexpected_native_training(*args, **kwargs):
        del args, kwargs
        training_calls.append("called")
        raise AssertionError("unsupported wealth reached the native trainer")

    def unexpected_observation_projection(*args, **kwargs):
        del args, kwargs
        observation_calls.append("called")
        raise AssertionError("unsupported wealth reached observation projection")

    def unexpected_store_build(*args, **kwargs):
        del args, kwargs
        store_build_calls.append("called")
        raise AssertionError("unsupported wealth created a training store")

    monkeypatch.setattr(
        training_adapter_module,
        "train_actor_critic_with_artifact",
        unexpected_native_training,
    )
    monkeypatch.setattr(
        EconomicsTrainingAdapter,
        "observation_dim",
        unexpected_observation_projection,
    )
    monkeypatch.setattr(api_module, "build_artifact_store", unexpected_store_build)
    output_dir = tmp_path / "signed-wealth-training"
    result = simulator.train(
        training_config=config,
        seed=31,
        output_dir=output_dir,
    )

    assert result.status == "bridge_pending"
    assert result.reason is not None
    assert result.reason.code == "training_active_gini_profile_unsupported"
    assert result.trained_policy is None
    assert result.artifact is None
    assert result.artifact_refs is None
    assert result.final_state is simulator._state
    assert training_calls == []
    assert observation_calls == []
    assert store_build_calls == []
    assert not output_dir.exists()

    current_state = simulator.get_state()
    assert simulator._executor is not None
    direct_adapter = EconomicsTrainingAdapter(current_state, simulator._executor)
    with pytest.raises(TrainingBridgeError) as refusal:
        direct_adapter.train(actor, config, seed=31)
    assert refusal.value.code == "training_active_gini_profile_unsupported"
    assert training_calls == []
    assert observation_calls == []
    assert store_build_calls == []
    assert not output_dir.exists()


@pytest.mark.parametrize(
    "invalid_wealth",
    [
        pytest.param(float("nan"), id="nan"),
        pytest.param(float("inf"), id="positive-infinity"),
        pytest.param(float("-inf"), id="negative-infinity"),
    ],
)
def test_nonfinite_active_wealth_is_typed_before_output_creation(
    simulator: PolisySimulator,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    invalid_wealth: float,
) -> None:
    """Non-finite active values take the same typed refusal without training."""

    from polisyos.foundry.plugins import api as api_module
    from polisyos.foundry.plugins import training_adapter as training_adapter_module

    simulator.initialize(seed=7)
    state = simulator.get_state()
    domain = state.get_domain("economics")
    agents = domain.agents.replace(
        wealth=domain.agents.wealth.at[0].set(invalid_wealth),
    )
    simulator._state = state.update_domain("economics", domain.replace(agents=agents))
    training_calls: list[str] = []
    observation_calls: list[str] = []
    store_build_calls: list[str] = []

    def unexpected_native_training(*args, **kwargs):
        del args, kwargs
        training_calls.append("called")
        raise AssertionError("invalid wealth reached the native trainer")

    def unexpected_observation_projection(*args, **kwargs):
        del args, kwargs
        observation_calls.append("called")
        raise AssertionError("invalid wealth reached observation projection")

    def unexpected_store_build(*args, **kwargs):
        del args, kwargs
        store_build_calls.append("called")
        raise AssertionError("invalid wealth created a training store")

    monkeypatch.setattr(
        training_adapter_module,
        "train_actor_critic_with_artifact",
        unexpected_native_training,
    )
    monkeypatch.setattr(
        EconomicsTrainingAdapter,
        "observation_dim",
        unexpected_observation_projection,
    )
    monkeypatch.setattr(api_module, "build_artifact_store", unexpected_store_build)
    output_dir = tmp_path / "nonfinite-wealth-training"
    result = simulator.train(
        training_config=_small_config(),
        seed=7,
        output_dir=output_dir,
    )

    assert result.status == "bridge_pending"
    assert result.reason is not None
    assert result.reason.code == "training_active_gini_profile_unsupported"
    assert result.trained_policy is None
    assert result.artifact_refs is None
    assert training_calls == []
    assert observation_calls == []
    assert store_build_calls == []
    assert not output_dir.exists()


def test_training_input_gate_preserves_zero_active_and_negative_inactive_wealth(
    simulator: PolisySimulator,
) -> None:
    """Active zero resources remain valid and inactive malformed values are excluded."""

    simulator.initialize(seed=7)
    state = simulator.get_state()
    domain = state.get_domain("economics")
    active = domain.agents.active.at[-1].set(False)
    wealth = domain.agents.wealth.at[:-1].set(0.0).at[-1].set(-1_000.0)
    income = domain.agents.income.at[-1].set(jnp.nan)
    domain = domain.replace(
        agents=domain.agents.replace(active=active, wealth=wealth, income=income)
    )
    state = state.update_domain("economics", domain)

    assert simulator._executor is not None
    assert (
        EconomicsTrainingAdapter.assess(
            state,
            simulator._executor,
            require_supported_active_wealth=True,
        )
        is None
    )


@pytest.mark.parametrize(
    "selector",
    [
        pytest.param(None, id="falsey-none"),
        pytest.param("false", id="truthy-string"),
    ],
)
@pytest.mark.parametrize("constructor", ["assess", "from_composite"])
def test_training_bridge_rejects_malformed_boolean_selector(
    simulator: PolisySimulator,
    selector: object,
    constructor: str,
) -> None:
    """Both bridge intake paths reject present non-bool selectors before truthiness."""

    simulator.initialize(seed=37)
    assert simulator._executor is not None
    state = simulator.get_state()
    domain = state.get_domain("economics")
    agents = domain.agents.replace(
        active=jnp.ones_like(domain.agents.active),
        wealth=jnp.ones_like(domain.agents.wealth),
        income=jnp.ones_like(domain.agents.income).at[0].set(jnp.nan),
    )
    malformed_state = state.update_domain("economics", domain.replace(agents=agents))
    entrypoint = getattr(EconomicsTrainingAdapter, constructor)

    with pytest.raises(TypeError, match="require_supported_active_wealth must be a bool"):
        entrypoint(
            malformed_state,
            simulator._executor,
            require_supported_active_wealth=selector,
        )


def test_training_bridge_selector_keeps_valid_false_and_true_meanings(
    simulator: PolisySimulator,
) -> None:
    """The legacy false path remains general while true checks active income."""

    simulator.initialize(seed=41)
    assert simulator._executor is not None
    state = simulator.get_state()
    domain = state.get_domain("economics")
    agents = domain.agents.replace(
        active=jnp.ones_like(domain.agents.active),
        wealth=jnp.ones_like(domain.agents.wealth),
        income=jnp.ones_like(domain.agents.income).at[0].set(jnp.nan),
    )
    malformed_income_state = state.update_domain("economics", domain.replace(agents=agents))

    assert (
        EconomicsTrainingAdapter.assess(
            malformed_income_state,
            simulator._executor,
            require_supported_active_wealth=False,
        )
        is None
    )
    assessment = EconomicsTrainingAdapter.assess(
        malformed_income_state,
        simulator._executor,
        require_supported_active_wealth=True,
    )
    assert assessment is not None
    assert assessment.code == "training_active_gini_profile_unsupported"
    assert (
        EconomicsTrainingAdapter.from_composite(
            malformed_income_state,
            simulator._executor,
            require_supported_active_wealth=False,
        )
        is not None
    )
    assert (
        EconomicsTrainingAdapter.from_composite(
            malformed_income_state,
            simulator._executor,
            require_supported_active_wealth=True,
        )
        is None
    )


@pytest.mark.parametrize(
    "invalid_income",
    [
        pytest.param(-1.0, id="active-negative-income"),
        pytest.param(float("nan"), id="active-nonfinite-income"),
    ],
)
def test_active_income_outside_gini_profile_is_typed_before_optimizer_or_projection(
    simulator: PolisySimulator,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    invalid_income: float,
) -> None:
    """Refuse unsupported active income before the bridge reaches classical Gini."""
    from polisyos.foundry.agent_sim.distributions import compute_gini_hard
    from polisyos.foundry.plugins import training_adapter as training_adapter_module

    simulator.initialize(seed=31)
    source = simulator.get_state()
    domain = source.get_domain("economics")
    agents = domain.agents.replace(
        active=jnp.ones_like(domain.agents.active),
        wealth=jnp.full_like(domain.agents.wealth, 1_000_000.0),
        income=jnp.ones_like(domain.agents.income).at[0].set(invalid_income),
        wage=jnp.full_like(domain.agents.wage, 30.0),
        skill_level=jnp.full_like(domain.agents.skill_level, 2.0),
        employed=jnp.ones_like(domain.agents.employed),
    )
    policy_state = domain.policy.replace(
        transfer_rate=jnp.asarray(0.0, dtype=jnp.float32),
        unemployment_benefit=jnp.asarray(0.0, dtype=jnp.float32),
        minimum_wage=jnp.asarray(0.0, dtype=jnp.float32),
        interest_rate=jnp.asarray(0.0, dtype=jnp.float32),
    )
    # Keep stored aggregates untouched: the admitted consumer must refuse this
    # malformed supplied input before any projection recomputes classical Gini.
    domain = domain.replace(agents=agents, policy=policy_state)
    simulator._state = source.update_domain("economics", domain)
    rejected_state = simulator._state
    assert simulator._executor is not None

    assessment = EconomicsTrainingAdapter.assess(
        rejected_state,
        simulator._executor,
        require_supported_active_wealth=True,
    )
    assert assessment is not None
    assert assessment.code == "training_active_gini_profile_unsupported"
    assert (
        EconomicsTrainingAdapter.from_composite(
            rejected_state,
            simulator._executor,
            require_supported_active_wealth=True,
        )
        is None
    )

    # The existing classical-Gini guard remains active for direct consumers;
    # the bridge's typed refusal does not change or suppress that contract.
    with pytest.raises(
        ValueError, match="classical Gini requires finite nonnegative active values"
    ):
        jax.block_until_ready(compute_gini_hard(agents.income, agents.active))

    adapter = EconomicsTrainingAdapter.from_composite(rejected_state, simulator._executor)
    assert adapter is not None
    config = _small_config()
    observation_dim = adapter.observation_dim(config)
    policy = ActorCritic(
        jax.random.PRNGKey(31),
        obs_dim=observation_dim,
        hidden_dims=(64, 64),
        action_dim=1,
    )
    with pytest.raises(TrainingBridgeError) as direct_refusal:
        adapter.run(policy, config, seed=31, n_steps=1)
    assert direct_refusal.value.code == "training_active_gini_profile_unsupported"

    optimizer_calls: list[object] = []

    def unexpected_native_training(*args, **kwargs):
        optimizer_calls.append((args, kwargs))
        raise AssertionError("unsupported profile reached the native optimizer")

    monkeypatch.setattr(
        training_adapter_module,
        "train_actor_critic_with_artifact",
        unexpected_native_training,
    )
    cas = FileSystemCAS(tmp_path / f"unsupported-income-{invalid_income!r}")
    result = simulator.train(
        training_config=config,
        seed=31,
        artifact_store=cas,
    )

    assert isinstance(result, TrainingResult)
    assert result.status == "bridge_pending"
    assert result.reason is not None
    assert result.reason.code == "training_active_gini_profile_unsupported"
    assert result.trained_policy is None
    assert result.artifact is None
    assert result.artifact_refs is None
    assert result.final_state is rejected_state
    assert optimizer_calls == []
    assert not list(cas.root.rglob("*.blob"))
    assert not list(cas.root.rglob("*.manifest.json"))


def test_training_gini_profile_excludes_inactive_nonfinite_income_padding(
    simulator: PolisySimulator,
) -> None:
    """The selected population predicate excludes inactive padding consistently."""

    from polisyos.foundry.agent_sim.distributions import compute_gini_hard

    simulator.initialize(seed=7)
    state = simulator.get_state()
    domain = state.get_domain("economics")
    active = domain.agents.active.at[-1].set(False)
    income = jnp.ones_like(domain.agents.income).at[-1].set(jnp.nan)
    agents = domain.agents.replace(active=active, income=income)
    selected_state = state.update_domain("economics", domain.replace(agents=agents))
    assert simulator._executor is not None

    assert (
        EconomicsTrainingAdapter.assess(
            selected_state,
            simulator._executor,
            require_supported_active_wealth=True,
        )
        is None
    )
    gini = compute_gini_hard(income, active)
    assert jnp.isfinite(gini)
    assert jnp.isclose(gini, 0.0)


def test_temporal_resource_overflow_is_terminal_before_optimizer_or_cas(
    simulator: PolisySimulator,
    tmp_path: Path,
) -> None:
    """Finite inputs whose native temporal sum overflows stop before Gini/PPO/CAS."""

    simulator.initialize(seed=41)
    source = simulator.get_state()
    domain = source.get_domain("economics")
    active = domain.agents.active
    large_finite = jnp.asarray(1.9e38, dtype=domain.agents.wealth.dtype)
    agents = domain.agents.replace(
        wealth=jnp.where(active, large_finite, domain.agents.wealth),
        income=jnp.where(active, large_finite, domain.agents.income),
    )
    simulator._state = source.update_domain("economics", domain.replace(agents=agents))
    assert jnp.all(jnp.isfinite(agents.wealth[active]))
    assert jnp.all(jnp.isfinite(agents.income[active]))
    assert jnp.all(agents.wealth[active] >= 0.0)
    assert jnp.all(agents.income[active] >= 0.0)

    cas = FileSystemCAS(tmp_path / "temporal-overflow-cas")
    result = simulator.train(
        training_config=_small_config(),
        seed=41,
        artifact_store=cas,
    )

    assert result.status == "bridge_pending"
    assert result.reason is not None
    assert result.reason.code == "training_active_gini_trajectory_unsupported"
    assert result.trained_policy is None
    assert result.artifact is None
    assert result.artifact_refs is None
    assert result.loss_history == []
    assert result.final_state is simulator._state
    assert not list(cas.root.rglob("*.blob"))
    assert not list(cas.root.rglob("*.manifest.json"))


class _SetEconomicsActiveIncome:
    """Write a fixed income value through the real Economics mechanism seam."""

    def __init__(self, name: str, value: float) -> None:
        self.name = name
        self.value = value

    def apply(self, state, rng_key, **kwargs):
        del rng_key, kwargs
        income = jnp.where(
            state.agents.active,
            jnp.full_like(state.agents.income, self.value),
            state.agents.income,
        )
        return state.replace(agents=state.agents.replace(income=income))


def test_invalid_economics_producer_is_terminal_through_native_bridge_and_cas(
    simulator: PolisySimulator,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A later valid producer cannot erase an invalid intermediate training state."""

    simulator.initialize(seed=53)
    _set_supported_nonnegative_active_wealth(simulator, 1_000_000.0)
    source = simulator.get_state()
    source_domain = source.get_domain("economics")
    source_agents = source_domain.agents
    source_income = jnp.where(
        source_agents.active,
        jnp.full_like(source_agents.income, 7.0),
        source_agents.income,
    )
    source_domain = source_domain.replace(
        agents=source_agents.replace(income=source_income)
    ).update_aggregates()
    source = source.update_domain("economics", source_domain)
    simulator._state = source
    assert simulator._executor is not None
    plugin = simulator._executor.registry.get("economics")
    mechanisms = [
        _SetEconomicsActiveIncome("labor_market", float("nan")),
        _SetEconomicsActiveIncome("taxation", 1.0),
    ]
    monkeypatch.setattr(plugin, "get_mechanisms", lambda: mechanisms)

    adapter = EconomicsTrainingAdapter.from_composite(source, simulator._executor)
    assert adapter is not None
    selected_source = CompositeState(
        domain_states=source.domain_states,
        time_step=source.time_step,
        config=adapter.bridge_config,
        gini_profile_supported=source.gini_profile_supported,
    )
    terminal = adapter.bridge_executor.step(selected_source, jax.random.PRNGKey(53))
    source_domain = selected_source.get_domain("economics")
    terminal_domain = terminal.get_domain("economics")
    assert not bool(terminal.gini_profile_supported)
    assert jnp.all(source_domain.agents.income[source_domain.agents.active] == 7.0)
    assert jnp.all(terminal_domain.agents.income[terminal_domain.agents.active] == 7.0)
    assert jnp.array_equal(terminal_domain.agents.income, source_domain.agents.income)
    assert int(terminal.time_step) == int(selected_source.time_step)

    cas = FileSystemCAS(tmp_path / "invalid-then-repaired-economics-cas")
    result = simulator.train(
        training_config=_small_config(),
        seed=53,
        artifact_store=cas,
    )

    assert isinstance(result, TrainingResult)
    assert result.status == "bridge_pending"
    assert result.reason is not None
    assert result.reason.code == "training_active_gini_trajectory_unsupported"
    assert result.trained_policy is None
    assert result.artifact is None
    assert result.artifact_refs is None
    assert result.loss_history == []
    assert result.final_state is source
    assert simulator._agent_policy is None
    assert simulator._training_config is None
    assert not list(cas.root.rglob("*.blob"))
    assert not list(cas.root.rglob("*.manifest.json"))


class _NegativeThenPositiveWealthMechanism(Mechanism):
    """Emit a negative first public-step state and a positive second one."""

    @property
    def spec(self) -> MechanismSpec:
        return MechanismSpec(
            name="negative_then_positive_wealth",
            reads=frozenset({"time_step", "agents.active"}),
            writes=frozenset({"agents.wealth"}),
            parameters={},
            stochastic=False,
        )

    def apply(self, state, rng_key, fidelity):
        del rng_key, fidelity
        step_wealth = jnp.where(
            state.time_step == 0,
            jnp.full_like(state.agents.wealth, -1.0),
            jnp.full_like(state.agents.wealth, 1.0),
        )
        wealth = jnp.where(state.agents.active, step_wealth, state.agents.wealth)
        return state.replace(agents=state.agents.replace(wealth=wealth)), {}


class _NativeValidationFailureMechanism(Mechanism):
    """Trigger Equinox's runtime guard on the native PureExecutor path."""

    @property
    def spec(self) -> MechanismSpec:
        return MechanismSpec(
            name="native_validation_failure",
            reads=frozenset({"agents.active", "agents.wealth"}),
            writes=frozenset({"agents.wealth"}),
            parameters={},
            stochastic=False,
        )

    def apply(self, state, rng_key, fidelity):
        del rng_key, fidelity
        guarded = eqx.error_if(
            state.agents.wealth,
            jnp.any(state.agents.active),
            "opaque validation failure fixture",
        )
        return state.replace(agents=state.agents.replace(wealth=guarded)), {}


class _NativeInfrastructureFailureMechanism(Mechanism):
    """Raise an ordinary callback failure that is not an Equinox guard."""

    @property
    def spec(self) -> MechanismSpec:
        return MechanismSpec(
            name="native_infrastructure_failure",
            reads=frozenset(),
            writes=frozenset(),
            parameters={},
            stochastic=False,
        )

    def apply(self, state, rng_key, fidelity):
        del rng_key, fidelity

        def fail_callback() -> None:
            raise RuntimeError("infrastructure callback fixture")

        jax.debug.callback(fail_callback, ordered=True)
        return state, {}


def test_native_monitor_observes_negative_public_step_even_when_final_step_recovers(
    tmp_path: Path,
) -> None:
    """A positive final state cannot hide a failed intermediate public transition."""

    from polisyos.foundry.agent_sim.jit_training import _ActiveWealthTrajectoryValidationError
    from polisyos.foundry.agent_sim.training import train_actor_critic_with_artifact

    state = GlobalState.empty(2, seed=17)
    observation = build_temporal_observations(state, horizon=4, include_expectations=False)
    actor = ActorCritic(jax.random.PRNGKey(17), obs_dim=observation.shape[-1], hidden_dims=(8, 4))
    config = TrainingConfig(
        n_episodes=1,
        steps_per_episode=2,
        horizon=4,
        ppo_epochs=1,
        include_expectations=False,
    )

    def make_executor(_actor):
        del _actor
        return PureExecutor([_NegativeThenPositiveWealthMechanism()])

    executor = make_executor(actor)
    first_state, _ = executor.step(state, fidelity=config.fidelity)
    final_state, _ = executor.step(first_state, fidelity=config.fidelity)
    active = state.agents.active
    assert jnp.any(first_state.agents.active & (first_state.agents.wealth < 0.0))
    assert jnp.all(final_state.agents.wealth[active] > 0.0)
    assert executor.compute_gini is False
    assert executor.aggregate_every is None

    cas = FileSystemCAS(tmp_path / "trajectory-monitor-cas")
    with jax.enable_x64(True), pytest.raises(_ActiveWealthTrajectoryValidationError) as refused:
        train_actor_critic_with_artifact(
            actor,
            state,
            config,
            make_executor=make_executor,
            run_id="negative-intermediate-positive-final",
            seed=17,
            cas=cas,
            track_active_wealth=True,
        )
    assert refused.value.code == "training_active_gini_trajectory_unsupported"
    assert not list(cas.root.rglob("*.blob"))
    assert not list(cas.root.rglob("*.manifest.json"))


@pytest.mark.parametrize("with_metrics", [False, True], ids=["without-metrics", "with-metrics"])
def test_native_jit_factory_preserves_typed_validation_cause(with_metrics: bool) -> None:
    """Both JIT factories type the Equinox guard and preserve it as the cause."""

    from polisyos.foundry.agent_sim.jit_training import (
        JITTrainingConfig,
        _NativeExecutionValidationError,
        create_jit_trainer,
        create_jit_trainer_with_metrics,
    )

    state = GlobalState.empty(2, seed=23)
    config = JITTrainingConfig(**_small_config().common_kwargs(), track_active_wealth=True)
    observation = build_temporal_observations(
        state,
        horizon=config.horizon,
        include_expectations=config.include_expectations,
    )
    actor = ActorCritic(jax.random.PRNGKey(23), obs_dim=observation.shape[-1], hidden_dims=(8, 4))

    def make_executor(_actor):
        del _actor
        return PureExecutor([_NativeValidationFailureMechanism()])

    factory = create_jit_trainer_with_metrics if with_metrics else create_jit_trainer
    with jax.enable_x64(True):
        trainer = factory(actor, make_executor, state, config)
        with pytest.raises(_NativeExecutionValidationError) as refused:
            trainer(jax.random.PRNGKey(23))
    assert refused.value.code == "native_execution_validation_refused"
    assert isinstance(refused.value.__cause__, eqx.EquinoxRuntimeError)
    assert "opaque validation failure fixture" in str(refused.value.__cause__)


@pytest.mark.parametrize("with_metrics", [False, True], ids=["without-metrics", "with-metrics"])
def test_native_jit_factory_preserves_unclassified_jax_failure(with_metrics: bool) -> None:
    """An ordinary JAX callback failure must not become a typed policy refusal."""

    from polisyos.foundry.agent_sim.jit_training import (
        JITTrainingConfig,
        _NativeExecutionValidationError,
        create_jit_trainer,
        create_jit_trainer_with_metrics,
    )

    state = GlobalState.empty(2, seed=29)
    base_config = _small_config()
    observation = build_temporal_observations(
        state,
        horizon=base_config.horizon,
        include_expectations=base_config.include_expectations,
    )
    actor = ActorCritic(jax.random.PRNGKey(29), obs_dim=observation.shape[-1], hidden_dims=(8, 4))
    config = JITTrainingConfig(**base_config.common_kwargs(), track_active_wealth=True)

    def make_executor(_actor):
        del _actor
        return PureExecutor([_NativeInfrastructureFailureMechanism()])

    factory = create_jit_trainer_with_metrics if with_metrics else create_jit_trainer
    with jax.enable_x64(True):
        trainer = factory(actor, make_executor, state, config)
        with pytest.raises(
            jax.errors.JaxRuntimeError, match="infrastructure callback fixture"
        ) as failure:
            trainer(jax.random.PRNGKey(29))
    assert not isinstance(failure.value, _NativeExecutionValidationError)


def test_training_uses_supplied_tenant_store_for_persist_and_readback(
    simulator: PolisySimulator,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Training keeps the caller's tenant store through artifact write and readback."""

    from polisyos.foundry.agent_sim.artifact import AgentPolicyArtifact
    from polisyos.foundry.plugins import training_adapter as training_adapter_module

    simulator.initialize(seed=7)
    _set_supported_nonnegative_active_wealth(simulator, 1_000_000.0)
    config = _small_config()

    def stub_native_training(policy, _initial_state, _config, **kwargs):
        assert kwargs["track_active_wealth"] is True
        trained_artifact = dataclass_replace(
            AgentPolicyArtifact.from_trained_policy(
                policy,
                run_id="tenant-store-test",
                steps=1,
                loss=0.25,
                fingerprint=EnvironmentFingerprint.capture(kwargs["tier"], kwargs["seed"]),
            ),
            schema_version="1.1",
            training_profile=TrainingProfileDescriptor(),
        )
        return policy, {"loss_history": [0.25]}, trained_artifact

    monkeypatch.setattr(
        training_adapter_module,
        "train_actor_critic_with_artifact",
        stub_native_training,
    )
    monkeypatch.setattr(training_adapter_module, "_parameter_delta", lambda *args: jnp.array(1.0))
    monkeypatch.setattr(training_adapter_module, "_action_delta", lambda *args: jnp.array(1.0))
    tenant_store = FileSystemCAS(tmp_path / "shared-cas").for_tenant(
        "tenant-a",
        cell_id="cell-a",
    )

    class RecordingTenantStore:
        """Record read selectors while keeping the tenant-bound store as owner."""

        def __init__(self, delegate: FileSystemCAS) -> None:
            self.delegate = delegate
            self.read_refs: list[ArtifactID | ArtifactRef | str] = []

        def __getattr__(self, name: str):
            return getattr(self.delegate, name)

        def get_bytes(self, reference: ArtifactID | ArtifactRef | str) -> bytes:
            self.read_refs.append(reference)
            return self.delegate.get_bytes(reference)

    supplied_store = RecordingTenantStore(tenant_store)
    store_calls: list[object] = []
    load_calls: list[object] = []
    store_policy_artifact = training_adapter_module.store_policy_artifact
    load_policy_artifact = training_adapter_module.load_policy_artifact

    def record_store(store, value):
        store_calls.append(store)
        return store_policy_artifact(store, value)

    def record_load(store, *args, **kwargs):
        load_calls.append(store)
        return load_policy_artifact(store, *args, **kwargs)

    monkeypatch.setattr(training_adapter_module, "store_policy_artifact", record_store)
    monkeypatch.setattr(training_adapter_module, "load_policy_artifact", record_load)

    result = simulator.train(
        n_episodes=config.n_episodes,
        training_config=config,
        seed=7,
        artifact_store=supplied_store,
    )

    assert result.status == "trained"
    assert result.artifact_refs is not None
    assert len(store_calls) == 1 and store_calls[0] is supplied_store
    assert len(load_calls) == 1 and load_calls[0] is supplied_store
    weights_ref, manifest_ref = result.artifact_refs
    assert supplied_store.has(weights_ref)
    assert supplied_store.has(manifest_ref)
    assert isinstance(supplied_store.read_refs[0], ArtifactRef)
    assert supplied_store.read_refs[0].artifact_id == manifest_ref.artifact_id

    foreign_store = FileSystemCAS(tmp_path / "shared-cas").for_tenant(
        "tenant-b",
        cell_id="cell-b",
    )
    assert foreign_store.has(manifest_ref) is False
    with pytest.raises(ArtifactOwnershipError):
        foreign_store.get_bytes(manifest_ref)


def test_output_dir_training_persists_under_the_active_tenant_owner(
    simulator: PolisySimulator,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The output-dir composition path records and enforces the ambient owner."""

    from polisyos.foundry.agent_sim.artifact import AgentPolicyArtifact
    from polisyos.foundry.plugins import training_adapter as training_adapter_module

    simulator.initialize(seed=7)
    _set_supported_nonnegative_active_wealth(simulator, 1_000_000.0)
    config = _small_config()

    def stub_native_training(policy, _initial_state, _config, **kwargs):
        assert kwargs["track_active_wealth"] is True
        trained_artifact = dataclass_replace(
            AgentPolicyArtifact.from_trained_policy(
                policy,
                run_id="ambient-tenant-store-test",
                steps=1,
                loss=0.25,
                fingerprint=EnvironmentFingerprint.capture(kwargs["tier"], kwargs["seed"]),
            ),
            schema_version="1.1",
            training_profile=TrainingProfileDescriptor(),
        )
        return policy, {"loss_history": [0.25]}, trained_artifact

    monkeypatch.setattr(
        training_adapter_module, "train_actor_critic_with_artifact", stub_native_training
    )
    monkeypatch.setattr(training_adapter_module, "_parameter_delta", lambda *args: jnp.array(1.0))
    monkeypatch.setattr(training_adapter_module, "_action_delta", lambda *args: jnp.array(1.0))
    output_dir = tmp_path / "tenant-training-output"
    with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
        result = simulator.train(
            n_episodes=config.n_episodes,
            training_config=config,
            seed=7,
            output_dir=output_dir,
        )

    assert result.status == "trained"
    assert result.artifact_refs is not None
    shared_store = FileSystemCAS(output_dir / "artifacts")
    ownership = shared_store.ownership_evidence(tenant_id="tenant-a", cell_id="cell-a")
    assert ownership["tenant_artifact_count"] == 2

    foreign_store = shared_store.for_tenant("tenant-b", cell_id="cell-b")
    with pytest.raises(ArtifactOwnershipError):
        foreign_store.get_bytes(result.artifact_refs[1])


def test_load_payload_reads_non_default_selected_view_for_shared_blob(
    tmp_path: Path,
) -> None:
    """A tenant can read its selected typed manifest view, not another tenant's default."""

    from polisyos.foundry.agent_sim.artifact import _load_payload

    payload = {"selected_view": "tenant-b"}
    shared_store = FileSystemCAS(tmp_path / "shared-view-cas")
    default_owner = shared_store.for_tenant("tenant-a", cell_id="cell-a")
    selected_view_owner = shared_store.for_tenant("tenant-b", cell_id="cell-b")

    default_ref = default_owner.put_json(
        payload,
        PutOptions(kind="foundry.policy.default-view", media_type="application/json"),
    )
    selected_ref = selected_view_owner.put_json(
        payload,
        PutOptions(kind="foundry.policy.selected-view", media_type="application/json"),
    )

    assert default_ref.artifact_id == selected_ref.artifact_id
    assert default_ref.manifest_profile_sha256 is None
    assert selected_ref.manifest_profile_sha256 is not None
    assert default_owner.get_manifest(default_ref).kind == "foundry.policy.default-view"
    assert selected_view_owner.get_manifest(selected_ref).kind == "foundry.policy.selected-view"

    assert _load_payload(selected_view_owner, selected_ref) == payload
    with pytest.raises(ArtifactOwnershipError):
        _load_payload(selected_view_owner, selected_ref.artifact_id)


def test_unsupported_composite_remains_bridge_pending() -> None:
    """Interactions are not silently dropped by the one-domain adapter."""

    registry = PluginRegistry()
    registry.clear()
    registry.register(EconomicsPlugin())
    simulator = PolisySimulator(registry, auto_discover=False)
    simulator.add_domain("economics", DomainConfig(n_agents=10, max_agents=10))
    simulator.add_interaction(
        "economics",
        "economics",
        "agents.wealth",
        "agents.income",
    )

    result = simulator.train(
        n_episodes=1,
        training_config=_small_config(),
        seed=7,
    )

    assert result.status == "bridge_pending"
    assert result.trained_policy is None
    assert result.reason is not None
    assert result.reason.code == "training_composite_profile_unsupported"


def test_cli_reports_optimizer_loss_and_artifact_without_reward_alias(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CLI reports the real optimizer result for a supported safe-wealth profile."""

    original_train = PolisySimulator.train
    training_calls: list[str] = []
    observed_results: list[TrainingResult] = []
    training_seed = 7

    def train_supported_profile(
        simulator: PolisySimulator,
        n_episodes: int = 100,
        training_config=None,
        seed: int = 42,
        output_dir: Path | None = None,
        artifact_store=None,
    ) -> TrainingResult:
        del seed
        if simulator._state is None:
            simulator.initialize(training_seed)
        _set_supported_nonnegative_active_wealth(simulator, 1_000_000.0)
        training_calls.append("real_train")
        result = original_train(
            simulator,
            n_episodes=n_episodes,
            training_config=training_config or _small_config(),
            seed=training_seed,
            output_dir=output_dir,
            artifact_store=artifact_store,
        )
        observed_results.append(result)
        return result

    monkeypatch.setattr(PolisySimulator, "train", train_supported_profile)
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps({"domains": {"economics": {"n_agents": 10, "max_agents": 10}}}),
        encoding="utf-8",
    )
    cmd_train(
        argparse.Namespace(
            config=config_path,
            domain=None,
            n_episodes=1,
            output=tmp_path / "output",
        )
    )

    output = capsys.readouterr().out
    assert "Training complete!" in output
    assert "Final loss:" not in output
    assert training_calls == ["real_train"]
    assert len(observed_results) == 1
    result = observed_results[0]
    assert result.status == "trained"
    assert result.reason is None
    assert result.trained_policy is not None
    assert result.artifact is not None
    assert result.artifact_refs is not None
    assert result.loss_history
    assert result.artifact.metrics.final_loss == result.loss_history[-1]
    assert f"  PPO loss: {result.loss_history[-1]:.4f}" in output
    assert f"  Artifact: {result.artifact.artifact_id}" in output
