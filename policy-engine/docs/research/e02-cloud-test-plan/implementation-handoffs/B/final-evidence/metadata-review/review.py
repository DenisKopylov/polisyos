"""Read-only final-a3 metadata custody review. No utility reruns, tests or checkouts."""
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter
import ast, csv, hashlib, io, json, subprocess

ROOT = Path('/tmp/e02-B-cas-final-a3-metadata-review')
REPO = '/workspace/e02-B-acceptance'
INPUT = Path('/workspace/e02-B-coordination/.polisyos/e02-B/raw/final-a3')
FINAL = 'a3daffbe867ddfe9eede5e5990687283b552952a'
RECEIPTS = 'policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/B'
ORG = 'policy-engine/docs/research/e02-cloud-test-plan/execution-organization'
RESULTS = 'policy-engine/docs/research/e02-cloud-test-plan/results'
BASES = {'run':'run.json','exe':'exe-state.json','cas':'cas-tenant-contract.json','dur':'dur-ledger.json','cmp':'cmp-res.json','adapters':'adapters.json'}
CUSTODY = {}
CACHE = {}

def digest(data):
    return hashlib.sha256(data).hexdigest()

def canonical_digest(value):
    return digest(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode())

def git(*args):
    return subprocess.check_output(['git','-C',REPO,*args],stderr=subprocess.PIPE)

def obj(sha,path):
    key = sha+':'+path
    if key not in CACHE:
        data=git('show',key)
        CUSTODY[key]={'git_blob':git('rev-parse','--verify',key).decode().strip(),'bytes':len(data),'sha256':digest(data)}
        CACHE[key]=data
    return CACHE[key]

def blob(sha,path):
    return git('rev-parse','--verify',sha+':'+path).decode().strip()

def ancestor(parent,child):
    return subprocess.run(['git','-C',REPO,'merge-base','--is-ancestor',parent,child],stdout=subprocess.PIPE,stderr=subprocess.PIPE).returncode==0

def load_file(path):
    data=path.read_bytes()
    CUSTODY[str(path)]={'bytes':len(data),'sha256':digest(data)}
    return json.loads(data)

def dispositions(doc):
    value=doc.get('finding_dispositions',doc.get('finding_classification'))
    if isinstance(value,list): return [(r.get('finding_id',r.get('id')),i,r) for i,r in enumerate(value)]
    if isinstance(value,dict): return [(key,key,row) for key,row in value.items()]
    raise AssertionError('Missing actual per-finding dispositions')

def table(root,name):
    return list(csv.DictReader(io.StringIO(obj(FINAL,root+'/'+name+'.tsv').decode()),delimiter='\t'))

prepared=load_file(INPUT/'preparation-commands.json')
cohort=load_file(INPUT/'cohort.json')
reconciled=load_file(INPUT/'reconciliation.json')
assert prepared['final_source_frozen'] and prepared['no_runtime_execution_by_preparer']
assert prepared['tool_source_sha']=='898a28dc9c6cddb84be0747326c5a9f5fd43ed81'
for name in ['b_family_inputs.py','reconcile_b_owners.py','prepare_native_cohort.py']:
    obj(prepared['tool_source_sha'],RECEIPTS+'/verification-tools/'+name)
assert cohort['final_head']==reconciled['final_head']==FINAL
final_tree=git('rev-parse',FINAL+'^{tree}').decode().strip()
assert cohort['final_tree']==reconciled['final_tree']==final_tree
heads=cohort['family_heads']; pins=cohort['explicit_final_source_points']
assert set(heads)==set(pins)==set(BASES)
ordered_overlays={'run':[],'exe':[RECEIPTS+'/exe-cold-seed.json'],'cas':[RECEIPTS+'/cas-archive-output-entry.json'],'dur':[],'cmp':[],'adapters':[RECEIPTS+'/adapters-deadline.json']}
for command in prepared['commands']:
    argv=command['argv']
    assert command['exit_code']==0 and command['stderr']==''
    assert argv[argv.index('--final-head')+1]==FINAL and '--require-ready' in argv
    for key,expected in [('--family-head',heads),('--source-point',pins)]:
        found=dict(argv[i+1].split('=',1) for i,arg in enumerate(argv) if arg==key)
        assert found==expected
    got=[argv[i+1] for i,arg in enumerate(argv) if arg=='--overlay']
    assert got==[family+'='+path for family in ['exe','cas','adapters'] for path in ordered_overlays[family]]

