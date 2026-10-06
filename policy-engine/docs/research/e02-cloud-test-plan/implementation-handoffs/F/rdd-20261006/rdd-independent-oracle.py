import os,sys,json,subprocess,pathlib,hashlib,importlib.metadata,itertools
import numpy as np
from rdrobust import rdrobust
root=pathlib.Path('/workspace/e02-F-rdd-20261006/policy-engine')
rows=[]
for index,(p,kernel,h,b,level) in enumerate(itertools.product((1,2),('triangular','uniform','epanechnikov'),(.35,.6),(.45,),(.8,.95,.99))):
 rng=np.random.default_rng(95100+index);z=rng.uniform(-1,1,500);x=z+.12;y=np.sin(3*z)+(3+z*z)*(z>=0)+rng.normal(size=len(z))*(.25+.25*(z>=0))
 rows.append({'x':x.tolist(),'y':y.tolist(),'cutoff':.12,'settings':{'bias_correction':True,'bandwidth':h,'bias_bandwidth':b,'polynomial_order':p,'kernel':kernel,'confidence_level':level,'manipulation_test':False}})
code='''import json,sys,pathlib,hashlib; import numpy as np
from polisyos.foundry.methods.catalog.causal.rdd import RegressionDiscontinuity as M
from polisyos.foundry.methods.catalog.causal.protocols import RDDObservationalData
out=[]
for row in json.load(sys.stdin):
 r=M.pure_step(RDDObservationalData(running_variable=row['x'],outcome=row['y'],cutoff=row['cutoff']),row['settings'])['report']
 assert r.status.value=='success',r.status_reason
 out.append({'point':r.point_estimate,'se':r.standard_error,'ci':r.confidence_interval,'tau_us':r.method_params['tau_us'],'se_us':r.method_params['se_us']})
import polisyos.foundry.methods.catalog.causal.rdd as owner
print(json.dumps({'rows':out,'owner':owner.__file__,'sha256':hashlib.sha256(pathlib.Path(owner.__file__).read_bytes()).hexdigest(),'python':sys.version}))'''
env=os.environ.copy();env['PYTHONPATH']='src:.';env['PYTHONDONTWRITEBYTECODE']='1'
child=subprocess.run(['/workspace/e02-F-closeout-20261006/policy-engine/.venv/bin/python','-c',code],cwd=root,env=env,input=json.dumps(rows).encode(),capture_output=True)
assert child.returncode==0,child.stderr.decode();native=json.loads(child.stdout);assert len(native['rows'])==36
comparisons=[]
for row,actual in zip(rows,native['rows'],strict=True):
 s=row['settings'];fit=rdrobust(row['y'],row['x'],c=row['cutoff'],p=s['polynomial_order'],q=s['polynomial_order']+1,h=s['bandwidth'],b=s['bias_bandwidth'],kernel=s['kernel'],vce='hc0',masspoints='off',level=s['confidence_level']*100)
 estimate=fit.Estimate.loc['Estimate'];expected={'point':float(estimate['tau.bc']),'se':float(estimate['se.rb']),'ci':fit.ci.loc['Robust'].values.tolist(),'tau_us':float(estimate['tau.us']),'se_us':float(estimate['se.us'])}
 errors={k:float(np.max(np.abs(np.asarray(actual[k])-np.asarray(expected[k])))) for k in actual}
 assert all(np.allclose(actual[k],expected[k],atol=5e-9,rtol=5e-9) for k in actual),errors
 comparisons.append({'settings':s,'actual':actual,'reference':expected,'abs_errors':errors})
receipt={'source_sha':subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),'outcome':'PASS','native':native,'oracle':{'python':sys.version,'executable':sys.executable,'rdrobust':importlib.metadata.version('rdrobust')},'scope':'36 new independently generated nonpolynomial heteroskedastic panels; finite sharp fixed HC0 profile, no coverage/real-data claim','cases':comparisons,'child_exit':child.returncode,'child_stderr':child.stderr.decode()}
path=pathlib.Path('/workspace/e02-F-20261006-receipts/cau/rdd-independent-oracle.json');path.write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps({'outcome':'PASS','case_count':36,'source_sha':receipt['source_sha'],'max_absolute_errors':{k:max(c['abs_errors'][k] for c in comparisons) for k in actual}}))
