from __future__ import annotations

import sqlite3
import threading
from typing import ClassVar

import pytest

from polisyos.foundry.methods.base import (
    ComplexityClass,
    ComputeBackend,
    FidelityLevel,
    MethodMetadata,
    MethodSignature,
    SlotSpec,
    SlotType,
    Unit,
)
from polisyos.foundry.methods.cache import RegistryPersistenceLayer
from polisyos.foundry.methods.registry import MethodRegistry
from polisyos.ir.analytics.uncertainty import (
    NativeValueEstimandBinding,
    OutputContractCapability,
    ValueUncertaintyProjectionKind,
    value_uncertainty_output_contract,
)


def _make_signature(name: str, version: str = "1.0.0") -> MethodSignature:
    unit = Unit(dimension="none", symbol="1")
    slot = SlotSpec(name="slot", slot_type=SlotType.SCALAR, unit=unit)
    return MethodSignature(
        name=name,
        namespace="tests.cache",
        version=version,
        input_slots=frozenset({slot}),
        output_slots=frozenset({slot}),
        parameters=(),
        fidelity=FidelityLevel.LOW,
        complexity=ComplexityClass.O_1,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )


class _EagerMethod:
    signature: ClassVar[MethodSignature] = _make_signature("eager")
    metadata: ClassVar[MethodMetadata] = MethodMetadata(description="eager")

    @staticmethod
    def pure_step(state, params):
        return state


class _LazyPersistableMethod:
    signature: ClassVar[MethodSignature] = _make_signature("lazy")
    metadata: ClassVar[MethodMetadata] = MethodMetadata(description="lazy")

    @staticmethod
    def pure_step(state, params):
        return state


class _CacheValueOutput:
    contract_id = "tests.cache.value_output.v1"
    output_contract_declaration = value_uncertainty_output_contract(
        contract_id,
        projection_kind=ValueUncertaintyProjectionKind.POSTERIOR,
    )

    def to_value_uncertainty(
        self,
        *,
        estimand: object,
        projection_binding: NativeValueEstimandBinding,
    ) -> None:
        del estimand, projection_binding
        return None


class _CapabilityMethod:
    signature: ClassVar[MethodSignature] = MethodSignature(
        name="capability",
        namespace="tests.cache",
        version="1.0.0",
        input_slots=frozenset(),
        output_slots=frozenset(
            {
                SlotSpec.for_output_contract(
                    "result",
                    SlotType.SCALAR,
                    Unit(dimension="value", symbol="json"),
                    output_contract=_CacheValueOutput,
                )
            }
        ),
        parameters=(),
        fidelity=FidelityLevel.LOW,
        complexity=ComplexityClass.O_1,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )
    metadata: ClassVar[MethodMetadata] = MethodMetadata(description="capability")

    @staticmethod
    def pure_step(state, params):
        return state


@pytest.fixture(autouse=True)
def _reset_registry():
    MethodRegistry.reset_instance()
    yield
    MethodRegistry.reset_instance()


def test_snapshot_from_real_registry_and_restore_round_trip(tmp_path) -> None:
    registry = MethodRegistry.get_instance()
    registry.register(_EagerMethod)
    registry.register_lazy(
        _LazyPersistableMethod.signature,
        _LazyPersistableMethod.metadata,
        factory=lambda cls=_LazyPersistableMethod: cls,
        import_target=(_LazyPersistableMethod.__module__, _LazyPersistableMethod.__qualname__),
    )

    layer = RegistryPersistenceLayer(tmp_path / "registry.sqlite")
    written = layer.snapshot_from(registry)

    assert written == 2
    assert [record.fqn for record in layer.all_records()] == [
        _EagerMethod.signature.fqn,
        _LazyPersistableMethod.signature.fqn,
    ]

    MethodRegistry.reset_instance()
    restored_registry = MethodRegistry.get_instance()
    restored = layer.restore_into(restored_registry)

    assert restored == 2
    assert restored_registry.get(_EagerMethod.signature.fqn) is _EagerMethod
    assert restored_registry.get(_LazyPersistableMethod.signature.fqn) is _LazyPersistableMethod


def test_value_output_capability_round_trips_through_registry_cache(tmp_path) -> None:
    registry = MethodRegistry.get_instance()
    registry.register(_CapabilityMethod)
    layer = RegistryPersistenceLayer(tmp_path / "registry.sqlite")

    assert layer.snapshot_from(registry) == 1
    MethodRegistry.reset_instance()
    restored_registry = MethodRegistry.get_instance()
    assert layer.restore_into(restored_registry) == 1

    restored_entry = next(iter(restored_registry.snapshot().entries()))
    restored_slot = next(iter(restored_entry.signature.output_slots))
    assert restored_entry.signature.stable_digest() == (
        _CapabilityMethod.signature.stable_digest()
    )
    assert restored_slot.contract_capabilities == frozenset(
        {OutputContractCapability.VALUE_UNCERTAINTY_PROJECTION}
    )
    assert restored_slot.contract_owner == (
        f"{_CacheValueOutput.__module__}:{_CacheValueOutput.__qualname__}"
    )


