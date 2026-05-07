from __future__ import annotations

from decimal import Decimal

import jax.numpy as jnp
import numpy as np
import pytest
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.contracts.foundry import (
    ExecPlan,
    FoundryExecConfig,
    PatchOp,
    ProgramEdge,
    ProgramGraph,
    ProgramGraphRef,
    ProgramNode,
    ProgramOp,
    StateDelta,
)
from polisyos.foundry.contracts.state import GlobalState
from polisyos.foundry.execute._internal.graph import (
    _append_method_patch_records,
    _append_patch_map_records,
    _build_state_delta_ops,
    _incoming_dependencies,
    _mask_barrier_targets,
)
from polisyos.foundry.execute._internal.models import (
    get_state_path,
    load_tensor,
    put_tensor,
    set_state_path,
)
from polisyos.foundry.execute._internal.ops import (
    apply_op,
    apply_operator,
    apply_ops_for_slot,
    apply_ops_to_state,
    coerce_number,
    coerce_selector_scalar,
    evaluate_selector,
    selector_field_values,
    validate_ops_compatibility,
)
from polisyos.foundry.execute._internal.ops import (
    check_constraints as check_executor_constraints,
)
from polisyos.foundry.execute._internal.patching import (
    _merge_patch_records,
    apply_patch_map,
    apply_patch_records,
    apply_state_delta_and_snapshot,
)
from polisyos.foundry.execute._internal.posture import resolve_execution_posture
from polisyos.foundry.methods.exceptions import (
    ContractViolationError,
    SelectorCoercionError,
    SelectorEvaluationError,
    StatePathTraversalError,
)
from polisyos.ir.governance.selector_expr import (
    SelectorAll,
    SelectorAny,
    SelectorNot,
    SelectorPredicate,
)
from polisyos.ir.kernel import (
    DEFAULT_MERGE_RULE_REGISTRY,
    DEFAULT_SELECTOR_FIELD_REGISTRY,
    DEFAULT_SLOT_REGISTRY,
    ConstraintRegistry,
    ConstraintSpec,
    MergeRuleKind,
)
from polisyos.ir.kernel.values import CountValue, DurationValue, MoneyValue, RateValue
from polisyos.ir.types import SelectorOperator
from pydantic import ValidationError


def _program_ref() -> ProgramGraphRef:
    return ProgramGraphRef(
        artifact_id=ArtifactID.from_sha256_hex("a" * 64),
        kind="foundry.program_graph",
        media_type="application/json",
    )


def _ir_ref() -> ArtifactRef:
    return ArtifactRef(
        artifact_id=ArtifactID.from_sha256_hex("b" * 64),
        kind="ir.trinity_bundle",
        media_type="application/json",
    )


def test_state_path_helpers_update_nested_state_without_mutating_original() -> None:
    state = GlobalState.empty(n_agents=2, n_firms=1)

    updated = set_state_path(state, "agents.income", jnp.asarray([10.0, 20.0]))

    assert np.allclose(np.asarray(get_state_path(updated, "agents.income")), [10.0, 20.0])
    assert np.allclose(np.asarray(get_state_path(state, "agents.income")), [0.0, 0.0])


def test_state_path_helpers_report_invalid_segment_context() -> None:
    state = GlobalState.empty(n_agents=1, n_firms=1)

    with pytest.raises(StatePathTraversalError) as exc_info:
        set_state_path(state, "agents..income", jnp.asarray([1.0]))

    assert exc_info.value.path == "agents..income"
    assert exc_info.value.segment == ""
    assert exc_info.value.segment_index == 1


