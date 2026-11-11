from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import textwrap
import threading
from dataclasses import fields
from typing import ClassVar

import pytest

from polisyos.core.observability import DeterminismTier
from polisyos.foundry.methods.base import (
    ComplexityClass,
    ComputeBackend,
    DimVar,
    FidelityLevel,
    MethodContracts,
    MethodKind,
    MethodMetadata,
    MethodSignature,
    ParameterSpec,
    SideEffectProfile,
    SlotSpec,
    SlotType,
    Unit,
)
from polisyos.foundry.methods.cache import RegistryPersistenceLayer
from polisyos.foundry.methods.components.composer import MethodComposer
from polisyos.foundry.methods.registry import MethodRegistry
from polisyos.foundry.methods.selection.cache import (
    _complete_metadata_payload,
    _complete_signature_payload,
    _semantic_snapshot_hash,
)
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


class _MetadataDriftMethod:
    signature: ClassVar[MethodSignature] = _EagerMethod.signature
    metadata: ClassVar[MethodMetadata] = MethodMetadata(description="changed metadata")

    @staticmethod
    def pure_step(state, params):
        return state


class _WrongLazyMethod:
    signature: ClassVar[MethodSignature] = _make_signature("wrong-lazy")
    metadata: ClassVar[MethodMetadata] = MethodMetadata(description="wrong executable")

    @staticmethod
    def pure_step(state, params):
        return -1


class _IntentionalAliasMethod:
    signature: ClassVar[MethodSignature] = _EagerMethod.signature
    metadata: ClassVar[MethodMetadata] = _EagerMethod.metadata

    @staticmethod
    def pure_step(state, params):
        return state


_REGISTRY_OVERLAY = MethodMetadata(
    description="provider-supplied metadata overlay",
    tags=frozenset({"provider", "current"}),
)


class _OverlayMethod:
    signature: ClassVar[MethodSignature] = _EagerMethod.signature
    metadata: ClassVar[MethodMetadata] = MethodMetadata(description="class declaration")

    @staticmethod
    def pure_step(state, params):
        return {"slot": state}


class _BoundedMethod:
    signature: ClassVar[MethodSignature] = MethodSignature(
        name="bounded",
        namespace="tests.cache",
        version="1.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    name="input",
                    slot_type=SlotType.SCALAR,
                    unit=Unit(dimension="value", symbol="u"),
                    description="Input declaration",
                    bounds=(0, 100),
                )
            }
        ),
        output_slots=frozenset(
            {
                SlotSpec(
                    name="output",
                    slot_type=SlotType.SCALAR,
                    unit=Unit(dimension="value", symbol="u"),
                    description="Output declaration",
                    bounds=(-10, 10),
                )
            }
        ),
        parameters=(
            ParameterSpec(
                name="rate",
                default=1.0,
                bounds=(0.0, 2.0),
                description="Bounded rate",
            ),
        ),
        fidelity=FidelityLevel.LOW,
        complexity=ComplexityClass.O_1,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )
    metadata: ClassVar[MethodMetadata] = MethodMetadata(description="bounded")

    @staticmethod
    def pure_step(state, params):
        return state


_CONTRACTS = MethodContracts(
    preconditions=("len(state) > 0",),
    postconditions=("result >= 0",),
    invariants=("len(params) >= 0",),
)


class _ContractsMethod:
    signature: ClassVar[MethodSignature] = _make_signature("contracts")
    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="contracted method", contracts=_CONTRACTS
    )

    @staticmethod
    def pure_step(state, params):
        return state


class _ContractsDriftMethod:
    signature: ClassVar[MethodSignature] = _ContractsMethod.signature
    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="contracted method",
        contracts=MethodContracts(preconditions=("len(state) > 1",)),
    )

    @staticmethod
    def pure_step(state, params):
        return state


