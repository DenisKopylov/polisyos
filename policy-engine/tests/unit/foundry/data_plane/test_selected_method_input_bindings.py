"""Persisted source and NPY controls for the selected method-input boundary."""

from __future__ import annotations

import hashlib
import json
from contextlib import contextmanager
from dataclasses import replace
from decimal import Decimal
from io import BytesIO

import numpy as np
import pytest

from polisyos.core.artifacts.manifest import SchemaInfo, input_ref_from_artifact_ref
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.contracts.foundry import FoundryInputBindings
from polisyos.core.contracts.model_input_requirements import load_model_input_obligation_set
from polisyos.core.contracts.semantic_input_binding import load_resolved_input_binding_manifest
from polisyos.core.contracts.variable_binding import (
    load_variable_representation,
    variable_representation_manifest_inputs,
)
from polisyos.foundry.data_plane.bindings import (
    SelectedMethodInputFacts,
    SelectedMethodInputResolution,
    _prepare_selected_method_input,
    load_input_bindings,
    reconcile_selected_method_input_bindings,
    replay_selected_method_input_facts,
    resolve_bound_state_snapshot_ref,
)
from polisyos.foundry.execute._internal.models import put_tensor
from polisyos.foundry.methods.catalog.policy.accounting import PeriodFlowToStock
from polisyos.foundry.methods.registry import MethodRegistry
from tests._helpers.derived_selected_method_input import materialize_selected_method_input_case
from tests._helpers.selected_method_input import prepare_selected_method_input_case
from tests.unit.core.contracts.test_semantic_derived_binding import _put_contract


def _independent_value_sha256(value):
    array = np.asarray(value, dtype=np.float64)
    digest = hashlib.sha256()
    digest.update(array.dtype.str.encode("ascii"))
    digest.update(json.dumps(array.shape, separators=(",", ":")).encode("ascii"))
    digest.update(array.tobytes(order="C"))
    return digest.hexdigest()


def _blob_path(store, ref):
    identifier = ref.artifact_id.hex
    return (
        store.root
        / "artifacts"
        / "sha256"
        / identifier[:2]
        / identifier[2:4]
        / f"{identifier}.blob"
    )


@contextmanager
def _removed_blob(store, ref):
    path = _blob_path(store, ref)
    held = path.with_suffix(".held")
    path.rename(held)
    try:
        yield
    finally:
        held.rename(path)


@contextmanager
def _corrupt_blob(store, ref, replacement):
    path = _blob_path(store, ref)
    original = path.read_bytes()
    path.write_bytes(replacement)
    try:
        yield
    finally:
        path.write_bytes(original)


def _persist_rebuilt_record(store, original_ref, bindings, record):
    rebuilt = bindings.model_copy(update={"selected_method_inputs": (record,)})
    inputs = [
        edge
        for edge in store.get_manifest(original_ref).inputs
        if not edge.role.startswith("method_input.")
    ]
    inputs.extend(
        (
            input_ref_from_artifact_ref(
                record.model_input_obligation_ref,
                role=f"method_input.{record.binding_id}.obligation",
            ),
            input_ref_from_artifact_ref(
                record.npy_value_ref, role=f"method_input.{record.binding_id}.value"
            ),
        )
    )
    return store.put_json(
        rebuilt,
        PutOptions(
            kind=FoundryInputBindings.ARTIFACT_KIND,
            media_type=FoundryInputBindings.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(name=FoundryInputBindings.ARTIFACT_SCHEMA_NAME, version="1.4"),
            inputs=inputs,
        ),
        return_selected_profile=True,
    )


