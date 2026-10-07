"""Freeze a bounded independent review; read immutable source and full outputs."""
import hashlib
import json
import pathlib
import subprocess

D = pathlib.Path(__file__).resolve().parent
R = pathlib.Path('/workspace/e02-F-api-20261006')
A = pathlib.Path('/tmp/e02-F-continuation-20261006/api')
SHA = '0c6c7efaab3eba502b44bf6471e7a3c675608f2a'
TREE = '17f9025202b5c94ba78f3e2a3cffdb075404eeea'
PREV = '35b1808c63fa84dd0555ff9043e0aaffe9831e7b'
BASE = '449d32909928caf39382f4ff02ac74b0adf277eb'

def digest(body):
    return hashlib.sha256(body).hexdigest()

def ref(path):
    path = pathlib.Path(path)
    body = path.read_bytes()
    return {'path': str(path), 'bytes': len(body), 'sha256': digest(body), 'full': True}

def git(*args):
    return subprocess.check_output(['git', *args], cwd=R)

def validate_ref(row):
    body = pathlib.Path(row['path']).read_bytes()
    assert len(body) == row['bytes'] and digest(body) == row['sha256']

assert git('rev-parse', 'HEAD').decode().strip() == SHA
assert git('rev-parse', 'HEAD^{tree}').decode().strip() == TREE
assert not git('status', '--porcelain', '--untracked-files=no').decode().strip()
names = ['native101', 'effects-imports', 'root-probe', 'namespace-gate', 'determinism', 'clone-profile']
records = []
for name in names:
    row = json.loads((D / (name + '.json')).read_text())
    assert row['source_sha'] == SHA and row['source_tree'] == TREE
    assert row['source_begin'] == row['source_end']
    assert len(row['source_begin']) == 9
    for source in row['source_begin']:
        body = git('show', SHA + ':' + source['source_path'])
        assert len(body) == source['bytes'] and digest(body) == source['sha256']
        assert body == (R / source['source_path']).read_bytes()
    for output in row['output_refs']:
        validate_ref(output)
    records.append(row)
assert '101 passed, 1 warning' in (D / 'native101.stdout.txt').read_text()
assert '16 passed' in (D / 'effects-imports.stdout.txt').read_text()
assert '3 passed' in (D / 'clone-profile.stdout.txt').read_text()
assert all(row['exit_code'] == 0 for row in records if row['name'] != 'namespace-gate')
assert records[3]['exit_code'] == 1 and records[3]['check'] == 'FAIL'

namespace = json.loads((D / 'namespace-gate.stdout.txt').read_text())
assert namespace['entrypoint_count'] == namespace['unknown_count'] == 38
assert len(namespace['canonical_contract_violations']) == 38
assert namespace['explicit_successful_read_count'] == 103
source_reads = []
for row in namespace['entrypoints']:
    assert row['export_count'] is None and row['known_export_count'] == 0 and not row['complete']
    for source in row['resolution']['inputs']:
        if source['operation'] == 'read_bytes' and source['status'] == 'read':
            body = git('show', SHA + ':policy-engine/' + source['path'])
            assert len(body) == source['bytes'] and digest(body) == source['sha256']
            source_reads.append(source)
policy = namespace['policy_ref']
body = git('show', SHA + ':policy-engine/' + policy['source_path'])
assert len(body) == policy['bytes'] and digest(body) == policy['sha256']
assert namespace['actual_analytics_runtime_count'] == 278
assert namespace['actual_world_runtime_count'] == 59
assert len(namespace['world_declared_unproved_candidates']) == 41

proof = json.loads((D / 'generation-portability-probe.json').read_text())
assert proof['byte_equal'] and not proof['differing_entrypoints']
for process in proof['checks']:
    assert process['source_sha'] == SHA and process['exit_code'] == 0
    for channel in ['stdout', 'stderr']:
        validate_ref(process[channel])
