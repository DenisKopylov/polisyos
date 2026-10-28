from __future__ import annotations

from collections.abc import Callable, Mapping
from decimal import Decimal
from pathlib import Path
from typing import NoReturn

import jax
import numpy as np
import pytest
from pydantic import BaseModel

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.contracts.fabric import DataSnapshot
from polisyos.core.contracts.foundry import FoundryInputBindingRule
from polisyos.core.registry import build_default_registry_bundle, load_registry_bundle_content
from polisyos.foundry.contracts.state import GlobalState
from polisyos.foundry.data_plane import (
    InputBindingsPreparation,
    build_input_bindings,
    prepare_input_bindings,
    prepare_json_input_binding_values,
)
from polisyos.foundry.data_plane.bindings import load_input_bindings
from polisyos.foundry.execute.executor import get_state_path, load_state_snapshot
from tests.unit.foundry.data_plane.test_bindings_multiscale import (
    SYNTHETIC_MULTISCALE_PAYLOAD,
    _put_json,
)


def _without_writes[T](
    store: FileSystemCAS,
    monkeypatch: pytest.MonkeyPatch,
    invoke: Callable[[], T],
) -> T:
    """Refuse any artifact emission, including hidden state/report writes."""

    def refuse_write(*args: object, **kwargs: object) -> NoReturn:
        del args, kwargs
        pytest.fail("input preparation emitted a CAS artifact")

    with monkeypatch.context() as patch:
        patch.setattr(store, "put_json", refuse_write)
        patch.setattr(store, "put_bytes", refuse_write)
        return invoke()


def _assert_typed_value(actual: object, expected: object) -> None:
    """Compare the complete typed value; do not serialize an Any field to JSON."""

    if isinstance(expected, BaseModel):
        assert type(actual) is type(expected)
        assert isinstance(actual, BaseModel)
        for field in type(expected).model_fields:
            _assert_typed_value(getattr(actual, field), getattr(expected, field))
    elif isinstance(expected, Mapping):
        assert type(actual) is type(expected)
        assert isinstance(actual, Mapping)
        assert actual.keys() == expected.keys()
        for key in expected:
            _assert_typed_value(actual[key], expected[key])
    elif isinstance(expected, tuple | list):
        assert type(actual) is type(expected)
        assert isinstance(actual, tuple | list)
        assert len(actual) == len(expected)
        for actual_item, expected_item in zip(actual, expected, strict=True):
            _assert_typed_value(actual_item, expected_item)
    elif isinstance(expected, float | np.generic | np.ndarray | jax.Array):
        actual_array = np.asarray(actual)
        expected_array = np.asarray(expected)
        assert actual_array.shape == expected_array.shape
        assert actual_array.dtype == expected_array.dtype
        assert not expected_array.dtype.hasobject
        assert actual_array.tobytes(order="C") == expected_array.tobytes(order="C")
    elif isinstance(expected, Decimal):
        assert type(actual) is type(expected)
        assert isinstance(actual, Decimal)
        assert actual.as_tuple() == expected.as_tuple()
    else:
        # Fail closed for an unsupported native value in an open model field.
        assert expected is None or isinstance(expected, str | int | bool)
        assert type(actual) is type(expected)
        assert actual == expected


def _assert_complete_state(actual: GlobalState, expected: GlobalState) -> None:
    """Use the state's complete tree and exact numeric leaf representation."""

    actual_leaves, actual_tree = jax.tree_util.tree_flatten(actual)
    expected_leaves, expected_tree = jax.tree_util.tree_flatten(expected)
    assert actual_tree == expected_tree
    for actual_leaf, expected_leaf in zip(actual_leaves, expected_leaves, strict=True):
        if isinstance(expected_leaf, BaseModel):
            _assert_typed_value(actual_leaf, expected_leaf)
            continue
        actual_array = np.asarray(actual_leaf)
        expected_array = np.asarray(expected_leaf)
        # Numeric state bytes preserve signed zero and NaN representation. An
        # object array would compare pointers, so it is outside this byte law.
        assert not actual_array.dtype.hasobject
        assert not expected_array.dtype.hasobject
        assert actual_array.shape == expected_array.shape
        assert actual_array.dtype == expected_array.dtype
        assert actual_array.tobytes(order="C") == expected_array.tobytes(order="C")


