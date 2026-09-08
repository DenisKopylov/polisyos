"""Complete source inventory for PA1 producer and current-reader boundaries."""
from __future__ import annotations
import ast
import io
import json
from pathlib import Path
import subprocess
import tokenize

root = Path.cwd()
tracked = set(subprocess.check_output(['git', 'ls-files', 'src/**/*.py'], text=True).splitlines())
walked = {str(path.relative_to(root)) for path in (root/'src').rglob('*.py')}
symbols = {'get_job', 'get_latest_job_by_run', 'get_latest_job_for_run', 'get_job_status', 'resolve_generation_value_choices', 'project_normative_run_disposition', 'project_generation_disposition', 'NormativeValueScheduleOwner', 'NormativeRunDisposition', 'NormativeGenerationDisposition', '_current_normative_job_record'}
by_ast = {name: set() for name in symbols}
by_token = {name: set() for name in symbols}
references, ambiguous = [], []
for path in sorted(tracked | walked):
    try:
        source = (root/path).read_text()
        tree = ast.parse(source, filename=path)
        for token in tokenize.generate_tokens(io.StringIO(source).readline):
            value = token.string if token.type == tokenize.NAME else None
            if token.type == tokenize.STRING:
                try: value = ast.literal_eval(token.string)
                except (SyntaxError, ValueError): pass
            if isinstance(value, str) and value in symbols: by_token[value].add(path)
        parents = {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}
        for node in ast.walk(tree):
            value = None
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef, ast.alias)): value = node.name
            elif isinstance(node, ast.Name): value = node.id
            elif isinstance(node, ast.Attribute): value = node.attr
            elif isinstance(node, ast.Constant): value = node.value
            elif isinstance(node, (ast.arg, ast.keyword)): value = node.arg
            if isinstance(value, str) and value in symbols:
                by_ast[value].add(path)
                owner = node
                scope = []
                while owner in parents:
                    owner = parents[owner]
                    if isinstance(owner, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)): scope.append(owner.name)
                references.append({'path':path,'line':node.lineno,'symbol':value,'syntax':type(node).__name__,'scope':'.'.join(reversed(scope))})
    except (OSError, SyntaxError, UnicodeError, tokenize.TokenError) as exc:
        ambiguous.append({'path':path,'error':str(exc)})
differences = {key:{'ast_only':sorted(by_ast[key]-by_token[key]),'token_only':sorted(by_token[key]-by_ast[key])} for key in sorted(symbols)}
print(json.dumps({'denominator':'ALL src/**/*.py; git-index identities independently reconciled to filesystem; syntax AST independently reconciled to token stream including exact getattr strings','tracked_count':len(tracked),'walked_count':len(walked),'tracked_only':sorted(tracked-walked),'walked_only':sorted(walked-tracked),'complete_source_identities':sorted(tracked|walked),'ambiguous':ambiguous,'independent_identity_differences':differences,'symbol_file_sets':{key:sorted(values) for key,values in sorted(by_ast.items())},'references':references},indent=2))
assert tracked == walked and not ambiguous
assert all(not item['ast_only'] and not item['token_only'] for item in differences.values())
