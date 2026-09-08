"""Reconcile complete tested identities and removal finding deltas."""
import ast
import hashlib
import json
from pathlib import Path

ROOT=Path.cwd(); DIR=ROOT/"_build/gy-gaps/d1/fabric"
base_path=DIR/"owner-importer-contract-final.json"
base=json.loads(base_path.read_text())
def ids(receipt):
    out={}
    for line in receipt["stdout"].splitlines():
        if line.startswith(("PASSED ","FAILED ","SKIPPED ","ERROR ")):
            status,node,*_=line.split()
            out[node]=status
    return out
base_ids=ids(base)
selectors=[p for p in base["command"] if p.split("::",1)[0].endswith(".py")]
paths={Path(p.split("::",1)[0]) for p in selectors}
independent=0
for selector in selectors:
    path=Path(selector.split("::",1)[0])
    selected_name=selector.rsplit("::",1)[1] if "::" in selector else None
    tree=ast.parse(path.read_text())
    for node in ast.walk(tree):
        if not isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) or not node.name.startswith("test_"):continue
        if selected_name is not None and node.name!=selected_name:continue
        count=1
        for deco in node.decorator_list:
            if isinstance(deco,ast.Call) and isinstance(deco.func,ast.Attribute) and deco.func.attr=="parametrize":
                values=deco.args[1]
                if not isinstance(values,(ast.List,ast.Tuple)):
                    raise ValueError(f"unevaluated parameter source: {path}:{node.lineno}")
                count*=len(values.elts)
        independent+=count
assert len(base_ids)==independent and all(v=="PASSED" for v in base_ids.values())
out={"baseline":{"receipt":str(base_path.relative_to(ROOT)),"sha256":hashlib.sha256(base_path.read_bytes()).hexdigest(),
                 "test_file_denominator":len(paths),"reported_test_identities":len(base_ids),"independent_ast_parameter_count":independent},
     "removal_deltas":{}}
for filename in ("shared-catalog-removal-final.json","bulk-source-removal-final.json","source-comparison-removal-final.json","current-contract-removal.json"):
    path=DIR/filename;r=json.loads(path.read_text()); observed=ids(r)
    mode=r["command"][-1]
    probe_tree=ast.parse((ROOT/"_build/gy_gaps/d1/fabric_removal.py").read_text())
    branch=next(node for node in ast.walk(probe_tree) if isinstance(node,ast.If)
        and isinstance(node.test,ast.Compare) and isinstance(node.test.left,ast.Name)
        and node.test.left.id=="MODE" and isinstance(node.test.comparators[0],ast.Constant)
        and node.test.comparators[0].value==mode)
    selection=next(node.value for node in branch.body if isinstance(node,ast.Assign)
                   and any(isinstance(t,ast.Name) and t.id=="selected" for t in node.targets))
    selected=ast.literal_eval(selection)
    expected={key for key in base_ids if key.split("[",1)[0].rsplit("::",1)[-1] in selected}
    assert set(observed)==expected, (filename,sorted(expected-set(observed)),sorted(set(observed)-expected))
    assert observed and all(k in base_ids for k in observed)
    assert sum(line.startswith(("PASSED ","FAILED ","SKIPPED ","ERROR ")) for line in r["stdout"].splitlines())==len(observed)
    baseline_failed={key for key in observed if base_ids[key]!="PASSED"}
    failed={key for key,status in observed.items() if status!="PASSED"}
    assert r["returncode"]==1 and failed and any(status=="PASSED" for status in observed.values())
    out["removal_deltas"][filename]={"sha256":hashlib.sha256(path.read_bytes()).hexdigest(),
        "invoked_identity_denominator":len(observed),"all_invoked_identities_exist_in_complete_green_baseline":True,
        "complete_invocation_reconciliation":"actual probe selection AST expanded over complete green baseline equals every observed identity",
        "added_finding_identities":sorted(failed-baseline_failed),"lost_baseline_finding_identities":sorted(baseline_failed-failed),
        "positive_control_identities":[key for key,status in observed.items() if status=="PASSED"]}
prior_path=DIR/"catalog-bulk-gate.json";final_path=DIR/"catalog-bulk-final.json"
prior=json.loads(json.loads(prior_path.read_text())["stdout"])
final=json.loads(json.loads(final_path.read_text())["stdout"])
identity=lambda finding:json.dumps(finding,sort_keys=True,separators=(",",":"))
prior_ids={identity(finding) for finding in prior["finding_identities"]}
final_ids={identity(finding) for finding in final["finding_identities"]}
assert prior["denominator"]==final["denominator"]
out["full_catalog_delta"]={"prior_receipt_sha256":hashlib.sha256(prior_path.read_bytes()).hexdigest(),
    "final_receipt_sha256":hashlib.sha256(final_path.read_bytes()).hexdigest(),
    "denominator":final["denominator"],"added_finding_identities":[json.loads(v) for v in sorted(final_ids-prior_ids)],
    "lost_finding_identities":[json.loads(v) for v in sorted(prior_ids-final_ids)],
    "bound_identity_digest_unchanged":prior["bound_identity_digest"]==final["bound_identity_digest"]}
print(json.dumps(out,indent=2,sort_keys=True))
