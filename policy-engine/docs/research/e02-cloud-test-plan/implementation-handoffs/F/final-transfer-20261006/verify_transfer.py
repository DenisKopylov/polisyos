"""Verify the committed final F index and full source-card/Git transport denominator."""
import argparse
import hashlib
import gzip
import json
from pathlib import Path
import subprocess

parser = argparse.ArgumentParser()
parser.add_argument('--candidate', required=True)
args = parser.parse_args()
# Locate the repository from the actual script, without assuming a receiving worktree path.
ROOT = Path(subprocess.check_output(['git', '-C', str(Path(__file__).resolve().parent), 'rev-parse', '--show-toplevel'], text=True).strip())
PREFIX = 'policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/F/final-transfer-20261006/'

def git(*argv):
    return subprocess.check_output(['git', '-C', str(ROOT), *argv])

def read(path):
    return git('show', args.candidate + ':' + path)

def digest(raw):
    return hashlib.sha256(raw).hexdigest()

index = json.loads(read(PREFIX + 'index.json'))
transport = json.loads(read(PREFIX + 'artifact-transports.json'))
rows = index['finding_rows']
expected = {'B54','B56',*(f'B{i}' for i in range(204,226)),
            'LA-001','LA-002','LA-003','LA-004','LA-007','LA-016','LA-017','LA-019','LA-020','LA-035','LA-037'}
assert len(rows) == 35 and {r['finding_id'] for r in rows} == expected
assert len({r['primary_bundle'] for r in rows}) == 17
assert len(index['topics']) == 12 and len({t['branch'] for t in index['topics']}) == 12
assert index['G_integration']['main_authorized'] is False
assert index['P41']['predicate_basis'] == 'not_established'
assert index['common_base_tree'] == git('rev-parse', index['common_base_sha']+'^{tree}').decode().strip()
subprocess.run(['git','-C',str(ROOT),'merge-base','--is-ancestor',index['published_anchor'],index['common_base_sha']],check=True)
assert len({t['original_path'] for t in transport['files']}) == len(transport['files'])
for ref in transport['files']:
    raw = git('show',ref['git_ref']+':'+ref['path']) if 'git_ref' in ref else read(ref['path'])
    assert len(raw) == ref['bytes'] and digest(raw) == ref['sha256'], ref['path']
registry = index['receipt_registry']
receipt_count = 0
for topic in index['topics']:
    for component in topic['components']:
        ref = component['receipt']; raw = git('show', ref['git_ref']+':'+ref['path']); d=json.loads(raw)
        assert len(raw)==ref['bytes'] and digest(raw)==ref['sha256'], ref
        assert d['schema']=='policyos.e02.implementation_handoff.v1' and d['unit']=='F'
        assert component['implementation_commits']==d['implementation_commits']
        candidate=component['implementation_candidate_sha']
        assert component['implementation_candidate_tree']==git('rev-parse',candidate+'^{tree}').decode().strip()
        subprocess.run(['git','-C',str(ROOT),'merge-base','--is-ancestor',candidate,ref['git_ref']],check=True)
        patch=git('diff','--binary',component['slice_base_sha'],candidate)
        assert digest(patch)==component['full_base_to_implementation_diff']['sha256']
        assert git('diff','--name-only',component['slice_base_sha'],candidate).decode().splitlines()==component['full_base_to_implementation_diff']['paths']
        for check in d['checks']:
            for field in ['command','target_sha','environment','input_closure','outcome','output']:
                assert field in check,(ref,field)
            assert check['outcome'] in {'PASS','FAIL','ERROR','SKIP','UNRUN'}
            assert isinstance(check['output'],str) and check['output']
            git('cat-file','-e',check['target_sha']+'^{commit}')
            if check['output'].startswith('policy-engine/'):
                git('cat-file','-e',ref['git_ref']+':'+check['output'])
        receipt_count += 1
