from pathlib import Path
import copy, hashlib, json, re, subprocess, tomllib

R=Path('/workspace/e02-E-continuation-20261006');P=R/'policy-engine';O=Path(__file__).parent
REF='7dc540d08d30bad8cf23744172c253c934dfc77e';BASE='bf3b54c3a894d2d9d9bfb0cd13edb13177405f33'
paths=subprocess.check_output(['git','diff','--name-only',BASE,REF],cwd=R,text=True).splitlines()
assert set(paths)=={'policy-engine/architecture/public_surface/inventory.json','policy-engine/docs/reference/public-surface.md','policy-engine/src/polisyos/foundry/uncertainty/README.md'}
hashes={}
for path in paths:
    data=subprocess.check_output(['git','show',REF+':'+path],cwd=R)
    assert (R/path).read_bytes()==data;hashes[path]=hashlib.sha256(data).hexdigest()
for path,generated in [('architecture/public_surface/inventory.json','inventory.json'),('docs/reference/public-surface.md','public-surface.md'),('docs/reference/generated-artifacts.md','generated-artifacts.md')]:
    assert (P/path).read_bytes()==(O/'generated-bf3'/generated).read_bytes()
data=json.loads((P/'architecture/public_surface/inventory.json').read_text());readme=(P/'src/polisyos/foundry/uncertainty/README.md').read_text()
release=tomllib.loads((P/'release-fragments/unreleased/2026-10-06-e02-foundry-calibration-reader.toml').read_text())
def entry(x,module):return next(e for p in x['packages'] for e in p['entrypoints'] if e['module']==module)
def validate(x,doc,fragment):
    assert x==json.loads((O/'generated-bf3/inventory.json').read_text())
    assert entry(x,'polisyos.calibration')['export_count']==29
    assert entry(x,'polisyos.foundry.uncertainty')['export_count']==20
    assert 'load_foundry_calibration_report' in entry(x,'polisyos.foundry.uncertainty')['exports']
    assert re.search('Exports: 20 names declared',doc)
    assert fragment['surface_classification']=='public_stable'
validate(data,readme,release);controls=[]
for label in ['stale-uncertainty-count19','omitted-reader-export-count20-retained','fake-lazy-mode','stale-readme-count19','wrong-classification']:
    corrupt=copy.deepcopy(data);doc=readme;fragment=copy.deepcopy(release)
    if label=='stale-uncertainty-count19':entry(corrupt,'polisyos.foundry.uncertainty')['export_count']=19
    elif label=='omitted-reader-export-count20-retained':entry(corrupt,'polisyos.foundry.uncertainty')['exports'].remove('load_foundry_calibration_report')
    elif label=='fake-lazy-mode':entry(corrupt,'polisyos.foundry.uncertainty')['facade_mode_observed']='lazy_facade'
    elif label=='stale-readme-count19':doc=doc.replace('Exports: 20 names declared','Exports: 19 names declared')
    else:fragment['surface_classification']='public_experimental'
    try:validate(corrupt,doc,fragment)
    except AssertionError:controls.append({'case':label,'outcome':'REJECTED'})
    else:raise AssertionError('corrupt publication property admitted')
for path,h in hashes.items():assert hashlib.sha256((R/path).read_bytes()).hexdigest()==h
result={'source_sha':BASE,'source_tree':'0a414803650c9646b597ba24c93afbea0632dcd1','companion_sha':REF,'companion_tree':subprocess.check_output(['git','rev-parse',REF+'^{tree}'],cwd=R,text=True).strip(),'exact_footprint':paths,'property_paths':hashes,'before_after_equal':True,'canonical_generator_byte_equal':True,'counts':{'Calibration':29,'Foundry uncertainty':20},'source_Python_unchanged':True,'new_reader_release_classification':release['surface_classification'],'inventory_reviewed_flag_at_this_candidate':release['public_surface_inventory_reviewed'],'flag_followup':'Owner may append true companion after this independent canonical confirmation; validate that exact one-line delta separately.','controls':controls,'publication_verdict':'GO-bounded-owned-canonical-publication','global_guard':'UNRUN by reviewer; no inherited/global PASS asserted','Core_IR_execute_decisions':'not_ratified/unapplied'}
(O/'publication-review20.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
