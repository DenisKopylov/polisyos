"""Independent exact publication review; no full global guard or checkout edits."""
from pathlib import Path
import ast,copy,hashlib,json,re,subprocess
O=Path(__file__).parent;R=Path('/workspace/e02-E-continuation-20261006');BASE='5d4e01011a0b7e0a3954decdb622a9e9cf1fb787';CANDIDATE='c0f146702219cd3280c3b7d06e9d2bc4c7b95dd6'
def git(*args):return subprocess.check_output(['git',*args],cwd=R)
def blob(ref,path):return git('show',ref+':'+path)
def exports(ref,module):
 p='policy-engine/src/'+module.replace('.','/')+'/__init__.py';t=ast.parse(blob(ref,p));a=[n for n in t.body if isinstance(n,ast.Assign) and any(isinstance(x,ast.Name) and x.id=='__all__' for x in n.targets)];assert len(a)==1;names=ast.literal_eval(a[0].value);f={n.name for n in t.body if isinstance(n,ast.FunctionDef)};return names,'lazy_facade' if names and '__getattr__' in f else 'eager_exports',p
expectedfiles=['policy-engine/architecture/public_surface/inventory.json','policy-engine/docs/reference/public-surface.md','policy-engine/src/polisyos/foundry/uncertainty/README.md']
paths=git('diff','--name-only',BASE,CANDIDATE).decode().splitlines();assert sorted(paths)==sorted(expectedfiles),paths
original=json.loads(blob(BASE,expectedfiles[0]));inventory=json.loads(blob(CANDIDATE,expectedfiles[0]));canonical=(O/'generated-current-final/inventory.json').read_bytes();assert canonical==blob(CANDIDATE,expectedfiles[0]);assert (O/'generated-current-final/public-surface.md').read_bytes()==blob(CANDIDATE,expectedfiles[1]);assert (O/'generated-current-final/generated-artifacts.md').read_bytes()==blob(CANDIDATE,'policy-engine/docs/reference/generated-artifacts.md')
def package(inv,name):return next(x for x in inv['packages'] if x['module']==name)
modules=['polisyos.calibration','polisyos.foundry.uncertainty'];truth={m:exports(CANDIDATE,m) for m in modules}
def entry(inv,name):
 return package(inv,name) if name=='polisyos.calibration' else next(x for x in package(inv,'polisyos.foundry')['entrypoints'] if x['module']==name)
def validate(inv,readme):
 for m,(names,mode,p) in truth.items():
  e=entry(inv,m);assert e['exports']==names,(m,'names');assert e['export_count']==len(names),(m,'count');assert e['facade_mode_observed']==mode,(m,'mode')
 assert re.search(r'Exports: (\d+) names',readme) and int(re.search(r'Exports: (\d+) names',readme)[1])==len(truth['polisyos.foundry.uncertainty'][0]),'README count'
readme=blob(CANDIDATE,expectedfiles[2]).decode();validate(inventory,readme)
a=copy.deepcopy(original);b=copy.deepcopy(inventory)
for inv in [a,b]:
 inv['packages']=[p for p in inv['packages'] if p['module']!='polisyos.calibration'];p=package(inv,'polisyos.foundry');p['entrypoints']=[e for e in p['entrypoints'] if e['module']!='polisyos.foundry.uncertainty']
assert a==b,'unrelated inventory delta'
controls=[]
for label,mut in [('historical-count-markers-retained',lambda inv:entry(inv,'polisyos.calibration').update(export_count=10)),('removed-export-count-marker-retained',lambda inv:entry(inv,'polisyos.foundry.uncertainty')['exports'].remove('verify_mean_certificate')),('mode-marker-forged',lambda inv:entry(inv,'polisyos.foundry.uncertainty').update(facade_mode_observed='lazy_facade'))]:
 x=copy.deepcopy(inventory);mut(x)
 try:validate(x,readme)
 except AssertionError as exc:controls.append({'label':label,'outcome':'REJECTED','reason':str(exc)})
 else:raise AssertionError('corrupt inventory passed '+label)
try:validate(inventory,readme.replace('Exports: 16 names','Exports: 12 names'))
except AssertionError as exc:controls.append({'label':'old-README-current-inventory','outcome':'REJECTED','reason':str(exc)})
else:raise AssertionError('old README passed')
try:validate(original,blob(BASE,expectedfiles[2]).decode())
except AssertionError as exc:controls.append({'label':'exact-base-snapshot-divergence','outcome':'REJECTED','reason':str(exc)})
else:raise AssertionError('old inventory satisfied new exports')
result={'review_role':'independent E-only publication companion reviewer','base_sha':BASE,'candidate_sha':CANDIDATE,'candidate_tree':git('rev-parse',CANDIDATE+'^{tree}').decode().strip(),'verdict':'GO','bounded_claim':'canonical inventory/docs/readme agree with exact existing two owned facades; no global architecture gate or finding closure inferred','changed_paths':paths,'canonical_sync':json.loads((O/'generated-current-final/execution.json').read_text()),'public_surface':{m:{'count':len(v[0]),'mode':v[1],'source_path':v[2],'source_sha256':hashlib.sha256(blob(CANDIDATE,v[2])).hexdigest()} for m,v in truth.items()},'artifact_bytes':{p:{'sha256':hashlib.sha256(blob(CANDIDATE,p)).hexdigest(),'bytes':len(blob(CANDIDATE,p))} for p in paths},'unrelated_inventory_delta':False,'negative_controls':controls,'source_authority':'not_claimed','institutional_or_IR_semantic_authority':'not_claimed','required_owner_packets':'Core/IR/Foundry execute admissions remain not_ratified; proposed patches were exercised only in private fixture','P41_global_red':'not_established; this review measures canonical inventory delta only'}
(O/'owned-companion-review.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'verdict':result['verdict'],'candidate_sha':CANDIDATE,'tree':result['candidate_tree'],'controls':controls,'surface':result['public_surface']},indent=2))
