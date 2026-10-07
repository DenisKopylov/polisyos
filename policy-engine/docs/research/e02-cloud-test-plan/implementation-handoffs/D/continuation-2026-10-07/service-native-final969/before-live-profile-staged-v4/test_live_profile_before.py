"""Independent actual staged-v4 live-profile falsifiers, not authority appointment."""
from copy import deepcopy
from pathlib import Path
import importlib.util,json,hashlib,sys
import pytest
from polisyos.scientist.methods.autotune.dedup import TrialDeduplicator
from polisyos.scientist.methods.search.service import _decode_checkpoint
p=Path('/dev/shm/e02-D-B124-independent-tests/v4/test_service_trial_deduplication.py')
spec=importlib.util.spec_from_file_location('_immutable_B124_v4_fixture',p)
f=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=f
spec.loader.exec_module(f)
@pytest.mark.parametrize('change',['evaluator_scale','nested_context'])
def test_actual_live_profile_change_refuses_before_duplicate_skip(tmp_path,change):
 runner,store,_,suite,evaluator,loop=f._runner(tmp_path,promotable=False)
 service=runner.create_service(loop,suite_ref=suite,max_iterations=4,dedup=TrialDeduplicator())
 context={'offset':0,'caller_scope':{'split':'original'}}
 first=service.ask(None,None,context)[0]
 measurement=service.controller._evaluate_for_tell(first.payload,iteration=0,context=context)
 service.tell(first.candidate_id,measurement)
 oldref=service.checkpoint_ref
 oldbytes=store.get_verified_snapshot(oldref).data
 oldconfig=_decode_checkpoint(oldbytes)['configuration']
 before=deepcopy(service.controller._generator.get_state())
 if change=='evaluator_scale': evaluator.scale=2
 else: context['caller_scope']['split']='changed'
 currentconfig=service._configuration(context)
 assert currentconfig != oldconfig, 'falsifier must actually change persisted input profile'
 print('LIVE_PROFILE_BEFORE:'+json.dumps({'change':change,'old_reference':oldref.model_dump(mode='json'),'old_bytes_sha256':hashlib.sha256(oldbytes).hexdigest(),'old_config':oldconfig,'current_config':currentconfig,'generator_before':before,'calls_before':evaluator.calls},sort_keys=True))
 refused=False
 proposals=None
 try:
  proposals=service.ask(None,None,context)
 except ValueError:
  refused=True
 print('LIVE_PROFILE_AFTER:'+json.dumps({'change':change,'refused':refused,'returned_proposals':None if proposals is None else [x.model_dump(mode='json') for x in proposals],'generator_after':service.controller._generator.get_state(),'calls_after':evaluator.calls,'current_checkpoint':service.checkpoint_ref.model_dump(mode='json')},sort_keys=True))
 assert refused, 'changed actual live profile must refuse before treating old completed CAS as a current duplicate'
 assert service.controller._generator.get_state()==before
 assert f._values(evaluator)==[1]