class _CompleteFieldMethod:
    signature: ClassVar[MethodSignature] = MethodSignature(
        name="complete-fields",
        namespace="tests.cache",
        version="1.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    name="input",
                    slot_type=SlotType.MATRIX,
                    unit=Unit(dimension="money", symbol="$", scale=2.5),
                    contract_id="tests.cache.output.v1",
                    shape=("$DimVar:literal", DimVar("rows")),
                    description="Input contract",
                    bounds=(1, 8),
                    contract_capabilities=frozenset(
                        {OutputContractCapability.VALUE_UNCERTAINTY_PROJECTION}
                    ),
                    contract_owner="tests.cache:_CacheValueOutput",
                )
            }
        ),
        output_slots=frozenset(
            {SlotSpec("output", SlotType.VECTOR, Unit("people", "person"), shape=("rows",))}
        ),
        parameters=(
            ParameterSpec(
                name="marker",
                default="0x1.0000000000000p+0",
                is_static=True,
                bounds=(0, 2),
                description="String that resembles a stable float",
            ),
        ),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_N,
        backend=ComputeBackend.NUMPY,
        kind=MethodKind.SIMULATION,
        family="tests.cache.complete",
        variant="complete-fields",
        data_modalities=frozenset({"panel", "spatial"}),
        fidelity_tier=FidelityLevel.HIGH,
        commutes_with=frozenset({"tests.cache.other@1.0.0"}),
        conflicts_with=frozenset({"tests.cache.conflict@1.0.0"}),
        requires=frozenset({"tests.cache.prerequisite@1.0.0"}),
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )
    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="all metadata fields",
        tags=frozenset({"complete", "cache"}),
        citations=("source-a", "source-b"),
        equations={"effect": "y = beta * x"},
        assumptions={"sampling": "iid"},
        simulator_regime_schema={"type": "object", "required": ["seed"]},
        summary_schema_ref="schema:summary.v1",
        identifiable_target={"name": "effect", "scope": "local"},
        coverage_contract={"minimum": 0.8},
        diagnostic_contract={"check": "residuals"},
        determinism_tier=DeterminismTier.STRICT_CPU,
        declared_truthfulness_tier="exact",
        truthfulness_scope="posterior",
        required_deps=("tests.cache.prerequisite@1.0.0",),
        optional_deps=("tests.cache.optional@1.0.0",),
        fallback_policy="bounded",
        side_effect_profile=SideEffectProfile.ARTIFACT_EMISSION,
        contracts=_CONTRACTS,
        when_to_use="Use when all declarations are available.",
        when_not_to_use="Do not use without calibrated inputs.",
        prerequisites=("tests.cache.prerequisite@1.0.0",),
        diagnostic_checks=("tests.cache.diagnostic@1.0.0",),
        typical_min_obs=11,
        output_interpretation="The output is in policy units.",
    )

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
    assert restored_entry.signature.stable_digest() == (_CapabilityMethod.signature.stable_digest())
    assert restored_slot.contract_capabilities == frozenset(
        {OutputContractCapability.VALUE_UNCERTAINTY_PROJECTION}
    )
    assert restored_slot.contract_owner == (
        f"{_CacheValueOutput.__module__}:{_CacheValueOutput.__qualname__}"
    )


def test_cache_validity_tracks_metadata_drift_without_changing_abi(tmp_path) -> None:
    registry = MethodRegistry._create_fresh()
    target = (_EagerMethod.__module__, _EagerMethod.__qualname__)
    registry.register_lazy(
        _EagerMethod.signature,
        _EagerMethod.metadata,
        factory=lambda: _EagerMethod,
        import_target=target,
    )
    layer = RegistryPersistenceLayer(tmp_path / "registry.sqlite")
    assert layer.snapshot_from(registry) == 1
    assert layer.is_cache_valid(registry)

    changed = MethodRegistry._create_fresh()
    changed.register_lazy(
        _MetadataDriftMethod.signature,
        _MetadataDriftMethod.metadata,
        factory=lambda: _EagerMethod,
        import_target=target,
    )
    assert _EagerMethod.signature.stable_digest() == _MetadataDriftMethod.signature.stable_digest()
    assert not layer.is_cache_valid(changed)


def test_valid_cache_restore_preserves_registry_overlay_through_composition_and_execution(
    tmp_path,
) -> None:
    target = (_OverlayMethod.__module__, _OverlayMethod.__qualname__)
    source_registry = MethodRegistry._create_fresh()
    source_registry.register_lazy(
        _OverlayMethod.signature,
        _REGISTRY_OVERLAY,
        factory=lambda: _OverlayMethod,
        import_target=target,
    )
    layer = RegistryPersistenceLayer(tmp_path / "registry.sqlite")
    assert layer.snapshot_from(source_registry) == 1
    assert layer.is_cache_valid(source_registry)

    restored_registry = MethodRegistry._create_fresh()
    assert layer.restore_into(restored_registry) == 1
    assert layer.is_cache_valid(source_registry)
    restored_entry = restored_registry.get_entry(_OverlayMethod.signature.fqn)
    assert restored_entry is not None
    assert restored_entry.metadata == _REGISTRY_OVERLAY

    composer = MethodComposer(registry=restored_registry)
    composer.add(_OverlayMethod.signature.fqn)
    chain = composer.build(validate_semantics=False)
    result = chain.execute_heterogeneous(
        state={"sentinel": 7},
        registry=restored_registry,
        executor_mode="sequential",
    )
    assert result.final_state["slot"] == {"sentinel": 7}
    assert restored_registry.get_entry(_OverlayMethod.signature.fqn).metadata == _REGISTRY_OVERLAY


