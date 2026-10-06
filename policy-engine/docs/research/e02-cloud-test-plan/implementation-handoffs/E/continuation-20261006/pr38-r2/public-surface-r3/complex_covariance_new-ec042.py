from pathlib import Path
import subprocess,hashlib
EXPECTED='ec042402ec91fbdcb51006852e29fe67f38d9452'
import json,warnings
import numpy as np
from polisyos.foundry.uncertainty import PropagationConfig
from polisyos.foundry.uncertainty.monte_carlo import MonteCarloPropagator
from polisyos.ir.analytics.uncertainty import DistributionFamily,IntervalSemantics,PropagationMethod,UncertaintyEnvelope,UncertaintySource
import polisyos.foundry.uncertainty.sampling_admission as owner
SOURCE=Path(owner.__file__).resolve();ROOT=Path('/workspace/e02-E-continuation-20261006');p='policy-engine/src/polisyos/foundry/uncertainty/sampling_admission.py';expected=subprocess.check_output(['git','show',EXPECTED+':'+p],cwd=ROOT);assert SOURCE.read_bytes()==expected;before=hashlib.sha256(SOURCE.read_bytes()).hexdigest()
calls=[]
env=UncertaintyEnvelope(point_estimate=0.,confidence_interval=(-1.96,1.96),confidence_level=.95,distribution_family=DistributionFamily.NORMAL,source=UncertaintySource.CALIBRATION,propagation_method=PropagationMethod.NONE,interval_semantics=IntervalSemantics.CONFIDENCE_INTERVAL,gate_eligible=False,metadata={'std':1.,'covariance_params':['x'],'covariance_row':np.array([1.+5j])})
with warnings.catch_warnings(record=True) as observed:
 warnings.simplefilter('always'); result=MonteCarloPropagator(PropagationConfig(mc_n_samples=100,compute_sensitivity=False)).propagate(lambda **p:calls.append(p) or {'y':p['x']},{'x':0.},{'x':env},['y'])[0]
print(json.dumps({'exact_source':EXPECTED,'law':'declared Normal with unsupported complex covariance row[1+5j]','callback_count':len(calls),'family':result.envelope.distribution_family.value,'gate_eligible':result.envelope.gate_eligible,'warnings':[str(w.message) for w in observed],'failure':result.envelope.metadata.get('failure')},indent=2))

assert hashlib.sha256(SOURCE.read_bytes()).hexdigest()==before
assert calls==[] and result.envelope.distribution_family is DistributionFamily.UNKNOWN and not result.envelope.gate_eligible
