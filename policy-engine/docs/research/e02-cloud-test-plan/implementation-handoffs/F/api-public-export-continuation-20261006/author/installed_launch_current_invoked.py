from pathlib import Path
import hashlib,importlib,json,platform,sys
import pytest
b=Path('/tmp/e02-F-continuation-20261006/api');kind=sys.argv[1]
site=Path(sys.prefix)/'lib/python3.14/site-packages';consumer=b/(kind+'-consumer-5484')
assert sys.flags.isolated==1
assert not any('/src' in p for p in sys.path),sys.path
# This test carrier contains the frozen fixture bytes; none of its parent
# conftests is loaded from the source checkout.
status=pytest.main(['-q','-o','addopts=','--import-mode=importlib','-p','no:cacheprovider','-k','not case_insensitive and not computed_import',str(consumer/'test_installed_facade_contract.py'),str(consumer/'test_facade_consumer_continuation.py')])
origins={name:str(Path(mod.__file__).resolve()) for name,mod in sys.modules.copy().items() if name.startswith(('polisyos','tools')) and getattr(mod,'__file__',None)}
violations={name:path for name,path in origins.items() if not Path(path).is_relative_to(site)}
assert not violations,violations
proof=dict(source_sha='5484db7a25014953bdab7cb2418df735f972ff93',source_tree='0406094722182749d3f7b9a64fa00c5337a9b391',executable=sys.executable,python=platform.python_version(),isolated=sys.flags.isolated,cwd=str(Path.cwd()),sys_path=sys.path,product_origins=origins,origin_violations=violations,exit_code=int(status),test_carriers=[dict(path=str(p),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in consumer.glob('test_*.py')],limitations=['Four census-source-only cases deliberately deselected from neutral installed consumer; complete immutable Git census and source class controls are separate checks.','Third-party dependencies reused via literal read-only site directory, editable .pth files not traversed.','Selected API source has no later worker/profile composition; no DoWhy/EconML/scientific or production authority claim.'])
(b/(kind+'-installed-current-proof.json')).write_text(json.dumps(proof,indent=2)+'\n');print(json.dumps(dict(installed_origins=len(origins),violations=violations,exit_code=int(status))))
raise SystemExit(status)
