"""Actual closed-file import oracle for the declared passive dunder boundary."""
from dataclasses import asdict
import hashlib
import json
import subprocess
import sys

import pytest
from tools.devx.architecture import guardrails as g

CASES = [
    ('assign', 'PASSIVE=1\n__getattr__=[]\n', False, '', True),
    ('annotated', 'PASSIVE=1\n__getattr__: list=[]\n', False, '', True),
    ('import_alias', 'PASSIVE=1\nfrom .values import BAD as __getattr__\n', False, '', True),
    ('owner_initializer', 'PASSIVE=1\n__getattr__=[]\n', True, '', True),
    ('parent_initializer', 'PASSIVE=1\n', False, '__loader__=[]\n', False),
    ('declarative_all_positive', 'PASSIVE=1\n__all__=["PASSIVE"]\n', False, '__all__=[]\n', False),
]

@pytest.mark.parametrize('name,owner,package_owner,parent,import_fails', CASES)
def test_actual_protocol_import_and_static_profile(tmp_path, monkeypatch, name, owner, package_owner, parent, import_fails):
    source_root=tmp_path/'src'
    package=source_root/'polisyos'/'fixture'
    package.mkdir(parents=True)
    (source_root/'polisyos'/'__init__.py').write_text(parent)
    (package/'values.py').write_text('BAD=[]\n')
    if package_owner:
        (package/'owner').mkdir()
        owner_path=package/'owner'/'__init__.py'
    else:
        owner_path=package/'owner.py'
    owner_path.write_text(owner)
    facade=package/'__init__.py'
    facade.write_text('from .owner import PASSIVE\nM={"StaticName":None}\n__all__=sorted(M)\n')
    monkeypatch.setattr(g,'SRC_ROOT',source_root)
    monkeypatch.setattr(g,'REPO_ROOT',tmp_path)
    policy=g.PackagePolicy(module='polisyos.fixture', classification='public_experimental', facade_mode='eager_exports', owner='independent-review', readme=facade, reference_doc=facade, supported_entrypoints=('polisyos.fixture',), major_subsystem=False, notes='Complete closed source protocol fixture')
    inventory=g.build_public_surface_inventory([policy])
    row=inventory[0].entrypoints[0]
    violations=g._check_public_surface_contracts(inventory)
    script='import sys,json;sys.path.insert(0,sys.argv[1]);import polisyos.fixture as f;print(json.dumps(f.__all__))'
    process=subprocess.run([sys.executable,'-I','-c',script,str(source_root)],cwd=tmp_path,capture_output=True,text=True)
    for item in row.export_resolution['inputs']:
        if item['operation']=='read_bytes' and item['status']=='read':
            body=(tmp_path/item['path']).read_bytes()
            assert len(body)==item['bytes'] and hashlib.sha256(body).hexdigest()==item['sha256']
    print(json.dumps({'case':name, 'owner_source':owner, 'parent_source':parent, 'facade_source':facade.read_text(), 'actual_CPython':{'argv':process.args,'returncode':process.returncode,'stdout':process.stdout,'stderr':process.stderr}, 'static':asdict(row), 'canonical_violations':[asdict(item) for item in violations]},indent=2))
    if import_fails:
        assert process.returncode==1 and "TypeError: 'list' object is not callable" in process.stderr
    else:
        assert process.returncode==0 and json.loads(process.stdout)==['StaticName']
    if name=='declarative_all_positive':
        assert row.export_count==row.known_export_count==1 and row.exports==('StaticName',)
        assert row.export_resolution['complete'] and not violations
    else:
        assert row.export_count is None and row.known_export_count==0 and row.exports==()
        assert not row.export_resolution['complete']
        assert any(item.detail=='incomplete_exports' for item in violations)

