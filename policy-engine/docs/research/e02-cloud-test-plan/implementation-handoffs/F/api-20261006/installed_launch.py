import sys,os,json,importlib,platform,subprocess
from pathlib import Path
import pytest
os.environ['E02_CENSUS_SCRIPT']='/workspace/e02-F-api-20261006/policy-engine/docs/research/e02-cloud-test-plan/verification/F/api-20261006/census.py'
kind=sys.argv[1];scratch=Path('/workspace/e02-F-20261006-receipts/api');consumer=scratch/(kind+'-consumer')
site=Path(sys.prefix)/'lib/python3.14/site-packages'
assert not any('/src' in p for p in sys.path),sys.path
r=json.loads((scratch/'census-candidate.json').read_text());imported=[]
for row in r['literal_imports']:
    if row['kind']=='import': importlib.import_module(row['module'])
    else: exec('from '+row['module']+' import '+', '.join(row['names']),{})
    imported.append({'path':row['path'],'line':row['line'],'module':row['module'],'names':row['names']})
for row in r['dynamic_import_candidates']:
    if row['address']: importlib.import_module(row['address'])
args=['-o','addopts=','-q','-ra','-k','not repository_literal_facade_imports_resolve',*[str(p) for p in sorted(consumer.glob('test_*.py'))]]
status=pytest.main(args)
origins={name:mod.__file__ for name,mod in sys.modules.copy().items() if name.startswith('polisyos') and getattr(mod,'__file__',None)}
violations={name:path for name,path in origins.items() if not Path(path).is_relative_to(site)}
assert not violations,violations
proof={'python':platform.python_version(),'executable':sys.executable,'isolated_mode':sys.flags.isolated,'cwd':str(Path.cwd()),'sys_path':sys.path,'installed_site':str(site),'product_module_origins':origins,'source_sha':r['source_sha'],'literal_import_execution':imported,'literal_imports_executed':len(imported),'resolved_dynamic_imports_executed':sum(bool(row['address']) for row in r['dynamic_import_candidates']),'pytest_args':args,'exit':status,'limits':['One original repository-census testcase deselected because neutral installedconsumer has no Gitcheckout; separate complete census imports executed here.','Third-party dependencies reused readonly directly; no editable pth traversal.','FamilyICcertificate does not establish familystate operation.']}
(scratch/(kind+'-installed-proof.json')).write_text(json.dumps(proof,indent=2)+'\n')
print(json.dumps({'installed_product_modules':len(origins),'origin_violations':violations,'literal_imports_executed':len(imported),'source_sha':r['source_sha']}))
raise SystemExit(status)
