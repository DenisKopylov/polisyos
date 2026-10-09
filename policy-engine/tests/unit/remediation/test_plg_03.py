"""PLG-03 witnesses for the bounded Economics-to-native training bridge."""

from __future__ import annotations

import argparse
import json
from decimal import Decimal
from pathlib import Path

import jax
import jax.numpy as jnp
import pytest

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.ownership import ArtifactOwnershipError
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.security.tenant_context import tenant_scope
from polisyos.foundry.agent_sim import ActorCritic, TrainingConfig, build_temporal_observations
from polisyos.foundry.plugins.api import PolisySimulator, TrainingResult
from polisyos.foundry.plugins.cli import cmd_train
from polisyos.foundry.plugins.core import DomainConfig, PluginRegistry
from polisyos.foundry.plugins.economics import EconomicsPlugin
from polisyos.foundry.plugins.training_adapter import EconomicsTrainingAdapter
from polisyos.foundry.runtime.fingerprint import EnvironmentFingerprint


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


def test_economics_training_updates_policy_and_produces_readable_artifact(
    simulator: PolisySimulator,
    tmp_path: Path,
) -> None:
    """The bridge must use the native optimizer and expose a learned artifact."""

    simulator.initialize(seed=7)
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

    result = simulator.train(
        n_episodes=1,
        training_config=_small_config(),
        seed=7,
        output_dir=tmp_path / "training-output",
    )

    assert isinstance(result, TrainingResult)
    assert result.status == "trained"
    assert result.trained_policy is not None
    assert result.artifact is not None
    assert result.artifact_refs is not None
    assert result.loss_history
    assert all(jnp.isfinite(jnp.asarray(result.loss_history)))
    assert _tree_delta(initial_policy, result.trained_policy) > 0.0

    manifest_payload = from_canonical_bytes(
        FileSystemCAS(tmp_path / "training-output" / "artifacts").get_bytes(
            result.artifact_refs[1].artifact_id
        )
    )
    assert isinstance(manifest_payload, dict)
    assert isinstance(manifest_payload["metrics"]["final_loss"], Decimal)
    assert isinstance(manifest_payload["metrics"]["learning_rate"], Decimal)

    before_action, _ = result.trained_policy(obs, deterministic=True)
    assert jnp.all(jnp.isfinite(before_action))
    assert result.artifact.load_weights(result.trained_policy) is not None

    final_state = simulator.get_state()
    assert int(final_state.time_step) > 0


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


def test_training_uses_supplied_tenant_store_for_persist_and_readback(
    simulator: PolisySimulator,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Training keeps the caller's tenant store through artifact write and readback."""

    from polisyos.foundry.agent_sim.artifact import AgentPolicyArtifact
    from polisyos.foundry.plugins import training_adapter as training_adapter_module

    simulator.initialize(seed=7)
    config = _small_config()

    def stub_native_training(policy, _initial_state, _config, **kwargs):
        trained_artifact = AgentPolicyArtifact.from_trained_policy(
            policy,
            run_id="tenant-store-test",
            steps=1,
            loss=0.25,
            fingerprint=EnvironmentFingerprint.capture(kwargs["tier"], kwargs["seed"]),
        )
        return policy, {"loss_history": [0.25]}, trained_artifact

    monkeypatch.setattr(
        training_adapter_module,
        "train_actor_critic_with_artifact",
        stub_native_training,
    )
    monkeypatch.setattr(training_adapter_module, "_parameter_delta", lambda *args: jnp.array(1.0))
    monkeypatch.setattr(training_adapter_module, "_action_delta", lambda *args: jnp.array(1.0))
    monkeypatch.setattr(
        EconomicsTrainingAdapter,
        "run",
        lambda self, *args, **kwargs: (simulator.get_state(), []),
    )

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
    config = _small_config()

    def stub_native_training(policy, _initial_state, _config, **kwargs):
        trained_artifact = AgentPolicyArtifact.from_trained_policy(
            policy,
            run_id="ambient-tenant-store-test",
            steps=1,
            loss=0.25,
            fingerprint=EnvironmentFingerprint.capture(kwargs["tier"], kwargs["seed"]),
        )
        return policy, {"loss_history": [0.25]}, trained_artifact

    monkeypatch.setattr(
        training_adapter_module, "train_actor_critic_with_artifact", stub_native_training
    )
    monkeypatch.setattr(training_adapter_module, "_parameter_delta", lambda *args: jnp.array(1.0))
    monkeypatch.setattr(training_adapter_module, "_action_delta", lambda *args: jnp.array(1.0))
    monkeypatch.setattr(
        EconomicsTrainingAdapter,
        "run",
        lambda self, *args, **kwargs: (simulator.get_state(), []),
    )

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
) -> None:
    """CLI names the native optimizer metric and never calls reward a final loss."""

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
    assert "PPO loss:" in output
    assert "Final loss:" not in output
    assert "Artifact:" in output