blocks = 0
distinct_blocks=set()
for row in rows:
    assert row['check'] in {'PASS','FAIL','ERROR','SKIP','UNRUN'}
    assert row['outcome'] in {'closed','limited','held'}
    assert row['actual_consumer'] and row['criterion_short_ru'] and row['limit_next_owner_short_ru']
    assert row['candidate_tree_sha']==git('rev-parse',row['implementation_sha']+'^{tree}').decode().strip(),row['finding_id']
    ref=row['receipt_ref']; raw=git('show',ref['head']+':'+ref['path'])
    assert len(raw)==ref['bytes'] and digest(raw)==ref['sha256'],row['finding_id']
    owner_receipt=json.loads(raw)
    if row['outcome']=='closed': assert row['finding_id'] in owner_receipt['closure_ids'], row['finding_id']
    for source in row['original_source_criterion_refs']:
        assert source['criterion_id']==row['finding_id'],(row['finding_id'],source['criterion_id'])
        raw_source=git('show',source['source_sha']+':'+source['source_path'])
        assert git('rev-parse',source['source_sha']+':'+source['source_path']).decode().strip()==source['document_git_blob']
        a,b=source['lines']; block=b''.join(raw_source.splitlines(keepends=True)[a-1:b])
        assert len(block)==source['bytes'] and digest(block)==source['sha256'],(row['finding_id'],source)
        assert block.decode('utf-8').splitlines()[0].startswith('## '+row['finding_id']+'.'),(row['finding_id'],block[:120])
        blocks += 1
        distinct_blocks.add((source['source_sha'],source['source_path'],tuple(source['lines']),source['sha256']))
    rec=registry[row['receipt_registry_index']]
    assert rec['head']==ref['head'] and rec['receipt_path']==ref['path']
    assert all(0<=i<len(owner_receipt['checks']) for i in row['deciding_check_registry_indices'])
assert blocks==36 and len(distinct_blocks)==35
assert receipt_count==15 and len(registry)==15
assert {(r['head'],r['receipt_path']) for r in registry} == {(c['receipt']['git_ref'],c['receipt']['path']) for t in index['topics'] for c in t['components']}
counts={state:sum(r['outcome']==state for r in rows) for state in ['closed','limited','held','open']}
assert {k:v for k,v in counts.items() if v}==index['summary']['outcome_counts']
protocol_ref=index['complete_input_and_audit_refs']['protocol']
protocol_raw=read(protocol_ref['path'])
if protocol_ref.get('content_encoding')=='gzip':
    protocol_raw=gzip.decompress(protocol_raw)
    assert len(protocol_raw)==protocol_ref['decoded_bytes'] and digest(protocol_raw)==protocol_ref['decoded_sha256']
protocol=json.loads(protocol_raw)
assert protocol.get('current_deciding_reference_check',protocol['check'])=='PASS',protocol.get('issues')
assert not protocol.get('current_deciding_issues',[]),protocol.get('current_deciding_issues')
pending=json.loads(read(PREFIX+'audit/final35-inputs/pending-scientific-blockers.json'))
assert pending['status']=='resolved'
assert all(i.get('resolution_check')=='PASS' and i.get('resolution_receipt_head') for i in pending['items']),pending
if protocol['check']!='PASS':
    assert protocol['check']=='UNRUN' and protocol.get('historical_non_deciding_reference_check')=='UNRUN'
print(json.dumps({'check':'PASS','candidate_sha':args.candidate,'candidate_tree':git('rev-parse',args.candidate+'^{tree}').decode().strip(),
    'finding_count':len(rows),'bundle_count':17,'original_card_bindings':blocks,'unique_original_card_blocks':len(distinct_blocks),'topics':len(index['topics']),
    'current_handoff_components':receipt_count,'complete_transports':len(transport['files']),
    'outcomes':counts,'all_reference_custody_check':protocol['check'],
    'current_deciding_reference_check':protocol.get('current_deciding_reference_check',protocol['check']),
    'formal_G_acceptance':'pending','P41':'not_established'},ensure_ascii=False,indent=2))
