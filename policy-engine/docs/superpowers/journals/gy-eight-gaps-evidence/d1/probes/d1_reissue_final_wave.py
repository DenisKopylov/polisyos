"""One real producer run, then complete baseline and governing-removal gates."""
from __future__ import annotations
import ast, contextlib, hashlib, inspect, io, json, subprocess, sys
from pathlib import Path
import pytest

ROOT=Path.cwd()
TEST="tests/repo_quality/tools/test_layer3_gy_promotion_contract.py"

class Identities:
    def __init__(self): self.collected=[];self.failed=[]
    def pytest_collection_finish(self, session): self.collected=[item.nodeid for item in session.items]
    def pytest_runtest_logreport(self, report):
        if report.failed: self.failed.append(f"{report.nodeid}::{report.when}")

def hashes():
    from tests.repo_quality.tools.test_gy_d1_catalog_wiring import _current_python_paths
    sources, _ = _current_python_paths()  # independently reconciles full source identities
    selected={"tools/quality/validation/check_layer3_gy_promotion_contract.py", TEST}
    paths=subprocess.check_output(["git","ls-files","-z","--cached","--others","--exclude-standard","--","src",*sorted(selected)]).decode().split("\0")
    actual={p for p in paths if p.endswith(".py") and Path(p).is_file()}
    assert actual == set(sources) | selected
    return {p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in actual}

def run(label, args):
    tracker=Identities();stdout,stderr=io.StringIO(),io.StringIO();saved=sys.__stdout__
    try:
        sys.__stdout__=stdout
        with contextlib.redirect_stdout(stdout),contextlib.redirect_stderr(stderr):
            status=int(pytest.main(["-q","--tb=short","--show-capture=no",*args],plugins=[tracker]))
    finally: sys.__stdout__=saved
    packet={"gate":label,"command":[sys.executable,"-m","pytest","-q","--tb=short","--show-capture=no",*args],
            "returncode":status,"collected_ids":tracker.collected,"finding_ids":sorted(tracker.failed),
            "stdout":stdout.getvalue(),"stderr":stderr.getvalue()}
    print(json.dumps(packet),flush=True)
    return packet

def main():
    from tools.quality.validation import check_layer3_gy_promotion_contract as owner
    before=hashes();builder=owner._build_payload_with_comparison_plan;cached=[]
    def one_real_build(repo):
        if not cached: cached.append(builder(repo))
        import copy
        value,plan=cached[0]
        return copy.deepcopy(value),plan
    owner._build_payload_with_comparison_plan=one_real_build
    baseline=run("baseline",[TEST,"-k","reissue"])
    if baseline["returncode"]!=0 or baseline["finding_ids"] or len(cached)!=1:
        print(json.dumps({"result":"baseline_failed","source_hashes_stable":before==hashes()}));return 2
    # Remove the strict comparison, retaining every original marker and input.
    predicate=owner._is_authorized_v6_source_scope_epoch_reissue
    try:
        owner._is_authorized_v6_source_scope_epoch_reissue=lambda *_: True
        selected=TEST+"::test_n9_credal_epoch_reissue_refuses_other_frozen_drift[governing_value]"
        comparison=run("strict_predicate_removed",[selected])
    finally: owner._is_authorized_v6_source_scope_epoch_reissue=predicate
    # Delete only the equality refusal from the actual translator in memory.
    translator=owner._translate_n9_v6_receipt_epoch
    syntax=ast.parse(inspect.getsource(translator));function=syntax.body[0];removed=0
    for statement in function.body:
        if isinstance(statement,ast.If) and isinstance(statement.test,ast.Compare) and ast.unparse(statement.test)=="previous.model_dump(mode='json') != value":
            statement.body=[ast.Expr(ast.Constant("promotion_reissue_historical_receipt_incomplete"))];removed+=1
    assert removed==1
    namespace=dict(translator.__globals__)
    exec(compile(ast.fix_missing_locations(syntax),translator.__code__.co_filename,"exec"),namespace)
    try:
        owner._translate_n9_v6_receipt_epoch=namespace[translator.__name__]
        selected2=TEST+"::test_n9_reissue_translation_refuses_missing_defaulted_custody_field"
        custody=run("raw_custody_equality_removed",[selected2])
    finally:
        owner._translate_n9_v6_receipt_epoch=translator
        owner._build_payload_with_comparison_plan=builder
    after=hashes()
    expected=(comparison["returncode"]==1 and comparison["finding_ids"]==[selected+"::call"]
              and comparison["collected_ids"]==[selected]
              and custody["returncode"]==1 and custody["finding_ids"]==[selected2+"::call"]
              and custody["collected_ids"]==[selected2] and before==after)
    print(json.dumps({"result":"expected_red" if expected else "unexpected_result",
        "one_actual_live_build":len(cached)==1,"source_hashes_stable":before==after,
        "source_python_denominator":len(before),"source_identity_sets_independently_reconciled":True,"baseline_identity_denominator":len(baseline["collected_ids"]),
        "removed_source_identities":sorted(set(before)-set(after)),"added_source_identities":sorted(set(after)-set(before)),
        "changed_source_identities":sorted(k for k in set(before)&set(after) if before[k]!=after[k])}),flush=True)
    return 1 if expected else 2

if __name__=="__main__": raise SystemExit(main())
