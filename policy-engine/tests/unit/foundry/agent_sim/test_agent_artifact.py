"""
Tests for AgentPolicyArtifact and EnvironmentFingerprint.

Covers:
1. Round-trip serialization (save -> load -> verify identical)
2. Environment fingerprint mismatch detection
3. Hot-swap compatibility guards
4. Determinism tier validation
"""

from __future__ import annotations

from dataclasses import fields, replace
from decimal import Decimal
from importlib import import_module
from typing import get_args, get_type_hints

import equinox as eqx
import jax
import jax.numpy as jnp
import pytest

from polisyos.core.artifacts.manifest import InputRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import from_canonical_bytes
from polisyos.foundry.agent_sim.actor_critic import ActorCritic
from polisyos.foundry.agent_sim.artifact import (
    AgentPolicyArtifact,
    TrainingMetrics,
    TrainingProfileDescriptor,
    _load_artifact_from_cas,
    store_policy_artifact,
)
from polisyos.foundry.agent_sim.state import GlobalState
from polisyos.foundry.agent_sim.temporal import build_temporal_observations
from polisyos.foundry.agent_sim.temporal_executor import create_temporal_executor
from polisyos.foundry.agent_sim.training import (
    TrainingConfig,
    train_actor_critic_with_artifact,
)
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


def _test_metric_fields() -> tuple[tuple[str, type, bool], ...]:
    """Derive test coverage from the declared dataclass field contract."""

    annotations = get_type_hints(TrainingMetrics)
    supported = {str, int, float}
    result = []
    for metric_field in fields(TrainingMetrics):
        annotation = annotations[metric_field.name]
        args = get_args(annotation)
        optional = False
        if annotation in supported:
            field_type = annotation
        elif len(args) == 2 and type(None) in args:
            field_type = next(arg for arg in args if arg is not type(None))
            optional = True
        else:
            raise AssertionError(f"Unsupported TrainingMetrics field: {metric_field.name}")
        result.append((metric_field.name, field_type, optional))
    return tuple(result)


def _profiled_artifact(artifact: AgentPolicyArtifact, selected: bool) -> AgentPolicyArtifact:
    """Return the same artifact under the requested existing schema contract."""

    if not selected:
        return artifact
    return replace(
        artifact,
        schema_version="1.1",
        training_profile=TrainingProfileDescriptor(),
    )


@pytest.mark.parametrize("profiled", [False, True], ids=["schema-1.0", "schema-1.1"])
def test_generic_cas_writer_stores_finite_metrics_without_mutating_runtime_artifact(
    sample_artifact: AgentPolicyArtifact,
    tmp_path,
    profiled: bool,
) -> None:
    """Finite values become canonical Decimals in a copy for either schema."""

    field_values = {
        name: float(index + 1) / 100
        for index, (name, _field_type, _optional) in enumerate(_test_metric_fields())
        if _field_type is float
    }
    artifact = replace(
        sample_artifact,
        metrics=replace(sample_artifact.metrics, **field_values),
    )
    artifact = _profiled_artifact(artifact, profiled)
    expected = {name: Decimal(str(value)) for name, value in field_values.items()}
    store = FileSystemCAS(tmp_path / f"generic-cas-{profiled}")

    weights_ref, manifest_ref = store_policy_artifact(store, artifact)

    assert store.has(weights_ref)
    assert store.has(manifest_ref)
    payload = from_canonical_bytes(store.get_bytes(manifest_ref))
    assert isinstance(payload, dict)
    assert payload["schema_version"] == artifact.schema_version
    for field_name, value in expected.items():
        assert payload["metrics"][field_name] == value
        assert type(payload["metrics"][field_name]) is Decimal
        runtime_value = getattr(artifact.metrics, field_name)
        assert type(runtime_value) is float
        assert runtime_value == float(value)
    loaded_artifact = _load_artifact_from_cas(store, manifest_ref)
    for field_name, value in expected.items():
        loaded_value = getattr(loaded_artifact.metrics, field_name)
        assert type(loaded_value) is float
        assert loaded_value == float(value)
    if profiled:
        assert payload["training_profile"] == TrainingProfileDescriptor().to_manifest_dict()
    else:
        assert "training_profile" not in payload


