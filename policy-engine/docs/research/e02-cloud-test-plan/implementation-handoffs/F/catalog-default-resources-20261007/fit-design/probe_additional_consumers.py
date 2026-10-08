from __future__ import annotations
import asyncio
import hashlib
import importlib
import json
from pathlib import Path
import sys
import traceback

sys.dont_write_bytecode = True
config = json.loads(Path(sys.argv[1]).read_bytes())
kind = sys.argv[2]
site = Path(config['sites'][kind]).resolve()
source_data = Path(sys.argv[3]).resolve()
scratch = Path(sys.argv[4]).resolve()
assert sys.flags.isolated == 1
rows = []

def observed(name, call):
    row = {'name': name}
    try:
        value = call()
        row.update(execution='PASS', value=value)
    except Exception as exc:
        row.update(execution='ERROR', error_type=type(exc).__name__, error=str(exc))
        traceback.print_exc(file=sys.stderr)
    rows.append(row)
    return row

cfg = importlib.import_module('polisyos.data_forge.domains.catalog.batch.config')
seed = importlib.import_module('polisyos.data_forge.domains.catalog.knowledge.variable_alignment')
proxy = importlib.import_module('polisyos.data_forge.domains.catalog.knowledge.proxy_penalties')
wvs = importlib.import_module('polisyos.fabric.connectors.sources.wvs')
api = importlib.import_module('polisyos.data_forge.read_api.catalog')
assert api.default_seed_alignments_path is seed.default_seed_alignments_path
assert api.load_seed_alignments is seed.load_seed_alignments
assert api.score_variable_pair is seed.score_variable_pair

row = observed('actual_default_DatasetBatchConfig', lambda: cfg.DatasetBatchConfig(snapshot_root=scratch / kind / 'default').run_signature)
assert row['execution'] == 'ERROR' and row['error_type'] == 'ValueError' and 'metrics_map.yaml not found:' in row['error']

row = observed('actual_explicit_original_metrics_map_DatasetBatchConfig', lambda: {'metrics_map_path': str((obj := cfg.DatasetBatchConfig(snapshot_root=scratch / kind / 'explicit', metrics_map_path=source_data / 'metrics_map.yaml')).resolved_metrics_map_path), 'signature': obj.run_signature, 'source_registry_count': len(obj.load_registry().sources)})
assert row['execution'] == 'PASS' and row['value']['metrics_map_path'] == str(source_data / 'metrics_map.yaml')

row = observed('actual_explicit_original_seed_pair', lambda: api.score_variable_pair(left_name='RL.EST', right_name='GE.EST', seed_path=source_data / 'seed_variable_alignments.yaml').model_dump(mode='json'))
assert row['execution'] == 'PASS' and row['value']['seed_support_score'] == 1.0 and row['value']['shared_canonical_vars'] == ['institutional_quality']

row = observed('actual_explicit_original_proxy_penalty_profile', lambda: {label: proxy.resolve_proxy_penalty(metric_name='health_spending', canonical_var='health_outcomes', base_penalty=0.3, country_code=country, year=year, path=source_data / 'proxy_metric_alignments.yaml') for label, country, year in [('UA_2024', 'UA', 2024), ('PL_2024', 'PL', 2024), ('PL_2022', 'PL', 2022)]})
assert row['execution'] == 'PASS' and row['value'] == {'UA_2024': 0.12, 'PL_2024': 0.18, 'PL_2022': 0.15}

row = observed('actual_default_Fabric_WVS_registry', lambda: {'registry_count': len(wvs._load_wvs_registry_indicators())})
assert row['execution'] == 'PASS' and row['value']['registry_count'] == 0

async def list_actual_wvs():
    connector = wvs.WVSConnector()
    return [item.dataset_id async for item in connector.list_datasets(None)]
row = observed('actual_default_Fabric_WVS_list_datasets', lambda: {'dataset_ids': asyncio.run(list_actual_wvs())})
assert row['execution'] == 'PASS' and set(row['value']['dataset_ids']) == set(wvs.WVSConnector._WAVE7_INDICATORS)

origins = {name: str(Path(module.__file__).resolve()) for name, module in sys.modules.copy().items() if name.startswith('polisyos') and getattr(module, '__file__', None)}
violations = {name: path for name, path in origins.items() if not Path(path).is_relative_to(site)}
assert not violations, violations
modules = {}
for module in [cfg, seed, proxy, wvs, api]:
    path = Path(module.__file__).resolve()
    data = path.read_bytes()
    modules[module.__name__] = {'path': str(path), 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
print(json.dumps({'source_sha': config['source_sha'], 'source_tree': config['source_tree'], 'kind': kind, 'python': sys.executable, 'version': sys.version, 'isolated': sys.flags.isolated, 'cwd': str(Path.cwd()), 'sys_path': sys.path, 'site': str(site), 'modules': modules, 'product_origin_count': len(origins), 'product_origins': origins, 'origin_violations': violations, 'results': rows, 'meaning': 'Read-only installed resource characterization. ERROR is an actual missing default; explicit original tracked YAML is a caller-path ABI control, not an installed-default success. WVS empty registry/static catalogue is degraded behavior, not a resource PASS.'}, indent=2))
