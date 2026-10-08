"""Exercise finite current-G CAS producer/reader boundaries on isolated fixtures."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from polisyos.core.artifacts.ir_adapter import ensure_ir_artifact_store
from polisyos.core.artifacts.manifest import CanonInfo, WarningRecord
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.ir.analytics.backtest import BacktestReport, load_backtest_report, persist_backtest_report
from polisyos.ir.artifacts.io import get_json_artifact
from polisyos.ir.model_layer.canon import CanonViolation
from decimal import Decimal

ROOT=Path('/workspace/orch02-r2-c06-can')
BASE='dee58973f7673299070b7c7374f419b0adb8175c'
FROZEN='70051ecf56771a59c0ecc468e975e7878b66f728'
OUT=Path('/workspace/orch02-r2/c06-can')

class FreshMappingReader:
    """Forward bytes to a new real CAS instance while exposing its JSON-mode manifest."""
    def __init__(self, store, artifact_id, mutation=None):
        self.store=store
        self.manifest=store.get_manifest(artifact_id).model_dump(mode='json')
        if mutation:mutation(self.manifest)
        self.byte_reads=0
        self.manifest_reads=0
    def get_manifest(self, artifact_id):
        self.manifest_reads+=1
        return self.manifest
    def get_bytes(self, artifact_id):
        self.byte_reads+=1
        return self.store.get_bytes(artifact_id)

def result_payload(value):
    if isinstance(value, BacktestReport):return {'type':'BacktestReport','report_id':value.report_id,'n_scenarios':value.n_scenarios}
    if isinstance(value, dict):return {'type':'dict','value':{k:result_payload(v) for k,v in value.items()}}
    if isinstance(value, list):return {'type':'list','value':[result_payload(v) for v in value]}
    if isinstance(value, Decimal):return {'type':'Decimal','value':str(value)}
    if isinstance(value, bytes):return {'type':'bytes','hex':value.hex()}
    return {'type':type(value).__name__,'value':value}

cases=[]
with tempfile.TemporaryDirectory(prefix='can-finite-',dir=OUT) as d:
    fixture=Path(d)
    def run(label,emit,*,mutation=None,typed=False,expect_error=None,expected_reads=1,limitation=None):
        root=fixture/label
        ref=emit(FileSystemCAS(root))
        artifact_id=str(ref.artifact_id)
        fresh=FileSystemCAS(root)
        before=fresh.get_bytes(artifact_id)
        reader=FreshMappingReader(fresh,artifact_id,mutation)
        error=None;value=None
        try:value=load_backtest_report(reader,ref) if typed else get_json_artifact(reader,artifact_id)
        except Exception as exc:error={'type':type(exc).__name__,'message':str(exc)}
        if expect_error is None:assert error is None,(label,error)
        else:assert error and error['type']==expect_error[0] and expect_error[1] in error['message'],(label,error)
        assert reader.byte_reads==expected_reads,(label,reader.byte_reads)
        assert before==fresh.get_bytes(artifact_id)
        row={'case':label,'artifact_id':artifact_id,'exact_payload_utf8':before.decode('utf-8'),'payload_sha256':hashlib.sha256(before).hexdigest(),'payload_bytes':len(before),'complete_persisted_JSON_mode_manifest':True,'read_manifest_canon':reader.manifest.get('canon'),'actual_fresh_reader':str(type(fresh)),'typed_result':None if error else result_payload(value),'error':error,'reader_manifest_calls':reader.manifest_reads,'reader_payload_calls':reader.byte_reads,'stored_bytes_unchanged':True,'minimum_read_rule':'Complete name polisyos.canon.json/version0.2.0 profile with strict field types, JSON separator-list normalization, persisted max_depth, IR historical supported typed tags. Profile metadata does not establish emitter or authority.','limitation':limitation}
        cases.append(row)
    default=lambda s:s.put_json({'amount':Decimal('12.30')},ArtifactWriteOptions(kind='fixture.can',media_type='application/json'))
    run('default-current-Core-put_json-shared-subset',default)
    run('default-current-IR-producer-typed-consumer',lambda s:persist_backtest_report(ensure_ir_artifact_store(s),BacktestReport(report_id='bt.finite.G')),typed=True)
    run('nondefault-Core-canon-options',lambda s:s.put_json({'label':'д','value':1.5,'empty':None},ArtifactWriteOptions(kind='fixture.can',media_type='application/json'),CanonSpec(forbid_floats=False,exclude_none=False,sort_keys=False,separators=(', ',': '),ensure_ascii=True)))
    run('profile-less-historical-bytes',lambda s:s.put_bytes(b'{"value":1}',ArtifactWriteOptions(kind='fixture.can',media_type='application/json')),expect_error=('CanonViolation','unsupported_ir_canon_profile'),expected_reads=0,limitation='Historical profile-less artifact support is not ratified; explicit refusal retained.')
    for tag,payload in [('float_hex',{'_type':'float_hex','value':'0x1.8p+1'}),('bytes_hex',{'_type':'bytes_hex','value':'00ff'}),('array_digest',{'_type':'array_digest','digest':'sha256:abc','length':2})]:
        run('current-Core-only-'+tag,lambda s,payload=payload:s.put_json(payload,ArtifactWriteOptions(kind='fixture.can',media_type='application/json')),expect_error=('CanonViolation','Unknown canonical _type'),limitation='C02/G must ratify distinct supported tag profile or pair with IR encoder; shared name/version alone does not imply full Core→IR compatibility.')
    run('raw-Core-bypass-shaped-profile',lambda s:s.put_bytes(b'{"_type":"float_hex","value":"0x1.8p+1"}',ArtifactWriteOptions(kind='fixture.can',media_type='application/json',canon=CanonInfo())),expect_error=('CanonViolation','Unknown canonical _type'),limitation='Reader cannot intercept raw Core writes; actual IR tag rejection still occurs after bytes.')
    run('missing-persisted-profile-field',default,mutation=lambda m:m['canon'].pop('max_depth'),expect_error=('CanonViolation','unsupported_ir_canon_profile'),expected_reads=0)
    run('mismatch-persisted-profile-version',lambda s:s.put_json({'value':1},ArtifactWriteOptions(kind='fixture.can',media_type='application/json',canon=CanonInfo(version='0.3.0'))),expect_error=('CanonViolation','unsupported_ir_canon_profile'),expected_reads=0)
    run('malformed-fake-profile-field',default,mutation=lambda m:m['canon'].update({'max_depth':True}),expect_error=('CanonViolation','unsupported_ir_canon_profile'),expected_reads=0)
    run('shaped-profile-is-not-producer-attestation',lambda s:s.put_bytes(b'{"value":1.5}',ArtifactWriteOptions(kind='fixture.can',media_type='application/json',canon=CanonInfo())),limitation='A raw numeric float under a shaped forbid_floats=true profile is decoded. Reader validates profile ABI/depth/tag set, not producer conformance, institutional provenance, or every serialization assertion. C02/G owns emitter/profile binding; no producer authority claim.')
    warning=WarningRecord(code='fixture-warning',msg='portable option discriminator')
    for mapping in [False,True]:
        root=fixture/('mapping-write-options' if mapping else 'typed-write-options')
        store=FileSystemCAS(root)
        opts=ArtifactWriteOptions(kind='fixture.options',media_type='application/json',warnings=[warning])
        passed={'kind':opts.kind,'media_type':opts.media_type,'warnings':[warning.model_dump(mode='python')]} if mapping else opts
        ref=ensure_ir_artifact_store(store).put_json({'value':1},passed)
        fresh=FileSystemCAS(root);manifest=fresh.get_manifest(ref).model_dump(mode='json')
        warning_count=len(manifest.get('warnings') or [])
        assert warning_count==(0 if mapping else 1)
        cases.append({'case':'mapping-adapter-write-options-warning-loss' if mapping else 'typed-adapter-write-options-warning-preserved','artifact_id':str(ref.artifact_id),'exact_payload_utf8':fresh.get_bytes(ref).decode(),'payload_sha256':ref.artifact_id.hex,'actual_persisted_warning_count':warning_count,'requested_warning_count':1,'typed_result':result_payload(get_json_artifact(FreshMappingReader(fresh,ref.artifact_id),ref.artifact_id)),'minimum_rule':'Current Core typed ArtifactWriteOptions preserves metadata; generic Mapping coercion drops new fields.','limitation':'Actionable C02/G _coerce_write_options extension/capability refusal seam. C06 changes no Core writer/default.' if mapping else None})

observed=[];unresolved=[]
for name,module in sorted(sys.modules.items()):
    if not name.startswith('polisyos'):continue
    origin=getattr(module,'__file__',None)
    if origin is None:unresolved.append({'module':name,'reason':'no_file_namespace_or_dynamic'});continue
    file=Path(origin).resolve()
    try:relative=file.relative_to(ROOT).as_posix()
    except ValueError:raise AssertionError(('foreign polisyos origin',name,str(file)))
    content=file.read_bytes();blob=hashlib.sha1(b'blob '+str(len(content)).encode()+b'\0'+content).hexdigest()
    expected=subprocess.check_output(['git','-C',str(ROOT),'rev-parse',FROZEN+':'+relative],text=True).strip()
    assert blob==expected,(name,relative,blob,expected)
    prior=subprocess.run(['git','-C',str(ROOT),'rev-parse',BASE+':'+relative],capture_output=True,text=True)
    observed.append({'module':name,'path':relative,'blob':blob,'sha256':hashlib.sha256(content).hexdigest(),'bytes':len(content),'selected_G_blob':prior.stdout.strip() if prior.returncode==0 else None,'equals_selected_G':prior.returncode==0 and blob==prior.stdout.strip()})
manifest={'schema':'policyos.e02.c06_can.r2_finite_compatibility_matrix.v1','author':'/root/c06_can_writer','fixture_only':True,'source_tree':FROZEN,'prospective_base':BASE,'cases':cases,'case_denominator':len(cases),'actual_polysios_file_origin_denominator':len(observed),'origins':observed,'unresolved_module_origins':unresolved,'scope':'Actual current-G producers/CAS fresh readers and typed IR consumer; author finite mechanism evidence pending independent review/tester reconciliation. No integrated/source acceptance or formal closure.','source_acceptance':'not_issued_by_G','formal_closure_ids':[]}
(OUT/'finite-compatibility-matrix.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'cases':len(cases),'case_names':[r['case'] for r in cases],'polysios_file_origins':len(observed),'G_nonidentical_origins':[(r['module'],r['path']) for r in observed if not r['equals_selected_G']],'unresolved_origins':unresolved},ensure_ascii=False,indent=2))
