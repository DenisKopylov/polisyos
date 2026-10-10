"""
Tests for MethodRegistry and version resolution.

Test Coverage:
- Singleton pattern behavior
- Thread-safe concurrent registration
- Version resolution policies (EXACT, LATEST, LATEST_COMPATIBLE, PINNED)
- Lazy loading deferred instantiation
- Secondary index queries
- Edge cases and error handling
"""

from __future__ import annotations

import concurrent.futures
import threading
import time
from collections.abc import Mapping
from typing import Any, ClassVar
from unittest.mock import MagicMock

import pytest

from polisyos.foundry.methods.base import (
    ComplexityClass,
    FidelityLevel,
    FoundryMethod,
    MethodMetadata,
    MethodSignature,
    ParameterSpec,
    SlotSpec,
    SlotType,
    Unit,
)
from polisyos.foundry.methods.exceptions import (
    MethodAlreadyRegisteredError,
    MethodNotFoundError,
    ResolutionError,
)
from polisyos.foundry.methods.registry import (
    MethodRegistry,
    get_registry,
    get_registry_audit_log,
)
from polisyos.foundry.methods.resolution import (
    ResolutionPolicy,
    VersionConstraint,
    compare_versions,
    find_compatible_versions,
    is_compatible_upgrade,
    resolve_version,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture(autouse=True)
def reset_registry():
    """Reset registry singleton before and after each test."""
    MethodRegistry.reset_instance()
    yield
    MethodRegistry.reset_instance()


@pytest.fixture
def sample_unit() -> Unit:
    """Sample unit for slot specs."""
    return Unit(dimension="currency", symbol="USD")


@pytest.fixture
def unitless() -> Unit:
    """Unitless unit for generic slots."""
    return Unit(dimension="none", symbol="1")


@pytest.fixture
def income_slot(sample_unit: Unit) -> SlotSpec:
    """Sample income input slot."""
    return SlotSpec(
        name="income",
        slot_type=SlotType.VECTOR,
        unit=sample_unit,
        shape=("n_agents",),
        description="Agent incomes",
    )


@pytest.fixture
def tax_slot(sample_unit: Unit) -> SlotSpec:
    """Sample tax output slot."""
    return SlotSpec(
        name="tax_due",
        slot_type=SlotType.VECTOR,
        unit=sample_unit,
        shape=("n_agents",),
        description="Computed tax",
    )


@pytest.fixture
def rate_param() -> ParameterSpec:
    """Sample parameter spec."""
    return ParameterSpec(name="rate", default=0.15, bounds=(0.0, 1.0))


def create_method_signature(
    name: str,
    namespace: str,
    version: str,
    input_slots: frozenset[SlotSpec],
    output_slots: frozenset[SlotSpec],
    parameters: tuple[ParameterSpec, ...] = (),
) -> MethodSignature:
    """Helper to create method signatures."""
    return MethodSignature(
        name=name,
        namespace=namespace,
        version=version,
        input_slots=input_slots,
        output_slots=output_slots,
        parameters=parameters,
        fidelity=FidelityLevel.LOW,
        complexity=ComplexityClass.O_N,
    )


def create_mock_method(
    name: str,
    namespace: str,
    version: str,
    tags: frozenset[str] | None = None,
    input_slots: frozenset[SlotSpec] | None = None,
    output_slots: frozenset[SlotSpec] | None = None,
) -> type[FoundryMethod]:
    """
    Create a mock method class for testing.

    Returns a class that satisfies the FoundryMethod protocol.
    """
    if input_slots is None:
        unit = Unit("none", "1")
        input_slots = frozenset({SlotSpec(name="input", slot_type=SlotType.SCALAR, unit=unit)})
    if output_slots is None:
        unit = Unit("none", "1")
        output_slots = frozenset({SlotSpec(name="output", slot_type=SlotType.SCALAR, unit=unit)})

    sig = MethodSignature(
        name=name,
        namespace=namespace,
        version=version,
        input_slots=input_slots,
        output_slots=output_slots,
        parameters=(),
        fidelity=FidelityLevel.LOW,
        complexity=ComplexityClass.O_1,
    )

    meta = MethodMetadata(
        description=f"Mock method {name}",
        tags=tags or frozenset(),
    )

    class MockMethod:
        signature: ClassVar[MethodSignature] = sig
        metadata: ClassVar[MethodMetadata] = meta

        @staticmethod
        def pure_step(state: Any, params: Mapping[str, Any]) -> Any:
            return state

    MockMethod.__name__ = f"Mock_{namespace}_{name}_{version}".replace(".", "_")

    return MockMethod  # type: ignore[return-value]


# =============================================================================
# Resolution Module Tests
# =============================================================================


class TestVersionConstraint:
    """Tests for VersionConstraint dataclass."""

    def test_major_only_matches_any_minor_patch(self):
        constraint = VersionConstraint(major=1)
        assert constraint.matches("1.0.0")
        assert constraint.matches("1.5.0")
        assert constraint.matches("1.99.99")
        assert not constraint.matches("0.1.0")
        assert not constraint.matches("2.0.0")

    def test_major_minor_matches_gte_minor(self):
        constraint = VersionConstraint(major=1, minor=2)
        assert constraint.matches("1.2.0")
        assert constraint.matches("1.2.5")
        assert constraint.matches("1.5.0")
        assert not constraint.matches("1.1.0")
        assert not constraint.matches("1.1.99")
        assert not constraint.matches("0.2.0")
        assert not constraint.matches("2.2.0")

    def test_major_minor_patch_matches_gte_patch(self):
        constraint = VersionConstraint(major=1, minor=2, patch=3)
        assert constraint.matches("1.2.3")
        assert constraint.matches("1.2.4")
        assert constraint.matches("1.2.99")
        assert constraint.matches("1.3.0")
        assert not constraint.matches("1.2.2")
        assert not constraint.matches("1.2.0")
        assert not constraint.matches("1.1.5")

    def test_caret_zero_major_respects_minor_boundary(self):
        constraint = VersionConstraint(major=0, minor=2, patch=3)
        assert constraint.matches("0.2.3")
        assert constraint.matches("0.2.9")
        assert not constraint.matches("0.3.0")
        assert not constraint.matches("0.9.0")

    def test_caret_zero_minor_respects_patch_boundary(self):
        constraint = VersionConstraint(major=0, minor=0, patch=3)
        assert constraint.matches("0.0.3")
        assert not constraint.matches("0.0.4")
        assert not constraint.matches("0.1.0")

    def test_from_version_creates_constraint(self):
        constraint = VersionConstraint.from_version("1.2.3")
        assert constraint.major == 1
        assert constraint.minor == 2
        assert constraint.patch == 3

    def test_major_only_factory(self):
        constraint = VersionConstraint.major_only(2)
        assert constraint.major == 2
        assert constraint.minor is None
        assert constraint.patch is None

    def test_invalid_negative_major(self):
        with pytest.raises(ValueError, match="non-negative"):
            VersionConstraint(major=-1)

    def test_invalid_patch_without_minor(self):
        with pytest.raises(ValueError, match="Cannot specify patch without minor"):
            VersionConstraint(major=1, patch=3)

    def test_str_representation(self):
        assert str(VersionConstraint(major=1)) == ">=1.0.0,<2.0.0"
        assert str(VersionConstraint(major=1, minor=2)) == ">=1.2.0,<2.0.0"
        assert str(VersionConstraint(major=1, minor=2, patch=3)) == ">=1.2.3,<2.0.0"
        assert str(VersionConstraint(major=0, minor=2, patch=3)) == ">=0.2.3,<0.3.0"


class TestResolveVersion:
    """Tests for resolve_version function."""

    @pytest.fixture
    def versions(self) -> list[str]:
        """Sample version list for testing."""
        return ["1.0.0", "1.1.0", "1.5.0", "2.0.0", "2.1.0"]

    def test_exact_finds_matching_version(self, versions: list[str]):
        result = resolve_version(versions, "1.1.0", ResolutionPolicy.EXACT)
        assert result == "1.1.0"

    def test_exact_raises_on_missing(self, versions: list[str]):
        with pytest.raises(ResolutionError) as exc:
            resolve_version(versions, "1.2.0", ResolutionPolicy.EXACT)
        assert exc.value.policy == ResolutionPolicy.EXACT
        assert "1.2.0" in exc.value.reason

    def test_exact_requires_version(self, versions: list[str]):
        with pytest.raises(ValueError, match="requires an explicit version"):
            resolve_version(versions, None, ResolutionPolicy.EXACT)

    def test_pinned_finds_matching_version(self, versions: list[str]):
        result = resolve_version(versions, "2.0.0", ResolutionPolicy.PINNED)
        assert result == "2.0.0"

    def test_pinned_raises_on_missing(self, versions: list[str]):
        with pytest.raises(ResolutionError) as exc:
            resolve_version(versions, "3.0.0", ResolutionPolicy.PINNED)
        assert exc.value.policy == ResolutionPolicy.PINNED

    def test_pinned_requires_version(self, versions: list[str]):
        with pytest.raises(ValueError, match="requires an explicit version"):
            resolve_version(versions, None, ResolutionPolicy.PINNED)

    def test_latest_returns_newest(self, versions: list[str]):
        result = resolve_version(versions, None, ResolutionPolicy.LATEST)
        assert result == "2.1.0"

    def test_latest_ignores_requested(self, versions: list[str]):
        result = resolve_version(versions, "1.0.0", ResolutionPolicy.LATEST)
        assert result == "2.1.0"

    def test_latest_ignores_prerelease_by_default(self):
        result = resolve_version(
            ["1.0.0-alpha.1", "1.0.0"],
            None,
            ResolutionPolicy.LATEST,
        )
        assert result == "1.0.0"

    def test_latest_prerelease_requires_explicit_request(self):
        with pytest.raises(ResolutionError):
            resolve_version(["1.0.0-alpha.1"], None, ResolutionPolicy.LATEST)

    def test_latest_compatible_same_major(self, versions: list[str]):
        result = resolve_version(versions, "1.0.0", ResolutionPolicy.LATEST_COMPATIBLE)
        assert result == "1.5.0"

    def test_latest_compatible_respects_constraint(self, versions: list[str]):
        constraint = VersionConstraint(major=2)
        result = resolve_version(versions, None, ResolutionPolicy.LATEST_COMPATIBLE, constraint)
        assert result == "2.1.0"

    def test_latest_compatible_zero_major_respects_minor(self):
        versions = ["0.2.3", "0.2.9", "0.3.0"]
        result = resolve_version(versions, "0.2.3", ResolutionPolicy.LATEST_COMPATIBLE)
        assert result == "0.2.9"

    def test_latest_compatible_no_match_raises(self, versions: list[str]):
        constraint = VersionConstraint(major=3)
        with pytest.raises(ResolutionError) as exc:
            resolve_version(versions, None, ResolutionPolicy.LATEST_COMPATIBLE, constraint)
        assert exc.value.policy == ResolutionPolicy.LATEST_COMPATIBLE

    def test_latest_compatible_derives_constraint_from_requested(self, versions: list[str]):
        result = resolve_version(versions, "1.1.0", ResolutionPolicy.LATEST_COMPATIBLE)
        assert result == "1.5.0"

    def test_empty_available_raises(self):
        with pytest.raises(ResolutionError, match="No versions available"):
            resolve_version([], "1.0.0", ResolutionPolicy.EXACT)

    def test_invalid_version_in_available_raises(self):
        with pytest.raises(ResolutionError, match="Invalid semver"):
            resolve_version(["not-a-version"], None, ResolutionPolicy.LATEST)

    def test_single_version_available(self):
        result = resolve_version(["1.0.0"], None, ResolutionPolicy.LATEST)
        assert result == "1.0.0"


class TestResolutionHelpers:
    """Tests for helper functions in resolution module."""

    def test_compare_versions_less(self):
        assert compare_versions("1.0.0", "1.1.0") == -1
        assert compare_versions("1.0.0", "2.0.0") == -1

    def test_compare_versions_equal(self):
        assert compare_versions("1.0.0", "1.0.0") == 0

    def test_compare_versions_greater(self):
        assert compare_versions("2.0.0", "1.0.0") == 1
        assert compare_versions("1.1.0", "1.0.0") == 1

    def test_is_compatible_upgrade_same_major(self):
        assert is_compatible_upgrade("1.0.0", "1.1.0")
        assert is_compatible_upgrade("1.0.0", "1.99.99")
        assert not is_compatible_upgrade("1.0.0", "2.0.0")
        assert not is_compatible_upgrade("1.1.0", "1.0.0")

    def test_find_compatible_versions(self):
        versions = ["1.0.0", "1.2.0", "1.5.0", "2.0.0"]
        constraint = VersionConstraint(major=1)
        result = find_compatible_versions(versions, constraint)
        assert result == ["1.5.0", "1.2.0", "1.0.0"]


# =============================================================================
# Registry Singleton Tests
# =============================================================================


class TestSingletonPattern:
    """Tests for singleton behavior."""

    def test_same_instance_returned(self):
        reg1 = MethodRegistry()
        reg2 = MethodRegistry()
        assert reg1 is reg2

    def test_get_instance_returns_same(self):
        reg1 = MethodRegistry.get_instance()
        reg2 = MethodRegistry.get_instance()
        assert reg1 is reg2

    def test_get_registry_convenience_function(self):
        reg1 = get_registry()
        reg2 = MethodRegistry()
        assert reg1 is reg2

    def test_reset_creates_new_instance(self):
        reg1 = MethodRegistry()
        MethodRegistry.reset_instance()
        reg2 = MethodRegistry()
        assert reg1 is not reg2

    def test_state_persists_across_access(self):
        method = create_mock_method("test", "ns", "1.0.0")

        reg1 = MethodRegistry()
        reg1.register(method)

        reg2 = MethodRegistry()
        assert len(reg2) == 1
        assert "ns.test@1.0.0" in reg2


class TestConcurrentRegistration:
    """Tests for thread-safe registration."""

    def test_concurrent_registration_thread_safe(self):
        registry = MethodRegistry()
        num_threads = 10
        methods_per_thread = 20

        def register_methods(thread_id: int) -> list[str]:
            fqns = []
            for i in range(methods_per_thread):
                method = create_mock_method(
                    f"method_{i}",
                    f"thread_{thread_id}",
                    "1.0.0",
                )
                fqn = registry.register(method)
                fqns.append(fqn)
            return fqns

        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(register_methods, i) for i in range(num_threads)]
            all_fqns = []
            for future in concurrent.futures.as_completed(futures):
                all_fqns.extend(future.result())

        assert len(all_fqns) == num_threads * methods_per_thread
        assert len(registry) == num_threads * methods_per_thread
        assert len(set(all_fqns)) == len(all_fqns)

    def test_concurrent_read_write(self):
        registry = MethodRegistry()

        for i in range(50):
            method = create_mock_method(f"pre_{i}", "initial", "1.0.0")
            registry.register(method)

        results = {"reads": 0, "writes": 0, "errors": []}
        lock = threading.Lock()

        def reader(iterations: int):
            for _ in range(iterations):
                try:
                    list(registry.query(namespace="initial"))
                    with lock:
                        results["reads"] += 1
                except Exception as exc:
                    with lock:
                        results["errors"].append(str(exc))

        def writer(thread_id: int, iterations: int):
            for i in range(iterations):
                try:
                    method = create_mock_method(f"new_{i}", f"writer_{thread_id}", "1.0.0")
                    registry.register(method)
                    with lock:
                        results["writes"] += 1
                except Exception as exc:
                    with lock:
                        results["errors"].append(str(exc))

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            futures = []
            for _ in range(4):
                futures.append(executor.submit(reader, 100))
            for i in range(4):
                futures.append(executor.submit(writer, i, 25))

            concurrent.futures.wait(futures)

        assert not results["errors"], f"Errors occurred: {results['errors']}"
        assert results["reads"] == 400
        assert results["writes"] == 100


