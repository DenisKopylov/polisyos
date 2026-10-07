"""Complete pinned tracked Python census plus bounded native typing consumers."""
from __future__ import annotations
import argparse
import ast
import asyncio
import collections.abc
import hashlib
import inspect
import json
import os
from pathlib import Path
import subprocess
import sys
import typing

parser = argparse.ArgumentParser()
parser.add_argument('--target-sha', required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
root = Path(__file__).resolve().parents[7]
source_path = 'policy-engine/src/polisyos/common/async_tools.py'
module_name = 'polisyos.common.async_tools'
ls = subprocess.check_output(['git', 'ls-tree', '-r', '-z', args.target_sha], cwd=root)
entries = []
for entry in ls.split(b'\0'):
    if not entry:
        continue
    meta, path = entry.split(b'\t', 1)
    mode, kind, blob = meta.decode().split()
    if kind == 'blob':
        entries.append((path.decode(), blob))
python_entries = [(path, blob) for path, blob in entries if path.endswith('.py')]
packed = subprocess.check_output(['git', 'cat-file', '--batch'], input=('\n'.join(blob for _, blob in python_entries)+'\n').encode(), cwd=root)
offset = 0
consumers = []
parse_failures = []
findings = []
for path, blob in python_entries:
    line_end = packed.index(b'\n', offset)
    header = packed[offset:line_end].split()
    size = int(header[2])
    raw = packed[line_end+1:line_end+1+size]
    offset = line_end+1+size+1
    assert header[0].decode() == blob
    try:
        tree = ast.parse(raw, filename=path)
    except (SyntaxError, UnicodeDecodeError, ValueError) as exc:
        parse_failures.append({'path':path,'blob':blob,'error':str(exc)})
        continue
    aliases = set()
    facts = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == module_name:
            names = [a.name for a in node.names]
            facts.append({'kind':'from_import','line':node.lineno,'names':names})
            if 'T' in names or '*' in names:
                findings.append({'path':path,'line':node.lineno,'kind':'T_or_star_import','names':names})
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == module_name:
                    aliases.add(alias.asname or 'polisyos')
                    facts.append({'kind':'module_import','line':node.lineno,'alias':alias.asname})
        elif isinstance(node, ast.ImportFrom) and node.module == 'polisyos.common':
            for alias in node.names:
                if alias.name == 'async_tools':
                    aliases.add(alias.asname or alias.name)
                    facts.append({'kind':'module_alias','line':node.lineno,'alias':alias.asname})
        elif isinstance(node, ast.Constant) and node.value == module_name:
            facts.append({'kind':'constant_module_reference','line':node.lineno})
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr == 'T':
            chain = ast.unparse(node.value)
            if chain in aliases or chain == module_name:
                findings.append({'path':path,'line':node.lineno,'kind':'module_T_attribute','expression':ast.unparse(node)})
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'getattr' and len(node.args)>=2:
            if isinstance(node.args[1], ast.Constant) and node.args[1].value == 'T':
                chain = ast.unparse(node.args[0])
                if chain in aliases or chain == module_name:
                    findings.append({'path':path,'line':node.lineno,'kind':'constant_T_reflection','expression':ast.unparse(node)})
    if facts:
        reflections = [{'line':n.lineno,'expression':ast.unparse(n)} for n in ast.walk(tree) if isinstance(n,ast.Call) and ('get_type_hints' in ast.unparse(n.func) or (isinstance(n.func,ast.Name) and n.func.id=='getattr'))]
        consumers.append({'path':path,'blob':blob,'facts':facts,'reflection_calls':reflections})
assert offset == len(packed)
raw = subprocess.check_output(['git','show',args.target_sha+':'+source_path],cwd=root)
assert (root/source_path).read_bytes()==raw, 'runtime producer differs from pinned Git input'
tree = ast.parse(raw)
params = [{'function':n.name,'params':[p.name for p in n.type_params]} for n in tree.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.type_params]
global_names = []
for node in tree.body:
    if isinstance(node,(ast.Assign,ast.AnnAssign)):
        targets=node.targets if isinstance(node,ast.Assign) else [node.target]
        if any(isinstance(t,ast.Name) and t.id=='T' for t in targets):global_names.append(ast.unparse(node))
from polisyos.common import async_tools
assert Path(async_tools.__file__).resolve()==(root/source_path).resolve()
namespace = dict(vars(async_tools), Awaitable=collections.abc.Awaitable, Callable=collections.abc.Callable)
reflections = []
for fact in params:
    function = getattr(async_tools,fact['function'])
    localns = {p.__name__:p for p in function.__type_params__}
    try:
        hints = typing.get_type_hints(function,globalns=namespace,localns=localns)
        reflections.append({'function':function.__name__,'type_params':[str(p) for p in function.__type_params__],'hints':{k:str(v) for k,v in hints.items()},'outcome':'PASS'})
    except Exception as exc:
        reflections.append({'function':function.__name__,'outcome':'FAIL','error':repr(exc)})
star = {}
exec('from polisyos.common.async_tools import *',star)
async def value():return 17
before_loop=async_tools.run_coro_sync(value())
async def nested():
    return async_tools.run_coro_sync(value()), await async_tools.run_blocking_async(lambda:23,unbounded=True)
inside_loop=asyncio.run(nested())
configuration = [(p,b) for p,b in entries if Path(p).name in {'pyproject.toml','mypy.ini','setup.cfg','setup.py','tox.ini','pytest.ini','pyrightconfig.json'}]
packet={'schema':'policyos.e02.finite_consumer_census.v1','target_sha':args.target_sha,'target_tree':subprocess.check_output(['git','rev-parse',args.target_sha+'^{tree}'],cwd=root,text=True).strip(),'complete_denominator':{'tracked_blob_files':len(entries),'tracked_python_files':len(python_entries),'parsed_python_files':len(python_entries)-len(parse_failures),'python_path_blob_manifest_sha256':hashlib.sha256(json.dumps(python_entries,separators=(',',':')).encode()).hexdigest(),'typing_configuration_files':len(configuration)},'parse_failures':parse_failures,'related_consumers':consumers,'required_T_or_star_consumers':findings,'source':{'path':source_path,'sha256':hashlib.sha256(raw).hexdigest(),'function_local_type_params':params,'global_T_assignments':global_names,'module_T_exposed':hasattr(async_tools,'T'),'star_T_exposed':'T' in star},'runtime_typing':reflections,'native_behavior':{'before_loop':before_loop,'inside_loop':inside_loop,'pass':before_loop==17 and inside_loop==(17,23)},'typing_configuration_refs':dict(configuration),'environment':{'python':sys.executable,'version':sys.version,'PYTHONPATH':os.environ.get('PYTHONPATH'),'runtime_module_file':async_tools.__file__},'limitations':['Complete tracked Python AST census, not a claim over opaque external distributions, arbitrary computed getattr/import strings, monkeypatched module exports or packaging not present in Git.','Correct namespace explicitly includes the annotation-only Awaitable/Callable and each function-local T; no module T is introduced.','Fresh baseline already lacked the global TypeVar/T residue; this verifies preservation rather than claiming a new deletion.']}
args.output.parent.mkdir(parents=True,exist_ok=True)
args.output.write_text(json.dumps(packet,indent=2)+'\n')
print(json.dumps(packet,indent=2))
