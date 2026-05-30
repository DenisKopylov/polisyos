from __future__ import annotations

from datetime import UTC, datetime

import pytest

pytest.importorskip("pytest_benchmark", reason="pytest-benchmark not installed")

from polisyos.ir.connectors import FetchRequest, QualityTier
from polisyos.ir.kernel.units import MoneyUnit, UnitsRegistry
from polisyos.ir.registry.registry_fragments import (
    ComposePolicy,
    RegistryComposeRequest,
    RegistryFragmentMeta,
    UnitsFragment,
    compose_registry_fragments,
)

pytestmark = [pytest.mark.benchmark, pytest.mark.performance]


def _units_fragment(fragment_id: str, currency: str, priority: int) -> UnitsFragment:
    return UnitsFragment(
        meta=RegistryFragmentMeta(
            fragment_id=fragment_id,
            namespace="phase3.benchmark",
            priority=priority,
        ),
        payload=UnitsRegistry(units={"usd": MoneyUnit(currency=currency)}),
    )


def test_registry_fragment_composition_is_bounded(benchmark) -> None:
    request = RegistryComposeRequest(
        fragments=[
            _units_fragment(
                fragment_id=f"frag_{idx}",
                currency=["USD", "EUR", "CAD", "GBP"][idx % 4],
                priority=idx % 7,
            )
            for idx in range(64)
        ],
        policy=ComposePolicy(mode="prefer_higher_priority"),
    )

    result = benchmark(compose_registry_fragments, request)

    assert result.composed is not None
    assert benchmark.stats.get("mean", 0.0) * 1e3 < 50.0


def test_fetch_request_cached_keys_are_bounded(benchmark) -> None:
    request = FetchRequest(
        dataset_id="phase3.dataset",
        date_start=datetime(2025, 1, 1, tzinfo=UTC),
        filters=(("country", ("USA", "DEU", "FRA")),),
        include_metadata=True,
        include_schema=False,
        page_size=100,
        min_quality_tier=QualityTier.SILVER,
    )

    value = benchmark(lambda: (request.query_key, request.request_key, request.cache_key))

    assert value[0].startswith("sha256:")
    assert value[1].startswith("sha256:")
    assert benchmark.stats.get("mean", 0.0) * 1e3 < 1.0