def test_cache_round_trips_all_declared_signature_and_metadata_fields(tmp_path) -> None:
    from polisyos.foundry.methods.base import MethodContracts, MethodMetadata, MethodSignature

    registry = MethodRegistry._create_fresh()
    registry.register(_CompleteFieldMethod)
    layer = RegistryPersistenceLayer(tmp_path / "registry.sqlite")
    assert layer.snapshot_from(registry) == 1

    with sqlite3.connect(tmp_path / "registry.sqlite") as connection:
        row = connection.execute(
            "SELECT signature_json, metadata_json FROM method_entries"
        ).fetchone()
    assert row is not None
    signature_payload = json.loads(row[0])
    metadata_payload = json.loads(row[1])

    assert set(signature_payload) == {item.name for item in fields(MethodSignature)}
    assert set(metadata_payload) == {item.name for item in fields(MethodMetadata)}
    for slot_payload in (*signature_payload["input_slots"], *signature_payload["output_slots"]):
        assert set(slot_payload) == {item.name for item in fields(SlotSpec)}
        assert set(slot_payload["unit"]) == {item.name for item in fields(Unit)}
    for parameter_payload in signature_payload["parameters"]:
        assert set(parameter_payload) == {item.name for item in fields(ParameterSpec)}
    assert set(metadata_payload["contracts"]) == {
        item.name for item in fields(MethodContracts)
    }

    restored_registry = MethodRegistry._create_fresh()
    assert layer.restore_into(restored_registry) == 1
    restored_entry = restored_registry.get_entry(_CompleteFieldMethod.signature.fqn)
    assert restored_entry is not None
    restored_signature = restored_entry.signature
    restored_metadata = restored_entry.metadata

    assert _complete_signature_payload(restored_signature) == _complete_signature_payload(
        _CompleteFieldMethod.signature
    )
    assert _complete_metadata_payload(restored_metadata) == _complete_metadata_payload(
        _CompleteFieldMethod.metadata
    )
    assert restored_signature.stable_digest() == _CompleteFieldMethod.signature.stable_digest()
    assert restored_metadata.stable_digest() == _CompleteFieldMethod.metadata.stable_digest()
    assert restored_signature.parameters[0].default == "0x1.0000000000000p+0"
    input_shape = next(iter(restored_signature.input_slots)).shape
    assert input_shape == ("$DimVar:literal", DimVar("rows"))


def test_cache_validity_tracks_contract_drift_without_changing_legacy_digest(tmp_path) -> None:
    target = (_ContractsMethod.__module__, _ContractsMethod.__qualname__)
    registry = MethodRegistry._create_fresh()
    registry.register_lazy(
        _ContractsMethod.signature,
        _ContractsMethod.metadata,
        factory=lambda: _ContractsMethod,
        import_target=target,
    )
    layer = RegistryPersistenceLayer(tmp_path / "registry.sqlite")
    assert layer.snapshot_from(registry) == 1
    assert layer.is_cache_valid(registry)

    changed = MethodRegistry._create_fresh()
    changed.register_lazy(
        _ContractsDriftMethod.signature,
        _ContractsDriftMethod.metadata,
        factory=lambda: _ContractsMethod,
        import_target=target,
    )
    assert _ContractsMethod.metadata.stable_digest() == (
        _ContractsDriftMethod.metadata.stable_digest()
    )
    assert not layer.is_cache_valid(changed)

    restored = MethodRegistry._create_fresh()
    assert layer.restore_into(restored) == 1
    restored_metadata = restored.get_entry(_ContractsMethod.signature.fqn).metadata
    assert restored_metadata.contracts == _CONTRACTS


def test_cache_validity_tracks_declared_import_target_drift(tmp_path) -> None:
    registry = MethodRegistry._create_fresh()
    registry.register(_EagerMethod)
    layer = RegistryPersistenceLayer(tmp_path / "registry.sqlite")
    assert layer.snapshot_from(registry) == 1

    aliased = MethodRegistry._create_fresh()
    aliased.register_lazy(
        _EagerMethod.signature,
        _EagerMethod.metadata,
        factory=lambda: _IntentionalAliasMethod,
        import_target=(
            _IntentionalAliasMethod.__module__,
            _IntentionalAliasMethod.__qualname__,
        ),
    )
    assert _EagerMethod.signature.stable_digest() == _IntentionalAliasMethod.signature.stable_digest()
    assert _EagerMethod.metadata.stable_digest() == _IntentionalAliasMethod.metadata.stable_digest()
    assert not layer.is_cache_valid(aliased)


