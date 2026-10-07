from pathlib import Path
import hashlib,json,subprocess
O=Path(__file__).parent;R=Path('/workspace/e02-E-continuation-20261006');F=O/'fixture-current'
ref='8486baad6fdef8063cfaad80b15f6b6d8532460a';paths=['policy-engine/src/polisyos/calibration/__init__.py','policy-engine/src/polisyos/calibration/forecast_bridge.py','policy-engine/src/polisyos/scientist/methods/backtesting/forecast_owner.py']
rows=[]
for p in paths:
 b=subprocess.check_output(['git','show',ref+':'+p],cwd=R);old=(F/p).read_bytes();(F/p).write_bytes(b);rows.append({'path':p,'overlay_source_sha':ref,'before_sha256':hashlib.sha256(old).hexdigest(),'after_sha256':hashlib.sha256(b).hexdigest(),'bytes':len(b)})
p='policy-engine/architecture/production_quality/method_catalog_dependency_digest_domains.toml'; refbase='31059ec77f9add8651667967a4b1a51acfab6d24';b=subprocess.check_output(['git','show',refbase+':'+p],cwd=R);(F/p).parent.mkdir(parents=True,exist_ok=True);(F/p).write_bytes(b);rows.append({'path':p,'overlay_source_sha':refbase,'sha256':hashlib.sha256(b).hexdigest(),'bytes':len(b),'reason':'native execution producer imports tracked method digest registry'})
(O/'future-fixture-inputs.json').write_text(json.dumps({'is_git_candidate':False,'fixture_base_sha':refbase,'overlay_rows':rows,'source_history_not_modified':True},indent=2)+'\n'); print(json.dumps(rows,indent=2))