bundle_table=table(ORG,'bundle-owners');finding_table=table(ORG,'finding-owners')
owned_bundles={r['bundle_id'] for r in bundle_table if r['unit']=='B'}
owned_findings={r['finding_id']:r for r in finding_table if r['unit']=='B'}
assert len(bundle_table)==127 and len(finding_table)==282 and len(owned_bundles)==25 and len(owned_findings)==60
assert reconciled['denominators']=={'all_bundles':127,'all_findings':282,'B_bundles':25,'B_findings':60}
assert not reconciled['errors'] and reconciled['bookkeeping_outcome']=='PASS_with_declaration_warnings'
assert reconciled['formal_closure_or_runtime_acceptance']=='not_established_by_this_metadata_join'
expected_warning={'kind':'advertised_bundle_scope_mismatch','family':'cas','missing_advertised_bundles':['CAS-01','CAS-03'],'extra_advertised_bundles':[],'note':'Criterion-owner join is explicit; never treat closure_ids as scope.'}
assert reconciled['warnings']==[expected_warning]
joined={r['finding_id']:r for r in reconciled['findings']}
assert len(joined)==len(reconciled['findings'])==60 and set(joined)==set(owned_findings)
assert set(reconciled['canonical_owned_bundles'])==owned_bundles
family_checks={}
receipts_by_family={}
for family in sorted(heads):
    head=heads[family];pin=pins[family];meta=reconciled['families'][family]
    assert meta['head']==head and meta['head_is_ancestor_of_final'] and ancestor(head,FINAL)
    assert ancestor(pin,head) and meta['explicit_final_source_point']==pin
    assert meta['source_point_declared_in_ordered_receipts'] is True
    expected_paths=[RECEIPTS+'/'+BASES[family],*ordered_overlays[family]]
    assert [r['source_receipt'] for r in meta['ordered_receipts']]==[p+'@'+head for p in expected_paths]
    effective={};history={};docs=[];declared_pins=set()
    for priority,path in enumerate(expected_paths):
        doc=json.loads(obj(head,path));docs.append((path,doc))
        declared_pins.update(doc.get('implementation_commits',[]))
        for key in ['source_sha','candidate_sha','target_sha']:
            if isinstance(doc.get(key),str):declared_pins.add(doc[key])
        declared_pins.update(c.get('target_sha') for c in doc.get('checks',[]) if isinstance(c.get('target_sha'),str))
        rows=dispositions(doc)
        assert len({fid for fid,_,_ in rows})==len(rows)
        assert meta['ordered_receipts'][priority]['receipt_blob']==CUSTODY[head+':'+path]['git_blob']
        for fid,index,row in rows:
            hist={'source_receipt':path+'@'+head,'receipt_blob':CUSTODY[head+':'+path]['git_blob'],'disposition_index':index,'priority':priority,'disposition_sha256':canonical_digest(row)}
            history.setdefault(fid,[]).append(hist)
            effective[fid]=(path,index,priority,row)
    assert pin in declared_pins
    actual_ids={fid for fid,row in joined.items() if row['family']==family}
    assert actual_ids==set(effective)
    for fid,(path,index,priority,row) in effective.items():
        actual=joined[fid];canonical=owned_findings[fid]
        assert actual['canonical_owner_row']==canonical and actual['canonical_bundle']==canonical['source_closure_owner']
        assert actual['canonical_source_status']==canonical['source_status']
        assert actual['head']==head and actual['source_receipt']==path+'@'+head
        assert actual['disposition_index']==index and actual['priority']==priority
        assert actual['effective_disposition']==row and actual['ordered_disposition_history']==history[fid]
    receipts_by_family[family]=docs
    family_checks[family]={'head':head,'source_point':pin,'source_point_ancestor_of_family':True,'family_ancestor_of_final':True,'source_point_explicitly_declared':True,'owned_findings':len(actual_ids),'rich_dispositions_equal_exact_git_receipts':True,'ordered_receipts':[p+'@'+head for p in expected_paths]}
assert joined['B52']['priority']==joined['B60']['priority']==1
assert all(r['priority']==1 for r in joined.values() if r['family'] in ['cas','adapters'])
assert all('cas.json@' not in str(r) for r in joined.values() if r['family']=='cas')