def test_selected_method_values_replay_sources_and_keep_exact_prestate(tmp_path):
    case, metadata = prepare_selected_method_input_case(tmp_path, method_class=PeriodFlowToStock)
    try:
        materialized = materialize_selected_method_input_case(case, metadata)
        fresh = FileSystemCAS(case.store_root)
        resolution = reconcile_selected_method_input_bindings(
            fresh, input_bindings_ref=materialized.input_bindings_ref, effective_step=0
        )
        assert resolution.bindings.schema_version == "1.4"
        assert resolution.bindings.bound_state_snapshot_ref == case.bound_state_snapshot_ref
        assert resolve_bound_state_snapshot_ref(fresh, materialized.input_bindings_ref) == (
            case.bound_state_snapshot_ref
        )
        (record,) = resolution.records
        assert record.canonical_value == Decimal("-6000000000")
        assert record.value_sha256 == _independent_value_sha256(-6_000_000_000.0)
        value = resolution.values["period_flow"]
        assert type(value) is np.ndarray and value.shape == () and value.dtype == np.float64
        assert float(value) == -6_000_000_000.0 and not value.flags.writeable
        with pytest.raises(ValueError, match="read-only"):
            value[...] = 0
        with pytest.raises(ValueError, match="WRITEABLE"):
            value.setflags(write=True)
        with pytest.raises(TypeError):
            resolution.values["extra"] = value
        again = reconcile_selected_method_input_bindings(
            fresh, input_bindings_ref=materialized.input_bindings_ref
        )
        assert again.values["period_flow"] is not value
        assert not np.shares_memory(again.values["period_flow"], value)
        assert "semantic_input_limitation:method_external_reads_not_observed" in resolution.notes
        assert "semantic_input_limitation:external_empirical_context_not_established" in (
            resolution.notes
        )
        assert "semantic_input_limitation:method_provider_completeness_not_established" in (
            resolution.notes
        )
        assert "semantic_input_limitation:method_nominal_abi_not_checked" not in resolution.notes
        # This immutable physical-port check also runs in historical replay,
        # where a current MethodRegistry preflight must not be consulted.
        representation = load_variable_representation(fresh, metadata["representation_ref"])
        wrong_money_representation = representation.model_copy(
            update={"money_unit": metadata["money"].model_copy(update={"currency": "UAH"})}
        )
        wrong_money_ref = _put_contract(
            fresh,
            wrong_money_representation,
            version="3.0",
            inputs=variable_representation_manifest_inputs(wrong_money_representation),
        )
        wrong_money_port = metadata["obligation"].port.model_copy(
            update={"representation_ref": wrong_money_ref}
        )
        (selection,) = load_resolved_input_binding_manifest(
            fresh, materialized.resolved_binding_manifest_ref
        ).derivations
        with pytest.raises(
            ValueError, match=r"^foundry_selected_method_input_canonical_money_unit_mismatch$"
        ):
            _prepare_selected_method_input(
                fresh,
                selection=selection,
                manifest_ref=materialized.resolved_binding_manifest_ref,
                obligation=metadata["obligation"].model_copy(update={"port": wrong_money_port}),
                canonical_value=record.canonical_value,
                physical_value=Decimal("-6000000000"),
            )

        manifest = load_resolved_input_binding_manifest(
            fresh, materialized.resolved_binding_manifest_ref
        )
        selected_set, _ = load_model_input_obligation_set(
            fresh, manifest.model_input_obligation_set_ref
        )
        invocation = selected_set.invocation
        # B is a distinct selected binding artifact, not an execution. Its
        # immutable facts can be replayed under a changed live method ABI.
        retained_binding = resolution.bindings.model_copy(
            update={"notes": [*resolution.bindings.notes, "fixture:retained-selection-B"]}
        )
        retained_ref = _persist_rebuilt_record(
            fresh, materialized.input_bindings_ref, retained_binding, record
        )
        assert retained_ref.artifact_id != materialized.input_bindings_ref.artifact_id
        source = next(iter(PeriodFlowToStock.signature.input_slots))

        class ChangedABI(PeriodFlowToStock):
            signature = replace(
                PeriodFlowToStock.signature,
                input_slots=frozenset(
                    (*PeriodFlowToStock.signature.input_slots, replace(source, name="new_input"))
                ),
            )

        registry = MethodRegistry.get_instance()
        registry.register(ChangedABI, override=True)
        try:
            with pytest.raises(ValueError):
                reconcile_selected_method_input_bindings(fresh, input_bindings_ref=retained_ref)
            retained_facts = replay_selected_method_input_facts(
                fresh, input_bindings_ref=retained_ref, expected_invocation=invocation
            )
            assert type(retained_facts) is SelectedMethodInputFacts
            assert not isinstance(retained_facts, SelectedMethodInputResolution)
            assert float(retained_facts.values["period_flow"]) == -6_000_000_000.0
            assert retained_facts.records[0].value_sha256 == record.value_sha256
            assert "semantic_input_limitation:method_nominal_abi_not_checked" in (
                retained_facts.notes
            )
            assert "semantic_input_limitation:method_provider_completeness_not_established" in (
                retained_facts.notes
            )
        finally:
            registry.register(PeriodFlowToStock, override=True)
        with pytest.raises(
            ValueError, match=r"^foundry_input_bindings_semantic_invocation_mismatch$"
        ):
            replay_selected_method_input_facts(
                fresh,
                input_bindings_ref=retained_ref,
                expected_invocation=invocation.model_copy(update={"steps": (1,)}),
            )

        # No embedded certificate, canonical_value label, or physical-state
        # fallback can replace the separately selected source and NPY bytes.
        for removed in (
            record.npy_value_ref,
            metadata["recipe_ref"],
            metadata["roles"][0].source_series_ref,
            metadata["roles"][0].occurrence_ref,
        ):
            with _removed_blob(fresh, removed):
                with pytest.raises((FileNotFoundError, ValueError)):
                    reconcile_selected_method_input_bindings(
                        fresh, input_bindings_ref=materialized.input_bindings_ref
                    )
                with pytest.raises((FileNotFoundError, ValueError)):
                    replay_selected_method_input_facts(
                        fresh, input_bindings_ref=retained_ref, expected_invocation=invocation
                    )
        replacement = BytesIO()
        np.save(replacement, np.asarray(0, dtype=np.float64))
        with (
            _corrupt_blob(fresh, record.npy_value_ref, replacement.getvalue()),
            pytest.raises(ValueError),
        ):
            reconcile_selected_method_input_bindings(
                fresh, input_bindings_ref=materialized.input_bindings_ref
            )

        original = load_input_bindings(fresh, materialized.input_bindings_ref)
        for update in (
            {"canonical_value": Decimal("0")},
            {"value_sha256": "0" * 64},
            {"port_id": "another-period-flow"},
            {"slot_id": "gdp"},
        ):
            forged_ref = _persist_rebuilt_record(
                fresh, materialized.input_bindings_ref, original, record.model_copy(update=update)
            )
            with pytest.raises(
                ValueError, match=r"^foundry_selected_method_input_record_source_mismatch$"
            ):
                reconcile_selected_method_input_bindings(fresh, input_bindings_ref=forged_ref)

        value_inputs = fresh.get_manifest(record.npy_value_ref).inputs
        for wrong in (
            np.asarray([[-6_000_000_000.0]]),
            np.asarray(-6_000_000_000.0, dtype=np.float32),
        ):
            wrong_ref = put_tensor(
                fresh,
                wrong,
                return_selected_profile=True,
                kind="foundry.selected_method_input_value",
                inputs=value_inputs,
            )
            forged_ref = _persist_rebuilt_record(
                fresh,
                materialized.input_bindings_ref,
                original,
                record.model_copy(update={"npy_value_ref": wrong_ref}),
            )
            with pytest.raises(ValueError, match="shape or dtype"):
                reconcile_selected_method_input_bindings(fresh, input_bindings_ref=forged_ref)
        no_source_ref = put_tensor(
            fresh,
            np.asarray(-6_000_000_000.0, dtype=np.float64),
            return_selected_profile=True,
            kind="foundry.selected_method_input_value",
            inputs=[edge for edge in value_inputs if edge.role != "source.selected_value"],
        )
        forged_ref = _persist_rebuilt_record(
            fresh,
            materialized.input_bindings_ref,
            original,
            record.model_copy(update={"npy_value_ref": no_source_ref}),
        )
        with pytest.raises(
            ValueError, match=r"^foundry_selected_method_input_value_lineage_mismatch$"
        ):
            reconcile_selected_method_input_bindings(fresh, input_bindings_ref=forged_ref)
        assert (
            float(
                reconcile_selected_method_input_bindings(
                    fresh, input_bindings_ref=materialized.input_bindings_ref
                ).values["period_flow"]
            )
            == -6_000_000_000.0
        )
    finally:
        case.close()
