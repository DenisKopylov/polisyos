from __future__ import annotations
import hashlib
import importlib
import importlib.metadata as metadata
import json
import sys
import tarfile
import zipfile
from pathlib import Path
import numpy as np
import pandas as pd
from packaging.markers import default_environment
from packaging.requirements import Requirement
from packaging.version import Version

RAW=Path('/Users/deniskopylov/.codex/worktrees/e02-c-continuation-20261006/polisyos/.tmp/e02-C2/raw/installed/obs-5a75').resolve()
ROOT=Path('/Users/deniskopylov/.codex/worktrees/e02-c-obs-udf-20261006/polisyos').resolve()
WHEEL=RAW/'dist/policy_engine-0.1.0-py3-none-any.whl'
ARCHIVE=RAW/'candidate.tar'
def require(ok:bool,msg:str)->None:
    if not ok: raise AssertionError(msg)
def sha(data:bytes)->str: return hashlib.sha256(data).hexdigest()

dist=metadata.distribution('policy-engine')
site=Path(dist.locate_file('')).resolve()
require(Path.cwd().resolve()==Path('/tmp').resolve(),f'wrong CWD: {Path.cwd()}')
require(not any(str(ROOT) in entry for entry in sys.path),'candidate source checkout visible on sys.path')
env=default_environment(); env['extra']=''; base=[]; missing=[]
for raw in dist.requires or []:
    req=Requirement(raw)
    if req.marker is not None and not req.marker.evaluate(env): continue
    base.append(raw)
    try: actual=Version(metadata.version(req.name))
    except metadata.PackageNotFoundError:
        missing.append({'requirement':raw,'reason':'distribution absent'}); continue
    if req.specifier and not req.specifier.contains(actual,prereleases=True):
        missing.append({'requirement':raw,'installed':str(actual),'reason':'specifier mismatch'})
require(not missing,f'base dependency closure unsatisfied: {missing}')
require(len(base)==34,f'expected 34 active base requirements, found {len(base)}')
for absent in ('pytest','hnswlib','sentence-transformers','torch','transformers'):
    try: metadata.version(absent)
    except metadata.PackageNotFoundError: pass
    else: raise AssertionError(f'unselected extra/test dependency installed: {absent}')

modules={
 'polisyos.data_forge.domains.ukraine.builders.sources':'src/polisyos/data_forge/domains/ukraine/builders/sources.py',
 'polisyos.data_forge.domains.ukraine.builders':'src/polisyos/data_forge/domains/ukraine/builders/__init__.py',
 'polisyos.data_forge.domains.ukraine.orchestrator':'src/polisyos/data_forge/domains/ukraine/orchestrator.py',
 'polisyos.data_forge.domains.ukraine.models':'src/polisyos/data_forge/domains/ukraine/models.py',
 'polisyos.data_forge.domains.ukraine.manifests':'src/polisyos/data_forge/domains/ukraine/manifests.py',
 'polisyos.data_forge.domains.ukraine.cli':'src/polisyos/data_forge/domains/ukraine/cli.py',
 'polisyos.data_forge.domains.ukraine.demography':'src/polisyos/data_forge/domains/ukraine/demography/__init__.py',
 'polisyos.data_forge.domains.ukraine.builders.demography':'src/polisyos/data_forge/domains/ukraine/builders/demography.py',
 'polisyos.data_forge.read_api.ukraine':'src/polisyos/data_forge/read_api/ukraine.py',
 'polisyos.data_forge.read_api._lazy':'src/polisyos/data_forge/read_api/_lazy.py',
 'polisyos.core.artifacts.store':'src/polisyos/core/artifacts/store.py',
}
origins=[]
with zipfile.ZipFile(WHEEL) as wheel, tarfile.open(ARCHIVE,'r:') as archive:
    wheel_names=set(wheel.namelist()); archive_names=set(archive.getnames())
    for name,source_path in modules.items():
        mod=importlib.import_module(name); origin=Path(mod.__file__).resolve()
        require(origin.is_relative_to(site),f'{name} not imported from installed site-packages: {origin}')
        wheel_member=source_path.removeprefix('src/'); archive_member=f'source/policy-engine/{source_path}'
        require(wheel_member in wheel_names and archive_member in archive_names,f'{name} missing from wheel/archive')
        installed=origin.read_bytes(); source=archive.extractfile(archive_member).read()
        require(installed==wheel.read(wheel_member)==source,f'{name} bytes differ from frozen candidate')
        origins.append({'module':name,'origin':str(origin),'sha256':sha(installed),'wheel_member':wheel_member,'archive_member':archive_member,'byte_identical_to_wheel_and_frozen_source':True})

