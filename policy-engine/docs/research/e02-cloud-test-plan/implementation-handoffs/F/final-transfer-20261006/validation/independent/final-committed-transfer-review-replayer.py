"""Exact committed F transfer review; only own ignored scratch output is written."""
from __future__ import annotations
import argparse
import copy
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from datetime import datetime, timezone

REPO = Path('/workspace/e02-F-closeout-20261006')
PREFIX = 'policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/F/final-transfer-20261006/'
SCRATCH = Path('/workspace/e02-F-20261006-receipts/cau')
parser = argparse.ArgumentParser()
parser.add_argument('--candidate', required=True)
parser.add_argument('--case')
args = parser.parse_args()
real_check_output = subprocess.check_output

def git(*argv):
    return real_check_output(['git', '-C', str(REPO), *argv])

def read(path):
    return git('show', args.candidate + ':' + path)

def digest(raw):
    return hashlib.sha256(raw).hexdigest()

def ref(path):
    raw = Path(path).read_bytes()
    return {'path': str(path), 'bytes': len(raw), 'sha256': digest(raw)}

index_raw = read(PREFIX + 'index.json')
transport_raw = read(PREFIX + 'artifact-transports.json')
verifier_raw = read(PREFIX + 'verify_transfer.py')
index = json.loads(index_raw)
transport = json.loads(transport_raw)

if args.case:
    changed_index = copy.deepcopy(index)
    changed_transport = copy.deepcopy(transport)
    mutations = {}
    if args.case == 'missing_component':
        changed_index['topics'][0]['components'].pop()
    elif args.case == 'wrong_owner':
        wrong = next(r for r in changed_index['finding_rows'] if r['finding_id'] == 'B212')
        target = next(r for r in changed_index['finding_rows'] if r['finding_id'] == 'B204')
        target['receipt_ref'] = copy.deepcopy(wrong['receipt_ref'])
    elif args.case == 'stale_transport_hash':
        changed_transport['files'][0]['sha256'] = '0' * 64
    elif args.case == 'coherent_open':
        target = next(r for r in changed_index['finding_rows'] if r['finding_id'] == 'B204')
        target['outcome'] = 'open'
        states = ['closed', 'limited', 'held', 'open']
        changed_index['summary']['outcome_counts'] = {s: sum(r['outcome'] == s for r in changed_index['finding_rows']) for s in states}
        changed_index['summary']['outcome_counts'] = {k: v for k, v in changed_index['summary']['outcome_counts'].items() if v}
    elif args.case == 'coherent_pending':
        pending_path = PREFIX + 'audit/final35-inputs/pending-scientific-blockers.json'
        pending = json.loads(read(pending_path))
        pending['status'] = 'freeze_blocked'
        pending['items'][0]['resolution_check'] = 'UNRUN'
        pending['items'][0]['resolution_receipt_head'] = None
        raw = (json.dumps(pending, ensure_ascii=False, indent=2) + '\n').encode()
        mutations[args.candidate + ':' + pending_path] = raw
        target = next(t for t in changed_transport['files'] if t['path'] == pending_path)
        target['bytes'] = len(raw)
        target['sha256'] = digest(raw)
    elif args.case == 'swapped_source_cards':
        left = next(r for r in changed_index['finding_rows'] if r['finding_id'] == 'B212')
        right = next(r for r in changed_index['finding_rows'] if r['finding_id'] == 'B213')
        left['original_source_criterion_refs'], right['original_source_criterion_refs'] = right['original_source_criterion_refs'], left['original_source_criterion_refs']
    elif args.case != 'native':
        raise ValueError(args.case)
    if args.case != 'native':
        mutations[args.candidate + ':' + PREFIX + 'index.json'] = (json.dumps(changed_index, ensure_ascii=False, indent=2) + '\n').encode()
        mutations[args.candidate + ':' + PREFIX + 'artifact-transports.json'] = (json.dumps(changed_transport, ensure_ascii=False, indent=2) + '\n').encode()

    def readonly_git_interception(command, *extra, **kwargs):
        if isinstance(command, (list, tuple)) and len(command) >= 5 and command[0] == 'git' and command[3] == 'show' and command[4] in mutations:
            raw = mutations[command[4]]
            return raw.decode(kwargs.get('encoding') or 'utf8') if kwargs.get('text') or kwargs.get('universal_newlines') else raw
        return real_check_output(command, *extra, **kwargs)

    subprocess.check_output = readonly_git_interception
    sys.argv = [str(REPO / (PREFIX + 'verify_transfer.py')), '--candidate', args.candidate]
    namespace = {'__name__': '__main__', '__file__': str(REPO / (PREFIX + 'verify_transfer.py'))}
    # Exact verifier bytecode is unchanged; only specified frozen JSON reads are varied.
    exec(compile(verifier_raw, namespace['__file__'], 'exec'), namespace)
    raise SystemExit(0)

