"""Real unpacked installed default callers; source bodies are never injected."""
from __future__ import annotations
import asyncio
import hashlib
import json
import os
from pathlib import Path
from typing import get_args
import pytest
import yaml
from polisyos.data_forge.domains.catalog import _resources
from polisyos.data_forge.read_api.catalog import catalog_default_resource_path

EXPECTED = json.loads(Path(os.environ['E02_CATALOG_EXPECTED_JSON']).read_text())
NAMES = tuple(EXPECTED['resources'])

@pytest.mark.parametrize('name', NAMES)
def test_installed_path_abi_and_exact_original_yaml_bytes(name, tmp_path, monkeypatch):
    assert len(NAMES) == 4 and set(NAMES) == set(get_args(_resources.CatalogDefaultResource))
    path = catalog_default_resource_path(name)
    expected_dir = Path(_resources.__file__).resolve().parent / '_resources'
    assert isinstance(path, Path) and path.is_absolute() and path == expected_dir / name
    raw = path.read_bytes()
    row = EXPECTED['resources'][name]
    assert len(raw) == row['bytes'] and hashlib.sha256(raw).hexdigest() == row['sha256']
    unrelated = tmp_path / 'data' / 'dataset_catalog'
    unrelated.mkdir(parents=True)
    (unrelated / name).write_text('foreign: true\n')
    monkeypatch.chdir(unrelated)
    assert catalog_default_resource_path(name) == path
    monkeypatch.chdir(tmp_path)
    assert path.read_bytes() == raw

@pytest.mark.parametrize('name', ['../seed_variable_alignments.yaml', 'other.yaml', '', '/tmp/x'])
def test_installed_unknown_resource_names_are_typed_refusals(name):
    with pytest.raises(ValueError, match='unsupported curated catalog resource'):
        catalog_default_resource_path(name)

def test_real_six_owner_defaults_load_curated_content(tmp_path):
    from polisyos.data_forge.domains.catalog.batch import harvester
    from polisyos.data_forge.domains.catalog.batch.config import DatasetBatchConfig
    from polisyos.data_forge.domains.catalog.batch.core_sources import loaders
    from polisyos.data_forge.domains.catalog.knowledge import proxy_penalties, variable_alignment
    from polisyos.data_forge.domains.catalog.metrics_map import load_metrics_map
    from polisyos.fabric.connectors.sources import wvs
    seed = catalog_default_resource_path('seed_variable_alignments.yaml')
    assert variable_alignment.default_seed_alignments_path() == loaders._seed_alignments_path() == seed
    alignments = variable_alignment.load_seed_alignments(seed)
    original = yaml.safe_load(seed.read_bytes())['alignments']
    assert len(alignments) == 8
    assert [(a.dataset_id, a.dataset_var, a.confidence) for a in alignments] == [
        (a['dataset_id'], a['dataset_var'], a['confidence']) for a in original]
    score = variable_alignment.score_variable_pair(left_name='RL.EST', right_name='GE.EST')
    assert score.seed_support_score == 1.0 and score.shared_canonical_vars == ['institutional_quality']
    proxy_penalties.load_proxy_metric_alignments.cache_clear()
    assert proxy_penalties.default_proxy_metric_alignments_path() == catalog_default_resource_path('proxy_metric_alignments.yaml')
    assert len(proxy_penalties.load_proxy_metric_alignments()) == 1
    for country, year, expected in [('UA', 2020, .12), ('PL', 2024, .18), ('DE', 2024, .15)]:
        assert proxy_penalties.resolve_proxy_penalty(metric_name='health_spending', canonical_var='health_outcomes', base_penalty=.99, country_code=country, year=year) == expected
    registry = catalog_default_resource_path('wvs_indicator_registry.yaml')
    expected = yaml.safe_load(registry.read_bytes())['indicators']
    assert len(expected) == 1049 and loaders._wvs_registry_path() == harvester._wvs_registry_path() == registry
    loaders._wvs_registry_cache = None
    harvester._load_wvs_indicator_registry.cache_clear()
    wvs._load_wvs_registry_indicators.cache_clear()
    normalized = {str(code).strip().upper(): spec for code, spec in expected.items()}
    assert loaders._load_wvs_registry() == harvester._load_wvs_indicator_registry() == normalized
    wave7 = {code: spec.get('title', code) for code, spec in expected.items() if 7 in spec.get('waves', [])}
    assert len(wave7) == 400 and wvs._load_wvs_registry_indicators() == wave7
    async def dataset_ids():
        return {item.dataset_id async for item in wvs.WVSConnector().list_datasets(None)}
    assert asyncio.run(dataset_ids()) == set(wvs.WVSConnector._WAVE7_INDICATORS) | set(wave7)
    config = DatasetBatchConfig(snapshot_root=tmp_path / 'snapshot')
    assert config.resolved_metrics_map_path == catalog_default_resource_path('metrics_map.yaml')
    assert len(load_metrics_map(config.resolved_metrics_map_path)) == 14
    assert config.raw_dir.is_relative_to(tmp_path / 'snapshot')
    # Mutable/raw output layout is distinct from the curated immutable inputs.
    assert loaders._wvs_raw_dir() == harvester._wvs_raw_dir() == config.repo_root / 'data' / 'raw' / 'wvs'

