"""Canonical selected collectors/generator on exact Git-backed source overlays."""
from __future__ import annotations
import ast
import contextlib
import hashlib
import importlib.util
import io
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path('/workspace/e02-E-continuation-20261006')
BASE = '5e3e3727685132f270a3a07b9f63dd962a88cd96'
OUT = Path(__file__).parent
POST = OUT / 'postimage'
PRODUCT = ROOT / 'policy-engine'
sys.path.insert(0, str(PRODUCT))

def original(path: str) -> bytes:
    return subprocess.check_output(['git', '-C', str(ROOT), 'show', BASE+':'+path])

def load_module(name, relative):
    actual=ROOT/relative
    assert actual.read_bytes()==original(relative)
    spec=importlib.util.spec_from_file_location(name,actual)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
    return module

guard_path='policy-engine/tools/devx/architecture/guardrails.py'
guard=load_module('e02_covariance_native_guard',guard_path)
lint_path='policy-engine/tools/quality/lint/lint_imports.py'
lint=load_module('e02_facade_native_import_policy',lint_path)
contract='policy-engine/architecture/public_surface/contract.toml'
assert (ROOT/contract).read_bytes()==original(contract)
policies=guard._parse_public_surface(ROOT/contract)
generated=guard._parse_public_generated_artifact_families(ROOT/contract)
paths={
 'polisyos.foundry.uncertainty':'policy-engine/src/polisyos/foundry/uncertainty/__init__.py',
 'polisyos.scientist.nodes.builtins.simulate.propagate_welfare':'policy-engine/src/polisyos/scientist/nodes/builtins/simulate/propagate_welfare.py',
 'polisyos.calibration':'policy-engine/src/polisyos/calibration/__init__.py',
 'polisyos.scientist.nodes.builtins.simulate.propagate_uncertainty':'policy-engine/src/polisyos/scientist/nodes/builtins/simulate/propagate_uncertainty.py',
}
proposed={ROOT/path:(POST/path).read_text() for path in paths.values()}
original_read=Path.read_text

def source_reader(values):
 def read(path,*args,**kwargs):
  if path in values:return values[path]
  if path.is_relative_to(ROOT/'policy-engine/src'):
   baseline=original(str(path.relative_to(ROOT)));assert path.read_bytes()==baseline;return baseline.decode()
  return original_read(path,*args,**kwargs)
 return read

def collect(values):
 with patch.object(Path,'read_text',source_reader(values)),patch.object(guard,'_iter_py_files',lambda:[ROOT/path for path in paths.values()]):
  return guard.collect_deep_import_edges(policies)

old_edges=collect({});new_edges=collect(proposed)
fake=dict(proposed);welfare_path=paths['polisyos.scientist.nodes.builtins.simulate.propagate_welfare'];fake[ROOT/welfare_path]=original(welfare_path).decode()
fake_edges=collect(fake)
target='polisyos.scientist.nodes.builtins.simulate.propagate_welfare->polisyos.foundry.uncertainty.covariance'
old_keys={edge.key for edge in old_edges};new_keys={edge.key for edge in new_edges};fake_keys={edge.key for edge in fake_edges}
assert target in old_keys and target not in new_keys and target in fake_keys
assert old_keys-new_keys=={target} and not new_keys-old_keys

# Execute the actual canonical lint_imports main, not a recreated allow-list predicate.
# Bound the file iterator only; source overlays feed its real AST visitor and rule loop.
# Turn parse cache off to prevent original-file hash/cache reuse for changed in-memory bytes.
parse_native=lint.parse_imports
policy_path='policy-engine/architecture/imports/policy.toml';exceptions_path='policy-engine/architecture/imports/exceptions.toml'
for relative in (policy_path,exceptions_path,'policy-engine/architecture/packages/boundaries.toml'):
 assert (ROOT/relative).read_bytes()==original(relative)

def policy_check(values,label):
 sink=io.StringIO()
 argv=['--policy',str(ROOT/policy_path),'--exceptions',str(ROOT/exceptions_path),'--output-format','json','--cache-dir',str(OUT/('import-policy-'+label+'-cache'))]
 with patch.object(Path,'read_text',source_reader(values)),patch.object(lint,'iter_py_files',lambda src_root:[ROOT/path for path in paths.values()]),patch.object(lint,'parse_imports',lambda config,cache_root=None:parse_native(config,cache_root=None)),contextlib.redirect_stdout(sink):
  code=lint.main(argv)
 stdout=sink.getvalue();(OUT/('import-policy-'+label+'.json')).write_text(stdout)
 return {'argv':argv,'exit_code':code,'result':json.loads(stdout)}
old_policy=policy_check({},'old5e');new_policy=policy_check(proposed,'postimage')
alias_fake=dict(proposed);cal_path=paths['polisyos.calibration'];alias_fake[ROOT/cal_path]=original(cal_path).decode().replace('    "load_foundry_calibration_report",\n','')
fake_policy=policy_check(alias_fake,'present-old-alias')
assert old_policy['exit_code']==1 and new_policy['exit_code']==0 and fake_policy['exit_code']==1
assert '[ARCH001] forbidden internal import: calibration -> foundry' in json.dumps(old_policy['result'])
assert '[ARCH001] forbidden internal import: calibration -> foundry' in json.dumps(fake_policy['result'])
assert '[ARCH001]' not in json.dumps(new_policy['result'])

