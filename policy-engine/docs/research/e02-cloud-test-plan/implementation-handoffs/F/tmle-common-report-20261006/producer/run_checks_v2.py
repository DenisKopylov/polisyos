from pathlib import Path
import hashlib,json,os,platform,subprocess,sys,time
ROOT=Path("/workspace/e02-F-tmle-20261006"); OUT=Path(__file__).parent; PY="/workspace/e02-F-closeout-20261006/policy-engine/.venv/bin/python"
tag=sys.argv[1];selectors=sys.argv[2:]
(OUT/tag).mkdir(parents=True,exist_ok=True)
paths=["policy-engine/src/polisyos/foundry/methods/catalog/causal/treatment_effects.py","policy-engine/src/polisyos/foundry/methods/catalog/causal/tmle_core.py","policy-engine/src/polisyos/foundry/methods/catalog/causal/nuisance_layer.py","policy-engine/src/polisyos/foundry/methods/catalog/causal/protocols.py","policy-engine/src/polisyos/ir/analytics/causal.py","policy-engine/tests/unit/foundry/methods/catalog/causal/test_tmle_common_report.py"]
def git(*args):return subprocess.check_output(["git",*args],cwd=ROOT).decode().strip()
def bind(name):
 data=(ROOT/name).read_bytes();return dict(path=name,bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
before=[bind(p) for p in paths];head=git("rev-parse","HEAD");tree=git("rev-parse","HEAD^{tree}")
env=dict(os.environ);env["PYTHONPATH"]=str(ROOT/"policy-engine/src")+":"+str(ROOT/"policy-engine/tools");env["TMPDIR"]="/tmp"
cmd=[PY,"-m","pytest",*selectors,"-o","addopts=","-o",f"cache_dir={OUT/tag/'cache'}","-q","-ra","--basetemp="+str(OUT/tag/"pytest-tmp"),"--junitxml="+str(OUT/(tag+".junit.xml"))]
start=time.monotonic();p=subprocess.run(cmd,cwd=ROOT/"policy-engine",env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE);wall=time.monotonic()-start
for name,data in (("stdout",p.stdout),("stderr",p.stderr)):(OUT/(tag+"."+name+".txt")).write_bytes(data)
assert before==[bind(path) for path in paths];assert head==git("rev-parse","HEAD")
report=dict(source_sha=head,source_tree=tree,source_clean=not bool(git("status","--porcelain=v1")),input_closure=before,argv=cmd,cwd=str(ROOT/"policy-engine"),environment=dict(interpreter=PY,PYTHONPATH=env["PYTHONPATH"],TMPDIR="/tmp",inherited_environment=True,artificial_cloud_quota=False,python=subprocess.check_output([PY,"-c","import platform;print(platform.python_version())"]).decode().strip()),exit_code=p.returncode,wall_seconds=wall,output=str(OUT/(tag+".stdout.txt")),stderr=str(OUT/(tag+".stderr.txt")),junit=str(OUT/(tag+".junit.xml")))
(OUT/(tag+".json")).write_text(json.dumps(report,indent=2)+"\n");print(json.dumps(dict(tag=tag,exit_code=p.returncode,wall_seconds=wall,receipt=str(OUT/(tag+".json")))))