# =============================================================================
# Registration Tests
# =============================================================================


class TestRegistration:
    """Tests for method registration."""

    def test_register_valid_method(self, income_slot: SlotSpec, tax_slot: SlotSpec):
        registry = MethodRegistry()
        method = create_mock_method(
            "flat_tax",
            "fiscal.taxation",
            "1.0.0",
            input_slots=frozenset({income_slot}),
            output_slots=frozenset({tax_slot}),
        )

        fqn = registry.register(method)

        assert fqn == "fiscal.taxation.flat_tax@1.0.0"
        assert fqn in registry
        assert len(registry) == 1

    def test_register_duplicate_raises(self):
        registry = MethodRegistry()
        method = create_mock_method("test", "ns", "1.0.0")

        registry.register(method)

        with pytest.raises(MethodAlreadyRegisteredError) as exc:
            registry.register(method)
        assert exc.value.fqn == "ns.test@1.0.0"

    def test_register_duplicate_with_override(self):
        registry = MethodRegistry()
        method1 = create_mock_method("test", "ns", "1.0.0", tags=frozenset({"v1"}))
        method2 = create_mock_method("test", "ns", "1.0.0", tags=frozenset({"v2"}))

        registry.register(method1)
        registry.register(method2, override=True)

        assert len(registry) == 1
        entry = registry.get_entry("ns.test@1.0.0")
        assert "v2" in entry.metadata.tags

    def test_register_missing_signature_raises(self):
        registry = MethodRegistry()

        class BadMethod:
            pass

        with pytest.raises(TypeError, match="missing 'signature'"):
            registry.register(BadMethod)  # type: ignore

    def test_register_missing_metadata_raises(self):
        registry = MethodRegistry()
        sig = create_method_signature("test", "ns", "1.0.0", frozenset(), frozenset())

        class BadMethod:
            signature = sig

        with pytest.raises(TypeError, match="missing 'metadata'"):
            registry.register(BadMethod)  # type: ignore

    def test_unregister_removes_method(self):
        registry = MethodRegistry()
        method = create_mock_method("test", "ns", "1.0.0")
        registry.register(method)

        result = registry.unregister("ns.test@1.0.0")

        assert result is True
        assert "ns.test@1.0.0" not in registry
        assert len(registry) == 0

    def test_unregister_nonexistent_returns_false(self):
        registry = MethodRegistry()
        result = registry.unregister("ns.test@1.0.0")
        assert result is False


