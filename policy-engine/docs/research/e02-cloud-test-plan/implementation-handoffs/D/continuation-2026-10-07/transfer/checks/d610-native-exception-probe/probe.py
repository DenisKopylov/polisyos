from pathlib import Path
import importlib.metadata, json, subprocess, sys
from polisyos.core import artifacts, canon
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.scientist.agent.vector_memory import VectorMemoryStore
root=Path(sys.argv[1]);store=FileSystemCAS(root/'cas')
source=VectorMemoryStore(dim=2,max_elements=2);source.add("prepared",[0.0,1.0],{})
original=source.save_to_artifact(store)
payload=canon.from_canonical_bytes(store.get_bytes(original))
index_ref=artifacts.ArtifactRef.model_validate(payload["index_ref"])
valid=store.get_bytes(index_ref);broken=valid[:-1]
VectorMemoryStore._admit_native_header(broken,2,2,1)
changed=store.put_bytes(broken,artifacts.PutOptions(kind=index_ref.kind,media_type=index_ref.media_type))
payload["index_ref"]=changed.model_dump(mode="json")
bundle=store.put_json(payload,artifacts.PutOptions(kind=original.kind,media_type=original.media_type),canon_spec=canon.CanonSpec(forbid_floats=False))
reader=VectorMemoryStore(dim=2,max_elements=2);reader.add("prior",[1.0,0.0],{})
before=reader._generation
try:
 reader.load_from_artifact(store,bundle)
except Exception as exc:
 print(json.dumps({"type":type(exc).__name__,"reason":str(exc),"header_passed":True,"valid_bytes":len(valid),"broken_bytes":len(broken),"old_pointer_unchanged":reader._generation is before,"query":reader.query([1.0,0.0]),"hnswlib":importlib.metadata.version("hnswlib"),"exact_bundle":bundle.model_dump(mode="json"),"exact_index":changed.model_dump(mode="json")}),flush=True)
else:
 print(json.dumps({"type":"NO_EXCEPTION","header_passed":True}),flush=True)
request=root/'request.json';request.write_text(json.dumps({"cas":str(store.root),"bundle":bundle.model_dump(mode="json"),"native_only":True}))
worker=Path("/dev/shm/e02-D-oct07-continuation/policy-engine/tests/unit/scientist/agent/vector_generation_reader.py")
cp=subprocess.run([sys.executable,str(worker),str(request)],capture_output=True,text=True)
(root/'child.stdout').write_text(cp.stdout);(root/'child.stderr').write_text(cp.stderr)
print(json.dumps({"child_returncode":cp.returncode,"child_stdout":cp.stdout,"child_stderr":cp.stderr}),flush=True)
