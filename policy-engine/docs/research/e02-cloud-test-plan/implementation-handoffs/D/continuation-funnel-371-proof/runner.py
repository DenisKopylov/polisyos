import hashlib,json,pathlib,subprocess,sys
import pytest
class Origins:
 def pytest_sessionfinish(self,session,exitstatus):
  lane=pathlib.Path('/workspace/e02-D-published-funnel/policy-engine')
  names=['polisyos.core.llm.response','polisyos.core.llm.settlement','polisyos.core.llm.traced_client','polisyos.scientist.orchestration.engine.budget_ledger','polisyos.scientist.orchestration.engine.budget_middleware','polisyos.scientist.orchestration.llm.budget_enforcer','polisyos.scientist.orchestration.llm.factory','polisyos.scientist.orchestration.llm.gateway_client','polisyos.scientist.methods.search.funnel.types','polisyos.scientist.methods.search.funnel.orchestrator','polisyos.scientist.methods.search.funnel.level5_refutation_governance','polisyos.scientist.policy_design.translator','polisyos.scientist.policy_design.adversary','polisyos.scientist.methods.doe.stress_report','polisyos.scientist.methods.search.adversarial']
  results=[]
  for name in names:
   module=sys.modules.get(name);p=pathlib.Path(module.__file__).resolve() if module else None
   local=p is not None and p.is_relative_to(lane/'src')
   actual=hashlib.sha256(p.read_bytes()).hexdigest() if p else None
   expected=hashlib.sha256(subprocess.check_output(['git','show','HEAD:policy-engine/'+str(p.relative_to(lane))])).hexdigest() if local else None
   results.append({'module':name,'file':str(p),'sha256':actual,'tracked_frozen_sha256':expected,'PASS':local and actual==expected})
  print('E02_RUNTIME_ORIGINS='+json.dumps(results,sort_keys=True))
  if not all(r['PASS'] for r in results):session.exitstatus=1
raise SystemExit(pytest.main(sys.argv[1:],plugins=[Origins()]))
