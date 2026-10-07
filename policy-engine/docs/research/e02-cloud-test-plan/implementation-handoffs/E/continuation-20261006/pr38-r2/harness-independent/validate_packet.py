"""Recompute moderate copy custody and native-harness predicate denominators."""
from pathlib import Path, PurePosixPath
import argparse, copy, hashlib, json

def validate_index(root, index):
    rows=index['files'];seen=set();total=0
    for row in rows:
        name=row['path'];path=PurePosixPath(name)
        assert not path.is_absolute() and '..' not in path.parts and name not in seen
        seen.add(name);data=(root/name).read_bytes();total+=len(data)
        assert len(data)==row['size_bytes'],name
        assert hashlib.sha256(data).hexdigest()==row['sha256'],name
    assert index['total_files']==len(rows) and index['total_bytes']==total
    return len(rows),total

def validate_properties(root, review=None):
    review=review or json.loads((root/'review.json').read_text())
    plan=json.loads((root/'plan-snapshot.json').read_text())
    correction=json.loads((root/'denominator-correction.json').read_text())
    raw=json.loads((root/'harness-independent-review.json').read_text())
    assert review['candidate']==plan['candidate_sha']==raw['source_sha']==correction['source_sha']=='4758d495abb81aa51fea8e28cd071ca9ff989155'
    assert review['tree']==plan['candidate_tree_sha']==raw['source_tree']
    assert review['verdict']=='GO-bounded-owned-harness-readiness-and-preservation'
    d=review['input_denominators']
    groups=plan['groups'];native=[x for xs in groups.values() for x in xs]
    assert len(native)==len(set(native))==d['native_test_paths']==plan['native_test_path_count']==120
    assert len(plan['owner_packet_extra_inputs'])==d['A_owner_packet_paths']==2
    assert d['total_test_file_inputs']==len(native)+len(plan['owner_packet_extra_inputs'])==122
    assert d['native_groups']==len(groups)==7
    paths=plan['changed_python_lint_paths'];docs=[x for x in paths if x.startswith('docs/')]
    assert d['planned_Ruff_changed_Python_exact4758']==len(paths)==correction['total_denominator']==211
    assert d['docs_witnesses_in_Ruff_denominator_exact4758']==len(docs)==correction['actual_value']==109
    assert correction['historical_reported_value']==raw['planned_Ruff_docs_artifact_paths']==0
    assert d['focused_configured_Ruff_files']==3
    gate_names=[j['name'] for j in plan['jobs'] if j['kind']=='gate']
    assert gate_names==raw['required_gate_sequence']==['architecture','runtime-api-contract','static-invocation','ruff','ruff-format','workspace-verify','ci-parity']
    assert plan['execution_state']=='NOT_RUN' and raw['native_wave_state'].startswith('UNRUN')
    assert plan['missing_required_paths']==[] and plan['old_paths_retained']
    for j in plan['jobs']:
        if j['kind']=='numerical':
            assert 'addopts=' not in j['argv'] and 'no:cacheprovider' not in j['argv']
    assert raw['controls'][0]['prepare_counter']==raw['controls'][1]['process_counter']==0
    assert raw['controls'][2]['process_spy_counter']==1 and raw['controls'][2]['real_children_launched']==0
    assert raw['controls'][3]['counts']=={'cases':4,'passed':1,'failed':1,'errors':1,'skipped':1}
    browser=json.loads((root/'browser-capability-receipt.json').read_text())
    assert browser['capability']['actualRenderedText']=='4'
    data=(root/'browser-capability.stdout').read_bytes()
    assert len(data)==browser['stdout_size_bytes'] and hashlib.sha256(data).hexdigest()==browser['stdout_sha256']
    assert browser['exit_code']==0
    return True

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,default=Path(__file__).parent);a=parser.parse_args()
    index=json.loads((a.root/'copy-index.json').read_text())
    count,total=validate_index(a.root,index);assert validate_properties(a.root)
    negatives=[]
    for field,value in [('size_bytes',-1),('sha256','0'*64)]:
        damaged=copy.deepcopy(index);damaged['files'][0][field]=value
        try:validate_index(a.root,damaged)
        except AssertionError:negatives.append(field+' REFUSED')
        else:raise AssertionError('custody corruption accepted')
    damaged=json.loads((a.root/'review.json').read_text());damaged['input_denominators']['native_test_paths']=119
    try:validate_properties(a.root,damaged)
    except AssertionError:negatives.append('native denominator REFUSED')
    else:raise AssertionError('predicate count corruption accepted')
    print(json.dumps({'outcome':'PASS-recomputing-moderate-custody-and-predicate-validator','corrupt_field_controls':negatives,'numeric_and_full_CI':'UNRUN'}))
if __name__=='__main__':main()
