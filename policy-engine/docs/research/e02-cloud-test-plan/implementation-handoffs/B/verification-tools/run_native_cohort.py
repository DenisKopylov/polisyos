"""Execute a prepared, source-frozen B whole-file cohort and retain its output."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--source-base", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    repo = args.repo.resolve()
    input_bytes = args.input.read_bytes()
    input_sha256 = hashlib.sha256(input_bytes).hexdigest()
    cohort = json.loads(input_bytes)

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
    # Resolving a venv executable symlink bypasses its pyvenv.cfg and packages.
    python_executable = str(args.python.absolute())
    argv = [python_executable, "-m", "pytest", "-o", "addopts=", "-q",
            "--tb=short", "-ra", "--basetemp", str(args.output / "tmp"), "-o",
            "cache_dir=" + str(args.output / "pytest-cache"), "--junitxml",
            str(args.output / "cohort.xml"), *cohort["test_paths"]]
    env = dict(os.environ, PYTHONPATH="src:product", POLISYOS_METRICS_PORT="0")
    changed_modules = {}
    for path in git("diff", "--name-only", args.source_base, before["sha"],
                    "--", "policy-engine/src").splitlines():
        if path.endswith(".py"):
            module = path.split("/src/", 1)[1][:-3].replace("/", ".")
            changed_modules[module.removesuffix(".__init__")] = str(repo / path)
    identity_script = """import hashlib, importlib.metadata as m, importlib.util as u, json, pathlib, platform, sys
origins={}
for name,expected in json.loads(sys.argv[1]).items():
 spec=u.find_spec(name);origin=spec.origin if spec else None
 origins[name]={'origin':origin,'expected':expected,'matches_expected':origin is not None and pathlib.Path(origin).resolve()==pathlib.Path(expected).resolve(),
 'sha256':hashlib.sha256(pathlib.Path(origin).read_bytes()).hexdigest() if origin else None}
print(json.dumps({'python':sys.version,'executable':sys.executable,'platform':platform.platform(),'sys_path':sys.path,
'versions':{n:m.version(n) for n in ['pytest','numpy','orjson','pydantic','jax','duckdb']},
'module_origins':{n:u.find_spec(n).origin for n in ['polisyos','pytest','numpy','orjson','pydantic','jax','duckdb']},'changed_source_origins':origins}))"""
    identity = json.loads(subprocess.check_output([python_executable, "-c", identity_script,
                         json.dumps(changed_modules)],
                         cwd=repo / "policy-engine", env=env, text=True))
    if not all(row["matches_expected"] for row in identity["changed_source_origins"].values()):
        raise SystemExit("Changed source modules do not resolve to the frozen checkout")
    started = datetime.now(timezone.utc).isoformat()
    clock = time.monotonic()
    measurement_error = None
    with (args.output / "native.txt").open("wb") as stream:
        run = subprocess.Popen(argv, cwd=repo / "policy-engine", env=env,
                               stdout=stream, stderr=subprocess.STDOUT)
        try:
            _pid, status, usage = os.wait4(run.pid, 0)
        except BaseException as error:
            measurement_error = {"type": type(error).__name__, "message": str(error)}
            # Reap this measured child before writing a terminal harness receipt.
            # This does not claim containment of arbitrary descendant sessions.
            try:
                os.kill(run.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            _pid, status, usage = os.wait4(run.pid, 0)
        run.returncode = os.waitstatus_to_exitcode(status)
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
               "command_argv": argv, "resource_measurement": "os.wait4 on the actual pytest child PID",
               "max_rss_kib": usage.ru_maxrss / 1024 if sys.platform == "darwin" else usage.ru_maxrss,
               "user_cpu_s": usage.ru_utime, "system_cpu_s": usage.ru_stime,
               "cwd": str(repo / "policy-engine"), "environment":
               {"PYTHONPATH": env["PYTHONPATH"], "POLISYOS_METRICS_PORT": "0"},
               "interpreter": identity, "source_before": before, "source_after": after,
               "source_base": args.source_base,
               "source_unchanged": before == after, "exit_code": run.returncode,
               "whole_file_count": len(cohort["test_paths"]), "outputs": outputs,
               "input": {"path": str(args.input.resolve()), "sha256": input_sha256,
                         "bytes": len(input_bytes), "hash_basis": "Initial bytes parsed to construct this argv"},
               "resource_policy": "No imposed process or numerical worker quota; isolated test tmp/cache/metrics port.",
               "measurement_error": measurement_error,
               "outcome": "ERROR" if measurement_error else "PASS" if run.returncode == 0 and before == after else "FAIL",
               "scope": "Actual affected native whole-file execution; formal closure, full production and live optional backends not established."}
    (args.output / "wrapper.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"exit_code": run.returncode, "wall_s": elapsed,
                      "source_unchanged": before == after, "output": str(args.output)}))
    return run.returncode or int(before != after or measurement_error is not None)


if __name__ == "__main__":
    sys.exit(main())
