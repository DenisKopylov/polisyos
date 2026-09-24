"""Stage-one owner census; tracked source paths independently checked against tree walk."""
import ast
import hashlib
import json
import os
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parents[5]
tracked = subprocess.check_output(['git', 'ls-files', 'src'], cwd=root, text=True).splitlines()
walked = [str(Path(base, name).relative_to(root)) for base, _, names in os.walk(root/'src') for name in names if name.endswith('.py')]
python_paths = {p for p in tracked if p.endswith('.py')}
assert python_paths == {p for p in walked if '__pycache__' not in p}
roots = ['runtime/quality', 'lex', 'scholar']
result = {'source_file_denominator': len(tracked), 'python_file_denominator': len(python_paths), 'independent_path_check': 'git ls-files = os.walk .py'}
terms = ['human_comprehension_established', 'MAEP', 'operator comprehension', 'behavioural_contract', 'behavioral_contract']
result['complete_tracked_src_search'] = {term: [p for p in tracked if term.casefold() in (root/p).read_text(errors='strict').casefold()] for term in terms}
result['owner_candidates'] = {}
for owner in roots:
    paths = sorted(p for p in python_paths if p.startswith(f'src/polisyos/{owner}/'))
    # Parse every member; malformed code must stop the result, never disappear as zero.
    definitions = [(p, n.name) for p in paths for n in ast.walk(ast.parse((root/p).read_text())) if isinstance(n, (ast.ClassDef, ast.FunctionDef))]
    result['owner_candidates'][owner] = {'python_denominator': len(paths), 'topical_definitions': [(p, name) for p, name in definitions if any(t in name.lower() for t in ['diagnostic','benchmark','authority','comprehension','multilingual'])]}
result['read_owner_identities'] = {p: hashlib.sha256((root/p).read_bytes()).hexdigest() for p in ['src/polisyos/runtime/quality/event_log.py','src/polisyos/runtime/quality/diagnostic_events.py','src/polisyos/lex/normpack/legal_authority.py','src/polisyos/lex/knowledge/benchmark.py','src/polisyos/scholar/README.md']}
print(json.dumps(result, indent=2))
