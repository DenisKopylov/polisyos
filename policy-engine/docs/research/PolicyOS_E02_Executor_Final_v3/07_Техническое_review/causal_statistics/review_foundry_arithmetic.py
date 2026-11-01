"""Independent stdlib-only finite arithmetic; never imports repository/science packages."""
import json, math, statistics, struct
from fractions import Fraction
from decimal import Decimal, localcontext
from itertools import permutations
from pathlib import Path

def f32(x): return struct.unpack('f',struct.pack('f',x))[0]
report={'execution':'STANDARD_LIBRARY_ONLY; NOT_PRODUCT_TESTS','native':'NOT_RUN'}
K=f32(1+f32(1e-8)); lognormal=-.5*(1+math.log(2*math.pi)); ppo=[]
for rs in [(1.3,.7),(.9,1.1),(.7,1.3)]:
 old=[f32(lognormal-math.log(r)) for r in rs]; r=[math.exp(lognormal-o) for o in old]
 contributions=[]; derivatives=[]
 for ri,a,action in zip(r,[1/K,-1/K],[1,-1]):
  clip=max(.8,min(1.2,ri)); unclipped=ri*a; clipped=clip*a
  contributions.append(-min(unclipped,clipped)/2)
  derivative=-ri*a/2 if unclipped<clipped or .8<ri<1.2 else 0
  derivatives.append(derivative)
 ppo.append({'ideal_ratios':rs,'stored_old_lp':old,'actual_reference_ratios':r,'loss':sum(contributions),'d_log_ratios':derivatives,'d_mu':derivatives[0]-derivatives[1]})
report['ppo']={'K':K,'policy_cases':ppo,'component_cases':[]}
H0=.5*(1+math.log(2*math.pi))
for cv,ce in [(.5,0),(.25,0),(0,.1),(0,.2),(.5,.1),(.25,.2)]:
 cv,ce=f32(cv),f32(ce)
 report['ppo']['component_cases'].append({'cv_float32':cv,'ce_float32':ce,'value_loss':5,'entropy':H0,'policy_loss':0,'total':5*cv-ce*H0,'d_nu':-4*cv,'d_log_std':-ce})
def gae(ds):
 adv=[0,0]; ret=[0,0]; next_adv=0; next_v=1
 for t in [1,0]:
  v=[.25,.5][t]; keep=not ds[t]
  delta=[1,2][t]+.5*next_v*keep-v
  adv[t]=delta+.5*next_adv*keep;ret[t]=adv[t]+v;next_adv=adv[t];next_v=v
 return {'dones':ds,'returns':ret,'advantages':adv}
report['gae']=[gae(x) for x in [(False,False),(False,True),(True,True)]]
report['calibration']={'f32_scale_plus_epsilon':f32(f32(1)+f32(1e-8)),'cases':[],'overflow_square_approx':(3e38/10)**2}
for w in [(9,1),(1,9)]:
 base=w[0]+81*w[1]; grad=-2*w[0]-18*w[1]; hess=2*sum(w)
 def loss(theta):return w[0]*(theta-1)**2+w[1]*(theta-9)**2+6
 h=.125
 report['calibration']['cases'].append({'weights':w,'weighted':base,'total':base+6,'physical_gradient':grad,'physical_hessian':hess,'u_gradient':grad*.25,'u_hessian':hess/16,'central_hessian':(loss(h)-2*loss(0)+loss(-h))/h**2})
report['backtest']=[]
with localcontext() as ctx:
 ctx.prec=1200
 for xs in [[0.,1e308],[1e154,1e154],[1e308],[1e308,1e308]]:
  ds=list(map(Decimal.from_float,xs));n=Decimal(len(xs));sse=sum(x*x for x in ds);mae=sum(ds)/n;rmse=(sse/n).sqrt()
  scale=max(xs);scaled=scale*math.sqrt(sum((x/scale)**2 for x in xs)/len(xs)) if scale else 0
  report['backtest'].append({'residuals':xs,'mae':float(mae),'rmse_decimal':float(rmse),'rmse_scaled':scaled,'relative_error':abs(scaled-float(rmse))/float(rmse) if rmse else 0,'SSE_representable':sse<=Decimal.from_float(float.fromhex('0x1.fffffffffffffp1023'))})
report['means']=[]
for xs in [[1e308,1e308],[1e308,-1e308], [1.,3.], [1e308,-1e308,3*math.ulp(0.)]]:
 exact=float(sum(map(Fraction.from_float,xs))/len(xs))
 with localcontext() as ctx:
  ctx.prec=1200; decimal=float(sum(map(Decimal.from_float,xs))/Decimal(len(xs)))
 variations=[statistics.mean(list(p)) for p in permutations(xs)]
 report['means'].append({'inputs':xs,'statistics_mean':statistics.mean(xs),'fraction_reference':exact,'decimal_reference':decimal,'permutations_equal':all(v==exact for v in variations),'whole_multiset_repeat_equal':statistics.mean(xs*3)==exact})
report['pca_analytic']={'small_singular_values_squared':[60,2/3],'small_explained_variance_ratio':[90/91,1/91],'capped_rank1_ratio':6/25,'M_grid_num_levels8_centered_rank_upper_bound':63,'M_grid_num_levels4_centered_rank_upper_bound':15,'M_SALib_preflight':'NOT_RUN; cannot claim two of four declared seeds pass'}
cols={j:[math.sqrt(2/600)*math.cos(math.pi*(i+.5)*j/600) for i in range(600)] for j in [1,2,3,4,5,6,100]}
report['pca_analytic']['DCT_max_column_mean']=max(abs(math.fsum(v)/600) for v in cols.values())
report['pca_analytic']['DCT_max_orthogonality_error']=max(abs(math.fsum(a*b for a,b in zip(cols[j],cols[k]))-(j==k)) for j in cols for k in cols)
s2=[2**(-j/2) for j in range(1,101)]
report['pca_analytic']['DCT_first5_ratios']=[x/math.fsum(s2) for x in s2[:5]]
report['pca_analytic']['DCT_optimal_rank5_residual']=math.sqrt(math.fsum(s2[5:]))
# Matrix oracle is analytic; neither PCA nor SALib is executed.
out=Path(__file__).with_suffix('.json');out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(out);print(json.dumps(report,ensure_ascii=False,indent=2))
