from pathlib import Path
import hashlib,json,os,subprocess,sys,time
ROOT=Path("/workspace/e02-F-tmle-20261006");OUT=Path(__file__).parent;PY="/workspace/e02-F-closeout-20261006/policy-engine/.venv/bin/python"
mode=sys.argv[1];head=subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT).decode().strip();tree=subprocess.check_output(["git","rev-parse","HEAD^{tree}"],cwd=ROOT).decode().strip();assert not subprocess.check_output(["git","status","--porcelain=v1"],cwd=ROOT).strip()
env=dict(os.environ);env["PYTHONPATH"]=str(ROOT/"policy-engine")+":"+str(ROOT/"policy-engine/src")+":"+str(ROOT/"policy-engine/tools");env["TMPDIR"]="/tmp"
cmd=[PY,"-m","tools.quality.diagnostics.gen_schema","--check","--cache-dir",str(OUT/"full-check-cache")] if mode=="full" else [PY,str(OUT/"check_selected_origin.py"),mode]
t=time.monotonic();r=subprocess.run(cmd,cwd=ROOT/"policy-engine",env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE);wall=time.monotonic()-t
for key,data in (("stdout",r.stdout),("stderr",r.stderr)):(OUT/(mode+"."+key+".txt")).write_bytes(data)
assert head==subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT).decode().strip();assert not subprocess.check_output(["git","status","--porcelain=v1"],cwd=ROOT).strip()
report=dict(source_sha=head,source_tree=tree,argv=cmd,cwd=str(ROOT/"policy-engine"),environment=dict(interpreter=PY,PYTHONPATH=env["PYTHONPATH"],TMPDIR="/tmp",inherited_environment=True,artificial_cloud_quota=False),exit_code=r.returncode,wall_seconds=wall,output=str(OUT/(mode+".stdout.txt")),stderr=str(OUT/(mode+".stderr.txt")),source_clean_before_after=True)
(OUT/(mode+".json")).write_text(json.dumps(report,indent=2)+"\n");print(json.dumps(report))
