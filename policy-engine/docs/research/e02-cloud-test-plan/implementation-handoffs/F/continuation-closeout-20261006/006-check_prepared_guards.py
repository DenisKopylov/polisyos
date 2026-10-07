"""Independent bounded guard execution on actual selected Git inputs; not final packet acceptance."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent
CHECKER = Path('/tmp/e02-F-continuation-20261006/cau/final35-validator/validate_packet.py')
MANIFEST = Path('/tmp/e02-F-continuation-20261006/cau/original35-reconciliation.json')
spec = importlib.util.spec_from_file_location('independent_packet_checker', CHECKER)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
manifest = json.loads(MANIFEST.read_bytes())
required = json.loads((OUT / 'required-registry-prepared.json').read_bytes())
REPO = '/workspace/e02-F-closeout-20261006'

def validator():
    return module.Validator(REPO, manifest, required)

def index_from_required():
    return {'receipt_registry': [
        {'head': r['head'], 'receipt_path': r['path'], 'receipt_bytes': r['bytes'],
         'receipt_sha256': r['sha256'], 'implementation_sha': r['implementation_sha'],
         'candidate_tree_sha': r['candidate_tree_sha']} for r in required],
        'topics': [{'components': [{'receipt': {'git_ref': r['head'], 'path': r['path']}}]}
                   for r in required]}

records = []
base = index_from_required()
v = validator()
v.registry(base)
assert not v.issues, v.issues
records.append({'name': 'actual35-selected-Git-custody-positive', 'guard_check': 'PASS',
                'expected': 'PASS', 'issues': v.issues, 'observations': v.observations,
                'complete_current_refs': v.current_refs})

mutant = copy.deepcopy(base)
removed = mutant['receipt_registry'].pop()
mutant['topics'].pop()
v = validator()
v.registry(mutant)
assert any(i['kind'] == 'MISSING_REQUIRED_COMPONENT' for i in v.issues)
assert not any(i['kind'] == 'REGISTRY_BIJECTION' for i in v.issues)
records.append({'name': 'remove-component-and-corresponding-topic-keep-bijection',
                'guard_check': 'FAIL', 'expected': 'FAIL', 'removed_component': removed,
                'issues': v.issues, 'observations': v.observations})

mutant = copy.deepcopy(base)
mutant['receipt_registry'][0]['receipt_sha256'] = '0' * 64
v = validator()
v.registry(mutant)
assert {'ARTIFACT_BYTES', 'REQUIRED_COMPONENT_BINDING'}.issubset({i['kind'] for i in v.issues})
records.append({'name': 'wrong-content-hash-with-ref-markers-retained', 'guard_check': 'FAIL',
                'expected': 'FAIL', 'issues': v.issues, 'observations': v.observations})

mutant = copy.deepcopy(base)
mutant['receipt_registry'][0]['candidate_tree_sha'] = '0' * 40
v = validator()
v.registry(mutant)
assert any(i['kind'] == 'CODE_TREE' for i in v.issues)
records.append({'name': 'wrong-code-tree-with-source-markers-retained', 'guard_check': 'FAIL',
                'expected': 'FAIL', 'issues': v.issues, 'observations': v.observations})

# Real compressed navigation/infrastructure streams remain ancillary. Their
# decoded custody is exercised; no estimator/backend authority is inferred.
storage = next(r for r in required if r['path'].endswith('continuation-inputs-and-storage-20261006.json'))
v = validator()
receipt = json.loads(v.git_bytes(storage['head'], storage['path']))
streams = [{**c['output'], 'git_ref': storage['head']} for c in receipt['checks']
           if c['output']['path'].endswith('.gz')]
assert len(streams) == 3
v.material({'files': streams}, storage['head'])
assert not v.issues, v.issues
records.append({'name': 'actual3-gzip-encoded-and-decoded-custody', 'guard_check': 'PASS',
                'expected': 'PASS', 'issues': v.issues, 'observations': v.observations,
                'complete_current_refs': v.current_refs})
corrupted = copy.deepcopy(streams)
corrupted[0]['decoded_sha256'] = '0' * 64
v = validator()
v.material({'files': corrupted}, storage['head'])
assert any(i['kind'] == 'DECODED_TRANSPORT_BYTES' for i in v.issues)
records.append({'name': 'wrong-decoded-hash-keep-stored-bytes-and-markers', 'guard_check': 'FAIL',
                'expected': 'FAIL', 'issues': v.issues, 'observations': v.observations})

result = {'schema': 'F-independent-prepared-metadata-guards/1', 'check': 'PASS',
          'role': 'Actual selected immutable input/guard preparation only; no final index read or acceptance.',
          'guard_cases': records, 'case_count': len(records),
          'expected_PASS': sum(r['expected'] == 'PASS' for r in records),
          'expected_FAIL': sum(r['expected'] == 'FAIL' for r in records),
          'checker': {'path': str(CHECKER), 'bytes': CHECKER.stat().st_size,
                      'sha256': hashlib.sha256(CHECKER.read_bytes()).hexdigest()},
          'required_registry_ref': {'path': str(OUT / 'required-registry-prepared.json'),
                                   'sha256': hashlib.sha256((OUT / 'required-registry-prepared.json').read_bytes()).hexdigest()},
          'limitations': ['Final packet validation UNRUN until ROOT freezes its publication.',
                          'Three gzip outputs are input custody, not scientific backend measurements.']}
(OUT / 'prepared-guard-review.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result, indent=2))
