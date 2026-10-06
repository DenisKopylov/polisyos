"""Read the complete owned receipt and byte-bind its source/output carriers."""
import hashlib
import json
import pathlib
import subprocess

root = pathlib.Path('/workspace/e02-F-graph-20261006')
path = root / 'policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/F/scm-schema-version-20261006.json'
receipt = json.loads(path.read_text())
required = {'schema','unit','slice','closure_ids','bundle_ids','slice_base_sha',
            'implementation_commits','candidate_tree_sha','branch','pull_request',
            'changed_paths','baseline_cells','checks','property','predicate_basis',
            'capability_state_or_finding_state','limitations_and_next_owner'}
assert required <= receipt.keys(), required - receipt.keys()
assert receipt['closure_ids'] == []
assert receipt['scientific_runtime_sha'] == 'eaf9d0e0ee2dae728351cbb3dfc333474c88931b'
assert receipt['implementation_commits'][-1] == 'e94a40e78416b7392edf96f1f24c7846a808c8d0'
actual_tree = subprocess.check_output(['git','rev-parse',receipt['implementation_commits'][-1]+'^{tree}'],cwd=root,text=True).strip()
assert actual_tree == receipt['candidate_tree_sha']
subprocess.run(['git','merge-base','--is-ancestor',receipt['slice_base_sha'],receipt['implementation_commits'][-1]],cwd=root,check=True)
source_count = 0
for item in receipt['source_bindings'] + receipt['dependency_bindings']:
    body = subprocess.check_output(['git','show',item['source_sha']+':'+item['source_path']],cwd=root)
    assert len(body)==item['bytes'] and hashlib.sha256(body).hexdigest()==item['sha256'],item
    source_count += 1
refs = receipt['evidence_transfer']['complete_companions']
assert len(refs) == receipt['evidence_transfer']['companion_count']
assert len({item['path'] for item in refs}) == len(refs)
for item in refs:
    body = (root/item['path']).read_bytes()
    assert len(body)==item['bytes'] and hashlib.sha256(body).hexdigest()==item['sha256'],item
    original = pathlib.Path(item['original_path'])
    assert original.read_bytes() == body,item
committed_carrier_paths = {item['path'] for item in refs}
allowed = {'PASS','FAIL','ERROR','SKIP','UNRUN'}
for check in receipt['checks']:
    assert {'command','target_sha','environment','input_closure','outcome','output'} <= check.keys(),check
    assert check['outcome'] in allowed and isinstance(check['output'],str),check
    assert check['output'] in committed_carrier_paths,check
    assert check.get('stderr_output',check['output']) in committed_carrier_paths,check
    if 'execution_receipt' in check:
        execution = json.loads((root/check['execution_receipt']).read_text())
        assert execution['source_sha']==check['target_sha']
        assert execution['check']==check['outcome']
        for output in execution['outputs']:
            body=pathlib.Path(output['path']).read_bytes()
            assert len(body)==output['bytes'] and hashlib.sha256(body).hexdigest()==output['sha256']
for value in receipt['per_id'].values():
    assert value['check'] in allowed and value['outcome'] in {'closed','limited','held','open'}
    assert value['outcome']=='limited'
assert all(field in receipt['property'] for field in ['statement','runtime_path','proxy_divergence','negative_controls'])
assert receipt['original_failure_harness_binding']['harness_equal_current_frozen_source']
assert any(c['id']=='scm-version-full-generator-check' and c['outcome']=='FAIL' for c in receipt['checks'])
assert any(c['id']=='scm-version-public-fragment' and c['outcome']=='FAIL' for c in receipt['checks'])
assert any(c['id']=='scm-version-public-fragment-corrected' and c['outcome']=='PASS' for c in receipt['checks'])
print(json.dumps({'check':'PASS','receipt':str(path.relative_to(root)),
                  'receipt_bytes':path.stat().st_size,'receipt_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                  'implementation_tree':actual_tree,'source_bindings_checked':source_count,
                  'complete_companions_checked':len(refs),'canonical_checks':len(receipt['checks']),
                  'closure_ids':[],'per_id_scope':'5 schema-layer limited companion decisions',
                  'historical_and_global_FAIL_retained':True},indent=2))
