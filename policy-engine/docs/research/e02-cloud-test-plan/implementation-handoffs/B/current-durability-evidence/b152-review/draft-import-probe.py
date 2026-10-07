"""Independent real FileSystemCAS snapshot/signature/quality-consumer checks."""
from __future__ import annotations
import hashlib, importlib.util, json, pathlib, subprocess, sys
from polisyos.core.artifacts import FileSystemCAS, PutOptions, build_cas_integrity_report
from polisyos.core.artifacts import store as store_module
from polisyos.core.artifacts.signing import KeyPair, Ed25519Signer, Ed25519Verifier, SignatureVerificationStatus as Status
from polisyos.core.artifacts.errors import ArtifactOwnershipError
ROOT=pathlib.Path('/workspace/e02-B-current-durability')
TARGET='2456205c9845042ee94bae4d7c35df7939ca3bd2'
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()==TARGET
assert pathlib.Path(store_module.__file__).resolve()==ROOT/'policy-engine/src/polisyos/core/artifacts/store.py'
TMP=pathlib.Path(sys.argv[1]).resolve(); assert not TMP.exists(); TMP.mkdir(parents=True)
records=[]
store=FileSystemCAS(TMP/'signed',ownership_enforced=False)
ref=store.put_bytes(b'one signed snapshot',PutOptions(kind='review.snapshot',media_type='text/plain'))
key=KeyPair.generate();signer=Ed25519Signer.from_pem(key.private_pem()); store.sign_artifact(ref,signer,signer_identity='review-owner')
verifier=Ed25519Verifier(); verifier.add_trusted_key(key.public_key,key_id=key.key_id,identity='review-owner')
assert store.verify_signature(ref,verifier,strict_identity=True).status is Status.VALID
blob,_=store._paths(ref.artifact_id); manifest=store._manifest_path_for_ref(ref.artifact_id,ref.manifest_profile_sha256)
old_blob=blob.read_bytes(); old_manifest=manifest.read_bytes(); reads={'blob':0,'manifest':0,'signature':0}; actual_read=store._read_cas_file_no_follow
swapped=False

def swap_after_actual_read(path,*,member,max_bytes=None):
 global swapped
 data=actual_read(path,member=member,max_bytes=max_bytes);reads[member]+=1
 if member=='blob' and not swapped:
  swapped=True;blob.write_bytes(b'corrupt same length');assert len(blob.read_bytes())==len(old_blob)
 return data
store._read_cas_file_no_follow=swap_after_actual_read
result=store.verify_signature(ref,verifier,strict_identity=True)
assert result.status is Status.VALID and reads=={'blob':1,'manifest':1,'signature':1}
store._read_cas_file_no_follow=actual_read
assert store.verify_signature(ref,verifier,strict_identity=True).status is Status.ERROR
try: build_cas_integrity_report(store,ref)
except ValueError: pass
else: raise AssertionError('fresh corrupt bytes admitted by public report')
blob.write_bytes(old_blob); assert manifest.read_bytes()==old_manifest
records.append({'case':'signature retained exact bytes after actual same-size filesystem swap','status':result.status.value,'reads':reads,'fresh_corrupt_reopen':'ERROR/report ValueError','manifest_unchanged':True})
assert store.verify_signature(ref,verifier,strict_identity=True).status is Status.VALID
verifier.add_revoked_key_id(key.key_id)
assert store.verify_signature(ref,verifier,strict_identity=True).status is Status.REVOKED
assert store.verify_signature(ref,Ed25519Verifier()).status is Status.UNTRUSTED
wrong_identity=Ed25519Verifier(); wrong_identity.add_trusted_key(key.public_key,key_id=key.key_id,identity='different-owner')
assert store.verify_signature(ref,wrong_identity,strict_identity=True).status is Status.INVALID
fresh=Ed25519Verifier();fresh.add_trusted_key(key.public_key,key_id=key.key_id,identity='review-owner')
assert store.verify_signature(ref,fresh,strict_identity=True).status is Status.VALID
sig=store._sig_path(ref.artifact_id,ref.manifest_profile_sha256); old_sig=sig.read_bytes(); wire=json.loads(old_sig); encoded=wire['signature_hex']; wire['signature_hex']=('00' if encoded[:2]!='00' else '01')+encoded[2:]; sig.write_text(json.dumps(wire))
assert store.verify_signature(ref,fresh,strict_identity=True).status is Status.INVALID
sig.write_bytes(old_sig);assert store.verify_signature(ref,fresh,strict_identity=True).status is Status.VALID
records.append({'case':'same stored snapshot rechecks current key authority and actual Ed25519 bytes','statuses':['valid','revoked','untrusted','invalid_identity','valid_fresh_trust','invalid_signature','valid_restored']})
owner_a=FileSystemCAS(TMP/'owned').for_tenant('review-tenant-a');owner_b=FileSystemCAS(TMP/'owned').for_tenant('review-tenant-b')
owned=owner_a.put_bytes(b'owned immutable bytes',PutOptions(kind='review.owned',media_type='text/plain'))
assert owner_a.get_verified_snapshot(owned).data==b'owned immutable bytes'
for operation in [lambda:owner_b.get_verified_snapshot(owned),lambda:build_cas_integrity_report(owner_b,owned)]:
 try:operation()
 except ArtifactOwnershipError:pass
 else:raise AssertionError('foreign unclaimed owner read admitted')
records.append({'case':'actual optional snapshot/report port preserves current tenant admission','positive_owner':'A','unclaimed_B_snapshot_and_report':'ArtifactOwnershipError'})
quality_path=ROOT/'policy-engine/tools/quality/validation/check_layer3_artifact_surface_safety.py'
spec=importlib.util.spec_from_file_location('independent_b152_quality_consumer',quality_path);quality=importlib.util.module_from_spec(spec);sys.modules[spec.name]=quality;spec.loader.exec_module(quality)
quality_store=FileSystemCAS(TMP/'quality',ownership_enforced=False)
authority=quality._write_authority_payload(quality_store,{'independent':'actual authority input','value':3},kind='surface.review_authority')
payload=quality._build_cas_payload(store=quality_store,exit_payload_refs=[authority])
assert payload['dedup_probe']['same_digest'];assert payload['tamper_probe']['result'].startswith('rejected:');assert len(payload['reports'])==3
assert not payload['gc_dry_run_summary']['authority_missing'];assert not payload['gc_dry_run_summary']['not_retained'];assert payload['gc_dry_run_summary']['unreferenced_authority_probe']['result']=='blocked'
records.append({'case':'actual quality _build_cas_payload invokes public concrete FileSystemCAS report port','dedup':payload['dedup_probe'],'tamper':payload['tamper_probe'],'gc':payload['gc_dry_run_summary'],'report_count':len(payload['reports']),'full_reports':payload['reports']})
print(json.dumps({'target_sha':TARGET,'tree':subprocess.check_output(['git','rev-parse','HEAD^{tree}'],cwd=ROOT,text=True).strip(),'environment':{'python':sys.version,'executable':sys.executable,'store_module':store_module.__file__,'quality_consumer':str(quality_path)},'cases':records,'result':'PASS; finite concrete FileSystemCAS consumer profile; no generic backend conformance'},indent=2))
