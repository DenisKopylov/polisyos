"""Real input binding reaches existing aggregate state fields."""

from __future__ import annotations

from pathlib import Path

import pytest

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.contracts.foundry import FoundryInputBindingRule
from polisyos.core.registry import build_default_registry_bundle, load_registry_bundle_content
from polisyos.foundry.data_plane import prepare_json_input_binding_values


def test_nominal_gdp_and_labor_rate_bind_distinct_real_state_slots(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    registry_ref = build_default_registry_bundle(store).bundle_ref
    registry = load_registry_bundle_content(store, registry_ref).slot_registry
    assert registry.slots["global.gdp"].state_path == "gdp"
    assert registry.slots["global.gdp"].unit.unit_id == "usd"
    assert registry.slots["global.unemployment_rate"].state_path == "market.unemployment_rate"
    assert registry.slots["global.unemployment_rate"].unit.unit_id == "ratio"
    rules = [
        FoundryInputBindingRule(
            binding_id="source.nominal_gdp",
            source_path="source.gdp_usd",
            target_slot_id="global.gdp",
            required=True,
        ),
        FoundryInputBindingRule(
            binding_id="source.unemployment",
            source_path="source.unemployment_ratio",
            target_slot_id="global.unemployment_rate",
            required=True,
        ),
    ]
    payload = b'{"source":{"gdp_usd":80.0,"unemployment_ratio":0.175}}'
    result = prepare_json_input_binding_values(
        store, payload_json=payload, registry_bundle_ref=registry_ref, rules=rules
    )
    state = result.materialized_state
    assert float(state.gdp) == pytest.approx(80.0)
    assert float(state.market.unemployment_rate) == pytest.approx(0.175)
    assert float(state.government_balance) == 0.0
    assert float(state.tax_rate) == 0.0
    assert set(result.applied_binding_ids) == {"source.nominal_gdp", "source.unemployment"}

    with pytest.raises(ValueError, match="unknown slot_id"):
        prepare_json_input_binding_values(
            store,
            payload_json=payload,
            registry_bundle_ref=registry_ref,
            rules=[rules[0].model_copy(update={"target_slot_id": "global.unknown"})],
        )
