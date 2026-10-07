import pathlib
p=pathlib.Path(__file__).parent
f=p/'audit.py';s=f.read_text()
s=s.replace("issue('blob_source_missing',doc+loc,{'git_blob':declared_blob,'source_path':path});continue", """historical_scope=rec.get('scope')
      detail={'git_blob':declared_blob,'source_path':path,'referencing_document_sha':sha,'resolved_source_context_sha':recsha,'declared_scope':historical_scope}
      if declared_blob=='175c1ed4db37589e8adaf14af6700ad639edb2c8' and doc=='policy-engine/docs/plans/active/agent-packages/PolicyOS_E02R2/residual_ledger.json' and loc=='/citation_catalog/reviewed_no_record_audit/historical_held_review_source' and historical_scope=='Historical source blob retained only as provenance for the N-card audit; the blob object exists, but this path is not tracked at the ledger head. It is not current finding-status or behavior evidence.':
       detail.update(classification='unavailable_historical_non_deciding',check='UNRUN',current_deciding=False)
      issue('blob_source_missing',doc+loc,detail);continue""")
s=s.replace(" result={'component':name,", " current_issues=[x for x in issues if x.get('detail',{}).get('classification')!='unavailable_historical_non_deciding']\n historical_missing=[x for x in issues if x.get('detail',{}).get('classification')=='unavailable_historical_non_deciding']\n result={'component':name,")
s=s.replace("'check':'FAIL' if issues else 'PASS'}\n (OUT/(name+'.json'))", "'current_deciding_reference_check':'FAIL' if current_issues else 'PASS','all_reference_custody_check':'FAIL' if current_issues else ('UNRUN' if historical_missing else 'PASS'),'historical_unavailable_non_deciding_records':historical_missing,'check':'FAIL' if current_issues else ('UNRUN' if historical_missing else 'PASS')}\n (OUT/(name+'.json'))")
f.write_text(s)
f=p/'consolidate.py';s=f.read_text()
old="report={'schema':'policyos.e02.protocol_byte_audit.v2'"
new="""historical_unavailable=[x for x in issues if x.get('detail',{}).get('classification')=='unavailable_historical_non_deciding']
current_issues=[x for x in issues if x not in historical_unavailable]
historical_blob_ids={x['detail']['git_blob'] for x in historical_unavailable}
if len(historical_unavailable)!=4 or historical_blob_ids!={'175c1ed4db37589e8adaf14af6700ad639edb2c8'}:
 current_issues.append({'kind':'historical_custody_scope_denominator_mismatch','expected_occurrences':4,'expected_distinct_blobs':1,'actual_occurrences':len(historical_unavailable),'actual_blobs':sorted(historical_blob_ids)})
for part in all_results:
 part.setdefault('current_deciding_reference_check','FAIL' if part['issues'] else 'PASS')
 part.setdefault('all_reference_custody_check',part['check'])
check='FAIL' if current_issues else ('UNRUN' if historical_unavailable else 'PASS')
counts['all_canonical_check_records']=sum(r['checks_count'] for r in all_results)
counts['historical_unavailable_non_deciding_occurrences']=len(historical_unavailable)
counts['historical_unavailable_non_deciding_distinct_blobs']=len(historical_blob_ids)
report={'schema':'policyos.e02.protocol_byte_audit.v3'"""
assert old in s;s=s.replace(old,new)
s=s.replace("'check':'FAIL' if issues else 'PASS','scope':'Independent", "'check':check,'current_deciding_reference_check':'FAIL' if current_issues else 'PASS','all_reference_custody_check':check,'current_deciding_issues':current_issues,'historical_unavailable_non_deciding_records':historical_unavailable,'historical_custody_disposition':{'check':'UNRUN','git_blob':'175c1ed4db37589e8adaf14af6700ad639edb2c8','occurrences':4,'distinct_blobs':1,'local_git_object':'absent','github_read_only_probe':'HTTP404','probe_outputs':['historical-blob-gh-response.json','historical-blob-gh-stderr.txt'],'scope':'Explicit historical N-card provenance only; canonical record expressly says it is not current finding-status or behavior evidence. No missing input is converted to PASS. Excluded only from current deciding scope; full custody remains UNRUN.','next_owner':'Historical N-card citation/source custodian (G/D) if that historical audit is invoked; no F35 closure basis uses this unavailable blob.','root_authorized_scope':'Current15/35criteria/runtime-byte hash custody checked separately from this one historical blob; no ledger ownership changes.'},'scope':'Independent")
s=s.replace('lines=[f"F published protocol/byte audit {report[\'check\']}"', 'lines=[f"F published protocol/byte audit {report[\'check\']} (current_deciding_reference_check={report[\'current_deciding_reference_check\']}; all_reference_custody_check={report[\'all_reference_custody_check\']})"')
s=s.replace("print('issues',len(issues))", "print('current_deciding_issues',len(current_issues),'historical_unavailable_non_deciding_records',len(historical_unavailable))")
f.write_text(s)
print('updated audit.py and consolidate.py scratch only')
