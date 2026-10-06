"""Independent metadata-only B37 removal control; immutable Git receipts, no pytest."""
from pathlib import Path
import contextlib, copy, hashlib, importlib, io, json, subprocess, sys

ROOT = Path('/tmp/e02-B-cas-metadata75f')
TOOLS = ROOT/'research/implementation-handoffs/B/verification-tools'
sys.path.insert(0,str(TOOLS))
coordinated=Path('/workspace/e02-B-coordination/.polisyos/e02-B/raw/pre-freeze-75f')
commands=json.loads((coordinated/'commands.json').read_text())
ROOT.joinpath('commands-original.json').write_bytes((coordinated/'commands.json').read_bytes())
b_inputs=importlib.import_module('b_family_inputs')
reconcile=importlib.import_module('reconcile_b_owners')
original=reconcile.ordered_receipts
original_args=commands['commands'][0]['argv'][2:]
mutation=[]

def fault_rows(args,heads,family):
    rows=original(args,heads,family)
    if family!='dur':
        return rows
    output=[]
    for path,doc in rows:
        changed=copy.deepcopy(doc)
        old=changed['finding_dispositions']
        removed=[row for row in old if row.get('finding_id')=='B37']
        if len(removed)!=1:
            raise AssertionError('B37 must exist exactly once in the real current DUR receipt')
        changed['finding_dispositions']=[row for row in old if row.get('finding_id')!='B37']
        assert {k:v for k,v in doc.items() if k!='finding_dispositions'}=={k:v for k,v in changed.items() if k!='finding_dispositions'}
        mutation.append({'family':family,'receipt':path+'@'+heads[family],'only_change':'remove finding_dispositions row B37 in memory','removed_row':removed[0],'unchanged_closure_ids':changed.get('closure_ids'),'unchanged_bundle_ids':changed.get('bundle_ids'),'before_rows':len(old),'after_rows':len(changed['finding_dispositions'])})
        output.append((path,changed))
    return output

runs=[]
for mode in ['unaltered','remove-B37']:
    output=ROOT/(mode+'-reconciliation.json')
    args=list(original_args)
    args[args.index('--output')+1]=str(output)
    sys.argv=[str(TOOLS/'reconcile_b_owners.py'),*args]
    reconcile.ordered_receipts=original if mode=='unaltered' else fault_rows
    stdout=io.StringIO()
    with contextlib.redirect_stdout(stdout):
        code=reconcile.main()
    log=stdout.getvalue()
    (ROOT/(mode+'-stdout.txt')).write_text(log)
    report=json.loads(output.read_text())
    runs.append({'mode':mode,'argv':sys.argv,'exit_code':code,'stdout':log,'report':output.name,'report_sha256':hashlib.sha256(output.read_bytes()).hexdigest(),'joined_finding_count':len(report['findings']),'bookkeeping_outcome':report['bookkeeping_outcome'],'errors':report['errors'],'warnings':report['warnings'],'formal_closure_or_runtime_acceptance':report['formal_closure_or_runtime_acceptance']})
reconcile.ordered_receipts=original
unaltered=json.loads((ROOT/'unaltered-reconciliation.json').read_text())
fault=json.loads((ROOT/'remove-B37-reconciliation.json').read_text())
assert runs[0]['exit_code']==0 and len(unaltered['findings'])==60 and not unaltered['errors']
assert unaltered==json.loads((coordinated/'reconciliation.json').read_text())
assert runs[1]['exit_code']!=0 and fault['bookkeeping_outcome']=='FAIL'
partition=[row for row in fault['errors'] if row['kind']=='finding_partition_failure']
assert len(partition)==1 and partition[0]=={'kind':'finding_partition_failure','missing_ids':['B37'],'foreign_ids':[],'overlaps':{}}
assert len(fault['findings'])==59
assert len({row['canonical_bundle'] for row in fault['findings']})==24
assert fault['formal_closure_or_runtime_acceptance']=='not_established_by_this_metadata_join'
# Check the actual rich overlay rows rather than the short class bucket.
exe_head=unaltered['families']['exe']['head']
exe_path=b_inputs.RECEIPT_ROOT+'/exe-cold-seed.json'
exe_doc=b_inputs.read_json(exe_head,exe_path)
rich=dict((fid,row) for fid,_,row in b_inputs.disposition_rows(exe_doc))
assert set(rich)=={'B52','B60'}
for fid in ['B52','B60']:
    effective=next(row for row in unaltered['findings'] if row['finding_id']==fid)
    assert effective['effective_disposition']==rich[fid]
    assert effective['priority']==1 and effective['source_receipt']==exe_path+'@'+exe_head