def test_installed_explicit_custom_path_semantics(tmp_path):
    from polisyos.data_forge.domains.catalog.batch.config import DatasetBatchConfig
    from polisyos.data_forge.domains.catalog.knowledge import proxy_penalties, variable_alignment
    custom = tmp_path / 'custom.yaml'
    custom.write_text('custom_metric: {keywords: [custom]}\n')
    assert DatasetBatchConfig(snapshot_root=tmp_path / 'snapshot', metrics_map_path=custom).resolved_metrics_map_path == custom
    assert proxy_penalties.load_proxy_metric_alignments(tmp_path / 'missing.yaml') == {}
    with pytest.raises(FileNotFoundError):
        variable_alignment.load_seed_alignments(tmp_path / 'missing.yaml')
    with pytest.raises(ValueError, match=r'metrics_map\.yaml not found'):
        DatasetBatchConfig(snapshot_root=tmp_path / 'absent', metrics_map_path=tmp_path / 'missing')

def test_missing_private_default_preserves_required_and_optional_policies(tmp_path, monkeypatch):
    from polisyos.data_forge.domains.catalog.batch import harvester
    from polisyos.data_forge.domains.catalog.batch.config import DatasetBatchConfig
    from polisyos.data_forge.domains.catalog.batch.core_sources import loaders
    from polisyos.data_forge.domains.catalog.knowledge import proxy_penalties, variable_alignment
    from polisyos.fabric.connectors.sources import wvs
    private = tmp_path / 'site-packages' / 'polisyos' / 'data_forge' / 'domains' / 'catalog'
    private.mkdir(parents=True)
    neighbour = tmp_path / 'data' / 'dataset_catalog'
    neighbour.mkdir(parents=True)
    (neighbour / 'seed_variable_alignments.yaml').write_text('foreign: true\n')
    monkeypatch.setattr(_resources, '__file__', str(private / '_resources.py'))
    monkeypatch.chdir(tmp_path)
    proxy_penalties.load_proxy_metric_alignments.cache_clear()
    harvester._load_wvs_indicator_registry.cache_clear()
    wvs._load_wvs_registry_indicators.cache_clear()
    monkeypatch.setattr(loaders, '_wvs_registry_cache', None)
    try:
        path = catalog_default_resource_path('seed_variable_alignments.yaml')
        assert path == private / '_resources' / 'seed_variable_alignments.yaml' and not path.exists()
        assert proxy_penalties.load_proxy_metric_alignments() == {}
        assert loaders._load_wvs_registry() == harvester._load_wvs_indicator_registry() == {}
        assert wvs._load_wvs_registry_indicators() == {}
        with pytest.raises(FileNotFoundError):
            variable_alignment.score_variable_pair(left_name='E', right_name='E')
        with pytest.raises(ValueError, match=r'metrics_map\.yaml not found'):
            DatasetBatchConfig(snapshot_root=tmp_path / 'snapshot')
    finally:
        proxy_penalties.load_proxy_metric_alignments.cache_clear()
        harvester._load_wvs_indicator_registry.cache_clear()
        wvs._load_wvs_registry_indicators.cache_clear()
        loaders._wvs_registry_cache = None

def test_installed_facade_is_the_canonical_function():
    assert catalog_default_resource_path is _resources.catalog_default_resource_path
    assert isinstance(catalog_default_resource_path('seed_variable_alignments.yaml'), Path)