def _bad_storage_values(field_type: type) -> tuple[tuple[object, type[Exception], str, str], ...]:
    if field_type is float:
        return (
            (True, TypeError, "real numeric", "bool"),
            ("not-numeric", TypeError, "real numeric", "string"),
            (float("inf"), ValueError, "finite", "positive-infinity"),
            (float("nan"), ValueError, "finite", "nan"),
            (Decimal("NaN"), ValueError, "finite", "decimal-nan"),
        )
    if field_type is int:
        return (
            (True, TypeError, "integer", "bool"),
            (1.5, TypeError, "integer", "float"),
            ("not-integer", TypeError, "integer", "string"),
        )
    return (
        (1, TypeError, "string", "integer"),
        (False, TypeError, "string", "bool"),
    )


@pytest.mark.parametrize(
    ("field_name", "field_type", "bad_value", "error_type", "message"),
    [
        pytest.param(
            field_name,
            field_type,
            bad_value,
            error_type,
            message,
            id=f"{field_name}-{case}",
        )
        for field_name, field_type, _optional in _test_metric_fields()
        for bad_value, error_type, message, case in _bad_storage_values(field_type)
    ],
)
def test_generic_cas_writer_rejects_bad_metrics_before_writing_either_object(
    sample_artifact: AgentPolicyArtifact,
    tmp_path,
    field_name: str,
    field_type: type,
    bad_value: object,
    error_type: type[Exception],
    message: str,
) -> None:
    """Every declared TrainingMetrics field is validated before either CAS write."""

    artifact = replace(
        sample_artifact,
        metrics=replace(sample_artifact.metrics, **{field_name: bad_value}),
    )
    store = FileSystemCAS(tmp_path / f"invalid-metric-cas-{field_name}")

    with pytest.raises(error_type, match=message):
        store_policy_artifact(store, artifact)

    assert not list(store.root.rglob("*.blob"))
    assert not list(store.root.rglob("*.manifest.json"))


@pytest.mark.parametrize(
    "field_name",
    [name for name, _field_type, optional in _test_metric_fields() if not optional],
)
def test_generic_cas_writer_rejects_null_required_metrics_before_writes(
    sample_artifact: AgentPolicyArtifact,
    tmp_path,
    field_name: str,
) -> None:
    """Required nulls cannot leave weights or a manifest in the CAS."""

    artifact = replace(
        sample_artifact,
        metrics=replace(sample_artifact.metrics, **{field_name: None}),
    )
    store = FileSystemCAS(tmp_path / f"missing-required-metric-{field_name}")

    with pytest.raises(TypeError, match="cannot be null"):
        store_policy_artifact(store, artifact)

    assert not list(store.root.rglob("*.blob"))
    assert not list(store.root.rglob("*.manifest.json"))


@pytest.mark.parametrize("profiled", [False, True], ids=["schema-1.0", "schema-1.1"])
def test_generic_cas_writer_preserves_optional_none_and_all_declared_types(
    sample_artifact: AgentPolicyArtifact,
    tmp_path,
    profiled: bool,
) -> None:
    """Optional nulls remain explicit and all present fields round-trip by type."""

    values: dict[str, object] = {}
    expected: dict[str, object] = {}
    for index, (name, field_type, optional) in enumerate(_test_metric_fields()):
        if optional:
            values[name] = None
            expected[name] = None
        elif field_type is str:
            values[name] = f"run-{index}"
            expected[name] = values[name]
        elif field_type is int:
            values[name] = index + 100
            expected[name] = values[name]
        else:
            values[name] = float(index + 1) / 10
            expected[name] = float(values[name])
    artifact = replace(
        sample_artifact,
        metrics=replace(sample_artifact.metrics, **values),
    )
    artifact = _profiled_artifact(artifact, profiled)
    store = FileSystemCAS(tmp_path / f"full-metric-contract-{profiled}")
    _weights_ref, manifest_ref = store_policy_artifact(store, artifact)
    payload = from_canonical_bytes(store.get_bytes(manifest_ref))
    loaded = _load_artifact_from_cas(store, manifest_ref)

    assert isinstance(payload, dict)
    assert loaded.schema_version == artifact.schema_version
    for name, field_type, optional in _test_metric_fields():
        if optional:
            assert name in payload["metrics"]
            assert payload["metrics"][name] is None
            assert getattr(loaded.metrics, name) is None
        elif field_type is float:
            assert type(payload["metrics"][name]) is Decimal
            assert type(getattr(loaded.metrics, name)) is float
            assert getattr(loaded.metrics, name) == expected[name]
        else:
            assert type(payload["metrics"][name]) is type(values[name])
            assert getattr(loaded.metrics, name) == expected[name]
    if profiled:
        assert loaded.training_profile == TrainingProfileDescriptor()
    else:
        assert loaded.training_profile is None


