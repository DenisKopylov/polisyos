from __future__ import annotations

import hypothesis.strategies as st
import jax.numpy as jnp
import numpy as np
import pytest
from hypothesis import HealthCheck, assume, given, settings

from polisyos.foundry.merge_engine import (
    JAXMergeEngine,
    MergeConflictKind,
    MergeEngine,
    MergeRecord,
)
from polisyos.ir.kernel import (
    DEFAULT_MERGE_RULE_REGISTRY,
    DEFAULT_SLOT_REGISTRY,
    MergeRuleRef,
    SlotKind,
    SlotRegistry,
    SlotScope,
    SlotSpec,
    SlotValueType,
)

_PROPERTY_TEST_HEALTH_CHECKS = [
    HealthCheck.function_scoped_fixture,
    HealthCheck.too_slow,
]


@pytest.fixture
def sum_slot_registry() -> SlotRegistry:
    return SlotRegistry(
        slots={
            "test.sum_slot": SlotSpec(
                slot_id="test.sum_slot",
                scope=SlotScope.GLOBAL,
                value_type=SlotValueType.DECIMAL,
                kind=SlotKind.FLOW,
                merge_rule=MergeRuleRef(rule_id="sum"),
                state_path="test.sum_slot",
            )
        }
    )


@pytest.fixture
def priority_slot_registry() -> SlotRegistry:
    return SlotRegistry(
        slots={
            "test.priority_slot": SlotSpec(
                slot_id="test.priority_slot",
                scope=SlotScope.GLOBAL,
                value_type=SlotValueType.DECIMAL,
                kind=SlotKind.STOCK,
                merge_rule=MergeRuleRef(rule_id="priority"),
                state_path="test.priority_slot",
            )
        }
    )


@pytest.fixture
def error_slot_registry() -> SlotRegistry:
    return SlotRegistry(
        slots={
            "test.error_slot": SlotSpec(
                slot_id="test.error_slot",
                scope=SlotScope.GLOBAL,
                value_type=SlotValueType.DECIMAL,
                kind=SlotKind.STOCK,
                merge_rule=MergeRuleRef(rule_id="error"),
                state_path="test.error_slot",
            )
        }
    )


@pytest.fixture
def override_slot_registry() -> SlotRegistry:
    return SlotRegistry(
        slots={
            "test.override_slot": SlotSpec(
                slot_id="test.override_slot",
                scope=SlotScope.GLOBAL,
                value_type=SlotValueType.DECIMAL,
                kind=SlotKind.STOCK,
                merge_rule=MergeRuleRef(rule_id="override"),
                state_path="test.override_slot",
            )
        }
    )


