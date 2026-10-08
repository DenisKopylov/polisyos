"""Independent exact arithmetic for mean SEM; no runtime law/authority admission."""
from fractions import Fraction
import math,json

def exact_sem_square(rows):
    x=[Fraction(v) if not isinstance(v,float) else Fraction.from_float(v) for v in rows]
    n=len(x)
    if n<2:return None
    mean=sum(x,Fraction(0))/n
    return sum(((v-mean)**2 for v in x),Fraction(0))/(n*(n-1))

panels=[[-2,0,4,6],[0,0,3],[1,2,3,4],[-3,3,0,0],[-3,3]*5+[0]*6,[0],[2,2,2],[-1e12,0.,1e12],[1e12+0.,1e12+1.,1e12+2.]]
out=[]
for rows in panels:
    var=exact_sem_square(rows)
    out.append({'rows':rows,'n':len(rows),'sem_square_fraction':None if var is None else str(var),'sem':None if var is None else math.sqrt(float(var))})
a=exact_sem_square(panels[3]);b=exact_sem_square(panels[4])
assert a==Fraction(3,2) and b==Fraction(3,8)
assert b/a==Fraction(1,4)
print(json.dumps({'meaning':'Conditional finite-sample sample-mean SEM; not a causal/model CI or independence/regularity certificate','formula':'SEM²=sum_i(x_i-xbar)²/(n*(n-1))','panels':out,'controlled_equal_sample_variance_scaling':{'n_first':4,'n_second':16,'sample_variance_each':6,'sem_ratio':0.5,'basis':'Exact constructed arithmetic panels, not synthetic stochastic sampling coverage.'},'dependent_copy_negative':{'law':'Y_i=Z, Z~N(0,1), same random Z all i','observed_sample_variance':0,'true_mean_variance':1,'conclusion':'Internal source draw count and sample s alone do not certify output independence.'},'finite_rows_not_finite_variance_negative':{'law':'X~N(0,1), Y=exp(0.3X²)','mean':1/math.sqrt(0.4),'second_moment':'infinite','conclusion':'Every finite draw finite does not establish finite variance; regular profile remains an assumption.'},'RQMC_negative':{'method':'fixed Sobol/Halton net, or independent scrambles with pooled individual rows','conclusion':'Pooled row s/sqrt(n) unavailable; independent-scramble replicate-mean mechanism is separate E_source8d reuse input, not supplied by this G slice.'}},indent=2,sort_keys=True))
