"""
Unit tests for method execution artifacts.

Tests verify:
- Source change detection (comment changes alter hash)
- Deterministic hashing (same input → same hash)
- Manifest generation compatibility with Core CAS
- Edge case handling (unavailable source, etc.)
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any, ClassVar
from uuid import uuid4

import pytest

from polisyos.foundry.methods.artifacts import (
    ChainArtifact,
    ChainNodeRecord,
    DeviceInfo,
    ExecutionEvidence,
    MethodArtifact,
    MethodTiming,
    SlotBindingRecord,
    compute_source_fingerprint,
    compute_source_hash,
)
from polisyos.foundry.methods.base import (
    ComplexityClass,
    FidelityLevel,
    MethodMetadata,
    MethodSignature,
    ParameterSpec,
    SlotSpec,
    SlotType,
    Unit,
)
from polisyos.foundry.methods.specialization import (
    BackendSpec,
    ShapeSpec,
    Specialization,
)

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def sample_unit() -> Unit:
    """Create a sample unit for testing."""
    return Unit(dimension="currency", symbol="USD")


@pytest.fixture
def sample_signature(sample_unit: Unit) -> MethodSignature:
    """Create a sample method signature."""
    return MethodSignature(
        name="flat_tax",
        namespace="fiscal.taxation",
        version="1.0.0",
        input_slots=frozenset(
            {
                SlotSpec(name="income", slot_type=SlotType.VECTOR, unit=sample_unit),
            }
        ),
        output_slots=frozenset(
            {
                SlotSpec(name="tax_amount", slot_type=SlotType.VECTOR, unit=sample_unit),
            }
        ),
        parameters=(ParameterSpec(name="rate", default=0.15, bounds=(0.0, 1.0), is_static=True),),
        fidelity=FidelityLevel.LOW,
        complexity=ComplexityClass.O_N,
    )


@pytest.fixture
def sample_metadata() -> MethodMetadata:
    """Create sample method metadata."""
    return MethodMetadata(
        description="Simple flat tax calculation",
        tags=frozenset({"fiscal", "taxation"}),
    )


@pytest.fixture
def sample_specialization() -> Specialization:
    """Create a sample specialization."""
    return Specialization(
        method_fqn="fiscal.taxation.flat_tax@1.0.0",
        static_params_hash="a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",
        input_shapes=(("income", ShapeSpec(shape=(1000,), dtype="float32")),),
        backend=BackendSpec(
            platform="cpu",
            device_count=1,
            precision="float32",
            xla_flags=frozenset(),
            device_kinds=("cpu",),
            jax_version="0.4.20",
            jaxlib_version="0.4.20",
            config_fingerprint="default",
        ),
        jit_enabled=True,
        vmap_axis=None,
    )


def create_mock_method_class(
    signature: MethodSignature,
    metadata: MethodMetadata,
    source_content: str = "default",
) -> type:
    """
    Create a mock method class with customizable source.

    Note: The source_content parameter doesn't actually change the source
    that inspect.getsource() returns, but we use it to test the hashing
    logic by creating distinct classes.
    """
    signature_value = signature
    metadata_value = metadata

    class MockMethod:
        signature: ClassVar[MethodSignature] = signature_value
        metadata: ClassVar[MethodMetadata] = metadata_value

        @staticmethod
        def pure_step(state: Any, params: Mapping[str, Any]) -> Any:
            return state

    MockMethod.__name__ = f"MockMethod_{hash(source_content) % 10000}"
    return MockMethod


# =============================================================================
# Source Hash Tests
# =============================================================================


class TestComputeSourceHash:
    """Tests for compute_source_hash function."""

    def test_returns_hash_for_regular_class(self):
        """Regular classes should return a valid hash."""

        class TestClass:
            def method(self):
                pass

        result = compute_source_hash(TestClass)

        assert isinstance(result, str)
        assert len(result) == 32
        assert all(c in "0123456789abcdef" for c in result)

    def test_returns_fallback_for_builtin(self):
        """Built-in classes should return fallback value."""
        result = compute_source_hash(dict)
        assert result == "unavailable"

    def test_custom_fallback_value(self):
        """Should use custom fallback when provided."""
        result = compute_source_hash(dict, fallback_value="custom_fallback")
        assert result == "custom_fallback"

    def test_hash_changes_with_source(self):
        """Different source code should produce different hashes."""

        class ClassV1:
            def method(self):
                return 1

        class ClassV2:
            def method(self):
                return 2

        hash1 = compute_source_hash(ClassV1)
        hash2 = compute_source_hash(ClassV2)

        assert hash1 != hash2

    def test_comment_changes_hash(self):
        """Even comment changes should alter the hash."""

        class ClassWithComment:
            # This is a comment
            def method(self):
                return 1

        class ClassNoComment:
            def method(self):
                return 1

        hash1 = compute_source_hash(ClassWithComment)
        hash2 = compute_source_hash(ClassNoComment)

        assert hash1 != hash2

    def test_hash_is_deterministic(self):
        """Same class should always produce same hash."""

        class StableClass:
            def method(self):
                return 42

        hash1 = compute_source_hash(StableClass)
        hash2 = compute_source_hash(StableClass)

        assert hash1 == hash2

    def test_source_fingerprint_strategy(self):
        """Fingerprint should include a viable strategy."""

        class FingerprintClass:
            def method(self):
                return 1

        fp = compute_source_fingerprint(FingerprintClass)

        assert fp.strategy in {"inspect", "file_sha256", "git_tree", "unavailable"}


# =============================================================================
# MethodArtifact Tests
# =============================================================================


class TestMethodArtifact:
    """Tests for MethodArtifact creation and serialization."""

    def test_from_method_creates_valid_artifact(
        self,
        sample_signature: MethodSignature,
        sample_metadata: MethodMetadata,
        sample_specialization: Specialization,
    ):
        """from_method should create a valid artifact."""
        method_class = create_mock_method_class(sample_signature, sample_metadata)

        artifact = MethodArtifact.from_method(method_class, sample_specialization)

        assert artifact.fqn == "fiscal.taxation.flat_tax@1.0.0"
        assert len(artifact.signature_hash) == 32
        assert len(artifact.metadata_hash) == 32
        assert artifact.source_module == method_class.__module__
        assert artifact.specialization == sample_specialization
        assert isinstance(artifact.compiled_at, datetime)
        assert artifact.source_fingerprint.strategy

    def test_deterministic_hashing_ignores_timestamps(
        self,
        sample_signature: MethodSignature,
        sample_metadata: MethodMetadata,
        sample_specialization: Specialization,
    ):
        """Artifacts with different compiled_at should share the same ID."""
        method_class = create_mock_method_class(sample_signature, sample_metadata)

        fixed_time = datetime(2025, 1, 15, 10, 30, 0, tzinfo=UTC)
        later_time = fixed_time + timedelta(seconds=30)

        artifact1 = MethodArtifact.from_method(
            method_class, sample_specialization, compiled_at=fixed_time
        )
        artifact2 = MethodArtifact.from_method(
            method_class, sample_specialization, compiled_at=later_time
        )

        assert artifact1.artifact_id == artifact2.artifact_id
        assert artifact1.to_canonical_bytes() == artifact2.to_canonical_bytes()

    def test_to_manifest_produces_valid_structure(
        self,
        sample_signature: MethodSignature,
        sample_metadata: MethodMetadata,
        sample_specialization: Specialization,
    ):
        """to_manifest should produce valid ArtifactManifest."""
        method_class = create_mock_method_class(sample_signature, sample_metadata)

        artifact = MethodArtifact.from_method(method_class, sample_specialization)
        manifest = artifact.to_manifest()

        assert manifest.kind == "foundry.method_artifact"
        assert manifest.media_type == "application/json"
        assert manifest.byte_size > 0
        assert manifest.artifact_schema is not None
        assert manifest.artifact_schema.name == "polisyos.foundry.method_artifact"
        assert manifest.integrity is not None
        assert len(manifest.integrity.sha256) == 64

    def test_source_unavailable_flag(
        self,
        sample_signature: MethodSignature,
        sample_metadata: MethodMetadata,
        sample_specialization: Specialization,
    ):
        """Artifact should track when source is unavailable."""
        method_class = create_mock_method_class(sample_signature, sample_metadata)

        artifact = MethodArtifact.from_method(method_class, sample_specialization)

        assert artifact.source_available is True
        assert artifact.source_hash != "unavailable"


# =============================================================================
# ChainArtifact Tests
# =============================================================================


class TestSlotBindingRecord:
    """Tests for SlotBindingRecord."""

    def test_to_dict(self):
        """to_dict should produce serializable dictionary."""
        record = SlotBindingRecord(
            source_method="method.a@1.0.0",
            source_slot="output",
            target_method="method.b@1.0.0",
            target_slot="input",
            source_node_id="uuid-123",
            target_node_id="uuid-456",
            conversion_factor=1.0,
            requires_fx_rate=False,
        )

        result = record.to_dict()

        assert result["source_method"] == "method.a@1.0.0"
        assert result["source_slot"] == "output"
        assert result["target_method"] == "method.b@1.0.0"
        assert result["target_slot"] == "input"
        assert result["conversion_factor"]["_type"] == "float_hex"


class TestChainArtifact:
    """Tests for ChainArtifact."""

    def test_chain_hash_is_deterministic(self):
        """Chain hash should be deterministic for same topology."""
        nodes = (
            ChainNodeRecord(
                node_id="a|hash|0",
                method_fqn="a@1.0.0",
                method_artifact_id="a" * 64,
                static_params_hash="s1",
                instance_index=0,
            ),
            ChainNodeRecord(
                node_id="b|hash|0",
                method_fqn="b@1.0.0",
                method_artifact_id="b" * 64,
                static_params_hash="s2",
                instance_index=0,
            ),
        )
        bindings = (
            SlotBindingRecord(
                source_method="a@1.0.0",
                source_slot="out",
                target_method="b@1.0.0",
                target_slot="in",
                source_node_id="a|hash|0",
                target_node_id="b|hash|0",
                conversion_factor=1.0,
            ),
        )

        chain_hash1 = ChainArtifact._compute_chain_hash(nodes, bindings)
        chain_hash2 = ChainArtifact._compute_chain_hash(nodes, bindings)

        assert chain_hash1 == chain_hash2

    def test_different_topology_different_hash(self):
        """Different topologies should produce different hashes."""
        nodes = (
            ChainNodeRecord(
                node_id="a|hash|0",
                method_fqn="a@1.0.0",
                method_artifact_id="a" * 64,
                static_params_hash="s1",
                instance_index=0,
            ),
            ChainNodeRecord(
                node_id="b|hash|0",
                method_fqn="b@1.0.0",
                method_artifact_id="b" * 64,
                static_params_hash="s2",
                instance_index=0,
            ),
            ChainNodeRecord(
                node_id="c|hash|0",
                method_fqn="c@1.0.0",
                method_artifact_id="c" * 64,
                static_params_hash="s3",
                instance_index=0,
            ),
        )
        bindings1 = (
            SlotBindingRecord(
                source_method="a@1.0.0",
                source_slot="out",
                target_method="b@1.0.0",
                target_slot="in",
                source_node_id="a|hash|0",
                target_node_id="b|hash|0",
            ),
        )
        bindings2 = (
            SlotBindingRecord(
                source_method="a@1.0.0",
                source_slot="out",
                target_method="c@1.0.0",
                target_slot="in",
                source_node_id="a|hash|0",
                target_node_id="c|hash|0",
            ),
        )

        hash1 = ChainArtifact._compute_chain_hash(nodes, bindings1)
        hash2 = ChainArtifact._compute_chain_hash(nodes, bindings2)

        assert hash1 != hash2

    def test_to_manifest_includes_inputs(self):
        """Manifest should include method artifacts as inputs."""
        nodes = (
            ChainNodeRecord(
                node_id="a|hash|0",
                method_fqn="a@1.0.0",
                method_artifact_id="a" * 64,
                static_params_hash="s1",
                instance_index=0,
            ),
            ChainNodeRecord(
                node_id="b|hash|0",
                method_fqn="b@1.0.0",
                method_artifact_id="b" * 64,
                static_params_hash="s2",
                instance_index=0,
            ),
        )
        bindings = (
            SlotBindingRecord(
                source_method="a@1.0.0",
                source_slot="out",
                target_method="b@1.0.0",
                target_slot="in",
                source_node_id="a|hash|0",
                target_node_id="b|hash|0",
            ),
        )
        fixed_time = datetime(2025, 1, 15, tzinfo=UTC)

        artifact = ChainArtifact(
            chain_id=uuid4(),
            chain_hash=ChainArtifact._compute_chain_hash(nodes, bindings),
            topology_hash=ChainArtifact._compute_topology_hash(nodes, bindings),
            method_fqns=("a@1.0.0", "b@1.0.0"),
            method_artifact_ids=("a" * 64, "b" * 64),
            nodes=nodes,
            bindings=bindings,
            execution_order=("a|hash|0", "b|hash|0"),
            composed_at=fixed_time,
            warnings=(),
        )

        manifest = artifact.to_manifest()

        assert len(manifest.inputs) == 2
        assert all(inp.role == "method" for inp in manifest.inputs)

    def test_method_count_property(self):
        """method_count should return number of methods."""
        nodes = (
            ChainNodeRecord(
                node_id="a|hash|0",
                method_fqn="a@1.0.0",
                method_artifact_id="a" * 64,
                static_params_hash="s1",
                instance_index=0,
            ),
            ChainNodeRecord(
                node_id="b|hash|0",
                method_fqn="b@1.0.0",
                method_artifact_id="b" * 64,
                static_params_hash="s2",
                instance_index=0,
            ),
            ChainNodeRecord(
                node_id="c|hash|0",
                method_fqn="c@1.0.0",
                method_artifact_id="c" * 64,
                static_params_hash="s3",
                instance_index=0,
            ),
        )
        artifact = ChainArtifact(
            chain_id=uuid4(),
            chain_hash=ChainArtifact._compute_chain_hash(nodes, ()),
            topology_hash=ChainArtifact._compute_topology_hash(nodes, ()),
            method_fqns=("a@1.0.0", "b@1.0.0", "c@1.0.0"),
            method_artifact_ids=("a" * 64, "b" * 64, "c" * 64),
            nodes=nodes,
            bindings=(),
            execution_order=("a|hash|0", "b|hash|0", "c|hash|0"),
            composed_at=datetime.now(UTC),
            warnings=(),
        )

        assert artifact.method_count == 3


# =============================================================================
# ExecutionEvidence Tests
# =============================================================================


class TestExecutionEvidence:
    """Tests for ExecutionEvidence."""

    def test_create_sets_all_fields(self):
        """create() should properly set all fields."""
        started = datetime(2025, 1, 15, 10, 0, 0, tzinfo=UTC)
        completed = datetime(2025, 1, 15, 10, 0, 5, tzinfo=UTC)
        device_info = DeviceInfo(
            platform="cpu",
            device_count=1,
            precision="float32",
            jax_version="0.4.20",
            jaxlib_version="0.4.20",
        )

        evidence = ExecutionEvidence.create(
            chain_artifact_id="c" * 64,
            input_state_hash="input_hash_abc",
            input_params_hash="params_hash_def",
            output_state_hash="output_hash_ghi",
            started_at=started,
            completed_at=completed,
            method_timings=[
                MethodTiming("a@1.0.0", "node1", 2.5),
                MethodTiming("b@1.0.0", "node2", 2.5),
            ],
            rng_key_used=(42, 0),
            device_info=device_info,
        )

        assert evidence.chain_artifact_id == "c" * 64
        assert evidence.input_state_hash == "input_hash_abc"
        assert evidence.output_state_hash == "output_hash_ghi"
        assert evidence.duration_seconds == 5.0
        assert len(evidence.method_timings) == 2
        assert evidence.rng_key_used == (42, 0)
        assert evidence.success is True

    def test_duration_seconds_computed(self):
        """duration_seconds should be computed from timestamps."""
        started = datetime(2025, 1, 15, 10, 0, 0, tzinfo=UTC)
        completed = datetime(2025, 1, 15, 10, 0, 10, tzinfo=UTC)

        evidence = ExecutionEvidence.create(
            chain_artifact_id="c" * 64,
            input_state_hash="in",
            input_params_hash="params",
            output_state_hash="out",
            started_at=started,
            completed_at=completed,
            method_timings=[],
            device_info=DeviceInfo(
                platform="cpu",
                device_count=1,
                precision="float32",
                jax_version="0.4.20",
                jaxlib_version="0.4.20",
            ),
        )

        assert evidence.duration_seconds == 10.0

    def test_to_manifest_includes_chain_as_input(self):
        """Manifest should include chain artifact as input."""
        chain_id = "a" * 64

        evidence = ExecutionEvidence.create(
            chain_artifact_id=chain_id,
            input_state_hash="in",
            input_params_hash="params",
            output_state_hash="out",
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
            method_timings=[],
            input_state_artifact_ids=["b" * 64],
            output_state_artifact_ids=["c" * 64],
            params_artifact_id="d" * 64,
            device_info=DeviceInfo(
                platform="cpu",
                device_count=1,
                precision="float32",
                jax_version="0.4.20",
                jaxlib_version="0.4.20",
            ),
        )

        manifest = evidence.to_manifest()

        roles = [inp.role for inp in manifest.inputs]
        assert "chain" in roles
        assert "input_state" in roles
        assert "output_state" in roles
        assert "params" in roles

    def test_failed_execution(self):
        """Should properly record failed executions."""
        evidence = ExecutionEvidence.create(
            chain_artifact_id="c" * 64,
            input_state_hash="in",
            input_params_hash="params",
            output_state_hash="",
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
            method_timings=[],
            success=False,
            error_message="Division by zero in method a@1.0.0",
            device_info=DeviceInfo(
                platform="cpu",
                device_count=1,
                precision="float32",
                jax_version="0.4.20",
                jaxlib_version="0.4.20",
            ),
        )

        assert evidence.success is False
        assert "Division by zero" in evidence.error_message


class TestDeviceInfo:
    """Tests for DeviceInfo."""

    def test_to_dict(self):
        """to_dict should produce serializable dictionary."""
        info = DeviceInfo(
            platform="cpu",
            device_count=1,
            precision="float32",
            jax_version="0.4.20",
            jaxlib_version="0.4.20",
        )

        result = info.to_dict()

        assert result["platform"] == "cpu"
        assert result["device_count"] == 1
        assert result["precision"] == "float32"


class TestMethodTiming:
    """Tests for MethodTiming."""

    def test_to_dict_without_jit_time(self):
        """to_dict should handle None jit_compile_time."""
        timing = MethodTiming(
            method_fqn="a@1.0.0",
            node_id="node1",
            duration_seconds=1.5,
        )

        result = timing.to_dict()

        assert "jit_compile_time_seconds" not in result

    def test_to_dict_with_jit_time(self):
        """to_dict should include jit time when present."""
        timing = MethodTiming(
            method_fqn="a@1.0.0",
            node_id="node1",
            duration_seconds=1.5,
            jit_compile_time_seconds=0.5,
        )

        result = timing.to_dict()

        assert result["jit_compile_time_seconds"]["_type"] == "float_hex"


# =============================================================================
# Integration Tests
# =============================================================================


class TestArtifactIntegration:
    """Integration tests for artifact workflow."""

    def test_full_artifact_chain(
        self,
        sample_signature: MethodSignature,
        sample_metadata: MethodMetadata,
        sample_specialization: Specialization,
    ):
        """Test creating a full artifact chain: Method → Chain → Evidence."""
        method_class = create_mock_method_class(sample_signature, sample_metadata)
        method_artifact = MethodArtifact.from_method(method_class, sample_specialization)

        nodes = (
            ChainNodeRecord(
                node_id="node1",
                method_fqn=method_artifact.fqn,
                method_artifact_id=method_artifact.artifact_id,
                static_params_hash=sample_specialization.static_params_hash,
                instance_index=0,
            ),
            ChainNodeRecord(
                node_id="node2",
                method_fqn="budget.revenue@1.0.0",
                method_artifact_id="b" * 64,
                static_params_hash="static2",
                instance_index=0,
            ),
        )
        bindings = (
            SlotBindingRecord(
                source_method=method_artifact.fqn,
                source_slot="tax_amount",
                target_method="budget.revenue@1.0.0",
                target_slot="income",
                source_node_id="node1",
                target_node_id="node2",
            ),
        )

        chain_artifact = ChainArtifact(
            chain_id=uuid4(),
            chain_hash=ChainArtifact._compute_chain_hash(nodes, bindings),
            topology_hash=ChainArtifact._compute_topology_hash(nodes, bindings),
            method_fqns=(method_artifact.fqn, "budget.revenue@1.0.0"),
            method_artifact_ids=(method_artifact.artifact_id, "b" * 64),
            nodes=nodes,
            bindings=bindings,
            execution_order=("node1", "node2"),
            composed_at=datetime.now(UTC),
            warnings=(),
        )

        evidence = ExecutionEvidence.create(
            chain_artifact_id=chain_artifact.artifact_id,
            input_state_hash="input_hash",
            input_params_hash="params_hash",
            output_state_hash="output_hash",
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
            method_timings=[
                MethodTiming(method_artifact.fqn, "node1", 0.5),
            ],
            device_info=DeviceInfo(
                platform="cpu",
                device_count=1,
                precision="float32",
                jax_version="0.4.20",
                jaxlib_version="0.4.20",
            ),
        )

        assert evidence.chain_artifact_id == chain_artifact.artifact_id
        assert method_artifact.artifact_id in chain_artifact.method_artifact_ids

        method_manifest = method_artifact.to_manifest()
        chain_manifest = chain_artifact.to_manifest()
        evidence_manifest = evidence.to_manifest()

        assert method_manifest.kind == "foundry.method_artifact"
        assert chain_manifest.kind == "foundry.chain_artifact"
        assert evidence_manifest.kind == "foundry.execution_evidence"
