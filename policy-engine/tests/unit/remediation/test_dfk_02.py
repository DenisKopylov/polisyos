from __future__ import annotations

import importlib
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Literal

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
from polisyos.data_forge.kernel.embeddings import EmbeddingGenerationRef
from polisyos.data_forge.kernel.io.generation_basis import (
    GenerationIdentity,
    build_generation_basis,
    generation_basis_matches_members,
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


@pytest.mark.parametrize("wave", [None, "A", "B", "C", "D"])
def test_source_registry_and_module_selection_share_profile_and_wave_policy(
    wave: str | None,
) -> None:
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
            source.source_id for source in registry.enabled_sources(wave=wave, run_profile=profile)
        )

        assert (
            tuple(
                source.source_id
                for source in select_catalog_source_modules(
                    modules,
                    wave=wave,
                    run_profile=profile,
                )
            )
            == expected
        )
        assert (
            tuple(
                source.name
                for source in batch_registry.enabled_sources(wave=wave, run_profile=profile)
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
    expected_by_id = {module.source_id: module for module in modules}
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
    for family in (
        source_views.core,
        source_views.open_data,
        source_views.sdmx,
        source_views.specialized,
    ):
        family_members = {
            getattr(family, name).source_id
            for name in family.__all__
            if isinstance(getattr(family, name), CatalogSourceModuleSpec)
        }
        expected_family_ids = tuple(
            source.source_id for source in registry.sources if source.source_id in family_members
        )
        for export_name in family.__all__:
            exported = getattr(family, export_name)
            if isinstance(exported, CatalogSourceModuleSpec):
                assert exported == expected_by_id[exported.source_id]
            elif isinstance(exported, tuple) and all(
                isinstance(item, CatalogSourceModuleSpec) for item in exported
            ):
                assert tuple(item.source_id for item in exported) == expected_family_ids
                assert exported == tuple(
                    expected_by_id[source_id] for source_id in expected_family_ids
                )


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


def test_catalog_only_entry_profile_uses_metadata_policy_without_connector(tmp_path) -> None:
    registry_path = tmp_path / "catalog-only.yaml"
    registry_path.write_text(
        "version: 1\nsources:\n"
        "  - name: catalog_only\n"
        "    family: fixture\n"
        "    wave: A\n"
        "    endpoint: https://example.invalid/catalog\n",
        encoding="utf-8",
    )
    registry = load_catalog_source_registry(registry_path)
    batch = load_source_registry(registry_path)
    entry = registry.sources[0]

    for profile in ("prod_full", "catalog_refresh"):
        assert entry.included_in_run_profile(profile) is True
        assert batch.sources[0].included_in_run_profile(profile) is True
        assert registry.enabled_sources(run_profile=profile) == (entry,)
    assert entry.model_copy(update={"enabled": False}).included_in_run_profile("prod_full") is False
    with pytest.raises(CatalogSelectionError) as unknown:
        entry.included_in_run_profile("unknown")
    assert unknown.value.code == "unsupported_run_profile"
    with pytest.raises(CatalogSelectionError) as execution:
        entry.to_module_spec()
    assert execution.value.code == "connector_identity_missing"


def test_source_families_use_canonical_id_views_without_discarded_constructors(
    monkeypatch,
) -> None:
    from polisyos.data_forge.domains.catalog.sources import _factory

    def reject_redundant_constructor(*_args, **_kwargs):
        raise AssertionError("source family still constructs discarded policy")

    monkeypatch.setattr(_factory, "source", reject_redundant_constructor)
    expected = {
        entry.source_id: entry.to_module_spec() for entry in load_catalog_source_registry().sources
    }
    actual: dict[str, CatalogSourceModuleSpec] = {}
    for family in (
        source_views.core,
        source_views.open_data,
        source_views.sdmx,
        source_views.specialized,
    ):
        importlib.reload(family)
        for name in family.__all__:
            value = getattr(family, name)
            if isinstance(value, CatalogSourceModuleSpec):
                actual[value.source_id] = value
                canonical = expected[value.source_id]
                assert value.model_dump() == canonical.model_dump()
                assert value.asset_keys() == canonical.asset_keys()
                assert value.stage_contracts() == canonical.stage_contracts()
    assert actual == expected
    assert len(actual) == 35


def test_contract_import_keeps_registry_lazy_until_view_access() -> None:
    script = """
from pathlib import Path
from unittest.mock import patch

original = Path.read_text
reads = []
def guarded_read(path, *args, **kwargs):
    if path.name == "source_registry.yaml":
        reads.append(path)
        raise RuntimeError("explicit canonical view access")
    return original(path, *args, **kwargs)

with patch.object(Path, "read_text", guarded_read):
    from polisyos.data_forge.domains.catalog import registry, source_modules
    assert registry.CatalogSourceRegistryEntry
    assert source_modules.CatalogSourceModuleSpec
    assert reads == []
    try:
        source_modules.CORE_CATALOG_SOURCE_MODULES
    except RuntimeError as error:
        assert str(error) == "explicit canonical view access"
    else:
        raise AssertionError("canonical view did not read its source")
    assert len(reads) == 1
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


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


def _published_catalog_fixture_module():
    """Load the existing local HTTP fixture owner without building a catalog."""
    import importlib.util
    import sys

    fixture_path = Path(__file__).parents[1] / "runtime" / "http" / "_published_catalog_fixture.py"
    module_name = "_e02_dfk_02_published_catalog_fixture"
    spec = importlib.util.spec_from_file_location(module_name, fixture_path)
    if spec is None or spec.loader is None:
        raise AssertionError("published catalog fixture module spec is unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _build_dfk_02_published_catalog_fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Use the public full-pipeline fixture for DFK-02 consumer proofs."""
    return _published_catalog_fixture_module().build_published_catalog_fixture(
        tmp_path, monkeypatch
    )


def test_native_catalog_source_to_selected_generation_and_fabric_consumer(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Qualify one real raw-to-serving chain under an explicit controlled profile."""
    import copy
    import hashlib
    import json
    import os
    import re
    import threading
    import time
    import types
    import urllib.request
    from dataclasses import replace
    from typing import ClassVar
    from urllib.parse import parse_qs, urlparse

    import duckdb
    import hnswlib
    import numpy as np
    import yaml

    from polisyos.core.contracts.control import DataNeed, DataResolveRequest
    from polisyos.data_forge.domains.catalog._resources import catalog_default_resource_path
    from polisyos.data_forge.domains.catalog.batch.benchmark import DEFAULT_BENCHMARK_SUITE
    from polisyos.data_forge.domains.catalog.batch.config import DatasetBatchConfig
    from polisyos.data_forge.domains.catalog.batch.pipeline import (
        _harvest_stage_receipt,
        _should_skip_stage,
        current_catalog_publish_receipt,
        current_catalog_report_basis,
        run_dataset_pipeline_sync,
    )
    from polisyos.data_forge.domains.catalog.embedding_projection import (
        CATALOG_DATASET_EMBEDDING_BASIS_KIND,
        CATALOG_DATASET_EMBEDDING_PROJECTION_RULE_VERSION,
    )
    from polisyos.data_forge.domains.catalog.knowledge.search import DatasetCatalogGraph
    from polisyos.data_forge.kernel.embeddings import (
        derive_encoder_identity,
        embedding_generation_matches_encoder,
        resolve_embedding_generation,
    )
    from polisyos.fabric.connectors.profiles.models import SourceProfile
    from polisyos.fabric.connectors.profiles.registry import SourceProfileRegistry

    topics = (
        ("gdp_per_capita", "GDP per capita purchasing power parity ВВП на душу населення"),
        ("unemployment_rate", "Unemployment rate рівень безробіття"),
        ("inflation", "Inflation consumer prices інфляція споживчі ціни"),
        ("migration", "Migration flows міграційні потоки"),
        ("health_outcomes", "Health outcomes life expectancy очікувана тривалість життя здоров'я"),
        ("education_outcomes", "Education outcomes school enrollment освітні результати"),
        ("social_trust", "Social trust values survey соціальна довіра опитування"),
        ("poverty_rate", "Poverty rate income deprivation рівень бідності та доходи"),
        ("labor_force_participation", "Labor force participation участь у робочій силі"),
        ("institutional_quality", "Institutional quality rule of law державна спроможність"),
    )
    source_records = {f"FIXTURE.{metric.upper()}": (metric, title) for metric, title in topics}
    metrics_map = yaml.safe_load(
        catalog_default_resource_path("metrics_map.yaml").read_text(encoding="utf-8")
    )
    topic_titles = dict(topics)
    for metric, specification in metrics_map.items():
        for identifier in specification.get("worldbank_indicators", []):
            source_records.setdefault(
                identifier,
                (
                    metric,
                    f"{topic_titles.get(metric, ' '.join(specification['keywords']))} {identifier}",
                ),
            )
    expected_metrics = {metric for metric, _title in topics}
    assert expected_metrics == set(DEFAULT_BENCHMARK_SUITE.retrieval_metrics)
    assert expected_metrics == set(DEFAULT_BENCHMARK_SUITE.transport_variables)
    assert set(DEFAULT_BENCHMARK_SUITE.foundry_metrics) <= expected_metrics
    state = {"revision": 1}
    requests: list[str] = []
    request_lock = threading.Lock()
    fixture_owner = _published_catalog_fixture_module()

    class NativeProvider(fixture_owner._FixtureHandler):
        def end_headers(self) -> None:
            self.send_header("ETag", f'"e02-fixture-r{state["revision"]}"')
            super().end_headers()

        def do_HEAD(self) -> None:  # noqa: N802 - HTTP server protocol hook
            path = urlparse(self.path).path
            with request_lock:
                requests.append(f"HEAD {path}")
            identifier = path.removeprefix("/reach/")
            self._send(200 if identifier in source_records else 404, b"", "application/json")

        def do_GET(self) -> None:  # noqa: N802 - HTTP server protocol hook
            parsed = urlparse(self.path)
            path = parsed.path
            with request_lock:
                requests.append(f"GET {path}")
            if path == "/harvest/worldbank":
                rows = [
                    {
                        "id": identifier,
                        "name": title,
                        "sourceNote": (
                            f"{title}; controlled annual country statistics; "
                            f"fixture revision {state['revision']}."
                        ),
                        "metadata_modified": "2026-11-01T00:00:00Z",
                    }
                    for identifier, (_metric, title) in source_records.items()
                ]
                payload = [{"total": len(rows), "pages": 1}, rows]
            elif path == "/harvest/ukons":
                payload = {"items": []}
            elif path.startswith("/v2/country/") and "/indicator/" in path:
                identifiers = path.rsplit("/", 1)[-1].split(";")
                if any(
                    identifier not in source_records and identifier != "NY.GDP.MKTP.CD"
                    for identifier in identifiers
                ):
                    self._send(404, b"unknown fixture indicator", "text/plain")
                    return
                if any(identifier in source_records for identifier in identifiers):
                    assert path.startswith("/v2/country/UA/indicator/")
                    assert parse_qs(parsed.query).get("date") == ["2020:2020"]
                rows = [
                    {
                        "countryiso3code": "UKR",
                        "country": {"id": "UA", "value": "Ukraine"},
                        "indicator": {"id": identifier, "value": source_records[identifier][1]},
                        "date": "2020",
                        "value": float(10 + list(source_records).index(identifier)),
                        "unit": "fixture-unit",
                        "decimal": 1,
                    }
                    for identifier in identifiers
                    if identifier in source_records
                ]
                payload = [{"total": len(rows), "pages": 1}, rows]
            elif path.startswith("/reach/") and path.removeprefix("/reach/") in source_records:
                payload = {"fixture_provider": True, "revision": state["revision"]}
            else:
                self._send(404, b"not found", "text/plain")
                return
            self._send(200, json.dumps(payload, ensure_ascii=False).encode(), "application/json")

    model_root = tmp_path / "controlled-encoder"
    model_root.mkdir()
    model_path = model_root / "profile.json"

    def tokens(text: str) -> list[str]:
        return re.findall(r"[\w']+", text.lower())

    vocabulary = {
        token: index
        for index, token in enumerate(
            sorted({token for _metric, title in source_records.values() for token in tokens(title)})
        )
    }
    weights = [
        [
            float(token in tokens(title))
            + int(hashlib.sha256(f"{token}|{metric}".encode()).hexdigest()[:4], 16) / 65535 * 0.02
            for metric, title in topics
        ]
        for token in vocabulary
    ]
    model_path.write_text(
        json.dumps({"vocabulary": vocabulary, "weights": weights}), encoding="utf-8"
    )

    class NativeTokenizer:
        def __init__(self, vocabulary: dict[str, int]) -> None:
            self.vocabulary = vocabulary

        def get_vocab(self) -> dict[str, int]:
            return dict(self.vocabulary)

    class BoundEncoder:
        encode_calls: ClassVar[int] = 0

        def __init__(self, model_name: str, *, device: str = "cpu") -> None:
            material = json.loads((Path(model_name) / "profile.json").read_text())
            self.weight = np.asarray(material["weights"], dtype=np.float32)
            self.device = device
            self.tokenizer = NativeTokenizer(material["vocabulary"])

        def state_dict(self) -> dict[str, np.ndarray]:
            return {"controlled.weight": self.weight}

        def modules(self) -> tuple[BoundEncoder, ...]:
            return (self,)

        def get_config_dict(self) -> dict[str, object]:
            return {"hidden_size": len(topics), "profile": "controlled_catalog_wiring_v1"}

        def get_sentence_embedding_dimension(self) -> int:
            return len(topics)

        def encode(self, texts: list[str], **_kwargs: object) -> np.ndarray:
            type(self).encode_calls += 1
            vectors = []
            vocabulary = self.tokenizer.get_vocab()
            for text in texts:
                vector = np.full(len(topics), 0.1, dtype=np.float32)
                for token in tokens(text):
                    if token in vocabulary:
                        vector += self.weight[vocabulary[token]]
                vector /= np.linalg.norm(vector)
                vectors.append(vector)
            return np.asarray(vectors, dtype=np.float32)

    monkeypatch.setitem(
        sys.modules,
        "sentence_transformers",
        types.SimpleNamespace(SentenceTransformer=BoundEncoder),
    )
    server = fixture_owner._FixtureServer(("127.0.0.1", 0), NativeProvider)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    host, port = server.server_address[:2]
    base_url = f"http://{host}:{port}"
    original_urlopen = urllib.request.urlopen

    def provider_urlopen(request, *args, **kwargs):
        raw_url = request.full_url if isinstance(request, urllib.request.Request) else str(request)
        parsed = urlparse(raw_url)
        if parsed.netloc == "api.worldbank.org":
            identifier = parsed.path.rsplit("/", 1)[-1]
            assert identifier in source_records
            method = request.get_method() if isinstance(request, urllib.request.Request) else "GET"
            request = urllib.request.Request(  # noqa: S310 - finite loopback provider
                f"{base_url}/reach/{identifier}", method=method
            )
        return original_urlopen(request, *args, **kwargs)

    # Translate the declared finite provider's public URI only at the HTTP edge;
    # the normalizer, QC evaluator and their required denominators remain real.
    monkeypatch.setattr(urllib.request, "urlopen", provider_urlopen)
    profiles = SourceProfileRegistry()
    profiles.register(
        SourceProfile(
            profile_id="worldbank_wdi",
            display_name="Controlled finite WDI-format provider",
            connector_family="worldbank",
            base_url=f"{base_url}/v2",
            preferred_core_transport="api_sync",
            preferred_backfill_transport="api_sync",
        )
    )
    monkeypatch.setattr(SourceProfileRegistry, "_instance", profiles)
    policy = yaml.safe_load(default_catalog_source_registry_path().read_text(encoding="utf-8"))
    selected_rows = [
        copy.deepcopy(row) for row in policy["sources"] if row["name"] in {"worldbank", "ukons"}
    ]
    assert [row["name"] for row in selected_rows] == ["worldbank", "ukons"]
    for row in selected_rows:
        row["endpoint"] = f"{base_url}/harvest/{row['name']}"
    registry_path = tmp_path / "registry.yaml"
    registry_path.write_text(
        yaml.safe_dump({"version": policy["version"], "sources": selected_rows}, sort_keys=False),
        encoding="utf-8",
    )
    config = DatasetBatchConfig(
        snapshot_root=tmp_path / "snapshot",
        registry_path=registry_path,
        stages=frozenset(
            {
                "harvest",
                "normalize",
                "merge_dedup",
                "graph_load",
                "graph_index",
                "core_sources_ingest",
                "embed",
                "benchmark",
                "qc",
                "publish",
            }
        ),
        embedding_model=str(model_root),
        embedding_device="cpu",
        embedding_dimension=len(topics),
        embedding_batch_size=4,
        run_profile="prod_full",
        observation_mode="core",
        preflight_sources=("worldbank",),
        active_countries=("UA",),
        active_year_window=(2020, 2020),
        max_datasets_per_source=100_000,
        resume=True,
        fail_fast_qc=False,
        harvest_timeout=5,
    )
    graphs: list[DatasetCatalogGraph] = []
    measurements: dict[str, float] = {}

    def close_graphs() -> None:
        while graphs:
            graphs.pop().close()

    def fresh_consumer(label: str):
        graph = DatasetCatalogGraph(
            config.db_path,
            config.index_dir,
            overlay_path=tmp_path / f"absent-{label}.duckdb",
            embedding_model=str(model_root),
        )
        graphs.append(graph)
        return graph, RetrievalService(
            curated_dir=tmp_path / f"curated-{label}", dataset_catalog=graph, profiles=profiles
        )

    def index_identity() -> tuple[tuple[str, str], ...]:
        return tuple(
            (str(path.relative_to(config.index_dir)), hashlib.sha256(path.read_bytes()).hexdigest())
            for path in sorted(config.index_dir.rglob("*"))
            if path.is_file()
        )

    monkeypatch.setenv("POLISYOS_RETRIEVAL_FASTLANE_ENABLED", "0")
    monkeypatch.setattr(
        catalog_read_api,
        "load_catalog_source_registry",
        lambda: load_catalog_source_registry(registry_path),
    )
    request = DataResolveRequest(
        data_needs=[
            DataNeed(metric="gdp_per_capita", geography="UKR", time_start="2020", time_end="2020")
        ],
        mode="fastlane",
        allow_explore_fallback=False,
    )
    try:
        started = time.perf_counter()
        stats = run_dataset_pipeline_sync(replace(config, stages=config.stages - {"publish"}))
        measurements["cold_pipeline_seconds"] = time.perf_counter() - started
        benchmark = json.loads(config.benchmark_report_path.read_text())
        qc = json.loads(config.qc_report_path.read_text())
        print(
            json.dumps(
                {
                    "phase": "native_producer_reports",
                    "benchmark_metrics": benchmark["metrics"],
                    "query_refusals": sorted(
                        {str(case["vector_refusal_code"]) for case in benchmark["search"]["cases"]}
                    ),
                    "failed_QC": [check for check in qc["checks"] if not check["passed"]],
                },
                sort_keys=True,
            )
        )
        assert stats.metrics["harvest_records"] == len(source_records)
        harvest = _harvest_stage_receipt(config)
        assert harvest is not None and harvest[0] == ["worldbank", "ukons"]
        assert harvest[1]["ukons"]["records_fetched"] == 0
        normalized = [
            json.loads(line)
            for line in (config.normalized_dir / "worldbank.jsonl").read_text().splitlines()
        ]
        assert {row["dataset_id"] for row in normalized} == set(source_records)
        assert expected_metrics <= {
            metric for row in normalized for metric in row["polisyos_metrics"]
        }
        normalized_by_id = {row["id"]: row for row in normalized}
        with duckdb.connect(str(config.db_path), read_only=True) as connection:
            dataset_ids = {
                row[0] for row in connection.execute("SELECT id FROM ds_datasets").fetchall()
            }
            assert dataset_ids == {row["id"] for row in normalized}
            observations = connection.execute(
                "SELECT observation_id,dataset_id,raw_variable,canonical_var,country_code,year,"
                "survey_year,wave,value,condition_json,acquisition_method,source_watermark,"
                "dataset_version FROM ds_observations"
            ).fetchall()
            assert observations and all(len(row) == 13 for row in observations)
            assert all(
                row[1] in dataset_ids and row[2] in normalized_by_id[row[1]]["variables"]
                for row in observations
            )
            assert all(row[4] == "UA" and row[5] == 2020 and row[10] for row in observations)
            assert all(
                row[8]
                == float(10 + list(source_records).index(normalized_by_id[row[1]]["dataset_id"]))
                and json.loads(row[9])["indicator_id"] == normalized_by_id[row[1]]["dataset_id"]
                for row in observations
            )
            assert expected_metrics <= {row[3] for row in observations}
            for row in observations:
                provider_id = normalized_by_id[row[1]]["dataset_id"]
                condition = json.dumps(
                    {
                        "country_name": "Ukraine",
                        "indicator_id": provider_id,
                        "indicator_name": source_records[provider_id][1],
                        "unit": "fixture-unit",
                        "decimal": 1,
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
                condition_digest = hashlib.sha256(condition.encode()).hexdigest()[:12]
                identity = f"{row[1]}|{row[2]}|{row[3]}|UA|2020|None|None|{condition_digest}"
                assert row == (
                    hashlib.sha256(identity.encode()).hexdigest()[:24],
                    row[1],
                    row[2],
                    row[3],
                    "UA",
                    2020,
                    None,
                    None,
                    float(10 + list(source_records).index(provider_id)),
                    condition,
                    "api_sync",
                    "2026-11-01T00:00:00Z",
                    provider_id,
                )
        started = time.perf_counter()
        generation = resolve_embedding_generation(config.index_dir)
        measurements["selected_generation_resolve_seconds"] = time.perf_counter() - started
        assert generation is not None and generation.status == "complete"
        assert set(generation.ids) == dataset_ids
        assert generation.inventory["embedding_dimension"] == len(topics)
        profile = {
            "basis_kind": CATALOG_DATASET_EMBEDDING_BASIS_KIND,
            "projection_rule_version": CATALOG_DATASET_EMBEDDING_PROJECTION_RULE_VERSION,
            "embedding_model": str(model_root),
            "embedding_device": "cpu",
            "embedding_dimension": len(topics),
        }
        live_encoder = BoundEncoder(str(model_root))
        assert embedding_generation_matches_encoder(generation, encoder=live_encoder, **profile)
        live_encoder.weight[0] += 0.25
        assert not embedding_generation_matches_encoder(generation, encoder=live_encoder, **profile)
        started = time.perf_counter()
        with np.load(generation.embeddings_path, allow_pickle=False) as archive:
            vectors = np.asarray(archive["vectors"], dtype=np.float32)
        measurements["NPZ_load_seconds"] = time.perf_counter() - started
        native_index = hnswlib.Index(space="cosine", dim=len(topics))
        started = time.perf_counter()
        native_index.load_index(str(generation.index_path))
        native_index.set_ef(64)
        measurements["native_HNSW_load_seconds"] = time.perf_counter() - started
        assert len(vectors) >= 3
        started = time.perf_counter()
        for anchor in (-1, len(vectors) // 2):
            query = vectors[anchor] + np.linspace(0.001, 0.009, len(topics), dtype=np.float32)
            query /= np.linalg.norm(query)
            cosine = vectors @ query / np.linalg.norm(vectors, axis=1)
            expected = np.argsort(-cosine)
            assert np.min(np.abs(np.diff(cosine[expected[:3]]))) > 1e-7
            labels, distances = native_index.knn_query(query.reshape(1, -1), k=2)
            np.testing.assert_array_equal(labels[0], expected[:2])
            np.testing.assert_allclose(distances[0], 1.0 - cosine[expected[:2]], atol=1e-5)
            if anchor == -1:
                assert list(expected[:2]) != [0, 1]
        measurements["native_knn_oracle_seconds"] = time.perf_counter() - started
        assert current_catalog_report_basis(config)["state"] == "current"
        assert all(case["vector_refusal_code"] is None for case in benchmark["search"]["cases"])
        run_dataset_pipeline_sync(replace(config, stages=frozenset({"publish"})))
        assert (
            current_catalog_publish_receipt(config.db_path, run_profile="prod_full")["state"]
            == "current"
        )
        graph, service = fresh_consumer("revision-one")
        started = time.perf_counter()
        response = graph.search_datasets_with_status(topics[0][1], top_k=3)
        measurements["cold_guarded_query_seconds"] = time.perf_counter() - started
        assert response.vector_refusal_code is None
        assert response.query_generation_context.selected_generation_id == generation.generation_id
        assert response.query_generation_context.reader_profile.encoder_asset_identity == (
            derive_encoder_identity(BoundEncoder(str(model_root))).content_identity
        )
        started = time.perf_counter()
        repeated_query = graph.search_datasets_with_status(topics[0][1], top_k=3)
        measurements["warm_guarded_query_seconds"] = time.perf_counter() - started
        assert repeated_query.vector_refusal_code is None
        assert repeated_query.query_generation_context == response.query_generation_context
        assert service.resolve(request, run_profile="prod_full").fetch_plans
        loaded_weight = graph._embedder.weight.copy()
        graph._embedder.weight[0, 0] += 0.25
        changed_query = graph.search_datasets_with_status(topics[0][1], top_k=3)
        assert changed_query.vector_refusal_code
        assert changed_query.query_generation_context.state == "refused"
        graph._embedder.weight[:] = loaded_weight
        assert graph.search_datasets_with_status(topics[0][1], top_k=3).vector_refusal_code is None
        bound_index = index_identity()

        class UnboundEncoder(BoundEncoder):
            state_dict = None

        with monkeypatch.context() as unbound:
            unbound.setitem(
                sys.modules,
                "sentence_transformers",
                types.SimpleNamespace(SentenceTransformer=UnboundEncoder),
            )
            assert not _should_skip_stage(config, "embed")
            refused_graph, _refused_service = fresh_consumer("unbound-encoder")
            refused = refused_graph.search_datasets_with_status(topics[0][1], top_k=3)
            assert refused.vector_refusal_code
            assert refused.query_generation_context.state == "refused"
        assert index_identity() == bound_index
        preserved_inventory = generation.inventory_path.read_bytes()
        generation.inventory_path.unlink()
        assert not _should_skip_stage(config, "embed")
        assert graph.search_datasets_with_status(topics[0][1], top_k=3).vector_refusal_code
        fresh_invalid, _invalid_service = fresh_consumer("missing-inventory")
        assert fresh_invalid.search_datasets_with_status(topics[0][1], top_k=3).vector_refusal_code
        generation.inventory_path.write_bytes(preserved_inventory)
        close_graphs()
        warm_config = replace(
            config,
            stages=frozenset(
                {"harvest", "normalize", "merge_dedup", "graph_load", "graph_index", "embed"}
            ),
        )
        before_requests = list(requests)
        before_encode = BoundEncoder.encode_calls
        started = time.perf_counter()
        warm = run_dataset_pipeline_sync(warm_config)
        measurements["warm_resume_seconds"] = time.perf_counter() - started
        assert set(warm.skipped_stages) == set(warm_config.stages)
        assert requests == before_requests and BoundEncoder.encode_calls == before_encode
        _warm_graph, warm_service = fresh_consumer("warm-before-raw-drift")
        assert warm_service.resolve(request, run_profile="prod_full").fetch_plans
        payload = Path(harvest[1]["worldbank"]["payload_path"])
        old_stat = payload.stat()
        old_payload = payload.read_bytes()
        changed_payload = old_payload.replace(b"fixture revision 1", b"fixture revision 2")
        assert changed_payload != old_payload and len(changed_payload) == len(old_payload)
        payload.write_bytes(changed_payload)
        os.utime(payload, ns=(old_stat.st_atime_ns, old_stat.st_mtime_ns))
        assert not _should_skip_stage(config, "harvest")
        assert not _should_skip_stage(config, "normalize")
        assert (
            current_catalog_publish_receipt(config.db_path, run_profile="prod_full")["state"]
            != "current"
        )
        original_index = index_identity()
        _stale_graph, stale_service = fresh_consumer("fresh-after-raw-drift")
        assert not warm_service.resolve(request, run_profile="prod_full").fetch_plans
        assert not stale_service.resolve(request, run_profile="prod_full").fetch_plans
        assert index_identity() == original_index
        close_graphs()
        state["revision"] = 2
        started = time.perf_counter()
        run_dataset_pipeline_sync(config)
        measurements["reissue_pipeline_seconds"] = time.perf_counter() - started
        current = resolve_embedding_generation(config.index_dir)
        assert current is not None and current.generation_id != generation.generation_id
        assert generation.embeddings_path.is_file() and generation.index_path.is_file()
        assert (
            current_catalog_publish_receipt(config.db_path, run_profile="prod_full")["state"]
            == "current"
        )
        graph, service = fresh_consumer("revision-two")
        assert graph.search_datasets_with_status(topics[0][1], top_k=3).vector_refusal_code is None
        assert service.resolve(request, run_profile="prod_full").fetch_plans
        close_graphs()
        assert index_identity() != original_index
        published_index = index_identity()
        denied_policy = yaml.safe_load(registry_path.read_text())
        denied_policy["sources"][0]["seed_from"] = "fixture_disabled_seed"
        denied_policy["sources"].append(
            {
                "name": "fixture_disabled_seed",
                "family": "fixture",
                "wave": "A",
                "endpoint": "https://example.invalid/seed",
                "connector_id": "fixture.disabled_seed",
                "enabled": False,
            }
        )
        denied_path = tmp_path / "disabled-seed.yaml"
        denied_path.write_text(yaml.safe_dump(denied_policy), encoding="utf-8")
        monkeypatch.setattr(
            catalog_read_api,
            "load_catalog_source_registry",
            lambda: load_catalog_source_registry(denied_path),
        )
        _graph, denied_service = fresh_consumer("denied")
        with pytest.raises(CatalogSelectionError) as denied:
            denied_service.resolve(request, run_profile="prod_full")
        assert denied.value.code == "dependency_disabled"
        assert index_identity() == published_index
        wrong_connector_policy = yaml.safe_load(registry_path.read_text())
        wrong_connector_policy["sources"][0]["connector_id"] = "rest.json"
        wrong_path = tmp_path / "wrong-connector.yaml"
        wrong_path.write_text(yaml.safe_dump(wrong_connector_policy), encoding="utf-8")
        monkeypatch.setattr(
            catalog_read_api,
            "load_catalog_source_registry",
            lambda: load_catalog_source_registry(wrong_path),
        )
        _wrong_graph, wrong_service = fresh_consumer("wrong-connector")
        with pytest.raises(CatalogSelectionError) as wrong_connector:
            wrong_service.resolve(request, run_profile="prod_full")
        assert wrong_connector.value.code == "catalog_source_connector_mismatch"
        assert index_identity() == published_index
        print(
            json.dumps(
                {
                    "profile": "controlled_catalog_wiring_v1",
                    "timings": measurements,
                    "datasets": len(dataset_ids),
                    "observations": len(observations),
                    "selected_generation": current.generation_id,
                    "selected_artifact_bytes": sum(
                        path.stat().st_size
                        for path in (
                            current.embeddings_path,
                            current.index_path,
                            current.ids_path,
                            current.basis_path,
                            current.inventory_path,
                            current.selector_path,
                        )
                    ),
                    "HTTP_requests_total": len(requests),
                },
                sort_keys=True,
            )
        )
    finally:
        close_graphs()
        server.shutdown()
        server.server_close()
        server_thread.join(timeout=2)


def test_warm_and_fresh_catalog_consumers_reconcile_same_id_source_policy(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Reissue bound producer evidence before each warm and fresh consumer assertion."""
    import json
    import os
    from dataclasses import replace

    import yaml

    from polisyos.core.contracts.control import (
        DataNeed,
        DataResolveRequest,
        MetricCandidate,
    )
    from polisyos.data_forge.domains.catalog.batch.config import DatasetBatchConfig
    from polisyos.data_forge.domains.catalog.batch.core_sources.validators import (
        _current_core_output_receipt_state,
    )
    from polisyos.data_forge.domains.catalog.batch.core_sources_ingest import (
        run_core_sources_ingest,
    )
    from polisyos.data_forge.domains.catalog.batch.pipeline import (
        _harvest_stage_receipt,
        current_catalog_publish_receipt,
        current_catalog_report_basis,
        run_content_stage_with_receipt,
        run_dataset_pipeline_sync,
    )
    from polisyos.data_forge.domains.catalog.knowledge.search import DatasetCatalogGraph
    from polisyos.data_forge.domains.catalog.registry import load_catalog_source_registry
    from polisyos.data_forge.read_api import catalog as catalog_read_api
    from polisyos.fabric.retrieval.service import ResolveOutcome, RetrievalService

    fixture = _build_dfk_02_published_catalog_fixture(tmp_path, monkeypatch)
    reader_graphs: list[DatasetCatalogGraph] = [fixture.producer_graph]
    try:
        registry_path = tmp_path / "registry.yaml"
        monkeypatch.setattr(
            catalog_read_api,
            "load_catalog_source_registry",
            lambda: load_catalog_source_registry(registry_path),
        )
        monkeypatch.setenv("POLISYOS_RETRIEVAL_FASTLANE_ENABLED", "0")

        stage_state = json.loads(
            (fixture.snapshot_root / "datasets" / "manifests" / "stage_state.json").read_text(
                encoding="utf-8"
            )
        )
        producer_config_snapshot = stage_state["qc"]["input_basis"]["config"][
            "effective_producer_config"
        ]
        config = DatasetBatchConfig.from_producer_config_snapshot(producer_config_snapshot)
        assert config is not None
        config.run_profile = "prod_core_blocking"

        def worldbank_row(payload: object) -> dict[str, object]:
            assert isinstance(payload, dict)
            sources = payload.get("sources")
            assert isinstance(sources, list)
            rows = [
                row
                for row in sources
                if isinstance(row, dict) and row.get("name", row.get("source_id")) == "worldbank"
            ]
            assert len(rows) == 1
            return rows[0]

        def replace_worldbank_policy_bytes(
            blocking: bool,
            *,
            preserve_stat: os.stat_result | None = None,
        ) -> bytes:
            old_bytes = registry_path.read_bytes()
            payload = yaml.safe_load(old_bytes)
            row = worldbank_row(payload)
            assert isinstance(row.get("publish_blocking"), bool)
            text = old_bytes.decode("utf-8")
            document = yaml.compose(text)
            assert document is not None
            root_fields = {key.value: value for key, value in document.value}
            sources_node = root_fields["sources"]
            matching_nodes = []
            for source_node in sources_node.value:
                source_fields = {key.value: value for key, value in source_node.value}
                name_node = source_fields.get("name")
                if name_node is not None and name_node.value == "worldbank":
                    matching_nodes.append(source_fields["publish_blocking"])
            assert len(matching_nodes) == 1
            policy_node = matching_nodes[0]
            line_end = text.find("\n", policy_node.end_mark.index)
            if line_end < 0:
                line_end = len(text)
            assert text[policy_node.end_mark.index : line_end].strip() == ""
            replacement = "true " if blocking else "false"
            new_bytes = (
                text[: policy_node.start_mark.index] + replacement + text[line_end:]
            ).encode("utf-8")
            assert new_bytes != old_bytes
            registry_path.write_bytes(new_bytes)
            if preserve_stat is not None:
                os.utime(
                    registry_path,
                    ns=(preserve_stat.st_atime_ns, preserve_stat.st_mtime_ns),
                )
                actual_stat = registry_path.stat()
                assert (
                    actual_stat.st_dev,
                    actual_stat.st_ino,
                    actual_stat.st_size,
                    actual_stat.st_mtime_ns,
                ) == (
                    preserve_stat.st_dev,
                    preserve_stat.st_ino,
                    preserve_stat.st_size,
                    preserve_stat.st_mtime_ns,
                )
            actual_payload = yaml.safe_load(new_bytes)
            actual_row = worldbank_row(actual_payload)
            assert actual_row["publish_blocking"] is blocking
            return new_bytes

        def close_reader_graphs() -> None:
            while reader_graphs:
                reader_graphs.pop().close()

        def reissue_current_producer_basis() -> None:
            assert reader_graphs == []
            harvest_config = replace(config, stages=frozenset({"harvest"}))
            run_dataset_pipeline_sync(harvest_config)
            assert _harvest_stage_receipt(config) is not None

            core_stats = run_core_sources_ingest(config)
            assert not core_stats.failures
            assert not core_stats.failed_shards
            assert not core_stats.deferred_shards
            assert _current_core_output_receipt_state(config).is_current

            run_content_stage_with_receipt(config, "benchmark")
            run_content_stage_with_receipt(config, "qc")
            assert current_catalog_report_basis(config)["state"] == "current"
            run_content_stage_with_receipt(config, "publish")
            receipt = current_catalog_publish_receipt(
                config.db_path, run_profile=config.run_profile
            )
            assert receipt["state"] == "current"
            assert receipt["profile_input_coverage_state"] == "established"

        def open_consumer(label: str) -> RetrievalService:
            graph = DatasetCatalogGraph(
                fixture.database_path,
                fixture.snapshot_root / "datasets",
                overlay_path=tmp_path / f"missing-{label}-overlay.duckdb",
            )
            reader_graphs.append(graph)
            return RetrievalService(
                curated_dir=tmp_path / f"curated-{label}",
                dataset_catalog=graph,
                profiles=fixture.profile_registry,
            )

        request = DataResolveRequest(
            data_needs=[
                DataNeed(
                    metric="scope_metric",
                    geography="DEU",
                    time_start="2025",
                    time_end="2025",
                )
            ],
            mode="fastlane",
            allow_explore_fallback=False,
        )

        def resolve(service: RetrievalService) -> ResolveOutcome:
            return service.resolve(request, run_profile=config.run_profile)

        def plan_ids(outcome: ResolveOutcome) -> list[str]:
            return [plan.dataset_id for plan in outcome.fetch_plans]

        def worldbank_candidates(outcome: ResolveOutcome) -> list[MetricCandidate]:
            return [
                candidate
                for candidate in outcome.candidates
                if candidate.metric_id == "scope_metric"
                and candidate.connector_id == "worldbank.wdi"
                and candidate.dataset_id == "scope_dataset"
            ]

        def assert_currentness_warning(outcome: ResolveOutcome, state: str) -> None:
            assert any(
                warning.startswith(f"catalog_source_{state}:") for warning in outcome.warnings
            )

        initial_registry_bytes = registry_path.read_bytes()
        registry = yaml.safe_load(initial_registry_bytes)
        initial_worldbank = worldbank_row(registry)
        assert initial_worldbank["enabled"] is True
        assert initial_worldbank["publish_blocking"] is True
        padded_true_bytes = replace_worldbank_policy_bytes(True)
        assert padded_true_bytes != initial_registry_bytes

        close_reader_graphs()
        reissue_current_producer_basis()
        original_registry_bytes = registry_path.read_bytes()
        original_stat = registry_path.stat()

        warm = open_consumer("warm-true")
        initial_outcome = resolve(warm)
        assert plan_ids(initial_outcome) == ["scope_dataset"]
        initial_candidates = worldbank_candidates(initial_outcome)
        assert len(initial_candidates) == 1
        assert initial_candidates[0].metadata["source_currentness"] == "current"
        assert (
            initial_candidates[0].metadata["plan_admission_reason"]
            == "catalog_profile_inputs_covered"
        )
        warmed_stat = registry_path.stat()
        assert (warmed_stat.st_size, warmed_stat.st_mtime_ns) == (
            original_stat.st_size,
            original_stat.st_mtime_ns,
        )

        changed_registry_bytes = replace_worldbank_policy_bytes(False, preserve_stat=warmed_stat)
        changed_stat = registry_path.stat()
        assert changed_registry_bytes != original_registry_bytes
        assert (changed_stat.st_size, changed_stat.st_mtime_ns) == (
            warmed_stat.st_size,
            warmed_stat.st_mtime_ns,
        )
        stale_false_receipt = current_catalog_publish_receipt(
            config.db_path, run_profile=config.run_profile
        )
        stale_false_state = str(stale_false_receipt["state"])
        assert stale_false_state != "current"
        fresh_false = open_consumer("fresh-false-stale")
        for outcome in (resolve(warm), resolve(fresh_false)):
            assert plan_ids(outcome) == []
            assert worldbank_candidates(outcome) == []
            assert_currentness_warning(outcome, stale_false_state)

        close_reader_graphs()
        reissue_current_producer_basis()
        current_false = open_consumer("warm-false")
        current_false_outcome = resolve(current_false)
        assert plan_ids(current_false_outcome) == []
        assert worldbank_candidates(current_false_outcome) == []

        restored_registry_bytes = replace_worldbank_policy_bytes(True, preserve_stat=changed_stat)
        restored_stat = registry_path.stat()
        assert restored_registry_bytes != changed_registry_bytes
        assert (restored_stat.st_size, restored_stat.st_mtime_ns) == (
            changed_stat.st_size,
            changed_stat.st_mtime_ns,
        )
        stale_true_receipt = current_catalog_publish_receipt(
            config.db_path, run_profile=config.run_profile
        )
        stale_true_state = str(stale_true_receipt["state"])
        stale_true_reason = str(stale_true_receipt.get("reason") or "receipt_not_current")
        assert stale_true_state != "current"
        fresh_true = open_consumer("fresh-true-stale")
        for outcome in (resolve(current_false), resolve(fresh_true)):
            assert plan_ids(outcome) == []
            candidates = worldbank_candidates(outcome)
            assert len(candidates) == 1
            assert candidates[0].metadata["source_currentness"] == stale_true_state
            assert candidates[0].metadata["source_currentness_reason"] == stale_true_reason
            assert candidates[0].metadata["plan_admission_reason"] == stale_true_reason
            assert_currentness_warning(outcome, stale_true_state)

        close_reader_graphs()
        reissue_current_producer_basis()
        current_true = open_consumer("fresh-true-current")
        current_true_outcome = resolve(current_true)
        assert plan_ids(current_true_outcome) == ["scope_dataset"]
        current_true_candidates = worldbank_candidates(current_true_outcome)
        assert len(current_true_candidates) == 1
        assert current_true_candidates[0].metadata["source_currentness"] == "current"
        assert (
            current_true_candidates[0].metadata["plan_admission_reason"]
            == "catalog_profile_inputs_covered"
        )

        registry_path.write_text("version: 1\nsources: invalid\n", encoding="utf-8")
        with pytest.raises(ValueError):
            resolve(current_true)
    finally:
        close_reader_graphs()
        fixture.close()


def test_fresh_catalog_consumer_fails_closed_on_disabled_seed_without_index_mutation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Exercise disabled seed closure through a real fresh catalog reader."""
    import copy
    import hashlib

    import yaml

    from polisyos.core.contracts.control import DataNeed, DataResolveRequest
    from polisyos.data_forge.domains.catalog.batch.pipeline import (
        current_catalog_publish_receipt,
    )
    from polisyos.data_forge.domains.catalog.knowledge.search import DatasetCatalogGraph
    from polisyos.data_forge.domains.catalog.registry import load_catalog_source_registry
    from polisyos.data_forge.read_api import catalog as catalog_read_api
    from polisyos.fabric.retrieval.service import RetrievalService

    fixture = _build_dfk_02_published_catalog_fixture(tmp_path / "producer", monkeypatch)
    reader_graphs: list[DatasetCatalogGraph] = [fixture.producer_graph]
    try:
        registry_path = tmp_path / "producer" / "registry.yaml"
        consumer_root = tmp_path / "consumer-policies"
        consumer_root.mkdir()
        disabled_registry_path = consumer_root / "disabled-seed.yaml"
        removed_seed_registry_path = consumer_root / "removed-seed-edge.yaml"
        producer_registry_bytes = registry_path.read_bytes()
        index_root = fixture.snapshot_root / "datasets"

        def physical_index_identity() -> tuple[tuple[str, int, str], ...]:
            return tuple(
                (
                    str(path.relative_to(index_root)),
                    path.stat().st_size,
                    hashlib.sha256(path.read_bytes()).hexdigest(),
                )
                for path in sorted(index_root.rglob("*"))
                if path.is_file()
            )

        consumer_payload = yaml.safe_load(producer_registry_bytes)
        worldbank_rows = [
            row
            for row in consumer_payload["sources"]
            if row.get("name", row.get("source_id")) == "worldbank"
        ]
        assert len(worldbank_rows) == 1
        worldbank_rows[0]["seed_from"] = "i4_disabled_seed"
        consumer_payload["sources"].append(
            {
                "name": "i4_disabled_seed",
                "family": "fixture",
                "wave": "A",
                "endpoint": "https://example.invalid/i4-disabled-seed",
                "connector_id": "fixture.disabled_seed",
                "enabled": False,
                "execution_tier": "catalog",
                "run_lane": "catalog",
                "publish_blocking": False,
            }
        )
        disabled_registry_path.write_text(
            yaml.safe_dump(consumer_payload, sort_keys=False),
            encoding="utf-8",
        )
        removed_seed_payload = copy.deepcopy(consumer_payload)
        removed_worldbank = next(
            row
            for row in removed_seed_payload["sources"]
            if row.get("name", row.get("source_id")) == "worldbank"
        )
        removed_worldbank.pop("seed_from")
        removed_seed_registry_path.write_text(
            yaml.safe_dump(removed_seed_payload, sort_keys=False),
            encoding="utf-8",
        )

        monkeypatch.setenv("POLISYOS_RETRIEVAL_FASTLANE_ENABLED", "0")
        request = DataResolveRequest(
            data_needs=[
                DataNeed(
                    metric="scope_metric",
                    geography="DEU",
                    time_start="2025",
                    time_end="2025",
                )
            ],
            mode="fastlane",
            allow_explore_fallback=False,
        )

        def resolve_fresh(label: str, selected_registry: Path):
            monkeypatch.setattr(
                catalog_read_api,
                "load_catalog_source_registry",
                lambda: load_catalog_source_registry(selected_registry),
            )
            graph = DatasetCatalogGraph(
                fixture.database_path,
                index_root,
                overlay_path=tmp_path / f"missing-{label}-overlay.duckdb",
            )
            try:
                service = RetrievalService(
                    curated_dir=tmp_path / f"curated-{label}",
                    dataset_catalog=graph,
                    profiles=fixture.profile_registry,
                )
                return service.resolve(request, run_profile="prod_full")
            finally:
                graph.close()

        assert (
            current_catalog_publish_receipt(fixture.database_path, run_profile="prod_full")["state"]
            == "current"
        )
        original_index_identity = physical_index_identity()

        with pytest.raises(catalog_read_api.CatalogSelectionError) as caught:
            resolve_fresh("disabled-seed", disabled_registry_path)
        assert caught.value.code == "dependency_disabled"
        assert caught.value.detail == "source=worldbank/seed=i4_disabled_seed"
        assert physical_index_identity() == original_index_identity
        assert registry_path.read_bytes() == producer_registry_bytes

        wrong_registry = resolve_fresh("wrong-registry-control", registry_path)
        assert [plan.dataset_id for plan in wrong_registry.fetch_plans] == ["scope_dataset"]
        assert physical_index_identity() == original_index_identity
        assert registry_path.read_bytes() == producer_registry_bytes

        removed_seed = resolve_fresh("removed-seed-control", removed_seed_registry_path)
        assert [plan.dataset_id for plan in removed_seed.fetch_plans] == ["scope_dataset"]
        assert physical_index_identity() == original_index_identity
        assert registry_path.read_bytes() == producer_registry_bytes
        assert (
            current_catalog_publish_receipt(fixture.database_path, run_profile="prod_full")["state"]
            == "current"
        )
    finally:
        while reader_graphs:
            reader_graphs.pop().close()
        fixture.close()


def _generation_ref(
    *,
    basis: object,
    status: Literal["complete", "empty_generation", "legacy"] = "complete",
    selected: bool = True,
) -> EmbeddingGenerationRef:
    path = Path("generation")
    return EmbeddingGenerationRef(
        generation_id="a" * 32,
        status=status,
        root_dir=path,
        embeddings_path=path / "embeddings.npz",
        index_path=path / "index.hnsw",
        ids_path=path / "ids.json",
        basis_path=path / "basis.json",
        inventory_path=path / "inventory.json",
        selector_path=path / "embedding_generation.json",
        ids=("dataset-a", "dataset-b"),
        dimension=2,
        inventory={"basis": basis},
        selected=selected,
    )


def test_embedding_generation_basis_matches_actual_current_members() -> None:
    basis = build_generation_basis(
        basis_kind="catalog_dataset_embedding",
        generator_rule_version="policyos.catalog_dataset_embedding_projection.v1",
        members=(("dataset-b", b"projected b"), ("dataset-a", b"projected a")),
    )
    reference = _generation_ref(basis=basis.to_dict())

    assert generation_basis_matches_members(
        reference,
        basis_kind="catalog_dataset_embedding",
        members=(("dataset-a", b"projected a"), ("dataset-b", b"projected b")),
    )
    assert not generation_basis_matches_members(
        reference,
        basis_kind="catalog_dataset_embedding",
        members=(("dataset-a", b"changed projection"), ("dataset-b", b"projected b")),
    )
    assert not generation_basis_matches_members(
        reference,
        basis_kind="catalog_dataset_embedding",
        members=(("dataset-a", b"projected a"),),
    )


@pytest.mark.parametrize(
    ("status", "selected"),
    [("legacy", False), ("complete", False), ("empty_generation", True)],
)
def test_embedding_generation_basis_rejects_nonselected_or_incomplete_ref(
    status: Literal["complete", "empty_generation", "legacy"], selected: bool
) -> None:
    basis = build_generation_basis(
        basis_kind="catalog_dataset_embedding",
        generator_rule_version="policyos.catalog_dataset_embedding_projection.v1",
        members=(("dataset-a", b"projected a"),),
    )

    assert not generation_basis_matches_members(
        _generation_ref(basis=basis.to_dict(), status=status, selected=selected),
        basis_kind="catalog_dataset_embedding",
        members=(("dataset-a", b"projected a"),),
    )


@pytest.mark.parametrize(
    "basis",
    [
        None,
        {},
        {"generator_rule_version": ""},
        {"generator_rule_version": "policyos.rule.v1"},
    ],
)
def test_embedding_generation_basis_rejects_missing_or_malformed_persisted_basis(
    basis: object,
) -> None:
    assert not generation_basis_matches_members(
        _generation_ref(basis=basis),
        basis_kind="catalog_dataset_embedding",
        members=(("dataset-a", b"projected a"),),
    )


@pytest.mark.parametrize("members", [(), (("dataset-a", b"a"), ("dataset-a", b"b"))])
def test_embedding_generation_basis_rejects_empty_or_duplicate_members(
    members: tuple[tuple[str, bytes], ...],
) -> None:
    basis = build_generation_basis(
        basis_kind="catalog_dataset_embedding",
        generator_rule_version="policyos.catalog_dataset_embedding_projection.v1",
        members=(("dataset-a", b"projected a"),),
    )

    assert not generation_basis_matches_members(
        _generation_ref(basis=basis.to_dict()),
        basis_kind="catalog_dataset_embedding",
        members=members,
    )


def test_generation_identity_is_content_bound_and_validated() -> None:
    identity = GenerationIdentity.from_bytes(b"encoder-fingerprint")

    assert identity.content_identity.startswith("sha256:")
    assert len(identity.content_identity) == len("sha256:") + 64
    with pytest.raises(ValueError, match="sha256 content identity"):
        GenerationIdentity(content_identity="encoder-v1")
