"""Memory-only removal of one frozen generated companion property."""
from pathlib import Path
import json
import sys
from unittest.mock import patch
import pytest

root = Path('/workspace/e02-F-tmle-20261006/policy-engine/schemas/snapshots/ir')
mode, key = sys.argv[1:]
if mode == 'enum':
    target = root / f'{key}.schema.json'
    value = json.loads(target.read_text())
    value['$defs']['CausalMethod']['enum'].remove('tmle')
    selector = ('test_native_tmle_report_actual_cas_and_exported_schema'
                if key == 'causal_effect_report'
                else 'test_hte_tmle_supported_wire_actual_cas_and_exported_schema')
elif mode == 'hash':
    target = root / '_manifest.json'
    value = json.loads(target.read_text())
    value['models'][key]['sha256_full'] = '0' * 64
    selector = f'test_canonical_snapshot_matches_fresh_model_generation[{key}]'
else:
    raise ValueError(mode)
corrupt = json.dumps(value, sort_keys=True, indent=2) + '\n'
read = Path.read_text
print(json.dumps(dict(mode=mode, key=key, property_removed='tmle enum' if mode=='enum' else 'model full schema hash',
    source_files_modified=False, retained=['native provider', 'CausalMethod.TMLE', 'class names', 'schema_version1.0', 'all field IDs'])), flush=True)
with patch.object(Path, 'read_text', lambda p,*a,**kw: corrupt if p==target else read(p,*a,**kw)):
    code = pytest.main([str(Path(__file__).with_name('test_tmle_generated_consumer.py')) + '::' + selector,
        '-o', 'addopts=', '-p', 'no:cacheprovider', '-q', '-s', '--tb=short',
        '--basetemp=' + str(Path(__file__).parent / ('removed-' + mode + '-' + key))])
raise SystemExit(code)