before=guard.build_public_surface_inventory(policies)
before_json=guard.render_public_surface_json(before,generated_artifact_families=generated);before_md=guard.render_public_surface_markdown(before)
assert before_json.encode()==original('policy-engine/architecture/public_surface/inventory.json')
assert before_md.encode()==original('policy-engine/docs/reference/public-surface.md')
with patch.object(Path,'read_text',source_reader(proposed)):
 after=guard.build_public_surface_inventory(policies);after_json=guard.render_public_surface_json(after,generated_artifact_families=generated);after_md=guard.render_public_surface_markdown(after)
def exports(items,module):
 return next(entry for package in items for entry in package.entrypoints if entry.module==module)
for items,counts in ((before,{'polisyos.calibration':29,'polisyos.foundry.uncertainty':20,'polisyos.ddm':17}),(after,{'polisyos.calibration':28,'polisyos.foundry.uncertainty':25,'polisyos.ddm':17})):
 for module,count in counts.items():assert exports(items,module).export_count==count
assert exports(after,'polisyos.foundry.uncertainty').has___getattr__
before_parsed=json.loads(before_json);after_parsed=json.loads(after_json)
expected=json.loads(before_json)
for package in expected['packages']:
 actual_pkg=next(item for item in after_parsed['packages'] if item['module']==package['module'])
 if package['module']=='polisyos.calibration':
  package['export_count']=actual_pkg['export_count'];package['exports']=actual_pkg['exports']
 for entry in package['entrypoints']:
  if entry['module'] in ('polisyos.calibration','polisyos.foundry.uncertainty'):
   actual=next(entry2 for package2 in after_parsed['packages'] for entry2 in package2['entrypoints'] if entry2['module']==entry['module']);entry.update(actual)
assert expected==after_parsed
for relative,content in (('policy-engine/architecture/public_surface/inventory.json',after_json),('policy-engine/docs/reference/public-surface.md',after_md)):
 destination=POST/relative;destination.parent.mkdir(parents=True,exist_ok=True);destination.write_text(content)
def body(tree):return [ast.dump(node,include_attributes=False) for node in tree.body if not isinstance(node,(ast.Import,ast.ImportFrom))]
for module in ('polisyos.scientist.nodes.builtins.simulate.propagate_welfare','polisyos.scientist.nodes.builtins.simulate.propagate_uncertainty'):
 path=paths[module];assert body(ast.parse(original(path)))==body(ast.parse(proposed[ROOT/path]))
cov_path='policy-engine/src/polisyos/foundry/uncertainty/covariance.py';assert (ROOT/cov_path).read_bytes()==original(cov_path)
result={
 'schema':'policyos.e02.owned_facade_route_collectors_generator.v1','base':BASE,'base_tree':'3b63e778d5b6d17b2e9edc3b4bf91af079b32eb0',
 'actual_deep_collector':'guardrails.collect_deep_import_edges(_parse_public_surface(contract))','collector_source_sha256':hashlib.sha256(original(guard_path)).hexdigest(),
 'actual_import_policy_scanner':'tools.quality.lint.lint_imports.main with selected four-file iterator and parse cache disabled; actual source AST + policy/exceptions/packages unchanged',
 'import_policy_scanner_sha256':hashlib.sha256(original(lint_path)).hexdigest(),'import_policy_checks':{'old5e':old_policy,'postimage':new_policy,'present_old_alias_negative':fake_policy},
 'selected_full_source_denominator':paths,'selected_old_deep_edges':[edge.key for edge in old_edges],'selected_new_deep_edges':[edge.key for edge in new_edges],
 'removed_owned_covariance_edge':target,'new_cross_root_private_edges':sorted(new_keys-old_keys),
 'exports_present_old_route_negative':{'exports':25,'owned_covariance_edge_retained':target in fake_keys,'outcome':'EXPECTED_FAIL_actual_collector'},
 'alias_name_removed_old_import_negative':{'Cal___all___export_count':28,'alias_runtime_import_retained':True,'outcome':'EXPECTED_FAIL_actual_ARCH001'},
 'canonical_generator':'build_public_surface_inventory + render_public_surface_json/markdown; all base facade source reads bound to exact5e','baseline_generated_bytes_exact':True,
 'postimage_counts':{'Calibration':28,'Foundry uncertainty':25,'DDM':17},'only_owned_facade_JSON_values_changed':True,
 'Welfare_non_import_AST_unchanged':True,'PropagateUncertainty_non_import_AST_unchanged':True,
 'covariance_body_bytes_unchanged':{'path':cov_path,'sha256':hashlib.sha256(original(cov_path)).hexdigest()},
 'private_covariance_import_introducing_commit':'28ea3bb56bc4e751bf1303615d79219b56d7a24c',
 'P41':'Actual original full5e guard FAIL retained separately. Exact selected canonical collectors reproduce two owned violations. No old full-guard rerun/disjointness or global architecture PASS claimed.',
 'remaining_owner_boundaries':'Full selected deep-edge remainder listed; Core/IR/API admission and nine foreign packets stay separate. No policy/baseline/exception/shared-contract change.',
}
(OUT/'collector-generator.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({key:result[key] for key in ('base','removed_owned_covariance_edge','new_cross_root_private_edges','postimage_counts','baseline_generated_bytes_exact','only_owned_facade_JSON_values_changed','Welfare_non_import_AST_unchanged','PropagateUncertainty_non_import_AST_unchanged','exports_present_old_route_negative','alias_name_removed_old_import_negative')},indent=2))
