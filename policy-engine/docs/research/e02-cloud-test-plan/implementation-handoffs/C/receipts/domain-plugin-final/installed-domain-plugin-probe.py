from __future__ import annotations
import hashlib
import importlib
import importlib.metadata as metadata
import json
import sys
import tarfile
import zipfile
from pathlib import Path
from packaging.markers import default_environment
from packaging.requirements import Requirement
from packaging.version import Version

RAW=Path('/Users/deniskopylov/.codex/worktrees/e02-c-continuation-20261006/polisyos/.tmp/e02-C2/raw/installed/plg-a452').resolve()
ROOT=Path('/Users/deniskopylov/.codex/worktrees/e02-c-plugins-20261006/polisyos').resolve()
WHEEL=RAW/'dist/policy_engine-0.1.0-py3-none-any.whl'
ARCHIVE=RAW/'candidate.tar'
def require(ok:bool,msg:str)->None:
    if not ok: raise AssertionError(msg)
def sha(data:bytes)->str: return hashlib.sha256(data).hexdigest()

dist=metadata.distribution('policy-engine')
site=Path(dist.locate_file('')).resolve()
require(Path.cwd().resolve()==Path('/tmp').resolve(),f'wrong CWD: {Path.cwd()}')
require(not any(str(ROOT) in x for x in sys.path), 'candidate source checkout visible on sys.path')
# Check the actual installed distribution's base requirement closure in this fresh no-extra env.
base=[]; missing=[]
env=default_environment(); env['extra']=''
for raw in dist.requires or []:
    req=Requirement(raw)
    if req.marker is not None and not req.marker.evaluate(env):
        continue
    base.append(raw)
    try:
        actual=Version(metadata.version(req.name))
    except metadata.PackageNotFoundError:
        missing.append({'requirement':raw,'reason':'distribution absent'})
        continue
    if req.specifier and not req.specifier.contains(actual,prereleases=True):
        missing.append({'requirement':raw,'installed':str(actual),'reason':'specifier mismatch'})
require(not missing,f'base dependency closure not satisfied: {missing}')
require(len(base)==34,f'expected 34 active base requirements, observed {len(base)}')
for absent in ('pytest','hnswlib','sentence-transformers','torch','transformers'):
    try: metadata.version(absent)
    except metadata.PackageNotFoundError: pass
    else: raise AssertionError(f'optional/test package unexpectedly present: {absent}')

critical_modules={
 'polisyos.foundry.plugins':'src/polisyos/foundry/plugins/__init__.py',
 'polisyos.foundry.plugins.cli':'src/polisyos/foundry/plugins/cli.py',
 'polisyos.foundry.plugins.core':'src/polisyos/foundry/plugins/core.py',
 'polisyos.foundry.plugins.discovery':'src/polisyos/foundry/plugins/discovery.py',
 'polisyos.foundry.plugins.api':'src/polisyos/foundry/plugins/api.py',
 'polisyos.foundry.plugins.training_adapter':'src/polisyos/foundry/plugins/training_adapter.py',
 'polisyos.foundry.plugins.economics':'src/polisyos/foundry/plugins/economics/__init__.py',
 'polisyos.foundry.plugins.economics.plugin':'src/polisyos/foundry/plugins/economics/plugin.py',
 'polisyos.core.discovery':'src/polisyos/core/discovery/__init__.py',
 'polisyos.core.discovery.base':'src/polisyos/core/discovery/base.py',
}
origin_rows=[]
with zipfile.ZipFile(WHEEL) as wheel, tarfile.open(ARCHIVE,'r:') as archive:
    wheel_names=set(wheel.namelist()); archive_names=set(archive.getnames())
    for module_name,source_path in critical_modules.items():
        module=importlib.import_module(module_name)
        origin=Path(module.__file__).resolve()
        require(origin.is_relative_to(site),f'{module_name} origin outside site-packages: {origin}')
        wheel_member=source_path.removeprefix('src/')
        archive_member=f'source/policy-engine/{source_path}'
        require(wheel_member in wheel_names,f'{wheel_member} absent from wheel')
        require(archive_member in archive_names,f'{archive_member} absent from frozen source archive')
        installed_bytes=origin.read_bytes(); source_bytes=archive.extractfile(archive_member).read()
        require(installed_bytes==wheel.read(wheel_member)==source_bytes,f'{module_name} bytes drifted')
        origin_rows.append({'module':module_name,'origin':str(origin),'sha256':sha(installed_bytes),'wheel_member':wheel_member,'archive_member':archive_member,'byte_identical_to_wheel_and_frozen_source':True})