seed1 = pathlib.Path(proof['checks'][0]['stdout']['path'])
seed2 = pathlib.Path(proof['checks'][1]['stdout']['path'])
assert seed1.read_bytes() == seed2.read_bytes()
assert len(seed1.read_bytes()) == 292516
assert digest(seed1.read_bytes()) == '62dd50ac51daf02d53d83b3de69bb4a7516f4ea5fd050b40c5b3ef59af878163'
assert '/workspace/' not in seed1.read_text() and '/tmp/' not in seed1.read_text()
root_probe = json.loads((D / 'root-probe-results.json').read_text())
assert root_probe['source_sha'] == SHA and root_probe['source_tree'] == TREE
assert all(row['state'] == 'UNRESOLVED' for name, row in root_probe['cases'].items() if name != 'supported_literal')
assert root_probe['cases']['supported_literal']['result'] == ['x']

delta_refs = []
for path in git('diff', '--name-only', PREV, SHA).decode().splitlines():
    body = git('show', SHA + ':' + path)
    delta_refs.append({'source_sha': SHA, 'source_path': path, 'bytes': len(body), 'sha256': digest(body)})
assert len(delta_refs) == 3
removal = json.loads((A / 'passive-import-profile-removal.json').read_text())
assert removal['target_sha'] == SHA and removal['tree_sha'] == TREE and removal['exit_code'] == 1
assert removal['source_status_before'] == removal['source_status_after'] == ''
validate_ref(removal['stdout'])
validate_ref(removal['stderr'])
assert '1 failed' in (A / 'passive-import-profile-removal.stdout').read_text()
historical = []
for directory in ['api-review', 'api-review-fd36', 'api-review-35']:
    path = D.with_name(directory)
    old = json.loads((path / 'review.json').read_text())
    if directory == 'api-review':
        assert old['specification_verdict'].startswith('BLOCK')
        historical_sha = old['source_sha']
    else:
        assert old['decision'] == 'BLOCK' and old['check'] == 'FAIL'
        historical_sha = old['candidate_sha']
    historical.append({'role': 'historical_non_deciding', 'source_sha': historical_sha, 'review_ref': ref(path / 'review.json'), 'transfer_selection_ref': ref(path / 'transfer-selection.json'), 'decision_unchanged': 'BLOCK'})