expected_ids = {'B54', 'B56', *(f'B{i}' for i in range(204, 226)), 'LA-001', 'LA-002', 'LA-003', 'LA-004', 'LA-007', 'LA-016', 'LA-017', 'LA-019', 'LA-020', 'LA-035', 'LA-037'}
rows = index['finding_rows']
assert len(rows) == 35 and {r['finding_id'] for r in rows} == expected_ids
assert len({r['primary_bundle'] for r in rows}) == 17
assert index['summary']['outcome_counts'] == {'closed': 17, 'limited': 16, 'held': 2}
assert index['G_integration']['main_authorized'] is False
assert index['P41']['predicate_basis'] == 'not_established'
assert len(index['topics']) == 12
components = [c for t in index['topics'] for c in t['components']]
assert len(components) == len(index['receipt_registry']) == 15
assert len({t['branch'] for t in index['topics']}) == 12
assert {(r['head'], r['receipt_path']) for r in index['receipt_registry']} == {(c['receipt']['git_ref'], c['receipt']['path']) for c in components}
card_refs = []
for row in rows:
    assert row['outcome'] != 'open'
    assert row['actual_consumer'] and row['criterion_short_ru'] and row['limit_next_owner_short_ru']
    assert 'GiniPureExecutor' not in row['actual_consumer']
    if row['finding_id'] == 'LA-001': assert 'compile_plan' not in row['actual_consumer']
    for source in row['original_source_criterion_refs']:
        raw = git('show', source['source_sha'] + ':' + source['source_path'])
        a, b = source['lines']
        block = b''.join(raw.splitlines(keepends=True)[a - 1:b])
        assert source['criterion_id'] == row['finding_id']
        assert block.decode().splitlines()[0].startswith('## ' + row['finding_id'] + '.')
        assert len(block) == source['bytes'] and digest(block) == source['sha256']
        card_refs.append(source)
assert len(card_refs) == 36
assert len({(r['source_sha'], r['source_path'], tuple(r['lines']), r['sha256']) for r in card_refs}) == 35
protocol_ref = index['complete_input_and_audit_refs']['protocol']
protocol_raw = read(protocol_ref['path'])
assert len(protocol_raw) == protocol_ref['bytes'] and digest(protocol_raw) == protocol_ref['sha256']
if protocol_ref.get('content_encoding') == 'gzip':
    protocol_raw = gzip.decompress(protocol_raw)
    assert len(protocol_raw) == protocol_ref['decoded_bytes'] and digest(protocol_raw) == protocol_ref['decoded_sha256']
protocol = json.loads(protocol_raw)
assert protocol['current_deciding_reference_check'] == 'PASS' and not protocol['current_deciding_issues']
assert protocol['check'] == protocol['historical_non_deciding_reference_check'] == 'UNRUN'
assert len(transport['files']) == len({f['original_path'] for f in transport['files']})
for f in transport['files']:
    raw = git('show', f['git_ref'] + ':' + f['path']) if 'git_ref' in f else read(f['path'])
    assert len(raw) == f['bytes'] and digest(raw) == f['sha256']