@pytest.mark.parametrize("mutation", ["scalar_for_vector", "signed_zero"])
def test_complete_state_oracle_rejects_same_value_representation_mutants(mutation: str) -> None:
    """Identical scalar values cannot conceal a changed state shape or sign."""

    expected = GlobalState.empty(n_agents=2, n_firms=1)
    dtype = np.asarray(expected.agents.savings).dtype
    changed = (
        np.asarray(0.0, dtype=dtype)
        if mutation == "scalar_for_vector"
        else np.full((2,), -0.0, dtype=dtype)
    )
    actual = expected.replace(agents=expected.agents.replace(savings=changed))
    with pytest.raises(AssertionError):
        _assert_complete_state(actual, expected)


@pytest.mark.parametrize("explicit_rules", [False, True])
def test_actual_binding_preparation_is_write_free_and_matches_fresh_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    explicit_rules: bool,
) -> None:
    """The numerical plan and actual writer share the complete state owner."""

    store = FileSystemCAS(tmp_path / "cas")
    payload_ref = _put_json(
        store,
        SYNTHETIC_MULTISCALE_PAYLOAD,
        kind="fabric.synthetic_multiscale_payload",
    )
    snapshot_ref = _put_json(store, DataSnapshot(data_ref=payload_ref), kind="fabric.data_snapshot")
    registry_ref = build_default_registry_bundle(store).bundle_ref
    rules = (
        [
            FoundryInputBindingRule(
                binding_id="selected.population",
                source_path="cells.population",
                target_slot_id="cells.population",
            ),
            FoundryInputBindingRule(
                binding_id="selected.household_income",
                source_path="household_cells.disposable_income",
                target_slot_id="household_cells.disposable_income",
            ),
        ]
        if explicit_rules
        else None
    )
    files_before = {path.relative_to(tmp_path) for path in tmp_path.rglob("*") if path.is_file()}
    preparation = _without_writes(
        store,
        monkeypatch,
        lambda: prepare_input_bindings(
            store,
            data_snapshot_ref=snapshot_ref,
            registry_bundle_ref=registry_ref,
            rules=rules,
        ),
    )
    assert {path.relative_to(tmp_path) for path in tmp_path.rglob("*") if path.is_file()} == (
        files_before
    )
    assert preparation.materialized_state.cells is not None
    assert preparation.materialized_state.household_cells is not None
    np.testing.assert_array_equal(
        preparation.materialized_state.cells.population,
        SYNTHETIC_MULTISCALE_PAYLOAD["cells"]["population"],
    )
    np.testing.assert_array_equal(
        preparation.materialized_state.household_cells.disposable_income,
        SYNTHETIC_MULTISCALE_PAYLOAD["household_cells"]["disposable_income"],
    )
    built = build_input_bindings(
        store,
        data_snapshot_ref=snapshot_ref,
        registry_bundle_ref=registry_ref,
        rules=rules,
    )
    # Reopen through a new store instance: the prepared value cannot substitute
    # for the persisted writer and maintained state reader.
    reader = FileSystemCAS(tmp_path / "cas")
    state = load_state_snapshot(reader, snapshot_ref=built.bound_state_snapshot_ref)
    _assert_complete_state(state, preparation.materialized_state)
    bindings = load_input_bindings(reader, built.input_bindings_ref)
    assert bindings.rules == list(preparation.effective_rules)
    assert built.applied_binding_ids == preparation.applied_binding_ids


