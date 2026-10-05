from __future__ import annotations

import hashlib
import importlib
import os
from dataclasses import fields
from pathlib import Path
import sys
import tempfile
from zipfile import ZipFile

from pydantic import ValidationError
import yaml

BASE = Path('/Users/deniskopylov/.codex/scratch/e02-c-catalog-installed-probe-20261005-c863664274c7cf08fe3340c21e3130dc3904b5ae').resolve()
SOURCE_ROOT = BASE / 'source/policy-engine'
SOURCE_PYTHON = SOURCE_ROOT / 'src'
SOURCE_PACKAGE = SOURCE_PYTHON / 'polisyos/data_forge/domains/catalog'
WHEEL = BASE / 'dist/policy_engine-0.1.0-py3-none-any.whl'
SITE_PACKAGES = BASE / 'venv/lib/python3.14/site-packages'
INSTALLED_PACKAGE = SITE_PACKAGES / 'polisyos/data_forge/domains/catalog'
FIXTURES = BASE / 'fixtures'
WORKTREE = Path('/Users/deniskopylov/.codex/worktrees/e02-c-catalog/polisyos').resolve()
SHARED_CHECKOUT = Path('/Users/deniskopylov/polisyos/policy-engine').resolve()

assert os.environ.get('PYTHONPATH') is None, 'PYTHONPATH must be unset for installed consumer'
os.chdir('/tmp')
for entry in sys.path:
    path = Path(entry or os.getcwd()).resolve()
    assert not path.is_relative_to(SOURCE_ROOT.resolve()), f'archive source on sys.path: {path}'
    assert not path.is_relative_to(WORKTREE), f'worktree on sys.path: {path}'
    assert path not in {SHARED_CHECKOUT, SHARED_CHECKOUT / 'src'}, f'editable checkout path on sys.path: {path}'
assert not any(type(item).__name__ == '_EditableFinder' for item in sys.meta_path), 'editable finder leaked from shared env'
assert not any('editable_impl_policy_engine' in key for key in sys.modules), 'editable .pth helper executed'

package_files = sorted(
    path for path in SOURCE_PACKAGE.rglob('*')
    if path.is_file() and path.suffix in {'.py', '.yaml', '.yml'}
)
assert package_files, 'no catalog package module or YAML files found in frozen archive'
manifest_rows: list[tuple[str, str]] = []
with ZipFile(WHEEL) as wheel:
    wheel_names = set(wheel.namelist())
    for source_file in package_files:
        relative = source_file.relative_to(SOURCE_PYTHON).as_posix()
        source_bytes = source_file.read_bytes()
        assert relative in wheel_names, f'missing from wheel: {relative}'
        wheel_bytes = wheel.read(relative)
        installed_path = SITE_PACKAGES / relative
        installed_bytes = installed_path.read_bytes()
        assert wheel_bytes == source_bytes, f'wheel differs from frozen source: {relative}'
        assert installed_bytes == source_bytes, f'installed bytes differ from frozen source: {relative}'
        manifest_rows.append((relative, hashlib.sha256(source_bytes).hexdigest()))
manifest = hashlib.sha256('\n'.join(f'{path}:{digest}' for path, digest in manifest_rows).encode()).hexdigest()
print(f'BYTE_IDENTITY_PASS files={len(manifest_rows)} bytes={sum(path.stat().st_size for path in package_files)} manifest_sha256={manifest}')

module_names = (
    'polisyos',
    'polisyos.data_forge.domains.catalog',
    'polisyos.data_forge.domains.catalog.registry',
    'polisyos.data_forge.domains.catalog.selection',
    'polisyos.data_forge.domains.catalog.source_modules',
    'polisyos.data_forge.domains.catalog.batch',
    'polisyos.data_forge.domains.catalog.batch.config',
    'polisyos.data_forge.domains.catalog.batch.source_registry',
    'polisyos.data_forge.domains.catalog.batch.ckan_curation',
    'polisyos.data_forge.domains.catalog.batch.harvester',
)
modules = {name: importlib.import_module(name) for name in module_names}
for name, module in modules.items():
    module_path = Path(module.__file__).resolve()
    assert module_path.is_relative_to(SITE_PACKAGES), f'{name} not from installed site-packages: {module_path}'
    assert not module_path.is_relative_to(SOURCE_ROOT.resolve()), f'{name} loaded from archive source'
    assert not module_path.is_relative_to(WORKTREE), f'{name} loaded from worktree'