cases = ['native', 'missing_component', 'wrong_owner', 'stale_transport_hash', 'coherent_open', 'coherent_pending', 'swapped_source_cards']
running = []
start = time.time()
for name in cases:
    stdout = SCRATCH / ('final-committed-transfer-review-' + name + '.stdout')
    stderr = SCRATCH / ('final-committed-transfer-review-' + name + '.stderr')
    so, se = stdout.open('wb'), stderr.open('wb')
    command = [sys.executable, str(Path(__file__)), '--candidate', args.candidate, '--case', name]
    launched = time.time()
    process = subprocess.Popen(command, stdout=so, stderr=se, env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
    running.append((name, process, so, se, stdout, stderr, command, launched))
checks = []
issues = []
for name, process, so, se, stdout, stderr, command, launched in running:
    rc = process.wait()
    so.close(); se.close()
    expected_rejection = name != 'native'
    valid = (rc == 0) if not expected_rejection else (rc == 1 and 'AssertionError' in stderr.read_text() and 'CalledProcessError' not in stderr.read_text() and 'KeyError' not in stderr.read_text())
    check = {'name': name, 'command': command, 'cwd': str(REPO), 'process_exit_code': rc,
        'wall_seconds_observed_until_wait': time.time() - launched, 'check': 'PASS' if valid else 'FAIL',
        'expected_property_rejection': expected_rejection, 'stdout': ref(stdout), 'stderr': ref(stderr),
        'verifier_source_sha256': digest(verifier_raw), 'scientific_backend_executions': 0}
    checks.append(check)
    if not valid: issues.append({'case': name, 'issue': 'Canonical guard failed to reject altered property or verifier/harness did not execute', 'check': check})
native = json.loads((SCRATCH / 'final-committed-transfer-review-native.stdout').read_text()) if checks[0]['check'] == 'PASS' else None
report = {'schema': 'policyos.e02.F.independent_committed_transfer_review.v1', 'reviewer': 'F/cau independent direct leaf',
    'utc': datetime.now(timezone.utc).isoformat(), 'candidate_sha': args.candidate,
    'candidate_tree': git('rev-parse', args.candidate + '^{tree}').decode().strip(), 'check': 'FAIL' if issues else 'PASS',
    'outcome': 'limited', 'scope': 'Exact committed doc-only transfer, source/owner/card/transport fidelity and actual metadata admission guards; no scientific reruns or G ledger acceptance',
    'denominator': {'findings': 35, 'bundles': 17, 'topics': 12, 'receipt_components': 15, 'finding_bearing_components': 14,
        'ancillary_components': 1, 'source_card_bindings': 36, 'unique_original_blocks': 35, 'full_byte_transports': len(transport['files'])},
    'input_blobs': [{'path': PREFIX + p, 'bytes': len(b), 'sha256': digest(b), 'git_ref': args.candidate} for p, b in [('index.json', index_raw), ('artifact-transports.json', transport_raw), ('verify_transfer.py', verifier_raw)]],
    'row_states': [{k: row[k] for k in ['finding_id', 'primary_bundle', 'implementation_sha', 'candidate_tree_sha', 'check', 'outcome', 'actual_consumer', 'limit_next_owner_short_ru', 'receipt_ref']} for row in rows],
    'component_source_and_receipt_heads': components, 'source_card_refs': card_refs,
    'whole_reference_custody_check': protocol['check'], 'historical_non_deciding_reference_check': protocol['historical_non_deciding_reference_check'],
    'current_deciding_reference_check': protocol['current_deciding_reference_check'],
    'historical_qualification': 'Unavailable historical175c blob is provenance-only: overall custody UNRUN; current deciding refs PASS is a separately measured property, not blanket custody PASS.',
    'native_verifier': native, 'checks': checks, 'issues': issues,
    'limits': ['17 closed are F original-criterion technical recommendations;16limited/2held and formal G integration/ledger pending remain.',
        'Known synthetic DGP/graph/backend profiles do not establish admitted real-data assumptions, current-law/economic authority or a composed G runtime.',
        'P41 not_established and recorded whole gates FAIL/ERROR/SKIP/UNRUN remain explicit. No main/ledger/source changes.'],
    'environment': {'python': sys.version, 'executable': sys.executable, 'dependencies': 'stdlib only', 'PYTHONDONTWRITEBYTECODE': '1', 'thread_cpu_quotas': 'none'},
    'full_oracle': ref(Path(__file__)), 'wall_seconds': time.time() - start, 'production_or_ledger_writes': 0}
output = SCRATCH / 'final-committed-transfer-review.json'
output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'check': report['check'], 'candidate_sha': args.candidate, 'denominator': report['denominator'],
    'current_deciding_reference_check': protocol['current_deciding_reference_check'], 'all_reference_custody_check': protocol['check'], 'output': ref(output)}, ensure_ascii=False))
raise SystemExit(1 if issues else 0)
