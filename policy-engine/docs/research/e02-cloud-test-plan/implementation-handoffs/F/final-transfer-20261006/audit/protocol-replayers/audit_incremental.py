import concurrent.futures,json,pathlib,sys
RUNNER=pathlib.Path(__file__).with_name('audit.py');ns={};exec(RUNNER.read_text().split('with concurrent.futures.ThreadPoolExecutor(max_workers=len(PINS))')[0],ns)
ns['PINS']['installed']=('3dde887e22592cdd7c1fe8865707afdfd72dc6fb','installed-worker-20261006.json')
ns['PINS']['installed_latest']=('3dde887e22592cdd7c1fe8865707afdfd72dc6fb','installed-latest-dependencies-20261006.json')
ns['PINS']['graph_native']=('bf335dd687c313fda9001fa3bb1365df6bc5ae1f','graph-native-20261006.json')
names=sys.argv[1:];assert names
items=[(n,ns['PINS'][n]) for n in names]
with concurrent.futures.ThreadPoolExecutor(max_workers=len(items)) as pool:results=list(pool.map(ns['component'],items))
print(json.dumps([{'component':r['component'],'head':r['head'],'check':r['check'],'issues':r['issues']} for r in results]))
