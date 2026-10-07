"""Independent controlled-namespace falsifier for finite static export effects."""
from dataclasses import asdict
import ast
import json
from pathlib import Path

import pytest
from tools.devx.architecture import guardrails

CASES = {
    'implicit_descriptor_hook': '''
class Descriptor:
    def __set_name__(self, owner, name):
        M["RuntimeAdded"] = None
D = Descriptor()
M = {"StaticName": None}
class C:
    descriptor = D
__all__ = sorted(M)
''',
    'prebinding_builtin_rebind': '''
globals()["sorted"] = lambda values: ["RuntimeShadow"]
M = {"StaticName": None}
__all__ = sorted(M)
''',
    'multiline_selected_mapping_value_call': '''
def poison():
    globals()["sorted"] = lambda values: ["RuntimeShadow"]
    return None
M = {
    "StaticName": poison(),
}
__all__ = sorted(M)
''',
}


@pytest.mark.parametrize('name', CASES)
def test_unknown_executable_effect_cannot_admit_a_wrong_complete_namespace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str,
) -> None:
    source = CASES[name]
    package = tmp_path / 'src/polisyos/fixture'
    package.mkdir(parents=True)
    facade = package / '__init__.py'
    facade.write_text(source)
    monkeypatch.setattr(guardrails, 'SRC_ROOT', tmp_path / 'src')
    monkeypatch.setattr(guardrails, 'REPO_ROOT', tmp_path)
    # Runtime execution is solely of this wholly authored, closed fixture.
    # The product static reader does not execute any source or runtime import.
    namespace = {}
    exec(compile(source, str(facade), 'exec'), namespace)
    policy = guardrails.PackagePolicy(
        module='polisyos.fixture', classification='public_experimental',
        facade_mode='eager_exports', owner='independent-review', readme=facade,
        reference_doc=facade, supported_entrypoints=('polisyos.fixture',),
        major_subsystem=False, notes='Closed adversarial fixture',
    )
    inventory = guardrails.build_public_surface_inventory([policy])
    output = json.loads(guardrails.render_public_surface_json(inventory))['packages'][0]
    violations = guardrails._check_public_surface_contracts(inventory)
    record = {'case': name, 'source': source, 'controlled_runtime_all': namespace['__all__'],
              'actual_static_inventory': output,
              'actual_canonical_contract_violations': [asdict(v) for v in violations],
              'property': 'Unknown import-time effects must refuse a complete selected namespace when they change the invoked export builtin identity.'}
    print(json.dumps(record, indent=2))
    assert output['export_count'] is None, 'False complete namespace is emitted despite the controlled actual namespace differing'
    assert any(v.detail == 'incomplete_exports' for v in violations)


def test_supported_literal_same_real_caller_matches_controlled_runtime(tmp_path, monkeypatch):
    source='M = {"B": None, "A": None}\n__all__ = sorted(M)\n'
    package=tmp_path/'src/polisyos/fixture';package.mkdir(parents=True)
    facade=package/'__init__.py';facade.write_text(source)
    monkeypatch.setattr(guardrails,'SRC_ROOT',tmp_path/'src')
    monkeypatch.setattr(guardrails,'REPO_ROOT',tmp_path)
    namespace={};exec(compile(source,str(facade),'exec'),namespace)
    row=guardrails._entrypoint_inventory('polisyos.fixture')
    assert row.export_count==2 and row.export_resolution['complete']
    assert list(row.exports)==namespace['__all__']==['A','B']
