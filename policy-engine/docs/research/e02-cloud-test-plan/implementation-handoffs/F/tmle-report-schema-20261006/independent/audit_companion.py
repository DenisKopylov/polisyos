"""Read-only exact generated companion footprint/source custody audit."""
from pathlib import Path
import dataclasses
import hashlib
import importlib.metadata as metadata
import json
import os
import platform
import subprocess
import sys
import tomllib

from polisyos.ir.analytics.causal import CausalEffectReport, CausalMethod
from polisyos.ir.analytics.hte import HTEResult
from polisyos.ir.analytics.structural_causal_model import StructuralCausalModelSpec
from tools.quality.diagnostics import gen_schema as generator
from tools.quality.diagnostics import generate_ir_reference_catalog as docs
from tools.ops_runners.release import check_compatibility_release_gates as release

root = Path('/workspace/e02-F-tmle-20261006')
engine = root/'policy-engine'
pin = '27f28925d8ecaa674ae7b553faa262b1cb624903'
base = 'ae9f30204c84cb3f9d1bd418752145eec2a5429d'
here = Path(__file__).parent

def git(*args):
    return subprocess.check_output(['git','-C',str(root),*args])

assert git('rev-parse','HEAD').decode().strip()==pin
assert not git('status','--porcelain').strip()
paths=json.loads((here/'source-paths.json').read_text())
refs=[]
for path in paths:
    data=git('show',f'{pin}:{path}')
    assert (root/path).read_bytes()==data
    refs.append(dict(git_sha=pin,path=path,bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),
        git_blob=git('rev-parse',f'{pin}:{path}').decode().strip()))
changed=git('diff','--name-only',base,pin).decode().splitlines()
expected=['policy-engine/docs/reference/ir/schema-catalog.md',
    'policy-engine/release-fragments/unreleased/2026-10-06-tmle-report-schema.toml',
    'policy-engine/schemas/snapshots/ir/_manifest.json',
    'policy-engine/schemas/snapshots/ir/causal_effect_report.schema.json',
    'policy-engine/schemas/snapshots/ir/hte_result.schema.json']
assert changed==expected
snapdir=engine/'schemas/snapshots/ir'
for key in ['causal_effect_report','hte_result']:
    old=json.loads(git('show',f'{base}:policy-engine/schemas/snapshots/ir/{key}.schema.json'))
    new=json.loads((snapdir/f'{key}.schema.json').read_text())
    values=old['$defs']['CausalMethod']['enum']
    values.insert(values.index('double_ml')+1,'tmle')
    assert values==[x.value for x in CausalMethod] and len(values)==37
    if key=='causal_effect_report':
        old['description']=generator._load_or_generate_entry_payload(
            generator._resolve_entry(generator.select_abi_entries([key])[0]),
            cache_root=None,pydantic_version=generator._import_version('pydantic'))['schema_payload']['description']
    assert old==new, key
    assert new['properties']['schema_version']['default']=='1.0'
manifest=json.loads((snapdir/'_manifest.json').read_text())
original=json.loads(git('show',f'{base}:policy-engine/schemas/snapshots/ir/_manifest.json'))
for key in ['causal_effect_report','hte_result']:
    assert {k:v for k,v in original['models'][key].items() if not k.startswith('sha256_')}=={
        k:v for k,v in manifest['models'][key].items() if not k.startswith('sha256_')}
    original['models'][key]['sha256_full']=manifest['models'][key]['sha256_full']
    original['models'][key]['sha256_semantic']=manifest['models'][key]['sha256_semantic']
original['content_hash']=generator._schema_hash(original['models'])
assert original==manifest
catalog='policy-engine/docs/reference/ir/schema-catalog.md'
old_catalog=git('show',f'{base}:{catalog}').decode()
assert old_catalog.count('| `double_ml` |\n')==1
assert old_catalog.replace('| `double_ml` |\n','| `double_ml` |\n| `tmle` |\n')==(root/catalog).read_text()
assert docs.generate_reference_docs(check=True)==[]
assert CausalEffectReport.model_fields['schema_version'].default==HTEResult.model_fields['schema_version'].default=='1.0'
assert StructuralCausalModelSpec.model_fields['schema_version'].default=='1.1'
assert str(Path(generator.__file__)).startswith(str(engine))
assert str(Path(docs.__file__)).startswith(str(engine))
fragment=engine/'release-fragments/unreleased/2026-10-06-tmle-report-schema.toml'
row=tomllib.loads(fragment.read_text());row['__path__']=str(fragment.relative_to(engine))
errors,findings=release._validate_fragments(engine,release._read_toml(engine/'architecture/gates/compatibility_release.toml'),[row],breaking_classes=())
assert errors==[],errors
unchanged=[name for name in paths if name not in changed]
for name in unchanged:
    assert git('show',f'{base}:{name}')==git('show',f'{pin}:{name}'),name
assert git('rev-parse','HEAD').decode().strip()==pin
assert not git('status','--porcelain').strip()
packages={d.metadata['Name']:d.version for d in metadata.distributions() if d.metadata['Name']}
env=dict(interpreter=sys.executable,python=platform.python_version(),platform=platform.platform(),
    packages=dict(sorted(packages.items())),PYTHONPATH=os.environ.get('PYTHONPATH'),
    artificial_resource_quotas=False,product_modules=dict(generator=generator.__file__,docs=docs.__file__),
    backend_witness='Actual native NumPy TMLE; no DoWhy/EconML backend use or availability claim.')
print(json.dumps(dict(outcome='PASS',source_sha=pin,tree=git('rev-parse','HEAD^{tree}').decode().strip(),
    base_sha=base,base_tree=git('rev-parse',base+'^{tree}').decode().strip(),
    changed_paths=changed,full_diff_sha256=hashlib.sha256(git('diff','--binary',base,pin)).hexdigest(),
    source_refs=refs,unchanged_source_paths=unchanged,
    canonical_schema='Both selected complete snapshots byte-exact freshly generated native models; only existing enum insertion and admitted report description.',
    manifest='Exactly two hash-pair updates; derived99-entry digest; 97 rows and all provenance/ABI headers unchanged.',
    docs='Full reflection catalogue and schemas.md canonical check PASS; only one catalog enum row added.',
    fragment_errors=errors,fragment_findings=[dataclasses.asdict(x) for x in findings],
    environment=env,whole_global_generator='FAIL independently read author actual full output, not repeated; unrelated FeedbackSolveResult/manifest drift retained.',
    source_files_modified=False),sort_keys=True,indent=2))
