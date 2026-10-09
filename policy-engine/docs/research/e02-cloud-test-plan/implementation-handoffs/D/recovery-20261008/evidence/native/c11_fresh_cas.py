"""Independent synthetic CAS fixture; real configured funnel in a fresh reader.

No persisted-ticket restoration, native producer, numerical GP or refinement-law claim.
"""
import argparse,dataclasses,datetime,json,pathlib
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS,PutOptions
from polisyos.ir import UncertaintyType
from polisyos.scientist.methods.search.funnel.orchestrator import FunnelOrchestrator
from polisyos.scientist.methods.search.funnel.types import FunnelStage,FunnelStageResult
from polisyos.scientist.methods.search.uncertainty import SearchUncertaintyBasis,SearchUncertaintyObservation,UncertaintyEnvelope,UncertaintyEstimate,persist_search_uncertainty
p=argparse.ArgumentParser();p.add_argument('mode',choices=['produce','read']);p.add_argument('--packet',required=True);p.add_argument('--cas',required=True);p.add_argument('--case',default='valid',choices=['valid','foreign','substituted','missing']);a=p.parse_args();packet=pathlib.Path(a.packet);store=FileSystemCAS(pathlib.Path(a.cas))
def envelope(value):return UncertaintyEnvelope.from_partial({k:UncertaintyEstimate(level=value,source='independent synthetic supplied observation',quantification_method='fixture',is_reducible=True) for k in UncertaintyType})
if a.mode=='produce':
 def ref(name):return store.put_json({'fixture':name},PutOptions(kind='scientist.independent_fixture',media_type='application/json'))
 basis=SearchUncertaintyBasis(subject_ref=ref('candidate'),value_ref=ref('value'),input_refs=(ref('input'),),rule_ref=ref('rule'),producer_ref=ref('producer'),valid_time=datetime.datetime(2026,10,8,tzinfo=datetime.timezone.utc),estimand='fixture ATE',unit='kg')
 basis_ref=persist_search_uncertainty(store,basis)
 foreign_ref=persist_search_uncertainty(store,basis.model_copy(update={'unit':'USD'}))
 refs=[persist_search_uncertainty(store,SearchUncertaintyObservation(basis_ref=basis_ref,producer_ref=basis.producer_ref,risk_ref=ref(f'risk-{i}'),envelope=envelope(v))) for i,v in enumerate([0.9,0.1])]
 payload={'basis':basis.model_dump(mode='json'),'basis_ref':basis_ref.model_dump(mode='json'),'foreign_basis_ref':foreign_ref.model_dump(mode='json'),'observation_refs':[r.model_dump(mode='json') for r in refs]};packet.write_text(json.dumps(payload,indent=2)+'\n');print(json.dumps({'case':'produce','basis_ref':str(basis_ref.artifact_id),'observations':[str(r.artifact_id) for r in refs]}))
else:
 payload=json.loads(packet.read_text());basis=SearchUncertaintyBasis.model_validate(payload['basis']);basis_ref=ArtifactRef.model_validate(payload['basis_ref']);foreign=ArtifactRef.model_validate(payload['foreign_basis_ref']);refs=[ArtifactRef.model_validate(x) for x in payload['observation_refs']]
 class Stage(FunnelStage):
  def __init__(self,level,ref,value):self.level,self.ref,self.value,self.calls=level,ref,value,0
  @property
  def stage_name(self):return f'independent-fixture-L{self.level}'
  @property
  def fidelity_level(self):return self.level
  @property
  def estimated_cost_usd(self):return 0.0
  def evaluate(self,candidate,context):
   self.calls+=1;return FunnelStageResult(policy_candidate=candidate,objective_value=1.0,is_promising=True,stage_name=self.stage_name,fidelity_level=self.level,uncertainty_envelope=envelope(self.value),uncertainty_observation_ref=self.ref)
 stages=[Stage(0,refs[0],0.9),Stage(1,refs[1],0.1)]
 if a.case=='missing':stages[1].ref=None
 if a.case=='substituted':stages[1].value=0.001
 runtime=FunnelOrchestrator(stages);context={'store':store,'uncertainty_basis_ref':foreign if a.case=='foreign' else basis_ref,'policy_candidate_ref':basis.subject_ref};outcome=runtime.advance(runtime.submit({'independent':'candidate'},context))
 current=outcome.current_uncertainty_envelope;history=outcome.uncertainty_envelope
 assert [s.calls for s in stages]==[1,1]
 assert all(x.level==0.9 for x in history.uncertainties.values())
 if a.case=='valid':
  assert current is not None
  assert all(x.level==0.9 for x in current.uncertainties.values())
  assert len(outcome.uncertainty_observation_refs)==2
  assert outcome.uncertainty_intake_failures==[]
  assert outcome.final_result.feedback['uncertainty_refinement_status']=='producer_law_not_established'
 else:
  assert current is None
  assert outcome.uncertainty_intake_failures
 print(json.dumps({'case':a.case,'current':None if current is None else current.model_dump(mode='json'),'history':history.model_dump(mode='json'),'failures':outcome.uncertainty_intake_failures,'calls':[s.calls for s in stages]}))
