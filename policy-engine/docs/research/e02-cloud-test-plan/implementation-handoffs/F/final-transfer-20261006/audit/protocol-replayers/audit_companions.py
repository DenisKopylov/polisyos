import concurrent.futures,json,pathlib
RUNNER=pathlib.Path(__file__).with_name('audit.py');ns={};exec(RUNNER.read_text().split('with concurrent.futures.ThreadPoolExecutor(max_workers=len(PINS))')[0],ns)
PINS={'root_consumer':('92148340601ac6ea69f0dbd4764aae7428ad83d7','causal-consumer-binding-20261006.json'),'installed':('3dde887e22592cdd7c1fe8865707afdfd72dc6fb','installed-worker-20261006.json'),'intake':('2044260c39dc4988b37d5a1568b65a1cdb1e3d31','graph-intake-native-20261006.json'),'installed_latest':('3dde887e22592cdd7c1fe8865707afdfd72dc6fb','installed-latest-dependencies-20261006.json'), 'graph_native':('bf335dd687c313fda9001fa3bb1365df6bc5ae1f','graph-native-20261006.json')}
with concurrent.futures.ThreadPoolExecutor(max_workers=len(PINS)) as pool:results=list(pool.map(ns['component'],PINS.items()))
print(json.dumps([{'component':r['component'],'head':r['head'],'check':r['check'],'issue_count':len(r['issues'])} for r in results]))
