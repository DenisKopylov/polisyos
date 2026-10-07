import hashlib,json,os,subprocess,time,sys
from pathlib import Path
OUT=Path('/tmp/e02-F-graph-profile-20261007/api-review/combined4ee')
REPO=Path('/workspace/e02-F-closeout-20261006')
EXPECTED='4ee2f2a4f1d9c4d42c6e5ec7f85f973e07358f0d'
def guard():
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip()
    tree=subprocess.check_output(['git','rev-parse','HEAD^{tree}'],cwd=REPO,text=True).strip()
    assert head==EXPECTED
    bindings=[]
    for p in ['policy-engine/src/polisyos/foundry/methods/catalog/causal/graph_reconciliation.py','policy-engine/src/polisyos/scientist/nodes/builtins/causal/reconcile_causal_graph.py','policy-engine/tests/unit/scientist/methods/causal/test_graph_intake_current_content.py']:
        raw=(REPO/p).read_bytes(); frozen=subprocess.check_output(['git','show',EXPECTED+':'+p],cwd=REPO)
        assert raw==frozen
        bindings.append({'path':p,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'git_blob':subprocess.check_output(['git','rev-parse',EXPECTED+':'+p],cwd=REPO,text=True).strip()})
    return {'head':head,'tree':tree,'source_bindings':bindings}
def ref(p):
    raw=p.read_bytes();return {'path':str(p),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
for mode in ['untouched','removed']:
    argv=['/workspace/e02-F-closeout-20261006/policy-engine/.venv/bin/python',str(OUT/'graph_guard_probe.py'),mode]
    env={'PYTHONPATH':str(REPO/'policy-engine/src')+':'+str(REPO/'policy-engine/tools')+':'+str(REPO/'policy-engine'),'PYTHONDONTWRITEBYTECODE':'1'}
    before=guard();start=time.perf_counter()
    r=subprocess.run(argv,cwd=REPO/'policy-engine',env={**os.environ,**env},capture_output=True)
    (OUT/('graph-'+mode+'.stdout.txt')).write_bytes(r.stdout);(OUT/('graph-'+mode+'.stderr.txt')).write_bytes(r.stderr)
    record={'argv':argv,'cwd':str(REPO/'policy-engine'),'env_overrides':env,'source_before':before,'source_after':guard(),'exit_code':r.returncode,'wall_seconds':time.perf_counter()-start,'stdout':ref(OUT/('graph-'+mode+'.stdout.txt')),'stderr':ref(OUT/('graph-'+mode+'.stderr.txt')),'junit':ref(OUT/('graph-'+mode+'.xml')),'replayer':ref(OUT/'graph_guard_probe.py'),'scope':'selected 7 cases; retained-marker graph-family admission control, no numerical worker/backend/authority claim'}
    (OUT/('graph-'+mode+'.execution.json')).write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps(record,indent=2),flush=True)
    assert r.returncode==(0 if mode=='untouched' else 1)