class TestLazyLoading:
    """Tests for lazy loading support."""

    def test_lazy_register_does_not_call_factory(self):
        registry = MethodRegistry()
        factory = MagicMock(return_value=create_mock_method("test", "ns", "1.0.0"))

        sig = create_method_signature("test", "ns", "1.0.0", frozenset(), frozenset())
        meta = MethodMetadata(description="test")

        registry.register_lazy(sig, meta, factory)

        factory.assert_not_called()

        entry = registry.get_entry("ns.test@1.0.0")
        assert entry is not None
        assert entry.loaded is False

    def test_lazy_factory_called_on_get(self):
        registry = MethodRegistry()
        mock_method = create_mock_method("test", "ns", "1.0.0")
        factory = MagicMock(return_value=mock_method)

        sig = create_method_signature("test", "ns", "1.0.0", frozenset(), frozenset())
        meta = MethodMetadata(description="test")

        registry.register_lazy(sig, meta, factory)

        result = registry.get("ns.test@1.0.0")

        factory.assert_called_once()
        assert result is mock_method

        entry = registry.get_entry("ns.test@1.0.0")
        assert entry.loaded is True

    def test_lazy_factory_called_only_once(self):
        registry = MethodRegistry()
        mock_method = create_mock_method("test", "ns", "1.0.0")
        factory = MagicMock(return_value=mock_method)

        sig = create_method_signature("test", "ns", "1.0.0", frozenset(), frozenset())
        meta = MethodMetadata(description="test")

        registry.register_lazy(sig, meta, factory)

        registry.get("ns.test@1.0.0")
        registry.get("ns.test@1.0.0")
        registry.get("ns.test@1.0.0")

        factory.assert_called_once()

    def test_lazy_concurrent_loading(self):
        registry = MethodRegistry()
        load_count = {"count": 0}
        lock = threading.Lock()

        def slow_factory():
            with lock:
                load_count["count"] += 1
            time.sleep(0.1)
            return create_mock_method("test", "ns", "1.0.0")

        sig = create_method_signature("test", "ns", "1.0.0", frozenset(), frozenset())
        meta = MethodMetadata(description="test")
        registry.register_lazy(sig, meta, slow_factory)

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(registry.get, "ns.test@1.0.0") for _ in range(5)]
            results = [future.result() for future in futures]

        assert all(result is results[0] for result in results)
        assert load_count["count"] == 1


