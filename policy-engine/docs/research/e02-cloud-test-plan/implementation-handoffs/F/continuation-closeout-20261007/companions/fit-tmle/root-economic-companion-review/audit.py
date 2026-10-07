"""Read immutable ECO receipts and current ROOT documentation, without numerical runs."""
from __future__ import annotations

import hashlib
import json
import lzma
from pathlib import Path
import re
import subprocess
import xml.etree.ElementTree as ET

REPO = Path('/workspace/e02-F-closeout-20261006')
OUT = Path(__file__).resolve().parent
CARRIER = 'fa53da2812eaa8578f79ec914b3b2abe4c491f3d'
SCIENCE = '193b3582a72c640c1d06a131f93502654a77a36a'
DOC = 'c0084cd530c1dbe01eedfb9b5c24f055954a97be'
BASE = '072d45a56d1119fe3e7665cec2cbbdca015d2934'
PRODUCT = '8236d9c368336a5ea20c1586f29aea7321db6536'
G = '9a187afa4ef75af4a7b01ca49f1cc8194f7b6fe7'
ROOT_OLD = '5609d09cbf519f01bde1ea81c6b3ee4a36a484a8'
PREFIX = 'policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/F/economic-baseline-consumer-proof-20261007'
PRIMARY = PREFIX + '.json'
DOC_PATHS = ['policy-engine/docs/research/e02-cloud-test-plan/closure-decisions/' + s for s in ('F.md', 'method-decisions.md', 'runtime-profiles.md')]

def git(*args: str) -> bytes:
    return subprocess.check_output(['git', *args], cwd=REPO)

def digest(body: bytes) -> dict:
    return {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}

def binding(ref: str, path: str) -> dict:
    body = git('show', ref + ':' + path)
    return {'git_ref': ref, 'path': path, 'git_blob': git('rev-parse', ref + ':' + path).decode().strip(), **digest(body)}

raw = git('show', CARRIER + ':' + PRIMARY)
j = json.loads(raw)
assert j['candidate_sha'] == DOC
assert git('rev-parse', DOC + '^{tree}').decode().strip() == j['candidate_tree_sha']
head = git('rev-parse', 'HEAD').decode().strip()
report = {'schema': 'policyos.e02.readonly_evidence_audit.v1', 'numerical_execution': 'UNRUN; explicitly excluded by parent review scope', 'primary': binding(CARRIER, PRIMARY), 'science': SCIENCE, 'doc_candidate': DOC, 'root_historical_caption_source': ROOT_OLD, 'observed_root_head': head, 'observed_root_tree': git('rev-parse', 'HEAD^{tree}').decode().strip(), 'issues': []}
decoded = {}
manifest_audit = []
for row in j['evidence_transfer']['manifest']:
    body = git('show', CARRIER + ':' + row['path'])
    assert digest(body) == {k: row[k] for k in ('bytes', 'sha256')}, row['path']
    actual = lzma.decompress(body) if row['encoding'] == 'xz' else body
    assert row['encoding'] in {'xz', 'raw'}, row
    assert digest(actual) == {'bytes': row['raw_bytes'], 'sha256': row['raw_sha256']}, row['path']
    decoded[row['path']] = actual
    manifest_audit.append({'path': row['path'], 'encoding': row['encoding'], 'stored': digest(body), 'decoded': digest(actual), 'outcome': 'PASS'})
assert len(decoded) == len(j['evidence_transfer']['manifest'])
report['complete_evidence_transfer'] = {'count': len(manifest_audit), 'stored_bytes': sum(r['stored']['bytes'] for r in manifest_audit), 'decoded_bytes': sum(r['decoded']['bytes'] for r in manifest_audit), 'entries': manifest_audit, 'outcome': 'PASS'}
source_audit = []
for row in j['source_bindings']:
    b = binding(row['git_ref'], row['path'])
    assert all(b[k] == row[k] for k in ('git_blob', 'bytes', 'sha256'))
    observed = binding(ROOT_OLD, row['path'])
    assert observed['git_blob'] == b['git_blob'], row['path']
    source_audit.append({'declared': b, 'root_5609': observed, 'outcome': 'PASS'})
report['all_four_changed_sources'] = source_audit
report['four_path_delta'] = git('diff', '--name-status', BASE, DOC).decode()
assert set(line.split('\t')[1] for line in report['four_path_delta'].splitlines()) == set(j['changed_paths'])
assert not git('diff', '--name-only', PRODUCT, SCIENCE, '--', 'policy-engine/src/polisyos').strip()
assert not git('diff', '--name-only', SCIENCE, DOC, '--', 'policy-engine/src/polisyos').strip()
report['runtime_unchanged'] = {'product_to_science': 'PASS, complete src/polisyos Git diff denominator zero', 'science_to_doc': 'PASS, complete src/polisyos Git diff denominator zero'}
runtime_paths = ['policy-engine/src/polisyos/foundry/' + s for s in ('plugins/economics/baselines.py', 'methods/_internal/loss.py', 'methods/loss.py', 'runtime/numeric.py', 'plugins/training_adapter.py', 'plugins/composite.py', 'plugins/economics/state.py', 'plugins/economics/mechanisms.py', 'agent_sim/training.py', 'agent_sim/metrics.py', 'agent_sim/distributions.py', 'agent_sim/jit_training.py', 'execute/_internal/numeric/__init__.py')]
report['runtime_providers'] = []
for path in runtime_paths:
    copies = [binding(ref, path) for ref in (PRODUCT, SCIENCE, DOC, ROOT_OLD, head)]
    assert len({b['git_blob'] for b in copies}) == 1, path
    report['runtime_providers'].append({'path': path, 'bindings': copies, 'outcome': 'PASS'})