from polisyos.data_forge.domains.ukraine.builders import STAGE_BUILDERS
from polisyos.data_forge.domains.ukraine.builders.sources import build_d0_p0_stage
from polisyos.data_forge.domains.ukraine.manifests import ArtifactRecord, NormalizedArtifactManifest, PartAGateManifest, write_manifest
from polisyos.data_forge.domains.ukraine.models import StageId, build_default_pipeline_config
from polisyos.data_forge.domains.ukraine.orchestrator import UkraineDataOrchestrator
from polisyos.data_forge.read_api.ukraine import (
    UkraineStageArtifactVerificationError,
    build_static_aging_state,
    load_demography_artifacts as read_api_load_demography,
    load_verified_stage_artifacts,
    load_verified_stage_output_bytes,
)
from polisyos.data_forge.domains.ukraine.demography import load_demography_artifacts as domain_load_demography
from polisyos.core.artifacts.store import FileSystemCAS

require(STAGE_BUILDERS[StageId.D0_P0] is build_d0_p0_stage,'D0/P0 builder is not the registered installed source builder')
FIX=RAW/'runtime-fixtures'
pipe_root=FIX/'pipeline-root'
config=build_default_pipeline_config(root=pipe_root)
# Explicit local fixture mode only: this skips the MacOS server-only production gate;
# it does not claim the server capability or Part A integration gate.
config.server.require_server_for_build=False
orchestrator=UkraineDataOrchestrator(config,workspace_root=None)
orchestrator.ensure_layout()
write_manifest(config.build_root.part_a_gate_manifest_path,PartAGateManifest(status='fixture_passed',passed=True,command=['isolated-fixture-only']))

def frame_for(source_id:str,required_columns:list[str])->pd.DataFrame:
    if source_id=='edr_current':
        return pd.DataFrame({'agent_id':['agent::1','agent::2'],'registration_code':['11111111','22222222'],'tax_id':['11111111','22222222'],'edrpou':['11111111','22222222'],'name':['Entity One','Entity Two'],'region_code':['01','02'],'sector_id':['A','B'],'region_numeric':[1,2],'revenue':[100.0,200.0],'assets':[80.0,160.0],'liabilities':[20.0,40.0],'employees':[2.0,4.0],'longitude':[30.0,31.0],'latitude':[50.0,51.0],'cell_id':['cell::01::A','cell::02::B']})
    if source_id=='spending_full':
        return pd.DataFrame({'source_agent_id':['11111111'],'target_agent_id':['22222222'],'amount':[100.0],'period_id':['2024-01'],'registration_code':['11111111']})
    if source_id in {'spending_contracts_procurement_proxy','prozorro_full'}:
        return pd.DataFrame({'buyer_agent_id':['11111111'],'supplier_agent_id':['22222222'],'supplier_name':['Entity Two'],'amount':[50.0],'period_id':['2024-01'],'registration_code':['11111111']})
    if source_id=='macro_nbu_derzhstat':
        return pd.DataFrame({'period_id':['2024-01'],'metric_id':['gdp'],'observed_value':[1.0],'region_code':['01']})
    if source_id=='dps_financials':
        return pd.DataFrame({'agent_id':['agent::1'],'registration_code':['11111111'],'period_id':['2024'],'revenue':[100.0],'assets':[80.0],'liabilities':[20.0],'employees':[2.0]})
    rows=[]
    for index,agent in enumerate(('agent::1','agent::2')):
        row={}
        for column in required_columns:
            if column in {'agent_id','source_agent_id','buyer_agent_id'}: row[column]=agent
            elif column in {'target_agent_id','supplier_agent_id'}: row[column]='agent::2' if index==0 else 'agent::1'
            elif column=='registration_code': row[column]=('11111111','22222222')[index]
            elif column=='period_id': row[column]='2024-01'
            elif column=='region_code': row[column]='01'
            elif column=='sector_id': row[column]='A'
            elif column=='cell_id': row[column]='cell::01::A'
            elif column=='metric_id': row[column]=f'{source_id}_metric'
            elif column=='name': row[column]=f'Entity {index+1}'
            else: row[column]=1.0
        rows.append(row)
    return pd.DataFrame.from_records(rows,columns=required_columns)