class TestRegistryAuditLog:
    def test_audit_log_is_bounded(self):
        audit_log = get_registry_audit_log()
        audit_log.clear()

        for i in range(audit_log.max_events + 25):
            audit_log.record("register", f"ns.test_{i}@1.0.0")

        history = audit_log.get_history()
        assert len(history) == audit_log.max_events
        assert history[0].fqn == "ns.test_25@1.0.0"
        assert history[-1].fqn == f"ns.test_{audit_log.max_events + 24}@1.0.0"

        audit_log.clear()


# =============================================================================
# Retrieval Tests
# =============================================================================


class TestRetrieval:
    """Tests for method retrieval."""

    def test_get_by_fqn(self):
        registry = MethodRegistry()
        method = create_mock_method("test", "ns", "1.0.0")
        registry.register(method)

        result = registry.get("ns.test@1.0.0")

        assert result is method

    def test_get_by_base_name_exact(self):
        registry = MethodRegistry()
        method = create_mock_method("test", "ns", "1.0.0")
        registry.register(method)

        result = registry.get("ns.test", version="1.0.0", policy=ResolutionPolicy.EXACT)

        assert result is method

    def test_get_by_short_name_unambiguous(self):
        registry = MethodRegistry()
        method = create_mock_method("unique_test", "some.namespace", "1.0.0")
        registry.register(method)

        result = registry.get("unique_test", version="1.0.0", policy=ResolutionPolicy.EXACT)

        assert result is method

    def test_get_by_short_name_ambiguous_raises(self):
        registry = MethodRegistry()
        method1 = create_mock_method("test", "ns1", "1.0.0")
        method2 = create_mock_method("test", "ns2", "1.0.0")
        registry.register(method1)
        registry.register(method2)

        with pytest.raises(MethodNotFoundError, match="Ambiguous"):
            registry.get("test", version="1.0.0", policy=ResolutionPolicy.EXACT)

    def test_get_nonexistent_raises(self):
        registry = MethodRegistry()

        with pytest.raises(MethodNotFoundError):
            registry.get("ns.does_not_exist@1.0.0")

    def test_get_with_version_resolution(self):
        registry = MethodRegistry()
        method1 = create_mock_method("test", "ns", "1.0.0")
        method2 = create_mock_method("test", "ns", "1.5.0")
        method3 = create_mock_method("test", "ns", "2.0.0")
        registry.register(method1)
        registry.register(method2)
        registry.register(method3)

        result = registry.get(
            "ns.test",
            version="1.0.0",
            policy=ResolutionPolicy.LATEST_COMPATIBLE,
        )
        assert result is method2

        result = registry.get("ns.test", policy=ResolutionPolicy.LATEST)
        assert result is method3

    def test_default_policy_used(self):
        registry = MethodRegistry()
        registry.set_default_policy(ResolutionPolicy.LATEST)

        method1 = create_mock_method("test", "ns", "1.0.0")
        method2 = create_mock_method("test", "ns", "2.0.0")
        registry.register(method1)
        registry.register(method2)

        result = registry.get("ns.test")
        assert result is method2


