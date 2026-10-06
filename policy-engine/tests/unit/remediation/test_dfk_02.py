from __future__ import annotations

from collections.abc import Callable

import pytest

from polisyos.data_forge.domains.catalog import sources as source_views
from polisyos.data_forge.domains.catalog.batch.source_registry import load_source_registry
from polisyos.data_forge.domains.catalog.knowledge.derivation_catalog_selection import (
    CatalogSelectionError,
)
from polisyos.data_forge.domains.catalog.registry import (
    CatalogSourceRegistryEntry,
    CatalogSourceRegistrySpec,
    catalog_source_modules_from_registry,
    default_catalog_source_registry_path,
    load_catalog_source_registry,
)
from polisyos.data_forge.domains.catalog.selection import (
    resolve_catalog_source_dependencies,
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
    assert {item.source_id for item in registry.sources if not item.enabled}.isdisjoint(default_ids)
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


def test_source_selection_rejects_duplicate_module_identities() -> None:
    module = _module("source")

    with pytest.raises(CatalogSelectionError, match="duplicate_source_identity"):
        select_catalog_source_modules((module, module))


def test_dependency_resolution_uses_registered_row_for_selected_identity() -> None:
    registered = _module("dependent", seed_from="missing")
    selected_copy = _module("dependent")

    _assert_typed_dependency_failure(
        lambda: resolve_catalog_source_dependencies((registered,), (selected_copy,)),
        expected_code="dependency_missing",
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


def test_source_registry_and_module_selection_share_profile_and_wave_policy() -> None:
    registry = load_catalog_source_registry()
    modules = catalog_source_modules_from_registry(registry)
    batch_registry = load_source_registry(default_catalog_source_registry_path())

    for profile in (
        "prod_full",
        "prod_core_blocking",
        "rest_backfill",
        "catalog_refresh",
        "preflight_core",
        "observations_backfill",
    ):
        expected = tuple(
            source.source_id for source in registry.enabled_sources(wave="C", run_profile=profile)
        )

        assert (
            tuple(
                source.source_id
                for source in select_catalog_source_modules(
                    modules,
                    wave="C",
                    run_profile=profile,
                )
            )
            == expected
        )
        assert (
            tuple(
                source.name
                for source in batch_registry.enabled_sources(wave="C", run_profile=profile)
            )
            == expected
        )


def test_canonical_selectors_hold_unknown_profiles_even_for_empty_inputs() -> None:
    registry = CatalogSourceRegistrySpec(version=1, sources=())

    _assert_typed_dependency_failure(
        lambda: registry.enabled_sources(run_profile="future_profile"),
        expected_code="unsupported_run_profile",
    )
    _assert_typed_dependency_failure(
        lambda: select_catalog_source_modules((), run_profile="future_profile"),
        expected_code="unsupported_run_profile",
    )


def test_registry_projection_preserves_rich_source_filters() -> None:
    registry = load_catalog_source_registry()
    projection = {item.source_id: item for item in catalog_source_modules_from_registry(registry)}

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
    source_exports = {
        module.source_id: module
        for module in vars(source_views).values()
        if isinstance(module, CatalogSourceModuleSpec)
    }

    assert len(registry.sources) == 35
    assert sum(source.enabled for source in registry.sources) == 32
    assert sum(not source.enabled for source in registry.sources) == 3
    assert sum(source.seed_from is not None for source in registry.sources) == 7
    assert tuple(entry.source_id for entry in registry.sources) == tuple(
        item.source_id for item in CORE_CATALOG_SOURCE_MODULES
    )
    assert modules == CORE_CATALOG_SOURCE_MODULES
    assert tuple(item.source_id for item in source_views.ALL_CATALOG_SOURCE_MODULES) == tuple(
        entry.source_id for entry in registry.sources
    )
    assert source_exports == {module.source_id: module for module in modules}


def test_custom_yaml_registry_drives_projection_and_seed_selection(tmp_path) -> None:
    registry_path = tmp_path / "custom-source-registry.yaml"
    registry_path.write_text(
        """version: 1
sources:
  - name: base
    family: fixture
    wave: B
    endpoint: https://example.invalid/base
    connector_id: fixture.catalog
    execution_tier: catalog
    run_lane: catalog
    publish_blocking: false
    enabled: true
  - name: dependent
    family: fixture
    wave: C
    endpoint: https://example.invalid/dependent
    connector_id: fixture.fetch
    execution_tier: fetchable
    run_lane: empirical
    publish_blocking: true
    history_policy: rolling_window
    seed_from: base
    format_allowlist: [CSV]
    default_lookback_days: 14
    enabled: true
  - name: unrelated
    family: fixture
    wave: C
    endpoint: https://example.invalid/unrelated
    connector_id: fixture.fetch
    execution_tier: fetchable
    run_lane: empirical
    publish_blocking: false
    enabled: true
""",
        encoding="utf-8",
    )

    registry = load_catalog_source_registry(registry_path)
    modules = catalog_source_modules_from_registry(registry)
    dependent = modules[1]

    assert dependent.format_allowlist == ("CSV",)
    assert dependent.default_lookback_days == 14
    unrelated = registry.source_by_id("unrelated")
    assert unrelated is not None
    assert not unrelated.included_in_run_profile("prod_core_blocking")
    assert tuple(
        module.source_id
        for module in registry.enabled_sources(
            wave="C",
            run_profile="prod_core_blocking",
        )
    ) == ("base", "dependent")
    assert tuple(
        module.source_id
        for module in select_catalog_source_modules(
            modules,
            wave="C",
            run_profile="prod_core_blocking",
        )
    ) == ("base", "dependent")


@pytest.mark.parametrize(
    ("row", "error_fragment"),
    [
        ("family: fixture\n", "Field required"),
        ("not-a-mapping\n", "mapping"),
        (
            'name: ""\n    family: fixture\n    wave: A\n'
            "    endpoint: https://example.invalid\n    connector_id: fixture\n",
            "string_pattern_mismatch",
        ),
        (
            "name: fixture\n    family: fixture\n    wave: A\n    endpoint: https://example.invalid\n"
            "    connector_id: fixture\n    enabled: 'false'\n",
            "valid boolean",
        ),
        (
            "name: fixture\n    family: fixture\n    wave: A\n    endpoint: 42\n"
            "    connector_id: fixture\n",
            "valid string",
        ),
        (
            "name: fixture\n    family: fixture\n    wave: A\n    endpoint: https://example.invalid\n"
            "    connector_id: fixture\n    format_denylist: PDF\n",
            "valid tuple",
        ),
        (
            "name: fixture\n    family: fixture\n    wave: A\n    endpoint: https://example.invalid\n"
            "    connector_id: fixture\n    enabld: true\n",
            "Extra inputs are not permitted",
        ),
        (
            "name: fixture\n    source_id: other\n    family: fixture\n"
            "    wave: A\n    endpoint: https://example.invalid\n    connector_id: fixture\n",
            "repeats source identity",
        ),
    ],
)
def test_registry_parser_rejects_rows_that_would_be_silently_omitted_or_coerced(
    tmp_path,
    row: str,
    error_fragment: str,
) -> None:
    registry_path = tmp_path / "invalid-source-registry.yaml"
    registry_path.write_text(f"version: 1\nsources:\n  - {row}", encoding="utf-8")

    for loader in (load_catalog_source_registry, load_source_registry):
        with pytest.raises(ValueError, match=error_fragment):
            loader(registry_path)


def test_registry_parser_rejects_truthy_text_for_every_boolean_field(tmp_path) -> None:
    boolean_fields = tuple(
        name
        for name, field in CatalogSourceRegistryEntry.model_fields.items()
        if field.annotation is bool
    )
    assert boolean_fields

    for field_name in boolean_fields:
        registry_path = tmp_path / f"invalid-{field_name}-registry.yaml"
        registry_path.write_text(
            "version: 1\nsources:\n"
            "  - name: source\n"
            "    family: fixture\n"
            "    wave: A\n"
            "    endpoint: https://example.invalid/source\n"
            f"    {field_name}: 'false'\n",
            encoding="utf-8",
        )
        for loader in (load_catalog_source_registry, load_source_registry):
            with pytest.raises(ValueError):
                loader(registry_path)


@pytest.mark.parametrize(
    "registry_text",
    [
        "version: 1\nversion: 2\nsources: []\n",
        "version: 1\nsources:\n"
        "  - name: shadowed_source\n"
        "    name: admitted_source\n"
        "    family: fixture\n"
        "    wave: A\n"
        "    endpoint: https://example.invalid/source\n"
        "    enabled: false\n"
        "    enabled: true\n",
        "version: 1\nsources:\n"
        "  - <<: &defaults\n"
        "      name: shadowed_source\n"
        "      family: fixture\n"
        "      wave: A\n"
        "      endpoint: https://example.invalid/source\n"
        "      enabled: false\n"
        "    <<: *defaults\n"
        "    name: admitted_source\n"
        "    enabled: true\n",
    ],
)
def test_registry_loaders_reject_duplicate_yaml_mapping_keys_before_admission(
    tmp_path,
    registry_text: str,
) -> None:
    registry_path = tmp_path / "duplicate-source-registry.yaml"
    registry_path.write_text(registry_text, encoding="utf-8")

    for loader in (load_catalog_source_registry, load_source_registry):
        with pytest.raises(ValueError, match="duplicate YAML mapping key"):
            loader(registry_path)


def test_registry_model_and_projection_preserve_identity_invariants() -> None:
    from pydantic import ValidationError

    duplicate = CatalogSourceRegistryEntry(
        source_id="source",
        family="fixture",
        wave="A",
        endpoint="https://example.invalid/source",
        connector_id="fixture.source",
    )

    with pytest.raises(ValidationError, match="duplicate source identity"):
        CatalogSourceRegistrySpec(sources=(duplicate, duplicate))

    omitted_connector_registry = load_catalog_source_registry()
    projected = catalog_source_modules_from_registry(omitted_connector_registry)
    assert len(projected) == len(omitted_connector_registry.sources)


def test_registry_parser_preserves_execution_tier_dependent_defaults(tmp_path) -> None:
    registry_path = tmp_path / "defaulted-source-registry.yaml"
    registry_path.write_text(
        "version: 1\nsources:\n"
        "  - name: fetchable\n"
        "    family: fixture\n"
        "    wave: A\n"
        "    endpoint: https://example.invalid/fetchable\n"
        "    connector_id: fixture.fetch\n"
        "    execution_tier: fetchable\n",
        encoding="utf-8",
    )

    source = load_catalog_source_registry(registry_path).sources[0]

    assert source.run_lane == "empirical"
    assert source.publish_blocking is True


def test_registry_parser_preserves_omitted_connector_default(tmp_path) -> None:
    registry_path = tmp_path / "defaulted-connector-registry.yaml"
    registry_path.write_text(
        "version: 1\nsources:\n"
        "  - name: catalog_only\n"
        "    family: fixture\n"
        "    wave: A\n"
        "    endpoint: https://example.invalid/catalog\n",
        encoding="utf-8",
    )

    source = load_catalog_source_registry(registry_path).sources[0]

    assert source.connector_id == ""
    with pytest.raises(CatalogSelectionError) as caught:
        catalog_source_modules_from_registry(CatalogSourceRegistrySpec(sources=(source,)))
    assert caught.value.code == "connector_identity_missing"
    assert "source=catalog_only" in caught.value.detail
    assert "CatalogSourceRegistryEntry.connector_id" in caught.value.detail
    assert load_source_registry(registry_path).sources[0].connector_id == ""


@pytest.mark.parametrize(
    "policy_fields",
    [
        "    run_lane: enrichment\n    publish_blocking: true\n",
        "    allow_manual_backfill: true\n",
        "    default_lookback_days: 30\n",
    ],
)
def test_registry_parser_preserves_cross_field_policy_constraints(
    tmp_path,
    policy_fields: str,
) -> None:
    registry_path = tmp_path / "invalid-policy-source-registry.yaml"
    registry_path.write_text(
        "version: 1\nsources:\n"
        "  - name: source\n"
        "    family: fixture\n"
        "    wave: A\n"
        "    endpoint: https://example.invalid/source\n"
        "    connector_id: fixture.source\n" + policy_fields,
        encoding="utf-8",
    )

    with pytest.raises(ValueError):
        load_catalog_source_registry(registry_path)


def test_registry_parser_keeps_positive_future_version_valid(tmp_path) -> None:
    registry_path = tmp_path / "versioned-source-registry.yaml"
    registry_path.write_text("version: 2\nsources: []\n", encoding="utf-8")

    assert load_catalog_source_registry(registry_path).version == 2


def test_registry_parser_preserves_implicit_version_one_default(tmp_path) -> None:
    registry_path = tmp_path / "unversioned-source-registry.yaml"
    registry_path.write_text("sources: []\n", encoding="utf-8")

    assert load_catalog_source_registry(registry_path).version == 1


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
