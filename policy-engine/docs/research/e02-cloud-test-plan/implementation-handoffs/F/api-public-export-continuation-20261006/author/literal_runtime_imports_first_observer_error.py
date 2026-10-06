from pathlib import Path
import importlib,json,sys
b=Path('/tmp/e02-F-continuation-20261006/api');kind=sys.argv[1]
x=json.loads((b/'census-final-complete.json').read_text());site=Path(sys.prefix)/'lib/python3.14/site-packages'
assert sys.flags.isolated==1 and not any('/src' in path for path in sys.path)
selected=[row for row in x['literal_imports'] if '/src/' in row['path']]
results=[]
for row in selected:
 module=importlib.import_module(row['module'])
 names={name:getattr(module,name) for name in row['names'] if name!='*'}
 results.append(dict(source_path=row['path'],source_line=row['line'],module=row['module'],names=list(names),scope='Actual binding readback, not execution of the source calling function'))
origins={name:str(Path(module.__file__).resolve()) for name,module in sys.modules.copy().items() if name.startswith('polisyos') and getattr(module,'__file__',None)}
assert all(Path(path).is_relative_to(site) for path in origins.values()),origins
print(json.dumps(dict(source_sha=x['source_sha'],selected_import_statements=len(selected),selected_source_files=len({row['path'] for row in selected}),rows=results,installed_origins=origins,unresolved='Computed imports, arbitrary plugins/configs and invocation of every caller remain unestablished; no inferred182/185client count.'),indent=2))
