"""Remove shared guard at runtime, retaining public function identities and names."""
import argparse,hashlib,json,math,warnings
from pathlib import Path
import numpy as np
import polisyos.foundry.uncertainty as f
from polisyos.foundry.uncertainty import sampling_admission as c
from polisyos.foundry.uncertainty.monte_carlo import MonteCarloPropagator
from polisyos.ir.analytics.uncertainty import DistributionFamily,IntervalSemantics,PropagationMethod,UncertaintyEnvelope,UncertaintySource
P=argparse.ArgumentParser();P.add_argument('--entry',choices=['mc','pilot'],required=True);args=P.parse_args()
source=Path(c.__file__);before=hashlib.sha256(source.read_bytes()).hexdigest();identities={n:getattr(f,n) for n in ['admit_empirical_weights','empirical_cdf','admit_unit_uniform']}
def unsafe_real(values):return np.asarray(values,dtype=np.float64)
c._real_float64.__code__=unsafe_real.__code__
assert all(getattr(f,n) is value is getattr(c,n) and n in f.__all__ for n,value in identities.items()) and len(f.__all__)==19
if args.entry=='mc':
 calls=[];env=UncertaintyEnvelope(point_estimate=0.,confidence_interval=(-1.96,1.96),confidence_level=.95,distribution_family=DistributionFamily.NORMAL,source=UncertaintySource.CALIBRATION,propagation_method=PropagationMethod.NONE,interval_semantics=IntervalSemantics.CONFIDENCE_INTERVAL,gate_eligible=False,metadata={'std':1.,'covariance_params':['x'],'covariance_row':np.array([1.+5j])})
 result=MonteCarloPropagator(f.PropagationConfig(mc_n_samples=100,compute_sensitivity=False)).propagate(lambda **p:calls.append(p) or {'y':p['x']},{'x':0.},{'x':env},['y'])[0]
 assert hashlib.sha256(source.read_bytes()).hexdigest()==before
 print(json.dumps({'entry':'actual native MC','callback_count':len(calls),'family':result.envelope.distribution_family.value,'export_names_and_canonical_identities_retained':True,'source_files_unchanged':True}),flush=True)
 assert calls==[], 'shared domain guard removed: actual native MC reached101 callbacks with complex covariance'
else:
 emitted=None
 try:emitted=c.frozen_bernstein_budget(np.full(256,1j),c.BoundedIIDMeanPlan(metric_id='fixture-y'))
 except ValueError:pass
 assert hashlib.sha256(source.read_bytes()).hexdigest()==before
 print(json.dumps({'entry':'actual frozen bounded-pilot budget producer','emitted':emitted,'export_names_and_canonical_identities_retained':True,'source_files_unchanged':True}),flush=True)
 assert emitted is None, 'shared domain guard removed: complex pilot emitted mainN408 certificate'
