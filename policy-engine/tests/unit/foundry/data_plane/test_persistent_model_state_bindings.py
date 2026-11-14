"""Real persistent snapshot sources survive the canonical binding producer."""

from __future__ import annotations

from decimal import Decimal

import numpy as np
import pytest

from polisyos.core.artifacts import artifact_ref_identity_key, validate_core_model_json_artifact
from polisyos.core.contracts import FoundryInputBindingRule, StateSnapshot
from polisyos.core.registry import build_registry_bundle, load_registry_bundle_content
from polisyos.foundry.data_plane.bindings import (
    build_input_bindings,
    load_input_bindings,
    prepare_input_bindings,
    reconcile_selected_method_input_bindings,
)
from polisyos.foundry.execute.patch_vm import ModelStatePatchContext
from polisyos.foundry.methods.catalog.policy.accounting import PeriodFlowToStock
from polisyos.ir.kernel import SlotRegistry
from tests._helpers.registered_derived_method_input import materialize_registered_method_input_case
from tests._helpers.selected_method_input import prepare_selected_method_input_case
from tests.unit.foundry.data_plane.test_selected_method_input_bindings import _removed_blob

_STOCK = "accounts.reserve"


def test_original_persistent_snapshot_is_reused_without_a_shadow_state(tmp_path):
    case, _ = prepare_selected_method_input_case(
        tmp_path,
        method_class=PeriodFlowToStock,
        persistent_stock_slot=_STOCK,
        state_writes=(_STOCK,),
    )
    try:
        initial = load_input_bindings(case.store, case.input_bindings_ref)
        assert initial.schema_version == "1.0" and not initial.rules
        assert artifact_ref_identity_key(
            initial.bound_state_snapshot_ref
        ) == artifact_ref_identity_key(case.source_ref)
        prepared = prepare_input_bindings(
            case.store,
            data_snapshot_ref=case.data_snapshot_ref,
            registry_bundle_ref=case.registry_bundle_ref,
            rules=[],
        )
        assert artifact_ref_identity_key(prepared.reused_bound_state_snapshot_ref) == (
            artifact_ref_identity_key(case.source_ref)
        )
        context = ModelStatePatchContext(case.store, case.source_ref, case.registry_bundle_ref)
        assert float(context.read_slot(_STOCK)) == 10_000_000_000.0
        assert np.asarray(context.read_slot(_STOCK)).dtype == np.float32
        snapshot = validate_core_model_json_artifact(StateSnapshot, case.store, case.source_ref)
        assert snapshot.schema_version == "2.4"
        assert context.bound_state.layout_ref is not None
        for ref in (case.source_ref, snapshot.state_ref, context.bound_state.layout_ref):
            with _removed_blob(case.store, ref), pytest.raises((ValueError, FileNotFoundError)):
                prepare_input_bindings(
                    case.store,
                    data_snapshot_ref=case.data_snapshot_ref,
                    registry_bundle_ref=case.registry_bundle_ref,
                    rules=[],
                )
        restored = build_input_bindings(
            case.store,
            data_snapshot_ref=case.data_snapshot_ref,
            registry_bundle_ref=case.registry_bundle_ref,
            rules=[],
            return_selected_profile=True,
        )
        assert artifact_ref_identity_key(
            restored.bound_state_snapshot_ref
        ) == artifact_ref_identity_key(case.source_ref)
        with pytest.raises(ValueError, match="state_rewrite_not_established"):
            prepare_input_bindings(
                case.store,
                data_snapshot_ref=case.data_snapshot_ref,
                registry_bundle_ref=case.registry_bundle_ref,
                rules=[
                    FoundryInputBindingRule(
                        binding_id="forbidden-rewrite",
                        source_path="step",
                        target_slot_id="agents.income",
                    )
                ],
            )

        registry = load_registry_bundle_content(case.store, case.registry_bundle_ref)
        foreign_slots = dict(registry.slot_registry.slots)
        foreign_slots[_STOCK] = foreign_slots[_STOCK].model_copy(
            update={"description": "A different selected registry declaration."}
        )
        foreign = build_registry_bundle(
            case.store,
            slot_registry=SlotRegistry(slots=foreign_slots),
            merge_registry=registry.merge_registry,
            mechanism_registry=registry.mechanism_registry,
            constraint_registry=registry.constraint_registry,
            selector_field_registry=registry.selector_field_registry,
            metric_registry=registry.metric_registry,
            units_registry=registry.units_registry,
            return_selected_profile=True,
        )
        with pytest.raises(ValueError, match="registry_mismatch"):
            prepare_input_bindings(
                case.store,
                data_snapshot_ref=case.data_snapshot_ref,
                registry_bundle_ref=foreign.bundle_ref,
                rules=[],
            )
    finally:
        case.close()


def test_persistent_absence_is_preserved_instead_of_becoming_a_present_zero(tmp_path):
    case, _ = prepare_selected_method_input_case(
        tmp_path,
        method_class=PeriodFlowToStock,
        persistent_stock_slot=_STOCK,
        state_writes=(_STOCK,),
        persistent_stock_value=None,
    )
    try:
        context = ModelStatePatchContext(
            case.store, case.bound_state_snapshot_ref, case.registry_bundle_ref
        )
        with pytest.raises(ValueError, match="model_scalar_state_slot_absent"):
            context.read_slot(_STOCK)
        assert artifact_ref_identity_key(
            case.bound_state_snapshot_ref
        ) == artifact_ref_identity_key(case.source_ref)
    finally:
        case.close()


def test_real_derived_method_values_preserve_the_original_persistent_prestate(tmp_path):
    case, metadata = prepare_selected_method_input_case(
        tmp_path,
        method_class=PeriodFlowToStock,
        persistent_stock_slot=_STOCK,
        state_writes=(_STOCK,),
    )
    try:
        materialized = materialize_registered_method_input_case(case, metadata)
        actual = load_input_bindings(case.store, materialized.input_bindings_ref)
        assert actual.schema_version == "1.4"
        assert artifact_ref_identity_key(
            actual.bound_state_snapshot_ref
        ) == artifact_ref_identity_key(case.source_ref)
        replayed = reconcile_selected_method_input_bindings(
            case.store, input_bindings_ref=materialized.input_bindings_ref
        )
        assert replayed.records[0].canonical_value == Decimal("-6000000000")
        assert float(replayed.values["period_flow"]) == -6_000_000_000.0
        context = ModelStatePatchContext(
            case.store, actual.bound_state_snapshot_ref, case.registry_bundle_ref
        )
        assert float(context.read_slot(_STOCK)) == 10_000_000_000.0
        assert context.bound_state.layout_ref is not None
        with (
            _removed_blob(case.store, context.bound_state.layout_ref),
            pytest.raises((ValueError, FileNotFoundError)),
        ):
            reconcile_selected_method_input_bindings(
                case.store, input_bindings_ref=materialized.input_bindings_ref
            )
        assert (
            reconcile_selected_method_input_bindings(
                case.store, input_bindings_ref=materialized.input_bindings_ref
            ).records
            == replayed.records
        )
    finally:
        case.close()
