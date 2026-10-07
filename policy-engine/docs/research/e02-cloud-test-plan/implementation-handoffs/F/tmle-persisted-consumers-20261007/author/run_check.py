"""Run one frozen, source-guarded command and retain full deciding bytes."""
import hashlib
import json
import os
import pathlib
import platform
import resource
import subprocess
import sys
import time

scratch = pathlib.Path(__file__).resolve().parent
spec = json.loads((scratch / (sys.argv[1]+"-spec.json")).read_bytes())
name = sys.argv[1]
repo = pathlib.Path(spec["repository_root"])
def git(*args):
    return subprocess.check_output(["git", *args], cwd=repo).decode().strip()
def file_ref(path):
    raw = path.read_bytes()
    return {"path": str(path), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
def source():
    result = []
    for relative in spec["guard_paths"]:
        path = repo / relative
        raw = path.read_bytes()
        frozen = subprocess.check_output(["git", "show", spec["target_sha"]+":"+relative], cwd=repo)
        assert raw == frozen, relative
        result.append({"path": relative, "git_blob": git("rev-parse", spec["target_sha"]+":"+relative), **{k:v for k,v in file_ref(path).items() if k!="path"}})
    return result
assert git("rev-parse", "HEAD") == spec["target_sha"]
assert git("symbolic-ref", "--short", "HEAD") == "codex/e02-F-tmle-20261006"
before = source()
env = {**os.environ, **spec["environment_overrides"]}
start = time.perf_counter()
with (scratch/(name+".stdout.txt")).open("wb") as out, (scratch/(name+".stderr.txt")).open("wb") as err:
    process = subprocess.run(spec["argv"], cwd=spec["cwd"], env=env, stdout=out, stderr=err, check=False)
wall = time.perf_counter()-start
after = source()
assert before == after
receipt = {
    "target_sha": spec["target_sha"],
    "target_tree": git("rev-parse", spec["target_sha"]+"^{tree}"),
    "command": spec["argv"], "cwd": spec["cwd"],
    "environment": {"python": sys.version, "executable": sys.executable, "platform": platform.platform(), "overrides": spec["environment_overrides"], "safe_inherited_numeric_variables": {key:os.environ[key] for key in ("OMP_NUM_THREADS","OPENBLAS_NUM_THREADS","MKL_NUM_THREADS","NUMEXPR_NUM_THREADS","JAX_PLATFORMS") if key in os.environ}, "new_orchestration_quota": False},
    "wall_seconds": wall, "rss_kib": resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,
    "exit_code": process.returncode, "outcome": "PASS" if process.returncode == 0 else "FAIL",
    "stdout": file_ref(scratch/(name+".stdout.txt")), "stderr": file_ref(scratch/(name+".stderr.txt")),
    "source_guard_before_and_after": before,
    "limits": ["Scoped native consumer property only; positive causal identification and admitted competing-study budget remain UNRUN.", "No numerical coverage or cache/default-fold wave rerun."]
}
(scratch/(name+".json")).write_text(json.dumps(receipt, indent=2)+"\n")
print(json.dumps({"name":name,"exit_code":process.returncode,"wall_seconds":wall,"rss_kib":receipt["rss_kib"],"stdout":receipt["stdout"]}))
raise SystemExit(process.returncode)
