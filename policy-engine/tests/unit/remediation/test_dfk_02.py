from __future__ import annotations

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


def _build_dfk_02_published_catalog_fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Use the public full-pipeline fixture for DFK-02 consumer proofs."""
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
    return module.build_published_catalog_fixture(tmp_path, monkeypatch)


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