checks = [
    {'name': 'Pinned native selector', 'check': 'PASS', 'outcome': 'limited', 'passed': 101, 'failed': 0, 'skip': 0, 'error': 0, 'warnings': 1, 'output': str(D / 'native101.stdout.txt')},
    {'name': 'Same four implicit effects plus headers/import protocol and unexpected errors', 'check': 'PASS', 'outcome': 'limited', 'passed': 16, 'failed': 0, 'skip': 0, 'error': 0, 'output': str(D / 'effects-imports.stdout.txt'), 'scope': 'e576 prebinding/multiline/descriptor and fd36 baredecorator now typed UNKNOWN; header/default negatives typed UNKNOWN; genuine CPython owner hooks still execute RuntimeShadow while static rejects; pure local binding positive resolves; OSError/SyntaxError/unexpected ValueError/TypeError propagate unchanged.'},
    {'name': 'Original root four effects and literal positive', 'check': 'PASS', 'outcome': 'limited', 'output': str(D / 'root-probe-results.json')},
    {'name': 'Complete canonical selector and immutable Git read-byte binding', 'check': 'PASS', 'outcome': 'limited', 'entrypoints': 38, 'explicit_successful_reads': 103, 'output': str(D / 'namespace-gate.stdout.txt')},
    {'name': 'Actual canonical selected public-surface predicate', 'check': 'FAIL', 'outcome': 'limited', 'incomplete_rows': 38, 'exit_code': 1, 'output': str(D / 'namespace-gate.stdout.txt'), 'scope': 'All 38 rows honestly remain UNKNOWN/incomplete under the selected static grammar. No false empty namespace, full architecture PASS or generated-snapshot freshness claim.'},
    {'name': 'Declared candidates differ from native namespace and proven totals', 'check': 'PASS', 'outcome': 'limited', 'analytics_candidates': 278, 'analytics_native': 278, 'world_candidates': 41, 'world_native': 59, 'proven_known_count': 0, 'total': None, 'complete': False, 'output': str(D / 'namespace-gate.stdout.txt')},
    {'name': 'Two fresh hash seeds complete canonical JSON equality', 'check': 'PASS', 'outcome': 'limited', 'seeds': ['1', '2'], 'full_bytes_each': 292516, 'differing_entrypoints': 0, 'output': str(D / 'generation-portability-probe.json')},
    {'name': 'Relocated scratch literal/import/parent fixtures complete JSON equality', 'check': 'PASS', 'outcome': 'limited', 'passed': 3, 'failed': 0, 'skip': 0, 'error': 0, 'output': str(D / 'clone-profile.stdout.txt'), 'scope': 'Actual two roots per case: supported pure literal binding and passive dependency/parent function refusal; all full JSON bytes and explicit source read hashes compared. No new worktree.'},
    {'name': 'Author memory-only passive-import property removal', 'check': 'FAIL', 'outcome': 'limited', 'failed': 1, 'skip': 0, 'error': 0, 'output': str(A / 'passive-import-profile-removal.stdout'), 'expected': 'property removal produces one actual assertion FAIL', 'role': 'author_execution_independently_inspected_not_rerun', 'scope': 'Temporary passive-module clear preserves actual source/helpers/markers; real CPython hook RuntimeShadow remains while scanner wrongly proves StaticName; finally restores in-memory guard. No product write.'},
    {'name': 'Initial reviewer finalizer historical-field assumption', 'check': 'ERROR', 'outcome': 'limited', 'output': str(D / 'finish-review-initial-error.txt'), 'scope': 'Historical e576 review uses specification_verdict/source_sha, rather than decision/candidate_sha. KeyError occurred after every candidate/Git/output assertion passed, before review write; corrected explicit format handling, no native rerun or product defect.'},
]
report = {
    'reviewer': 'graph_scm', 'role': 'independent_read_only_finite_profile_review', 'check': 'PASS', 'decision': 'GO_bounded_static_profile', 'outcome': 'limited',
    'candidate_sha': SHA, 'candidate_tree': TREE, 'slice_base_sha': BASE, 'delta_predecessor_sha': PREV,
    'scope': 'Finite pure-declaration static resolver and passive local import-owner containment, source binding and deterministic generated bytes. Actual canonical incompleteness is retained as FAIL. No universal Python interpreter, installed ABI, scientific/backend, authority or G acceptance closure.',
    'source_bindings': records[0]['source_begin'], 'delta_source_refs': delta_refs,
    'source_begin_end_check': 'PASS', 'canonical_policy_ref': policy,
    'explicit_source_read_refs': source_reads,
    'findings': [],
    'resolved_prior_review_classes': [
        {'class': 'P40 implicit import-time effects including headers and local import protocol', 'check': 'PASS', 'outcome': 'limited', 'discriminator': 'The same genuine two from-owner hooks still change actual runtime namespace; candidate rejects unproved owner profiles before canonical gate. Missing named owner binding never borrows expression builtin allowance. Literal passive owner/import remains positive.', 'output': str(D / 'effects-imports.stdout.txt')},
        {'class': 'Generated-output deterministic queue and portable source locators', 'check': 'PASS', 'outcome': 'limited', 'discriminator': 'Independent fresh hash seeds produce identical full 38-entrypoint JSON; relocated literal and passive-source fixtures produce identical complete output without absolute root.', 'output': str(D / 'generation-portability-probe.json')},
    ],
    'checks': checks, 'executions': records, 'hash_seed_proof_ref': ref(D / 'generation-portability-probe.json'),
    'hash_seed_process_outputs': [process[channel] for process in proof['checks'] for channel in ['stdout', 'stderr']],
    'author_property_removal': {'execution': removal, 'execution_ref': ref(A / 'passive-import-profile-removal.json'), 'spec_ref': ref(A / 'passive-import-profile-removal-spec.json'), 'replayer_ref': ref(A / 'remove_passive_import_profile.py')},
    'historical_block_reviews': historical,
    'related_finding_ids': ['LA-020', 'LA-007', 'LA-019'], 'closure_ids': [],
    'limits': [
        'All dependency/ancestor callable definitions and all classes, external imports including __future__, control/context and foreign callback/attribute/subscript/operator protocols are outside the selected passive profile and remain UNKNOWN.',
        'Selected-module plain function bodies are excluded, passive headers/defaults are audited; this is a declared finite grammar, not a Python execution proof.',
        'The explicit collector observes only its recorded file-reader operations; Python imports, Git object/ref reads, subprocesses and external services are named unobserved boundaries, not repository absence claims.',
        'Actual HumanDecisionRecord/DDM supported native observations are distinct from UNKNOWN namespace format. Analytics 278 and world declared 41/native 59 do not establish proven export totals.',
        'One cache_dir configuration warning in native101 is retained; baseline DoWhy/EconML markers do not provide a positive backend witness.',
        'Previous e576/fd36/35 BLOCK bytes remain exact historical observations; no old installed/scientific run relabelled on current source.',
        'Full architecture, generated inventory freshness, installed-source migration and G acceptance are UNRUN by this review. No product/source/author receipt or environment mutation.',
    ],
    'author_hold_release': 'All pinned source reads, controlled executions and readback complete. Author may proceed with root-authorized packaging and generation work. This GO does not turn the actual 38 incomplete canonical rows green.',
}
(D / 'review.json').write_text(json.dumps(report, indent=2) + '\n')
files = [D / 'review.json', D / 'finish_review.py', D / 'finish-review-initial-error.txt', D / 'run_check.py', D / 'root-probe-current.py', D / 'root-probe-results.json', D / 'test_implicit_function_effect.py', D / 'test_import_profile_corrected.py', D / 'test_clone_profile.py', D / 'measure_namespace_gate.py', D / 'generation_portability_probe.py', D / 'generation-portability-probe.json']
for name in names:
    files.extend([D / (name + '.json'), D / (name + '.stdout.txt'), D / (name + '.stderr.txt')])
