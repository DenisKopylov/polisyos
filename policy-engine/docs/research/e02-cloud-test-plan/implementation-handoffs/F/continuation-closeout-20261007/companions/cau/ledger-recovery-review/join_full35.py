"""Read-only complete baseline cell/owner/candidate receipt pointer join."""
import collections
import hashlib
import json
from pathlib import Path
import subprocess
import time

REPO='/workspace/e02-F-cau-20261006'
OLD='d8334672f44d24dd32113264f96ca3f7954dace4'
OWN='4d8eaec43d09d9c7df3a2ac8bd244e4d132d03f9'
P='policy-engine/docs/research/e02-cloud-test-plan/'
PACK=P+'implementation-handoffs/F/continuation-transfer-20261007/per-ID/'
ROOT=Path(__file__).resolve().parent
start=time.monotonic();cache={};receipt_bindings={};checks=set();cell_ids=set();bindings=0;pointer_occurrences=0;json_pointer_occurrences=0
def sha(b):return hashlib.sha256(b).hexdigest()
def raw(ref,path):
    key=(ref,path)
    if key not in cache:cache[key]=subprocess.check_output(['git','show',ref+':'+path],cwd=REPO,stderr=subprocess.PIPE)
    return cache[key]
def ref(path):
    b=path.read_bytes();return dict(path=str(path),bytes=len(b),sha256=sha(b))
def pointer(obj,p):
    for key in p.strip('/').split('/') if p.strip('/') else []:
        key=key.replace('~1','/').replace('~0','~');obj=obj[int(key)] if isinstance(obj,list) else obj[key]
    return obj
proposal=json.loads((ROOT/'expected-original35-compact.json').read_text())
verification=json.loads(raw(OWN,P+'results/verification.json'));source_jobs={j['job']:j['source_sha'] for j in verification['sources']}
rows=[]
for expectation in proposal['rows']:
    fid=expectation['finding_id'];record=json.loads(raw(OLD,PACK+fid+'.json'))
    qpath=ROOT/'baseline-queries'/(fid+'.stdout.json');q=json.loads(qpath.read_text())
    assert q['matching_cells']==q['displayed_cells']==len(q['cells'])
    assert all(r['finding_id']==fid and r['unit']=='F' for r in q['finding_routes'])
    assert {r['cell_id'] for r in q['finding_routes']} == {c['id'] for c in q['cells']}
    mapped=[]
    for cell in q['cells']:
        assert cell['source_sha']==source_jobs[cell['job']]
        body_path=ROOT/'baseline-cells'/(cell['id']+'.stdout.json');body=json.loads(body_path.read_text())
        assert body['matching_cells']==body['displayed_cells']==1 and body['cells'][0]==cell
        mapped.append(dict(cell_id=cell['id'],baseline_source_sha=cell['source_sha'],reported_state=cell['state'],full_cell_query=ref(body_path),cell_pointer='/cells/0',complete_source_job_dictionary=ref(ROOT/'baseline-cells'/(cell['job']+'-context.stdout.json')),source_job_dictionary_pointer='/job_dictionary_or_context_blocks',raw_VM_archive_received=False,candidate_semantic_adequacy_from_baseline='not_established'))
        cell_ids.add(cell['id'])
    refs=[]
    for declared in record['deciding_receipt_refs']:
        refsha=declared['git_ref'];path=declared['path'];b=raw(refsha,path)
        assert len(b)==declared['bytes'] and sha(b)==declared['sha256']
        obj=json.loads(b);selected=pointer(obj,declared['json_pointer']) if declared.get('json_pointer') else obj
        refs.append(dict(artifact_ref=declared,json_pointer_exists=True,selected_complete_JSON_sha256=sha(json.dumps(selected,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()),selected_object_role='Actual immutable complete JSON selector; reference reconstructs full body; not copied/truncated to a summary'))
        receipt_bindings[(refsha,path)]=dict(git_ref=refsha,path=path,bytes=len(b),sha256=sha(b));pointer_occurrences+=1
        if declared.get('json_pointer'):json_pointer_occurrences+=1
    check_refs=[]
    for location in record['complete_raw_receipt_checks_refs']:
        artifact,p=location.split('#',1);carrier,path=artifact.split(':',1);b=raw(carrier,path);obj=json.loads(b);selected=pointer(obj,p)
        checks.add(location)
        check_refs.append(dict(full_check_ref=location,source_receipt_bytes=len(b),source_receipt_sha256=sha(b),selected_complete_JSON_sha256=sha(json.dumps(selected,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()),actual_state_fields={k:v for k,v in selected.items() if k in {'outcome','check','state','result','exit','returncode','target_sha','source_sha','candidate_sha'}} if isinstance(selected,dict) else None))
    bindings+=record['original_card_refs'].__len__()
    rows.append(dict(finding_id=fid,owner_and_criterion_locator=expectation['original_norm_text_ref'],complete_finding_query=ref(qpath),full_cells=mapped,scientific_source=record['scientific_implementation'],actual_candidate_receipt_selectors=refs,complete_actual_check_selectors=check_refs,retained_check=record['check_result'],retained_F_original_recommendation=record['F_finding_outcome'],basis='Original card and actual producer/oracle/consumer receipts. Baseline routes/rawstates are navigation and never criterion closure; current method/runtime/authority outcomes remain separately pinned.'))
assert len(rows)==35 and len({r['finding_id'] for r in rows})==35 and bindings==36
result=dict(schema='e02.F.full35-baseline-candidate-receipt-join.v1',check='PASS',denominator=dict(finding_IDs=35,original_bindings=bindings,bundles=17,unique_baseline_cells=len(cell_ids),complete_source_jobs=len(source_jobs),deciding_primary_receipts=len(receipt_bindings),deciding_receipt_reference_occurrences=pointer_occurrences,deciding_JSON_pointer_occurrences=json_pointer_occurrences,complete_check_pointer_refs=len(checks)),source=dict(prior_ROOT_ledger=OLD,query_source=OWN,expected_criteria_packet=ref(ROOT/'expected-original35-compact.json')),rows=rows,complete_deciding_primary_receipt_bindings=list(receipt_bindings.values()),metadata_results_not_product_PASS=True,old_scientific_material_rewalk=False,raw_VM_archives_missing=True,authority_not_established_from_query=True,scientific_method_rerun=False,elapsed_s=time.monotonic()-start,replayer=ref(Path(__file__)))
path=ROOT/'full35-baseline-candidate-join-v2.json';path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(dict(check=result['check'],denominator=result['denominator'],output=ref(path),elapsed_s=result['elapsed_s']),indent=2))
