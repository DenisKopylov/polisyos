"""
Tests for AgentPolicyArtifact and EnvironmentFingerprint.

Covers:
1. Round-trip serialization (save -> load -> verify identical)
2. Environment fingerprint mismatch detection
3. Hot-swap compatibility guards
4. Determinism tier validation
"""

from __future__ import annotations

import equinox as eqx
import jax
import jax.numpy as jnp
import pytest
from polisyos.foundry.agent_sim.actor_critic import ActorCritic
from polisyos.foundry.agent_sim.artifact import AgentPolicyArtifact
from polisyos.foundry.runtime.fingerprint import (
    DeterminismTier,
    EnvironmentFingerprint,
    configure_determinism,
)


@pytest.fixture
def sample_actor_critic():
    """Create a minimal ActorCritic for testing."""
    return ActorCritic(
        key=jax.random.PRNGKey(0),
        obs_dim=10,
        action_dim=4,
        hidden_dims=(32, 32),
        action_type="continuous",
    )


@pytest.fixture
def sample_fingerprint():
    """Create a sample environment fingerprint."""
    return EnvironmentFingerprint.capture(
        tier=DeterminismTier.BEST_EFFORT_GPU,
        seed=42,
    )


@pytest.fixture
def sample_artifact(sample_actor_critic, sample_fingerprint):
    """Create a sample artifact for testing."""
    return AgentPolicyArtifact.from_trained_policy(
        policy=sample_actor_critic,
        run_id="test_run_001",
        steps=1000,
        loss=0.05,
        fingerprint=sample_fingerprint,
    )


class TestRoundTripSerialization:
    """Verify that save -> load produces identical weights."""

    def test_weights_roundtrip_identical(self, sample_actor_critic, sample_fingerprint):
        """Weights should be bit-exact after round-trip."""
        artifact = AgentPolicyArtifact.from_trained_policy(
            policy=sample_actor_critic,
            run_id="roundtrip_test",
            steps=100,
            loss=0.1,
            fingerprint=sample_fingerprint,
        )

        skeleton = ActorCritic(
            key=jax.random.PRNGKey(1),
            obs_dim=10,
            action_dim=4,
            hidden_dims=(32, 32),
            action_type="continuous",
        )
        loaded = artifact.load_weights(skeleton)

        original_leaves = jax.tree_util.tree_leaves(
            eqx.filter(sample_actor_critic, eqx.is_inexact_array)
        )
        loaded_leaves = jax.tree_util.tree_leaves(eqx.filter(loaded, eqx.is_inexact_array))

        assert len(original_leaves) == len(loaded_leaves)
        for orig, load in zip(original_leaves, loaded_leaves):
            assert jnp.allclose(orig, load, atol=0), "Weights must be bit-exact"

    def test_weights_hash_deterministic(self, sample_actor_critic, sample_fingerprint):
        """Same policy should produce same hash."""
        artifact1 = AgentPolicyArtifact.from_trained_policy(
            policy=sample_actor_critic,
            run_id="hash_test_1",
            steps=100,
            loss=0.1,
            fingerprint=sample_fingerprint,
        )
        artifact2 = AgentPolicyArtifact.from_trained_policy(
            policy=sample_actor_critic,
            run_id="hash_test_2",
            steps=100,
            loss=0.1,
            fingerprint=sample_fingerprint,
        )

        assert artifact1.weights_hash == artifact2.weights_hash


class TestFingerprintMismatch:
    """Verify that environment mismatches are detected."""

    def test_identical_fingerprints_score_1(self):
        """Identical fingerprints should have score 1.0."""
        fp = EnvironmentFingerprint.capture(DeterminismTier.STRICT_CPU, seed=42)
        assert fp.compatibility_score(fp) == 1.0

    def test_different_jax_version_warning(self, sample_artifact):
        """Different JAX version should reduce score."""
        modified_fp = EnvironmentFingerprint(
            python_version=sample_artifact.fingerprint.python_version,
            platform_system=sample_artifact.fingerprint.platform_system,
            platform_machine=sample_artifact.fingerprint.platform_machine,
            jax_version="0.3.0",
            jaxlib_version="0.3.0",
            xla_flags="",
            x64_enabled=False,
            deterministic_ops=False,
            cpu_count=4,
            cuda_version=None,
            cudnn_version=None,
            device_name="cpu",
            determinism_tier=DeterminismTier.STRICT_CPU,
            random_seed=42,
        )

        score = sample_artifact.fingerprint.compatibility_score(modified_fp)
        assert score < 0.5, f"Major JAX version mismatch should reduce score, got {score}"

    def test_gpu_to_cpu_warning(self, sample_fingerprint):
        """GPU-trained policy on CPU should generate warning."""
        cpu_fp = EnvironmentFingerprint(
            python_version=sample_fingerprint.python_version,
            platform_system=sample_fingerprint.platform_system,
            platform_machine=sample_fingerprint.platform_machine,
            jax_version=sample_fingerprint.jax_version,
            jaxlib_version=sample_fingerprint.jaxlib_version,
            xla_flags="",
            x64_enabled=False,
            deterministic_ops=False,
            cpu_count=4,
            cuda_version=None,
            cudnn_version=None,
            device_name="cpu",
            determinism_tier=DeterminismTier.STRICT_CPU,
            random_seed=42,
        )

        if sample_fingerprint.cuda_version:
            score = sample_fingerprint.compatibility_score(cpu_fp)
            assert score < 0.8, "GPU vs CPU should reduce compatibility"


