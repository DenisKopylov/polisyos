"""Exact property removal on canonical code with actual filesystem accounting."""
import hashlib, json, os, subprocess, sys
from decimal import Decimal
from pathlib import Path
from polisyos.scientist.orchestration.engine import budget_ledger as module
from polisyos.scientist.orchestration.engine.budget import BudgetLimit, BudgetState
root = Path('/workspace/e02-B-current-durability')
expected = '2c52e1fe747627b227b5695e578b800cb7eade8b'
path = Path(sys.argv[2]).resolve()
assert not path.exists()
origin = Path(module.__file__).resolve()
assert origin == root/'policy-engine/src/polisyos/scientist/orchestration/engine/budget_ledger.py'
source_bytes = subprocess.check_output(['git','show',f'{expected}:policy-engine/src/polisyos/scientist/orchestration/engine/budget_ledger.py'],cwd=root)
assert source_bytes == origin.read_bytes()
source = source_bytes.decode()
needle = 'existing = snapshot.spend_receipts.get(event_id)'
assert source.count(needle) == 1
if sys.argv[1] == 'removal':
    changed = source.replace(needle, 'existing = None')
    exec(compile(changed, str(origin), 'exec'), module.__dict__)
else:
    assert sys.argv[1] == 'control'
ledger = module.FileBudgetLedger(path, mutation_history_limit=1)
ledger.load_or_bootstrap(BudgetState(limits={'run':BudgetLimit(key='run',max_usd=Decimal('10'))}))
args = dict(event_id='observed-producer-1:run',key='run',amount=Decimal('2'),provider='provider',payload_digest=hashlib.sha256(b'actual immutable result').hexdigest())
first = ledger.settle_spend(**args)
second = ledger.settle_spend(**args)
# Fresh actual unmodified source reads the resulting complete record.
reopen = subprocess.run([sys.executable,'-c', 'import json,sys; from pathlib import Path; from polisyos.scientist.orchestration.engine import budget_ledger as m; assert Path(m.__file__).resolve().is_relative_to(Path(sys.argv[2])); s=m.FileBudgetLedger(Path(sys.argv[1])).snapshot();print(s.model_dump_json())',str(path),str(root/'policy-engine/src')],cwd=root/'policy-engine',env={**os.environ,'PYTHONPATH':str(root/'policy-engine/src')},capture_output=True,text=True,check=True)
state = json.loads(reopen.stdout)
print(json.dumps({'mode':sys.argv[1],'source_sha':expected,'source_sha256':hashlib.sha256(source_bytes).hexdigest(),'property_removal':needle+' -> existing = None' if sys.argv[1]=='removal' else None,'path':str(path),'first_receipt':first.model_dump(mode='json'),'second_receipt':second.model_dump(mode='json'),'actual_fresh_reopen':state},indent=2),flush=True)
assert state['state']['spent']['run'] == '2', 'same producer event was charged twice'
assert first == second, 'exact retry lost its original durable acknowledgment'
