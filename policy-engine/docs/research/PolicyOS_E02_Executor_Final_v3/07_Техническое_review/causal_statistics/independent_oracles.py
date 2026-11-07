"""Independent stdlib arithmetic only; imports and executes NO repository code."""
from fractions import Fraction as F
import math,json,pathlib
O=pathlib.Path(__file__).parent
n=12
x=[[F(1),F(i,13)] for i in range(1,13)]
w=[1-r[1] for r in x]
g=[[sum(wi*r[a]*r[b] for wi,r in zip(w,x)) for b in range(2)] for a in range(2)]
d=g[0][0]*g[1][1]-g[0][1]*g[1][0]
b=[[g[1][1]/d,-g[0][1]/d],[-g[1][0]/d,g[0][0]/d]]
h=[[sum(x[i][a]*b[a][c]*x[j][c]*w[j] for a in range(2) for c in range(2)) for j in range(n)] for i in range(n)]
ell=[sum(b[0][a]*x[j][a]*w[j] for a in range(2)) for j in range(n)]
true=sum(t*t for t in ell)
er=sum(w[i]*sum((F(i==j)-h[i][j])**2 for j in range(n)) for i in range(n))
legacy=er/(n-2)*b[0][0]
def cdf_t5(t):
 theta=math.atan(t/math.sqrt(5))
 return .5+theta/math.pi+2*math.sin(2*theta)/(3*math.pi)+math.sin(4*theta)/(12*math.pi)
lo,hi=0.,10.
for _ in range(80):
 mid=(lo+hi)/2
 if cdf_t5(mid)<.975:lo=mid
 else:hi=mid
crit=(lo+hi)/2;se=math.sqrt(.8)
rows=[]
for a in (0,1):
 for xx,rr in [(-1,-1),(1,-1),(-1,1),(1,1)]:rows.append({'A':a,'X':xx,'Y':1+2*a+3*xx+rr})
doc={'status':'INDEPENDENT_STDLIB_ARITHMETIC_NOT_PRODUCT_TESTS','rdd':{'n_side':12,'u':'i/13 i=1..12','kernel':'triangular w=1-u','error_law':'independent mean0 variance1','true_intercept_variance':str(true),'true_float':float(true),'expected_legacy_variance':str(legacy),'legacy_float':float(legacy),'ratio':float(legacy/true),'derivation':'H=X B XtW; E(weighted RSS)=tr((I-H)t W (I-H)); true var=ell tell'},'ols':{'rows':rows,'column_order':['intercept','A','X'],'beta':[1,2,3],'SSE':8,'df_resid':5,'sigma2':1.6,'treatment_variance':.8,'treatment_se':se,'critical_t975_df5':crit,'ci95':[2-crit*se,2+crit*se],'reference':'independent closed CDF: F(t)=.5+theta/pi+2sin(2theta)/(3pi)+sin(4theta)/(12pi), theta=atan(t/sqrt(5)); root via bisection; no scipy/statsmodels/dowhy'},'elasticnet_global_target_scaling':{'derivation':'raw slope=(1-.005*s)/1.005 on training x,y=(-1,1); global s from[-1,1,M]','values':[{'M':m,'s':math.sqrt(2/3+2*m*m/9),'beta':(1-.005*math.sqrt(2/3+2*m*m/9))/1.005}for m in (0,30)]},'shap_game':{'f':'x1*x2+2*x1','background':[[0,0],[2,2]],'target':[1,3],'values':{'empty':4,'1':3,'2':5,'12':5},'phi':[-.5,1.5]}}
(O/'arithmetic_counterexamples.json').write_text(json.dumps(doc,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(doc['ols'],ensure_ascii=False))
