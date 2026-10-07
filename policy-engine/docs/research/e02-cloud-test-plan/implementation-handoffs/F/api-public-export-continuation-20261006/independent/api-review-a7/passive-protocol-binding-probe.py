import json,pathlib,tempfile,subprocess,sys
from dataclasses import asdict
from tools.devx.architecture import guardrails
root=pathlib.Path(tempfile.mkdtemp(prefix='passive-protocol-',dir='/tmp/e02-F-continuation-20261006/api'))
src=root/'src';pkg=src/'polisyos/fixture';pkg.mkdir(parents=True);(src/'polisyos/__init__.py').write_text('')
(pkg/'owner.py').write_text('PASSIVE=1\n__getattr__=[]\n')
f=pkg/'__init__.py';f.write_text('from .owner import PASSIVE\nM={"StaticName":None}\n__all__=sorted(M)\n')
guardrails.SRC_ROOT=src;guardrails.REPO_ROOT=root
p=guardrails.PackagePolicy(module='polisyos.fixture',classification='public_experimental',facade_mode='eager_exports',owner='bounded-control',readme=f,reference_doc=f,supported_entrypoints=('polisyos.fixture',),major_subsystem=False,notes='closed passive protocol binding')
i=guardrails.build_public_surface_inventory([p]);row=i[0].entrypoints[0]
proc=subprocess.run([sys.executable,'-I','-c',f'import sys;sys.path.insert(0,{str(src)!r});import polisyos.fixture as f;print(f.__all__)'],capture_output=True,text=True,cwd=root)
print(json.dumps({'source_sha':'0c6c7efaab3eba502b44bf6471e7a3c675608f2a','owner_source':(pkg/'owner.py').read_text(),'facade_source':f.read_text(),'static':asdict(row),'violations':[asdict(v) for v in guardrails._check_public_surface_contracts(i)],'actual_import':{'argv':proc.args,'exit':proc.returncode,'stdout':proc.stdout,'stderr':proc.stderr}},indent=2,default=str))
assert row.export_count is None, 'module import-protocol binding accepted complete though actual import fails'
