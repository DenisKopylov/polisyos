"""Read-only narrow appendix review; no main payload decode or scientific run."""
import collections
import gzip
import hashlib
import json
import pathlib
import subprocess
import sys
import time

START = time.monotonic()
REPO = pathlib.Path('/workspace/e02-F-closeout-20261006')
PREFIX = 'policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/F'
PACKAGE = PREFIX + '/continuation-closeout-20261007'
OLD = pathlib.Path('/tmp/e02-F-continuation-20261007/foundry/root-final-transport-review')
SOURCE = 'cbfc2647b63b7b43e608532abb2159d3785bab42'
MAIN = 'b300da2e134a67fbd6f585a21ab42286c356fe7e'


def bind(path):
    raw = pathlib.Path(path).read_bytes()
    return {'path': str(path), 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def json_body(path):
    return json.loads(pathlib.Path(path).read_bytes())


def git(*args):
    run = subprocess.run(['git', '-C', str(REPO), *args], capture_output=True)
    assert run.returncode == 0, (args, run.stderr.decode())
    return run.stdout


primary_path = PREFIX + '/continuation-closeout-reviewed-20261007.json'
manifest_path = PACKAGE + '/independent-materialized-review/outputs.json'
readme_path = PACKAGE + '/README.md'
primary = json_body(REPO / primary_path)
manifest = json_body(REPO / manifest_path)
readme = (REPO / readme_path).read_text()
assert bind(REPO / primary_path)['sha256'] == '9c5abb2e07cfca8ecf1e838502ca0c1e4a4569a5d57b81ae69013d6d42ae2a90'
assert bind(REPO / manifest_path)['sha256'] == 'cf7cec25040f6b8c982eea4cede2ea95c293072795e7e0d14e25f38b57438637'
assert manifest['schema'] == 'policyos.e02.independent_materialized_review_transport.v1'
assert manifest['source_sha'] == SOURCE and manifest['main_receipt'] == MAIN
assert manifest['source_tree'] == git('rev-parse', SOURCE + '^{tree}').decode().strip()

stored_bindings = []
by_original = {}
path_set = set()
for row in manifest['files']:
    relative = pathlib.PurePosixPath(row['path'])
    assert not relative.is_absolute() and '..' not in relative.parts
    assert row['path'].startswith(PACKAGE + '/independent-materialized-review/companions/')
    assert row['path'] not in path_set and row['original_path'] not in by_original
    path_set.add(row['path'])
    raw = (REPO / row['path']).read_bytes()
    assert len(raw) == row['bytes'] and hashlib.sha256(raw).hexdigest() == row['sha256']
    assert row['encoding'] in ('identity', 'gzip')
    decoded = gzip.decompress(raw) if row['encoding'] == 'gzip' else raw
    assert len(decoded) == row['decoded_bytes'] and hashlib.sha256(decoded).hexdigest() == row['decoded_sha256']
    original = pathlib.Path(row['original_path']).read_bytes()
    assert original == decoded, row['original_path']
    by_original[row['original_path']] = row
    stored_bindings.append({'path': row['path'], 'encoding': row['encoding'], 'bytes': len(raw),
        'sha256': hashlib.sha256(raw).hexdigest(), 'decoded_bytes': len(decoded),
        'decoded_sha256': hashlib.sha256(decoded).hexdigest(), 'original_path': row['original_path'],
        'actual_original_byte_equality': True})
actual_counts = {'files': len(stored_bindings), 'stored_bytes': sum(x['bytes'] for x in stored_bindings),
                 'decoded_bytes': sum(x['decoded_bytes'] for x in stored_bindings)}
assert manifest['counts'] == actual_counts == {'files': 53, 'stored_bytes': 1750566, 'decoded_bytes': 1750566}

selection = json_body(OLD / 'transfer-selection.json')
assert selection['frozen'] is True and len(selection['files']) == 21
for row in selection['files']:
    actual = by_original[row['path']]
    assert (actual['decoded_bytes'], actual['decoded_sha256']) == (row['bytes'], row['sha256'])
assert str(OLD / 'transfer-selection.json') in by_original
frozen_review = json_body(OLD / 'review.json')
assert primary['summary'] == frozen_review['summary']
assert primary['historical_harness_errors'] == frozen_review['historical_harness_attempts']
assert primary['independent_review'] == by_original[str(OLD / 'review.json')]
assert primary['F_finding_recommendation'] == primary['F_technical_original_recommendation'] == {'closed': 33, 'limited': 2}
assert primary['finding_checks'] == {'PASS': 34, 'UNRUN': 1}
assert primary['summary']['primary_typed_command_kinds'] == {'argv_or_recorded_command_sequence': 11,
    'pinned_or_prose_string': 4, 'bounded_UNRUN_null': 4}
assert primary['formal_G_closures'] == 0 and primary['formal_G_acceptance'] == 'not issued'
assert primary['closure_ids'] == [] and primary['changed_paths'] == [] and primary['implementation_commits'] == []
assert primary['evidence_only'] is True and primary['own_future_receipt_SHA_not_asserted'] is True
assert primary['main_or_integration_written'] is False and primary['history_rewritten'] is False
assert primary['production_data_uploaded'] is False and primary['cleanup_actions_recovery'] == []
assert primary['candidate_sha'] == primary['slice_base_sha'] == SOURCE
for role in ('product_source', 'ledger_implementation', 'main_materialized_receipt', 'late_materialized_receipt', 'fresh_G_dependency'):
    row = primary[role]
    assert git('cat-file', '-t', row['sha']).strip() == b'commit'
    assert git('rev-parse', row['sha'] + '^{tree}').decode().strip() == row['tree']
assert primary['checks'][0]['outcome'] == 'PASS'
negative = primary['checks'][1]
assert negative['outcome'] == 'FAIL' and negative['expected'] is True and negative['harness_result'] == 'PASS'
assert 'aggregate actual CLI exit0' in negative['negative_mechanism']
assert 'no fabricated subprocess exit1' in negative['negative_mechanism']
controls = json_body(OLD / 'negative-control-inputs.json')
assert controls['aggregate_cli_exit_code'] == 0 and controls['separate_control_process_exit_codes'] is None
assert len(controls['controls']) == 4
assert all(x['actual_outcome'] == 'FAIL' and x['expected_refusal'] == 'PASS' for x in controls['controls'])
assert len(primary['historical_harness_errors']) == 2
assert all(x['canonical_outcome'] == 'ERROR' and x['raw_process_exit_code'] == 1 for x in primary['historical_harness_errors'])
for phrase in ('four in-process', 'canonical harness ERROR', '33 closed / 2 limited', '34 PASS / 1 UNRUN',
               'formal G closures 0', 'No sdist-child', 'P41 not_established', 'do not confer operational or scientific authority'):
    assert phrase in readme, phrase

unchanged_paths = [PREFIX + '/continuation-closeout-20261007.json', PACKAGE + '/artifact-transports.json',
    PREFIX + '/continuation-transfer-20261007/index.json', PREFIX + '/continuation-transfer-20261007/full-audit.json']
index = json_body(REPO / unchanged_paths[2])
unchanged_paths += [x['path'] for x in index['per_ID_complete_records']]
unchanged = []
for path in unchanged_paths:
    raw = (REPO / path).read_bytes()
    old = git('show', SOURCE + ':' + path)
    assert raw == old
    unchanged.append({'path': path, 'git_ref': SOURCE, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest(),
                      'actual_worktree_byte_equal_to_frozen_Git': True})

result = {'schema': 'e02.F.independent.final_appendix_review.v1', 'outcome': 'PASS', 'decision': 'GO',
    'scope': 'Read-only precommit appendix review only; no repeated 233MB main payload decode, runtime or science.',
    'source_sha': SOURCE, 'source_tree': manifest['source_tree'], 'main_receipt_sha': MAIN,
    'appendix_primary': bind(REPO / primary_path), 'outputs_manifest': bind(REPO / manifest_path),
    'package_README': bind(REPO / readme_path), 'all_stored_decoded_original_bindings': stored_bindings,
    'actual_counts': actual_counts, 'own_frozen_21_inputs_transported': True,
    'own_frozen_selection_transported': True, 'main_and_35_small_metadata_paths_unchanged': unchanged,
    'statement_audit': {'actual_typed_commands': '11 list /4 string /4 bounded UNRUN null',
        'historical_harness_errors': 'two actual CLI exit1, canonical ERROR, exact script/config/stream bytes retained',
        'negative_controls': 'four actual caught in-process Invalid exceptions, aggregate CLI exit0, separate control process exitcodes not observed',
        'F_axes': 'both33closed/2limited', 'original_check_states': '34PASS/1UNRUN', 'formal_G_closures': 0,
        'future_own_receipt_SHA': 'not asserted', 'authority_or_G_acceptance': 'not inferred'},
    'review_command': [sys.executable, str(pathlib.Path(__file__).resolve())], 'cwd': str(pathlib.Path.cwd()),
    'environment': {'Python': sys.version.split()[0], 'product_imports': False, 'scope': 'stdlib and read-only Git'},
    'wall_seconds': time.monotonic() - START, 'product_or_root_mutations': False,
    'limitations': ['Precommit worktree appendix bytes, publication/readback remains ROOT action.',
        'Recorded scientific outcomes and original35 recommendations are preserved, not independently rerun/re-adjudicated.',
        'G admission, full operational/statistical authority and B56 admitted workload remain unissued or unavailable.']}
print(json.dumps(result, ensure_ascii=False, indent=2))
