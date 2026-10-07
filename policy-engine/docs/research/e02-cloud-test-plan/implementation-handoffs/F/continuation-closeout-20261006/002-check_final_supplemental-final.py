"""Read-only final packet schema, source-order and retained-marker metadata controls."""
from __future__ import annotations

import collections
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import jsonschema

TASK_ROOT = Path(__file__).resolve().parent
RUN = TASK_ROOT / 'f17b9a52784d9484ef65563dc6695240629bdfc6'
REPO = '/workspace/e02-F-closeout-20261006'
VPATH = Path('/tmp/e02-F-continuation-20261006/cau/final35-validator/validate_packet.py')
SCHEMA = Path('/tmp/e02-F-continuation-20261006/cau/final35-validator/root-adjudication.schema.json')
spec = importlib.util.spec_from_file_location('frozen_final_validator', VPATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
manifest = module.load_json(TASK_ROOT.parent.parent / 'cau/original35-reconciliation.json')
required = module.load_json(TASK_ROOT / 'required-registry-final.json')
index = module.load_json(RUN / 'immutable-index.json')
source = module.load_json(RUN / 'immutable-source-order.json')
transport = module.load_json(RUN / 'immutable-transports.json')
adjudication = module.load_json(RUN / 'immutable-root-adjudication.json')
issues = []
checks = []


def sha(body):
    return hashlib.sha256(body).hexdigest()


def git(*args):
    return subprocess.check_output(['git', '-C', REPO, *args])


def check(name, condition, detail=None):
    checks.append({'property': name, 'check': 'PASS' if condition else 'FAIL', 'detail': detail})
    if not condition:
        issues.append({'property': name, 'detail': detail})


def validator():
    return module.Validator(REPO, manifest, required)


def metadata_control(name, value, operation, expected):
    v = validator()
    operation(v, value)
    kinds = [i['kind'] for i in v.issues]
    check(name, expected in kinds, {'actual_guard_check': 'FAIL' if kinds else 'PASS',
                                   'expected_issue': expected, 'actual_issues': v.issues,
                                   'source_and_receipt_markers_preserved': True})


check('frozen_validator_hash', sha(VPATH.read_bytes()) == '51a95464831e426050bc9aac6abc0ed094a871c01d5634a8a021972acf0d9e1f')
check('frozen_schema_hash', sha(SCHEMA.read_bytes()) == '20d762000f692f2865972c45dd6953acf30ac41248a9154faae244dd2590a815')
schema = json.loads(SCHEMA.read_bytes())
errors = list(jsonschema.Draft202012Validator(schema).iter_errors(adjudication))
check('actual_committed_ROOT_adjudication_strict_schema', not errors,
      [dict(path=list(e.path), message=e.message) for e in errors])

shortened = copy.deepcopy(index)
removed = shortened['receipt_registry'].pop()
key = (removed['head'], removed['receipt_path'])
for topic in shortened['topics']:
    topic['components'] = [c for c in topic['components']
                           if (c['receipt'].get('git_ref'), c['receipt'].get('path')) != key]
metadata_control('actual_final_coherent_component_and_topic_omission', shortened,
                 lambda v, j: v.registry(j), 'MISSING_REQUIRED_COMPONENT')

wrong_tree = copy.deepcopy(index)
wrong_tree['receipt_registry'][0]['candidate_tree_sha'] = '0' * 40
metadata_control('actual_final_scientific_tree_corruption', wrong_tree,
                 lambda v, j: v.registry(j), 'CODE_TREE')

false_authority = copy.deepcopy(index)
false_authority['authority'] = {'formal_G_ledger_accepted': True}
metadata_control('actual_final_self_issued_G_acceptance', false_authority,
                 lambda v, j: v.custody(j), 'FORMAL_ACCEPTANCE')

false_budget = copy.deepcopy(index)
for row in false_budget['finding_rows']:
    if row['finding_id'] == 'B56':
        row['check'] = 'PASS'
        row['outcome'] = 'closed'
metadata_control('actual_final_missing_B56_admission_marked_closed', false_budget,
                 lambda v, j: v.rows(j), 'B56_SHARED_BUDGET')

records = transport.get('files', transport.get('items', []))
encoded = next(r for r in records if r.get('decoded_sha256') and r.get('decoded_bytes', 0) > 0
               and r['path'].endswith('.gz'))
damaged = copy.deepcopy(encoded)
damaged['decoded_sha256'] = '0' * 64
metadata_control('actual_final_decoded_hash_corruption_stored_bytes_unchanged', {'files': [damaged]},
                 lambda v, j: v.material(j, 'f17b9a52784d9484ef65563dc6695240629bdfc6'),
                 'DECODED_TRANSPORT_BYTES')

history = source['complete_root_topological_append_history']
actual_order = git('rev-list', '--topo-order', '--reverse', source['base_sha'] + '..' + source['root_sha']).decode().splitlines()
check('complete_current_append_history_exact_order', [r['sha'] for r in history] == actual_order,
      {'declared_commits': len(history), 'actual_commits': len(actual_order)})
history_errors = []


def check_commit(record):
    body = git('cat-file', 'commit', record['sha'])
    header, message = body.split(b'\n\n', 1)
    lines = header.decode().splitlines()
    tree = next(s[5:] for s in lines if s.startswith('tree '))
    parents = [s[7:] for s in lines if s.startswith('parent ')]
    if record.get('tree') != tree or record.get('parents') != parents:
        history_errors.append({'sha': record['sha'], 'problem': 'tree/parents'})
    if 'full_message' in record and record['full_message'] != message.decode():
        history_errors.append({'sha': record['sha'], 'problem': 'full_message'})


for record in history + source['transfer_carrier_history_through_adjudication']:
    check_commit(record)
check('all_current_and_transfer_commit_metadata', not history_errors,
      {'records': len(history) + len(source['transfer_carrier_history_through_adjudication']),
       'errors': history_errors})

binding_errors = []
binding_refs = []
cache = {}


def walk(value, where='source_order'):
    if isinstance(value, dict):
        ref = value.get('git_ref', value.get('head', value.get('source_sha')))
        if isinstance(ref, str) and len(ref) == 40 and value.get('path') and 'bytes' in value and 'sha256' in value:
            key = (ref, value['path'])
            try:
                body = cache.setdefault(key, git('show', ref + ':' + value['path'])) if key not in cache else cache[key]
                valid = len(body) == value['bytes'] and sha(body) == value['sha256']
                if not valid:
                    binding_errors.append({'where': where, 'ref': ref, 'path': value['path'], 'problem': 'bytes/hash'})
                binding_refs.append({'where': where, 'git_ref': ref, 'path': value['path'], 'check': 'PASS' if valid else 'FAIL'})
            except subprocess.CalledProcessError as error:
                binding_errors.append({'where': where, 'problem': repr(error)})
        for key, child in value.items():
            walk(child, where + '/' + str(key))
    elif isinstance(value, list):
        for number, child in enumerate(value):
            walk(child, where + '/' + str(number))


walk(source)
check('source_order_all_explicit_full_byte_refs', not binding_errors,
      {'occurrences': len(binding_refs), 'distinct': len(cache), 'errors': binding_errors})
lineage_errors = []
path_bindings = 0
for record in source['implementation_source_bindings']:
    tree = git('rev-parse', record['source_sha'] + '^{tree}').decode().strip()
    ancestor = subprocess.run(['git', '-C', REPO, 'merge-base', '--is-ancestor', record['source_sha'], source['root_sha']], capture_output=True).returncode
    if tree != record['source_tree'] or ancestor not in (0, 1) or record['root_ancestry']['is_ancestor'] != (ancestor == 0):
        lineage_errors.append({'sha': record['source_sha'], 'problem': 'tree/ancestry'})
    for bound in record['full_defining_commit_path_bindings']:
        left, right = bound['source_ref'], bound['root_ref']
        equal = bool(left and right and left['bytes'] == right['bytes'] and left['sha256'] == right['sha256'])
        for ref, state in [(record['source_sha'], left), (source['root_sha'], right)]:
            if state is None:
                exists = subprocess.run(['git', '-C', REPO, 'cat-file', '-e', ref + ':' + bound['path']], capture_output=True).returncode == 0
                if exists:
                    lineage_errors.append({'sha': ref, 'path': bound['path'], 'problem': 'null ref despite existing file'})
        if bound['bytes_equal'] != equal:
            lineage_errors.append({'sha': record['source_sha'], 'path': bound['path'], 'problem': 'bytes_equal flag'})
        path_bindings += 1
    for upstream in record.get('upstream_complete_history_if_not_ancestor', []):
        if isinstance(upstream, str):
            actual = git('show', '-s', '--format=%H %P %T %s', upstream.split()[0]).decode().strip()
            if actual != upstream:
                history_errors.append({'sha': upstream.split()[0], 'problem': 'upstream full log line'})
        else:
            check_commit(upstream)
check('implementation_bindings_tree_ancestry_vs_byte_equality', not lineage_errors and not history_errors,
      {'implementations': len(source['implementation_source_bindings']), 'path_pairs': path_bindings,
       'errors': lineage_errors + history_errors})

per_id = index['current_per_ID_receipts']
check('all_current_per_ID_receipts_are_tracked', len(per_id) == 35,
      {'receipts': len(per_id)})
check('current_deciding_vs_historical_custody_scope',
      index['current_deciding_reference_check'] == 'PASS' and
      index['historical_non_deciding_reference_check'] == 'UNRUN' and
      index['all_reference_custody_check'] == 'UNRUN' and
      index['zero_finding_deciding_dependence_on_missing_historical175c_and_lint_raw'] is True)

result = {'check': 'FAIL' if issues else 'PASS', 'scope': 'read-only schema/source-order/metadata guard review',
          'checks': checks, 'issues': issues, 'source_order_ref_bindings': binding_refs,
          'transport_arithmetic': {'stored_records': len(records), 'stored_bytes': sum(r['bytes'] for r in records),
                                  'decoded_records': sum('decoded_sha256' in r for r in records),
                                  'decoded_bytes': sum(r.get('decoded_bytes', 0) for r in records)},
          'no_scientific_or_backend_execution': True}
output = RUN / 'supplemental-checks-final.json'
output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'check': result['check'], 'checks': len(checks), 'issues': issues, 'output': str(output)}, ensure_ascii=False))
raise SystemExit(0 if not issues else 1)
