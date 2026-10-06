"""Remove numerical encoding mechanisms while retaining canonical names/fields."""
from __future__ import annotations
import importlib
import hashlib
import json
import subprocess
import sys
import pytest

BASE='4128879c3cec37dcb2bd1e7f91a1da5e4f51d2d3'
mode=sys.argv[1]
if mode=='temporal':
 module='polisyos.foundry.agent_sim.temporal_mechanisms'
 functions=['TemporalConsumptionMechanism.apply']
 selectors=['tests/unit/foundry/agent_sim/test_temporal_consumption_dtype.py']
elif mode=='carry':
 module='polisyos.foundry.agent_sim.jit_training'
 functions=['create_jit_trainer','create_jit_trainer_with_metrics']
 selectors=['tests/unit/foundry/agent_sim/test_training_dtype.py::test_real_plain_and_metric_trainer_promotes_loss_carry_and_preserves_parameters']
elif mode=='storage':
 module='polisyos.foundry.agent_sim.metrics'
 functions=['MetricsBuffer.write_scalar_at','MetricsBuffer.write_histogram_at']
 selectors=['tests/unit/foundry/agent_sim/test_training_dtype.py::test_metric_scalar_storage_explicitly_encodes_destination_dtype','tests/unit/foundry/agent_sim/test_training_dtype.py::test_metric_histogram_storage_encodes_fixed_dtype_after_finite_sample_equation']
else:
 raise SystemExit(mode)
mod=importlib.import_module(module)
path='policy-engine/src/'+module.replace('.','/')+'.py'
blob=subprocess.check_output(['git','show',BASE+':'+path]);ns=dict(vars(mod))
exec(compile(blob,BASE+':'+path,'exec'),ns)
for function in functions:
 if '.' in function:
  cls,member=function.split('.')
  getattr(getattr(mod,cls),member).__code__=getattr(ns[cls],member).__code__
 else:
  getattr(mod,function).__code__=ns[function].__code__
print(json.dumps({'mode':mode,'base_sha':BASE,'restored_source':path,'bytes':len(blob),'sha256':hashlib.sha256(blob).hexdigest(),'functions':functions,'markers':'Canonical class, function names, state fields, RNG law and storage keys remain; only forward encoding/carry mechanism removed.'}),flush=True)
raise SystemExit(pytest.main(selectors+sys.argv[2:]))