class TestCommutativity:
    @given(
        delta_a=st.floats(-1000, 1000, allow_nan=False, allow_infinity=False),
        delta_b=st.floats(-1000, 1000, allow_nan=False, allow_infinity=False),
        base=st.floats(-1000, 1000, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=200, suppress_health_check=_PROPERTY_TEST_HEALTH_CHECKS)
    def test_sum_commutativity(self, sum_slot_registry, delta_a, delta_b, base):
        engine = MergeEngine(sum_slot_registry, DEFAULT_MERGE_RULE_REGISTRY)
        record_a = MergeRecord(node_id="a", slot_id="test.sum_slot", delta=delta_a)
        record_b = MergeRecord(node_id="b", slot_id="test.sum_slot", delta=delta_b)

        result_ab = engine.merge_records([record_a, record_b], {"test.sum_slot": base})
        result_ba = engine.merge_records([record_b, record_a], {"test.sum_slot": base})

        np.testing.assert_allclose(
            result_ab.merged_values["test.sum_slot"],
            result_ba.merged_values["test.sum_slot"],
            rtol=1e-10,
        )

    @given(
        deltas=st.lists(st.integers(-1000, 1000), min_size=4, max_size=8),
        base=st.integers(-1000, 1000),
    )
    @settings(max_examples=150, suppress_health_check=_PROPERTY_TEST_HEALTH_CHECKS)
    def test_sum_commutativity_for_many_writers(self, sum_slot_registry, deltas, base):
        engine = MergeEngine(sum_slot_registry, DEFAULT_MERGE_RULE_REGISTRY)
        records = [
            MergeRecord(node_id=f"writer-{index}", slot_id="test.sum_slot", delta=delta)
            for index, delta in enumerate(deltas)
        ]

        result_forward = engine.merge_records(records, {"test.sum_slot": base})
        result_reverse = engine.merge_records(list(reversed(records)), {"test.sum_slot": base})

        assert (
            result_forward.merged_values["test.sum_slot"]
            == result_reverse.merged_values["test.sum_slot"]
        )

    @given(
        value_a=st.floats(-1000, 1000, allow_nan=False, allow_infinity=False),
        value_b=st.floats(-1000, 1000, allow_nan=False, allow_infinity=False),
        priority_a=st.integers(0, 100),
        priority_b=st.integers(0, 100),
    )
    @settings(max_examples=200, suppress_health_check=_PROPERTY_TEST_HEALTH_CHECKS)
    def test_priority_commutativity(
        self, priority_slot_registry, value_a, value_b, priority_a, priority_b
    ):
        assume(priority_a != priority_b)
        engine = MergeEngine(priority_slot_registry, DEFAULT_MERGE_RULE_REGISTRY)

        record_a = MergeRecord(
            node_id="a", slot_id="test.priority_slot", value=value_a, priority=priority_a
        )
        record_b = MergeRecord(
            node_id="b", slot_id="test.priority_slot", value=value_b, priority=priority_b
        )

        result_ab = engine.merge_records([record_a, record_b])
        result_ba = engine.merge_records([record_b, record_a])

        assert (
            result_ab.merged_values["test.priority_slot"]
            == result_ba.merged_values["test.priority_slot"]
        )


class TestAssociativity:
    @given(
        delta_a=st.floats(-1000, 1000, allow_nan=False, allow_infinity=False),
        delta_b=st.floats(-1000, 1000, allow_nan=False, allow_infinity=False),
        delta_c=st.floats(-1000, 1000, allow_nan=False, allow_infinity=False),
        base=st.floats(-1000, 1000, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=200, suppress_health_check=_PROPERTY_TEST_HEALTH_CHECKS)
    def test_sum_associativity(self, sum_slot_registry, delta_a, delta_b, delta_c, base):
        engine = MergeEngine(sum_slot_registry, DEFAULT_MERGE_RULE_REGISTRY)

        result_ab = engine.merge_records(
            [
                MergeRecord(node_id="a", slot_id="test.sum_slot", delta=delta_a),
                MergeRecord(node_id="b", slot_id="test.sum_slot", delta=delta_b),
            ],
            {"test.sum_slot": base},
        )
        intermediate = result_ab.merged_values["test.sum_slot"]
        result_left = engine.merge_records(
            [MergeRecord(node_id="c", slot_id="test.sum_slot", delta=delta_c)],
            {"test.sum_slot": intermediate},
        )

        result_all = engine.merge_records(
            [
                MergeRecord(node_id="a", slot_id="test.sum_slot", delta=delta_a),
                MergeRecord(node_id="b", slot_id="test.sum_slot", delta=delta_b),
                MergeRecord(node_id="c", slot_id="test.sum_slot", delta=delta_c),
            ],
            {"test.sum_slot": base},
        )

        np.testing.assert_allclose(
            result_left.merged_values["test.sum_slot"],
            result_all.merged_values["test.sum_slot"],
            rtol=1e-10,
        )

    @given(
        values=st.lists(
            st.floats(-1000, 1000, allow_nan=False, allow_infinity=False),
            min_size=3,
            max_size=3,
            unique=True,
        ),
        priorities=st.lists(st.integers(0, 1000), min_size=3, max_size=3, unique=True),
    )
    @settings(max_examples=150, suppress_health_check=_PROPERTY_TEST_HEALTH_CHECKS)
    def test_priority_associativity(self, priority_slot_registry, values, priorities):
        engine = MergeEngine(priority_slot_registry, DEFAULT_MERGE_RULE_REGISTRY)
        record_a = MergeRecord(
            node_id="a", slot_id="test.priority_slot", value=values[0], priority=priorities[0]
        )
        record_b = MergeRecord(
            node_id="b", slot_id="test.priority_slot", value=values[1], priority=priorities[1]
        )
        record_c = MergeRecord(
            node_id="c", slot_id="test.priority_slot", value=values[2], priority=priorities[2]
        )

        result_ab = engine.merge_records([record_a, record_b])
        winner_ab_value = result_ab.merged_values["test.priority_slot"]
        winner_ab = record_a if winner_ab_value == record_a.value else record_b
        result_left = engine.merge_records([winner_ab, record_c])

        result_bc = engine.merge_records([record_b, record_c])
        winner_bc_value = result_bc.merged_values["test.priority_slot"]
        winner_bc = record_b if winner_bc_value == record_b.value else record_c
        result_right = engine.merge_records([record_a, winner_bc])

        assert (
            result_left.merged_values["test.priority_slot"]
            == result_right.merged_values["test.priority_slot"]
        )


class TestIdempotency:
    @given(
        value=st.floats(-1000, 1000, allow_nan=False, allow_infinity=False),
        priority=st.integers(0, 100),
    )
    @settings(max_examples=100, suppress_health_check=_PROPERTY_TEST_HEALTH_CHECKS)
    def test_priority_idempotency(self, priority_slot_registry, value, priority):
        engine = MergeEngine(priority_slot_registry, DEFAULT_MERGE_RULE_REGISTRY)
        record = MergeRecord(
            node_id="a", slot_id="test.priority_slot", value=value, priority=priority
        )
        result_once = engine.merge_records([record])
        result_twice = engine.merge_records([record, record])
        assert (
            result_once.merged_values["test.priority_slot"]
            == result_twice.merged_values["test.priority_slot"]
        )


class TestConflictDetection:
    def test_error_single_writer_ok(self, error_slot_registry):
        engine = MergeEngine(error_slot_registry, DEFAULT_MERGE_RULE_REGISTRY)
        record = MergeRecord(node_id="a", slot_id="test.error_slot", value=42.0)
        report = engine.merge_records([record])
        assert report.ok
        assert report.merged_values["test.error_slot"] == 42.0

    def test_error_multiple_writers_conflict(self, error_slot_registry):
        engine = MergeEngine(error_slot_registry, DEFAULT_MERGE_RULE_REGISTRY)
        records = [
            MergeRecord(node_id="a", slot_id="test.error_slot", value=42.0),
            MergeRecord(node_id="b", slot_id="test.error_slot", value=43.0),
        ]
        report = engine.merge_records(records)
        assert not report.ok
        assert len(report.conflicts) == 1
        conflict = report.conflicts[0]
        assert conflict.slot_id == "test.error_slot"
        assert conflict.kind == MergeConflictKind.MULTIPLE_WRITERS
        assert set(conflict.writers) == {"a", "b"}


class TestRegressions:
    def test_override_deterministic_with_same_timestamp(self, override_slot_registry):
        engine = MergeEngine(override_slot_registry, DEFAULT_MERGE_RULE_REGISTRY)
        records = [
            MergeRecord(node_id="zebra", slot_id="test.override_slot", value=1.0, timestamp=100),
            MergeRecord(node_id="alpha", slot_id="test.override_slot", value=2.0, timestamp=100),
        ]
        results = []
        for _ in range(10):
            report = engine.merge_records(records)
            results.append(report.merged_values["test.override_slot"])
        assert all(result == results[0] for result in results)
        assert results[0] == 1.0


class TestJAXMergeEngine:
    def test_sum_jax_vectorized(self):
        engine = JAXMergeEngine(DEFAULT_SLOT_REGISTRY, DEFAULT_MERGE_RULE_REGISTRY)
        base = jnp.array([1.0, 2.0, 3.0])
        deltas = [jnp.array([0.1, 0.2, 0.3]), jnp.array([0.5, 0.5, 0.5])]
        masks = [jnp.array([True, True, True]), jnp.array([True, True, True])]
        result = engine.merge_sum_jax(base, deltas, masks)
        expected = jnp.array([1.6, 2.7, 3.8])
        np.testing.assert_allclose(result, expected, rtol=1e-5)

    def test_sum_jax_with_masks(self):
        engine = JAXMergeEngine(DEFAULT_SLOT_REGISTRY, DEFAULT_MERGE_RULE_REGISTRY)
        base = jnp.array([1.0, 2.0, 3.0])
        deltas = [jnp.array([10.0, 10.0, 10.0]), jnp.array([100.0, 100.0, 100.0])]
        masks = [
            jnp.array([True, False, True]),
            jnp.array([False, True, False]),
        ]
        result = engine.merge_sum_jax(base, deltas, masks)
        expected = jnp.array([11.0, 102.0, 13.0])
        np.testing.assert_allclose(result, expected, rtol=1e-5)

    def test_priority_jax_deterministic(self):
        engine = JAXMergeEngine(DEFAULT_SLOT_REGISTRY, DEFAULT_MERGE_RULE_REGISTRY)
        base = jnp.array(0.0)
        values = [jnp.array(10.0), jnp.array(20.0), jnp.array(30.0)]
        priorities = [jnp.array(5.0), jnp.array(10.0), jnp.array(5.0)]
        ranks = [jnp.array(0.0), jnp.array(1.0), jnp.array(2.0)]
        masks = [jnp.array(True), jnp.array(True), jnp.array(True)]
        result = engine.merge_priority_jax(base, values, priorities, ranks, masks)
        np.testing.assert_allclose(result, 20.0, rtol=1e-6)

    @pytest.mark.parametrize("seed", [0, 42, 123, 999])
    def test_jax_merge_is_jit_stable(self, seed):
        import jax

        engine = JAXMergeEngine(DEFAULT_SLOT_REGISTRY, DEFAULT_MERGE_RULE_REGISTRY)
        key = jax.random.PRNGKey(seed)
        base = jax.random.normal(key, shape=(10,))
        deltas = [jax.random.normal(key, shape=(10,)) for _ in range(3)]
        masks = [jnp.ones(10, dtype=bool) for _ in range(3)]

        result_eager = engine.merge_sum_jax(base, deltas, masks)
        merge_jit = jax.jit(engine.merge_sum_jax)
        result_jit = merge_jit(base, deltas, masks)
        np.testing.assert_allclose(result_eager, result_jit, rtol=1e-10)
