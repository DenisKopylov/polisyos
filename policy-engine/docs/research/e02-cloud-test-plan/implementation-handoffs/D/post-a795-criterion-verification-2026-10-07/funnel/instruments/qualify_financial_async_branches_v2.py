from pathlib import Path
import ast,hashlib,json,subprocess
R=Path('/dev/shm/e02-D-oct07-continuation'); O=Path('/dev/shm/e02-D-post-a795-88ghpj7t/funnel'); A='a7efe4b431986c3d79f490879cf49dbdedb1349e'; C='cbc46a0bc87761bc2267a0daa84da489d6702e89'
def blob(ref,p): return subprocess.check_output(['git','-C',str(R),'show',ref+':'+p])
def sh(x):return hashlib.sha256(x).hexdigest()
def functions(raw):
    return {n.name:sh(ast.dump(n,include_attributes=False).encode()) for n in ast.parse(raw).body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef))}
p='policy-engine/src/polisyos/common/async_tools.py'; aa=blob(A,p); cc=blob(C,p); af=functions(aa); cf=functions(cc)
paths=[
'policy-engine/tests/integration/scientist/methods/search/funnel/test_cache_settlement_binding.py',
'policy-engine/tests/integration/core/llm/test_gateway_response_text_cost.py',
'policy-engine/src/polisyos/scientist/orchestration/engine/budget.py',
'policy-engine/src/polisyos/scientist/orchestration/engine/budget_ledger.py',
'policy-engine/src/polisyos/scientist/orchestration/engine/budget_middleware.py',
'policy-engine/src/polisyos/scientist/orchestration/llm/budget_enforcer.py',
'policy-engine/src/polisyos/scientist/orchestration/llm/gateway_client.py',
'policy-engine/src/polisyos/scientist/orchestration/llm/factory.py',
'policy-engine/src/polisyos/core/llm/response.py',
'policy-engine/src/polisyos/core/llm/settlement.py',
'policy-engine/src/polisyos/core/llm/traced_client.py',
'policy-engine/src/polisyos/scientist/orchestration/llm/prompt_cache.py',
'policy-engine/src/polisyos/scientist/policy_design/adversary.py',
'policy-engine/src/polisyos/scientist/policy_design/translator.py',
'policy-engine/src/polisyos/scientist/methods/search/funnel/types.py',
'policy-engine/src/polisyos/scientist/methods/search/funnel/level3_medium.py',
'policy-engine/src/polisyos/scientist/orchestration/workflows/engine_simple.py']
rows=[]
for name in paths:
    try: old=blob(A,name); cur=blob(C,name)
    except subprocess.CalledProcessError:continue
    t=ast.parse(cur)
    imported_helpers=[ast.unparse(n) for n in ast.walk(t) if isinstance(n,ast.ImportFrom) and n.module and 'async_tools' in n.module]
    helper_calls=[ast.unparse(n.func) for n in ast.walk(t) if isinstance(n,ast.Call) and (isinstance(n.func,ast.Name) and n.func.id in ('run_coro_sync','run_blocking_async','get_shared_executor') or isinstance(n.func,ast.Attribute) and n.func.attr in ('run_coro_sync','run_blocking_async','get_shared_executor'))]
    direct_asyncio=[ast.unparse(n.func) for n in ast.walk(t) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and isinstance(n.func.value,ast.Name) and n.func.value.id=='asyncio' and n.func.attr in ('run','get_running_loop')]
    rows.append({'path':name,'a7_sha256':sh(old),'cbc_sha256':sh(cur),'same_blob':old==cur,'async_tools_imports':imported_helpers,'async_tools_calls':helper_calls,'direct_asyncio_calls':direct_asyncio})
value={'historical_source':A,'current_context':C,'common_async_tools':{'path':p,'a7_sha256':sh(aa),'cbc_sha256':sh(cc),'same_blob':False,'top_level_definitions':{name:{'a7_ast_sha256':af.get(name),'cbc_ast_sha256':cf.get(name),'same_ast':af.get(name)==cf.get(name)} for name in sorted(af.keys()|cf.keys())}},'selected_financial_and_native_caller_paths':rows,'predicate_basis':{'cache18':'Historical controlled native cache tests call actual generate via asyncio.run; supported invoke adapter also calls asyncio.run. No selected financial/test module imports/calls the shared executor helpers. The current native policy workers use their own direct asyncio.run outside a running loop, unchanged source. This is source/caller-edge qualification, not a new runtime replay.','raw32':'Historical actual response-text cells are native async pytest operations/direct awaits. No selected module imports/calls changed shared executor helpers. Original runtime source remains A7.','limits':'Common async_tools blob did change. No blanket A7 module/input equality or new current PASS is asserted. Active-event-loop/shared-executor properties belong to their actual new caller tests. Source inspection cannot certify deployment-wide unobserved dynamic calls.','original_outputs':'Committed A7 actual command/fullstreams/lossless snapshots remain canonical evidence; only source identity/caller edge is carried.'},'P41':'not_established/no inherited-red claim'}
p=O/'A7-financial-current-async-call-edge-qualification-v2.json';p.write_text(json.dumps(value,indent=2)+'\n');print(json.dumps({'path':str(p),'sha256':sh(p.read_bytes()),'same_blob_rows':sum(r['same_blob'] for r in rows),'rows':len(rows),'async_helper_calls':sum(len(r['async_tools_calls']) for r in rows),'async_helper_imports':sum(len(r['async_tools_imports']) for r in rows)},indent=2))
