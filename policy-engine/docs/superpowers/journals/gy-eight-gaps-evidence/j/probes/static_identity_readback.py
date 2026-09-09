"""Reconcile native/static input path identity sets against retained executions."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT=Path.cwd()


def main() -> int:
    rows=[]
    for component,roots in (("d1",["src","tools","tests"]),("k",["src","tools"])):
        path=ROOT/f"_build/gy-gaps/j/{component}-static-current.json"
        receipt=json.loads(path.read_bytes())
        assert receipt["returncode"]==0 and not receipt["timed_out"]
        measured=json.loads(receipt["stdout"])
        indexed={p for p in subprocess.check_output(["git","ls-files","-z","--cached","--others","--exclude-standard","--",*roots],text=True).split("\0") if p.endswith(".py") and Path(p).is_file()}
        ripgrep={p for p in subprocess.check_output(["rg","--files","--hidden",*roots],text=True).splitlines() if p.endswith(".py")}
        recursive={p.as_posix() for name in roots for p in Path(name).rglob("*.py")}
        walked={str(Path(directory)/name) for root in roots for directory,_,names in os.walk(root) for name in names if name.endswith(".py")}
        assert indexed==ripgrep==recursive==walked
        hashes={p:"sha256:"+hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in sorted(indexed)}
        basis="sha256:"+hashlib.sha256(json.dumps(hashes,sort_keys=True,separators=(",",":")).encode()).hexdigest()
        assert basis==measured["source_custody"]["full_current_path_and_raw_hash_basis"]
        assert len(indexed)==measured["source_custody"]["current_paths_git"]
        if component=="d1":
            native=json.loads(measured["owner_output"]["owner_stdout"])
            assert native["constructor_census"]["current_python_files"]==sum(p.startswith("src/") for p in indexed)
            baseline=json.loads(Path(measured["comparison"]["baseline_receipt"].split("@sha256:",1)[0]).read_bytes())
            old=json.loads(baseline["stdout"])
            assert old["predecessor_replacement_census"]["denominator"]["git"]==measured["source_custody"]["baseline_paths_git_tree"]
        else:
            native=measured["owner_output"]["owner_result"]
            assert native["source_denominator"]["rglob_py"]==len(recursive)
            assert native["source_denominator"]["os_walk_py"]==len(walked)
        rows.append({"component":component,"receipt_ref":path.relative_to(ROOT).as_posix()+"@sha256:"+hashlib.sha256(path.read_bytes()).hexdigest(),"actual_native_population_equals_git_rg_rglob_oswalk_sets":True,"raw_input_basis_still_exact":basis,"unreadable":[],"path_identity_differences":[]})
    print(json.dumps({"scope":"static input identity reconciliation only; no native owner or runtime rerun","executions":rows},indent=2))
    return 0


if __name__=="__main__": raise SystemExit(main())
