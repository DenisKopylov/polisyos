"""Explicit test inputs for a two-year constant-price method-input bridge.

This supplies fixture declarations and independent expected values only. Real
native occurrences, certificates, NPY values and execution must still come
from their canonical producers; these declarations establish no empirical
truth, source currentness or execution permission.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from polisyos.core.contracts import ModelInputScope
from polisyos.ir.kernel import MoneyUnit
from polisyos.ir.kernel.time_semantics import TimeSemantics
from polisyos.ir.model_layer import TimeFrequency


@dataclass(frozen=True)
class TemporalMethodYearInput:
    """One declared fixture year and its independently specified expected flow."""

    step: int
    year: int
    ratio: Decimal
    denominator: Decimal
    expected_flow: Decimal


@dataclass(frozen=True)
class TemporalSelectedMethodInputSpec:
    """One fixed-basis model clock, scope envelope and source-input sequence."""

    money_unit: MoneyUnit
    time_semantics: TimeSemantics
    scope: ModelInputScope
    rows: tuple[TemporalMethodYearInput, ...]
    opening_stock: Decimal
    expected_closing_stock: Decimal


def constant_price_two_year_method_spec() -> TemporalSelectedMethodInputSpec:
    """Return declared 2020/2021 inputs in constant 2020 USD.

    The same explicit valuation coordinates apply to both years. The literal
    expected values are mathematical test oracles, not produced observations
    or a reimplementation of the derivation engine.
    """
    return TemporalSelectedMethodInputSpec(
        money_unit=MoneyUnit(currency="USD", nominal_year=2020, price_base="constant"),
        time_semantics=TimeSemantics(
            frequency=TimeFrequency.YEAR, start_date="2020-01-01", step_count=2
        ),
        scope=ModelInputScope(
            population_ref="population:government",
            geography_ref="UA",
            jurisdiction_ref="jurisdiction:fixture",
            period_start=date(2020, 1, 1),
            period_end=date(2021, 12, 31),
            time_role="observation_time",
            period_basis="calendar_year",
        ),
        rows=(
            TemporalMethodYearInput(
                step=0,
                year=2020,
                ratio=Decimal("-0.03"),
                denominator=Decimal("200000000000"),
                expected_flow=Decimal("-6000000000"),
            ),
            TemporalMethodYearInput(
                step=1,
                year=2021,
                ratio=Decimal("0.02"),
                denominator=Decimal("210000000000"),
                expected_flow=Decimal("4200000000"),
            ),
        ),
        opening_stock=Decimal("10000000000"),
        expected_closing_stock=Decimal("8200000000"),
    )
