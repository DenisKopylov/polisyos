"""Run the existing bounded D1/K static owners with complete source custody.

No runtime owners, tests, canonical writers or protected data are imported/read.
D1's existing test module exposes a static census; its runtime fixtures stay idle.
K executes only the exact existing source function, not its surrounding module.
"""
from __future__ import annotations

import argparse
import ast
from contextlib import redirect_stdout
import hashlib
import importlib
import io
import json
import os
from pathlib import Path
import subprocess
import tarfile
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
D1_REV = "4f54c80cc4f668da81943b773536c3b92e71eae8"
L_REV = "8a9b92b416aaf5b2bc68fc6901fc5dbe098ced11"
D1_RECEIPT = "docs/superpowers/journals/gy-eight-gaps-evidence/d1/root/strangle-checkpoint.json"
K_ARTIFACT = "architecture/policy_design_case/layer3_gy_openalex_skg_ingest_records_v2.json"
K_OWNER = "tools/quality/validation/check_layer3_gy_openalex_artifacts.py"


def sha(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def current_paths(roots: list[str]) -> set[str]:
    git = {p for p in subprocess.check_output(["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard", "--", *roots], cwd=ROOT).decode().split("\0") if p.endswith(".py") and (ROOT/p).is_file()}
    independent = {p for p in subprocess.check_output(["rg", "--files", "--hidden", *roots], cwd=ROOT).decode().splitlines() if p.endswith(".py")}
    if git != independent:
        raise ValueError("current source path mismatch:" + json.dumps({"git_only": sorted(git-independent),"rg_only":sorted(independent-git)}))
    return git


def historical_paths(revision: str, roots: list[str]) -> set[str]:
    prefix = "policy-engine/"
    first = {p for p in subprocess.check_output(["git","ls-tree","-rz","--name-only",revision,"--",*roots],cwd=ROOT).decode().split("\0") if p.endswith(".py")}
    proc = subprocess.Popen(["git","archive","--format=tar",revision,"--",*[prefix+root for root in roots]],cwd=ROOT.parent,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    second = set()
    assert proc.stdout is not None
    with tarfile.open(fileobj=proc.stdout, mode="r|") as archive:
        for member in archive:
            if member.isfile() and member.name.endswith(".py"):
                if not member.name.startswith(prefix): raise ValueError("unexpected archive root")
                second.add(member.name.removeprefix(prefix))
    proc.stdout.close()
    stderr = proc.stderr.read().decode() if proc.stderr is not None else ""
    rc = proc.wait()
    if rc or first != second:
        raise ValueError("baseline source path mismatch:" + json.dumps({"rc":rc,"stderr":stderr,"git_only":sorted(first-second),"archive_only":sorted(second-first)}))
    return first


def snapshot(paths: set[str]) -> dict[str, str]:
    values = {}
    unreadable = []
    for path in sorted(paths):
        try:
            raw=(ROOT/path).read_bytes()
            ast.parse(raw.decode("utf-8"),filename=path)
            values[path]=sha(raw)
        except (OSError,UnicodeError,SyntaxError) as exc:
            unreadable.append({"path":path,"status":"ambiguous","error":f"{type(exc).__name__}:{exc}"})
    if unreadable:
        raise ValueError("source_unreadable:"+json.dumps(unreadable))
    return values


def semantic_calls(paths: set[str], revision: str | None) -> list[dict[str, Any]]:
    """Separate lexical owner/ordinal identities from changing line coordinates."""
    rows=[]
    for path in sorted(paths):
        raw=(ROOT/path).read_bytes() if revision is None else subprocess.check_output(["git","show",revision+":policy-engine/"+path],cwd=ROOT)
        source=raw.decode("utf-8")
        # The complete source population is established independently above;
        # here only paths represented by the already-complete native census run.
        tree=ast.parse(source,filename=path)
        class Visitor(ast.NodeVisitor):
            def __init__(self): self.scope=[]; self.ordinals={}
            def enter(self,node):
                self.scope.append(node.name)
                self.generic_visit(node)
                self.scope.pop()
            visit_FunctionDef=enter
            visit_AsyncFunctionDef=enter
            visit_ClassDef=enter
            def visit_Call(self,node):
                call=ast.unparse(node.func)
                if call.rsplit(".",1)[-1] in {"produce_from_catalog","produce_from_fabric_fetch"}:
                    scope=".".join(self.scope) or "<module>"
                    key=(scope,call)
                    ordinal=self.ordinals.get(key,0)+1; self.ordinals[key]=ordinal
                    rows.append({"identity":f"{path}::{scope}::{call}[{ordinal}]","path":path,"line":node.lineno,"column":node.col_offset,"call":call,"call_ast_sha256":sha(ast.dump(node,include_attributes=False).encode())})
                self.generic_visit(node)
        Visitor().visit(tree)
    return rows


def delta(before: list[dict], after: list[dict], key: str) -> dict:
    left={row[key]:row for row in before}; right={row[key]:row for row in after}
    if len(left)!=len(before) or len(right)!=len(after): raise ValueError("duplicate comparison identities")
    common=left.keys()&right.keys()
    ignored={key,"line","column"}
    return {"baseline_identity_denominator":len(left),"current_identity_denominator":len(right),
            "removed_identities":sorted(left.keys()-right.keys()),"added_identities":sorted(right.keys()-left.keys()),
            "coordinate_shifts":[{"identity":identity,"baseline":{"line":left[identity].get("line"),"column":left[identity].get("column")},"current":{"line":right[identity].get("line"),"column":right[identity].get("column")}} for identity in sorted(common) if (left[identity].get("line"),left[identity].get("column"))!=(right[identity].get("line"),right[identity].get("column"))],
            "semantic_member_changes":[{"identity":identity,"baseline":{k:v for k,v in left[identity].items() if k not in ignored},"current":{k:v for k,v in right[identity].items() if k not in ignored}} for identity in sorted(common) if {k:v for k,v in left[identity].items() if k not in ignored}!={k:v for k,v in right[identity].items() if k not in ignored}]}


def d1() -> tuple[dict,dict]:
    buffer=io.StringIO()
    with redirect_stdout(buffer):
        importlib.import_module("_build.gy_gaps.d1_strangle").main()
    original=buffer.getvalue()
    result=json.loads(original)
    baseline_receipt=json.loads((ROOT/D1_RECEIPT).read_bytes())
    if baseline_receipt["returncode"] != 0: raise ValueError("D1 baseline receipt is not complete")
    baseline=json.loads(baseline_receipt["stdout"])
    before_calls=baseline["predecessor_replacement_census"]["calls"]
    after_calls=result["predecessor_replacement_census"]["calls"]
    before_paths={row["path"] for row in before_calls}
    after_paths={row["path"] for row in after_calls}
    old_sem=semantic_calls(before_paths,D1_REV)
    new_sem=semantic_calls(after_paths,None)
    exact=lambda rows:{(row["path"],row["line"],row["call"]) for row in rows}
    if exact(old_sem)!=exact(before_calls) or exact(new_sem)!=exact(after_calls):
        raise ValueError("D1 receipt does not match its claimed source revision/native census")
    comparison={
        "baseline_receipt":D1_RECEIPT+"@"+sha((ROOT/D1_RECEIPT).read_bytes()),
        "baseline_source_revision":D1_REV,
        "constructor_delta":delta(baseline["constructor_census"]["sites"],result["constructor_census"]["sites"],"identity"),
        "exact_lexical_caller_delta":{"removed":[list(row) for row in sorted(exact(before_calls)-exact(after_calls))],"added":[list(row) for row in sorted(exact(after_calls)-exact(before_calls))]},
        "stable_caller_delta":delta(old_sem,new_sem,"identity"),
        "prior_semantic_removals":"retained prior measurements only; no current runtime reexecution claimed",
    }
    return {"owner_stdout":original},comparison


def k() -> tuple[dict,dict]:
    source=(ROOT/K_OWNER).read_bytes()
    tree=ast.parse(source.decode(),filename=K_OWNER)
    definitions=[node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=="recompute_openalex_accuracy_strangle"]
    if len(definitions)!=1: raise ValueError("K static owner identity unresolved")
    namespace={"Path":Path,"json":json,"Any":Any}
    exec(compile(ast.Module(body=definitions,type_ignores=[]),K_OWNER,"exec"),namespace)
    result=namespace[definitions[0].name](ROOT)
    raw=subprocess.check_output(["git","show",L_REV+":policy-engine/"+K_ARTIFACT],cwd=ROOT)
    if (ROOT/K_ARTIFACT).read_bytes()!=raw:
        raise ValueError("current K artifact differs from selected immutable baseline")
    declared=[ast.literal_eval(node.value) for node in tree.body if isinstance(node,ast.Assign) and any(isinstance(target,ast.Name) and target.id=="INGEST_PATH" for target in node.targets)]
    if declared!=[K_ARTIFACT]: raise ValueError("selected K output differs from actual owner")
    artifact=json.loads(raw)
    found=[]
    def visit(value,path=()):
        if isinstance(value,dict):
            if value.get("caller_guard_ref")=="recompute_openalex_accuracy_strangle": found.append((path,value))
            for key,item in value.items(): visit(item,(*path,key))
        elif isinstance(value,list):
            for index,item in enumerate(value): visit(item,(*path,index))
    visit(artifact)
    if len(found)!=1: raise ValueError("K prior strangle identity unresolved")
    pointer,full=found[0]
    baseline={key:full[key] for key in result}
    exact=lambda rows:{(row["path"],row["line"],row["column"]) for row in rows}
    comparison={"baseline_artifact":K_ARTIFACT+"@"+L_REV,"baseline_raw_sha256":sha(raw),"baseline_pointer":list(pointer),
                "returned_owner_projection_equal":baseline==result,
                "changed_returned_fields":[{"field":key,"baseline":baseline[key],"current":result[key]} for key in result if baseline[key]!=result[key]],
                "exact_forbidden_reference_delta":{"removed":[list(row) for row in sorted(exact(baseline["remaining_callers"])-exact(result["remaining_callers"]))],"added":[list(row) for row in sorted(exact(result["remaining_callers"])-exact(baseline["remaining_callers"]))]},
                "native_owner_function_sha256":sha(ast.get_source_segment(source.decode(),definitions[0]).encode())}
    return {"owner_result":result},comparison


def main() -> int:
    parser=argparse.ArgumentParser(); parser.add_argument("component",choices=["d1","k"]); args=parser.parse_args()
    roots=["src","tools","tests"] if args.component=="d1" else ["src","tools"]
    revision=D1_REV if args.component=="d1" else L_REV
    paths=current_paths(roots); before=snapshot(paths)
    baseline=historical_paths(revision,roots)
    owner_output,comparison=d1() if args.component=="d1" else k()
    after=snapshot(paths); final_paths=current_paths(roots)
    if before!=after or final_paths!=paths:
        raise ValueError("static source changed during execution:"+json.dumps({"changed":sorted(p for p in before if before[p]!=after.get(p)),"added_paths":sorted(final_paths-paths),"removed_paths":sorted(paths-final_paths)}))
    selected={"d1":["_build/gy_gaps/d1_strangle.py","tests/repo_quality/tools/test_gy_d1_catalog_wiring.py","src/polisyos/runtime/http/services/control/nl_pipeline.py","src/polisyos/runtime/http/services/control/run_lifecycle.py","src/polisyos/runtime/quality/acquisition_planner.py","src/polisyos/fabric/retrieval/executor.py"],"k":[K_OWNER,"src/polisyos/ir/analytics/literature.py"]}[args.component]
    print(json.dumps({"component":args.component,"current_revision":subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip(),
                      "owner_output":owner_output,"comparison":comparison,
                      "source_custody":{"roots":roots,"suffix":".py","current_paths_git":len(paths),"current_paths_rg":len(final_paths),"baseline_revision":revision,"baseline_paths_git_tree":len(baseline),"baseline_paths_tar_headers":len(baseline),"path_delta":{"added":sorted(paths-baseline),"removed":sorted(baseline-paths)},"full_current_path_and_raw_hash_basis":sha(json.dumps(before,sort_keys=True,separators=(",",":")).encode()),"changed_during_execution":[],"executing_owners":{path:sha((ROOT/path).read_bytes()) for path in selected},"no_runtime_tests_or_canonical_writes":True}},indent=2,sort_keys=True))
    return int(args.component=="k" and not comparison["returned_owner_projection_equal"])


if __name__=="__main__": raise SystemExit(main())
