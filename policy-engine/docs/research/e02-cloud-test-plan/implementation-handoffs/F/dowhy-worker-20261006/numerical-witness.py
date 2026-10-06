"""Recompute the nonauthoritative known-DGP MethodJob/CAS/fresh-reader witness."""
from __future__ import annotations
import hashlib,importlib.util,json,os,subprocess,sys
from pathlib import Path
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import from_canonical_bytes
from polisyos.foundry.methods.catalog.causal import _dowhy_worker as bridge
from polisyos.foundry.methods.catalog.causal.dowhy_identify_estimate import DoWhyIdentifyEstimate
from polisyos.foundry.methods.catalog.causal.protocols import GraphCausalData
from polisyos.foundry.methods.registry import MethodRegistry
from polisyos.ir.analytics.causal import CausalEffectReport
from polisyos.scientist.compute.job_spec import JobSpec
from polisyos.scientist.compute.runner import run_job
if len(sys.argv)>1 and sys.argv[1]=='--read':
    store=FileSystemCAS(Path(sys.argv[2]))
    result_ref=ArtifactRef.model_validate(json.loads(sys.argv[3]))
    source_ref=ArtifactRef.model_validate(json.loads(sys.argv[4]))
    payload=from_canonical_bytes(store.get_bytes(result_ref))
    report=CausalEffectReport.model_validate(payload['report'])
    source=GraphCausalData.model_validate(from_canonical_bytes(store.get_bytes(source_ref)))
    bridge.validate_persisted_worker_response(response=report.metadata['worker'],state=source,store=store,source_ref=source_ref)
    assert sys.version_info[:2]==(3,14)
    assert abs(report.point_estimate-2.016134929864521)<1e-10
    assert report.confidence_level==.95
    assert list(report.confidence_interval)==report.metadata['worker']['result']['interval']
    print(json.dumps({'reader_python':sys.version,'persisted_result_ref':result_ref.model_dump(mode='json'),'source_ref':source_ref.model_dump(mode='json'),'source_bytes_sha256':hashlib.sha256(store.get_bytes(source_ref)).hexdigest(),'report':report.model_dump(mode='json'),'envelope':report.to_uncertainty_envelope().model_dump(mode='json'),'execution_evidence_authority':'execution_reproducibility_only','scientific_authority':'not_established'},sort_keys=True))
    raise SystemExit(0)
spec=importlib.util.spec_from_file_location('known_dgp_fixture',Path('tests/unit/foundry/methods/catalog/causal/test_dowhy_worker.py'))
fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)
root=Path(sys.argv[1])
data=fixture.dgp()
store,source=fixture.admit(root,data)
os.environ['POLISYOS_DOWHY_WORKER_PYTHON']=str(bridge._worker_directory()/'.venv/bin/python')
MethodRegistry.get_instance().register(DoWhyIdentifyEstimate,override=True)
job=JobSpec(job_kind='method',method_fqn=DoWhyIdentifyEstimate.signature.fqn,seed=13,input_refs={'dowhy_observational_data':source})
with bridge.worker_execution_context(store=store,source_ref=source):
    result=run_job(job,cas_root=root,method_state=data)
assert not result.issues
reader=subprocess.run([sys.executable,__file__,'--read',str(root),result.method_result_ref.model_dump_json(),source.model_dump_json()],capture_output=True,text=True,check=False)
print(reader.stdout,end='');print(reader.stderr,file=sys.stderr,end='')
assert reader.returncode==0
print(json.dumps({'job_key':result.job_key.model_dump(mode='json'),'method_result_ref':result.method_result_ref.model_dump(mode='json'),'method_evidence':from_canonical_bytes(store.get_bytes(result.method_evidence_ref)),'manifest_inputs':[x.model_dump(mode='json') for x in store.get_manifest(result.method_result_ref).inputs]},sort_keys=True))
