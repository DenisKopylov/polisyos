from __future__ import annotations

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