entry_points=metadata.entry_points().select(group='polisyos.plugins')
ep_names=sorted(ep.name for ep in entry_points)
require('c2-installed-fixture' in ep_names and 'c2-invalid' in ep_names,f'fixture entry points not enumerated: {ep_names}')
from polisyos.foundry.plugins.core import DomainConfig, PluginRegistry
from polisyos.foundry.plugins.discovery import auto_register_plugins, discover_plugins
found=discover_plugins()
found_names=sorted(plugin.metadata.name for plugin in found)
require(found_names==['c2-installed-fixture','economics'],f'discovery result mismatch: {found_names}')
registry=PluginRegistry(); registry.clear()
registered=auto_register_plugins(registry)
registered_names=sorted(meta.name for meta in registry.list_plugins())
require(registered_names==['c2-installed-fixture','economics'],f'registry result mismatch: {registered_names}')
require('c2-invalid' not in registered and 'c2-invalid' not in registered_names,'invalid entry point was admitted')
fixture=registry.get('c2-installed-fixture')
fixture_state=fixture.create_initial_state(DomainConfig(n_agents=7,max_agents=7),None)
require(fixture_state=={'agents':7,'fixture':True},f'installed DomainPlugin consumer result differs: {fixture_state}')
economics=registry.get('economics')
require(economics.metadata.name=='economics','built-in Economics DomainPlugin not registered')

cli_stdout=(RAW/'installed-cli.stdout').read_bytes(); cli_stderr=(RAW/'installed-cli.stderr').read_bytes(); cli_exit=(RAW/'installed-cli.exit').read_text().strip()
require(cli_exit=='0','installed public console entrypoint failed')
require(b'Available Plugins (2)' in cli_stdout and b'economics (v1.0.0)' in cli_stdout and b'c2-installed-fixture (v1.0)' in cli_stdout,'installed public list command omitted discovered plugin')
require(b'c2-invalid' not in cli_stdout and b'plugin candidate class must inherit DomainPlugin' in cli_stderr,'installed public list command did not reject malformed candidate')
result={'cwd':str(Path.cwd()),'python':sys.executable,'distribution':{'name':dist.metadata['Name'],'version':dist.version,'site_packages':str(site)},'candidate_checkout_on_sys_path':False,'dependency_profile':{'source':'frozen baseline pyproject+uv.lock unchanged from base commit','active_base_requirement_count':len(base),'base_missing_or_mismatch':missing,'selected_extras':[],'pytest_present':False,'optional_hnswlib_present':False,'installed_distribution_count':len(list(metadata.distributions()))},'installed_module_origins_and_source_identity':origin_rows,'entry_point_group':'polisyos.plugins','entry_points_enumerated':ep_names,'discovered_domain_plugins':found_names,'registered_domain_plugins':registered_names,'fixture_consumer_result':fixture_state,'builtin_economics_registered':True,'malformed_plugin_admitted':False,'registry_status_semantics':'availability only; no verification/admission authority claimed','public_cli':{'command':'<venv>/bin/python -I <venv>/bin/polisy list --verbose','exit_code':int(cli_exit),'stdout_sha256':sha(cli_stdout),'stderr_sha256':sha(cli_stderr),'malformed_entrypoint_rejected':True},'training_execution':'not run; no CPU training or model/optimizer claim'}
print(json.dumps(result,sort_keys=True))