# =============================================================================
# Query Tests
# =============================================================================


class TestQueries:
    """Tests for query functionality."""

    @pytest.fixture
    def populated_registry(self, income_slot: SlotSpec, tax_slot: SlotSpec) -> MethodRegistry:
        registry = MethodRegistry()

        registry.register(
            create_mock_method(
                "flat_tax",
                "fiscal.taxation",
                "1.0.0",
                tags=frozenset({"fiscal", "simple"}),
                input_slots=frozenset({income_slot}),
                output_slots=frozenset({tax_slot}),
            )
        )
        registry.register(
            create_mock_method(
                "progressive_tax",
                "fiscal.taxation",
                "1.0.0",
                tags=frozenset({"fiscal", "complex"}),
                input_slots=frozenset({income_slot}),
                output_slots=frozenset({tax_slot}),
            )
        )

        registry.register(
            create_mock_method(
                "budget_allocator",
                "fiscal.budget",
                "1.0.0",
                tags=frozenset({"fiscal", "budget"}),
                input_slots=frozenset({tax_slot}),
            )
        )

        registry.register(
            create_mock_method(
                "gdp_calculator",
                "economic.aggregate",
                "1.0.0",
                tags=frozenset({"macro"}),
            )
        )

        return registry

    def test_query_by_namespace(self, populated_registry: MethodRegistry):
        results = list(populated_registry.query(namespace="fiscal.taxation"))
        assert len(results) == 2
        names = {r.name for r in results}
        assert names == {"flat_tax", "progressive_tax"}

    def test_query_by_single_tag(self, populated_registry: MethodRegistry):
        results = list(populated_registry.query(tags={"fiscal"}))
        assert len(results) == 3

    def test_query_by_multiple_tags_and(self, populated_registry: MethodRegistry):
        results = list(populated_registry.query(tags={"fiscal", "simple"}))
        assert len(results) == 1
        assert results[0].name == "flat_tax"

    def test_query_by_input_slot(self, populated_registry: MethodRegistry):
        results = list(populated_registry.query(input_slots={"income"}))
        assert len(results) == 2
        names = {r.name for r in results}
        assert names == {"flat_tax", "progressive_tax"}

    def test_query_by_output_slot(self, populated_registry: MethodRegistry):
        results = list(populated_registry.query(output_slots={"tax_due"}))
        assert len(results) == 2
        names = {r.name for r in results}
        assert names == {"flat_tax", "progressive_tax"}

    def test_query_combined_criteria(self, populated_registry: MethodRegistry):
        results = list(
            populated_registry.query(
                namespace="fiscal.taxation",
                tags={"complex"},
            )
        )
        assert len(results) == 1
        assert results[0].name == "progressive_tax"

    def test_query_no_match_returns_empty(self, populated_registry: MethodRegistry):
        results = list(populated_registry.query(tags={"nonexistent"}))
        assert len(results) == 0

    def test_query_deterministic_order(self, populated_registry: MethodRegistry):
        results = list(populated_registry.query(tags={"fiscal"}))
        fqns = [r.fqn for r in results]
        assert fqns == sorted(fqns)

    def test_find_connectable(self, populated_registry: MethodRegistry):
        results = list(populated_registry.find_connectable("fiscal.taxation.flat_tax@1.0.0"))
        assert any(r.name == "budget_allocator" for r in results)


