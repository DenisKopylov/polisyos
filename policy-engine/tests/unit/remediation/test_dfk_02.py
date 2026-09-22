from __future__ import annotations

from collections.abc import Callable

import pytest

from polisyos.data_forge.domains.catalog.registry import (
    CatalogSourceRegistryEntry,
    CatalogSourceRegistrySpec,
    catalog_source_modules_from_registry,
    load_catalog_source_registry,
)
from polisyos.data_forge.domains.catalog.source_modules import (
    CORE_CATALOG_SOURCE_MODULES,
    CatalogSourceModuleSpec,
    select_catalog_source_modules,
)
from polisyos.data_forge.read_api import catalog as catalog_read_api
from polisyos.fabric.retrieval.service import RetrievalService


def _module(
    source_id: str,
    *,
    enabled: bool = True,
    seed_from: str | None = None,
) -> CatalogSourceModuleSpec:
    return CatalogSourceModuleSpec(
        source_id=source_id,
        family="fixture",
        wave="A",
        connector_id="fixture.connector",
        profile_id="fixture",
        endpoint="https://example.invalid/catalog",
        enabled=enabled,
        execution_tier="fetchable",
        run_lane="empirical",
        publish_blocking=False,
        update_frequency="daily",
        metrics_required=True,
        seed_from=seed_from,
    )


def _assert_typed_dependency_failure(
    operation: Callable[[], object],
    *,
    expected_code: str,
) -> None:
    """Assert the source-selection owner reports a typed fail-closed reason."""
    with pytest.raises(catalog_read_api.CatalogSelectionError) as caught:
        operation()

    assert caught.value.code == expected_code


def _registry_entry(
    source_id: str,
    *,
    enabled: bool = True,
    seed_from: str | None = None,
) -> CatalogSourceRegistryEntry:
    return CatalogSourceRegistryEntry(
        source_id=source_id,
        family="fixture",
        wave="A",
        endpoint="https://example.invalid/catalog",
        connector_id="fixture.connector",
        enabled=enabled,
        seed_from=seed_from,
    )


def test_source_selection_distinguishes_none_default_from_explicit_empty() -> None:
    registry = load_catalog_source_registry()
    default_selection = select_catalog_source_modules(None, run_profile="prod_full")
    default_ids = tuple(item.source_id for item in default_selection)
    expected_default_ids = tuple(
        item.source_id for item in registry.enabled_sources(run_profile="prod_full")
    )

    assert default_ids == expected_default_ids
    assert {
        item.source_id for item in registry.sources if not item.enabled
    }.isdisjoint(default_ids)
    assert select_catalog_source_modules((), run_profile="prod_full") == ()


def test_source_selection_fails_closed_for_disabled_mandatory_seed() -> None:
    modules = (
        _module("seed", enabled=False),
        _module("exec", seed_from="seed"),
    )

    _assert_typed_dependency_failure(
        lambda: select_catalog_source_modules(modules, run_profile="prod_full"),
        expected_code="dependency_disabled",
    )


def test_source_selection_fails_closed_for_missing_seed() -> None:
    modules = (_module("exec", seed_from="missing"),)

    _assert_typed_dependency_failure(
        lambda: select_catalog_source_modules(modules, run_profile="prod_full"),
        expected_code="dependency_missing",
    )


def test_source_selection_fails_closed_for_cyclic_seeds() -> None:
    modules = (
        _module("first", seed_from="second"),
        _module("second", seed_from="first"),
    )

    _assert_typed_dependency_failure(
        lambda: select_catalog_source_modules(modules, run_profile="prod_full"),
        expected_code="dependency_cycle",
    )


def test_registry_selection_fails_closed_for_disabled_mandatory_seed() -> None:
    registry = CatalogSourceRegistrySpec(
        version=1,
        sources=(
            _registry_entry("seed", enabled=False),
            _registry_entry("exec", seed_from="seed"),
        ),
    )

    _assert_typed_dependency_failure(
        lambda: registry.enabled_sources(run_profile="prod_full"),
        expected_code="dependency_disabled",
    )


def test_registry_selection_fails_closed_for_missing_seed() -> None:
    registry = CatalogSourceRegistrySpec(
        version=1,
        sources=(_registry_entry("exec", seed_from="missing"),),
    )

    _assert_typed_dependency_failure(
        lambda: registry.enabled_sources(run_profile="prod_full"),
        expected_code="dependency_missing",
    )


def test_registry_selection_fails_closed_for_cyclic_seeds() -> None:
    registry = CatalogSourceRegistrySpec(
        version=1,
        sources=(
            _registry_entry("first", seed_from="second"),
            _registry_entry("second", seed_from="first"),
        ),
    )

    _assert_typed_dependency_failure(
        lambda: registry.enabled_sources(run_profile="prod_full"),
        expected_code="dependency_cycle",
    )


def test_registry_projection_preserves_rich_source_filters() -> None:
    registry = load_catalog_source_registry()
    projection = {
        item.source_id: item for item in catalog_source_modules_from_registry(registry)
    }

    ukraine_exec = projection["data_gov_ua_exec"].model_dump()
    assert ukraine_exec["format_allowlist"] == (
        "CSV",
        "JSON",
        "XLSX",
        "XLS",
        "ODS",
        "ZIP",
    )
    assert ukraine_exec["format_denylist"] == ("PDF", "DOC", "DOCX", "XML")
    assert ukraine_exec["keyword_allowlist"][:3] == ("demograph", "population", "birth")
    assert ukraine_exec["keyword_denylist"][-3:] == (
        "постанова",
        "скан",
        "листування",
    )
    assert ukraine_exec["require_curated_resources"] is True

    undata = projection["undata"].model_dump()
    assert undata["agency_allowlist"] == ("UNSD", "IAEG", "IAEG-SDGs", "UIS")
    assert undata["exclude_agencies"] == ("ESTAT", "WB")


def test_registry_projection_keeps_the_35_entry_order_and_equality_contract() -> None:
    registry = load_catalog_source_registry()
    modules = catalog_source_modules_from_registry(registry)

    assert len(registry.sources) == 35
    assert tuple(entry.source_id for entry in registry.sources) == tuple(
        item.source_id for item in CORE_CATALOG_SOURCE_MODULES
    )
    assert modules == CORE_CATALOG_SOURCE_MODULES


def test_public_read_and_fabric_consumers_use_the_canonical_registry_projection(tmp_path) -> None:
    direct_registry = load_catalog_source_registry()
    public_registry = catalog_read_api.load_catalog_source_registry()
    assert public_registry == direct_registry

    curated_dir = tmp_path / "curated"
    curated_dir.mkdir()
    service = RetrievalService(curated_dir=curated_dir)
    policy = service._source_policy("data_gov_ua_exec")

    assert policy is not None
    assert policy.source_id == "data_gov_ua_exec"
    assert policy.format_allowlist == (
        "CSV",
        "JSON",
        "XLSX",
        "XLS",
        "ODS",
        "ZIP",
    )
    assert policy.keyword_allowlist[:3] == ("demograph", "population", "birth")
