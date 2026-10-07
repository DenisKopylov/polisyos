"""Replay immutable LLM discriminator while retaining its actual fixture bytes."""
import hashlib,json,runpy,tempfile
from pathlib import Path
base=Path('/workspace/e02-B-current-coordination/.polisyos/e02-B-current/raw/review')
original=tempfile.TemporaryDirectory
class RetainedDirectory(original):
    def __init__(self,*args,**kwargs):
        kwargs['dir']=base
        super().__init__(*args,**kwargs)
        self._finalizer.detach()
        print(json.dumps({'retained_fixture_root':self.name,'cleanup_policy':'no native Trash; preserve actual ledger/receipt files'}),flush=True)
    def cleanup(self):
        self._finalizer.detach()
tempfile.TemporaryDirectory=RetainedDirectory
p=Path('docs/research/e02-cloud-test-plan/implementation-handoffs/B/current-adapters-evidence/unbound-owner-probe.py')
assert hashlib.sha256(p.read_bytes()).hexdigest()=='175fcffce1cb7aca07efb9d6ed52e8c2bf03fb75b4a74812d4d1e36580600a1a'
runpy.run_path(str(p),run_name='__main__')