routes=table(RESULTS,'routes');cells=table(RESULTS,'cells');properties=table(RESULTS,'properties')
cell_by_id={r['id']:r for r in [*cells,*properties]}
B_routes=[r for r in routes if r['unit']=='B']
assert {r['finding_id'] for r in B_routes}==set(owned_findings)
historical_cells={r['cell_id'] for r in B_routes}
assert len(historical_cells)==189 and historical_cells<=set(cell_by_id)
historical_counts={}
for family in sorted(heads):
    family_ids={fid for fid,row in joined.items() if row['family']==family}
    ids={row['cell_id'] for row in B_routes if row['finding_id'] in family_ids}
    selected=[cell_by_id[cid] for cid in sorted(ids)]
    for _,doc in receipts_by_family[family]:
        explicit={cell if isinstance(cell,str) else cell.get('id',cell.get('cell_id')) for cell in doc.get('baseline_cells',[])}
        assert explicit<=ids
        if family!='exe': assert explicit==ids
    if family=='exe':
        assert receipts_by_family[family][0][1]['baseline_denominator']['complete_unique_routed_cells_resolved']==len(ids)==64
    historical_counts[family]={'canonical_unique_cells':len(ids),'selected_canonical_cells_sha256':canonical_digest(selected),'role':'historical navigation context only; not new fix/runtime proof'}
assert {f:v['canonical_unique_cells'] for f,v in historical_counts.items()}=={'adapters':37,'cas':28,'cmp':23,'dur':19,'exe':64,'run':18}
assert sum(v['canonical_unique_cells'] for v in historical_counts.values())==189
for job_file in sorted({cell_by_id[cid]['source_file'] for cid in historical_cells}):obj(FINAL,RESULTS+'/'+job_file)

assert cohort['ready_at_final_head'] and cohort['no_test_execution_performed_by_preparer']
for name in ['final_missing_files','final_mismatching_files','missing_explicit_final_source_points','source_points_unconfirmed_in_explicit_receipts']: assert cohort[name]==[]
paths=cohort['test_paths'];bindings=cohort['per_file_bindings']
assert len(paths)==len(set(paths))==len(bindings)==cohort['whole_file_count']==74
assert set(paths)=={r['path'] for r in bindings}
assert len(cohort['native_waves'])==12
for record in bindings:
    path=record['path'];final_blob=blob(FINAL,'policy-engine/'+path)
    assert record['selection']=='complete_file_no_node_or_k_filter' and record['final_head_blob']==final_blob
    selected_blobs=[]
    for binding in record['source_bindings']:
        family=binding['family']
        assert binding['family_head']==heads[family] and binding['explicit_final_source_point']==pins[family]
        assert binding['family_head_blob']==blob(heads[family],'policy-engine/'+path)
        assert binding['observed_wave_blob']==blob(binding['observed_wave_target'],'policy-engine/'+path)
        source_blob=blob(pins[family],'policy-engine/'+path)
        assert binding['final_receipt_source_blob']==source_blob
        selected_blobs.append(source_blob)
    assert final_blob in selected_blobs and record['final_matches_at_least_one_final_receipt_source_point']
argv=cohort['candidate_command_argv']
assert [arg for arg in argv if arg.startswith('tests/')]==paths
assert not any('::' in p for p in paths) and '-k' not in argv and '-m' in argv
run_waves=[w for w in cohort['native_waves'] if w['family']=='run']
assert len(run_waves)==1 and run_waves[0]['file_count']==4 and run_waves[0]['observed_target_sha']==pins['run']
run_checks=[c for c in receipts_by_family['run'][0][1]['checks'] if c.get('command')==run_waves[0]['source_command'] and c.get('target_sha')==pins['run']]
assert len(run_checks)==1 and run_checks[0]['outcome']=='PASS' and '125 passed' in run_checks[0]['output']
nonpass=cohort['retained_nonpass']
assert len(nonpass)==2
assert nonpass[0]['observed_target_sha']==pins['cas'] and 'never xfail/deselect/normalize' in nonpass[0]['outcome']
assert nonpass[0]['existing_log']==RECEIPTS+'/cas-output-logs/native302.txt@'+heads['cas']
cas_log=obj(heads['cas'],RECEIPTS+'/cas-output-logs/native302.txt')
assert b'test_import_enforces_existing_tenant_ownership' in cas_log and b'301 passed' in cas_log
assert nonpass[1]['existing_log']==RECEIPTS+'/adapters-logs/llm-cancellation-final.log@'+heads['adapters']
llm_log=obj(heads['adapters'],RECEIPTS+'/adapters-logs/llm-cancellation-final.log')
assert b'test_cancelled_initiator_cannot_erase_actual_provider_cost' in llm_log
for entry in nonpass:
    assert entry['path'] in paths
    source=ast.parse(obj(FINAL,'policy-engine/'+entry['path']))
    node=next(n for n in ast.walk(source) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name==entry['node'])
    decorators=[ast.unparse(d) for d in node.decorator_list]
    if 'test_cas_02' in entry['path']:
        assert not any('xfail' in d or 'skip' in d for d in decorators)
    else:
        assert any('xfail' in d and 'strict=True' in d for d in decorators)