def _put_raw_manifest(store, artifact, manifest):
    """Write an old or malformed manifest directly to exercise the real CAS reader."""

    weights_ref = store.put_bytes(
        artifact.weights_bytes,
        PutOptions(kind="foundry.agent_policy", media_type="application/octet-stream"),
    )
    manifest_ref = store.put_json(
        manifest,
        PutOptions(
            kind="foundry.agent_policy_manifest",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.foundry.AgentPolicyArtifact",
                version=artifact.schema_version,
            ),
            inputs=[InputRef(artifact_id=weights_ref.artifact_id, role="weights")],
        ),
    )
    return manifest_ref


@pytest.mark.parametrize("profiled", [False, True], ids=["schema-1.0", "schema-1.1"])
def test_actual_cas_reader_allows_missing_optional_fields_as_none(
    sample_artifact: AgentPolicyArtifact,
    tmp_path,
    profiled: bool,
) -> None:
    """Omitted optional keys remain compatible with the declared optional fields."""

    artifact = _profiled_artifact(sample_artifact, profiled)
    manifest = artifact.to_manifest_dict()
    for name, field_type, optional in _test_metric_fields():
        value = manifest["metrics"].get(name)
        if field_type is float and value is not None:
            manifest["metrics"][name] = Decimal(str(value))
        if optional:
            manifest["metrics"].pop(name)
    store = FileSystemCAS(tmp_path / f"reader-absent-optional-{profiled}")
    manifest_ref = _put_raw_manifest(store, artifact, manifest)

    loaded = _load_artifact_from_cas(store, manifest_ref)

    for name, _field_type, optional in _test_metric_fields():
        if optional:
            assert getattr(loaded.metrics, name) is None


def test_actual_cas_reader_preserves_schema_1_0_absent_metrics_compatibility(
    sample_artifact: AgentPolicyArtifact,
    tmp_path,
) -> None:
    """A wholly absent legacy metrics block maps only to historical placeholders."""

    artifact = replace(sample_artifact, schema_version="1.0", training_profile=None)
    manifest = artifact.to_manifest_dict()
    manifest.pop("metrics")
    store = FileSystemCAS(tmp_path / "reader-legacy-absent-metrics")
    manifest_ref = _put_raw_manifest(store, artifact, manifest)

    loaded = _load_artifact_from_cas(store, manifest_ref)

    assert loaded.metrics == TrainingMetrics(
        training_run_id="unknown",
        training_steps=0,
        final_loss=0.0,
    )
    assert loaded.training_profile is None


def test_actual_cas_reader_rejects_schema_1_1_absent_metrics(
    sample_artifact: AgentPolicyArtifact,
    tmp_path,
) -> None:
    """The schema-1.0 compatibility projection never becomes a 1.1 fallback."""

    artifact = _profiled_artifact(sample_artifact, True)
    manifest = artifact.to_manifest_dict()
    manifest.pop("metrics")
    store = FileSystemCAS(tmp_path / "reader-schema-11-absent-metrics")
    manifest_ref = _put_raw_manifest(store, artifact, manifest)

    with pytest.raises(TypeError, match="require a metrics block"):
        _load_artifact_from_cas(store, manifest_ref)


