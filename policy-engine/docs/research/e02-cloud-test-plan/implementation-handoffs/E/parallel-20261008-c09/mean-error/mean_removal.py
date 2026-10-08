from pathlib import Path
import json,math,resource,sys,time
root=Path('/dev/shm/e02-orch03-20261008/c09/policy-engine');sys.path.insert(0,str(root/'src'))
import pytest
from polisyos.foundry.uncertainty import monte_carlo
original=monte_carlo._mean_estimator_error

def outcome_spread_instead_of_mean_error(values,**kwargs):
    result=original(values,**kwargs)
    if result['standard_error'] is not None:
        result['standard_error']*=math.sqrt(len(values))
    return result

monte_carlo._mean_estimator_error=outcome_spread_instead_of_mean_error
out=Path('/dev/shm/e02-orch03-20261008/c09-scratch')
argv=['-q','tests/unit/foundry/uncertainty/test_mean_estimator_error.py::test_actual_iid_mean_error_matches_independent_fraction_after_fresh_cas_reader',f'--basetemp={out/"mean-removed"}',f'--junitxml={out/"mean-removed.junit.xml"}','-o',f'cache_dir={out/"mean-removed-cache"}']
start=time.monotonic();rc=pytest.main(argv)
meta={'source_sha':'1b8c9e1c84d9f2e86d4b0900bf5aa54515487747','source_tree':'7a4ee9e71c793827abef998540dcd12ab129c4ba','method':'in-process remove sqrt(n) scaling of actual runtime result, retained status/source fields/assumptions/seed/markers and code files unchanged','argv':argv,'pytest_returncode':rc,'expected_returncode':1,'wall_seconds_after_import':time.monotonic()-start,'max_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
(out/'mean-removed.execution.json').write_text(json.dumps(meta,indent=2)+'\n');sys.exit(0 if rc==1 else 2)
