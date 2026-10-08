from __future__ import annotations

import importlib
import importlib.resources
import importlib.util
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.mark.parametrize('name',['polisyos.foundry.domain.schema','polisyos.foundry.domain.mechanisms','polisyos.data_forge.kernel.schemas.codegen'])
def test_retired_distribution_imports_are_absent(name):
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(name)
    try:
        spec=importlib.util.find_spec(name)
    except ModuleNotFoundError:
        spec=None
    assert spec is None


def test_installed_schema_alias_retains_identity():
    canonical=importlib.import_module('polisyos.data_forge.kernel.schemas')
    alias=importlib.import_module('polisyos.data_forge.kernel.pipeline.schemas')
    for name in ('CompatibilityMode','SchemaRegistry','SchemaVersion'):
        assert getattr(alias,name) is getattr(canonical,name)
    resources=importlib.resources.files('polisyos.data_forge.kernel.schemas')
    assert not (resources/'codegen.py').is_file()
    assert not (resources/'codegen').is_dir()


def test_installed_census_cli_preserves_ordinary_record_sentinel(tmp_path):
    def git(*args):
        return subprocess.run(['git',*args],cwd=tmp_path,capture_output=True,check=True).stdout
    git('init','--quiet');git('config','user.email','fixture@example.invalid');git('config','user.name','Fixture')
    names=('01 space.json','02\nпуть.json')
    for name in names:(tmp_path/name).write_text('{}\n')
    git('add','--all');git('commit','--quiet','-m','fixture base')
    for name in names:(tmp_path/name).write_text('{"new":true}\n')
    oracle={p.decode() for p in git('diff','--name-only','--no-renames','-z').split(b'\0') if p}
    import json
    completed=subprocess.run([sys.executable,'-I','-m','tools.quality.validation.schema_fqn_census','--repo-root',str(tmp_path)],capture_output=True,text=True,check=True)
    receipt=json.loads(completed.stdout)
    assert set(receipt['selection']['working_tree_changes'])==oracle==set(names)
    assert receipt['read_receipt']['complete_verdict'] is True
