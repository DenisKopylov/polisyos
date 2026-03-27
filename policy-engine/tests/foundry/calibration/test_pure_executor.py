from __future__ import annotations

from unittest.mock import MagicMock

import jax.numpy as jnp
import pytest

from polisyos.foundry.calibration.pure_executor import (
    PreparedNode,
    StaticBundle,
    TrainableHandle,
    apply_trainable_values,
    extract_trainable_values,
)


class TestPreparedNode:
    def test_prepared_node_fields(self) -> None:
        node = PreparedNode(
            node_id="n1",
            mechanism_type="flat_tax",
            rank=0,
            start=0,
            end=10,
            mechanism=MagicMock(),
            outputs=["tax"],
        )
        assert node.node_id == "n1"
        assert node.start == 0
        assert node.end == 10
        assert node.selector is None


class TestTrainableHandle:
    def test_trainable_handle_fields(self) -> None:
        handle = TrainableHandle(
            node_index=0,
            node_id="n1",
            mechanism_type="flat_tax",
            field_name="rate",
            lower=0.0,
            upper=1.0,
        )
        assert handle.lower == 0.0
        assert handle.upper == 1.0
        assert handle.prior_mean is None


class TestStaticBundle:
    def test_static_bundle_construction(self) -> None:
        mechanism = MagicMock()
        mechanism.rate = jnp.array(0.2)
        node = PreparedNode(
            node_id="n1",
            mechanism_type="flat_tax",
            rank=0,
            start=0,
            end=10,
            mechanism=mechanism,
            outputs=["tax"],
        )
        handle = TrainableHandle(
            node_index=0,
            node_id="n1",
            mechanism_type="flat_tax",
            field_name="rate",
            lower=0.0,
            upper=1.0,
        )
        bundle = StaticBundle(
            nodes=[node],
            slot_registry=MagicMock(),
            mechanism_registry=MagicMock(),
            merge_registry=MagicMock(),
            selector_field_registry=None,
            trainables=[handle],
        )
        assert len(bundle.nodes) == 1
        assert len(bundle.trainables) == 1


class TestExtractApplyTrainableValues:
    def test_extract_trainable_values(self) -> None:
        mechanism = MagicMock()
        mechanism.rate = jnp.array(0.25)
        node = PreparedNode(
            node_id="n1",
            mechanism_type="flat_tax",
            rank=0,
            start=0,
            end=10,
            mechanism=mechanism,
            outputs=["tax"],
        )
        handle = TrainableHandle(
            node_index=0,
            node_id="n1",
            mechanism_type="flat_tax",
            field_name="rate",
            lower=0.0,
            upper=1.0,
        )
        bundle = StaticBundle(
            nodes=[node],
            slot_registry=MagicMock(),
            mechanism_registry=MagicMock(),
            merge_registry=MagicMock(),
            selector_field_registry=None,
            trainables=[handle],
        )
        values = extract_trainable_values(bundle)
        assert len(values) == 1
        assert float(values[0]) == pytest.approx(0.25)

    def test_apply_trainable_values_updates(self) -> None:
        import equinox as eqx

        class SimpleMechanism(eqx.Module):
            rate: jnp.ndarray

        mechanism = SimpleMechanism(rate=jnp.array(0.25))

        node = PreparedNode(
            node_id="n1",
            mechanism_type="flat_tax",
            rank=0,
            start=0,
            end=10,
            mechanism=mechanism,
            outputs=["tax"],
        )
        handle = TrainableHandle(
            node_index=0,
            node_id="n1",
            mechanism_type="flat_tax",
            field_name="rate",
            lower=0.0,
            upper=1.0,
        )
        bundle = StaticBundle(
            nodes=[node],
            slot_registry=MagicMock(),
            mechanism_registry=MagicMock(),
            merge_registry=MagicMock(),
            selector_field_registry=None,
            trainables=[handle],
        )
        new_values = [jnp.array(0.5)]
        new_bundle = apply_trainable_values(bundle, new_values)
        assert new_bundle is not None
        assert len(new_bundle.nodes) == 1
        assert float(new_bundle.nodes[0].mechanism.rate) == pytest.approx(0.5)
