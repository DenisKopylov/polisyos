import json, os, resource, subprocess, time
from pathlib import Path
scratch=Path('/dev/shm/e02-orch03-20261008/c07-checks')
root=scratch/'retained-marker-source804'
base='policy-engine/tests/unit/ir/test_value_subject_relation.py'
cmd=['/workspace/e02-F-closeout-20261006/policy-engine/.venv/bin/python','-m','pytest',base+'::test_resolved_quantity_mismatch_refuses_despite_matching_metadata',base+'::test_complete_producer_roster_refuses_missing_extra_duplicate[extra]',base+'::test_persisted_fresh_child_preserves_separate_asymmetric_channels','-q','-ra','--junitxml='+str(scratch/'retained-marker.junit.xml'),'--basetemp='+str(scratch/'retained-marker-tmp')]
env=dict(os.environ);env['PYTHONPATH']=str(root/'policy-engine/src')+':'+str(root/'policy-engine')
start=time.time();clock=time.perf_counter()
with (scratch/'retained-marker.stdout').open('wb') as out,(scratch/'retained-marker.stderr').open('wb') as err:
    result=subprocess.run(cmd,cwd=root,env=env,stdout=out,stderr=err,check=False)
record={'source_sha':'804a6aba31125372b0b57a10041c6d6aad375ad5','source_tree':'bb1e30be80e5238ebd903ba327fa6dc4ac27c2b2','command':cmd,'cwd':str(root),'PYTHONPATH':env['PYTHONPATH'],'started_unix':start,'wall_seconds':time.perf_counter()-clock,'maxrss_children_kib':resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,'returncode':result.returncode,'result_policy':'Expected negative-control FAIL; not unexpected product failures. One unchanged same-unit positive remains. Exact 9 FAIL / 1 PASS required.'}
(scratch/'retained-marker.json').write_text(json.dumps(record,indent=2,sort_keys=True)+'\n')
print(json.dumps(record))
