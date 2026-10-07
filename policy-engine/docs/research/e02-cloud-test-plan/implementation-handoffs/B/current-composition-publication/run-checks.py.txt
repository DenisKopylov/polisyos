from __future__ import annotations
import datetime, hashlib, json, os, pathlib, subprocess, sys, time
root = pathlib.Path(__file__).resolve().parents[2]
raw = root / "_build/e02-B-current-composition/raw"
name, *paths = sys.argv[1:]
python = "/workspace/polisyos/policy-engine/.venv/bin/python"
def git(*args):
    return subprocess.check_output(["git", *args], cwd=root, text=True).strip()
def source():
    changed = sorted(set(git("diff", "--name-only", "HEAD").splitlines()))
    return {"sha": git("rev-parse", "HEAD"), "tree": git("rev-parse", "HEAD^{tree}"),
            "status": git("status", "--porcelain"),
            "changed_paths_sha256": {p: hashlib.sha256((root.parent / p).read_bytes()).hexdigest()
            for p in changed if (root.parent / p).is_file()}}
argv=[python,"-m","pytest","-o","addopts=","-o",f"cache_dir={raw / (name+'-cache')}","-q",*paths,
      f"--basetemp={raw / (name+'-tmp')}",f"--junitxml={raw / (name+'.xml')}"]
env=os.environ.copy(); env.update(PYTHONPATH="src",POLISYOS_METRICS_PORT="0",PYTHONDONTWRITEBYTECODE="1")
packet={"argv":argv,"cwd":str(root),"source_before":source(),
        "environment":{k:env[k] for k in ("PYTHONPATH","POLISYOS_METRICS_PORT","PYTHONDONTWRITEBYTECODE")},
        "python": subprocess.check_output([python,"--version"],text=True).strip(),
        "start_utc":datetime.datetime.now(datetime.UTC).isoformat()}
start=time.monotonic()
with (raw / (name+'.txt')).open('wb') as out:
    child=subprocess.Popen(argv,cwd=root,env=env,stdout=out,stderr=subprocess.STDOUT)
    _,status,usage=os.wait4(child.pid,0); child.returncode=os.waitstatus_to_exitcode(status)
packet.update(exit_code=child.returncode,wall_seconds=time.monotonic()-start,max_rss_kib=usage.ru_maxrss,
              resource_method="direct wait4 child rusage; Linux KiB",source_after=source(),
              end_utc=datetime.datetime.now(datetime.UTC).isoformat())
(raw / (name+'.json')).write_text(json.dumps(packet,indent=2)+"\n")
print(json.dumps(packet,indent=2))
print((raw / (name+'.txt')).read_text())
sys.exit(child.returncode)
