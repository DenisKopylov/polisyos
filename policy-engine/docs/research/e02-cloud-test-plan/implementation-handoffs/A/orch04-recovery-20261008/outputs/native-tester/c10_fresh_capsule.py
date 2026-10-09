"""Fresh-process reader on the committed mirrored producer's exact synthetic packet.

No real served GET/browser or protected-action authority claim.
"""
import argparse,json,pathlib
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.runtime.quality.cycle_substrate import CycleSubstrateContextArtifactOwner,ConfiguredCandidateSimulationContextAdmissionOwner
from polisyos.runtime.quality.recursive_generation_cycle import RecursiveLeafContextCapsule,RecursiveLeafContextOwner
from tests.unit.runtime.quality.test_cycle_substrate import _TestCurrentJobExecutionOwner,_authenticated_tenant_scope
p=argparse.ArgumentParser();p.add_argument('mode',choices=['produce','read']);p.add_argument('--packet',required=True);p.add_argument('--fixture-root',required=True);a=p.parse_args();packet=pathlib.Path(a.packet);fixture=pathlib.Path(a.fixture_root)
if a.mode=='produce':
 from tests.unit.runtime.quality.test_recursive_generation_cycle_epoch_gate import test_recursive_child_capsule_resolves_complete_owned_inputs_and_refuses_transplants
 original=RecursiveLeafContextOwner.persist
 def record(self,capsule):
  ref=original(self,capsule)
  packet.write_text(json.dumps({'capsule_ref':ref.model_dump(mode='json'),'capsule':capsule.model_dump(mode='json')},indent=2)+'\n')
  return ref
 RecursiveLeafContextOwner.persist=record
 try:test_recursive_child_capsule_resolves_complete_owned_inputs_and_refuses_transplants(fixture)
 finally:RecursiveLeafContextOwner.persist=original
 assert packet.exists();print(json.dumps({'case':'producer','synthetic_packet':str(packet),'cas_root':str(fixture/'child-cas')}))
else:
 data=json.loads(packet.read_text());capsule=RecursiveLeafContextCapsule.model_validate(data['capsule']);ref=ArtifactRef.model_validate(data['capsule_ref']);h=capsule.handoff
 store=FileSystemCAS(fixture/'child-cas');job_owner=_TestCurrentJobExecutionOwner(h.job_id,h.run_id)
 context_owner=CycleSubstrateContextArtifactOwner(store=store,control_store=job_owner)
 admission=ConfiguredCandidateSimulationContextAdmissionOwner(profiles=(h.profile,),store=store)
 owner=RecursiveLeafContextOwner(store=store,context_owner=context_owner,admission_owner=admission)
 kwargs={'node_ref':capsule.node_ref,'parent_ref':capsule.parent_ref,'problem':capsule.problem,'expected_job_id':h.job_id,'expected_run_id':h.run_id,'expected_tenant_id':h.tenant_id,'expected_cell_id':h.cell_id}
 with _authenticated_tenant_scope(tenant_id=h.tenant_id,cell_id=h.cell_id):
  actual=owner.read(ref,**kwargs);assert actual==capsule;owner.require_current(actual)
  try:owner.read(ref,**{**kwargs,'node_ref':'design://independent-foreign-child'})
  except ValueError as ex:assert 'reader_binding_mismatch' in str(ex);print(json.dumps({'case':'foreign_child','refusal':str(ex)}))
  else:raise AssertionError('foreign child admitted')
  job_owner.record.job_id='independent-changed-current-job'
  try:owner.require_current(capsule)
  except ValueError as ex:assert 'job_binding_mismatch' in str(ex);print(json.dumps({'case':'changed_current_job','refusal':str(ex)}))
  else:raise AssertionError('stale job current')
  historical=owner.read(ref,**kwargs);assert historical==capsule
 print(json.dumps({'case':'fresh_reader','capsule_ref':str(ref.artifact_id),'purpose':actual.authority_purpose,'historical_packet_retained':True,'complete_problem_hash':actual.handoff.context.design_problem_ref}))
