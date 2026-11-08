from __future__ import annotations

from collections.abc import Callable, Mapping
from decimal import Decimal, localcontext
from pathlib import Path
from typing import NoReturn

import jax
import numpy as np
import pytest
from pydantic import BaseModel

from polisyos.core.artifacts.manifest import SchemaInfo, input_ref_from_artifact_ref
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.contracts.fabric import DataSnapshot
from polisyos.core.contracts.foundry import (
    FoundryInputBindingRule,
    FoundryInputBindings,
    FoundryInputBindingsRef,
    FoundryInputBindingTransform,
)
from polisyos.core.registry import build_default_registry_bundle, load_registry_bundle_content
from polisyos.foundry.contracts.state import GlobalState
from polisyos.foundry.data_plane import (
    InputBindingsPreparation,
    build_input_bindings,
    prepare_input_bindings,
    prepare_json_input_binding_values,
)
from polisyos.foundry.data_plane.bindings import (
    _prepare_input_binding_values,
    _SelectedBindingTensorPolicy,
    load_input_bindings,
    reconcile_explicit_initial_binding_slots,
)
from polisyos.foundry.execute.executor import get_state_path, load_state_snapshot
from polisyos.ir.kernel.slots import DEFAULT_SLOT_REGISTRY, SlotRegistry
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


def _prepare_selected_values(
    tmp_path: Path,
    payload: dict[str, object],
    rules: list[FoundryInputBindingRule] | None,
    policies: dict[str, _SelectedBindingTensorPolicy] | None,
    *,
    slot_registry: SlotRegistry = DEFAULT_SLOT_REGISTRY,
) -> InputBindingsPreparation:
    """Exercise the shared numerical owner after selection, without claiming admission."""
    store = FileSystemCAS(tmp_path / "cas")
    payload_ref = _put_json(store, payload, kind="fabric.binding_payload")
    return _prepare_input_binding_values(
        store,
        snapshot=DataSnapshot(data_ref=payload_ref),
        slot_registry=slot_registry,
        binding_payload=payload,
        rules=rules,
        selected_tensor_policies=policies,
    )


def test_selected_empty_rules_never_infer_matching_payload_name(tmp_path: Path) -> None:
    payload = {"government_balance": 1000}
    legacy = _prepare_selected_values(tmp_path, payload, [], None)
    assert legacy.applied_binding_ids
    assert np.asarray(legacy.materialized_state.government_balance).item() == 1000

    selected = _prepare_selected_values(tmp_path, payload, [], {})
    assert selected.applied_binding_ids == selected.effective_rules == ()
    assert np.asarray(selected.materialized_state.government_balance).item() == 0
    with pytest.raises(ValueError, match="semantic_binding_explicit_rules_required"):
        _prepare_selected_values(tmp_path, payload, None, {})


@pytest.mark.parametrize(
    ("payload", "target", "shape", "reason"),
    [
        ({"other": 1}, "government.balance", (), "semantic_binding_source_missing"),
        ({"source": None}, "government.balance", (), "semantic_binding_source_null"),
        ({"source": [None]}, "agents.income", (1,), "semantic_binding_source_null"),
        ({"source": [0]}, "government.balance", (), "semantic_binding_shape_mismatch"),
        ({"source": [0, 2]}, "government.balance", (), "semantic_binding_shape_mismatch"),
        ({"source": 0}, "agents.income", (1,), "semantic_binding_shape_mismatch"),
        ({"source": [0, 2]}, "agents.income", (1,), "semantic_binding_shape_mismatch"),
        ({"source": "0"}, "government.balance", (), "semantic_binding_source_not_decimal"),
        ({"source": False}, "government.balance", (), "semantic_binding_source_not_decimal"),
    ],
)
def test_selected_binding_refuses_missing_null_or_coercion(
    tmp_path: Path,
    payload: dict[str, object],
    target: str,
    shape: tuple[int, ...],
    reason: str,
) -> None:
    rule = FoundryInputBindingRule(
        binding_id="selected", source_path="source", target_slot_id=target
    )
    policy = _SelectedBindingTensorPolicy(shape, "float32", Decimal(0))
    with pytest.raises(ValueError, match=f"^selected: {reason}$"):
        _prepare_selected_values(tmp_path, payload, [rule], {"selected": policy})