def test_prior_registry_cache_schema_is_rejected(tmp_path) -> None:
    db_path = tmp_path / "registry.sqlite"
    registry = MethodRegistry.get_instance()
    registry.register(_EagerMethod)
    layer = RegistryPersistenceLayer(db_path)
    assert layer.snapshot_from(registry) == 1
    layer.close()

    with sqlite3.connect(db_path) as connection:
        connection.execute(
            "UPDATE _meta SET value = ? WHERE key = 'schema_version'",
            ("2",),
        )
        connection.commit()

    stale_layer = RegistryPersistenceLayer(db_path)
    assert stale_layer.is_cache_valid() is False

    MethodRegistry.reset_instance()
    restored_registry = MethodRegistry.get_instance()
    assert stale_layer.restore_into(restored_registry) == 0
    assert restored_registry.get_entry(_EagerMethod.signature.fqn) is None


def test_snapshot_refresh_removes_stale_rows(tmp_path) -> None:
    registry = MethodRegistry.get_instance()
    registry.register(_EagerMethod)
    registry.register_lazy(
        _LazyPersistableMethod.signature,
        _LazyPersistableMethod.metadata,
        factory=lambda cls=_LazyPersistableMethod: cls,
        import_target=(_LazyPersistableMethod.__module__, _LazyPersistableMethod.__qualname__),
    )
    layer = RegistryPersistenceLayer(tmp_path / "registry.sqlite")
    assert layer.snapshot_from(registry) == 2

    MethodRegistry.reset_instance()
    trimmed_registry = MethodRegistry.get_instance()
    trimmed_registry.register(_EagerMethod)
    assert layer.snapshot_from(trimmed_registry) == 1

    assert [record.fqn for record in layer.all_records()] == [_EagerMethod.signature.fqn]


def test_snapshot_skips_non_persistable_lazy_entries(tmp_path) -> None:
    registry = MethodRegistry.get_instance()
    registry.register_lazy(
        _LazyPersistableMethod.signature,
        _LazyPersistableMethod.metadata,
        factory=lambda: _LazyPersistableMethod,
    )
    layer = RegistryPersistenceLayer(tmp_path / "registry.sqlite")

    written = layer.snapshot_from(registry)

    assert written == 0
    assert layer.all_records() == []

    MethodRegistry.reset_instance()
    restored_registry = MethodRegistry.get_instance()
    assert layer.restore_into(restored_registry) == 0
    assert restored_registry.get_entry(_LazyPersistableMethod.signature.fqn) is None


def test_cache_context_manager_closes_owned_connection(tmp_path) -> None:
    layer = RegistryPersistenceLayer(tmp_path / "registry.sqlite")
    assert layer._conn is not None

    with layer:
        assert layer._conn is not None

    assert layer._conn is None


def test_cache_open_close_invalidate_restore_thread_safe(tmp_path) -> None:
    registry = MethodRegistry.get_instance()
    registry.register(_EagerMethod)
    registry.register_lazy(
        _LazyPersistableMethod.signature,
        _LazyPersistableMethod.metadata,
        factory=lambda cls=_LazyPersistableMethod: cls,
        import_target=(_LazyPersistableMethod.__module__, _LazyPersistableMethod.__qualname__),
    )
    layer = RegistryPersistenceLayer(tmp_path / "registry.sqlite")
    assert layer.snapshot_from(registry) == 2

    errors: list[Exception] = []

    def reader() -> None:
        try:
            for _ in range(10):
                layer.open()
                fresh = MethodRegistry._create_fresh()
                restored = layer.restore_into(fresh)
                assert restored in {0, 2}
                layer.close()
        except Exception as exc:
            errors.append(exc)

    def writer() -> None:
        try:
            for _ in range(10):
                layer.invalidate()
                layer.snapshot_from(registry)
                layer.close()
        except Exception as exc:
            errors.append(exc)

    threads = [
        threading.Thread(target=reader),
        threading.Thread(target=reader),
        threading.Thread(target=writer),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10.0)

    assert not errors

    final_registry = MethodRegistry._create_fresh()
    assert layer.restore_into(final_registry) == 2
