"""Capture one complete child command and exact frozen Git/source inputs."""
from pathlib import Path
import hashlib,json,os,subprocess,sys,time
ROOT=Path("/workspace/orch02-c12")
OUT=Path("/workspace/orch02-r2/c12")
def git(*args):
    return subprocess.check_output(["git","-C",str(ROOT),*args],text=True).strip()
def sha(path):
    b=path.read_bytes();return {"bytes":len(b),"sha256":hashlib.sha256(b).hexdigest()}
name=sys.argv[1];argv=sys.argv[2:]
env=os.environ.copy();env.update({"PYTHONPATH":str(ROOT/"policy-engine/src")+":"+str(ROOT/"policy-engine"),"PYTHONDONTWRITEBYTECODE":"1","PYTHONNOUSERSITE":"1"})
inputs={p:sha(ROOT/"policy-engine"/p) for p in ["src/polisyos/lex/knowledge/store.py","src/polisyos/lex/knowledge/search.py","tests/unit/remediation/test_emb_03.py"]}
receipt={"argv":argv,"cwd":str(ROOT/"policy-engine"),"source_HEAD":git("rev-parse","HEAD"),"source_tree":git("rev-parse","HEAD^{tree}"),"status_before":git("status","--porcelain"),"input_bytes":inputs,"env":{k:env[k] for k in ["PYTHONPATH","PYTHONDONTWRITEBYTECODE","PYTHONNOUSERSITE"]},"timeout_seconds":None}
start=time.monotonic()
with (OUT/(name+".stdout.txt")).open("wb") as out,(OUT/(name+".stderr.txt")).open("wb") as err:
    child=subprocess.Popen(argv,cwd=ROOT/"policy-engine",env=env,stdout=out,stderr=err)
    pid,status,usage=os.wait4(child.pid,0);child.returncode=os.waitstatus_to_exitcode(status)
receipt.update({"exit_code":child.returncode,"wall_seconds":time.monotonic()-start,"resource":{"measurement":"Linux wait4 actual child","maxrss_kib":usage.ru_maxrss,"user_seconds":usage.ru_utime,"system_seconds":usage.ru_stime},"HEAD_after":git("rev-parse","HEAD"),"status_after":git("status","--porcelain"),"inputs_after":{p:sha(ROOT/"policy-engine"/p) for p in inputs},"outputs":{suffix:sha(OUT/(name+suffix)) for suffix in [".stdout.txt",".stderr.txt"]}})
(OUT/(name+".receipt.json")).write_text(json.dumps(receipt,indent=2)+"\n")
print(json.dumps({k:receipt[k] for k in ["exit_code","wall_seconds","resource"]}))