# =============================================================================
# Listing Tests
# =============================================================================


class TestListing:
    """Tests for listing methods."""

    def test_list_all(self):
        registry = MethodRegistry()
        method1 = create_mock_method("a", "ns", "1.0.0")
        method2 = create_mock_method("b", "ns", "1.0.0")
        registry.register(method1)
        registry.register(method2)

        result = registry.list_all()

        assert len(result) == 2
        assert result[0].name == "a"
        assert result[1].name == "b"

    def test_list_versions(self):
        registry = MethodRegistry()
        registry.register(create_mock_method("test", "ns", "1.0.0"))
        registry.register(create_mock_method("test", "ns", "1.5.0"))
        registry.register(create_mock_method("test", "ns", "2.0.0"))

        versions = registry.list_versions("ns.test")

        assert versions == ["2.0.0", "1.5.0", "1.0.0"]

    def test_list_versions_by_short_name(self):
        registry = MethodRegistry()
        registry.register(create_mock_method("test", "ns", "1.0.0"))
        registry.register(create_mock_method("test", "ns", "2.0.0"))

        versions = registry.list_versions("test")
        assert versions == ["2.0.0", "1.0.0"]

    def test_list_namespaces(self):
        registry = MethodRegistry()
        registry.register(create_mock_method("a", "ns1", "1.0.0"))
        registry.register(create_mock_method("b", "ns2", "1.0.0"))
        registry.register(create_mock_method("c", "ns1", "1.0.0"))

        namespaces = registry.list_namespaces()

        assert namespaces == ["ns1", "ns2"]

    def test_list_tags(self):
        registry = MethodRegistry()
        registry.register(create_mock_method("a", "ns", "1.0.0", tags=frozenset({"tag1", "tag2"})))
        registry.register(create_mock_method("b", "ns", "1.0.0", tags=frozenset({"tag2", "tag3"})))

        tags = registry.list_tags()

        assert tags == ["tag1", "tag2", "tag3"]


