from pathlib import Path
import hashlib,importlib,json,subprocess
import pytest
source='964c76dad1dc9f56bd89e2216bded373f0e66883'
functions={
 'polisyos.foundry.agent_sim.distributions':['compute_distribution_aware_reward'],
 'polisyos.foundry.agent_sim.analysis':['BehaviorAnalyzer.counterfactual_analysis'],
 'polisyos.foundry.agent_sim.metrics':['standard_training_metrics'],
 'polisyos.foundry.agent_sim.modes':['social_welfare_objective'],
 'polisyos.foundry.agent_sim.government_policy':['build_government_welfare_reward'],
 'polisyos.foundry.plugins.economics.objectives':['GiniObjective.evaluate','SocialWelfareObjective.evaluate'],
}
rows=[]
for name,attributes in functions.items():
 m=importlib.import_module(name);path='policy-engine/src/'+name.replace('.','/')+'.py';raw=subprocess.check_output(['git','show',source+':'+path]);ns=dict(vars(m));exec(compile(raw,source+':'+path,'exec'),ns)
 for attribute in attributes:
  if '.' in attribute:
   cls,member=attribute.split('.');setattr(getattr(m,cls),member,vars(ns[cls])[member])
  else:setattr(m,attribute,ns[attribute])
 rows.append(dict(path=path,source_sha=source,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),functions=attributes))
print(json.dumps(dict(mode='pre-ABI Git native functions restored; canonical equations/admission unchanged',source_bindings=rows),indent=2),flush=True)
raise SystemExit(pytest.main(['tests/unit/foundry/agent_sim/test_gini_consumers.py','-k','dtype_abi or carry_dtype','-q','-ra','--tb=short','--junitxml=/tmp/e02-F-continuation-20261006/economics/gini-consumer-dtype-pre-ABI.xml']))