class TestHotSwapGuards:
    """Verify hot-swap compatibility checking."""

    def test_compatible_policies_can_swap(self, sample_fingerprint):
        """Policies with same I/O shapes can hot-swap."""
        key1, key2 = jax.random.split(jax.random.PRNGKey(2))
        policy1 = ActorCritic(key=key1, obs_dim=10, action_dim=4, hidden_dims=(32,))
        policy2 = ActorCritic(key=key2, obs_dim=10, action_dim=4, hidden_dims=(64, 64))

        artifact1 = AgentPolicyArtifact.from_trained_policy(
            policy1, "run1", 100, 0.1, sample_fingerprint
        )
        artifact2 = AgentPolicyArtifact.from_trained_policy(
            policy2, "run2", 200, 0.05, sample_fingerprint
        )

        assert artifact1.can_hot_swap(artifact2), "Same I/O shapes should be swappable"

    def test_incompatible_output_dim_blocks_swap(self, sample_fingerprint):
        """Policies with different output dims cannot hot-swap."""
        key1, key2 = jax.random.split(jax.random.PRNGKey(3))
        policy1 = ActorCritic(key=key1, obs_dim=10, action_dim=4, hidden_dims=(32,))
        policy2 = ActorCritic(key=key2, obs_dim=10, action_dim=8, hidden_dims=(32,))

        artifact1 = AgentPolicyArtifact.from_trained_policy(
            policy1, "run1", 100, 0.1, sample_fingerprint
        )
        artifact2 = AgentPolicyArtifact.from_trained_policy(
            policy2, "run2", 100, 0.1, sample_fingerprint
        )

        assert not artifact1.can_hot_swap(artifact2), "Different output dims should block swap"

    def test_incompatible_input_dim_blocks_swap(self, sample_fingerprint):
        """Policies with different input dims cannot hot-swap."""
        key1, key2 = jax.random.split(jax.random.PRNGKey(4))
        policy1 = ActorCritic(key=key1, obs_dim=10, action_dim=4, hidden_dims=(32,))
        policy2 = ActorCritic(key=key2, obs_dim=20, action_dim=4, hidden_dims=(32,))

        artifact1 = AgentPolicyArtifact.from_trained_policy(
            policy1, "run1", 100, 0.1, sample_fingerprint
        )
        artifact2 = AgentPolicyArtifact.from_trained_policy(
            policy2, "run2", 100, 0.1, sample_fingerprint
        )

        assert not artifact1.can_hot_swap(artifact2), "Different input dims should block swap"


class TestDeterminismTierValidation:
    """Verify determinism tier configuration validation."""

    def test_strict_cpu_requires_deterministic_ops(self):
        """STRICT_CPU tier should require deterministic ops."""
        fp = EnvironmentFingerprint(
            python_version="3.11.0",
            platform_system="Linux",
            platform_machine="x86_64",
            jax_version="0.4.30",
            jaxlib_version="0.4.30",
            xla_flags="",
            x64_enabled=False,
            deterministic_ops=False,
            cpu_count=4,
            cuda_version=None,
            cudnn_version=None,
            device_name="cpu",
            determinism_tier=DeterminismTier.STRICT_CPU,
            random_seed=42,
        )

        warnings = fp.validate_for_tier()
        assert len(warnings) > 0, "Should warn about missing deterministic ops"
        assert any("deterministic" in w.lower() for w in warnings)

    def test_best_effort_gpu_without_cuda_warns(self):
        """BEST_EFFORT_GPU without CUDA should warn."""
        fp = EnvironmentFingerprint(
            python_version="3.11.0",
            platform_system="Linux",
            platform_machine="x86_64",
            jax_version="0.4.30",
            jaxlib_version="0.4.30",
            xla_flags="",
            x64_enabled=False,
            deterministic_ops=False,
            cpu_count=4,
            cuda_version=None,
            cudnn_version=None,
            device_name="cpu",
            determinism_tier=DeterminismTier.BEST_EFFORT_GPU,
            random_seed=42,
        )

        warnings = fp.validate_for_tier()
        assert len(warnings) > 0, "Should warn about missing CUDA"
        assert any("cuda" in w.lower() for w in warnings)

    def test_nondeterministic_no_warnings(self):
        """NONDETERMINISTIC tier should have no configuration warnings."""
        fp = EnvironmentFingerprint.capture(
            tier=DeterminismTier.NONDETERMINISTIC,
            seed=42,
        )

        warnings = fp.validate_for_tier()
        assert warnings == []


class TestConfigureDeterminism:
    """Verify determinism configuration produces correct env vars."""

    def test_strict_cpu_forces_cpu_only(self):
        """STRICT_CPU should set JAX_PLATFORMS=cpu."""
        env_vars = configure_determinism(DeterminismTier.STRICT_CPU)

        assert "JAX_PLATFORMS" in env_vars
        assert env_vars["JAX_PLATFORMS"] == "cpu"

    def test_strict_cpu_enables_deterministic_ops(self):
        """STRICT_CPU should enable XLA deterministic ops."""
        env_vars = configure_determinism(DeterminismTier.STRICT_CPU)

        assert "XLA_FLAGS" in env_vars
        assert "deterministic_ops=true" in env_vars["XLA_FLAGS"]

    def test_best_effort_gpu_deterministic_ops(self):
        """BEST_EFFORT_GPU should enable XLA deterministic ops."""
        env_vars = configure_determinism(DeterminismTier.BEST_EFFORT_GPU)

        assert "XLA_FLAGS" in env_vars
        assert "deterministic_ops=true" in env_vars["XLA_FLAGS"]

    def test_nondeterministic_minimal_config(self):
        """NONDETERMINISTIC should have minimal/no config."""
        env_vars = configure_determinism(DeterminismTier.NONDETERMINISTIC)

        assert "JAX_PLATFORMS" not in env_vars
