"""Independent finite import-owner/header/default profile containment consumers."""
import hashlib,json,os,pathlib,subprocess,sys
from dataclasses import asdict
import pytest
from tools.devx.architecture import guardrails

@pytest.mark.parametrize('name', ['default_callback','default_attribute','annotation_attribute','type_parameter_header'])
def test_headers_are_not_passive_without_supported_expression(tmp_path,monkeypatch,name):
    source={
        'default_callback':'def p(v=foreign_callback()): pass\n',
        'default_attribute':'def p(v=foreign.attr): pass\n',
        'annotation_attribute':'def p(v: foreign.attr): pass\n',
        'type_parameter_header':'def p[T: foreign.attr](): pass\n',
    }[name]+'M={"StaticName":None}\n__all__=sorted(M)\n'
    with pytest.raises(guardrails._UnresolvedExportDeclarationError):guardrails._extract_exports(__import__('ast').parse(source))
    print(json.dumps({'case':name,'actual_type':'_UnresolvedExportDeclarationError','source':source}))

@pytest.mark.parametrize('name', ['missing_builtin_name','defined_passive_name','no_hook_positive'])
def test_real_local_import_owner_protocol_cannot_grant_false_complete(tmp_path,monkeypatch,name):
    root=tmp_path/'src';package=root/'polisyos/fixture';package.mkdir(parents=True)
    hook='def __getattr__(name):\n    import builtins\n    builtins.sorted = lambda values: ["RuntimeShadow"]\n    return None\n'
    owner=('PASSIVE=1\n'+hook if name=='defined_passive_name' else hook if name=='missing_builtin_name' else 'PASSIVE=1\n')
    imported='len' if name=='missing_builtin_name' else 'PASSIVE'
    source=f'from .owner import {imported}\nM={{"StaticName":None}}\n__all__=sorted(M)\n'
    (package/'owner.py').write_text(owner);facade=package/'__init__.py';facade.write_text(source)
    monkeypatch.setattr(guardrails,'SRC_ROOT',root);monkeypatch.setattr(guardrails,'REPO_ROOT',tmp_path)
    policy=guardrails.PackagePolicy(module='polisyos.fixture',classification='public_experimental',facade_mode='eager_exports',owner='independent-review',readme=facade,reference_doc=facade,supported_entrypoints=('polisyos.fixture',),major_subsystem=False,notes='Closed exact local source import fixture')
    inventory=guardrails.build_public_surface_inventory([policy]);row=inventory[0].entrypoints[0];violations=guardrails._check_public_surface_contracts(inventory)
    # Genuine CPython import of these fully authored closed files in a fresh child.
    # No global builtins mutation escapes this child; reader itself never imports fixture.
    code=f'import sys,json;sys.path.insert(0,{str(root)!r});import polisyos.fixture as f;print(json.dumps(f.__all__))'
    proc=subprocess.run([sys.executable,'-I','-c',code],cwd=tmp_path,capture_output=True,text=True)
    assert proc.returncode==0,proc.stderr
    actual=json.loads(proc.stdout)
    record={'case':name,'source':source,'owner_source':owner,'controlled_actual_CPython_import_all':actual,'child_argv':proc.args,'child_stdout':proc.stdout,'child_stderr':proc.stderr,'static_exports':list(row.exports),'export_count':row.export_count,'known_export_count':row.known_export_count,'complete':row.export_resolution['complete'],'resolution':row.export_resolution,'canonical_violations':[asdict(v) for v in violations]}
    print(json.dumps(record,indent=2))
    if name=='no_hook_positive':
        assert actual==['StaticName'] and row.exports==('StaticName',) and row.export_count==1 and not violations
    else:
        assert actual==['RuntimeShadow']
        assert row.export_count is None,'import protocol executed body while pure static owner accepted complete WRONG namespace'
        assert any(v.detail=='incomplete_exports' for v in violations)
