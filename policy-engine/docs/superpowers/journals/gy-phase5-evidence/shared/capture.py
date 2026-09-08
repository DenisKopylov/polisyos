"""Capture an exact gate return code and complete streams without shell chaining."""
import json, os, shlex, subprocess, sys, time
from pathlib import Path
name, *command=sys.argv[1:]
start=time.monotonic()
result=subprocess.run(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
record={"cwd":str(Path.cwd()),"command":shlex.join(command),"argv":command,"PATH":os.environ.get("PATH"),"PYTHONPATH":os.environ.get("PYTHONPATH"),"returncode":result.returncode,"elapsed_seconds":time.monotonic()-start,"stdout":result.stdout,"stderr":result.stderr}
Path(name).write_text(json.dumps(record,indent=2,ensure_ascii=False)+"\n")
print(json.dumps({key:record[key] for key in ("command","returncode","elapsed_seconds")}),flush=True)
print(result.stdout,end="")
print(result.stderr,file=sys.stderr,end="")
raise SystemExit(result.returncode)
