"""Independent canonical reader identity, actual fresh consumer and removal control."""
from pathlib import Path
from types import SimpleNamespace
import hashlib, importlib, json, os, runpy, subprocess, sys
import numpy as np
from polisyos import calibration as facade
from polisyos.core.artifacts import FileSystemCAS, PutOptions, SchemaInfo
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.core.contracts.foundry import SimulationResult
from polisyos.ir.analytics.uncertainty import PosteriorSamplesCarrier, load_uncertainty_envelope
from polisyos.scientist.nodes.builtins.state_keys import ARTIFACT_PROPAGATION_REPORT_REF, ARTIFACT_SIMULATION_RESULT_REF
from polisyos.scientist.nodes.builtins.simulate import propagate_uncertainty as node
from polisyos.foundry.uncertainty import PropagationDispatcher

R=Path('/workspace/e02-E-continuation-20261006');S=R/'policy-engine/src';O=Path(__file__).parent;REF='43c443b6f1015d57cf624598531ef99c22a296e6'
property_paths=['policy-engine/src/polisyos/calibration/__init__.py','policy-engine/src/polisyos/scientist/nodes/builtins/simulate/propagate_uncertainty.py','policy-engine/src/polisyos/foundry/calibration/report.py','policy-engine/tests/unit/scientist/nodes/test_calibration_report_consumer.py','policy-engine/tests/unit/calibration/test_evidence_facades.py']
before={}
for p in property_paths:
    expected=subprocess.check_output(['git','show',REF+':'+p],cwd=R)
    assert (R/p).read_bytes()==expected
    before[p]=hashlib.sha256(expected).hexdigest()
owner=importlib.import_module('polisyos.foundry.calibration.report')
assert facade.load_foundry_calibration_report is owner.load_calibration_report is node.load_foundry_calibration_report
assert 'load_foundry_calibration_report' in facade.__all__ and len(facade.__all__)==29
assert not hasattr(facade, 'CalibrationReport')
assert owner.CalibrationReport.__module__ == 'polisyos.foundry.calibration.report'
mutant=os.environ.get('REMOVE_FOUNDRY_READER_ADMISSION')=='1'
if mutant:
    def unsafe_reader(store,ref):
        return CalibrationReport.model_validate(from_canonical_bytes(store.get_bytes(ref.artifact_id)))
    owner.load_calibration_report.__code__=unsafe_reader.__code__
    assert facade.load_foundry_calibration_report is owner.load_calibration_report is node.load_foundry_calibration_report

helper=runpy.run_path('tests/unit/scientist/nodes/test_calibration_report_consumer.py')
base=O/('cas-reader-removed' if mutant else 'cas-reader-positive')
results=[]
for label,kind,schema,version in [('wrong-kind','funnel.calibration_report','polisyos.foundry.CalibrationReport','2.0'),('wrong-schema','foundry.calibration_report','polisyos.foundry.FunnelCalibrationReport','2.0'),('wrong-payload-version','foundry.calibration_report','polisyos.foundry.CalibrationReport','1.0')]:
    store,report,inputs,valid=helper['_fixture'](base/label)
    forged=store.put_json(report,PutOptions(kind=kind,media_type='application/json',schema=SchemaInfo(name=schema,version=version),inputs=inputs),canon_spec=CanonSpec(forbid_floats=False,exclude_none=False))
    assert forged.artifact_id==valid.artifact_id
    fresh=FileSystemCAS(store.root);ctx,state=helper['_node_fixture'](fresh,forged,{'A.rate':1.0})
    callback_count=[0];dispatch_count=[0]
    original_build=node._build_propagation_fn;original_dispatch=PropagationDispatcher.propagate
    def counted_build(*args,**kwargs):
        fn,mapped=original_build(*args,**kwargs)
        def counted(**params):
            callback_count[0]+=1
            return fn(**params)
        counted._sensitivity_map=fn._sensitivity_map
        return counted,mapped
    def counted_dispatch(*args,**kwargs):
        dispatch_count[0]+=1
        return original_dispatch(*args,**kwargs)
    node._build_propagation_fn=counted_build;PropagationDispatcher.propagate=counted_dispatch
    try:
        try:
            outcome=node.PropagateUncertaintyNode().execute(ctx,state)
        except ValueError as exc:
            error=str(exc);outcome=None
        else:
            error=None
    finally:
        node._build_propagation_fn=original_build;PropagationDispatcher.propagate=original_dispatch
    result={'fixture':label,'same_payload_artifact_id':str(valid.artifact_id),'different_manifest_profile':valid.manifest_profile_sha256!=forged.manifest_profile_sha256,'kind':kind,'schema':schema,'manifest_version':version,'callback_count':callback_count[0],'dispatch_count':dispatch_count[0],'refusal':error,'outcome':None if outcome is None else outcome.status,'removed_admission':mutant}
    print(json.dumps(result),flush=True)
    results.append(result)
    assert callback_count[0]==dispatch_count[0]==0 and error is not None, 'canonical export retained but stripped reader admission reached actual consumer callbacks'

