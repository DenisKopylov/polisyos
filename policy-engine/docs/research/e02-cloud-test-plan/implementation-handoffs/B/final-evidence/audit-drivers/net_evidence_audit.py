import hashlib
import json
import pathlib
import subprocess
import xml.etree.ElementTree as ET

WT = '/workspace/e02-B-adapters'
HERE = pathlib.Path(__file__).parent
HEAD = '3d18f37a5953f577c99260442a5e9afbc308a1d6'
PREFIX = 'policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/B/'


def git(*args):
    return subprocess.check_output(['git', '-C', WT, *args])


def blob(path, ref=HEAD):
    return git('show', ref + ':' + path)


def sha(data):
    return hashlib.sha256(data).hexdigest()


receipt_bytes = blob(PREFIX + 'adapters-deadline.json')
receipt = json.loads(receipt_bytes)
index_bytes = blob(receipt['evidence_index'])
assert sha(index_bytes) == receipt['evidence_index_sha256']
index = json.loads(index_bytes)
assert index['candidate_sha'] == receipt['candidate_sha'] == '88e27af5f3aedac68fdbe268ec87e17f239d755f'
records = []
for path, record in index['files'].items():
    data = blob(path)
    assert sha(data) == record['sha256'] and len(data) == record['bytes'], path
    records.append({'path': path, 'sha256': sha(data), 'bytes': len(data)})
assert len(records) == 33

pool_path = 'policy-engine/src/polisyos/fabric/connectors/pool.py'
old = receipt['checks'][6]
old_origin = old['environment']['actual_pool_module_origin']
assert sha(blob(pool_path, old['target_sha'])) == old_origin['sha256']
assert git('rev-parse', old['target_sha'] + ':' + pool_path).decode().strip() == old_origin['git_blob']
assert 'module_origins' not in old['environment']
assert 'later' in old['environment']['identity_scope'].lower()

for index_number in [2, 3]:
    check = receipt['checks'][index_number]
    assert 'isolated in-memory method mutation' in check['input_closure']
    assert '3068af15d56d6eb43e247c456ae9b3a1f0ecbb7d7fed5dabc1b730893efea738' in check['input_closure']
    module = check['environment']['module_origins']['polisyos.fabric.connectors.pool']
    assert module['sha256'] == sha(blob(pool_path, check['target_sha']))

logprefix = PREFIX + 'adapters-deadline-logs/'
native = json.loads(blob(logprefix + 'native-full15.json'))
assert native['source_unchanged'] and native['source_before'] == native['source_after']
assert native['target_sha'] == receipt['candidate_sha'] == native['source_before']['sha']
assert native['source_before']['status'] == ''
assert native['source_before']['tree'] == receipt['candidate_tree_sha']
assert native['exit_code'] == 0
assert sha(blob(logprefix + 'native-full15.log')) == native['log']['sha256']
suite = ET.fromstring(blob(logprefix + 'native-full15.xml')).find('testsuite')
assert suite is not None
assert int(suite.attrib['tests']) == 390 and int(suite.attrib['failures']) == int(suite.attrib['errors']) == 0
assert int(suite.attrib['skipped']) == 1 and len(suite.findall('testcase')) == 390
skipped = [case for case in suite.findall('testcase') if case.find('skipped') is not None]
assert len(skipped) == 1
assert skipped[0].attrib['name'] == 'test_cancelled_initiator_cannot_erase_actual_provider_cost'
assert skipped[0].find('skipped').attrib['type'] == 'pytest.xfail'
old_suite = ET.fromstring(blob(logprefix + 'test-only-242.xml')).find('testsuite')
assert old_suite is not None and int(old_suite.attrib['tests']) == 14 and int(old_suite.attrib['failures']) == 3
independent_suite = ET.fromstring(blob(logprefix + 'independent-cmp/native-pool-88.xml')).find('testsuite')
assert independent_suite is not None and int(independent_suite.attrib['tests']) == 17
assert int(independent_suite.attrib['failures']) == int(independent_suite.attrib['errors']) == int(independent_suite.attrib['skipped']) == 0

resume = json.loads(blob(logprefix + 'admission-resume.json'))
assert resume['status'] == 'admitted' and resume['requested']['mode'] == 'resume'
assert resume['requested']['path'] == '/workspace/e02-B-adapters'
assert resume['requested']['branch'] == 'codex/e02-B-adapters'
checkpoint = json.loads(blob(logprefix + 'slice-base.json'))
assert checkpoint['admission_sha256'] == sha(blob(logprefix + 'admission-resume.json'))
assert checkpoint['slice_base_sha'] == receipt['slice_base_sha'] == 'd0eb247a2dff81f0a3ca48ea844c9ce3b8559b83'
assert checkpoint['status'] == '' and checkpoint['admission_exit_code'] == 0

assert not receipt['closure_ids']
assert len(receipt['finding_dispositions']) == 15 and len(receipt['baseline_cells']) == 37
assert any('externally requested caller cancellation' in value for value in receipt['limitations_and_next_owner'])
out = {
    'schema': 'policyos.e02.B.independent_NET_evidence_audit.v1',
    'head': HEAD, 'candidate': receipt['candidate_sha'], 'candidate_tree': receipt['candidate_tree_sha'],
    'receipt_sha256': sha(receipt_bytes), 'evidence_index_sha256': sha(index_bytes),
    'read_only': True, 'runtime_rerun': False, 'indexed_file_count': len(records),
    'indexed_bytes': sum(row['bytes'] for row in records), 'all_files_read_from_exact_git_objects': True,
    'indexed_files': records, 'native_junit': suite.attrib,
    'native_interpretation': '389 PASS + one strict XFAIL; direct --runxfail failure retained, no full finding closure',
    'test_only_242_junit': old_suite.attrib, 'independent_88_junit': independent_suite.attrib,
    'corrected_test_only_executed_origin_sha256': old_origin['sha256'],
    'removal_execution_overlay': 'Two isolated in-memory method removals with on-disk source88 preserved and committed driver3068 bound',
    'writer_resume_admission_scope': 'Root-provided adapters writer only; seven detached review custody qualifications remain not_established',
    'baseline_cells': 37, 'dispositions': 15, 'closure_ids': [],
    'verdict': 'PASS_METADATA_AND_DECIDING_BYTE_CUSTODY_BOUNDED; deadline admission/registration only, no universal external-cancel suppression/hardwall/served closure',
}
fp = HERE / 'net-evidence-audit.json'
fp.write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'path': str(fp), 'bytes': fp.stat().st_size, 'sha256': sha(fp.read_bytes()), 'verdict': out['verdict']}))
