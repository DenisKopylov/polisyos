from pathlib import Path
import hashlib,json,os,subprocess,sys,time
ROOT=Path("/workspace/e02-F-tmle-20261006");OUT=Path(__file__).parent;PY="/workspace/e02-F-closeout-20261006/policy-engine/.venv/bin/python";REF="6c711bd2d4f1b6bf851c42a5f3d22b795efb020d"
def git(*args):return subprocess.check_output(["git",*args],cwd=ROOT).decode().strip()
assert git("rev-parse","HEAD")==REF and not git("status","--porcelain=v1")
mode=sys.argv[1];cmd=[PY,str(OUT/"removal_replay.py"),mode];env=dict(os.environ);env["PYTHONPATH"]=str(ROOT/"policy-engine/src")+":"+str(ROOT/"policy-engine/tools");env["TMPDIR"]="/tmp"
t=time.monotonic();p=subprocess.run(cmd,cwd=ROOT/"policy-engine",env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE);wall=time.monotonic()-t
for key,data in (("stdout",p.stdout),("stderr",p.stderr)):(OUT/("removal-"+mode+"."+key+".txt")).write_bytes(data)
assert git("rev-parse","HEAD")==REF and not git("status","--porcelain=v1")
r=dict(source_sha=REF,source_tree=git("rev-parse",REF+"^{tree}"),argv=cmd,cwd=str(ROOT/"policy-engine"),environment=dict(interpreter=PY,PYTHONPATH=env["PYTHONPATH"],TMPDIR="/tmp",inherited_environment=True,artificial_cloud_quota=False),exit_code=p.returncode,wall_seconds=wall,output=str(OUT/("removal-"+mode+".stdout.txt")),stderr=str(OUT/("removal-"+mode+".stderr.txt")),removal_scope=mode,source_clean_after=True)
(OUT/("removal-"+mode+".json")).write_text(json.dumps(r,indent=2)+"\n");print(json.dumps(dict(control=mode,exit_code=p.returncode,wall_seconds=wall)))
