from __future__ import annotations

from unittest.mock import MagicMock, patch

import jax.numpy as jnp
import numpy as np
import pytest

from polisyos.foundry.calibration.calibrator import (
    CalibratorInputs,
    CalibrationMetricsCollector,
    TrainableGroup,
    _match_trainable,
    _selector_key,
)


class TestCalibratorInputs:
    def test_calibrator_inputs_fields(self) -> None:
        inputs = CalibratorInputs(
            config=MagicMock(),
            program_graph=MagicMock(),
            exec_plan=MagicMock(),
            base_state=MagicMock(),
            mechanism_registry=MagicMock(),
            slot_registry=MagicMock(),
            merge_registry=MagicMock(),
            selector_field_registry=None,
            parameter_loader=lambda x: {},
        )
        assert inputs.constraint_registry is None
        assert inputs.constraint_values is None
        assert inputs.controls_seq is None
        assert inputs.measurement_bundle is None
        assert inputs.measurement_loss_config is None
        assert inputs.measurement_loss_adapter is None


class TestCalibrationMetricsCollector:
    def test_record_step_accumulates(self) -> None:
        collector = CalibrationMetricsCollector(
            optimizer_name="adam", emit_interval=100, enabled=False,
        )
        collector.record_step(0, 0.01, 1.0, 0.5, is_warmup=True)
        assert collector._current_step == 0

    def test_finalize_calls_flush(self) -> None:
        collector = CalibrationMetricsCollector(
            optimizer_name="adam", emit_interval=100, enabled=False,
        )
        collector.record_step(0, 0.01, 1.0, 0.5, is_warmup=False)
        collector.finalize("converged", total_steps=1)


class TestTrainableGroup:
    def test_trainable_group_fields(self) -> None:
        group = TrainableGroup(
            group_id="g1",
            handle_indices=[0, 1],
            lower=0.0,
            upper=1.0,
            prior_mean=0.5,
            prior_std=0.1,
        )
        assert group.group_id == "g1"
        assert group.lower == 0.0
        assert group.upper == 1.0


class TestSelectorKey:
    def test_selector_key_none(self) -> None:
        assert _selector_key(None) == ""

    def test_selector_key_string(self) -> None:
        assert _selector_key("foo") == "foo"

    def test_selector_key_dict(self) -> None:
        result = _selector_key({"a": 1, "b": 2})
        assert '"a"' in result


class TestMatchTrainable:
    def test_match_trainable_basic(self) -> None:
        handle = MagicMock()
        handle.field_name = "rate"
        handle.node_id = "n1"
        handle.mechanism_type = "flat_tax"

        ref = MagicMock()
        ref.param_id = "rate"
        ref.node_id = "n1"
        ref.mechanism_type = None
        ref.selector = None

        assert _match_trainable(handle, ref) is True

    def test_match_trainable_mismatch_param_id(self) -> None:
        handle = MagicMock()
        handle.field_name = "rate"
        handle.node_id = "n1"

        ref = MagicMock()
        ref.param_id = "other"
        ref.node_id = "n1"
        ref.mechanism_type = None
        ref.selector = None

        assert _match_trainable(handle, ref) is False
