"""Independent complete-reader bounded profile relocation and ancestry oracle."""
from dataclasses import asdict
import hashlib,json
import pytest
from tools.devx.architecture import guardrails as g

@pytest.mark.parametrize('profile',['pure_literal_import','passive_import_function','passive_parent_function'])
def test_complete_JSON_relocates_with_same_bounded_profile(tmp_path,monkeypatch,profile):
    observations=[]
    for label in ['first-root','second-longer-root']:
        root=tmp_path/label;src=root/'src';package=src/'polisyos/fixture';package.mkdir(parents=True)
        parent=src/'polisyos/__init__.py';parent.write_text('def latent():\n    return foreign.callback()\n' if profile=='passive_parent_function' else '')
        owner=package/'owner.py';owner.write_text('NAMES={"Beta":None,"Alpha":None}\n'+('def latent():\n    return foreign.callback()\n' if profile=='passive_import_function' else ''))
        facade=package/'__init__.py';facade.write_text('from .owner import NAMES\n__all__=sorted(NAMES)\n')
        monkeypatch.setattr(g,'REPO_ROOT',root);monkeypatch.setattr(g,'SRC_ROOT',src)
        p=g.PackagePolicy(module='polisyos.fixture',classification='public_experimental',facade_mode='eager_exports',owner='independent-review',readme=facade,reference_doc=facade,supported_entrypoints=('polisyos.fixture',),major_subsystem=False,notes='Closed relocatable literal-dependency profile')
        inv=g.build_public_surface_inventory([p]);body=g.render_public_surface_json(inv);entry=inv[0].entrypoints[0];violations=g._check_public_surface_contracts(inv)
        assert str(root) not in body
        for r in entry.export_resolution['inputs']:
            if r['operation']=='read_bytes' and r['status']=='read':
                b=(root/r['path']).read_bytes();assert r['bytes']==len(b) and r['sha256']==hashlib.sha256(b).hexdigest()
        if profile=='pure_literal_import':
            assert entry.exports==('Alpha','Beta') and entry.export_count==2 and not violations
        else:
            assert entry.export_count is None and entry.known_export_count==0 and entry.exports==()
            assert any(v.detail=='incomplete_exports' for v in violations)
        observations.append(body)
    assert observations[0]==observations[1]
    print(json.dumps({'case':profile,'complete_json_byte_equal':True,'full_inventory_json':json.loads(observations[0]),'same_canonical_gate_result':True},indent=2))
