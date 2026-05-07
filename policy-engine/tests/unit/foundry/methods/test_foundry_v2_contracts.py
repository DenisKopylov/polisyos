from __future__ import annotations

from polisyos.foundry.methods.base import SlotType
from polisyos.foundry.methods.catalog import ensure_all_methods_registered
from polisyos.foundry.methods.catalog.snapshot import build_method_catalog_snapshot
from polisyos.foundry.methods.registry import MethodRegistry


def test_foundry_v2_registry_uses_unique_canonical_fqns() -> None:
    ensure_all_methods_registered()
    registry = MethodRegistry.get_instance()

    signatures = registry.list_all()
    fqns = [signature.fqn for signature in signatures]

    assert fqns
    assert len(fqns) == len(set(fqns))


def test_foundry_v2_registered_methods_define_shapes_for_non_scalar_slots() -> None:
    ensure_all_methods_registered()
    registry = MethodRegistry.get_instance()

    for signature in registry.list_all():
        for slot in (*signature.input_slots, *signature.output_slots):
            if slot.slot_type is SlotType.SCALAR:
                assert slot.shape == ()
            else:
                assert slot.shape, (
                    f"{signature.fqn}:{slot.name} is missing non-scalar shape metadata"
                )


def test_foundry_v2_snapshot_excludes_aggregate_wrapper_registrations() -> None:
    ensure_all_methods_registered()
    snapshot = build_method_catalog_snapshot(run_id="R_contracts")

    offenders = [
        entry.fqn
        for entry in snapshot.entries
        if any(tag == "deprecated:aggregate-wrapper" for tag in entry.tags)
    ]

    assert offenders == []


def test_foundry_v2_snapshot_capability_matrix_stays_in_sync_with_entry_fields() -> None:
    ensure_all_methods_registered()
    snapshot = build_method_catalog_snapshot(run_id="R_contracts")

    for entry in snapshot.entries:
        assert entry.capability_matrix["kind"] == entry.kind
        assert entry.capability_matrix["execution_backend"] == entry.execution_backend
        assert entry.capability_matrix["runtime_stack"] == entry.runtime_stack
        assert entry.capability_matrix["required_deps"] == entry.required_deps
        assert entry.capability_matrix["optional_deps"] == entry.optional_deps
        assert entry.capability_matrix["runnable"] == entry.runnable
