"""Read-only independent Git/original-wave custody + actual A-attribution review."""
from pathlib import Path
import ast
from collections import Counter
import hashlib
import json
import subprocess
from defusedxml import ElementTree as ET

ROOT=Path('/workspace/e02-E-continuation-20261006')
BASE=ROOT/'policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/E/continuation-20261006/pr38-r2'
OUT=Path(__file__).parent
REF='1e1b5028274814b7c4318671588202480390a6bc'
WAVE=Path('/workspace/e02-E-pr38-r2-receipts/common-wave-5e3e37276')
FROZEN='5e3e3727685132f270a3a07b9f63dd962a88cd96'

def identity(p):
    before=p.stat();sha=hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):sha.update(block)
    after=p.stat();assert (before.st_size,before.st_mtime_ns)==(after.st_size,after.st_mtime_ns)
    return dict(bytes=after.st_size,sha256=sha.hexdigest())

def git(path,ref=REF):
    return subprocess.check_output(['git','show',ref+':'+str(path)],cwd=ROOT)

def check_record(row):
    path=ROOT/row['copied_path'];assert path.read_bytes()==git(row['copied_path'])
    declared=dict(bytes=row['bytes'],sha256=row['sha256']);assert identity(path)==declared
    original=Path(row['source_path']);assert identity(original)==declared
    return dict(path=row['copied_path'],source_path=row['source_path'],**declared)

portable=[]
for folder in ['failed-wave-5e-collector','failed-wave-5e','failed-wave-5e-independent']:
    idx=BASE/folder/'portable-copy-index.json';assert idx.read_bytes()==git(idx.relative_to(ROOT))
    data=json.loads(idx.read_text());checked=[check_record(row) for row in data['records']]
    assert len(checked)==data['file_count'] and sum(row['bytes'] for row in checked)==data['bytes']
    assert data['raw_private_config_included'] is False and data['large_raw_included'] is False
    portable.append(dict(folder=folder,index_identity=identity(idx),files=len(checked),bytes=sum(x['bytes'] for x in checked),records=checked))
assert sum(x['files'] for x in portable)==79
# Parent's127 checks include48 nested asset checks below; they are not127 unique copies.
P=BASE/'failed-wave-5e';receipt=json.loads((P/'publication-receipt.json').read_text());index=json.loads((P/'copy-index.json').read_text());plan=json.loads((WAVE/'plan.json').read_text())
assert receipt['candidate_sha']==plan['candidate_sha']==FROZEN
assert receipt['candidate_tree_sha']==subprocess.check_output(['git','rev-parse',FROZEN+'^{tree}'],cwd=ROOT,text=True).strip()
assert index['file_count']==48 and len(index['files'])==48
assert sum(x['files'] for x in portable)+len(index['files'])==127
for row in index['files']:
    p=P/row['path'];assert identity(p)==dict(bytes=row['bytes'],sha256=row['sha256'])
assert sum(x['bytes'] for x in index['files'])==index['total_bytes']==6368501
source_assets=[]
for row in index['wave_source_assets']:
    original=Path('/workspace/e02-E-pr38-r2-receipts/source-freeze-5e3e37276.json') if row['path']=='source-freeze-receipt.json' else WAVE/row['path']
    assert identity(original)==dict(bytes=row['bytes'],sha256=row['sha256'])
    assert identity(P/row['path'])==identity(original)
    source_assets.append(dict(original=str(original),**row))
assert len(source_assets)==45
raw_records=receipt['excluded_raw_custody'];assert len(raw_records)==16
for row in raw_records:
    assert identity(WAVE/row['path'])==dict(bytes=row['bytes'],sha256=row['sha256'])
    assert not (P/row['path']).exists()
    assert row['path'] not in [x['path'] for x in index['files']]
raw=next(row for row in raw_records if row['path'].endswith('production-invocation.raw.json'))
assert raw['bytes']==171772803 and raw['sha256']=='404cdb1543a96433016ca3880c3d557e2d027f9fa62060be40d9b8e266b16fbd'
assert not any('git-config-private.nul' in x['path'] or 'production-invocation.raw.json' in x['path'] for x in index['files'])
# Independent actual JUnit attribution uses exact source/name/job uniqueness;
# actual seven packet cases have anonymous module/file labels.
origins={};sources={p for rows in plan['groups'].values() for p in rows}
sources.update(x['source'] for x in plan['owner_packet_extra_inputs'])
assert len(sources)==123
for source in sorted(sources):
    data=git(source,FROZEN)
    for node in ast.walk(ast.parse(data)):
        if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) and node.name.startswith('test_'):
            origins.setdefault(node.name,[]).append(source)
packets={}
for p in plan['owner_packet_extra_inputs']:
    b=git(p['source'],FROZEN);assert hashlib.sha256(b).hexdigest()==p['sha256']
    assert identity(Path(p['destination']))==dict(bytes=p['bytes'],sha256=p['sha256'])
    names={n.name for n in ast.walk(ast.parse(b)) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name.startswith('test_')}
    packets[p['source']]=dict(names=names,jobs={j['name'] for j in plan['jobs'] if p['destination'] in j['argv']})
