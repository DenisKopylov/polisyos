"""Run source-frozen reviewer gates without mutating the shared interpreter."""
from pathlib import Path
import hashlib
import importlib.metadata as metadata
import json
import os
import platform
import subprocess
import sys
import time

here = Path(__file__).parent
root = Path('/workspace/e02-F-tmle-20261006')
python = '/workspace/e02-F-closeout-20261006/policy-engine/.venv/bin/python'
pin, base = sys.argv[1:]
paths = [
    'policy-engine/schemas/snapshots/ir/causal_effect_report.schema.json',
    'policy-engine/schemas/snapshots/ir/hte_result.schema.json',
    'policy-engine/schemas/snapshots/ir/_manifest.json',
    'policy-engine/docs/reference/ir/schema-catalog.md',
    'policy-engine/docs/reference/schemas.md',
    'policy-engine/release-fragments/unreleased/2026-10-06-tmle-report-schema.toml',
    'policy-engine/src/polisyos/ir/analytics/causal.py',
    'policy-engine/src/polisyos/ir/analytics/hte.py',
    'policy-engine/src/polisyos/ir/analytics/structural_causal_model.py',
    'policy-engine/schemas/snapshots/ir/structural_causal_model_spec.schema.json',
    'policy-engine/src/polisyos/foundry/methods/catalog/causal/treatment_effects.py',
    'policy-engine/src/polisyos/foundry/methods/catalog/causal/tmle_core.py',
    'policy-engine/src/polisyos/ir/artifacts/io.py',
    'policy-engine/src/polisyos/ir/model_layer/canon.py',
    'policy-engine/src/polisyos/ir/registry/refs.py',
    'policy-engine/src/polisyos/core/artifacts/store.py',
    'policy-engine/tools/quality/diagnostics/gen_schema.py',
    'policy-engine/tools/quality/diagnostics/generate_ir_reference_catalog.py',
]
pathfile = here / 'source-paths.json'
pathfile.write_text(json.dumps(paths, indent=2) + '\n')
env = dict(os.environ, PYTHONPATH=str(root/'policy-engine/src')+':'+str(root/'policy-engine'),
    PYTHONDONTWRITEBYTECODE='1', REVIEW_SOURCE_SHA=pin,
    REVIEW_BASE_SHA=base, REVIEW_SOURCE_PATHS=str(pathfile))
records = []

def run(name, arguments):
    start = time.monotonic()
    proc = subprocess.run([python, *arguments], cwd=root/'policy-engine', env=env,
        capture_output=True, check=False)
    for kind,data in [('stdout',proc.stdout),('stderr',proc.stderr)]:
        (here/f'{name}.{kind}.txt').write_bytes(data)
    row = dict(name=name, argv=[python,*arguments], cwd=str(root/'policy-engine'),
        source_sha=pin, base_sha=base, environment={'python':python,'PYTHONPATH':env['PYTHONPATH'],
        'PYTHONDONTWRITEBYTECODE':'1', 'resource_quota_added':False},
        exit_code=proc.returncode, wall_seconds=time.monotonic()-start,
        outputs={kind:dict(path=f'{name}.{kind}.txt', bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
                 for kind,data in [('stdout',proc.stdout),('stderr',proc.stderr)]})
    records.append(row)
    (here/f'{name}.json').write_text(json.dumps(row,indent=2)+'\n')
    print(json.dumps(row), flush=True)

run('native-corrected', ['-m','pytest',str(here/'test_tmle_generated_consumer.py'),
    '-o','addopts=','-p','no:cacheprovider','-q','-s','--tb=short','--basetemp='+str(here/'pytest-corrected-tmp')])
if records[-1]['exit_code'] != 0:
    raise SystemExit('Native reviewer gate failed; controls held pending exact diagnosis.')
for mode in ('enum','hash'):
    for key in ('causal_effect_report','hte_result'):
        run('removal-'+mode+'-'+key, [str(here/'remove_enum_or_hash.py'),mode,key])
(here/'runs.json').write_text(json.dumps(records,indent=2)+'\n')
