import pathlib,json,math,hashlib,io,statistics
import torch
P=pathlib.Path('/dev/shm/e02-D-post-a795-88ghpj7t/gp/publication-current-CBC46-gp-state')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def scalar(v):
 while isinstance(v,list):v=v[0]
 return float(v)
def close(a,b,tol=1e-9):
 assert len(a)==len(b)
 e=max((abs(x-y) for x,y in zip(a,b)),default=0)
 assert e<tol,(e,tol)
 return e
def cholesky(c):
 n=len(c);l=[[0.0]*n for _ in range(n)]
 for i in range(n):
  for j in range(i+1):
   s=c[i][j]-sum(l[i][k]*l[j][k] for k in range(j))
   l[i][j]=math.sqrt(s) if i==j else s/l[j][j]
 return l
def solve(l,b):
 n=len(l);z=[0.0]*n;v=[0.0]*n
 for i in range(n):z[i]=(b[i]-sum(l[i][j]*z[j] for j in range(i)))/l[i][i]
 for i in reversed(range(n)):v[i]=(z[i]-sum(l[j][i]*v[j] for j in range(i+1,n)))/l[i][i]
 return v
rows=[]
for line in (P/'scopes/gp-defining/stdout.txt').read_text().splitlines():
 i=line.find('{')
 if i>=0:
  try:d=json.loads(line[i:])
  except ValueError:continue
  if d.get('cell') in ('initial-ten-point-independent-oracle','actual-eleven-point-conditioning'):rows.append(d)
assert len(rows)==2
results=[]
for label,receipt in zip(('initial','conditioned'),rows):
 saved=json.loads((P/f'inputs/analytic-{label}.artifact').read_text());meta=saved['metadata']
 weights=torch.load(io.BytesIO(bytes.fromhex(saved['model_state'])),map_location='cpu',weights_only=True)
 w={k:float(v.item()) for k,v in weights.items() if v.numel()==1}
 x=[r[0] for r in meta['train_X']];y=[scalar(v) for v in meta['train_y_bo']];q=rows[0]['queries'];ls=w['covar_module.raw_lengthscale'];noise=w['likelihood.noise_covar.raw_noise'];const=w['mean_module.raw_constant'];offset=w['input_transform._offset'];coef=w['input_transform._coefficient'];mu=w['outcome_transform.means'];std=w['outcome_transform.stdvs']
 assert all(abs(v+50+9*math.sin(5*t)+6*t)<1e-12 for v,t in zip(y,x))
 if label=='initial':
  for k,v in receipt['saved_scalar_parameters'].items():assert abs(w[k]-v)<1e-14
 k=lambda a,b:math.exp(-.5*((a-b)/(coef*ls))**2)
 c=[[k(a,b)+(noise if i==j else 0.0) for j,b in enumerate(x)] for i,a in enumerate(x)]
 l=cholesky(c);alpha=solve(l,[(v-mu)/std-const for v in y]);cross=[[k(a,b) for b in x] for a in q];solves=[solve(l,r) for r in cross]
 mean=[-(mu+std*(const+sum(a*b for a,b in zip(r,alpha)))) for r in cross]
 cov=[[(k(a,b)-sum(u*v for u,v in zip(cross[i],solves[j])))*std**2 for j,b in enumerate(q)] for i,a in enumerate(q)]
 meanerr=close(mean,receipt['expected_cost_mean']);coverr=close([v for r in cov for v in r],[v for r in receipt['expected_full_covariance'] for v in r])
 results.append({'case':label,'rows':len(x),'queries':len(q),'state_sha256':sha(P/f'inputs/analytic-{label}.artifact'),'mean_max_abs_difference':meanerr,'full_covariance_max_abs_difference':coverr,'independent_method':'stdlib math RBF+Cholesky; raw corpus/formula, saved tensors decoded weights_only; no model/kernel/posterior/transform method','true_MLL_count':receipt.get('real_mll_calls',receipt.get('extra_real_mll_calls'))})
pool=json.loads((P/'inputs/actual-CAS-producer-inputs.json').read_text());contents=pool['unique_utf8_content_pool'];cas=[]
for r in pool['records']:
 raw=contents[r['portable_content_key']].encode() if 'portable_content_key' in r else pathlib.Path(r['raw_path']).read_bytes();assert len(raw)==r['blob_bytes'];assert hashlib.sha256(raw).hexdigest()==r['blob_sha256'];assert (r['artifact_id'].removeprefix('sha256:')==r['blob_sha256'])==r['retained_byte_identity']
for case,identity in [('public-runner8',1),('public-runner7',2)]:
 hist=next(r for r in pool['records'] if r['kind']=='search.transfer.history' and r['case']==case);data=json.loads(contents[hist['portable_content_key']]);evals=data['evaluations'];parsed=[]
 for e in evals:
  if e['status']!='success' or e['stage_a_passed'] is not True:continue
  v=e['params']['x'];v=float(v['repr']) if isinstance(v,dict) else float(v)
  score=e['scalar_score'];score=float(score['repr']) if isinstance(score,dict) else float(score)
  assert abs(score-((v-.37)**2+.01))<1e-14;parsed.append((v,-score))
 # native train order is sorted by actual scalarizer, not artifact listing
 parsed.sort(key=lambda r:r[1],reverse=True)
 es=[json.loads(l) for l in (P/'scopes/transfer-public3/fit-events.jsonl').read_text().splitlines()];s=next(e['state'] for e in es if e['event']=='actual_mll_return' and e['identity']==identity);w=s['weights'];rawx=[r[0] for r in parsed];rawy=[r[1] for r in parsed];offset=min(rawx);coef=max(rawx)-offset;mu=statistics.mean(rawy);std=statistics.stdev(rawy)
 ex=[(v-offset)/coef for v in rawx];ey=[(v-mu)/std for v in rawy]
 xerr=close(ex,[r[0] for r in s['train_inputs'][0]],1e-12);yerr=close(ey,s['train_targets'],1e-12)
 for key,val in [('input_transform._offset',offset),('input_transform._coefficient',coef),('outcome_transform.means',mu),('outcome_transform.stdvs',std)]:assert abs(scalar(w[key])-val)<1e-12
 cas.append({'case':case,'actual_rows':len(rawx),'history_ref':hist['artifact_id'],'native_model_class':s['model_class'],'normalized_X_max_abs_difference':xerr,'standardized_Y_max_abs_difference':yerr,'calculation':'parsed real saved history; raw analytic score formula; min/range and sample stdev independent of model transforms','posttest_ref_tamper_phase':'qualified evaluation altered only after successful fit/restore; original matching fullref bytes retained in configured-controller8 pool'})
result={'actual_execution_head':'cbc46a0bc87761bc2267a0daa84da489d6702e89','assessed_product_source':'a795967a80818a61fbc939a8d1b1ec8b0fca6477','analytic':results,'CAS_record_bytes_verified':len(pool['records']),'CAS_to_native_training':cas,'new_fits_or_models_constructed':False}
out=pathlib.Path('/dev/shm/e02-D-post-a795-88ghpj7t/transfer/GP-independent-numeric-and-CAS-reconciliation.json');out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
