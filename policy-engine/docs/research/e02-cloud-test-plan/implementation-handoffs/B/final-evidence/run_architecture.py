"""Run the admitted frozen architecture gate; retain complete deciding bytes outside it."""

import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--frozen-sha", required=True)
    parser.add_argument("--checkout", type=Path, default=Path("/workspace/e02-B-acceptance"))
    parser.add_argument("--output-prefix", type=Path, required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"[0-9a-f]{40}", args.frozen_sha):
        parser.error("Use root's exact 40-character frozen SHA")
    checkout = args.checkout.resolve()
    cwd = checkout / "policy-engine"
    prefix = args.output_prefix.resolve()
    if prefix.is_relative_to(checkout):
        parser.error("Evidence must be outside the admitted checkout")
    prefix.parent.mkdir(parents=True, exist_ok=True)
    paths = {"log": Path(str(prefix) + ".txt"), "receipt": Path(str(prefix) + ".json"),
             "resource": Path(str(prefix) + ".time.txt")}
    if any(path.exists() for path in paths.values()):
        parser.error("Evidence paths already exist; use a fresh prefix")
    environment = os.environ.copy()
    node_prefix = "/workspace/e02-B-coordination/.polisyos/e02-B/node22/node_modules/node/bin"
    environment["PATH"] = node_prefix + os.pathsep + environment.get("PATH", "")
    environment["PYTHONPATH"] = "src:product"
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    python = "/workspace/polisyos/policy-engine/.venv/bin/python"
    argv = [python, "-m", "tools.cli", "architecture", "guardrails", "check"]

    def capture(command):
        try:
            result = subprocess.run(command, cwd=cwd, env=environment,
                                    capture_output=True, text=True)
        except OSError as error:
            return {"argv": command, "exit_code": None, "stdout": "", "stderr": str(error),
                    "execution_error": type(error).__name__}
        return {"argv": command, "exit_code": result.returncode,
                "stdout": result.stdout, "stderr": result.stderr}

    def git(*options):
        return capture(["git", "-C", str(checkout), *options])["stdout"].strip()

    def identity():
        return {"sha": git("rev-parse", "HEAD"), "tree": git("rev-parse", "HEAD^{tree}"),
                "branch": git("symbolic-ref", "--short", "HEAD"),
                "status_porcelain": git("status", "--porcelain=v1")}

    start = identity()
    wrapper = {"schema": "policyos.e02.B_final_architecture_execution.v1",
               "expected_frozen_sha": args.frozen_sha, "start": start,
               "cwd": str(cwd), "argv": argv, "stdio": "complete merged stdout/stderr",
               "selected_environment": {key: environment.get(key) for key in
                    ["PATH", "PYTHONPATH", "PYTHONDONTWRITEBYTECODE", "VIRTUAL_ENV",
                     "UV_CACHE_DIR", "UV_PROJECT_ENVIRONMENT", "UV_NO_SYNC", "UV_FROZEN",
                     "NODE_OPTIONS", "COREPACK_ENABLE_PROJECT_SPEC"]},
               "source_edit_authorization": "read_only; wrapper makes no source edits",
               "inherited_red_attribution": "not_established; no slice-base replay here",
               "process_or_numeric_quota": "none"}
    if start["sha"] != args.frozen_sha or start["status_porcelain"]:
        wrapper.update({"outcome": "UNRUN", "reason": "Frozen SHA/clean source preflight rejected",
                        "exit_code": None, "end": identity()})
        paths["receipt"].write_text(json.dumps(wrapper, indent=2) + "\n")
        print("UNRUN", wrapper["reason"], str(paths["receipt"]))
        return 3

    info_code = '''import importlib.metadata as m,importlib.util as u,json,platform,sys
names=["tools.cli","tools.devx.architecture.guardrails","polisyos","pydantic","duckdb","pytest","ruff"]
origins={}
for name in names:
 try:
  spec=u.find_spec(name);origins[name]={"origin":spec.origin if spec else None,"search_locations":list(spec.submodule_search_locations or []) if spec else []}
 except Exception as error:origins[name]={"resolution_error":type(error).__name__+": "+str(error)}
versions={}
for name in ["pytest","pydantic","duckdb","ruff","cryptography","numpy","typer","uv"]:
 try:versions[name]=m.version(name)
 except m.PackageNotFoundError:versions[name]=None
print(json.dumps({"executable":sys.executable,"python":sys.version,"platform":platform.platform(),"sys_path":sys.path,"origins":origins,"versions":versions},sort_keys=True))'''
    wrapper["python_environment"] = capture([python, "-c", info_code])
    commands = {"node": ["node", "--version"], "corepack": ["corepack", "--version"],
                "pnpm": ["corepack", "pnpm", "--version"], "uv": ["uv", "--version"]}
    wrapper["toolchain"] = {name: {"resolved_executable": shutil.which(command[0], path=environment["PATH"]),
                                   **capture(command)} for name, command in commands.items()}
    node_info = '''const fs=require("fs"); const path=require("path"); const root=process.cwd();const names=["typescript","ts-morph","tsx","openapi-typescript"];let modules={};for(const name of names){try{let manifest=require.resolve(name+"/package.json");modules[name]={manifest,real_manifest:fs.realpathSync(manifest),version:JSON.parse(fs.readFileSync(manifest,"utf8")).version};}catch(error){try{let entry=require.resolve(name);modules[name]={entry,real_entry:fs.realpathSync(entry),manifest_resolution_error:error.message};}catch(inner){modules[name]={resolution_error:inner.message};}}}console.log(JSON.stringify({executable:process.execPath,versions:process.versions,cwd:root,modules}));'''
    wrapper["node_environment"] = capture(["node", "-e", node_info])
    if wrapper["toolchain"]["node"]["stdout"].strip() != "v22.22.0":
        wrapper.update({"outcome": "UNRUN", "reason": "Supported Node22 identity rejected",
                        "exit_code": None, "end": identity()})
        paths["receipt"].write_text(json.dumps(wrapper, indent=2) + "\n")
        print("UNRUN", wrapper["reason"], str(paths["receipt"]))
        return 3
    input_paths = ["pnpm-lock.yaml", "package.json", "pnpm-workspace.yaml",
                   "policy-engine/pnpm-lock.yaml", "policy-engine/package.json",
                   "policy-engine/pnpm-workspace.yaml", "policy-engine/uv.lock",
                   "policy-engine/pyproject.toml", "policy-engine/tools/cli.py",
                   "policy-engine/tools/devx/architecture/guardrails.py"]
    wrapper["entry_input_hashes"] = {relative: hashlib.sha256((checkout / relative).read_bytes()).hexdigest()
                                     for relative in input_paths if (checkout / relative).is_file()}
    wrapper["entry_input_paths_absent"] = [relative for relative in input_paths
                                           if not (checkout / relative).is_file()]
    wrapper["installed_frontend_metadata"] = {relative: {"realpath": str((checkout / relative).resolve()),
                                                        "sha256": hashlib.sha256((checkout / relative).read_bytes()).hexdigest()}
                                                for relative in ["node_modules/.modules.yaml", "node_modules/.pnpm/lock.yaml",
                                                                 "policy-engine/node_modules/.modules.yaml",
                                                                 "policy-engine/node_modules/.pnpm/lock.yaml"]
                                                if (checkout / relative).is_file()}
    wrapper["input_closure_limit"] = "The exact frozen Git tree binds tracked inputs; installed dependency/toolchain snapshots above bind this machine. Temporary generated-freshness environment is gate-managed; no full production dataset admitted."
    start_again = identity()
    if start_again != start:
        wrapper.update({"outcome": "UNRUN", "reason": "Source changed during environment preflight",
                        "exit_code": None, "end": start_again})
        paths["receipt"].write_text(json.dumps(wrapper, indent=2) + "\n")
        print("UNRUN", wrapper["reason"], str(paths["receipt"]))
        return 3
    wrapper["started_at_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    began = time.monotonic()
    with paths["log"].open("wb") as log:
        process = subprocess.Popen(argv, cwd=cwd, env=environment,
                                   stdout=log, stderr=subprocess.STDOUT)
        _, status, usage = os.wait4(process.pid, 0)
        process.returncode = os.waitstatus_to_exitcode(status)
    wrapper["wall_seconds"] = time.monotonic() - began
    wrapper["ended_at_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    wrapper["exit_code"] = process.returncode
    wrapper["end"] = identity()
    wrapper["source_unchanged"] = wrapper["end"] == start
    wrapper["outcome"] = {0: "PASS", 1: "FAIL", 2: "UNRUN"}.get(process.returncode, "ERROR")
    wrapper["complete_gate_verdict_admitted"] = wrapper["source_unchanged"] and process.returncode in {0, 1}
    wrapper["max_rss_kib"] = usage.ru_maxrss
    resources = {"method": "OS wait4 child rusage; Linux maxrss KiB, including reaped descendant usage",
                 "wall_seconds": wrapper["wall_seconds"], "max_rss_kib": usage.ru_maxrss,
                 "user_seconds": usage.ru_utime, "system_seconds": usage.ru_stime,
                 "major_page_faults": usage.ru_majflt, "minor_page_faults": usage.ru_minflt,
                 "voluntary_context_switches": usage.ru_nvcsw,
                 "involuntary_context_switches": usage.ru_nivcsw,
                 "exit_code": process.returncode}
    paths["resource"].write_text(json.dumps(resources, indent=2) + "\n")
    wrapper["outputs"] = {name: {"path": str(path), "bytes": path.stat().st_size,
                                 "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
                           for name, path in paths.items() if name != "receipt"}
    paths["receipt"].write_text(json.dumps(wrapper, indent=2) + "\n")
    print(wrapper["outcome"], "exit", process.returncode, "wall", wrapper["wall_seconds"],
          "RSS_KiB", wrapper["max_rss_kib"], "source_unchanged", wrapper["source_unchanged"],
          str(paths["receipt"]))
    return process.returncode


if __name__ == "__main__":
    raise SystemExit(main())