@pytest.mark.parametrize(
    "metrics_value",
    [pytest.param(None, id="present-null"), pytest.param({}, id="present-empty")],
)
def test_actual_cas_reader_rejects_present_null_or_empty_metrics_block(
    sample_artifact: AgentPolicyArtifact,
    tmp_path,
    metrics_value: object,
) -> None:
    """Presence is distinct from absence: malformed supplied blocks fail closed."""

    manifest = sample_artifact.to_manifest_dict()
    manifest["metrics"] = metrics_value
    store = FileSystemCAS(tmp_path / f"reader-present-malformed-{metrics_value is None}")
    manifest_ref = _put_raw_manifest(store, sample_artifact, manifest)

    with pytest.raises(TypeError):
        _load_artifact_from_cas(store, manifest_ref)


@pytest.mark.parametrize(
    "field_name",
    [name for name, _field_type, optional in _test_metric_fields() if not optional],
)
def test_actual_cas_reader_rejects_null_required_metric(
    sample_artifact: AgentPolicyArtifact,
    tmp_path,
    field_name: str,
) -> None:
    """A supplied null required metric is not treated as an absent legacy block."""

    manifest = sample_artifact.to_manifest_dict()
    for name, field_type, _optional in _test_metric_fields():
        value = manifest["metrics"].get(name)
        if field_type is float and value is not None:
            manifest["metrics"][name] = Decimal(str(value))
    manifest["metrics"][field_name] = None
    store = FileSystemCAS(tmp_path / f"reader-null-required-{field_name}")
    manifest_ref = _put_raw_manifest(store, sample_artifact, manifest)

    with pytest.raises(TypeError, match="cannot be null"):
        _load_artifact_from_cas(store, manifest_ref)


@pytest.mark.parametrize(
    "field_name",
    [name for name, _field_type, optional in _test_metric_fields() if not optional],
)
def test_actual_cas_reader_rejects_missing_required_metric(
    sample_artifact: AgentPolicyArtifact,
    tmp_path,
    field_name: str,
) -> None:
    """The persisted reader does not invent defaults for absent required fields."""

    manifest = sample_artifact.to_manifest_dict()
    for name, field_type, optional in _test_metric_fields():
        if field_type is float:
            value = manifest["metrics"].get(name)
            if value is not None:
                manifest["metrics"][name] = Decimal(str(value))
    manifest["metrics"].pop(field_name)
    store = FileSystemCAS(tmp_path / f"reader-missing-required-{field_name}")
    manifest_ref = _put_raw_manifest(store, sample_artifact, manifest)

    with pytest.raises(TypeError, match="is missing"):
        _load_artifact_from_cas(store, manifest_ref)


@pytest.mark.parametrize(
    ("field_name", "bad_value"),
    [
        pytest.param(
            field_name,
            bad_value,
            id=f"{field_name}-wrong-type",
        )
        for field_name, field_type, _optional in _test_metric_fields()
        for bad_value in (
            (1 if field_type is str else "not-an-integer" if field_type is int else "not-a-number"),
        )
    ],
)
def test_actual_cas_reader_rejects_malformed_declared_metric_types(
    sample_artifact: AgentPolicyArtifact,
    tmp_path,
    field_name: str,
    bad_value: object,
) -> None:
    """The actual CAS reader rejects a representative wrong type for every field."""

    manifest = sample_artifact.to_manifest_dict()
    for name, field_type, optional in _test_metric_fields():
        value = manifest["metrics"].get(name)
        if field_type is float and value is not None:
            manifest["metrics"][name] = Decimal(str(value))
    manifest["metrics"][field_name] = bad_value
    store = FileSystemCAS(tmp_path / f"reader-wrong-type-{field_name}")
    manifest_ref = _put_raw_manifest(store, sample_artifact, manifest)

    with pytest.raises(TypeError):
        _load_artifact_from_cas(store, manifest_ref)