def test_semantic_signature_fields_round_trip_without_changing_abi(tmp_path) -> None:
    registry = MethodRegistry._create_fresh()
    registry.register(_BoundedMethod)
    layer = RegistryPersistenceLayer(tmp_path / "registry.sqlite")
    assert layer.snapshot_from(registry) == 1

    restored_registry = MethodRegistry._create_fresh()
    assert layer.restore_into(restored_registry) == 1
    restored = next(iter(restored_registry.snapshot().entries())).signature

    assert restored.stable_digest() == _BoundedMethod.signature.stable_digest()
    input_slot = next(iter(restored.input_slots))
    output_slot = next(iter(restored.output_slots))
    assert (input_slot.bounds, input_slot.description) == ((0, 100), "Input declaration")
    assert (output_slot.bounds, output_slot.description) == ((-10, 10), "Output declaration")
    assert restored.parameters[0].bounds == (0.0, 2.0)
    assert restored.parameters[0].description == "Bounded rate"


def test_lazy_registry_rejects_a_factory_with_a_different_admitted_signature() -> None:
    registry = MethodRegistry._create_fresh()
    registry.register_lazy(
        _EagerMethod.signature,
        _EagerMethod.metadata,
        factory=lambda: _WrongLazyMethod,
    )

    composer = MethodComposer(registry=registry)
    with pytest.raises(ValueError, match="lazy_method_signature_mismatch"):
        composer.add(_EagerMethod.signature.fqn)
    assert composer.dag.nodes == {}


def test_lazy_registry_allows_an_explicit_same_signature_alias() -> None:
    registry = MethodRegistry._create_fresh()
    registry.register_lazy(
        _EagerMethod.signature,
        _EagerMethod.metadata,
        factory=lambda: _IntentionalAliasMethod,
        import_target=(_IntentionalAliasMethod.__module__, _IntentionalAliasMethod.__qualname__),
    )

    method = registry.get(_EagerMethod.signature.fqn)
    assert method is _IntentionalAliasMethod
    assert method.pure_step(5, {}) == 5
    node = MethodComposer(registry=registry).add(_EagerMethod.signature.fqn)
    assert node.method_fqn == _EagerMethod.signature.fqn


def test_lazy_registry_rejects_factory_that_disagrees_with_declared_target() -> None:
    registry = MethodRegistry._create_fresh()
    registry.register_lazy(
        _EagerMethod.signature,
        _EagerMethod.metadata,
        factory=lambda: _IntentionalAliasMethod,
        import_target=(_EagerMethod.__module__, _EagerMethod.__qualname__),
    )

    with pytest.raises(ValueError, match="lazy_method_import_target_mismatch"):
        registry.get(_EagerMethod.signature.fqn)


def test_cache_rejects_changed_persisted_metadata_hash(tmp_path) -> None:
    registry = MethodRegistry._create_fresh()
    registry.register(_EagerMethod)
    database = tmp_path / "registry.sqlite"
    layer = RegistryPersistenceLayer(database)
    assert layer.snapshot_from(registry) == 1

    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE method_entries SET metadata_json = ?",
            ('{"description":"tampered"}',),
        )
        connection.commit()

    assert not layer.is_cache_valid(registry)
    restored = MethodRegistry._create_fresh()
    assert layer.restore_into(restored) == 0
    assert restored.get_entry(_EagerMethod.signature.fqn) is None


