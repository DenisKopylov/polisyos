"""Exercise the finite curated-default Path ABI and its real consumers."""

from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path
from typing import get_args

import pytest
import yaml

from polisyos.data_forge.domains.catalog import _resources

PRODUCT = Path(__file__).resolve().parents[5]
ORIGINALS = PRODUCT / "data" / "dataset_catalog"
NAMES = tuple(sorted(path.name for path in ORIGINALS.glob("*.yaml")))


def _helper_at(path: Path):
    path.parent.mkdir(parents=True)
    path.write_bytes(Path(_resources.__file__).read_bytes())
    spec = importlib.util.spec_from_file_location("catalog_resource_profile", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("name", NAMES)
def test_source_profile_returns_the_original_durable_path(name):
    assert len(NAMES) == 4
    assert set(NAMES) == set(get_args(_resources.CatalogDefaultResource))
    path = _resources.catalog_default_resource_path(name)
    assert type(path) is type(ORIGINALS)
    assert path == ORIGINALS / name
    assert path.read_bytes() == (ORIGINALS / name).read_bytes()


@pytest.mark.parametrize("name", ["../seed_variable_alignments.yaml", "other.yaml", "", "/tmp/x"])
def test_unknown_resource_names_refuse_instead_of_escaping_the_profile(name):
    with pytest.raises(ValueError, match="unsupported curated catalog resource"):
        _resources.catalog_default_resource_path(name)


@pytest.mark.parametrize("profile", ["source", "unpacked-installed"])
@pytest.mark.parametrize("name", NAMES)
def test_relocated_profiles_resolve_exact_bytes_without_cwd_search(
    tmp_path, monkeypatch, profile, name
):
    project = tmp_path / profile
    prefix = project / "src" if profile == "source" else project / "site-packages"
    catalog = prefix / "polisyos" / "data_forge" / "domains" / "catalog"
    helper = _helper_at(catalog / "_resources.py")
    if profile == "source":
        (project / "pyproject.toml").write_bytes((PRODUCT / "pyproject.toml").read_bytes())
        resource_dir = project / "data" / "dataset_catalog"
    else:
        resource_dir = catalog / "_resources"
    resource_dir.mkdir(parents=True)
    (resource_dir / name).write_bytes((ORIGINALS / name).read_bytes())
    unrelated = tmp_path / "neighbour" / "data" / "dataset_catalog"
    unrelated.mkdir(parents=True)
    (unrelated / name).write_text("foreign: true\n")
    monkeypatch.chdir(unrelated)
    path = helper.catalog_default_resource_path(name)
    assert path == resource_dir / name
    assert path.read_bytes() == (ORIGINALS / name).read_bytes()
    monkeypatch.chdir(tmp_path)
    assert path.read_bytes() == (ORIGINALS / name).read_bytes()


def test_missing_installed_default_does_not_search_a_neighbouring_checkout(tmp_path, monkeypatch):
    catalog = tmp_path / "site-packages" / "polisyos" / "data_forge" / "domains" / "catalog"
    helper = _helper_at(catalog / "_resources.py")
    neighbour = tmp_path / "data" / "dataset_catalog"
    neighbour.mkdir(parents=True)
    (neighbour / "seed_variable_alignments.yaml").write_bytes(
        (ORIGINALS / "seed_variable_alignments.yaml").read_bytes()
    )
    monkeypatch.chdir(tmp_path)
    path = helper.catalog_default_resource_path("seed_variable_alignments.yaml")
    assert path == catalog / "_resources" / "seed_variable_alignments.yaml"
    assert not path.exists()


def test_src_shaped_install_without_project_manifest_uses_package_private_path(tmp_path):
    catalog = tmp_path / "src" / "polisyos" / "data_forge" / "domains" / "catalog"
    helper = _helper_at(catalog / "_resources.py")
    assert helper.catalog_default_resource_path("metrics_map.yaml") == (
        catalog / "_resources" / "metrics_map.yaml"
    )


def test_all_existing_default_consumers_use_original_resources(tmp_path):
    from polisyos.data_forge.domains.catalog.batch import harvester
    from polisyos.data_forge.domains.catalog.batch.config import DatasetBatchConfig
    from polisyos.data_forge.domains.catalog.batch.core_sources import loaders
    from polisyos.data_forge.domains.catalog.knowledge import proxy_penalties, variable_alignment
    from polisyos.data_forge.domains.catalog.metrics_map import load_metrics_map
    from polisyos.fabric.connectors.sources import wvs

    seed = variable_alignment.default_seed_alignments_path()
    assert seed == loaders._seed_alignments_path() == ORIGINALS / "seed_variable_alignments.yaml"
    alignments = variable_alignment.load_seed_alignments(seed)
    assert len(alignments) == 8
    raw_seed = yaml.safe_load(seed.read_bytes())["alignments"]
    assert [(a.dataset_id, a.dataset_var, a.confidence) for a in alignments] == [
        (a["dataset_id"], a["dataset_var"], a["confidence"]) for a in raw_seed
    ]
    score = variable_alignment.score_variable_pair(left_name="RL.EST", right_name="GE.EST")
    assert score.seed_support_score == 1.0
    assert score.shared_canonical_vars == ["institutional_quality"]

    proxy_penalties.load_proxy_metric_alignments.cache_clear()
    assert proxy_penalties.default_proxy_metric_alignments_path() == (
        ORIGINALS / "proxy_metric_alignments.yaml"
    )
    assert len(proxy_penalties.load_proxy_metric_alignments()) == 1
    for country, year, expected in [("UA", 2020, 0.12), ("PL", 2024, 0.18), ("DE", 2024, 0.15)]:
        assert (
            proxy_penalties.resolve_proxy_penalty(
                metric_name="health_spending",
                canonical_var="health_outcomes",
                base_penalty=0.99,
                country_code=country,
                year=year,
            )
            == expected
        )

    registry = ORIGINALS / "wvs_indicator_registry.yaml"
    expected = yaml.safe_load(registry.read_bytes())["indicators"]
    assert len(expected) == 1049
    assert loaders._wvs_registry_path() == harvester._wvs_registry_path() == registry
    loaders._wvs_registry_cache = None
    harvester._load_wvs_indicator_registry.cache_clear()
    wvs._load_wvs_registry_indicators.cache_clear()
    normalized = {str(code).strip().upper(): spec for code, spec in expected.items()}
    assert loaders._load_wvs_registry() == harvester._load_wvs_indicator_registry() == normalized
    wave7 = {
        code: spec.get("title", code)
        for code, spec in expected.items()
        if 7 in spec.get("waves", [])
    }
    assert len(wave7) == 400
    assert wvs._load_wvs_registry_indicators() == wave7

    async def dataset_ids():
        connector = wvs.WVSConnector()
        return {item.dataset_id for item in [item async for item in connector.list_datasets(None)]}

    assert asyncio.run(dataset_ids()) == set(wvs.WVSConnector._WAVE7_INDICATORS) | set(wave7)
    config = DatasetBatchConfig(snapshot_root=tmp_path / "snapshot")
    assert config.resolved_metrics_map_path == ORIGINALS / "metrics_map.yaml"
    assert len(load_metrics_map(config.resolved_metrics_map_path)) == 14
    assert config.repo_root == PRODUCT
    assert config.raw_dir.is_relative_to(tmp_path / "snapshot")
    assert loaders._wvs_raw_dir() == harvester._wvs_raw_dir() == PRODUCT / "data" / "raw" / "wvs"


def test_explicit_custom_paths_keep_their_original_semantics(tmp_path):
    from polisyos.data_forge.domains.catalog.batch.config import DatasetBatchConfig
    from polisyos.data_forge.domains.catalog.knowledge import proxy_penalties, variable_alignment

    custom = tmp_path / "custom.yaml"
    custom.write_text("custom_metric: {keywords: [custom]}\n")
    config = DatasetBatchConfig(snapshot_root=tmp_path / "snapshot", metrics_map_path=custom)
    assert config.resolved_metrics_map_path == custom
    assert proxy_penalties.load_proxy_metric_alignments(tmp_path / "missing.yaml") == {}
    with pytest.raises(FileNotFoundError):
        variable_alignment.load_seed_alignments(tmp_path / "missing.yaml")
    with pytest.raises(ValueError, match=r"metrics_map\.yaml not found"):
        DatasetBatchConfig(snapshot_root=tmp_path / "absent", metrics_map_path=tmp_path / "missing")
    score = variable_alignment.score_variable_pair(
        left_name="E",
        right_name="E",
        left_definition="Employment rate",
        right_definition="Employment rate",
        left_unit="percent",
        right_unit="percent",
        seed_alignments=[],
    )
    assert score.seed_support_score == 0.0 and score.overall_score == 0.85


def test_optional_fallback_and_required_read_policies_survive_missing_defaults(
    tmp_path, monkeypatch
):
    from polisyos.data_forge.domains.catalog.batch import harvester
    from polisyos.data_forge.domains.catalog.batch.config import DatasetBatchConfig
    from polisyos.data_forge.domains.catalog.batch.core_sources import loaders
    from polisyos.data_forge.domains.catalog.knowledge import proxy_penalties, variable_alignment
    from polisyos.fabric.connectors.sources import wvs

    catalog = tmp_path / "site-packages" / "polisyos" / "data_forge" / "domains" / "catalog"
    catalog.mkdir(parents=True)
    monkeypatch.setattr(_resources, "__file__", str(catalog / "_resources.py"))
    proxy_penalties.load_proxy_metric_alignments.cache_clear()
    harvester._load_wvs_indicator_registry.cache_clear()
    wvs._load_wvs_registry_indicators.cache_clear()
    monkeypatch.setattr(loaders, "_wvs_registry_cache", None)
    try:
        assert proxy_penalties.load_proxy_metric_alignments() == {}
        assert loaders._load_wvs_registry() == harvester._load_wvs_indicator_registry() == {}
        assert wvs._load_wvs_registry_indicators() == {}
        with pytest.raises(FileNotFoundError):
            variable_alignment.score_variable_pair(left_name="E", right_name="E")
        with pytest.raises(ValueError, match=r"metrics_map\.yaml not found"):
            DatasetBatchConfig(snapshot_root=tmp_path / "snapshot")
    finally:
        proxy_penalties.load_proxy_metric_alignments.cache_clear()
        harvester._load_wvs_indicator_registry.cache_clear()
        wvs._load_wvs_registry_indicators.cache_clear()
        loaders._wvs_registry_cache = None


def test_runtime_facade_is_the_canonical_path_function():
    from polisyos.data_forge.read_api.catalog import catalog_default_resource_path

    assert catalog_default_resource_path is _resources.catalog_default_resource_path
    assert isinstance(catalog_default_resource_path("seed_variable_alignments.yaml"), Path)
