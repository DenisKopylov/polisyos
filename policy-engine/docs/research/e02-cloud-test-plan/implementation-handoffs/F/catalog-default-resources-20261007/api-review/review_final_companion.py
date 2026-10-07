"""Bind doc-only metadata successor; run maintained compatibility predicate."""
import dataclasses,hashlib,json,os,pathlib,subprocess,time,tomllib
from tools.ops_runners.release.build_release_notes import structured_compatibility_changes,render_release_notes
from tools.ops_runners.release.check_compatibility_release_gates import _validate_fragments
OUT=pathlib.Path(__file__).resolve().parent;ROOT=pathlib.Path('/workspace/e02-F-graph-20261006');PRODUCT=ROOT/'policy-engine';CODE='08983d96395fdde81ffa9e88d0150fd12c13fe2e';SHA='81f482e04bd8a2c85f894d425847c6e8657b6ea6';TREE='120103b1a375b5d405632936b2934f2b36a320f7'
def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT)
assert git('rev-parse','HEAD').decode().strip()==SHA and git('rev-parse','HEAD^{tree}').decode().strip()==TREE
assert not git('status','--porcelain','--untracked-files=no');changed=git('diff','--name-only',CODE,SHA).decode().splitlines();assert changed==['policy-engine/docs/reference/data-forge/catalog-default-resources.md','policy-engine/release-fragments/unreleased/2026-10-07-catalog-default-resources.toml','policy-engine/src/polisyos/data_forge/domains/README.md']
inspection=json.loads((OUT/'inspection.json').read_text());unchanged=[];docrefs=[]
for item in inspection['source_begin']+inspection['original_YAML_refs']:
 p=item.get('path');b=git('show',SHA+':'+p);assert (ROOT/p).read_bytes()==b
 if p not in changed:assert hashlib.sha256(b).hexdigest()==item['sha256'];unchanged.append({'path':p,'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()})
for p in changed:
 b=git('show',SHA+':'+p);docrefs.append({'path':p,'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()})
assert len(unchanged)==15
(OUT/'final-companion-diff.patch').write_bytes(git('diff',CODE,SHA))
path=PRODUCT/'release-fragments/unreleased/2026-10-07-catalog-default-resources.toml';fragment=tomllib.loads(path.read_text());fragment['__path__']=str(path);policy=tomllib.loads((PRODUCT/'architecture/gates/compatibility_release.toml').read_text());errors,findings=_validate_fragments(PRODUCT,policy,[fragment],breaking_classes=());changes=structured_compatibility_changes([fragment]);print(render_release_notes('e02-catalog-resources',[fragment],'2026-10-07'))
assert not errors and not findings and len(changes)==1 and changes[0]['impact']=='compatible' and changes[0]['change_class']=='python-public-api';assert fragment['public_surface_inventory_reviewed'] is True
assert 'public_experimental' in changes[0]['surface'] and 'polisyos.data_forge.read_api.catalog.catalog_default_resource_path' in changes[0]['surface']
for p in [changed[0],changed[2]]:
 text=(ROOT/p).read_text();assert 'public_experimental' in text and 'catalog_default_resource_path' in text and 'Path' in text and 'ValueError' in text and 'internal' in text
result={'source_sha':SHA,'tree':TREE,'runtime_proof_sha':CODE,'check':'PASS','changed_companion_refs':docrefs,'unchanged_runtime_test_Hatch_YAML_input_count':len(unchanged),'unchanged_inputs':unchanged,'canonical_one_fragment_errors':[dataclasses.asdict(e) for e in errors],'canonical_one_fragment_findings':[dataclasses.asdict(f) for f in findings],'classification':changes[0]['change_class'],'impact':changes[0]['impact'],'public_surface_inventory_reviewed':'Actual089 renderer/ABI inspection; not a completeness or whole gate verdict.','source_limit':'Only3doc/README/fragment bodies changed; no new runtime/test rerun. Prior08941+79 immutable checks remain source-specific carried by exact15input equality.'}
(OUT/'final-companion.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2));assert git('rev-parse','HEAD').decode().strip()==SHA