def test_cache_rejects_missing_contracts_even_when_stored_hash_is_recomputed(tmp_path) -> None:
    registry = MethodRegistry._create_fresh()
    registry.register(_EagerMethod)
    database = tmp_path / "registry.sqlite"
    layer = RegistryPersistenceLayer(database)
    assert layer.snapshot_from(registry) == 1

    with sqlite3.connect(database) as connection:
        row = connection.execute(
            "SELECT fqn, module, class_name, signature_json, signature_hash, metadata_json "
            "FROM method_entries"
        ).fetchone()
        assert row is not None
        fqn, module, qualname, signature_json, abi_hash, metadata_json = row
        signature_payload = json.loads(signature_json)
        metadata_payload = json.loads(metadata_json)
        del metadata_payload["contracts"]
        tampered_metadata_json = json.dumps(metadata_payload, sort_keys=True)
        connection.execute(
            "UPDATE method_entries SET metadata_json = ? WHERE fqn = ?",
            (tampered_metadata_json, fqn),
        )
        recomputed_entry_hash = _semantic_snapshot_hash(
            fqn=fqn,
            signature_payload=signature_payload,
            metadata_payload=metadata_payload,
            module=module,
            qualname=qualname,
            abi_hash=abi_hash,
        )
        recomputed_catalog_hash = hashlib.sha256(recomputed_entry_hash.encode()).hexdigest()
        connection.execute(
            "UPDATE _meta SET value = ? WHERE key = 'catalog_hash'",
            (recomputed_catalog_hash,),
        )
        connection.commit()

    assert layer.is_cache_valid() is False
    assert layer.restore_into(MethodRegistry._create_fresh()) == 0


def test_snapshot_skips_local_class_targets(tmp_path) -> None:
    class LocalMethod:
        signature = _EagerMethod.signature
        metadata = _EagerMethod.metadata

        @staticmethod
        def pure_step(state, params):
            return state

    assert "<locals>" in LocalMethod.__qualname__
    registry = MethodRegistry._create_fresh()
    with pytest.raises(ValueError, match="method_import_target_not_resolvable"):
        registry.register_lazy(
            LocalMethod.signature,
            LocalMethod.metadata,
            factory=lambda: LocalMethod,
            import_target=(LocalMethod.__module__, LocalMethod.__qualname__),
        )

    registry.register_lazy(
        LocalMethod.signature,
        LocalMethod.metadata,
        factory=lambda: LocalMethod,
    )
    assert registry.get(LocalMethod.signature.fqn) is LocalMethod
    entry = registry.get_entry(LocalMethod.signature.fqn)
    assert entry is not None
    assert entry.persistable_import_target is not None
    assert "<locals>" in entry.persistable_import_target[1]
    layer = RegistryPersistenceLayer(tmp_path / "registry.sqlite")
    assert layer.snapshot_from(registry) == 0
    assert layer.all_records() == []


def test_nested_import_target_restores_in_a_fresh_process(tmp_path) -> None:
    fixture_dir = tmp_path / "fixture"
    fixture_dir.mkdir()
    (fixture_dir / "nested_cache_fixture.py").write_text(
        textwrap.dedent(
            """
            from polisyos.foundry.methods.base import (
                ComplexityClass, ComputeBackend, FidelityLevel, MethodMetadata,
                MethodSignature,
            )

            class Nested:
                class Resource:
                    signature = MethodSignature(
                        name="nested", namespace="tests.cache", version="1.0.0",
                        input_slots=frozenset(), output_slots=frozenset(), parameters=(),
                        fidelity=FidelityLevel.LOW, complexity=ComplexityClass.O_1,
                        backend=ComputeBackend.NUMPY, supports_jit=False,
                        supports_vmap=False, supports_grad=False,
                    )
                    metadata = MethodMetadata(description="nested")

                    @staticmethod
                    def pure_step(state, params):
                        return state + 1
            """
        ),
        encoding="utf-8",
    )
    database = tmp_path / "registry.sqlite"
    script = textwrap.dedent(
        """
        import sys
        from pathlib import Path
        sys.path.insert(0, sys.argv[2])
        from nested_cache_fixture import Nested
        from polisyos.foundry.methods.selection.cache import RegistryPersistenceLayer
        from polisyos.foundry.methods.selection.registry import MethodRegistry

        cache = RegistryPersistenceLayer(Path(sys.argv[1]))
        registry = MethodRegistry._create_fresh()
        if sys.argv[3] == "write":
            method = Nested.Resource
            registry.register_lazy(
                method.signature, method.metadata, factory=lambda: method,
                import_target=(method.__module__, method.__qualname__),
            )
            assert cache.snapshot_from(registry) == 1
        else:
            assert cache.restore_into(registry) == 1
            method = registry.get("tests.cache.nested@1.0.0")
            assert method.__qualname__ == "Nested.Resource"
            assert method.pure_step(4, {}) == 5
        """
    )
    product_root = __import__("pathlib").Path(__file__).resolve().parents[4]
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(
        [str(product_root / "src"), env.get("PYTHONPATH", "")]
    ).rstrip(os.pathsep)

    for phase in ("write", "read"):
        subprocess.run(
            [sys.executable, "-c", script, str(database), str(fixture_dir), phase],
            cwd=product_root,
            env=env,
            check=True,
            capture_output=True,
            text=True,
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
            ("3",),
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