all_cases=[];A_cases=[];native=[];job_counts=[]
for j in plan['jobs']:
    if j['kind']!='numerical':continue
    rows=[]
    for case in ET.parse(j['junit'],forbid_dtd=True).getroot().iter('testcase'):
        outcomes=[name for name in ['failure','error','skipped'] if case.find(name) is not None]
        assert len(outcomes)<=1
        status={'failure':'failed','error':'errors','skipped':'skipped'}.get(outcomes[0] if outcomes else '', 'passed')
        name=(case.get('name') or '').split('[',1)[0]
        owners=[source for source,p in packets.items() if name in p['names'] and j['name'] in p['jobs'] and origins[name]==[source]]
        row=dict(name=case.get('name'),classname=case.get('classname'),file=case.get('file'),job=j['name'],outcome=status,packet=owners)
        assert len(owners)<=1
        if owners:
            assert not row['classname'] and row['file'] is None
            A_cases.append(row)
        else:native.append(row)
        rows.append(row);all_cases.append(row)
    c=Counter(x['outcome'] for x in rows);actual=dict(cases=len(rows),**{k:c[k] for k in ['passed','failed','errors','skipped']})
    assert actual==next(r['case_counts'] for r in receipt['jobs'] if r['name']==j['name'])
    job_counts.append(dict(job=j['name'],counts=actual))
def counts(rows):
    c=Counter(x['outcome'] for x in rows);return dict(cases=len(rows),**{k:c[k] for k in ['passed','failed','errors','skipped']})
assert counts(all_cases)==receipt['numeric_counts']==dict(cases=1440,passed=1086,failed=3,errors=351,skipped=0)
assert counts(native)==receipt['native_numeric_counts_excluding_A_packets']==dict(cases=1433,passed=1086,failed=2,errors=345,skipped=0)
assert counts(A_cases)==dict(cases=7,passed=0,failed=1,errors=6,skipped=0)
for p in receipt['foreign_owner_A_packet_cases']:
    assert p['counts']==counts([x for x in A_cases if x['packet']==[p['source']]])
# Hash/content corruption is independently rejected by custody equality.
controls=[]
for field,value in [('bytes',-1),('sha256','0'*64)]:
    row=dict(index['files'][0]);row[field]=value
    assert identity(P/row['path'])!=dict(bytes=row['bytes'],sha256=row['sha256']);controls.append(field+' REFUSED')
changed=receipt['native_numeric_counts_excluding_A_packets'].copy();changed['cases']=1440
assert changed!=counts(native);controls.append('native1433/A7 denominator forgery REFUSED')
# Verify source framework/observer labels and UNRUN stage counts without native commands.
assert receipt['doctor_is_full_ci'] is False and receipt['finding_closure'] is False
stage_counts={}
for row in receipt['jobs']:
    if row['name'] in ['workspace-verify','ci-parity']:
        steps=[s for scope in row['umbrella_stages']['scopes'] for s in scope['steps']]
        observed=dict(Counter(s['outcome'] for s in steps));assert observed==row['umbrella_stage_outcomes'];stage_counts[row['name']]=observed
assert stage_counts=={'workspace-verify':{'PASS':1,'FAIL':1,'UNRUN':13},'ci-parity':{'FAIL':1,'UNRUN':23}}
for row in receipt['jobs']:
    assert row['backend_observer_scope']=='Post-command observer process; test-child changed JAX config is not inferred.'
assert receipt['static_proxy']['P41'].startswith('not_established')
for part in portable:
    for row in part['records']:assert identity(ROOT/row['path'])==dict(bytes=row['bytes'],sha256=row['sha256'])
result=dict(source_sha=REF,tree='a4ed7ca77636c4e0165923e3d5400aea0c5068d5',actual_wave_source=FROZEN,portable_indexes=portable,custody_denominators={'portable_records':79,'nested_moderate_asset_records':48,'record_checks':127,'distinct_copied_paths':79},source_assets=source_assets,raw_exclusions=raw_records,counts=counts(all_cases),native=counts(native),A=counts(A_cases),A_attribution=A_cases,job_counts=job_counts,stage_counts=stage_counts,independent_corrupt_controls=controls,publication_verdict='GO-bounded-actual5e-custody-and-attribution',reusable_collector_verdict='HOLD-two synthetic protocol escapes separately recorded',numeric_or_product_commands_executed=0,limitations=['Custody COMPLETE_BOUND is not successful wave or finding closure.','Source-frame completeness is separately under independent CAL review; this validates exact existing bytes/declared frame consistency, not a new whole framework proof.','Observer backend does not establish child JAX state; static proxy P41 inherited-red remains not_established.','Actual raw171772803B and15 private config files were hashed only, not read into output or copied.','No deletion/Trash action. Existing original and source bytes remain unchanged.'])
(OUT/'custody-review.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k not in ['portable_indexes','source_assets','A_attribution','raw_exclusions']},indent=2))
