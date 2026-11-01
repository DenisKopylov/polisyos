"""Independent stdlib illustrations, not repository code/tests or execution evidence."""
from fractions import Fraction
from itertools import combinations
import json, math, statistics
from pathlib import Path

def hv(points):
    s=0
    for k in range(1,len(points)+1):
        for selected in combinations(points,k):
            s+=(-1)**(k+1)*math.prod(min(p[d] for p in selected) for d in range(3))
    return s

def rho(x,y):
    def ranks(v):
        return [1+sorted(v).index(i) for i in v]
    return statistics.correlation(ranks(x),ranks(y))
A=[(10,1,1),(1,10,1),(1,1,10)];B=[(4,4,4)]
out={
 'status':'INDEPENDENT_STDLIB_ARITHMETIC_ONLY_NOT_PRODUCT_TEST',
 'confusion':{'TP':0,'FP':0,'FN':10,'TN':990,'declared_window':1000,'FOR':float(Fraction(10,1000)),'FNR':float(Fraction(10,10))},
 'zero_errors_five_iid_bernoulli':{'one_sided_confidence_illustration':0.95,'upper_bound':1-math.pow(.05,1/5),'policy_confidence_not_assigned':True},
 'finite_proposal_search':{'domain_size':100,'seen':99,'uniform_attempts':20,'miss_remaining_probability':math.pow(.99,20)},
 'hypervolume':{'reference':[0,0,0],'maximize':True,'A':A,'B':B,'A_bbox':1000,'A_exact':hv(A),'B_bbox':64,'B_exact':hv(B)},
 'score_zero':{'declared_predictions':[0,1,2],'truth':[0,1,2],'objective_fallback':[3,1,2],'correct_rho':rho([0,1,2],[0,1,2]),'truthiness_fallback_rho':rho([3,1,2],[0,1,2])},
 'heterogeneous_pairs':{'u':[-1,0,1],'model':'Y=U+(2+U)*a','baseline':[-1,0,1],'policy':[0,2,4],'paired_effects':[1,2,3],'mean':2,'SE':1/math.sqrt(3),'wrong_reversed_baseline_effects':[-1,2,5],'wrong_SE':3/math.sqrt(3)},
 'hnsw_snapshot_scaling':{'assumption':'serialized size B(k) proportional to k for append-only rows','N_calls_cumulative_units':'N*(N-1)/2','not_measured_runtime_or_memory':True}}
levels=[0.5,0.8,0.95,0.99,math.nextafter(1.0,0.0),math.nextafter(0.0,1.0)]
quantiles=[]
for c in levels:
    q=(1-c)/2
    if q==0.5:
        quantiles.append({'confidence':c,'lower_tail':q,'status':'positive_confidence_lost_in_float_tail_projection','quantile':None,'mean_trajectory_not_invalidated':True})
    else:
        z=-statistics.NormalDist().inv_cdf(q)
        tail=0.5*math.erfc(z/math.sqrt(2))
        quantiles.append({'confidence':c,'lower_tail':q,'quantile':z,'independent_erfc_tail':tail,'tail_relative_residual':abs(tail-q)/q,'upper_probability_would_be':1-q})
out['deterministic_normal_quantile']={'status':'STDLIB_ONLY_NOT_NATIVE_PRODUCT','rows':quantiles,'float_profile':'host Python math/statistics; not a claim of target native execution or population CI coverage'}
Path(__file__).with_name('independent_arithmetic.json').write_text(json.dumps(out,indent=2))
print(json.dumps(out,indent=2))