def test_selected_observed_zero_and_exact_vector_are_materialized(tmp_path: Path) -> None:
    rules = [
        FoundryInputBindingRule(
            binding_id="balance", source_path="balance", target_slot_id="government.balance"
        ),
        FoundryInputBindingRule(
            binding_id="income", source_path="income", target_slot_id="agents.income"
        ),
    ]
    selected = _prepare_selected_values(
        tmp_path,
        {"balance": 0, "income": [100, 200]},
        rules,
        {
            "balance": _SelectedBindingTensorPolicy((), "float32", Decimal(0)),
            "income": _SelectedBindingTensorPolicy((2,), "float32", Decimal(0)),
        },
    )
    assert selected.applied_binding_ids == ("balance", "income")
    assert np.asarray(selected.materialized_state.government_balance).item() == 0
    np.testing.assert_array_equal(selected.materialized_state.agents.income, [100, 200])


@pytest.mark.parametrize(
    "rule_fields", [{"required": False}, {"default_value": 0}, {"source_path": ""}]
)
def test_selected_binding_cannot_supply_optional_or_default_value(
    tmp_path: Path, rule_fields: dict[str, object]
) -> None:
    rule = FoundryInputBindingRule(
        binding_id="selected", source_path="source", target_slot_id="government.balance"
    ).model_copy(update=rule_fields)
    policy = _SelectedBindingTensorPolicy((), "float32", Decimal(0))
    reason = (
        "semantic_binding_source_path_invalid"
        if "source_path" in rule_fields
        else "semantic_binding_source_required"
    )
    with pytest.raises(ValueError, match=f"^{reason}:selected$"):
        _prepare_selected_values(tmp_path, {"source": 0}, [rule], {"selected": policy})


@pytest.mark.parametrize("binding_ids", [("first", "second"), ("second", "first")])
@pytest.mark.parametrize("reverse_input_order", [False, True])
def test_selected_rules_cannot_overwrite_same_physical_destination(
    tmp_path: Path, binding_ids: tuple[str, str], reverse_input_order: bool
) -> None:
    first = DEFAULT_SLOT_REGISTRY.slots["government.balance"]
    second = first.model_copy(update={"slot_id": "government.other_balance"})
    slots = SlotRegistry(slots={first.slot_id: first, second.slot_id: second})
    rules = [
        FoundryInputBindingRule(
            binding_id=binding_id, source_path=source_path, target_slot_id=slot.slot_id
        )
        for binding_id, source_path, slot in zip(
            binding_ids, ("a", "b"), (first, second), strict=True
        )
    ]
    if reverse_input_order:
        rules.reverse()
    policy = _SelectedBindingTensorPolicy((), "float32", Decimal(0))
    with pytest.raises(
        ValueError, match="^semantic_binding_destination_conflict:government_balance$"
    ):
        _prepare_selected_values(
            tmp_path,
            {"a": 1000, "b": 2000},
            rules,
            dict.fromkeys(binding_ids, policy),
            slot_registry=slots,
        )


def test_selected_fixed_conversion_obeys_separately_verified_multiplier_and_precision(
    tmp_path: Path,
) -> None:
    rule = FoundryInputBindingRule(
        binding_id="selected",
        source_path="percent",
        target_slot_id="global.tax_rate",
        transforms=[FoundryInputBindingTransform(op="scale", params={"factor": "0.01"})],
    )
    # This is a physical representation test. A manifest owner must supply the
    # verified multiplier and selected port precision before real intake.
    payload = {"percent": 20}
    cases = (
        (Decimal("1e-8"), None, "semantic_binding_transform_mismatch"),
        (Decimal("1e-8"), Decimal("0.1"), "semantic_binding_transform_mismatch"),
        (Decimal("1e-9"), Decimal("0.01"), "semantic_binding_precision_loss"),
        (Decimal(0), Decimal("0.01"), "semantic_binding_precision_loss"),
    )
    for error, multiplier, reason in cases:
        with pytest.raises(ValueError, match=f"^selected: {reason}$"):
            _prepare_selected_values(
                tmp_path,
                payload,
                [rule],
                {"selected": _SelectedBindingTensorPolicy((), "float32", error, multiplier)},
            )
    selected = _prepare_selected_values(
        tmp_path,
        payload,
        [rule],
        {"selected": _SelectedBindingTensorPolicy((), "float32", Decimal("1e-8"), Decimal("0.01"))},
    )
    assert selected.applied_binding_ids == ("selected",)
    assert np.asarray(selected.materialized_state.tax_rate).item() == pytest.approx(0.2, abs=1e-8)
    with localcontext() as context:
        context.prec = 1
        selected = _prepare_selected_values(
            tmp_path,
            {"percent": 23},
            [rule],
            {
                "selected": _SelectedBindingTensorPolicy(
                    (), "float32", Decimal("1e-8"), Decimal("0.01")
                )
            },
        )
    assert np.asarray(selected.materialized_state.tax_rate).item() == pytest.approx(0.23, abs=1e-8)