DUR=Path('/workspace/e02-B-dur-ledger/_build/e02-B-dur-ledger/audit-net-final/final-receipt-audit-compact.json')
dur=load_file(DUR)
assert CUSTODY[str(DUR)]['sha256']=='a6f27ac657b39f7b22b85210c8af5841818a7429fab3b2ab3873410ef35b5404'
for lane in dur['compact_receipt_audit']['lanes']:
    family=lane['lane']
    assert lane['frozen_head']==heads[family] and lane['remote_head']==heads[family] and lane['remote_head_verified']
    assert lane['finding_disposition_count']==family_checks[family]['owned_findings']
    assert lane['baseline_cell_count']==historical_counts[family]['canonical_unique_cells']
    assert lane['verdict']=='metadata_custody_pass_bounded'
# Re-read only three frozen preparation inputs to detect a change during this metadata audit.
for name in ['preparation-commands.json','cohort.json','reconciliation.json']:
    path=INPUT/name
    assert digest(path.read_bytes())==CUSTODY[str(path)]['sha256']
report={'schema':'policyos.e02.B_final_metadata_independent_review.v1','observer':'/root/cas_probe','observed_utc':datetime.now(timezone.utc).isoformat(),'outcome':'PASS_bounded_metadata_custody','final_head':FINAL,'final_tree':final_tree,'tool_source_sha':prepared['tool_source_sha'],'review_script_sha256':digest(Path(__file__).read_bytes()),'runtime_execution_performed':False,'utility_or_fault_controls_rerun':False,'new_checkouts_created':0,'source_writes':False,'families':family_checks,'denominators':{'owned_bundles':25,'owned_findings':60,'canonical_historical_cells':189,'whole_test_files':74,'historical_native_waves':12},'historical_cell_context':historical_counts,'sole_advertisement_warning':expected_warning,'retained_nonpass':nonpass,'rich_dispositions_preserved_exactly':True,'DUR_independent_packet_crosscheck':{'path':str(DUR),**CUSTODY[str(DUR)],'same_six_heads_counts':True},'input_and_git_path_custody':CUSTODY,'limits':['Read-only metadata/Git custody review; no runtime verdict or formal finding closure','Historical189 cells and wave case counts remain context, not proof of this source fix','Actual native denominator and outcome come only from frozen-run stdout/JUnit','Existing workspace-admission and local-data/consumer residuals are preserved; no blanket admission claim']}
(ROOT/'review.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'outcome':report['outcome'],'final_head':FINAL,'final_tree':final_tree,'tool_source_sha':prepared['tool_source_sha'],'six_ancestor_heads_and_declared_source_points':True,'owned_bundles':25,'owned_findings':60,'historical_cells_context_only':189,'whole_test_files':74,'historical_native_waves':12,'rich_dispositions_preserved':True,'sole_warning':['CAS-01','CAS-03'],'CAS02_held_FAIL_and_LLM_strict_XFAIL_preserved':True,'no_runtime_tests_utility_controls_or_newtrees':True,'input_hashes':{n:CUSTODY[str(INPUT/n)]['sha256'] for n in ['cohort.json','reconciliation.json','preparation-commands.json']},'report_path':str(ROOT/'review.json'),'report_sha256':digest((ROOT/'review.json').read_bytes())},ensure_ascii=False,indent=2))
