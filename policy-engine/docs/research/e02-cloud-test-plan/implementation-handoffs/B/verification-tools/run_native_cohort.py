"""Execute a prepared, source-frozen B whole-file cohort and retain its output."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    repo = args.repo.resolve()
    cohort = json.loads(args.input.read_text())

    def git(*argv):
        return subprocess.check_output(["git", "-C", str(repo), *argv], text=True).strip()

    before = {"sha": git("rev-parse", "HEAD"), "tree": git("rev-parse", "HEAD^{tree}"),
              "branch": git("symbolic-ref", "HEAD"), "status": git("status", "--porcelain")}
    if not cohort["ready_at_final_head"] or before["sha"] != cohort["final_head"] or before["status"]:
        raise SystemExit("Cohort is not ready on this clean attached frozen source")
    if args.output.exists():
        raise SystemExit("Use a fresh output directory")
    args.output.mkdir(parents=True)
    args.output = args.output.resolve()
    argv = [str(args.python.resolve()), "-m", "pytest", "-o", "addopts=", "-q",
            "--tb=short", "-ra", "--basetemp", str(args.output / "tmp"), "-o",
            "cache_dir=" + str(args.output / "pytest-cache"), "--junitxml",
            str(args.output / "cohort.xml"), *cohort["test_paths"]]
    env = dict(os.environ, PYTHONPATH="src:product", POLISYOS_METRICS_PORT="0")
    identity_script = """import importlib.metadata as m, importlib.util as u, json, platform, sys
print(json.dumps({'python':sys.version,'executable':sys.executable,'platform':platform.platform(),
'versions':{n:m.version(n) for n in ['pytest','numpy','orjson','pydantic','jax','duckdb']},
'module_origins':{n:u.find_spec(n).origin for n in ['polisyos','pytest','numpy','orjson','pydantic','jax','duckdb']}}))"""
    identity = json.loads(subprocess.check_output([str(args.python), "-c", identity_script],
                         cwd=repo / "policy-engine", env=env, text=True))
    started = datetime.now(timezone.utc).isoformat()
    clock = time.monotonic()
    with (args.output / "native.txt").open("wb") as stream:
        run = subprocess.run(["/usr/bin/time", "-v", *argv], cwd=repo / "policy-engine",
                             env=env, stdout=stream, stderr=subprocess.STDOUT)
    elapsed = time.monotonic() - clock
    after = {"sha": git("rev-parse", "HEAD"), "tree": git("rev-parse", "HEAD^{tree}"),
             "branch": git("symbolic-ref", "HEAD"), "status": git("status", "--porcelain")}
    outputs = {}
    for name in ["native.txt", "cohort.xml"]:
        path = args.output / name
        if path.exists():
            data = path.read_bytes()
            outputs[name] = {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
    receipt = {"schema": "policyos.e02.B_native_execution.v1", "started_utc": started,
               "finished_utc": datetime.now(timezone.utc).isoformat(), "wall_s": elapsed,
               "command_argv": argv, "measurement_argv_prefix": ["/usr/bin/time", "-v"],
               "cwd": str(repo / "policy-engine"), "environment":
               {"PYTHONPATH": env["PYTHONPATH"], "POLISYOS_METRICS_PORT": "0"},
               "interpreter": identity, "source_before": before, "source_after": after,
               "source_unchanged": before == after, "exit_code": run.returncode,
               "whole_file_count": len(cohort["test_paths"]), "outputs": outputs,
               "input": {"path": str(args.input.resolve()), "sha256":
                         hashlib.sha256(args.input.read_bytes()).hexdigest()},
               "resource_policy": "No imposed process or numerical worker quota; isolated test tmp/cache/metrics port.",
               "outcome": "PASS" if run.returncode == 0 and before == after else "FAIL",
               "scope": "Actual affected native whole-file execution; formal closure, full production and live optional backends not established."}
    (args.output / "wrapper.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"exit_code": run.returncode, "wall_s": elapsed,
                      "source_unchanged": before == after, "output": str(args.output)}))
    return run.returncode or int(before != after)


if __name__ == "__main__":
    sys.exit(main())
