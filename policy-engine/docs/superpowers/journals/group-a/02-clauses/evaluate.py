"""Evaluate bounded clause predicates from source and retained execution receipts.

No product imports, writes, or gates. The ledger parser probe executes only AST-
selected pure parser definitions; the register is not read by this instrument.
"""
import ast
from collections import namedtuple
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[6]
OUT = Path(__file__).resolve().parent
BASE = "63bdb9640"


def read(path):
    return subprocess.check_output(["git", "show", f"{BASE}:{path}"], cwd=ROOT).decode()


def value(path):
    return json.loads(read(path))


loop_path = "policy-engine/tools/quality/validation/check_layer3_gy_loop_artifacts.py"
loop = ast.parse(read(loop_path))
requests = next(n for n in loop.body if isinstance(n, ast.FunctionDef) and n.name == "canonical_loop_requests")
request_members = [
    {k.arg: ast.literal_eval(k.value) for k in n.keywords}
    for n in ast.walk(requests)
    if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "CanonicalLoopRequest"
]
constants = {}
for n in loop.body:
    if isinstance(n, ast.Assign):
        for target in n.targets:
            if isinstance(target, ast.Name) and target.id in {"PROOFS_PATH", "GRADED_OUTCOME_PATH"}:
                constants[target.id] = ast.literal_eval(n.value)
graded = value("policy-engine/" + constants["GRADED_OUTCOME_PATH"])
proofs = value("policy-engine/" + constants["PROOFS_PATH"])["proofs"]
production = [p for p in request_members if p["catalog_mode"] == "production"]
population = graded["population"]["members"]
categories = graded["graded_outcomes"] + graded["honest_non_value_outcomes"] + graded["unmeasurable_outcomes"]
assert len(production) == len(population) == len(categories) == graded["population"]["member_count"]
assert {(p["job_id"], p["run_id"]) for p in population} == {(p["job_id"], p["run_id"]) for p in categories}
fixture_readbacks = [{"request": p["http_request_id"], "job_id": p["job_id"], "surfaces": p["surface_readbacks"]} for p in proofs]
assert not {p["job_id"] for p in proofs} & {p["job_id"] for p in population}

parser_path = "policy-engine/tools/quality/validation/check_debt_ledger.py"
tree = ast.parse(read(parser_path))
selected = []
for n in tree.body:
    if isinstance(n, ast.FunctionDef) and n.name in {"_parse_gy_tasks", "_gy_task_census", "_plain"}:
        selected.append(n)
    if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id in {"_GY_TASK_ROW", "_WorkRow"} for t in n.targets):
        selected.append(n)
env = {"re": re, "namedtuple": namedtuple}
exec(compile(ast.Module(body=selected, type_ignores=[]), parser_path, "exec"), env)
plan_path = "policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md"
plan = read(plan_path)
start, finish = plan.index("## 8.6 "), plan.index("## 9. ")
without = plan[:start] + plan[finish:]
before = env["_parse_gy_tasks"](plan)
after = env["_parse_gy_tasks"](without)
census = env["_gy_task_census"](plan)

f1_path = "policy-engine/tools/quality/validation/check_layer3_workflow_failure_authority.py"
f1_tree = ast.parse(read(f1_path))
surfaces = next(ast.literal_eval(n.value) for n in f1_tree.body if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "SURFACE_NAMES" for t in n.targets))
fixture_test_path = "policy-engine/tests/unit/runtime/quality/test_workspace_loop.py"
fixture_test = next(n for n in ast.walk(ast.parse(read(fixture_test_path))) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == "test_slice0_groundable_fixture_exits_partial_without_design_candidate")

result = {
    "base": BASE,
    "scope": "one complete three-request canonical population; two fixture proofs; one graded report; one plan and its actual pure parser; one canonical F1 surface tuple",
    "canonical_requests": request_members,
    "production_population": graded["population"],
    "production_categories": categories,
    "independent_request_and_artifact_denominators_equal": True,
    "recomputed_rate": {"numerator": len(graded["graded_outcomes"]), "denominator": len(population), "value": len(graded["graded_outcomes"])/len(population)},
    "published_summary": graded["summary"],
    "fixture_job_intersection_with_production": [],
    "fixture_readbacks": fixture_readbacks,
    "fixture_test_ast": {"path": fixture_test_path, "name": fixture_test.name, "line": fixture_test.lineno, "calls": [ast.unparse(n.func) for n in ast.walk(fixture_test) if isinstance(n, ast.Call)]},
    "artifact_history": {p: subprocess.check_output(["git", "log", "-1", "--format=%H %cI", BASE, "--", "policy-engine/"+p], cwd=ROOT).decode().strip() for p in constants.values()},
    "ledger_parser_probe": {"path": parser_path, "selected_ast_nodes": [getattr(n, "name", ast.unparse(n.targets[0]) if isinstance(n, ast.Assign) else "") for n in selected], "in_memory_change": "remove entire section 8.6 only", "work_output_identical": before == after, "status_census_identical": census == env["_gy_task_census"](without), "status_census": dict(census), "complete_table_rows": sum(c for _,c in census), "open_rows": len(before)},
    "f1_surface_tuple": list(surfaces),
    "f1_denominator_with_worker": len(surfaces)+1,
    "raw_receipts": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((OUT/"raw").glob("*.json"))},
    "exit_code": 0,
}
(OUT/"evaluation.json").write_text(json.dumps(result, indent=2)+"\n")
print(json.dumps(result, indent=2))