files.extend([seed1, pathlib.Path(proof['checks'][0]['stderr']['path'])])
files.extend([A / 'passive-import-profile-removal.json', A / 'passive-import-profile-removal-spec.json', A / 'passive-import-profile-removal.stdout', A / 'passive-import-profile-removal.stderr', A / 'remove_passive_import_profile.py'])
assert len(files) == len(set(files))
aliases = []
for channel in ['stdout', 'stderr']:
    original = proof['checks'][1][channel]
    target = proof['checks'][0][channel]
    assert pathlib.Path(original['path']).read_bytes() == pathlib.Path(target['path']).read_bytes()
    aliases.append({'original_ref': original, 'transport_ref': target, 'reason': 'Independent measured byte equality; retain one full stored body, not a truncated or summarized output.'})
selection = {'source_sha': SHA, 'source_tree': TREE, 'check': 'PASS', 'decision': 'GO_bounded_static_profile', 'unique_full_files': len(files), 'items': [ref(path) for path in files], 'lossless_identical_output_aliases': aliases, 'historical_selections_separately_preserved': [item['transfer_selection_ref'] for item in historical]}
selection['full_bytes'] = sum(item['bytes'] for item in selection['items'])
(D / 'transfer-selection.json').write_text(json.dumps(selection, indent=2) + '\n')
print(json.dumps({'review': ref(D / 'review.json'), 'selection': ref(D / 'transfer-selection.json'), 'files': len(files), 'bytes': selection['full_bytes'], 'source': SHA, 'tree': TREE, 'bounded_check': 'PASS', 'actual_canonical_predicate': 'FAIL', 'incomplete_rows': 38}))
