"""Read-only AST census over the complete pinned tracked Python denominator."""
import ast
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[6]
BASE = '63bdb9640'
OUT = Path(__file__).resolve().parent
TERMS = ('estimand', 'normative', 'write_operation', 'assurance_level')

def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT).decode()

def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n')
    return {'path': str(path.relative_to(ROOT)), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}

def strings(node):
    if isinstance(node, (ast.Name, ast.arg)):
        yield node.id if isinstance(node, ast.Name) else node.arg
    elif isinstance(node, ast.Attribute): yield node.attr
    elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)): yield node.name
    elif isinstance(node, ast.alias):
        yield node.name
        if node.asname: yield node.asname
    elif isinstance(node, ast.keyword) and node.arg: yield node.arg

paths = sorted(x for x in git('ls-tree', '-r', '--name-only', BASE).splitlines() if x.endswith('.py'))
index = sorted(x for x in git('ls-files').splitlines() if x.endswith('.py') and '/journals/group-a/' not in x)
# Both are independently enumerated Git tree/index. Physical readability is tested below.
assert paths == index, {'tree_minus_index': sorted(set(paths)-set(index)), 'index_minus_tree':sorted(set(index)-set(paths))}
source = [x for x in paths if x.startswith('policy-engine/src/')]
errors = []
dups = []
dynamic = []
counts = Counter()
density = {t:[] for t in TERMS}
for rel in paths:
    p = ROOT/rel
    try:
        text = p.read_text()
        tree = ast.parse(text, filename=rel)
    except (OSError, UnicodeError, SyntaxError) as exc:
        errors.append({'path':rel, 'error':str(exc)})
        continue
    doc_ids = {id(n.body[0].value) for n in ast.walk(tree) if isinstance(n,(ast.Module,ast.ClassDef,ast.FunctionDef,ast.AsyncFunctionDef)) and n.body and isinstance(n.body[0],ast.Expr) and isinstance(n.body[0].value,ast.Constant) and isinstance(n.body[0].value.value,str)}
    rows = {t:{'raw_occurrences':text.lower().count(t),'identifier_nodes':0,'string_nodes':0,'docstring_nodes':0,'definitions':[],'calls':[]} for t in TERMS}
    for node in ast.walk(tree):
        if isinstance(node,ast.Dict):
            counts['dict_literals'] += 1
            seen = {}
            expressions = {}
            for key in node.keys:
                counts['dict_key_slots'] += 1
                if key is None:
                    counts['unpack_key_slots'] += 1
                    continue
                try:
                    val = ast.literal_eval(key)
                    hash(val)
                except (ValueError, TypeError, SyntaxError, MemoryError, RecursionError):
                    counts['nonliteral_key_slots'] += 1
                    expr = ast.dump(key,include_attributes=False)
                    if expr in expressions:
                        dynamic.append({'path':rel,'dict_line':node.lineno,'key':ast.unparse(key),'first_line':expressions[expr],'line':key.lineno,'kind':'same_expression_not_proof_of_runtime_equality'})
                    expressions[expr] = key.lineno
                    continue
                counts['literal_key_slots'] += 1
                if val in seen:
                    dups.append({'path':rel,'dict_line':node.lineno,'key':repr(val),'first_line':seen[val],'line':key.lineno,'expression':ast.unparse(key)})
                seen[val] = key.lineno
        if rel not in source: continue
        identifiers = list(strings(node))
        for term in TERMS:
            row = rows[term]
            row['identifier_nodes'] += sum(term in x.lower() for x in identifiers)
            if isinstance(node,ast.Constant) and isinstance(node.value,str) and term in node.value.lower():
                row['docstring_nodes' if id(node) in doc_ids else 'string_nodes'] += 1
            if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)) and term in node.name.lower():
                row['definitions'].append({'name':node.name,'line':node.lineno,'kind':type(node).__name__})
            if isinstance(node,ast.Call) and term in ast.unparse(node.func).lower():
                row['calls'].append({'callee':ast.unparse(node.func),'line':node.lineno})
    if rel in source:
        for term,row in rows.items():
            if row['raw_occurrences'] or row['identifier_nodes'] or row['string_nodes'] or row['docstring_nodes']:
                row['path']=rel
                row['package']=rel.split('/')[3] if rel.startswith('policy-engine/src/polisyos/') else rel.split('/')[2]
                density[term].append(row)

summaries = {}
for term,rows in density.items():
    groups = {}
    for mode in ('raw_occurrences','identifier_nodes','string_nodes','docstring_nodes'):
        selected = [r for r in rows if r[mode]>0]
        groups[mode]={'files':len(selected),'by_package_files':dict(sorted(Counter(r['package'] for r in selected).items())), 'by_package_nodes':dict(sorted((k,sum(r[mode] for r in selected if r['package']==k)) for k in {r['package'] for r in selected})), 'top_files':sorted([{'path':r['path'],'count':r[mode]} for r in selected],key=lambda x:(-x['count'],x['path']))[:15]}
    summaries[term]=groups
raw_receipt = save(OUT/'raw/census.json',{'base':git('rev-parse',BASE).strip(),'python':sys.version,'enumerators':['git ls-tree -r --name-only 63bdb9640','git ls-files excluding this journal'], 'paths':paths,'source_paths':source,'errors':errors,'density':density,'duplicate_literals':dups,'repeated_nonliteral_expressions':dynamic,'counts':dict(counts)})
summary={'base':git('rev-parse',BASE).strip(),'python_files':len(paths),'source_python_files':len(source),'enumeration_equal':paths==index,'parse_errors':errors,'density':summaries,'dict_counts':dict(counts),'duplicate_literal_pairs':dups,'repeated_nonliteral_expression_pairs':dynamic,'raw_receipt':raw_receipt}
save(OUT/'summary.json',summary)
print(json.dumps(summary,ensure_ascii=False,indent=2))
