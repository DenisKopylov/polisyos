from __future__ import annotations

import numpy as np
import pytest

from polisyos.foundry.methods.base import SideEffectProfile, SlotType
from polisyos.foundry.methods.catalog.policy.accounting import PeriodFlowToStock
from polisyos.foundry.methods.types.units import Units


@pytest.mark.parametrize("period_total", [-6_000_000_000.0, 0.0])
def test_period_flow_to_stock_emits_one_period_total_without_scaling(
    period_total: float,
) -> None:
    target_slot = "fixture.accumulated_balance"
    selected = np.asarray(period_total, dtype=np.float64)

    result = PeriodFlowToStock.pure_step(
        {"period_flow": selected},
        {"target_slot": target_slot},
    )

    assert result["result"] == period_total
    assert result["patch_records"] == {target_slot: [{"delta": period_total}]}
    assert type(result["result"]) is float


def test_period_flow_to_stock_abi_declares_usd_scalar_and_static_target_only() -> None:
    signature = PeriodFlowToStock.signature

    assert signature.fqn == "policy.accounting.period_flow_to_stock@1.0.0"
    assert signature.input_slot_names == {"period_flow"}
    assert signature.output_slot_names == {"result"}
    assert signature.get_input_slot("period_flow") is not None
    assert signature.get_input_slot("period_flow").slot_type is SlotType.SCALAR
    assert signature.get_input_slot("period_flow").unit == Units.USD
    assert signature.get_output_slot("result") is not None
    assert signature.get_output_slot("result").slot_type is SlotType.SCALAR
    assert signature.get_output_slot("result").unit == Units.USD
    assert {parameter.name for parameter in signature.parameters} == {"target_slot"}
    assert signature.parameters[0].is_static is True
    assert len(signature.patch_targets) == 1
    assert signature.patch_targets[0].target_parameter == "target_slot"
    assert signature.patch_targets[0].source_input == "period_flow"
    assert signature.patch_targets[0].operation == "add"
    assert signature.patch_targets[0].target_kind == "stock"
    assert signature.patch_targets[0].target_scope == "global"
    assert signature.patch_targets[0].merge_rule_kind == "sum"
    assert PeriodFlowToStock.metadata.side_effect_profile is SideEffectProfile.PATCH_EMISSION
    assert PeriodFlowToStock.metadata.assumptions["empirical_status"] == "not_established"


@pytest.mark.parametrize("params", [{}, {"target_slot": None}, {"target_slot": " "}])
def test_period_flow_to_stock_refuses_missing_or_invalid_target(params: dict[str, object]) -> None:
    with pytest.raises(ValueError, match="period_flow_target_slot_required"):
        PeriodFlowToStock.pure_step(
            {"period_flow": np.asarray(0.0, dtype=np.float64)},
            params,
        )


@pytest.mark.parametrize(
    ("value", "error_code"),
    [
        (1.0, "period_flow_requires_numpy_float64_scalar"),
        (np.asarray(1.0, dtype=np.float32), "period_flow_requires_numpy_float64_scalar"),
        (np.asarray([1.0], dtype=np.float64), "period_flow_requires_numpy_float64_scalar"),
        (np.asarray(np.nan, dtype=np.float64), "period_flow_requires_finite_value"),
        (np.asarray(np.inf, dtype=np.float64), "period_flow_requires_finite_value"),
    ],
)
def test_period_flow_to_stock_refuses_wrong_shape_dtype_or_nonfinite_value(
    value: object,
    error_code: str,
) -> None:
    with pytest.raises(ValueError, match=error_code):
        PeriodFlowToStock.pure_step(
            {"period_flow": value},
            {"target_slot": "fixture.accumulated_balance"},
        )


@pytest.mark.parametrize(
    "state",
    [
        {},
        {"period_flow": np.asarray(0.0, dtype=np.float64), "gdp": np.asarray(200.0)},
    ],
)
def test_period_flow_to_stock_refuses_missing_or_ambient_input_keys(
    state: dict[str, object],
) -> None:
    with pytest.raises(ValueError, match="period_flow_method_input_mapping_invalid"):
        PeriodFlowToStock.pure_step(state, {"target_slot": "fixture.accumulated_balance"})
