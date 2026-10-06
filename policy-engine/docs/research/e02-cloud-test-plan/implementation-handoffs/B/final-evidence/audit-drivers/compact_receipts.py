import json,pathlib,subprocess,hashlib,datetime
p=pathlib.Path(__file__).parent;d=json.loads((p/'receipt-audit.json').read_text())
refs=['refs/heads/'+x['branch'] for x in d['lanes']];remote=subprocess.check_output(['git','-C','/workspace/e02-B-dur-ledger','ls-remote','origin',*refs]).decode().splitlines();heads={line.split()[1]:line.split()[0] for line in remote}
for l in d['lanes']:
 wt=l['worktree'];l['remote_head_verified']=heads.get('refs/heads/'+l['branch'])==l['frozen_head'];l['remote_head']=heads.get('refs/heads/'+l['branch'])
 impls=[c for r in l['receipts'] for c in r['implementation_commits']]
 newest=max(impls,key=lambda c:int(subprocess.check_output(['git','-C',wt,'show','-s','--format=%ct',c]))) if impls else None
 delta=subprocess.check_output(['git','-C',wt,'diff','--name-only',newest,l['frozen_head']]).decode().splitlines() if newest else []
 l['newer_unreceipted_implementation_paths']=[x for x in delta if not x.startswith('policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/')]
 if l['newer_unreceipted_implementation_paths']:l['verdict']='pending_new_slice_receipt' if not any(r['issues'] for r in l['receipts']) else 'pending_new_slice_receipt_and_prior_corrections'
compact={'schema':d['schema'],'generated_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'denominator':{'bundle_count':d['denominator']['bundle_count'],'finding_count':d['denominator']['finding_count'],'assignment_counts':d['denominator']['assignment_counts'],'assignment_count_match':all(d['denominator']['expected_counts_match'].values()),'distinct_findings':len({f for x in d['denominator']['findings'].values() for f in x})},'lanes':[],'blocking_mismatches':d['blocking_mismatches'],'limits':d['limits']}
for l in d['lanes']:
 x={k:l[k] for k in ['lane','frozen_head','remote_head','remote_head_verified','verdict','newer_unreceipted_implementation_paths']};x['finding_disposition_count']=len(l['finding_dispositions_present']);x['baseline_cell_count']=len(l['expected_baseline_cells']);x['missing_dispositions']=l['finding_dispositions_missing'];x['missing_baseline']=l['baseline_cells_missing'];x['receipts']=[]
 for r in l['receipts']:
  rr={k:r[k] for k in ['slice','receipt_commit','receipt_sha256','implementation_commits','candidate_tree_sha','base_ancestor','tree_matches','split_implementation_receipt','changed_paths_missing','changed_paths_extra','property_missing_fields','forbidden_shared_paths','verdict']};rr['checks_count']=len(r['checks']);rr['source_cell_identity_mismatches']=[c for c in r['source_cells'] if c['mismatches']];rr['deciding_logs']=[{k:c[k] for k in ['index','output_path','output_sha256','output_bytes','output_committed','hash_matches'] if k in c} for c in r['checks'] if 'output_path' in c];rr['check_identity_missing']=[c for c in r['checks'] if c['missing_fields'] or not c['target_object_exists'] or not c['environment_present'] or not c['input_closure_present']];x['receipts'].append(rr)
 compact['lanes'].append(x)
compact['overall_verdict']='metadata_custody_pass_bounded' if all(l['verdict']=='metadata_custody_pass_bounded' for l in compact['lanes']) else 'bounded_receipts_with_explicit_pending_or_corrections'
(p/'receipt-audit.json').write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n');fp=p/'receipt-audit-compact.json';fp.write_text(json.dumps(compact,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'path':str(fp),'bytes':fp.stat().st_size,'sha256':hashlib.sha256(fp.read_bytes()).hexdigest(),'overall':compact['overall_verdict'],'lanes':[{k:x[k] for k in ['lane','frozen_head','verdict','remote_head_verified']} for x in compact['lanes']],'blocking':compact['blocking_mismatches']},ensure_ascii=False))
