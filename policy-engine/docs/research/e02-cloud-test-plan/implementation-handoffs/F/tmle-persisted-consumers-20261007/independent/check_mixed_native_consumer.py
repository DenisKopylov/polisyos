"""Independent mixed-ref inputs for the persisted native TMLE consumer boundary."""
from __future__ import annotations
import functools,hashlib,inspect,json,runpy,sys
from dataclasses import replace
from pathlib import Path
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.governance.passes.base import IssueSeverity,PassContext
from polisyos.core.governance.profiles import ValidationProfile
from polisyos.ir.analytics.causal import EstimationStatus,load_causal_effect_report
from polisyos.ir.registry.refs import CausalEffectReportRef
from polisyos.ir.analytics.uncertainty import load_uncertainty_envelope
from polisyos.scientist.governance.passes.confidence_pass import ConfidencePass
SOURCE=Path('/workspace/e02-F-tmle-20261006/policy-engine/tests/unit/scientist/governance/test_tmle_persisted_evidence_consumers.py')
packet=json.loads(Path(sys.argv[1]).read_text());mode=sys.argv[2]
assert Path(inspect.getfile(ConfidencePass)).resolve().is_relative_to(Path('/workspace/e02-F-tmle-20261006/policy-engine/src'))
# First traverse the author's genuine bundle/report/value consumer, in this fresh process.
read=runpy.run_path(str(SOURCE))['_read']
base={**packet,'relabelled':True,'causal_location':'index','simulation_kind':'healthy','simulation_location':'index','min_ratio':0.0}
base_observation=read(base)
store=FileSystemCAS(Path(packet['cas_root']))
report_ref=CausalEffectReportRef.model_validate(packet['report_ref'])
report=load_causal_effect_report(store,report_ref)
bundle=from_canonical_bytes(store.get_bytes(ArtifactRef.model_validate(packet['bundle_ref'])))
assert report.model_dump(mode='json')==bundle['report']
assert report.status is EstimationStatus.SUCCESS and report.confidence_interval
original_report=report.model_dump(mode='json')
profile=replace(ValidationProfile.strict(),thresholds={'uncertainty_min_gate_eligible_ratio':0.0,'uncertainty_max_ci_width_ratio':1e12,'uncertainty_max_ci_width_abs':1e12})
healthy=ArtifactRef.model_validate(packet['simulation_refs']['healthy'])
corrupt=ArtifactRef.model_validate(packet['simulation_refs']['corrupt'])
forged=ArtifactRef.model_validate(packet['forged_ref'])
assert load_uncertainty_envelope(store,forged).gate_eligible is True
if mode=='malformed_top':
 state={'_store':store,'artifacts_index':{'causal_envelope_ref':forged},'simulation_result_ref':'not-an-artifact-ref'}
elif mode in {'mixed_priority','remove_role_issue'}:
 state={'_store':store,'artifacts_index':{'causal_envelope_ref':forged,'simulation_result_ref':corrupt},'simulation_result_ref':healthy}
else:raise AssertionError(mode)
def context(s):return PassContext(ir=None,state=s,registry_bundle=None,profile=profile,run_id='independent-native-tmle')
original=ConfidencePass.validate
markers=lambda f:{'name':f.__name__,'qualname':f.__qualname__,'module':f.__module__,'doc':f.__doc__,'signature':str(inspect.signature(f))}
marker_before=markers(original)
actual=original(ConfidencePass(),context(state))
if mode=='remove_role_issue':
 @functools.wraps(original)
 def drop_role(self,ctx):
  issues=original(self,ctx)
  return [i for i in issues if not(i.code=='CONFIDENCE_GATE_ELIGIBILITY_LOW' and i.path==['artifacts_index','causal_envelope_ref'])]
 ConfidencePass.validate=drop_role
 assert markers(ConfidencePass.validate)==marker_before
observed=ConfidencePass().validate(context(state)) if mode=='remove_role_issue' else actual
payload=[i.model_dump(mode='json') for i in observed]
blockers=[i for i in observed if i.severity is IssueSeverity.BLOCKER and i.code=='CONFIDENCE_GATE_ELIGIBILITY_LOW' and i.path==['artifacts_index','causal_envelope_ref']]
print(json.dumps({'mode':mode,'report_id':str(report_ref.artifact_id),'native_status':report.status.value,'native_point':report.point_estimate,'native_ci':report.confidence_interval,'actual_pre_removal_issues':[i.model_dump(mode='json') for i in actual],'observed_issues':payload,'causal_blocker_count':len(blockers),'marker_preserved':markers(ConfidencePass.validate)==marker_before,'value_refusal':base_observation['value_refusal'],'confidence_origin':inspect.getfile(ConfidencePass)},sort_keys=True),flush=True)
assert report.model_dump(mode='json')==original_report
assert len(blockers)==1,payload
if mode=='mixed_priority':
 assert any(i.code=='CONFIDENCE_SIM_RESULT_LOAD_FAILED' for i in observed),payload
elif mode=='malformed_top':
 assert not any(i.code=='CONFIDENCE_SIM_RESULT_LOAD_FAILED' for i in observed),payload
# Healthy supported noncausal intake is a control, not scientific admission.
noncausal=ConfidencePass().validate(context({'_store':store,'artifacts_index':{'simulation_result_ref':healthy}}))
assert not noncausal,[i.model_dump(mode='json') for i in noncausal]
print(json.dumps({'noncausal_healthy_control_issues':0,'mode':mode}),flush=True)
