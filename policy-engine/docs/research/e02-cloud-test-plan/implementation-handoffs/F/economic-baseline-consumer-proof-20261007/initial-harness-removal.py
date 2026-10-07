from pathlib import Path
import sys,hashlib,json
import pytest
kind=sys.argv[1]
if kind=='gini-domain':
 import polisyos.foundry.agent_sim.distributions as module
 original=module._admit_classical_gini_population
 module._admit_classical_gini_population=lambda values,active_mask:values
 selectors=['tests/unit/foundry/agent_sim/test_signed_gini_producer_route.py']
 print('in-memory canonical admission removal; names/signatures/producers/scheduler/state/RNG preserved')
elif kind in ['baseline-sign','baseline-guard']:
 import polisyos.foundry.plugins.economics.baselines as module
 original=module.normalized_income_budget_loss
 if kind=='baseline-sign':
  source=Path(module.__file__).read_text();assert source.count('objective_loss = -avg_income / income_scale')==1
  exec(compile(source.replace('objective_loss = -avg_income / income_scale','objective_loss = avg_income / income_scale'),module.__file__,'exec'),module.__dict__)
  import polisyos.foundry.methods._internal.loss as internal
  import polisyos.foundry.methods.loss as public
  internal.policy_loss_fn=public.policy_loss_fn=module.normalized_income_budget_loss
 else:module.finite_loss_or_inf=lambda value:value
 selectors=['tests/unit/foundry/plugins/test_historical_income_baseline.py']
 print('in-memory canonical baseline '+kind+' removal; function names/native fields/aliases/import owner preserved')
else:raise ValueError(kind)
p=Path(module.__file__);b=p.read_bytes();print(json.dumps({'canonical_module_path':str(p),'source_bytes':len(b),'source_sha256':hashlib.sha256(b).hexdigest(),'kind':kind,'selectors':selectors}))
sys.exit(pytest.main(['-p','no:cacheprovider','-p','origin_plugin',*selectors,'-v','--tb=short','--junitxml=/tmp/e02-F-continuation-20261007/economics/removal-'+kind+'.xml']))
