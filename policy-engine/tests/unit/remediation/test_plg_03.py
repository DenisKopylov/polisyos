"""PLG-03 witnesses for the bounded Economics-to-native training bridge."""

from __future__ import annotations

import argparse
import json
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

import jax
import jax.numpy as jnp
import pytest

from polisyos.core.artifacts.backends.config import ArtifactStoreConfig
from polisyos.core.artifacts.ownership import ArtifactOwnershipError
from polisyos.core.artifacts.protocol import ArtifactStore
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.security.tenant_context import tenant_scope
from polisyos.foundry.agent_sim import ActorCritic, TrainingConfig, build_temporal_observations
from polisyos.foundry.plugins.api import PolisySimulator, TrainingResult
from polisyos.foundry.plugins.cli import cmd_train
from polisyos.foundry.plugins.core import DomainConfig, PluginRegistry
from polisyos.foundry.plugins.economics import EconomicsPlugin
from polisyos.foundry.plugins.training_adapter import EconomicsTrainingAdapter
from polisyos.runtime.http.resilience import guard_runtime_cas


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


class _RecordingArtifactStore:
    """Record successful artifact operations while retaining tenant guards."""

    def __init__(self, delegate: ArtifactStore) -> None:
        self._delegate = delegate
        self.operations: list[tuple[str, str]] = []

    def __getattr__(self, name: str) -> Any:
        operation = getattr(self._delegate, name)
        if name not in {"put_bytes", "put_json", "get_manifest", "get_bytes"}:
            return operation

        def record(*args: Any, **kwargs: Any) -> Any:
            result = operation(*args, **kwargs)
            artifact_id = result.artifact_id if name.startswith("put_") else args[0]
            self.operations.append((name, str(artifact_id)))
            return result

        return record


def test_economics_training_updates_policy_and_produces_readable_artifact(
    simulator: PolisySimulator,
    tmp_path: Path,
    request: pytest.FixtureRequest,
) -> None:
    """The bridge uses the supplied tenant store and returns its learned artifact."""

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

    guarded_store = guard_runtime_cas(
        FileSystemCAS(tmp_path / "runtime-training-cas").with_ambient_ownership_enforcement()
    )
    request.addfinalizer(guarded_store.close)
    recording_store = _RecordingArtifactStore(guarded_store)
    runtime_store = cast("ArtifactStore", recording_store)
    with tenant_scope(None, tenant_id="training-tenant", cell_id="cell-a"):
        result = simulator.train(
            n_episodes=1,
            training_config=_small_config(),
            seed=7,
            artifact_store=runtime_store,
        )

    assert isinstance(result, TrainingResult)
    assert result.status == "trained"
    assert result.trained_policy is not None
    assert result.artifact is not None
    assert result.artifact_refs is not None
    assert result.loss_history
    assert all(jnp.isfinite(jnp.asarray(result.loss_history)))
    assert _tree_delta(initial_policy, result.trained_policy) > 0.0

    with tenant_scope(None, tenant_id="training-tenant", cell_id="cell-a"):
        manifest_bytes = runtime_store.get_bytes(result.artifact_refs[1].artifact_id)
    for tenant_id, cell_id in (("other-tenant", "cell-a"), ("training-tenant", "cell-b")):
        with (
            tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id),
            pytest.raises(ArtifactOwnershipError),
        ):
            runtime_store.get_bytes(result.artifact_refs[1].artifact_id)
    with tenant_scope(None, tenant_id="training-tenant", cell_id="cell-a"):
        assert runtime_store.get_bytes(result.artifact_refs[1].artifact_id) == manifest_bytes
    weights_ref, manifest_ref = result.artifact_refs
    recorded_operations = set(recording_store.operations)
    assert ("put_bytes", str(weights_ref.artifact_id)) in recorded_operations
    assert ("put_json", str(manifest_ref.artifact_id)) in recorded_operations
    assert ("get_bytes", str(weights_ref.artifact_id)) in recorded_operations
    assert ("get_bytes", str(manifest_ref.artifact_id)) in recorded_operations
    manifest_payload = from_canonical_bytes(manifest_bytes)
    assert isinstance(manifest_payload, dict)
    assert isinstance(manifest_payload["metrics"]["final_loss"], Decimal)
    assert isinstance(manifest_payload["metrics"]["learning_rate"], Decimal)

    before_action, _ = result.trained_policy(obs, deterministic=True)
    assert jnp.all(jnp.isfinite(before_action))
    assert result.artifact.load_weights(result.trained_policy) is not None

    final_state = simulator.get_state()
    assert int(final_state.time_step) > 0


def test_training_rejects_ambiguous_runtime_store_and_local_output_dir(
    simulator: PolisySimulator, tmp_path: Path
) -> None:
    """An explicit runtime owner cannot be silently shadowed by a local output path."""

    runtime_store = FileSystemCAS(tmp_path / "runtime-cas")
    with pytest.raises(
        ValueError, match="training_artifact_store_and_output_dir_are_mutually_exclusive"
    ):
        simulator.train(artifact_store=runtime_store, output_dir=tmp_path / "local-output")


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
    """Local CLI composition still persists an artifact through its configured store."""

    from polisyos.core.artifacts.ownership import ArtifactOwnershipError
    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.foundry.plugins import api as plugin_api

    created_stores: list[ArtifactStore] = []
    guarded_stores: list[ArtifactStore] = []
    training_results: list[TrainingResult] = []
    build_store = plugin_api.build_artifact_store
    ambient_guard = plugin_api.with_ambient_ownership_enforcement_if_supported
    train = plugin_api.PolisySimulator.train

    def _record_store(config: ArtifactStoreConfig) -> ArtifactStore:
        store = build_store(config)
        created_stores.append(store)
        return store

    def _record_ambient_guard(store: ArtifactStore) -> ArtifactStore:
        guarded = ambient_guard(store)
        guarded_stores.append(guarded)
        return guarded

    def _record_training(self, *args: Any, **kwargs: Any) -> TrainingResult:
        result = train(self, *args, **kwargs)
        training_results.append(result)
        return result

    monkeypatch.setattr(plugin_api, "build_artifact_store", _record_store)
    monkeypatch.setattr(
        plugin_api, "with_ambient_ownership_enforcement_if_supported", _record_ambient_guard
    )
    monkeypatch.setattr(plugin_api.PolisySimulator, "train", _record_training)
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps({"domains": {"economics": {"n_agents": 10, "max_agents": 10}}}),
        encoding="utf-8",
    )
    with tenant_scope(None, tenant_id="cli-training-tenant", cell_id="cell-a"):
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
    assert len(created_stores) == 1
    assert len(guarded_stores) == 1
    assert len(training_results) == 1
    assert training_results[0].artifact_refs is not None
    manifest_ref = training_results[0].artifact_refs[1]
    with tenant_scope(None, tenant_id="cli-training-tenant", cell_id="cell-a"):
        manifest_bytes = guarded_stores[0].get_bytes(manifest_ref.artifact_id)
    with (
        tenant_scope(None, tenant_id="foreign-cli-tenant", cell_id="cell-a"),
        pytest.raises(ArtifactOwnershipError),
    ):
        guarded_stores[0].get_bytes(manifest_ref.artifact_id)
    assert manifest_bytes
    assert created_stores[0].iter_artifact_ids()
