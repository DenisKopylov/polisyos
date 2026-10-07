"""Build owner-only review patches from exact Git blobs; never mutate checkout."""
from pathlib import Path
import ast, difflib, hashlib, json, subprocess
ROOT=Path('/workspace/e02-E-continuation-20261006'); OUT=Path(__file__).parent
CURRENT='31059ec77f9add8651667967a4b1a51acfab6d24'; FRC='8486baad6fdef8063cfaad80b15f6b6d8532460a'
FIXTURE=OUT/'fixture-current'; PATCHES=OUT/'patches'; PATCHES.mkdir(exist_ok=True)
def blob(ref,path):return subprocess.check_output(['git','show',ref+':'+path],cwd=ROOT)
def patch(name,changes):
    result=''
    for path,new in changes.items():
        old=blob(CURRENT,path).decode(); result+=''.join(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile='a/'+path,tofile='b/'+path))
    p=PATCHES/name;p.write_text(result);return p
contract='policy-engine/architecture/public_surface/contract.toml'
old=blob(CURRENT,contract).decode()
section=old[old.index('module = "polisyos.core"'):old.index('module = "polisyos.ir"')]
newsection=section.replace('  "polisyos.core.contracts",','  "polisyos.core.contracts",\n  "polisyos.core.artifacts",\n  "polisyos.core.canon",\n  "polisyos.core.registry",')
assert newsection!=section
patch('core-option-a-existing-entrypoints.patch',{contract:old.replace(section,newsection)})
core='policy-engine/src/polisyos/core/__init__.py'; text=blob(CURRENT,core).decode()
exports={n:('polisyos.core.artifacts',n) for n in ('ArtifactRef','ArtifactStore','ArtifactWriteOptions','PutOptions','SchemaInfo','input_ref_from_artifact_ref')}
exports.update({n:('polisyos.core.canon',n) for n in ('CanonSpec','from_canonical_bytes')});exports['load_registry_bundle_content']=('polisyos.core.registry','load_registry_bundle_content')
new=text.replace('_LAZY_EXPORTS = {','_LAZY_EXPORTS = {\n'+''.join(f'    "{n}": ("{m}", "{a}"),\n' for n,(m,a) in exports.items()),1)
new=new.replace('__all__ = [','__all__ = [\n'+''.join(f'    "{n}",\n' for n in exports),1)
patch('core-option-b-nine-root-exports.patch',{core:new})
ir='policy-engine/src/polisyos/ir/api.py';text=blob(CURRENT,ir).decode()
irexports={'PosteriorSamplesCarrier':('polisyos.ir.analytics.uncertainty','PosteriorSamplesCarrier'),'load_forecasting_uncertainty_bundle':('polisyos.ir.analytics.forecasting_uncertainty','load_forecasting_uncertainty_bundle'),'persist_forecasting_uncertainty_bundle':('polisyos.ir.analytics.forecasting_uncertainty','persist_forecasting_uncertainty_bundle')}
new=text.replace('ANALYTICS_FACADE_EXPORTS: dict[str, tuple[str, str]] = {','ANALYTICS_FACADE_EXPORTS: dict[str, tuple[str, str]] = {\n'+''.join(f'    "{n}": ("{m}", "{a}"),\n' for n,(m,a) in irexports.items()),1)
assert new!=text
patch('ir-three-canonical-analytics-exports.patch',{ir:new})
execute='policy-engine/src/polisyos/foundry/execute/__init__.py';text=blob(CURRENT,execute).decode()
names=['get_state_path','load_state_snapshot','put_state_snapshot']
new=text.replace('__all__ = ["ResolvedExecutionPosture", "execute", "resolve_execution_posture"]','__all__ = [\n    "ResolvedExecutionPosture",\n    "execute",\n    "get_state_path",\n    "load_state_snapshot",\n    "put_state_snapshot",\n    "resolve_execution_posture",\n]')
new=new.replace('_LAZY_IMPORTS: dict[str, tuple[str, str]] = {','_LAZY_IMPORTS: dict[str, tuple[str, str]] = {\n'+''.join(f'    "{n}": ("polisyos.foundry.execute.executor", "{n}"),\n' for n in names),1)
assert new!=text
patch('foundry-execute-three-canonical-snapshot-exports.patch',{execute:new})
readme='policy-engine/src/polisyos/foundry/uncertainty/README.md'; text=blob(CURRENT,readme).decode();new=text.replace('Exports: 12 names','Exports: 16 names');assert text!=new
patch('owned-uncertainty-readme-count.patch',{readme:new})
identities={'fixture_base_sha':CURRENT,'fixture_base_tree':subprocess.check_output(['git','rev-parse',CURRENT+'^{tree}'],cwd=ROOT,text=True).strip(),'FRC_overlay_sha':FRC,'fixture_is_git_candidate':False,'generator_source_paths':{},'pending_owner_exports':{'core_option_a_entrypoints':['polisyos.core.artifacts','polisyos.core.canon','polisyos.core.registry'],'core_option_b_exports':exports,'ir_analytics_exports':irexports,'foundry_execute_exports':names},'owner_patch_refs':[]}
for ref,path in [(CURRENT,p) for p in [contract,core,ir,execute,readme,'policy-engine/tools/devx/architecture/guardrails.py']]:
 b=blob(ref,path); identities['generator_source_paths'][path]={'source_sha':ref,'sha256':hashlib.sha256(b).hexdigest(),'bytes':len(b)}
for p in PATCHES.iterdir():identities['owner_patch_refs'].append({'path':str(p.relative_to(OUT)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size})
(OUT/'build-inputs.json').write_text(json.dumps(identities,indent=2)+'\n')
print(json.dumps({'patches':len(identities['owner_patch_refs']),'base':CURRENT,'fixture_root':str(FIXTURE),'pending_owner_ratification':True},indent=2))