seeded=[]
for source_id in config.stages[StageId.D0_P0.value].required_sources:
    source=config.sources[source_id]
    frame=frame_for(source_id,source.required_columns)
    artifact_path=config.build_root.normalized_dir/source_id/source.normalized_artifact
    artifact_path.parent.mkdir(parents=True,exist_ok=True)
    frame.to_parquet(artifact_path,index=False)
    manifest_path=config.build_root.manifests_dir/source_id/source.manifest_name
    write_manifest(manifest_path,NormalizedArtifactManifest(source_id=source_id,stage_id=source.stage_id,status='completed',normalized_artifact=ArtifactRecord.from_path(artifact_path,row_count=len(frame)),schema_version='1.0'))
    seeded.append({'source_id':source_id,'artifact':str(artifact_path),'rows':len(frame),'manifest':str(manifest_path)})
summary=orchestrator.build_stage(StageId.D0_P0)
require(summary.status=='completed',f'installed registered D0/P0 stage failed: {summary.manifest.errors}')
required=('agent_registry_runtime.parquet','identity_resolution_cohort_v1.json')
cas=FileSystemCAS(FIX/'stage-cas')
stage_receipt=load_verified_stage_artifacts(orchestrator.stage_manifest_path(StageId.D0_P0),store=cas,allowed_root=pipe_root,expected_stage=StageId.D0_P0.value,required_outputs=required)
cohort_bytes=load_verified_stage_output_bytes(cas,stage_receipt,'identity_resolution_cohort_v1.json')
require(sha(cohort_bytes)==stage_receipt.outputs['identity_resolution_cohort_v1.json'].sha256,'CAS stage output readback hash differs')
cohort_payload=json.loads(cohort_bytes)
require(cohort_payload.get('schema_version')=='1.0','readback cohort schema mismatch')
# Counterfactual: the installed read_api must refuse changed producer bytes.
cohort_path=Path(stage_receipt.outputs['identity_resolution_cohort_v1.json'].source_path)
original=cohort_path.read_bytes(); cohort_path.write_bytes(original+b'\n')
try:
    try:
        load_verified_stage_artifacts(orchestrator.stage_manifest_path(StageId.D0_P0),store=cas,allowed_root=pipe_root,expected_stage=StageId.D0_P0.value,required_outputs=required)
    except UkraineStageArtifactVerificationError as exc:
        tamper_result={'rejected':True,'error_type':type(exc).__name__,'message':str(exc)}
    else:
        raise AssertionError('read_api admitted mutated producer bytes')
finally:
    cohort_path.write_bytes(original)

# Real domain and public read_api consumers for a synthetic, closed demographic snapshot.
demo_root=FIX/'demography-new'
def write_json(path:Path,payload:dict[str,object])->None:
    path.parent.mkdir(parents=True,exist_ok=True); path.write_text(json.dumps(payload,ensure_ascii=True,indent=2),encoding='utf-8')
write_json(demo_root/'demography'/'targets.json',{'state_ids':['0-17:F:TEST','18-64:F:TEST'],'target_state_totals':[100.0,250.0],'entrant_state_totals':[10.0,2.0],'metadata':{'snapshot':'installed-new-2027','year':2027}})
write_json(demo_root/'demography'/'transition_priors.json',{'transition_prior_matrix':[[0.8,0.2],[0.1,0.9]],'allowed_transition_mask':[[True,True],[False,True]]})
write_json(demo_root/'demography'/'donor_pool.json',{'donor_weights':[0.25,0.75],'donor_state_index':[0,1],'donor_record_index':[1001,1002]})
domain_artifacts=domain_load_demography(demo_root)
read_api_artifacts=read_api_load_demography(demo_root)
require(domain_artifacts.metadata['snapshot']==read_api_artifacts.metadata['snapshot']=='installed-new-2027','domain/read_api did not resolve same fixture snapshot')
state=build_static_aging_state(base_weights=np.array([2.0,3.0]),origin_state_index=np.array([0,1]),artifacts=read_api_artifacts,exit_weights=np.array([0.5,0.0]),microsim_calibration_report={'decision':'pass','can_run_microsim':True,'compatibility_status':'compatible'})
require(np.allclose(state['target_state_totals'],np.array([100.0,250.0])),'downstream static-aging consumer changed target totals')
require(np.array_equal(state['donor_record_index'],np.array([1001,1002])),'downstream static-aging consumer lost donor record ids')
require(np.array_equal(state['allowed_transition_mask'],np.array([[True,True],[False,True]])),'downstream static-aging consumer lost transition mask')
# Counterfactual layout-mix control: even a partial alternate historical layout is rejected.
mixed=FIX/'demography-mixed'
for source in (demo_root/'demography').iterdir(): write_json(mixed/'demography'/source.name,json.loads(source.read_text()))
write_json(mixed/'demography_targets.json',{'state_ids':['legacy'],'target_state_totals':[999.0],'entrant_state_totals':[0.0]})
try:
    read_api_load_demography(mixed)