# One real configured Calibrator producer proves the alias reaches the persisted joint law.
tied=runpy.run_path('tests/unit/scientist/nodes/builtins/simulate/test_propagate_welfare.py')
store=FileSystemCAS(base/'real-tied-calibrator')
report_ref,report=tied['_run_b197_tied_calibrator'](store)
fresh=FileSystemCAS(store.root);read_report=facade.load_foundry_calibration_report(fresh,report_ref)
assert read_report.schema_version=='2.0' and set(read_report.uncertainty_envelopes)=={'A.rate','B.rate'}
ctx,state=helper['_node_fixture'](fresh,report_ref,{'A.rate':1.0,'B.rate':-1.0})
outcome=node.PropagateUncertaintyNode().execute(ctx,state);assert outcome.status=='ok'
fresh_again=FileSystemCAS(store.root)
sim=SimulationResult.model_validate(from_canonical_bytes(fresh_again.get_bytes(outcome.state.artifacts_index[ARTIFACT_SIMULATION_RESULT_REF].artifact_id)))
envelope=load_uncertainty_envelope(fresh_again,sim.uncertainty_envelopes['y'])
assert isinstance(envelope.distribution_payload,PosteriorSamplesCarrier) and not envelope.gate_eligible
samples=np.asarray(envelope.distribution_payload.samples)
# Independent algebra: the two calibrated rate coordinates share one draw, so A-B is zero.
assert len(samples)==100 and np.max(np.abs(samples))<1e-12
receipt=from_canonical_bytes(fresh_again.get_bytes(outcome.state.artifacts_index[ARTIFACT_PROPAGATION_REPORT_REF].artifact_id))
assert receipt['mapped_params']==['A.rate','B.rate']
positive={'producer':'actual Calibrator tied parameter projection','persisted_report_ref':report_ref.model_dump(mode='json'),'fresh_read_schema_version':read_report.schema_version,'consumer':'PropagateUncertaintyNode.execute','outcome':outcome.status,'output_ref':sim.uncertainty_envelopes['y'].model_dump(mode='json'),'joint_draw_oracle':'A and B use shared coordinate; A-B=0 for every draw','sample_count':len(samples),'maximum_abs_contrast':float(np.max(np.abs(samples))),'gate_eligible':False}
modules=[]
for name,module in sorted(sys.modules.items()):
    if name.startswith('polisyos.') and getattr(module,'__file__',None):
        path=Path(module.__file__).resolve();assert path.is_relative_to(S)
        rel='policy-engine/src/'+str(path.relative_to(S));expected=subprocess.check_output(['git','show',REF+':'+rel],cwd=R)
        assert path.read_bytes()==expected
        modules.append({'module':name,'path':rel,'sha256':hashlib.sha256(expected).hexdigest()})
for p,h in before.items():assert hashlib.sha256((R/p).read_bytes()).hexdigest()==h
result={'source_sha':REF,'source_tree':subprocess.check_output(['git','rev-parse',REF+'^{tree}'],cwd=R,text=True).strip(),'property_paths':before,'source_before_after_equal':True,'canonical_identity':True,'calibration_exports':29,'distinct_Foundry_and_Funnel_reports':True,'negatives':results,'positive':positive,'actual_import_modules':len(modules),'module_origins':modules,'verdict':'GO-bounded-canonical-reader-alias-and-actual-consumer','limitations':'Content/kind/schema integrity does not establish source fit/served evaluator authority; B197 remains held in committed ledger.'}
(O/'calibration-reader-independent.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:result[k] for k in ['source_sha','source_tree','source_before_after_equal','canonical_identity','calibration_exports','negatives','positive','actual_import_modules','verdict','limitations']},indent=2))
