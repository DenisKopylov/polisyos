"""Built-in binding profiles for common timeseries data schemas."""

from .models import BindingProfile, BindingRuleSpec, BindingTransformSpec

BUILTIN_BINDING_PROFILES: list[BindingProfile] = [
    # -----------------------------------------------------------------------
    # 1. Single-indicator timeseries (e.g., GDP, population)
    # -----------------------------------------------------------------------
    BindingProfile(
        profile_id="ts_single_indicator",
        display_name="Single-Indicator Timeseries",
        description=(
            "Maps a timeseries with time + value columns to macro.* slots. "
            "Suitable for World Bank WDI, Eurostat single-indicator queries."
        ),
        schema_family="timeseries",
        strategy="auto",
        rules=[
            BindingRuleSpec(
                binding_id="ts.time_period",
                source_path="TIME_PERIOD",
                target_slot_id="macro.time_index",
                required=True,
            ),
            BindingRuleSpec(
                binding_id="ts.value",
                source_path="value",
                target_slot_id="macro.observed_value",
                required=True,
                transforms=[
                    BindingTransformSpec(op="to_decimal"),
                ],
            ),
        ],
        expected_columns=["TIME_PERIOD", "value"],
        tags=["timeseries", "macro", "single_indicator"],
    ),
    # -----------------------------------------------------------------------
    # 2. Multi-indicator timeseries (panel data with geo + frequency dims)
    # -----------------------------------------------------------------------
    BindingProfile(
        profile_id="ts_multi_indicator",
        display_name="Multi-Indicator Timeseries",
        description=(
            "Maps timeseries with dimension columns (freq, geo, indicator) "
            "to macro slots. Suitable for SDMX multi-dimensional queries."
        ),
        schema_family="timeseries",
        strategy="auto",
        rules=[
            BindingRuleSpec(
                binding_id="ts_multi.time_period",
                source_path="TIME_PERIOD",
                target_slot_id="macro.time_index",
                required=True,
            ),
            BindingRuleSpec(
                binding_id="ts_multi.value",
                source_path="value",
                target_slot_id="macro.observed_value",
                required=True,
                transforms=[BindingTransformSpec(op="to_decimal")],
            ),
            BindingRuleSpec(
                binding_id="ts_multi.geo",
                source_path="REF_AREA",
                target_slot_id="macro.geo_id",
                required=False,
            ),
            BindingRuleSpec(
                binding_id="ts_multi.freq",
                source_path="FREQ",
                target_slot_id="macro.frequency",
                required=False,
            ),
        ],
        expected_columns=["TIME_PERIOD", "value", "REF_AREA", "FREQ"],
        tags=["timeseries", "macro", "multi_indicator", "panel"],
    ),
    # -----------------------------------------------------------------------
    # 3. Exchange rate timeseries (SDMX EXR)
    # -----------------------------------------------------------------------
    BindingProfile(
        profile_id="ts_exchange_rate",
        display_name="Exchange Rate Timeseries",
        description=(
            "Maps SDMX exchange rate data (EXR) to monetary.* slots "
            "with decimal rounding transforms."
        ),
        schema_family="timeseries",
        strategy="manual",
        rules=[
            BindingRuleSpec(
                binding_id="exr.time_period",
                source_path="TIME_PERIOD",
                target_slot_id="monetary.time_index",
                required=True,
            ),
            BindingRuleSpec(
                binding_id="exr.value",
                source_path="value",
                target_slot_id="monetary.exchange_rate",
                required=True,
                transforms=[
                    BindingTransformSpec(op="to_decimal"),
                    BindingTransformSpec(op="round", params={"digits": 6}),
                ],
            ),
            BindingRuleSpec(
                binding_id="exr.currency",
                source_path="CURRENCY",
                target_slot_id="monetary.currency_code",
                required=True,
            ),
            BindingRuleSpec(
                binding_id="exr.currency_denom",
                source_path="CURRENCY_DENOM",
                target_slot_id="monetary.currency_denom",
                required=False,
                default_value="EUR",
            ),
        ],
        expected_columns=["TIME_PERIOD", "value", "CURRENCY", "CURRENCY_DENOM"],
        tags=["timeseries", "monetary", "exchange_rate", "sdmx"],
    ),
]
