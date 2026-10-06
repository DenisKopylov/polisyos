from __future__ import annotations
import json, os, resource, subprocess, sys, time
print("command=" + json.dumps(sys.argv[1:]), flush=True)
print("PYTHONPATH=" + os.environ.get("PYTHONPATH", ""), flush=True)
start = time.monotonic()
process = subprocess.run(sys.argv[1:])
usage = resource.getrusage(resource.RUSAGE_CHILDREN)
print("measured=" + json.dumps({"exit_code": process.returncode, "wall_seconds": time.monotonic()-start, "user_seconds": usage.ru_utime, "system_seconds": usage.ru_stime, "max_rss_kib": usage.ru_maxrss}), flush=True)
sys.exit(process.returncode)