report['g_c_bridge_providers'] = []
for path in runtime_paths[4:9]:
    copies = [binding(ref, path) for ref in (G, BASE, SCIENCE)]
    assert len({b['git_blob'] for b in copies}) == 1, path
    report['g_c_bridge_providers'].append({'path': path, 'bindings': copies, 'outcome': 'PASS'})
report['g_metric_profile_delta'] = {'path': runtime_paths[9], 'g': binding(G, runtime_paths[9]), 'root_base': binding(BASE, runtime_paths[9]), 'literal_delta': digest(git('diff', G, BASE, '--', runtime_paths[9])), 'classification': 'Existing ROOT current-metric recomputation and declared storage-dtype companion differ from G; not a new ECO193 source edit. The five actual C producer/bridge bodies above are byte-identical.'}
report['checks_protocol'] = []
for i, c in enumerate(j['checks']):
    assert c['outcome'] in {'PASS','FAIL','ERROR','SKIP','UNRUN'}
    assert isinstance(c['output'],str) and c['output'] in decoded
    report['checks_protocol'].append({'index': i, 'target_sha': c['target_sha'], 'outcome': c['outcome'], 'output': c['output'], 'body_binding': digest(decoded[c['output']])})
report['native_junit'] = []
for path, body in decoded.items():
    if path.endswith('native.xml.xz'):
        xml = ET.fromstring(body)
        suites = list(xml.iter('testsuite'))
        values = {k: sum(int(s.get(k, '0')) for s in suites) for k in ('tests','failures','errors','skipped')}
        report['native_junit'].append({'git_ref': CARRIER, 'path': path, 'decoded': digest(body), 'values': values})
for finding in j['per_id_recommendations']:
    row = finding['original_criterion_ref']
    body = git('show', row['git_ref'] + ':' + row['path'])
    lines = body.splitlines(keepends=True)
    block = b''.join(lines[row['lines'][0]-1:row['lines'][1]])
    assert digest(block) == {'bytes':row['block_bytes'],'sha256':row['block_sha256']}
report['original_two_criteria'] = [{'finding_id':r['finding_id'],'check':r['check'],'outcome':r['outcome'],'role':r['role'],'ref':r['original_criterion_ref']} for r in j['per_id_recommendations']]
assert j['closure_ids'] == []
report['published_closure_ids'] = []
docs = []
for path in DOC_PATHS:
    body = (REPO / path).read_bytes()
    text = body.decode()
    old = git('show', ROOT_OLD + ':' + path).decode()
    diff = git('diff', ROOT_OLD, '--', path)
    docs.append({'path':path,'working_bytes':digest(body),'old_git':binding(ROOT_OLD,path),'literal_delta':digest(diff),'current_economic_lines':[{'line':i,'text':s} for i,s in enumerate(text.splitlines(),1) if any(k in s for k in ('LA-035','LA035','ECO193','ECOfa53','bundle-eco-01'))], 'historical_stale_caption_present': bool(re.search(r'LA-035[^\n]{0,200}(?:held|remains held|intent absent)',old)), 'current_optimizer_prerequisite': bool(re.search(r'LA-035[^\n]{0,200}(?:remains held|named optimizer/intent held|held intent)',text))})
    assert not docs[-1]['current_optimizer_prerequisite'], path
report['working_three_doc_delta'] = {'source_state':'UNCOMMITTED ROOT working-tree delta; not a frozen candidate or published receipt', 'outcome':'PASS for the narrow economic caption correction', 'files':docs}
table = (REPO / DOC_PATHS[0]).read_text()
rows = re.findall(r'^\| (B\d+|LA-\d+) \| ([^\n]*)', table, re.M)
outcomes = [re.search(r'; (closed|limited|held) \|', s).group(1) for _,s in rows]
report['mechanical_document_table_counts'] = {'row_count':len(rows),'closed':outcomes.count('closed'),'limited':outcomes.count('limited'),'held':outcomes.count('held'),'scope':'caption arithmetic only; independent full35 semantic adjudication is assigned to CAU/ROOT'}
assert len(rows)==35 and outcomes.count('closed')==33 and outcomes.count('limited')==2
assert all((REPO/r['path']).read_bytes() and digest((REPO/r['path']).read_bytes()) == r['working_bytes'] for r in docs)
report['source_guard_after'] = {'root_head':git('rev-parse','HEAD').decode().strip(),'status':git('status','--short').decode(),'outcome':'PASS; three working doc byte identities unchanged during this audit'}
assert report['source_guard_after']['root_head'] == head
report['outcome'] = 'PASS'
(OUT/'evidence-audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k in ('primary','science','doc_candidate','observed_root_head','runtime_unchanged','native_junit','mechanical_document_table_counts','source_guard_after','outcome')},ensure_ascii=False,indent=2))
print('COMPLETE',len(manifest_audit),'evidence files',sum(r['decoded']['bytes'] for r in manifest_audit),'decoded bytes;',len(runtime_paths),'runtime providers;',len(source_audit),'owned sources;',len(j['checks']),'canonical checks')
