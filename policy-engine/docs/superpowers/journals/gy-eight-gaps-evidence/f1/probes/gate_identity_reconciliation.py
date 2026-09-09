"""Complete finding-identity delta; an aborted report is explicitly not an empty set."""
import hashlib
import json
from pathlib import Path

root = Path.cwd() / '_build/gy-gaps/f1'
paths = {'baseline': root / 'canonical-check-final.json',
         'corruption': root / 'gate-committed-corruption.json',
         'execution_removal': root / 'gate-execution-removal.json'}
receipts = {key: json.loads(path.read_text()) for key, path in paths.items()}
reports = {key: json.loads(receipts[key]['stdout']) for key in ('baseline', 'corruption')}
assert receipts['baseline']['returncode'] == 0 and reports['baseline']['status'] == 'pass'
assert receipts['corruption']['returncode'] == 1 and reports['corruption']['status'] == 'fail'
identities = {key: {json.dumps(issue, sort_keys=True, separators=(',', ':'))
                    for issue in report['issues']} for key, report in reports.items()}
assert all(len(identities[key]) == len(report['issues']) for key, report in reports.items())
added = identities['corruption'] - identities['baseline']
lost = identities['baseline'] - identities['corruption']
assert not lost
assert added == {json.dumps({'code': 'layer3_workflow_failure_authority_drift',
                            'path': 'architecture/policy_design_case/layer3_gy_workflow_failure_authority_proofs_v2.json'},
                           sort_keys=True, separators=(',', ':'))}
removal = receipts['execution_removal']
assert removal['returncode'] == 1 and not removal['timed_out']
assert removal['stderr'].strip().endswith('ValueError: workflow_report_execution_not_established')
try:
    json.loads(removal['stdout'])
except json.JSONDecodeError:
    removal_report_available = False
else:
    removal_report_available = True
assert not removal_report_available
print(json.dumps({
    'receipt_sources': {key: {'path': str(path.relative_to(Path.cwd())),
                             'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
                        for key, path in paths.items()},
    'finding_identity_fields': 'complete issue objects, absence preserved',
    'baseline_complete_identities': [json.loads(value) for value in sorted(identities['baseline'])],
    'corruption_added_identities': [json.loads(value) for value in sorted(added)],
    'corruption_lost_identities': [json.loads(value) for value in sorted(lost)],
    'execution_removal': {
        'finding_report_available': False,
        'finding_set_comparison': 'not_available; abort is not an empty finding set',
        'terminal_exception': 'ValueError: workflow_report_execution_not_established',
        'property_result': 'real gate cannot emit proof when actual execution is removed',
    },
}, sort_keys=True))
