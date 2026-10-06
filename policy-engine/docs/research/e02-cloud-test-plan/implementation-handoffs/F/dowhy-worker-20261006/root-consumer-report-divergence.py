"""Independent real-job probe; no production evaluation authority is asserted."""
import hashlib,importlib.util,json,logging,os
from pathlib import Path
from polisyos.core.artifacts.store import FileSystemCAS,PutOptions
from polisyos.core.canon import CanonSpec,from_canonical_bytes
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.compute.job_spec import JobSpec
from polisyos.ir.analytics.causal import CausalEffectReport
from polisyos.scientist.nodes.builtins.simulate import run_causal_evaluation as owner
spec=importlib.util.spec_from_file_location('fixture',Path('tests/unit/scientist/nodes/builtins/simulate/test_causal_selected_consumers.py'))
fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)
store=FileSystemCAS(Path('/workspace/e02-F-20261006-receipts/dowhy/raw/root-report-divergence-cas'))
registry=build_default_registry_bundle(store).bundle_ref
run=RunContext.start(store=store,registry_bundle=registry,run_id='R_independent')
ctx=ExecutionContext(store=store,run=run,logger=logging.getLogger('independent'))
state=ExperimentState(run_id='R_independent',inputs={'registry_bundle_ref':registry})
data=fixture._graph_data();state,source=fixture._admit_source(ctx,state,data,fixture.DoWhyIdentifyEstimate)
os.environ['POLISYOS_DOWHY_WORKER_PYTHON']='/workspace/e02-F-dowhy-20261006/policy-engine/workers/dowhy-014/.venv/bin/python'
actual=owner.run_job
def consistent_corruption(*args,**kwargs):
    result=actual(*args,**kwargs)
    assert not result.issues
    payload=from_canonical_bytes(store.get_bytes(result.method_result_ref))
    report=CausalEffectReport.model_validate(payload['report'])
    report.point_estimate+=.05
    payload['report']=report.model_dump(mode='json')
    payload['envelope']=report.to_uncertainty_envelope().model_dump(mode='json')
    manifest=store.get_manifest(result.method_result_ref)
    result.method_result_ref=store.put_json(payload,PutOptions(kind=manifest.kind,media_type=manifest.media_type,schema=manifest.artifact_schema,inputs=manifest.inputs),canon_spec=CanonSpec(forbid_floats=False))
    result.final_state['report']=report
    result.final_state['envelope']=report.to_uncertainty_envelope()
    return result
owner.run_job=consistent_corruption
result=owner._run_primary_causal_job(ctx=ctx,state=state,observational_data=data,spec=JobSpec(job_kind='method',method_fqn=state.causal_method_fqn,seed=13))
report=CausalEffectReport.model_validate(result.final_state['report']);worker=report.metadata['worker']['result']
assert abs(report.point_estimate-worker['point']-.05)<1e-12
print(json.dumps({'source_sha':'93eed731088175fd244c5c66532ab6bd54e793b2','property':'typed consumed report numerical fields bind actual validated worker result','consumer_refused':False,'report_point':report.point_estimate,'worker_point':worker['point'],'unchanged_actual_worker_interval':worker['interval'],'actual_source_ref':source.model_dump(mode='json'),'worker_request_sha256':report.metadata['worker']['request_sha256'],'scope':'genuine numerical MethodJob/CAS only; no evaluation authority'},sort_keys=True))