def test_preparation_rejects_missing_required_value_without_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A populated snapshot cannot satisfy an unrelated required binding."""

    store = FileSystemCAS(tmp_path / "cas")
    payload_ref = _put_json(
        store, SYNTHETIC_MULTISCALE_PAYLOAD, kind="fabric.synthetic_multiscale_payload"
    )
    snapshot_ref = _put_json(store, DataSnapshot(data_ref=payload_ref), kind="fabric.data_snapshot")
    registry_ref = build_default_registry_bundle(store).bundle_ref
    rule = FoundryInputBindingRule(
        binding_id="selected.missing",
        source_path="acquisition.selected.absent",
        target_slot_id="cells.population",
        required=True,
    )
    with pytest.raises(ValueError, match="selected.missing"):
        _without_writes(
            store,
            monkeypatch,
            lambda: prepare_input_bindings(
                store,
                data_snapshot_ref=snapshot_ref,
                registry_bundle_ref=registry_ref,
                rules=[rule],
            ),
        )


def test_selected_registered_sql_preparation_matches_actual_writer_and_rejects_mismatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The write-free owner and actual writer resolve the same real SQL basis."""
    import sqlite3

    from polisyos.core.artifacts import ArtifactRef
    from polisyos.scientist.adapters.registered_sql_admission import RegisteredSQLProducer
    from tests.unit.scientist.adapters.test_registered_sql_snapshot import (
        _request,
        _storage_only_registered_source,
    )

    store, port, authority, owner, registration = _storage_only_registered_source(
        tmp_path, expected_query='SELECT * FROM "policy_inputs" LIMIT 100'
    )
    producer = RegisteredSQLProducer(port=port, owner=owner, authority=authority)
    request_ref = _request(store)
    receipt, materialization, source_ref = producer.acquire_and_admit(
        store=store,
        request_ref=request_ref,
        registration=registration,
        event_id="prepare-source-a",
        occurrence_id="prepare-occurrence-a",
        expected_predecessor=registration.event_ref,
    )
    registry_ref = build_default_registry_bundle(store, return_selected_profile=True).bundle_ref
    rules = [
        FoundryInputBindingRule(
            binding_id="income", source_path="income", target_slot_id="agents.income"
        )
    ]
    files_before = {path.relative_to(tmp_path) for path in tmp_path.rglob("*") if path.is_file()}
    preparation = _without_writes(
        store,
        monkeypatch,
        lambda: prepare_input_bindings(
            store,
            data_snapshot_ref=materialization.snapshot_ref,
            registry_bundle_ref=registry_ref,
            rules=rules,
            registered_sql_admission_ref=source_ref,
        ),
    )
    assert {path.relative_to(tmp_path) for path in tmp_path.rglob("*") if path.is_file()} == (
        files_before
    )
    np.testing.assert_array_equal(preparation.materialized_state.agents.income, [12.5])
    built = build_input_bindings(
        store,
        data_snapshot_ref=materialization.snapshot_ref,
        registry_bundle_ref=registry_ref,
        rules=rules,
        registered_sql_admission_ref=source_ref,
        return_selected_profile=True,
    )
    actual = load_state_snapshot(store, snapshot_ref=built.bound_state_snapshot_ref)
    _assert_complete_state(actual, preparation.materialized_state)
    assert built.applied_binding_ids == preparation.applied_binding_ids

    missing = [
        FoundryInputBindingRule(
            binding_id="defaulted",
            source_path="missing_income",
            target_slot_id="agents.income",
            required=False,
            default_value=12.5,
        )
    ]
    from polisyos.foundry.data_plane import bindings as binding_module

    def shared_numerical_owner_must_not_run(*args: object, **kwargs: object) -> NoReturn:
        del args, kwargs
        pytest.fail("shared numerical owner ran before SQL source-path refusal")

    with monkeypatch.context() as patch:
        patch.setattr(
            binding_module, "_prepare_input_binding_values", shared_numerical_owner_must_not_run
        )
        with pytest.raises(ValueError, match="registered_sql_binding_source_read_not_established"):
            _without_writes(
                store,
                patch,
                lambda: prepare_input_bindings(
                    store,
                    data_snapshot_ref=materialization.snapshot_ref,
                    registry_bundle_ref=registry_ref,
                    rules=missing,
                    registered_sql_admission_ref=source_ref,
                ),
            )
    unselected = ArtifactRef.model_validate(
        source_ref.model_dump(mode="python") | {"manifest_profile_sha256": None}
    )
    with pytest.raises(ValueError, match="registered_sql_binding_selected_profile_required"):
        prepare_input_bindings(
            store,
            data_snapshot_ref=materialization.snapshot_ref,
            registry_bundle_ref=registry_ref,
            rules=rules,
            registered_sql_admission_ref=unselected,
        )

    with sqlite3.connect(tmp_path / "rows.sqlite") as database:
        database.execute("UPDATE policy_inputs SET income = 37.0")
    _, other_materialization, _ = producer.acquire_and_admit(
        store=store,
        request_ref=request_ref,
        registration=registration,
        event_id="prepare-source-b",
        occurrence_id="prepare-occurrence-b",
        expected_predecessor=receipt.event_ref,
    )
    with pytest.raises(ValueError, match="registered_sql_binding_snapshot_mismatch"):
        prepare_input_bindings(
            store,
            data_snapshot_ref=other_materialization.snapshot_ref,
            registry_bundle_ref=registry_ref,
            rules=rules,
            registered_sql_admission_ref=source_ref,
        )