# =============================================================================
# Snapshot Tests
# =============================================================================


class TestSnapshot:
    """Tests for registry snapshots."""

    def test_snapshot_captures_state(self):
        registry = MethodRegistry()
        registry.register(create_mock_method("a", "ns", "1.0.0"))
        registry.register(create_mock_method("b", "ns", "1.0.0"))

        snapshot = registry.snapshot()

        assert len(snapshot) == 2

    def test_snapshot_immutable_to_changes(self):
        registry = MethodRegistry()
        registry.register(create_mock_method("a", "ns", "1.0.0"))

        snapshot = registry.snapshot()

        registry.register(create_mock_method("b", "ns", "1.0.0"))

        assert len(snapshot) == 1
        assert len(registry) == 2

    def test_snapshot_iteration(self):
        registry = MethodRegistry()
        registry.register(create_mock_method("a", "ns", "1.0.0"))
        registry.register(create_mock_method("b", "ns", "1.0.0"))

        snapshot = registry.snapshot()
        fqns = list(snapshot)

        assert fqns == ["ns.a@1.0.0", "ns.b@1.0.0"]

    def test_snapshot_signatures(self):
        registry = MethodRegistry()
        registry.register(create_mock_method("a", "ns", "1.0.0"))

        snapshot = registry.snapshot()
        sigs = list(snapshot.signatures())

        assert len(sigs) == 1
        assert sigs[0].name == "a"

    def test_snapshot_entry_does_not_mutate_with_live_lazy_load(self, unitless: Unit):
        registry = MethodRegistry()
        signature = create_method_signature(
            "lazy",
            "ns",
            "1.0.0",
            frozenset(),
            frozenset({SlotSpec(name="value", slot_type=SlotType.SCALAR, unit=unitless)}),
        )
        metadata = MethodMetadata(description="lazy snapshot")
        lazy_method = create_mock_method("lazy", "ns", "1.0.0")
        registry.register_lazy(signature, metadata, lambda: lazy_method)

        snapshot = registry.snapshot()
        snap_entry = next(snapshot.entries())
        assert snap_entry.loaded is False

        registry.get(signature.fqn)
        live_entry = registry.get_entry(signature.fqn)

        assert live_entry is not None
        assert live_entry.loaded is True
        assert snap_entry.loaded is False