except ValueError as exc:
    mixed_result={'rejected':True,'error_type':type(exc).__name__,'message':str(exc)}
else:
    raise AssertionError('read_api silently chose one of mixed/incomplete layouts')

entry_points=metadata.entry_points().select(group='console_scripts')
entry=next((ep for ep in entry_points if ep.name=='ukraine-data'),None)
cli_path=Path(sys.prefix)/'bin'/'ukraine-data'
require(entry is not None,'ukraine-data console entrypoint absent from installed metadata')
require(entry.value=='polisyos.data_forge.domains.ukraine.cli:main',f'unexpected ukraine-data entrypoint target: {entry.value}')
require(cli_path.is_file(),f'installed ukraine-data script absent: {cli_path}')
cli_text=cli_path.read_text()
require('polisyos.data_forge.domains.ukraine.cli' in cli_text,'ukraine-data script does not invoke installed CLI target')
cli_help=(RAW/'ukraine-cli-help.stdout').read_bytes(); cli_error=(RAW/'ukraine-cli-help.stderr').read_bytes()
require(b'usage: ukraine-data' in cli_help,'installed ukraine-data help output missing its public name')
result={'cwd':str(Path.cwd()),'python':sys.executable,'distribution':{'name':dist.metadata['Name'],'version':dist.version,'site_packages':str(site)},'candidate_checkout_on_sys_path':False,'dependency_profile':{'active_base_requirement_count':len(base),'missing_or_mismatched':missing,'selected_extras':[],'pytest_present':False,'hnswlib_present':False},'installed_module_origins_and_source_identity':origins,'changed_source_mapping':{'production_changed_paths':2,'both_exact_in_wheel_and_frozen_archive':True},'ukraine_data_entrypoint':{'installed_metadata_value':entry.value,'script_path':str(cli_path),'script_sha256':sha(cli_path.read_bytes()),'help_stdout_sha256':sha(cli_help),'help_stderr_sha256':sha(cli_error),'help_exit_code':int((RAW/'ukraine-cli-help.exit').read_text().strip())},'registered_stage':{'registry_owner':'polisyos.data_forge.domains.ukraine.builders.STAGE_BUILDERS','stage':'d0_p0','builder_module':STAGE_BUILDERS[StageId.D0_P0].__module__,'status':summary.status,'output_names':sorted(stage_receipt.outputs),'synthetic_sources_seeded':seeded,'server_gate':'disabled only in this isolated fixture; no server/Part-A capability claimed','part_a_gate':'synthetic fixture prerequisite, not real validation'},'stage_read_api':{'receipt_type':type(stage_receipt).__name__,'manifest_ref':stage_receipt.manifest_ref.model_dump(mode='json'),'manifest_sha256':stage_receipt.manifest_sha256,'verified_output_count':len(stage_receipt.outputs),'cohort_sha256':stage_receipt.outputs['identity_resolution_cohort_v1.json'].sha256,'cohort_payload':cohort_payload,'cas_readback_sha256':sha(cohort_bytes),'tamper_control':tamper_result,'authority_boundary':{'authoritative_for':list(stage_receipt.authoritative_for),'may_not_use_for':list(stage_receipt.may_not_use_for)}},'demography_read_api':{'snapshot':read_api_artifacts.metadata['snapshot'],'domain_loader_same_snapshot':domain_artifacts.metadata['snapshot'],'state_ids':read_api_artifacts.state_ids,'target_totals':np.asarray(read_api_artifacts.target_state_totals).tolist(),'transition_mask':np.asarray(read_api_artifacts.allowed_transition_mask).tolist(),'static_aging_target_totals':np.asarray(state['target_state_totals']).tolist(),'donor_record_index':np.asarray(state['donor_record_index']).tolist(),'mixed_layout_negative_control':mixed_result},'data_origin':'only small synthetic local fixtures; no production_data, source download, model, or remote service','full_c7_server_runtime':'UNRUN; this is a bounded local installed stage/read_api fixture, not the Linux server-only execution gate'}
print(json.dumps(result,sort_keys=True))
