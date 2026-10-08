from dataclasses import replace
import json
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.scientist.methods.search.funnel.orchestrator import FunnelOrchestrator
from polisyos.scientist.methods.search.funnel.types import FunnelStage,FunnelStageResult
class Stage(FunnelStage):
    stage_name='review-selected-view'
    fidelity_level=0
    estimated_cost_usd=0.0
    def __init__(self):self.calls=0
    def evaluate(self,candidate,context):
        self.calls+=1
        return FunnelStageResult(policy_candidate=candidate,objective_value=float(self.calls),is_promising=True,stage_name=self.stage_name,fidelity_level=0)
basis_a=ArtifactRef(artifact_id='sha256:'+'a'*64,kind='scientist.search.uncertainty_basis',media_type='application/json',manifest_profile_sha256='sha256:'+'1'*64)
basis_b=basis_a.model_copy(update={'manifest_profile_sha256':'sha256:'+'2'*64})
stage=Stage();runtime=FunnelOrchestrator([stage]);candidate={'id':'review-selected-view'}
first=runtime.submit(candidate,{'uncertainty_basis_ref':basis_a});first_outcome=runtime.advance(first)
second=runtime.submit(candidate,{'uncertainty_basis_ref':basis_b});second_outcome=runtime.advance(second)
print(json.dumps({'qualification':'Actual mocked callback on public real orchestrator/cache; refs are synthetically valid shapes, no real CAS or scientific authority established','selected_refs_differ':basis_a!=basis_b,'artifact_ids_equal':basis_a.artifact_id==basis_b.artifact_id,'reused_ticket':first is second,'calls':stage.calls,'first_score':first_outcome.final_result.objective_value,'second_score':second_outcome.final_result.objective_value,'retained_basis':second.context['uncertainty_basis_ref'].model_dump(mode='json')},indent=2))
assert first is not second and stage.calls==2,'Changed selected view was collapsed into the old terminal ticket'