# =============================================================================
# Container Protocol Tests
# =============================================================================


class TestContainerProtocol:
    """Tests for container protocol implementation."""

    def test_len(self):
        registry = MethodRegistry()
        assert len(registry) == 0

        registry.register(create_mock_method("a", "ns", "1.0.0"))
        assert len(registry) == 1

        registry.register(create_mock_method("b", "ns", "1.0.0"))
        assert len(registry) == 2

    def test_contains(self):
        registry = MethodRegistry()
        registry.register(create_mock_method("test", "ns", "1.0.0"))

        assert "ns.test@1.0.0" in registry
        assert "ns.other@1.0.0" not in registry

    def test_iter(self):
        registry = MethodRegistry()
        registry.register(create_mock_method("b", "ns", "1.0.0"))
        registry.register(create_mock_method("a", "ns", "1.0.0"))

        fqns = list(registry)

        assert fqns == ["ns.a@1.0.0", "ns.b@1.0.0"]


# =============================================================================
# Stats and Debug Tests
# =============================================================================


class TestStatsAndDebug:
    """Tests for debugging utilities."""

    def test_stats(self):
        registry = MethodRegistry()

        registry.register(create_mock_method("a", "ns1", "1.0.0", tags=frozenset({"tag1"})))
        registry.register(create_mock_method("b", "ns2", "1.0.0", tags=frozenset({"tag2"})))

        sig = create_method_signature("c", "ns3", "1.0.0", frozenset(), frozenset())
        meta = MethodMetadata(description="lazy")
        registry.register_lazy(sig, meta, lambda: create_mock_method("c", "ns3", "1.0.0"))

        stats = registry.stats()

        assert stats["total_methods"] == 3
        assert stats["loaded_methods"] == 2
        assert stats["lazy_methods"] == 1
        assert stats["namespaces"] == 3
        assert stats["registrations"] == 3

    def test_repr(self):
        registry = MethodRegistry()
        registry.register(create_mock_method("a", "ns", "1.0.0"))

        assert "methods=1" in repr(registry)