print('INSTALLED_IMPORT_ORIGINS_PASS modules=' + ','.join(module_names))
print('EDITABLE_PTH_LEAKAGE_PASS finder=absent helper=absent shared_checkout_paths=absent')

public_catalog = modules['polisyos.data_forge.domains.catalog']
registry_module = modules['polisyos.data_forge.domains.catalog.registry']
source_modules = modules['polisyos.data_forge.domains.catalog.source_modules']
batch_config_module = modules['polisyos.data_forge.domains.catalog.batch.config']
batch_registry_module = modules['polisyos.data_forge.domains.catalog.batch.source_registry']
curation_module = modules['polisyos.data_forge.domains.catalog.batch.ckan_curation']
harvester_module = modules['polisyos.data_forge.domains.catalog.batch.harvester']

canonical_path = public_catalog.default_catalog_source_registry_path().resolve()
assert canonical_path == INSTALLED_PACKAGE / 'source_registry.yaml'
canonical_payload = yaml.safe_load(canonical_path.read_text(encoding='utf-8'))
raw_ids = [row.get('source_id', row.get('name')) for row in canonical_payload['sources']]
typed_registry = public_catalog.load_catalog_source_registry()
assert len(raw_ids) == 35, f'canonical YAML source denominator changed: {len(raw_ids)}'
assert len(typed_registry.sources) == 35
assert [item.source_id for item in typed_registry.sources] == raw_ids
assert all(isinstance(item, public_catalog.CatalogSourceRegistryEntry) for item in typed_registry.sources)
module_specs = typed_registry.to_module_specs()
assert len(module_specs) == 35
assert module_specs == source_modules.CORE_CATALOG_SOURCE_MODULES
assert module_specs == public_catalog.CORE_CATALOG_SOURCE_MODULES
assert [item.source_id for item in module_specs] == raw_ids
print(f'DEFAULT_TYPED_CATALOG_PASS yaml={canonical_path} entries={len(typed_registry.sources)} ordered_projection=35')

FIXTURES.mkdir(parents=True, exist_ok=True)
metrics_map = FIXTURES / 'metrics_map.yaml'
metrics_map.write_text('{}\n', encoding='utf-8')
config = batch_config_module.DatasetBatchConfig(
    snapshot_root=FIXTURES / 'snapshot',
    metrics_map_path=metrics_map,
)
assert config.registry_path is None
assert config.default_registry_path.resolve() == canonical_path
batch_registry = config.load_registry()
assert batch_registry.version == typed_registry.version
assert len(batch_registry.sources) == 35
assert [item.name for item in batch_registry.sources] == raw_ids
for typed_item, batch_item in zip(typed_registry.sources, batch_registry.sources, strict=True):
    for dataclass_field in fields(batch_registry_module.SourceSpec):
        source_field = 'source_id' if dataclass_field.name == 'name' else dataclass_field.name
        expected = getattr(typed_item, source_field)
        if dataclass_field.name == 'seed_from' and expected is None:
            expected = ''
        actual = getattr(batch_item, dataclass_field.name)
        assert actual == expected, f'batch projection mismatch: {typed_item.source_id}.{dataclass_field.name}'
print(f'DEFAULT_BATCH_CONFIG_PASS path={config.default_registry_path} entries={len(batch_registry.sources)} metrics_map=scratch-empty')