def _selected_legacy_initial_binding(
    store: FileSystemCAS,
    payload: dict[str, object],
    rule: FoundryInputBindingRule,
) -> FoundryInputBindingsRef:
    payload_ref = store.put_json(
        payload,
        PutOptions(kind="fabric.binding_payload", media_type="application/json"),
        return_selected_profile=True,
    )
    snapshot_ref = store.put_json(
        DataSnapshot(data_ref=payload_ref),
        PutOptions(
            kind=DataSnapshot.ARTIFACT_KIND,
            media_type=DataSnapshot.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=DataSnapshot.ARTIFACT_SCHEMA_NAME, version=DataSnapshot.ARTIFACT_SCHEMA_VERSION
            ),
            inputs=[input_ref_from_artifact_ref(payload_ref, role="data_ref")],
        ),
        return_selected_profile=True,
    )
    return build_input_bindings(
        store,
        data_snapshot_ref=snapshot_ref,
        registry_bundle_ref=build_default_registry_bundle(
            store, return_selected_profile=True
        ).bundle_ref,
        rules=[rule],
        return_selected_profile=True,
    ).input_bindings_ref


@pytest.mark.parametrize(
    ("payload", "default", "supplied"),
    [
        ({"value": [100, 200]}, None, ("agents.income",)),
        ({"value": [0]}, None, ("agents.income",)),
        ({"value": None}, None, ()),
        ({"value": 100}, None, ()),
        ({}, [100], ()),
    ],
)
def test_legacy_explicit_initial_supply_requires_exact_replayed_value(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    payload: dict[str, object],
    default: list[int] | None,
    supplied: tuple[str, ...],
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    ref = _selected_legacy_initial_binding(
        store,
        payload,
        FoundryInputBindingRule(
            binding_id="income",
            source_path="value",
            target_slot_id="agents.income",
            default_value=default,
        ),
    )
    fresh = FileSystemCAS(tmp_path / "cas")
    assert (
        _without_writes(
            fresh,
            monkeypatch,
            lambda: reconcile_explicit_initial_binding_slots(
                fresh,
                input_bindings_ref=ref,
                expected_state_paths={"agents.income": "agents.income"},
            ),
        )
        == supplied
    )


def test_legacy_explicit_initial_supply_refuses_same_bytes_without_selected_edge(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    ref = _selected_legacy_initial_binding(
        store,
        {"value": [100, 200], "other": [100, 300]},
        FoundryInputBindingRule(
            binding_id="income", source_path="value", target_slot_id="agents.income"
        ),
    )
    manifest = store.get_manifest(ref)
    selected = load_input_bindings(store, ref)
    missing_data_edge = store.put_json(
        selected,
        PutOptions(
            kind=FoundryInputBindings.ARTIFACT_KIND,
            media_type=FoundryInputBindings.ARTIFACT_MEDIA_TYPE,
            schema=manifest.artifact_schema,
            inputs=[edge for edge in manifest.inputs if edge.role != "input.data_snapshot_ref"],
        ),
        return_selected_profile=True,
    )
    assert missing_data_edge.artifact_id == ref.artifact_id
    assert missing_data_edge.manifest_profile_sha256 != ref.manifest_profile_sha256
    wrong_rule = store.put_json(
        selected.model_copy(
            update={"rules": [selected.rules[0].model_copy(update={"source_path": "other"})]}
        ),
        PutOptions(
            kind=FoundryInputBindings.ARTIFACT_KIND,
            media_type=FoundryInputBindings.ARTIFACT_MEDIA_TYPE,
            schema=manifest.artifact_schema,
            inputs=manifest.inputs,
        ),
        return_selected_profile=True,
    )
    fresh = FileSystemCAS(tmp_path / "cas")
    with pytest.raises(
        ValueError, match="^explicit_initial_binding_lineage_mismatch:input.data_snapshot_ref$"
    ):
        reconcile_explicit_initial_binding_slots(
            fresh,
            input_bindings_ref=FoundryInputBindingsRef.model_validate(
                missing_data_edge.model_dump(mode="python")
            ),
            expected_state_paths={"agents.income": "agents.income"},
        )
    with pytest.raises(ValueError, match="^explicit_initial_binding_state_mismatch:agents.income$"):
        reconcile_explicit_initial_binding_slots(
            fresh,
            input_bindings_ref=FoundryInputBindingsRef.model_validate(wrong_rule.model_dump()),
            expected_state_paths={"agents.income": "agents.income"},
        )
    assert reconcile_explicit_initial_binding_slots(
        fresh,
        input_bindings_ref=ref,
        expected_state_paths={"agents.income": "agents.income"},
    ) == ("agents.income",)
