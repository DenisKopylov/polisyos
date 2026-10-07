from __future__ import annotations
import hashlib, json, os, subprocess, sys
from collections.abc import Mapping
from importlib.abc import MetaPathFinder
from importlib.machinery import PathFinder
from pathlib import Path
ROOT=Path(os.environ['C_CANON_GROOT']).resolve()
TASK=Path(__file__).resolve().parents[2]
SOURCE=TASK/'candidate/policy-engine/src'
SHA='55b45d9a5c95c3b773fc3b4d8679786b3993eb1e'
TREE='70ed14e004063536ff3a12d30d14d9bdd79a4916'
preloaded=[n for n in sys.modules if n=='polisyos' or n.startswith('polisyos.')]
if preloaded: raise RuntimeError(f'Polisyos preloaded before isolation: {preloaded}')
class CandidateOnlyFinder(MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname!='polisyos' and not fullname.startswith('polisyos.'): return None
        spec=PathFinder.find_spec(fullname,[str(SOURCE)] if fullname=='polisyos' else path,target)
        if spec is None: raise ModuleNotFoundError(f'{fullname} missing from pinned candidate')
        locations=[]
        if spec.origin and spec.origin not in {'built-in','frozen'}: locations.append(Path(spec.origin).resolve())
        if spec.submodule_search_locations: locations.extend(Path(p).resolve() for p in spec.submodule_search_locations)
        if not locations or any(not p.is_relative_to(SOURCE.resolve()) for p in locations):
            raise ModuleNotFoundError(f'{fullname} outside candidate: {locations}')
        return spec
sys.meta_path.insert(0,CandidateOnlyFinder());sys.path.insert(0,str(SOURCE))
os.chdir(TASK/'candidate/policy-engine')
from polisyos.core.artifacts.ir_adapter import ensure_ir_artifact_store
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.artifacts.io import get_json_artifact, put_json_artifact
cas_path=Path(__file__).resolve().parent/'cas'
core=FileSystemCAS(cas_path);store=ensure_ir_artifact_store(core)
payload={'mapping_exact_probe':True,'value':1729}
ref=put_json_artifact(store,payload,kind='test.canon.mapping-exact-probe',schema_name='test.canon.mapping-exact-probe',schema_version='1.0')
artifact_id=ref['artifact_id'];manifest=store.get_manifest(artifact_id)
manifest_json=manifest.model_dump(mode='json')
def canonical_json(value): return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'))
manifest_json_hash_before=hashlib.sha256(canonical_json(manifest_json).encode()).hexdigest()
canon_json=manifest_json.get('canon');separators=canon_json.get('separators') if isinstance(canon_json,Mapping) else None
# Positive real typed-manifest public read.
typed_read=get_json_artifact(store,artifact_id)
class PersistedJsonMappingView:
    def __init__(self): self.get_bytes_calls=0;self.returned_manifest_sha256=None
    def get_manifest(self,key):
        if str(key)!=str(artifact_id): raise AssertionError(f'unexpected key: {key}')
        exact=manifest.model_dump(mode='json')
        self.returned_manifest_sha256=hashlib.sha256(canonical_json(exact).encode()).hexdigest()
        return exact
    def get_bytes(self,key):
        self.get_bytes_calls+=1
        return store.get_bytes(key)
mapping_view=PersistedJsonMappingView();callback_before=mapping_view.get_bytes_calls
mapping_read=None;mapping_error=None
try: mapping_read=get_json_artifact(mapping_view,artifact_id)
except Exception as exc: mapping_error={'type':f'{type(exc).__module__}.{type(exc).__qualname__}','message':str(exc)}
callback_after=mapping_view.get_bytes_calls
manifest_json_hash_after=hashlib.sha256(canonical_json(manifest.model_dump(mode='json')).encode()).hexdigest()
# Bind the modules loaded by this exact probe to candidate Git objects; no live-tree imports.
ls=subprocess.check_output(['git','ls-tree','-r',SHA,'--','policy-engine/src/polisyos'],cwd=ROOT,text=True)
blobs={}
for line in ls.splitlines():
    left,path=line.split('\t',1);mode,kind,oid=left.split()[:3]
    if kind=='blob':blobs[path]={'mode':mode,'oid':oid}
origins=[]
for name,module in sorted(sys.modules.items()):
    if name!='polisyos' and not name.startswith('polisyos.'):continue
    filename=getattr(module,'__file__',None)
    if filename is None:
        locations=[str(Path(p).resolve()) for p in (getattr(module,'__path__',()) or ())]
        if any(not Path(p).is_relative_to(SOURCE.resolve()) for p in locations):raise AssertionError(f'namespace outside source: {name} {locations}')
        origins.append({'module':name,'namespace_locations':locations,'candidate_only':True});continue
    path=Path(filename).resolve();rel=path.relative_to(SOURCE.resolve()).as_posix();gitpath='policy-engine/src/'+rel
    data=path.read_bytes();actual=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest();expected=blobs.get(gitpath)
    row={'module':name,'origin':str(path),'git_path':gitpath,'source_sha256':hashlib.sha256(data).hexdigest(),'git_blob':expected['oid'] if expected else None,'blob_match':bool(expected and expected['oid']==actual)}
    if not row['blob_match']:raise AssertionError(f'candidate module blob mismatch: {row}')
    origins.append(row)
result={'candidate_sha':SHA,'candidate_tree':TREE,'candidate_source_root':str(SOURCE),'python':sys.version,'cas_root':str(cas_path),'artifact_id':str(artifact_id),'typed_roundtrip':'PASS' if typed_read==payload else 'FAIL','typed_readback':typed_read,'mapping_roundtrip':'PASS' if mapping_read==payload else 'FAIL','mapping_readback':mapping_read,'mapping_exception':mapping_error,'mapping_get_bytes_calls_before':callback_before,'mapping_get_bytes_calls_after':callback_after,'manifest_json_unchanged':manifest_json_hash_before==manifest_json_hash_after==mapping_view.returned_manifest_sha256,'manifest_json_sha256_before':manifest_json_hash_before,'manifest_json_sha256_returned':mapping_view.returned_manifest_sha256,'manifest_json_sha256_after':manifest_json_hash_after,'actual_persisted_canon_profile':canon_json,'json_separators':separators,'json_separators_type':type(separators).__name__,'loaded_polisyos_module_count':len(origins),'module_blob_mismatches':0,'module_origins':origins,'full_unmodified_mapping_manifest':manifest_json}
print('C_CANON_MAPPING_EXACT_RESULT='+json.dumps(result,ensure_ascii=False,sort_keys=True))
if typed_read!=payload or not result['manifest_json_unchanged']:raise SystemExit(2)
