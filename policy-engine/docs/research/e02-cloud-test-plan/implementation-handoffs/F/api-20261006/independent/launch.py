import hashlib
import importlib
import json
import os
from pathlib import Path
import sys

import pytest

ROOT=Path('/workspace/e02-F-20261006-receipts/economics/api-review')
kind=sys.argv[1]
site=Path(sys.prefix)/'lib/python3.14/site-packages'
os.environ['E02_CENSUS_SCRIPT']=str(ROOT/'census.py')
assert sys.flags.isolated == 1
assert not any(p.endswith('/src') for p in sys.path),sys.path
status=pytest.main([str(ROOT/'test_installed_facade_contract.py'),'-o','addopts=','-o','cache_dir='+str(ROOT/(kind+'-cache')),'--basetemp='+str(ROOT/(kind+'-tmp')),'-v','--tb=short'])
origins={n:m.__file__ for n,m in sys.modules.copy().items() if n.startswith('polisyos') and getattr(m,'__file__',None)}
wrong={n:p for n,p in origins.items() if not Path(p).is_relative_to(site)}
assert not wrong,wrong
record={'kind':kind,'python_executable':sys.executable,'isolated':sys.flags.isolated,'cwd':str(Path.cwd()),'sys_path':sys.path,'installed_site':str(site),'loaded_product_modules':len(origins),'origin_violations':wrong,'pytest_exit':status,'test_sha256':hashlib.sha256((ROOT/'test_installed_facade_contract.py').read_bytes()).hexdigest(),'census_script_sha256':hashlib.sha256((ROOT/'census.py').read_bytes()).hexdigest(),'source_sha':'729d137279b7d6334230045e420255762fe55f08'}
(ROOT/(kind+'-proof.json')).write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record))
raise SystemExit(status)
