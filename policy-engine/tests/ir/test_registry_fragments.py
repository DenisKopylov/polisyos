from __future__ import annotations

from polisyos.ir.kernel.units import MoneyUnit, UnitsRegistry
from polisyos.ir.registry_fragments import (
    ComposePolicy,
    RegistryComposeRequest,
    RegistryFragmentMeta,
    UnitsFragment,
    compose_registry_fragments,
)


def _units_fragment(
    fragment_id: str,
    currency: str,
    *,
    priority: int = 0,
    depends_on: list[str] | None = None,
) -> UnitsFragment:
    meta = RegistryFragmentMeta(
        fragment_id=fragment_id,
        namespace="roads",
        priority=priority,
        depends_on=list(depends_on or []),
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


def test_missing_dependency_fragment_is_not_applied_or_merged() -> None:
    frag_valid = _units_fragment("frag_valid", "USD", priority=0)
    frag_invalid = _units_fragment(
        "frag_invalid",
        "EUR",
        priority=50,
        depends_on=["frag_missing"],
    )

    result = compose_registry_fragments(
        RegistryComposeRequest(
            fragments=[frag_invalid, frag_valid],
            policy=ComposePolicy(mode="prefer_higher_priority"),
        )
    )

    assert result.composed is not None
    assert result.composed.units is not None
    assert result.composed.units.units["usd"].currency == "USD"
    assert result.applied_fragments == ["frag_valid"]
    assert any(
        conflict.conflict_kind == "dependency_missing" and conflict.item_key == "frag_invalid"
        for conflict in result.conflicts
    )


def test_dependency_cycle_detected_and_excluded_from_apply_order() -> None:
    frag_a = _units_fragment("frag_a", "USD", depends_on=["frag_b"])
    frag_b = _units_fragment("frag_b", "USD", depends_on=["frag_a"])
    frag_c = _units_fragment("frag_c", "CAD")

    result = compose_registry_fragments(
        RegistryComposeRequest(
            fragments=[frag_b, frag_c, frag_a],
            policy=ComposePolicy(mode="prefer_higher_priority"),
        )
    )

    assert result.composed is not None
    assert result.composed.units is not None
    assert result.composed.units.units["usd"].currency == "CAD"
    assert result.applied_fragments == ["frag_c"]
    assert sorted(
        conflict.item_key
        for conflict in result.conflicts
        if conflict.conflict_kind == "dependency_cycle"
    ) == ["frag_a", "frag_b"]


def test_topological_order_is_deterministic_across_input_orders() -> None:
    frag_a = _units_fragment("frag_a", "USD", priority=1)
    frag_b = _units_fragment("frag_b", "CAD", priority=100, depends_on=["frag_a"])
    frag_c = _units_fragment("frag_c", "EUR", priority=50)

    request_a = RegistryComposeRequest(
        fragments=[frag_b, frag_c, frag_a],
        policy=ComposePolicy(mode="prefer_higher_priority"),
    )
    request_b = RegistryComposeRequest(
        fragments=[frag_c, frag_a, frag_b],
        policy=ComposePolicy(mode="prefer_higher_priority"),
    )

    result_a = compose_registry_fragments(request_a)
    result_b = compose_registry_fragments(request_b)

    assert result_a.applied_fragments == result_b.applied_fragments
    assert result_a.deterministic_hash == result_b.deterministic_hash
