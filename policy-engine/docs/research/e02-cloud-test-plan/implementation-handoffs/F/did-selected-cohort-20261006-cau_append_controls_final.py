import hashlib
import json
import subprocess
from pathlib import Path

from polisyos.foundry.methods.catalog.causal.did import DifferenceInDifferences

def poison(*args, **kwargs):
    raise AssertionError('Historical aggregate adapter called')

DifferenceInDifferences.pure_step = poison
from benchmarks.interference import policy_did_interference as interference
from benchmarks.natural_experiments import policy_natural_experiments as natural

records=[]
for module,factory,key in [(interference,'_case_clean_policy_rollout','artifact'),(interference,'_case_contaminated_rollout','artifact'),(natural,'_case_clean_rollout','report'),(natural,'_case_placebo_null','report'),(natural,'_case_staggered_adoption','report')]:
    case=getattr(module,factory)()
    payload=case.runner()
    report=payload[key]
    rejected=None
    try:
        checker=case.checker(payload)
    except AssertionError as exc:
        checker=False
        rejected=str(exc)
    status=report.diagnostics[0].details.get('status') if report.diagnostics else None
    passed=report.diagnostics[0].passed if report.diagnostics else None
    if factory=='_case_clean_rollout':
        assert status=='not_testable' and passed is False and checker is False
        assert 'parallel-trends diagnostic' in rejected
    else:
        assert checker is True,(factory,rejected)
    records.append({'caller':module.__name__+'.'+factory,'status':report.status.value,'point_estimate':report.point_estimate,'diagnostic_status':status,'diagnostic_passed':passed,'checker_passed':checker,'checker_failure':rejected,'interpretation':'Expected descriptive not_testable boundary; original benchmark requires passed. DGP and checker unchanged.' if factory=='_case_clean_rollout' else 'Actual maintained native caller and checker pass with historical adapter poisoned.'})
root=Path.cwd()
before='c7d33a223e467964c589f61c8b097eb9175335c5'
candidate='cebe94d8134a4652bbfc1ae4d74ec6403940ced5'
for p in ['policy-engine/src/polisyos/foundry/methods/catalog/causal/did.py']:
    assert subprocess.check_output(['git','show',before+':'+p])==subprocess.check_output(['git','show',candidate+':'+p])
print(json.dumps({'source_sha':candidate,'control':'Historical adapter raises if invoked; actual unchanged native benchmark DGP/runner/checker consumed','native_cases':records,'numerical_source_bytes':'unchanged from reviewed c7d33a2; selected test now separately measures alternative coverage'},indent=2))