@pytest.mark.parametrize("explicit_rules", [False, True])
def test_prospective_json_values_match_real_persisted_owner_without_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, explicit_rules: bool
) -> None:
    """A prospective payload uses full actual state, not a scalar/receipt hash."""
    import json

    store = FileSystemCAS(tmp_path / "cas")
    registry_ref = build_default_registry_bundle(store).bundle_ref
    payload = SYNTHETIC_MULTISCALE_PAYLOAD
    rules = (
        [
            FoundryInputBindingRule(
                binding_id="prospective.population",
                source_path="cells.population",
                target_slot_id="cells.population",
            )
        ]
        if explicit_rules
        else None
    )
    before = {path.relative_to(tmp_path) for path in tmp_path.rglob("*") if path.is_file()}
    prospective = _without_writes(
        store,
        monkeypatch,
        lambda: prepare_json_input_binding_values(
            store,
            payload_json=json.dumps(payload, allow_nan=False).encode(),
            registry_bundle_ref=registry_ref,
            rules=rules,
        ),
    )
    assert {path.relative_to(tmp_path) for path in tmp_path.rglob("*") if path.is_file()} == before
    payload_ref = _put_json(store, payload, kind="fabric.synthetic_multiscale_payload")
    snapshot_ref = _put_json(store, DataSnapshot(data_ref=payload_ref), kind="fabric.data_snapshot")
    actual = build_input_bindings(
        store,
        data_snapshot_ref=snapshot_ref,
        registry_bundle_ref=registry_ref,
        rules=rules,
    )
    reader = FileSystemCAS(tmp_path / "cas")
    _assert_complete_state(
        prospective.materialized_state,
        load_state_snapshot(reader, snapshot_ref=actual.bound_state_snapshot_ref),
    )
    assert (
        list(prospective.effective_rules)
        == load_input_bindings(reader, actual.input_bindings_ref).rules
    )
    assert prospective.applied_binding_ids == actual.applied_binding_ids


@pytest.mark.parametrize("payload", [b"[]", b'{"value": NaN}', b'{"value": Infinity}'])
def test_prospective_json_rejects_unsupported_payload_without_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, payload: bytes
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    registry_ref = build_default_registry_bundle(store).bundle_ref
    with pytest.raises(ValueError):
        _without_writes(
            store,
            monkeypatch,
            lambda: prepare_json_input_binding_values(
                store,
                payload_json=payload,
                registry_bundle_ref=registry_ref,
            ),
        )


def test_prospective_json_reuses_real_can2_numeric_value_law(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A negative-zero decimal input follows the actual persisted payload codec."""
    import json

    store = FileSystemCAS(tmp_path / "cas")
    registry_ref = build_default_registry_bundle(store).bundle_ref
    payload = {"reported": {"balance": -0.0}}
    rules = [
        FoundryInputBindingRule(
            binding_id="prospective.reported_balance",
            source_path="reported.balance",
            target_slot_id="government.balance",
        )
    ]
    prospective = _without_writes(
        store,
        monkeypatch,
        lambda: prepare_json_input_binding_values(
            store,
            payload_json=json.dumps(payload).encode(),
            registry_bundle_ref=registry_ref,
            rules=rules,
        ),
    )
    payload_ref = _put_json(store, payload, kind="fabric.prospective_can2_payload")
    snapshot_ref = _put_json(store, DataSnapshot(data_ref=payload_ref), kind="fabric.data_snapshot")
    built = build_input_bindings(
        store,
        data_snapshot_ref=snapshot_ref,
        registry_bundle_ref=registry_ref,
        rules=rules,
    )
    actual = load_state_snapshot(
        FileSystemCAS(tmp_path / "cas"), snapshot_ref=built.bound_state_snapshot_ref
    )
    _assert_complete_state(prospective.materialized_state, actual)
    slot_registry = load_registry_bundle_content(store, registry_ref).slot_registry
    actual_state_path = slot_registry.slots[rules[0].target_slot_id].state_path
    assert actual_state_path
    assert not np.signbit(np.asarray(get_state_path(actual, actual_state_path))).any()
    assert not np.signbit(
        np.asarray(get_state_path(prospective.materialized_state, actual_state_path))
    ).any()