source_spec = next(item for item in batch_registry.sources if item.name == 'data_gov_ua_exec')
formats = ('csv', ' json ', 'XLSX', 'xls', 'ods', 'zip', 'pdf', 'docx', 'xml')
accepted_package = {
    'name': 'monthly-statistics',
    'title': 'Monthly population estimates by region',
    'tags': [{'name': 'population'}],
    'resources': [
        {'id': f'resource-{index}', 'name': fmt, 'format': fmt, 'url': f'https://fixture.invalid/{index}'}
        for index, fmt in enumerate(formats)
    ],
}
curated = curation_module.curate_ckan_package(accepted_package, source_spec)
assert curated is not None
expected_default_formats = ['CSV', 'JSON', 'XLSX', 'XLS', 'ODS', 'ZIP']
assert [item['format'] for item in curated['resources']] == expected_default_formats
assert curated['policyos_curated_source'] == 'data_gov_ua_exec'
blocked_package = {
    'name': 'committee-protocol',
    'title': 'Meeting protocol minutes',
    'resources': [{'format': 'CSV', 'url': 'https://fixture.invalid/minutes.csv'}],
}
assert curation_module.curate_ckan_package(blocked_package, source_spec) is None
seed_rows = harvester_module._harvest_from_seed_source(
    source_spec,
    config,
    harvested={'data_gov_ua_broad': [accepted_package, blocked_package]},
)
assert len(seed_rows) == 1 and seed_rows[0] == curated
print(f'DEFAULT_CKAN_CONSUMER_PASS source={source_spec.name} resources_in={len(formats)} resources_out={len(curated["resources"])} blocked_off_topic=1 seed_bridge_rows={len(seed_rows)}')

normalized_yaml = FIXTURES / 'normalized_formats.yaml'
normalized_yaml.write_text(
    'version: 1\n'
    'sources:\n'
    '  - name: normalized_formats\n'
    '    family: ckan\n'
    '    wave: T\n'
    '    endpoint: https://fixture.invalid/catalog\n'
    '    format_allowlist: [" csv ", " JSON ", "   ", " XlSx "]\n'
    '    format_denylist: [" pdf ", " XML ", "   "]\n'
    '    keyword_allowlist: [population]\n'
    '    require_curated_resources: true\n',
    encoding='utf-8',
)
normalized_spec = batch_registry_module.load_source_registry(normalized_yaml).sources[0]
assert normalized_spec.format_allowlist == ('CSV', 'JSON', 'XLSX')
assert normalized_spec.format_denylist == ('PDF', 'XML')
normalized_package = {
    'name': 'population-table',
    'title': 'Population estimates',
    'resources': [
        {'id': f'normalized-{index}', 'format': fmt, 'url': f'https://fixture.invalid/{index}'}
        for index, fmt in enumerate((' csv ', 'json', ' XLSX ', 'pdf', ' xml ', 'docx'))
    ],
}
normalized_curated = curation_module.curate_ckan_package(normalized_package, normalized_spec)
assert normalized_curated is not None
assert [item['format'] for item in normalized_curated['resources']] == ['CSV', 'JSON', 'XLSX']
print('LOWER_SPACE_FORMAT_CONSUMER_PASS allowlist=CSV,JSON,XLSX denylist=PDF,XML resources_out=3')

base_row = (
    'version: 1\n'
    'sources:\n'
    '  - name: malformed_probe\n'
    '    family: ckan\n'
    '    wave: T\n'
    '    endpoint: https://fixture.invalid/catalog\n'
)
invalid_cases = {
    'top-level-list': '[]\n',
    'sources-not-list': 'version: 1\nsources: {}\n',
    'strict-bool': base_row + '    enabled: "false"\n',
    'duplicate-identity-alias': base_row + '    source_id: other_identity\n',
    'scalar-format-list': base_row + '    format_allowlist: CSV\n',
}
for label, contents in invalid_cases.items():
    invalid_path = FIXTURES / f'invalid-{label}.yaml'
    invalid_path.write_text(contents, encoding='utf-8')
    try:
        public_catalog.load_catalog_source_registry(invalid_path)
    except (ValueError, ValidationError) as exc:
        print(f'MALFORMED_REFUSED {label}={type(exc).__name__}')
    else:
        raise AssertionError(f'malformed parser input accepted: {label}')
print(f'MALFORMED_INPUT_REFUSAL_PASS cases={len(invalid_cases)}')
print('INSTALLED_CONSUMER_PROBE_PASS cwd=/tmp PYTHONPATH=unset source_rescue=absent network=unused production_data=unused')