cas=[row for row in unaltered['findings'] if row['family']=='cas']
assert len(cas)==8 and all(row['priority']==1 and 'cas-archive-output-entry.json@' in row['source_receipt'] for row in cas)
assert all('cas.json@' not in str(row) for row in cas)
assert unaltered['warnings']==[{'kind':'advertised_bundle_scope_mismatch','family':'cas','missing_advertised_bundles':['CAS-01','CAS-03'],'extra_advertised_bundles':[],'note':'Criterion-owner join is explicit; never treat closure_ids as scope.'}]
# Run only the preparer, retaining exact pins/overlays and source SHA; no runtime execution.
argv=[commands['commands'][1]['argv'][0],str(TOOLS/'prepare_native_cohort.py'),*commands['commands'][1]['argv'][2:]]
argv[argv.index('--output')+1]=str(ROOT/'independent-cohort.json')
prepared=subprocess.run(argv,text=True,capture_output=True)
(ROOT/'prepare-stdout.txt').write_text(prepared.stdout)
(ROOT/'prepare-stderr.txt').write_text(prepared.stderr)
cohort=json.loads((ROOT/'independent-cohort.json').read_text())
assert prepared.returncode==0 and cohort==json.loads((coordinated/'cohort.json').read_text())
assert cohort['whole_file_count']==74 and len(cohort['native_waves'])==12
assert cohort['ready_at_final_head'] and cohort['no_test_execution_performed_by_preparer']
assert len(cohort['explicit_final_source_points'])==6
assert not cohort['final_missing_files'] and not cohort['final_mismatching_files']
run_wave=[row for row in cohort['native_waves'] if row['family']=='run']
assert len(run_wave)==1 and run_wave[0]['file_count']==4
run_doc=b_inputs.read_json(cohort['family_heads']['run'],b_inputs.RECEIPT_ROOT+'/run.json')
run_checks=[row for row in run_doc['checks'] if row.get('target_sha')==run_wave[0]['observed_target_sha'] and row.get('command')==run_wave[0]['source_command']]
assert len(run_checks)==1 and '125 passed' in run_checks[0]['output']
summary={'schema':'policyos.e02.B_metadata_utility_review.v1','tool_source_sha':'75f7648864f541757ba443828f94d6cdf80cc30c','final_head':cohort['final_head'],'final_tree':cohort['final_tree'],'runtime_execution_performed':False,'process_worktrees_created':False,'outcome':'PASS_bounded_metadata_control','original_outputs_equal_root_pre_freeze':True,'mutation':mutation[0],'runs':runs,'cohort':{'argv':argv,'exit_code':prepared.returncode,'stdout':prepared.stdout,'whole_file_count':cohort['whole_file_count'],'source_waves':len(cohort['native_waves']),'ready_at_final_head':cohort['ready_at_final_head'],'source_pins':cohort['explicit_final_source_points'],'unconfirmed_source_pins':cohort['source_points_unconfirmed_in_explicit_receipts']},'row_priority_control':{'actual_exe_overlay_ids':sorted(rich),'effective_rich_rows_equal':True,'cas_overlay_ids':[row['finding_id'] for row in cas],'all_8_preserved':True,'original_cas_receipt_excluded':True},'limits':['metadata join/preparation only, no runtime or formal finding closure','final head is pre-freeze; source follow-up and final preparation/run remain root/G responsibility','test blob readiness does not independently attest production semantics']}
(ROOT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'outcome':summary['outcome'],'original_join':runs[0]['bookkeeping_outcome'],'original_findings':60,'negative_join':runs[1]['bookkeeping_outcome'],'negative_findings':59,'negative_errors':fault['errors'],'whole_native_files':74,'waves':12,'ready_at_pre_freeze':True,'runtime_execution_performed':False,'artifact_root':str(ROOT)},ensure_ascii=False,indent=2))
