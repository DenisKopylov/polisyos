"""Replay immutable receipt checks in a caller-selected checkout and new scratch directory.

Example: python3 replay_final_protocol_audit.py --repo /your/fetched/repo --out /tmp/f-protocol-replay --snapshot F-published-protocol-audit.json.gz
Only Git reads and scratch writes occur. The optional fully measured snapshot supplies
previous raw-gzip decode identities; compressed Git bytes and exact declared raw
identities are rechecked before any cache reuse. Omitting it decodes every raw body.
"""
import argparse, concurrent.futures, gzip, json, pathlib
p=argparse.ArgumentParser();p.add_argument('--repo',type=pathlib.Path,required=True);p.add_argument('--out',type=pathlib.Path,required=True);p.add_argument('--snapshot',type=pathlib.Path);a=p.parse_args()
source=pathlib.Path(__file__).resolve().parent
repo=str(a.repo.resolve());out=a.out.resolve()
if out.exists() and any(out.iterdir()):raise SystemExit('Use a new empty scratch directory; no existing outputs will be overwritten.')
out.mkdir(parents=True,exist_ok=True)
if a.snapshot:
 raw=a.snapshot.read_bytes();snapshot=json.loads(gzip.decompress(raw) if a.snapshot.suffix=='.gz' else raw)
 for part in snapshot['primary_components']+snapshot['companion_components']+snapshot['ancillary_components']:
  name=part['component']
  if not name.replace('_','').isalnum():raise SystemExit('Invalid component cache name')
  (out/(name+'.json')).write_text(json.dumps(part)+'\n')
def relocated(filename):
 code=(source/filename).read_text()
 # These two substitutions change navigation only, preserving all validator logic.
 code=code.replace("'/workspace/e02-F-graph-20261006'",repr(repo))
 code=code.replace("'/workspace/e02-F-20261006-receipts/protocol-audit'",repr(str(out)))
 return code
ns={};exec(compile(relocated('audit.py').split('with concurrent.futures.ThreadPoolExecutor(max_workers=len(PINS))')[0],str(source/'audit.py'),'exec'),ns)
extra={'root_consumer':('92148340601ac6ea69f0dbd4764aae7428ad83d7','causal-consumer-binding-20261006.json'),'installed':('3dde887e22592cdd7c1fe8865707afdfd72dc6fb','installed-worker-20261006.json'),'intake':('2044260c39dc4988b37d5a1568b65a1cdb1e3d31','graph-intake-native-20261006.json'),'installed_latest':('3dde887e22592cdd7c1fe8865707afdfd72dc6fb','installed-latest-dependencies-20261006.json'),'graph_native':('bf335dd687c313fda9001fa3bb1365df6bc5ae1f','graph-native-20261006.json')}
items=list({**ns['PINS'],**extra}.items())
with concurrent.futures.ThreadPoolExecutor(max_workers=len(items)) as pool:list(pool.map(ns['component'],items))
exec(compile(relocated('consolidate.py'),str(source/'consolidate.py'),'exec'),{'__name__':'__main__'})
# Inventory uses its script directory to locate the final report: direct its location to scratch.
exec(compile(relocated('canonical_inventory.py'),str(source/'canonical_inventory.py'),'exec'),{'__name__':'__main__','__file__':str(out/'canonical_inventory.py')})
print('Complete protocol replay written to',out)
