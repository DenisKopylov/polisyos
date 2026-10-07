"""Independent real explicit-source deadline witness; retain filesystem fixtures."""
import hashlib,json,sys,subprocess,tempfile,time
from pathlib import Path
from polisyos.core.artifacts import FileSystemCAS,PutOptions
from polisyos.core.artifacts.signing import Ed25519Verifier
from polisyos.core.artifacts import store as store_module
root=Path('/workspace/e02-B-current-coordination/.polisyos/e02-B-current/raw/review')
path=Path(tempfile.mkdtemp(prefix='cas-duplicate-inventory-',dir=root))
cas=FileSystemCAS(path/'cas')
ref=cas.put_bytes(b'actual complete blob',PutOptions(kind='proof',media_type='text/plain'))
consumed=[]
def inventory():
    for index in range(64):
        consumed.append(index)
        if index:time.sleep(0.01)
        yield ref
started=time.monotonic()
report=cas.verify_all_signatures(Ed25519Verifier(),artifact_ids=inventory(),max_workers=2,pending_window=2,deadline=started+0.04)
value={'source_file':store_module.__file__,'source_sha256':hashlib.sha256(Path(store_module.__file__).read_bytes()).hexdigest(),'fixture_root':str(path),'source_consumed':len(consumed),'source_total':64,'elapsed':time.monotonic()-started,'state':report.state,'abort_reason':report.abort_reason,'admitted':report.admitted,'finished':report.finished,'inventory_exhausted':report.inventory_exhausted,'statuses':[x.status.value for x in report.details]}
print(json.dumps(value),flush=True)
(path/'observation.json').write_text(json.dumps(value,indent=2)+'\n')
assert len(consumed)<64,'dedup must check absolute admission while traversing supplied duplicates'