@pytest.mark.parametrize("profiled", [False, True], ids=["schema-1.0", "schema-1.1"])
def test_legacy_integer_float_metrics_read_as_runtime_floats(
    sample_artifact: AgentPolicyArtifact,
    tmp_path,
    profiled: bool,
) -> None:
    """Existing integer encodings for float-typed fields restore as Python floats."""

    artifact = _profiled_artifact(sample_artifact, profiled)
    manifest = artifact.to_manifest_dict()
    field_values = {
        name: index + 10
        for index, (name, field_type, _optional) in enumerate(_test_metric_fields())
        if field_type is float
    }
    manifest["metrics"].update(field_values)
    store = FileSystemCAS(tmp_path / f"legacy-integer-metrics-{profiled}")
    manifest_ref = _put_raw_manifest(store, artifact, manifest)

    loaded = _load_artifact_from_cas(store, manifest_ref)

    assert loaded.schema_version == artifact.schema_version
    if profiled:
        assert loaded.training_profile == TrainingProfileDescriptor()
    else:
        assert loaded.training_profile is None
    for name, field_type, _optional in _test_metric_fields():
        if field_type is float:
            assert type(getattr(loaded.metrics, name)) is float
            assert getattr(loaded.metrics, name) == float(field_values[name])


def test_legacy_numeric_string_training_steps_read_compatibility_is_explicit(
    sample_artifact: AgentPolicyArtifact,
    tmp_path,
) -> None:
    """The existing training_steps int-string reader cast remains supported."""

    manifest = sample_artifact.to_manifest_dict()
    for name, field_type, _optional in _test_metric_fields():
        value = manifest["metrics"].get(name)
        if field_type is float and value is not None:
            manifest["metrics"][name] = Decimal(str(value))
    manifest["metrics"]["training_steps"] = "123"
    store = FileSystemCAS(tmp_path / "legacy-training-step-string")
    manifest_ref = _put_raw_manifest(store, sample_artifact, manifest)

    loaded = _load_artifact_from_cas(store, manifest_ref)

    assert loaded.metrics.training_steps == 123
    assert type(loaded.metrics.training_steps) is int


def test_native_training_with_cas_stores_manifest_copy_and_returns_runtime_floats(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The native train(cas=...) path writes through the shared artifact owner."""

    state = GlobalState.empty(
        n_agents=4,
        simulation_horizon=4,
        max_agents=4,
        seed=23,
    )
    observations = build_temporal_observations(
        state,
        horizon=4,
        include_expectations=False,
    )
    actor = ActorCritic(
        key=jax.random.PRNGKey(23),
        obs_dim=observations.shape[-1],
        action_dim=1,
        hidden_dims=(8,),
    )
    config = TrainingConfig(
        n_episodes=1,
        steps_per_episode=1,
        horizon=4,
        ppo_epochs=1,
        include_expectations=False,
    )
    store = FileSystemCAS(tmp_path / "native-train-cas")
    training_module = import_module("polisyos.foundry.agent_sim.training")
    original_writer = training_module._store_artifact_in_cas
    written_refs = []

    def record_writer(cas, artifact):
        refs = original_writer(cas, artifact)
        written_refs.append(refs)
        return refs

    monkeypatch.setattr(training_module, "_store_artifact_in_cas", record_writer)

    _, _, artifact = train_actor_critic_with_artifact(
        actor,
        state,
        config,
        make_executor=lambda policy: create_temporal_executor(
            policy,
            horizon=config.horizon,
            include_expectations=config.include_expectations,
        ),
        run_id="native-cas-metrics",
        seed=23,
        cas=store,
    )

    assert artifact.schema_version == "1.0"
    assert artifact.training_profile is None
    assert type(artifact.metrics.final_loss) is float
    assert artifact.metrics.best_loss is not None
    assert type(artifact.metrics.best_loss) is float
    assert len(written_refs) == 1
    weights_ref, manifest_ref = written_refs[0]
    assert store.has(weights_ref)
    assert store.has(manifest_ref)
    payload = from_canonical_bytes(store.get_bytes(manifest_ref))
    assert isinstance(payload, dict)
    assert type(payload["metrics"]["final_loss"]) is Decimal
    assert payload["metrics"]["final_loss"] == Decimal(str(artifact.metrics.final_loss))
    assert type(payload["metrics"]["learning_rate"]) is Decimal
    assert payload["metrics"]["learning_rate"] == Decimal(str(config.learning_rate))
