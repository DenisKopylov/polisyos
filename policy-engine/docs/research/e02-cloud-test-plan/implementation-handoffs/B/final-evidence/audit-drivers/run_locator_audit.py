import hashlib
import json
import pathlib
import subprocess

WT = '/workspace/e02-B-run'
HERE = pathlib.Path(__file__).parent
PREFIX = 'policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/B/'
BASE = '8b913ecf7c4793004e9e3cec1b163bd04d950f25'
HEAD = '0b2ba4ae0f9a2f6be9e53dd71e28f20be66ecce3'


def git(*args):
    return subprocess.check_output(['git', '-C', WT, *args])


def blob(ref, path):
    return git('show', ref + ':' + path)


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def walk(value, pointer=''):
    if isinstance(value, dict):
        for key, nested in value.items():
            yield from walk(nested, pointer + '/' + key.replace('~', '~0').replace('/', '~1'))
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            yield from walk(nested, pointer + '/' + str(index))
    elif isinstance(value, str):
        yield pointer, value


qpath = PREFIX + 'run-canonical-locator-qualification.json'
qbytes = blob(HEAD, qpath)
qualification = json.loads(qbytes)
cpath = qualification['complete_census']['path']
cbytes = blob(HEAD, cpath)
census = json.loads(cbytes)
assert sha256(cbytes) == qualification['complete_census']['sha256']
expected = sorted(p for p in git('ls-tree', '-r', '--name-only', BASE, PREFIX).decode().splitlines() if p.startswith(PREFIX + 'run') and p.endswith('.json'))
assert expected == sorted(r['path'] for r in census['complete_JSON_paths'])
assert len(expected) == census['json_file_count'] == 25
refs = []
bad = []
for row in census['complete_JSON_paths']:
    data = blob(BASE, row['path'])
    assert sha256(data) == row['sha256'] and len(data) == row['bytes']
    for pointer, value in walk(json.loads(data)):
        if 'PolicyOS_E02_Combined_Agent_Package' in value:
            refs.append({'file': row['path'], 'json_pointer': pointer, 'value': value})
        if census['malformed_prefix'] in value:
            bad.append({'file': row['path'], 'json_pointer': pointer, 'value': value, 'occurrence_count': value.count(census['malformed_prefix'])})
assert refs == census['all_package_ref_strings']
assert bad == census['malformed_occurrences'] == qualification['qualified_historical_occurrences']
assert len(refs) == qualification['complete_census']['package_ref_string_count'] == 50
assert len(bad) == sum(r['occurrence_count'] for r in bad) == 3

binding = qualification['canonical_source_binding']
source = blob(binding['source_sha'], binding['path'])
assert sha256(source) == binding['sha256']
assert git('rev-parse', binding['source_sha'] + ':' + binding['path']).decode().strip() == binding['git_blob']
start, end = binding['line_range']
excerpt = ''.join(source.decode().splitlines(keepends=True)[start - 1:end])
assert excerpt == binding['exact_excerpt']
assert end - start + 1 == 19 and excerpt.startswith('## B69.')
assert qualification['effective_canonical_finding'] == binding['path'] + '@' + binding['source_sha'] + '#L1749-L1767'

original = qualification['captured_review_object']
assert sha256(blob(BASE, original['path'])) == original['sha256']
assert blob(BASE, original['path']) == blob(HEAD, original['path'])
for handoff, field in [('run-executor.json', 'independent_review'), ('run.json', 'independent_executor_review')]:
    old = json.loads(blob(BASE, PREFIX + handoff))
    new = json.loads(blob(HEAD, PREFIX + handoff))
    assert old[field]['complete_receipt'] == new[field]['complete_receipt']
    pointer = new['canonical_finding_locator_qualification']
    assert pointer['qualification_sha256'] == sha256(qbytes)
    assert pointer['effective_canonical_finding'] == qualification['effective_canonical_finding']
    new.pop('canonical_finding_locator_qualification')
    assert old == new

changed = git('diff', '--name-only', BASE, HEAD).decode().splitlines()
assert set(changed) == {PREFIX + 'run.json', PREFIX + 'run-executor.json', qpath, cpath}
assert not git('diff', BASE, HEAD, '--', PREFIX + 'run-executor-review')
assert not git('diff', BASE, HEAD, '--', 'policy-engine/src', 'policy-engine/tests', 'policy-engine/release-fragments')
out = {
    'schema': 'policyos.e02.B.independent_RUN_locator_audit.v1',
    'base': BASE, 'head': HEAD, 'read_only': True, 'runtime_rerun': False,
    'changed_paths': changed, 'complete_json_count': len(expected), 'package_string_count': len(refs),
    'qualified_historical_bad_fields': bad, 'historical_captured_bytes_preserved': True,
    'canonical_source_sha': binding['source_sha'], 'canonical_path': binding['path'],
    'canonical_git_blob': binding['git_blob'], 'canonical_file_sha256': binding['sha256'],
    'excerpt_line_count': 19, 'excerpt_sha256': sha256(excerpt.encode()),
    'qualification_path': qpath, 'qualification_sha256': sha256(qbytes),
    'census_path': cpath, 'census_sha256': sha256(cbytes),
    'effective_locator': qualification['effective_canonical_finding'],
    'verdict': 'PASS_METADATA_LOCATOR_QUALIFICATION; source/runtime/physical-callback-HOLD unchanged',
}
fp = HERE / 'run-locator-audit.json'
fp.write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'path': str(fp), 'bytes': fp.stat().st_size, 'sha256': sha256(fp.read_bytes()), 'verdict': out['verdict']}))
