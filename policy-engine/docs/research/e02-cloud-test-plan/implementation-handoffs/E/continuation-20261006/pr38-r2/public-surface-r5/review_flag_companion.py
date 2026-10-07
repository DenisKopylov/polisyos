from pathlib import Path
import hashlib,json,subprocess,tomllib

R=Path('/workspace/e02-E-continuation-20261006');O=Path(__file__).parent
CANONICAL='7dc540d08d30bad8cf23744172c253c934dfc77e'
CANDIDATE='7bc65f73d333bc4a526c55d8a959d2b7dea7e472'
PARENT=subprocess.check_output(['git','rev-parse',CANDIDATE+'^'],cwd=R,text=True).strip()
PATH='policy-engine/release-fragments/unreleased/2026-10-06-e02-foundry-calibration-reader.toml'
paths=subprocess.check_output(['git','diff','--name-only',PARENT,CANDIDATE],cwd=R,text=True).splitlines()
assert paths==[PATH]
a=subprocess.check_output(['git','show',PARENT+':'+PATH],cwd=R);b=subprocess.check_output(['git','show',CANDIDATE+':'+PATH],cwd=R)
assert a.replace(b'public_surface_inventory_reviewed = false',b'public_surface_inventory_reviewed = true')==b
assert (R/PATH).read_bytes()==b
x=tomllib.loads(b.decode());assert x['public_surface_inventory_reviewed'] is True and x['surface_classification']=='public_stable'
assert not subprocess.check_output(['git','diff','--name-only',CANONICAL,CANDIDATE,'--','policy-engine/src'],cwd=R,text=True).strip()
review={'source_sha':'bf3b54c3a894d2d9d9bfb0cd13edb13177405f33','canonical_companion':CANONICAL,'flag_parent':PARENT,'flag_companion':CANDIDATE,'flag_tree':'2c1b3fd02d751a6a8bd3053954ace7be4fce65ad','footprint':[PATH],'exact_one_line_false_to_true':True,'classification':'public_stable','source_and_canonical_metadata_unchanged':True,'path_sha256':hashlib.sha256(b).hexdigest(),'verdict':'GO-bounded-declaration-of-completed-independent-review','harness_history':'Initial whole7dc→7bc footprint assertion failed because parentc3 also committed r4 receipts. Corrected to exactflagcommit parent→candidate. No product failure; full canonical→flag delta includes those separate docs receipts.'}
(O/'reviewflag-companion.json').write_text(json.dumps(review,indent=2)+'\n');print(json.dumps(review,indent=2))
