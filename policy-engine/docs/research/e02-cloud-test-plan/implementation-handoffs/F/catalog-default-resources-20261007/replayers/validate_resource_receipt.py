"""Validate source and HANDOFF protocol structure independently of test PASS labels."""
import hashlib,json,pathlib,subprocess,sys
repo=pathlib.Path('/workspace/e02-F-graph-20261006');primary=pathlib.Path(sys.argv[1]);stage=pathlib.Path(sys.argv[2]);value=json.loads(primary.read_text())
required=['schema','unit','slice','closure_ids','bundle_ids','slice_base_sha','implementation_commits','candidate_tree_sha','branch','pull_request','changed_paths','baseline_cells','checks','property','predicate_basis','capability_state_or_finding_state','limitations_and_next_owner']
assert all(k in value for k in required)
assert value['closure_ids']==[]
assert value['candidate_sha']=='81f482e04bd8a2c85f894d425847c6e8657b6ea6'
assert len(value['changed_paths'])==14
for sha in value['implementation_commits']:
 subprocess.run(['git','merge-base','--is-ancestor',sha,value['candidate_sha']],cwd=repo,check=True)
actual=set(subprocess.check_output(['git','diff','--name-only',value['slice_base_sha'],value['candidate_sha']],cwd=repo,text=True).splitlines());assert actual==set(value['changed_paths'])
assert value['candidate_tree_sha']==subprocess.check_output(['git','rev-parse',value['candidate_sha']+'^{tree}'],cwd=repo,text=True).strip()
manifest=json.loads((stage/'outputs.json').read_text());material={r['path']:r for r in manifest['files']}
assert len(material)==len(manifest['files'])
for row in value['source_identity']['files']:
 b=subprocess.check_output(['git','show',value['candidate_sha']+':'+row['path']],cwd=repo);assert len(b)==row['bytes'] and hashlib.sha256(b).hexdigest()==row['sha256']
 if row['original_YAML_unchanged']:assert b==subprocess.check_output(['git','show',value['slice_base_sha']+':'+row['path']],cwd=repo)
for row in value['checks']:
 for k in ['command','target_sha','environment','input_closure','outcome','output']:assert isinstance(row[k],str) and row[k]
 assert row['outcome'] in ['PASS','FAIL','ERROR','SKIP','UNRUN']
 assert row['output'] in material
assert value['checks_denominator']['canonical_checks']==len(value['checks'])
assert value['P41']['check']=='not_established'
assert value['per_id']['B214']['outcome']=='limited'
assert any(r['outcome']=='UNRUN' and r['check_id']=='independent-fresh-full-installed-profile' for r in value['checks'])
assert any(r['outcome']=='FAIL' and r['check_id']=='resource-final-owned-ruff' for r in value['checks'])
assert any(r['outcome']=='FAIL' and r['check_id']=='independent-canonical-public-surface-completeness' for r in value['checks'])
print(json.dumps({'check':'PASS','candidate_sha':value['candidate_sha'],'source_paths':14,'original_curated_yaml':4,'required_minimum_fields':len(required),'canonical_checks':len(value['checks']),'material_files':len(material),'closure_ids':[],'scope':'Author source/protocol selfcheck; independent runtime/API review remains separate. Actual full encoded/decoded material uses verify_resource_transport.py.'},indent=2))
