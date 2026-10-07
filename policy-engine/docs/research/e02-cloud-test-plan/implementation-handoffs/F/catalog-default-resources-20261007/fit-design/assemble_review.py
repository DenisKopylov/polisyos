from pathlib import Path
import hashlib,json,subprocess
root=Path('/workspace/e02-F-closeout-20261006')
base=Path(__file__).resolve().parent
graph=Path('/tmp/e02-F-continuation-20261007/graph/packaged-default-diagnosis')
def ref(path):
 data=path.read_bytes();return {'path':str(path),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
basis=json.loads((base/'basis-audit.json').read_bytes())
checks=[]
for kind in ['wheel','sdist']:
 execution=json.loads((base/f'{kind}-additional.execution.json').read_bytes())
 assert execution['exit']==0
 for label in ['stdout','stderr']:
  obj=execution['outputs'][label];assert ref(Path(obj['path']))==obj
 checks.append({'id':f'{kind}-additional-consumer-characterization','outcome':'PASS','meaning':'Characterization assertions passed; actual default DatasetBatchConfig ERROR and Fabric empty/static degradation remain negative measurements, not default resource acceptance.','execution':ref(base/f'{kind}-additional.execution.json'),'output':str(base/f'{kind}-additional.stdout.txt'),'output_ref':ref(base/f'{kind}-additional.stdout.txt'),'stderr':ref(base/f'{kind}-additional.stderr.txt')})
for kind in ['wheel','sdist']:
 metadata=json.loads((graph/f'{kind}-defaults.json').read_bytes())
 for label in ['stdout','stderr']:
  path=graph/f'{kind}-defaults.{"stdout.json" if label=="stdout" else "stderr.txt"}'
  assert path.stat().st_size==metadata[f'{label}_bytes'] and hashlib.sha256(path.read_bytes()).hexdigest()==metadata[f'{label}_sha256']
review={
 'review_kind':'Independent read-only packaging diagnosis and bounded design review; no implementation acceptance',
 'source_sha':basis['source_sha'],'source_tree':basis['source_tree'],'closure_ids':[],
 'decision':'GO_BOUNDED for single canonical resource resolver + exact four original YAML projections; implementation and installed-default positive remain UNRUN until canonical writer freezes and tests them.',
 'runtime_changes_by_reviewer':False,'source_doc_git_writes_by_reviewer':False,'new_quota':False,'repeated_numerical_suites':False,
 'basis':ref(base/'basis-audit.json'),
 'observations':[
  {'property':'Required curated defaults are absent in actual built artifacts','outcome':'FAIL','denominator':'complete members of wheel3464/sdist12521/rebuilt-wheel3464 plus four exact basenames in each installed site','proof':ref(base/'basis-audit.json')},
  {'property':'Default seed scoring works in installed composition','outcome':'ERROR','reason':'Actual native score_variable_pair invokes missing default Path outside installed site; FileNotFoundError in both real environments.','existing_graph_outputs':[ref(graph/f'{kind}-defaults.stdout.json') for kind in ['wheel','sdist']]},
  {'property':'Default metrics configuration works in installed composition','outcome':'ERROR','reason':'Actual native DatasetBatchConfig fails ValueError for missing metrics_map.yaml in both real environments.','checks':['wheel-additional-consumer-characterization','sdist-additional-consumer-characterization']},
  {'property':'Default proxy/WVS resources were positively witnessed','outcome':'UNRUN','reason':'Observed native {} / 15 static Fabric dataset IDs are degraded fallbacks. No resource positive established by successful call return.'},
  {'property':'Existing explicit caller Path and curated law remain usable','outcome':'PASS','reason':'Both genuine installed modules consume original tracked source YAML: public seed facade identity and RL/GE seed support1, proxy country/year0.12/0.18/0.15, actual custom metrics configuration35source entries. This is explicit-path compatibility, not default packaging positive.','checks':['wheel-additional-consumer-characterization','sdist-additional-consumer-characterization']}
 ],
 'checks':checks,
 'proposal':{
  'canonical_owner':'team-data-forge catalog domain; parent root must choose one writer and coordinate C-owned sources.',
  'shared_resolver':'One internal catalog-domain helper returning durable pathlib.Path for a finite four-name allowlist. Source anchor is exact developer src layout pointing at original data/dataset_catalog; unpacked installed layout selects package-private catalog/_resources assets. No second YAML catalog, CWD/neighbor repository fallback, raw data search or temporary as_file Path.',
  'path_return_abi':'Existing public read_api.catalog.default_seed_alignments_path and load_seed_alignments identity/signatures remain stable. Existing explicit custom paths and seed_alignments iterable precedence remain stable; resource packaging does not rewrite curated laws.',
  'default_owner_source_files':[
   'policy-engine/src/polisyos/data_forge/domains/catalog/knowledge/variable_alignment.py',
   'policy-engine/src/polisyos/data_forge/domains/catalog/knowledge/proxy_penalties.py',
   'policy-engine/src/polisyos/data_forge/domains/catalog/batch/core_sources/loaders.py',
   'policy-engine/src/polisyos/data_forge/domains/catalog/batch/harvester.py',
   'policy-engine/src/polisyos/data_forge/domains/catalog/batch/config.py',
   'policy-engine/src/polisyos/fabric/connectors/sources/wvs.py'],
  'runtime_boundary':'Fabric must invoke the canonical helper through existing polisyos.data_forge.read_api.catalog. One additive lazy export avoids a new deep private cross-package dependency. IR alignment_certification already consumes that existing facade and requires no new internal import.',
  'packaging_owner_file':'policy-engine/hatch.toml',
  'wheel_projection':[{ 'source':r['path'],'target':'polisyos/data_forge/domains/catalog/_resources/'+Path(r['path']).name,'bytes':r['bytes'],'sha256':r['sha256']} for r in basis['resources']],
  'sdist_contract':'Include the four original data/dataset_catalog/*.yaml paths; wheel rebuilt from genuine sdist projects those same bytes. Existing seven force-includes remain exact. No app dependencies, uv.lock, markers or production raw data additions.',
  'compatibility_window':'Genuine source checkout and ordinary file-backed installed wheel/rebuilt sdist. Zip-import/non-filesystem resources cannot be claimed under current public Path contract without a separately specified reader lifetime/API.',
  'missing_corrupt_boundary':'The existing seed/metrics errors and proxy/WVS degraded fallbacks are different current contracts. Packaging-only repair preserves parse policy; it cannot claim classwide typed refusal merely because all YAML files are shipped. If root explicitly admits required-default fail-closed behavior, reuse existing DataForgeValidationError for missing/unreadable/syntactically corrupt default resource and propagate it through default-only broad WVS catches. Do not impose new per-indicator scientific validation, normalization, confidence law, custom-path schema or new error/authority subsystem.',
  'required_controls':[
   'Exact four original Git bytes in wheel, source sdist, rebuilt wheel and genuine installed sites; removal of any projection must fail actual corresponding default reader.',
   'All six default-owner files use canonical resolver; source layout returns original paths and installed layout returns paths under that installed package. Deliberate neighboring/CWD resources cannot rescue missing selected resource.',
   'Actual installed default seed score/public facade, proxy overrides, DatasetBatchConfig metrics reader and both DataForge WVS loaders plus real Fabric list_datasets, with current consumer semantics separately classified.',
   'Explicit original custom path override remains selected; prior default cache entries cannot replace a distinct explicit path; existing seed iterable precedence retained.',
   'Default missing/syntax corrupt behavior is measured and labeled under explicitly adopted absence/parse policy, not inferred from Path reflection. No fake file injected into installed default location.',
   'Public functions remain canonical same objects through read_api and preserve stable existing pickle/FQN behavior; unknown exports refuse.',
   'Actual-current Hatch build resource oracle is separate from historical LEGACY migration equivalence and reconstructs current seven projection sources plus four proposed assets from exact source inputs.'
  ]
 },
 'downstream_companions':{
  'public_surface':'policy-engine/architecture/public_surface/contract.toml declares only DataForge root and read_api supported entrypoints; nested catalog currently not inventoried. Adding catalog helper leaves literal root __all__ unchanged, but actual maintained generator review must establish generated inventory/reference deltas. If changed, canonical architecture/public_surface/inventory.json and docs/reference/public-surface.md belong existing architecture/API writer. No broad regeneration authority granted by this read-only review.',
  'public_owner_document':'policy-engine/src/polisyos/data_forge/README.md and nearest existing catalog/batch README (no catalog/README exists). Declare file-backed default-path window, explicit custom override and selected missing/corrupt policy in structured release fragment.',
  'packaging_tests':'Existing policy-engine/tests/repo_quality/tools/test_hatch_packaging.py uses original LEGACY includes and whole-archive equality; its context excludes all seven current force-include source paths. This static denominator limitation predates proposed assets. Add unique actual-current resource projection/build consumer test; do not indiscriminately weaken/replace historical LEGACY oracle assertions.'
 },
 'limitations':['No proposed implementation exists or is reviewed by this packet.','No installed repaired-default positive, missing/corrupt repaired-policy or negative-removal control has executed.','No statistical identification/operational admission/native value authority or B56 admitted workload/budget positive claimed.','Raw WVS CSV/XLSX, remote provider availability and full production data remain outside four curated resource projection.','Literal domainlaw/hash inventory is not a general DataForge resource census; Graph owner separately captures full source denominator.'],
 'external_complete_evidence':[ref(graph/name) for name in ['probe_installed_defaults.py','wheel-defaults.json','wheel-defaults.stdout.json','wheel-defaults.stderr.txt','sdist-defaults.json','sdist-defaults.stdout.json','sdist-defaults.stderr.txt']],
 'source_refs':'Exact resource/provider/reader/packaging source Git byte locators are in basis-audit.json; no copied tracked YAML/source or derived source views transported.'
}
body=json.dumps(review,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode();review['integrity']={'body_sha256':hashlib.sha256(body).hexdigest(),'meaning':'Receipt byte integrity only; not an authority signature or admission seal.'}
(base/'review.json').write_text(json.dumps(review,indent=2,ensure_ascii=False)+'\n')
files=[ref(base/name) for name in ['review.json','basis-audit.json','basis-audit.stdout.txt','basis-audit.stderr.txt','inspect_basis.py','probe_additional_consumers.py','run_probes.py','assemble_review.py','wheel-additional.execution.json','wheel-additional.stdout.txt','wheel-additional.stderr.txt','sdist-additional.execution.json','sdist-additional.stdout.txt','sdist-additional.stderr.txt']]
selection={'files':files,'external_existing_owner_files':review['external_complete_evidence'],'source_reconstruction':'Immutable Git b5 refs in basis-audit.json; originals are not copied. Archive binary zip/tar are optional local raw; complete archive membership observation is recorded. Graph full outputs must be transferred by canonical Graph owner or root via their exact bindings.','excluded':'Own /tmp state directories contain only custom-config created empty structure, no deciding state/input data; no production data copied.','unique_file_count':len(files),'unique_full_bytes':sum(item['bytes'] for item in files)}
(base/'transfer-selection.json').write_text(json.dumps(selection,indent=2)+'\n')
print(json.dumps({'review':ref(base/'review.json'),'selection':ref(base/'transfer-selection.json'),'unique_file_count':len(files),'unique_full_bytes':selection['unique_full_bytes']},indent=2))