def test_apply_ops_for_slot_combines_multiple_add_ops_with_masks(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    base = jnp.asarray([10.0, 20.0, 30.0])
    value_a = put_tensor(store, np.asarray([1.0, 1.0, 1.0], dtype=np.float32))
    value_b = put_tensor(store, np.asarray([10.0, 10.0, 10.0], dtype=np.float32))
    mask_b = put_tensor(store, np.asarray([True, False, True]))

    result = apply_ops_for_slot(
        store,
        base,
        [
            PatchOp(slot_id="agents.income", op="add", value_ref=value_a),
            PatchOp(
                slot_id="agents.income",
                op="add",
                value_ref=value_b,
                mask_ref=mask_b,
                mask_scope="per_agent",
            ),
        ],
    )

    np.testing.assert_allclose(np.asarray(result), np.asarray([21.0, 21.0, 41.0]))


def test_apply_op_set_with_mask_and_missing_value_ref(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    base = jnp.asarray([1.0, 2.0, 3.0])
    value_ref = put_tensor(store, np.asarray([10.0, 20.0, 30.0], dtype=np.float32))
    mask_ref = put_tensor(store, np.asarray([True, False, True]))

    result = apply_op(
        store,
        base,
        PatchOp(
            slot_id="agents.income",
            op="set",
            value_ref=value_ref,
            mask_ref=mask_ref,
            mask_scope="per_agent",
        ),
    )

    np.testing.assert_allclose(np.asarray(result), np.asarray([10.0, 2.0, 30.0]))

    with pytest.raises(ValueError, match="missing value_ref"):
        apply_op(store, base, PatchOp(slot_id="agents.income", op="add"))


def test_apply_ops_to_state_applies_set_and_rejects_unknown_slot(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    base_state = GlobalState.empty(n_agents=1, n_firms=1)
    value_ref = put_tensor(store, np.asarray(0.4, dtype=np.float32))

    updated = apply_ops_to_state(
        store,
        base_state=base_state,
        ops=[PatchOp(slot_id="global.tax_rate", op="set", value_ref=value_ref)],
        slot_registry=DEFAULT_SLOT_REGISTRY,
        merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
    )

    assert float(np.asarray(updated.tax_rate)) == pytest.approx(0.4)

    with pytest.raises(ValueError, match="missing state_path"):
        apply_ops_to_state(
            store,
            base_state=base_state,
            ops=[PatchOp(slot_id="unknown.slot", op="set", value_ref=value_ref)],
            slot_registry=DEFAULT_SLOT_REGISTRY,
            merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
        )


def test_validate_ops_compatibility_rejects_set_for_sum_rule(tmp_path) -> None:
    value_ref = put_tensor(FileSystemCAS(tmp_path), np.asarray(1.0, dtype=np.float32))

    with pytest.raises(ValueError, match="incompatible"):
        validate_ops_compatibility(
            "government.balance",
            MergeRuleKind.SUM,
            [PatchOp(slot_id="government.balance", op="set", value_ref=value_ref)],
        )


def test_selector_scalar_and_operator_paths() -> None:
    values = jnp.asarray([1.0, 2.0, 3.0])

    assert coerce_selector_scalar(Decimal("1.25")) == 1.25
    assert coerce_selector_scalar(True) is True
    assert coerce_selector_scalar(3) == 3
    assert coerce_selector_scalar(" false ") is False
    assert coerce_selector_scalar("2.5") == 2.5
    assert coerce_selector_scalar("not-number") == "not-number"

    np.testing.assert_array_equal(
        np.asarray(apply_operator(values, SelectorOperator.IN, [1, 3])),
        np.asarray([True, False, True]),
    )
    np.testing.assert_array_equal(
        np.asarray(apply_operator(values, SelectorOperator.NOT_IN, [1, 3])),
        np.asarray([False, True, False]),
    )
    np.testing.assert_array_equal(
        np.asarray(apply_operator(values, SelectorOperator.BETWEEN, [1, 2])),
        np.asarray([True, True, False]),
    )
    np.testing.assert_array_equal(
        np.asarray(apply_operator(values, SelectorOperator.NOT_EQUALS, 2)),
        np.asarray([True, False, True]),
    )
    np.testing.assert_array_equal(
        np.asarray(apply_operator(values, SelectorOperator.LESS_THAN, 3)),
        np.asarray([True, True, False]),
    )
    np.testing.assert_array_equal(
        np.asarray(apply_operator(values, SelectorOperator.GREATER_EQUAL, 2)),
        np.asarray([False, True, True]),
    )
    np.testing.assert_array_equal(
        np.asarray(apply_operator(values, SelectorOperator.LESS_EQUAL, 2)),
        np.asarray([True, True, False]),
    )
    np.testing.assert_array_equal(
        np.asarray(apply_operator(values, SelectorOperator.CONTAINS, [2, 3])),
        np.asarray([False, True, True]),
    )

    with pytest.raises(SelectorCoercionError, match="boolean"):
        apply_operator(values, SelectorOperator.GREATER_THAN, True, field_id="income")
    with pytest.raises(SelectorCoercionError, match="BETWEEN expects"):
        apply_operator(values, SelectorOperator.BETWEEN, [1], field_id="income")
    with pytest.raises(SelectorCoercionError, match="CONTAINS expects"):
        apply_operator(values, SelectorOperator.CONTAINS, 2, field_id="income")


def test_evaluate_selector_composes_all_any_not_and_scope_errors() -> None:
    state = GlobalState.empty(n_agents=3, n_firms=2).replace(
        agents=GlobalState.empty(n_agents=3, n_firms=2).agents.replace(
            income=jnp.asarray([10.0, 20.0, 30.0])
        ),
    )

    ids, id_scope = selector_field_values(
        state,
        "agent_id",
        selector_field_registry=DEFAULT_SELECTOR_FIELD_REGISTRY,
    )
    assert id_scope.value == "per_agent"
    np.testing.assert_array_equal(np.asarray(ids), np.asarray([0, 1, 2]))

    selector = SelectorAll(
        clauses=[
            SelectorPredicate(field="income", operator=SelectorOperator.GREATER_THAN, value=15),
            SelectorPredicate(field="agent_id", operator=SelectorOperator.IN, value=[1, 2]),
        ]
    )
    mask, scope = evaluate_selector(
        selector,
        state,
        selector_field_registry=DEFAULT_SELECTOR_FIELD_REGISTRY,
    )

    assert scope.value == "per_agent"
    np.testing.assert_array_equal(np.asarray(mask), np.asarray([False, True, True]))

    any_selector = SelectorAny(
        clauses=[
            SelectorPredicate(field="income", operator=SelectorOperator.EQUALS, value=10),
            SelectorNot(
                clause=SelectorPredicate(
                    field="agent_id",
                    operator=SelectorOperator.IN,
                    value=[0, 1],
                )
            ),
        ]
    )
    any_mask, _scope = evaluate_selector(
        any_selector,
        state,
        selector_field_registry=DEFAULT_SELECTOR_FIELD_REGISTRY,
    )
    np.testing.assert_array_equal(np.asarray(any_mask), np.asarray([True, False, True]))

    with pytest.raises(SelectorEvaluationError, match="requires selector field registry"):
        selector_field_values(state, "income", selector_field_registry=None)
    with pytest.raises(SelectorEvaluationError, match="selector mixes scopes"):
        evaluate_selector(
            SelectorAll(
                clauses=[
                    SelectorPredicate(
                        field="income",
                        operator=SelectorOperator.GREATER_THAN,
                        value=0,
                    ),
                    SelectorPredicate(field="sector", operator=SelectorOperator.EQUALS, value=0),
                ]
            ),
            state,
            selector_field_registry=DEFAULT_SELECTOR_FIELD_REGISTRY,
        )
    with pytest.raises(ValidationError, match="at least 1 item"):
        SelectorAll(clauses=[])


def test_coerce_number_supports_kernel_value_wrappers() -> None:
    assert coerce_number(Decimal("2.5")) == Decimal("2.5")
    assert coerce_number(2) == Decimal("2")
    assert coerce_number(2.5) == Decimal("2.5")
    assert coerce_number("3.5") == Decimal("3.5")
    assert coerce_number("not-a-number") is None
    assert coerce_number(True) is None
    assert coerce_number(MoneyValue(amount=Decimal("12.00"), currency="USD")) == Decimal("12.00")
    assert coerce_number(RateValue(value=Decimal("25"), base="percent")) == Decimal("0.25")
    assert coerce_number(CountValue(value=4)) == Decimal("4")
    assert coerce_number(DurationValue(value=6, unit="month")) == Decimal("6")


def test_check_constraints_lowers_values_and_raises_on_missing_or_violated() -> None:
    state = GlobalState.empty(n_agents=1, n_firms=1).replace(government_balance=jnp.asarray(10.0))
    registry = ConstraintRegistry(
        constraints={
            "minimum_balance": ConstraintSpec(
                constraint_id="minimum_balance",
                slot_id="government.balance",
                operator=">=",
                unit_id="usd",
            )
        }
    )

    report = check_executor_constraints(
        ["minimum_balance", 42, "unknown_constraint"],
        constraint_registry=registry,
        constraint_values={"minimum_balance": Decimal("5")},
        slot_registry=DEFAULT_SLOT_REGISTRY,
        state=state,
        events=[],
    )

    assert report.hard_fail is False
    assert report.total_constraints == 1

    with pytest.raises(ValueError, match="missing value"):
        check_executor_constraints(
            ["minimum_balance"],
            constraint_registry=registry,
            constraint_values={},
            slot_registry=DEFAULT_SLOT_REGISTRY,
            state=state,
        )
    with pytest.raises(ValueError, match="non-numeric"):
        check_executor_constraints(
            ["minimum_balance"],
            constraint_registry=registry,
            constraint_values={"minimum_balance": "bad"},
            slot_registry=DEFAULT_SLOT_REGISTRY,
            state=state,
        )
    with pytest.raises(ValueError, match="violated"):
        check_executor_constraints(
            ["minimum_balance"],
            constraint_registry=registry,
            constraint_values={"minimum_balance": Decimal("20")},
            slot_registry=DEFAULT_SLOT_REGISTRY,
            state=state,
        )


def test_apply_patch_records_merges_more_than_three_writers() -> None:
    base_state = GlobalState.empty(n_agents=1, n_firms=1).replace(
        government_balance=jnp.asarray(100.0)
    )
    patch_records = {
        "government.balance": [
            {"node_id": f"writer-{index}", "delta": jnp.asarray(float(index))}
            for index in range(1, 6)
        ]
    }

    updated = apply_patch_records(
        base_state,
        patch_records,
        slot_registry=DEFAULT_SLOT_REGISTRY,
        merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
    )

    assert float(np.asarray(updated.government_balance)) == pytest.approx(115.0)


def test_apply_patch_records_supports_new_value_base_value_and_unknown_slot() -> None:
    base_state = GlobalState.empty(n_agents=1, n_firms=1).replace(
        government_balance=jnp.asarray(100.0)
    )

    updated = apply_patch_records(
        base_state,
        {
            "government.balance": [
                {
                    "node_id": "writer",
                    "new_value": jnp.asarray(125.0),
                    "base_value": jnp.asarray(100.0),
                }
            ]
        },
        slot_registry=DEFAULT_SLOT_REGISTRY,
        merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
    )

    assert float(np.asarray(updated.government_balance)) == pytest.approx(125.0)

    with pytest.raises(ValueError, match="missing state_path"):
        apply_patch_records(
            base_state,
            {"unknown.slot": [{"node_id": "writer", "delta": jnp.asarray(1.0)}]},
            slot_registry=DEFAULT_SLOT_REGISTRY,
            merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
        )


def test_apply_patch_map_and_merge_patch_records_wrapper(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    base_state = GlobalState.empty(n_agents=1, n_firms=1).replace(
        government_balance=jnp.asarray(10.0)
    )

    updated = apply_patch_map(
        base_state,
        {"government.balance": {"delta": jnp.asarray(3.0)}},
        slot_registry=DEFAULT_SLOT_REGISTRY,
        merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
        default_node_id="patch-map",
        priority=7,
    )

    assert float(np.asarray(updated.government_balance)) == pytest.approx(13.0)

    ops = _merge_patch_records(
        store,
        {"government.balance": [{"node_id": "writer", "delta": jnp.asarray(2.0)}]},
        slot_registry=DEFAULT_SLOT_REGISTRY,
        merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
    )

    assert len(ops) == 1
    assert ops[0].slot_id == "government.balance"
    assert ops[0].op == "add"


def test_apply_state_delta_and_snapshot_persists_snapshot_with_base_ref(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    base_state = GlobalState.empty(n_agents=1, n_firms=1).replace(
        government_balance=jnp.asarray(10.0)
    )
    value_ref = put_tensor(store, np.asarray(5.0, dtype=np.float32))
    state_delta_ref = store.put_json(
        StateDelta(
            ops=[
                PatchOp(
                    slot_id="government.balance",
                    op="add",
                    value_ref=value_ref,
                )
            ]
        ),
        PutOptions(kind="foundry.state_delta", media_type="application/json"),
    )
    base_ref = ArtifactRef(
        artifact_id=ArtifactID.from_sha256_hex("d" * 64),
        kind="foundry.state_snapshot",
        media_type="application/json",
    )

    updated, artifacts = apply_state_delta_and_snapshot(
        store,
        base_state=base_state,
        state_delta_ref=state_delta_ref,
        slot_registry=DEFAULT_SLOT_REGISTRY,
        merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
        step=2,
        base_ref=base_ref,
    )

    assert float(np.asarray(updated.government_balance)) == pytest.approx(15.0)
    assert artifacts.state_snapshot_ref.kind == "foundry.state_snapshot"


def test_resolve_execution_posture_prefers_runtime_seed_and_records_hints() -> None:
    exec_plan = ExecPlan(
        program_ref=_program_ref(),
        random_seed=7,
        mode="audit",
        jit=True,
        max_steps=100,
        determinism_tier="unknown-tier",
    )
    exec_config = FoundryExecConfig(seed=11, mode="perf", max_steps=5)

    posture = resolve_execution_posture(exec_plan, exec_config)

    assert posture.seed == 11
    assert posture.seed_source == "exec_config.seed"
    assert posture.mode == "perf"
    assert posture.max_steps == 5
    assert "unsupported_exec_hint:jit=eager_only" in posture.notes
    assert "unsupported_exec_hint:mode=perf" in posture.notes
    assert "unknown_determinism_tier:unknown-tier" in posture.notes


def test_resolve_execution_posture_records_environment_fingerprint_probe_failure(
    monkeypatch,
) -> None:
    def _raise_capture(*_args, **_kwargs):
        raise RuntimeError("probe failed")

    monkeypatch.setattr(
        "polisyos.foundry.execute._internal.posture.EnvironmentFingerprint.capture",
        _raise_capture,
    )
    exec_plan = ExecPlan(
        program_ref=_program_ref(),
        random_seed=7,
        mode="dev",
        jit=False,
        max_steps=100,
        determinism_tier="strict_cpu",
        environment_fingerprint="expected-fingerprint",
    )

    posture = resolve_execution_posture(exec_plan)

    assert posture.current_environment_fingerprint is None
    assert "environment_fingerprint_unavailable:RuntimeError" in posture.notes


def test_executor_graph_dependency_helpers_track_mask_barriers() -> None:
    graph = ProgramGraph(
        ir_ref=_ir_ref(),
        nodes=[
            ProgramNode(
                node_id="mask",
                node_kind="op",
                op=ProgramOp(op_kind="make_mask", params={"selector": {}}),
            ),
            ProgramNode(
                node_id="apply",
                node_kind="op",
                op=ProgramOp(op_kind="apply_mechanism", params={"mask_id": "mask"}),
            ),
        ],
        edges=[ProgramEdge(src="writer", dst="mask")],
    )

    assert _incoming_dependencies(graph) == {"mask": ("writer",)}
    assert _mask_barrier_targets(graph) == {"mask": "apply"}


def test_append_patch_map_records_validates_expected_outputs() -> None:
    node = ProgramNode(
        node_id="mechanism_node",
        node_kind="mechanism",
        mechanism_type="income_tax",
        outputs=["agents.income"],
    )
    patch_records: dict[str, list[dict[str, object]]] = {}

    _append_patch_map_records(
        patch_records,
        node=node,
        payload={"priority": 9},
        patch_map={"agents.income": {"delta": jnp.asarray([1.0, 2.0])}},
    )

    assert patch_records["agents.income"][0]["node_id"] == "mechanism_node"
    assert patch_records["agents.income"][0]["priority"] == 9

    with pytest.raises(ContractViolationError, match="unexpected patch outputs"):
        _append_patch_map_records(
            {},
            node=node,
            payload={},
            patch_map={"unknown.slot": [{"delta": 1.0}]},
        )


def test_append_method_patch_records_adds_provenance_and_validates_contract() -> None:
    node = ProgramNode(
        node_id="method_node",
        node_kind="method",
        method_fqn="tests.method@1.0.0",
        outputs=["government.balance"],
    )
    patch_records: dict[str, list[dict[str, object]]] = {}
    provenance: dict[str, list[str]] = {}

    _append_method_patch_records(
        patch_records,
        provenance,
        node=node,
        output_payload={"patch_records": {"government.balance": [{"delta": jnp.asarray(4.0)}]}},
    )

    assert patch_records["government.balance"][0]["node_id"] == "method_node"
    assert provenance["government.balance"] == ["tests.method@1.0.0"]

    with pytest.raises(ContractViolationError, match="declared outputs require patch_records"):
        _append_method_patch_records({}, {}, node=node, output_payload={})


def test_build_state_delta_ops_uses_sum_diff_for_touched_slots(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    base_state = GlobalState.empty(n_agents=1, n_firms=1).replace(
        government_balance=jnp.asarray(10.0)
    )
    final_state = base_state.replace(government_balance=jnp.asarray(15.0))

    ops = _build_state_delta_ops(
        store,
        base_state=base_state,
        final_state=final_state,
        touched_slots={"government.balance"},
        slot_registry=DEFAULT_SLOT_REGISTRY,
        merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
    )

    assert len(ops) == 1
    assert ops[0].slot_id == "government.balance"
    assert ops[0].op == "add"
    assert float(np.asarray(load_tensor(store, ops[0].value_ref))) == pytest.approx(5.0)
