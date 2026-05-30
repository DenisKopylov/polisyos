from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from polisyos.ir.kernel.merge_rules import MergeRuleKind, MergeRuleRegistry, MergeRuleSpec
from polisyos.ir.kernel.slots import SlotKind, SlotRegistry, SlotScope, SlotSpec, SlotValueType
from polisyos.ir.kernel.time_semantics import TimeSemantics
from polisyos.ir.kernel.units import MoneyUnit, UnitRef, UnitsRegistry
from polisyos.ir.kernel.values import MoneyValue, RateValue
from polisyos.ir.model_layer.types import TimeFrequency


def test_units_registry_rejects_invalid_id() -> None:
    with pytest.raises(ValidationError):
        UnitsRegistry(units={"BadId": MoneyUnit(currency="USD")})


def test_merge_rule_registry_requires_matching_ids() -> None:
    with pytest.raises(ValidationError):
        MergeRuleRegistry(rules={"sum": MergeRuleSpec(rule_id="override", kind=MergeRuleKind.SUM)})


def test_slot_registry_requires_matching_ids() -> None:
    with pytest.raises(ValidationError):
        SlotRegistry(
            slots={
                "gov.balance": SlotSpec(
                    slot_id="gov.other",
                    scope=SlotScope.GLOBAL,
                    value_type=SlotValueType.DECIMAL,
                    unit=UnitRef(unit_id="usd"),
                    kind=SlotKind.STOCK,
                    merge_rule={"rule_id": "sum"},
                )
            }
        )


def test_money_value_rejects_float_amount() -> None:
    with pytest.raises(ValidationError):
        MoneyValue(amount=1.25, currency="USD")


def test_rate_value_range_enforced() -> None:
    with pytest.raises(ValidationError):
        RateValue(value=Decimal("1.5"), base="ratio")
    with pytest.raises(ValidationError):
        RateValue(value=Decimal("120"), base="percent")


def test_time_semantics_requires_extent() -> None:
    with pytest.raises(ValidationError):
        TimeSemantics(frequency=TimeFrequency.MONTH, start_date="2024-01-01")

    ts = TimeSemantics(
        frequency=TimeFrequency.MONTH,
        start_date="2024-01-01",
        step_count=12,
    )
    assert ts.date_for_step(1).isoformat() == "2024-02-01"
