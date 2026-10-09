from __future__ import annotations
import asyncio,json,sys,hashlib
from pathlib import Path
from decimal import Decimal
from tests.integration.runtime_quality.test_e02_recursive_budget_frontier import _run_recursive_fixture
from polisyos.scientist.orchestration.engine.budget import BudgetLimit,BudgetState
from polisyos.runtime.quality.recursive_generation_cycle import RecursiveGenerationCycleRun
from polisyos.pdc import SearchTerminalKind,gy_content_hash
async def main():
 result,*_rest=await _run_recursive_fixture(budget_state=BudgetState(limits={"run":BudgetLimit(key="run",max_usd=Decimal("5"))}))
 assert type(result) is RecursiveGenerationCycleRun
 raw=result.model_dump(mode="json")
 root=next(row for row in raw["nodes"] if row["node_ref"]==raw["root_node_ref"])
 assert root["child_refs"] and root["joint_simulation"] is None and root["composition_certificate"] is None
 original=root["terminal"]
 forged={**original,"kind":SearchTerminalKind.GROUNDED_ADMISSIBLE.value,"reason":"Source-independent forged root outcome","blocking_obligations":[],"budget_kind":None,"costed_plan":None,"data_need_spec":None}
 root["terminal"]=forged
 raw["terminal"]=forged
 raw["content_hash"]=gy_content_hash({k:v for k,v in raw.items() if k!="content_hash"})
 accepted=False;error=None
 try:
  replay=RecursiveGenerationCycleRun.model_validate(raw)
  accepted=replay.terminal.kind is SearchTerminalKind.GROUNDED_ADMISSIBLE
 except Exception as exc:
  error=type(exc).__name__+":"+str(exc)
 origins=[]
 export_root=Path(__file__).resolve().parent/"probe-export/policy-engine"
 for name,module in sorted(sys.modules.items()):
  origin=getattr(module,"__file__",None)
  if name.startswith("polisyos.") and origin and str(origin).endswith('.py'):
   path=Path(origin).resolve();expected=export_root/'src'/Path(*name.split('.')).with_suffix('.py')
   if path.name=='__init__.py':expected=export_root/'src'/Path(*name.split('.'))/'__init__.py'
   origins.append({"module":name,"origin":str(path),"in_export":path.is_relative_to(export_root/'src'),"sha256":hashlib.sha256(path.read_bytes()).hexdigest()})
 print(json.dumps({"source_sha":"b6c3201aca6f8a94f05479269e13cde2dd3e7119","original_root_terminal":original,"forged_root_terminal":forged,"forged_positive_accepted":accepted,"error":error,"origin_count":len(origins),"origins_outside_export":[r for r in origins if not r['in_export']]},indent=2))
 Path(__file__).with_suffix('.origins.json').write_text(json.dumps(origins,indent=2)+'\n')
 # Expected conservative rejection property. Nonzero is a deciding semantic FAIL.
 assert not accepted,"full uncomposed parent accepted rehashed self-asserted grounded terminal"
asyncio.run(main())
