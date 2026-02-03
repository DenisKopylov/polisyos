from __future__ import annotations

import pytest

from polisyos.ir.registry_fragments import (
    ComposePolicy,
    RegistryComposeRequest,
    RegistryFragmentMeta,
    UnitsFragment,
    compose_registry_fragments,
)
from polisyos.ir.kernel.units import MoneyUnit, UnitsRegistry


def _units_fragment(fragment_id: str, currency: str, *, priority: int = 0) -> UnitsFragment:
    meta = RegistryFragmentMeta(
        fragment_id=fragment_id,
        namespace="roads",
        priority=priority,
    )
    registry = UnitsRegistry(units={"usd": MoneyUnit(currency=currency)})
    return UnitsFragment(meta=meta, payload=registry)


def test_conflict_detected_error_mode() -> None:
    frag_a = _units_fragment("frag_a", "USD")
    frag_b = _units_fragment("frag_b", "EUR")

    request = RegistryComposeRequest(
        fragments=[frag_a, frag_b],
        policy=ComposePolicy(mode="error_on_conflict"),
    )
    result = compose_registry_fragments(request)

    assert result.composed is None
    assert any(c.conflict_kind == "duplicate_different" for c in result.conflicts)


def test_prefer_higher_priority() -> None:
    frag_a = _units_fragment("frag_a", "USD", priority=10)
    frag_b = _units_fragment("frag_b", "EUR", priority=0)

    request = RegistryComposeRequest(
        fragments=[frag_b, frag_a],
        policy=ComposePolicy(mode="prefer_higher_priority"),
    )
    result = compose_registry_fragments(request)

    assert result.composed is not None
    assert result.composed.units is not None
    assert result.composed.units.units["usd"].currency == "USD"


def test_duplicate_identical_is_non_blocking() -> None:
    frag_a = _units_fragment("frag_a", "USD")
    frag_b = _units_fragment("frag_b", "USD")

    request = RegistryComposeRequest(
        fragments=[frag_a, frag_b],
        policy=ComposePolicy(mode="error_on_conflict"),
    )
    result = compose_registry_fragments(request)

    assert result.composed is not None
    assert any(c.conflict_kind == "duplicate_identical" for c in result.conflicts)


def test_reserved_prefix_conflict() -> None:
    meta = RegistryFragmentMeta(
        fragment_id="frag_reserved",
        namespace="roads",
    )
    registry = UnitsRegistry(units={"core.usd": MoneyUnit(currency="USD")})
    frag = UnitsFragment(meta=meta, payload=registry)

    request = RegistryComposeRequest(fragments=[frag])
    result = compose_registry_fragments(request)

    assert result.composed is None
    assert any(c.conflict_kind == "reserved_prefix" for c in result.conflicts)
