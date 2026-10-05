import csv, hashlib, json, pathlib, shlex, subprocess, datetime
ROOT=pathlib.Path('/workspace/e02-B-dur-ledger')
OUT=pathlib.Path(__file__).parent
PREFIX='policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/B/'
LANES={'run':'e02-B-run','exe':'e02-B-exe-state','dur':'e02-B-dur-ledger','cmp':'e02-B-cmp-res','cas':'e02-B-cas','adapters':'e02-B-adapters'}
EXPECTED={'run':8,'exe':15,'dur':3,'cmp':11,'cas':8,'adapters':15}
MANDATORY=['schema','unit','slice','closure_ids','bundle_ids','slice_base_sha','implementation_commits','candidate_tree_sha','branch','pull_request','changed_paths','baseline_cells','checks','property','predicate_basis','capability_state_or_finding_state','limitations_and_next_owner']
def git(wt,*args):
 return subprocess.run(['git','-C',str(wt),*args],capture_output=True)
def blob(wt,sha,path):
 return git(wt,'show',sha+':'+path)
def rows(path):
 with path.open() as h:return list(csv.DictReader(h,delimiter='\t'))
pack=ROOT/'policy-engine/docs/research/e02-cloud-test-plan'
findings=[x for x in rows(pack/'execution-organization/finding-owners.tsv') if x['unit']=='B']
bundles=[x for x in rows(pack/'execution-organization/bundle-owners.tsv') if x['unit']=='B']
assignment={k:[] for k in LANES}
for x in findings:
 b=x['source_bundle_ids']
 lane='run' if 'RUN-' in b else 'dur' if 'DUR-' in b else 'cas' if 'CAS-' in b else 'cmp' if any(s in b for s in ['CMP-','RES-03','RES-04']) else 'exe' if any(s in b for s in ['EXE-','STA-','RES-01','RES-02']) else 'adapters'
 assignment[lane].append(x['finding_id'])
cells={x['id']:x for x in rows(pack/'results/cells.tsv')};routes=rows(pack/'results/routes.tsv')
audit={'schema':'policyos.e02.B.receipt_audit.v1','read_only_author_receipts':True,'generated_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'denominator':{'bundle_count':len(bundles),'finding_count':len(findings),'assignment_counts':{k:len(v) for k,v in assignment.items()},'expected_counts_match':{k:len(v)==EXPECTED[k] for k,v in assignment.items()},'findings':assignment},'lanes':[],'blocking_mismatches':[],'limits':['Metadata/deciding-byte custody audit; runtime/source independent acceptance remains separate.','Absent receipts are pending while authors finish; no defect inferred.','Ignored raw not transferred is accepted only as bounded not_established evidence with disclosed exact rerun.']}
for lane,worktree in LANES.items():
 wt=pathlib.Path('/workspace')/worktree;head=git(wt,'rev-parse','HEAD').stdout.decode().strip();branch=git(wt,'branch','--show-current').stdout.decode().strip()
 files=git(wt,'ls-tree','-r','--name-only',head,PREFIX).stdout.decode().splitlines();ps=[p for p in files if p.endswith('.json') and '/' not in p[len(PREFIX):]]
 lr={'lane':lane,'worktree':str(wt),'frozen_head':head,'branch':branch,'assigned_findings':assignment[lane],'expected_baseline_cells':sorted({x['cell_id'] for x in routes if x['finding_id'] in assignment[lane]}),'receipts':[]}
 seen=set();disps=set()
 for path in ps:
  bb=blob(wt,head,path);d=json.loads(bb.stdout)
  if d.get('schema')!='policyos.e02.implementation_handoff.v1':
   if 'implementation_handoff' in str(d.get('schema')):
    rc=git(wt,'log','-1','--format=%H',head,'--',path).stdout.decode().strip()
    issue={'code':'IMPLEMENTATION_HANDOFF_SCHEMA','observed_schema':d.get('schema'),'expected_schema':'policyos.e02.implementation_handoff.v1','missing_fields':[k for k in MANDATORY if k not in d]}
    check_missing=[{'check':i,'missing_fields':[k for k in ['command','target_sha','environment','input_closure','outcome','output'] if k not in c]} for i,c in enumerate(d.get('checks',[]))]
    rr={'path':path,'receipt_commit':rc,'receipt_sha256':hashlib.sha256(bb.stdout).hexdigest(),'slice':d.get('slice'),'implementation_commits':[],'candidate_tree_sha':None,'base_ancestor':None,'tree_matches':None,'split_implementation_receipt':None,'changed_paths_missing':[],'changed_paths_extra':[],'property_missing_fields':['statement','runtime_path','proxy_divergence','negative_controls'],'forbidden_shared_paths':[],'checks':[],'source_cells':[],'issues':[issue],'verdict':'correction_required','check_binding_missing':check_missing}
    lr['receipts'].append(rr);audit['blocking_mismatches'].append({'lane':lane,'receipt_commit':rc,'slice':d.get('slice'),**issue,'check_binding_missing':check_missing})
   continue
  rc=git(wt,'log','-1','--format=%H',head,'--',path).stdout.decode().strip()
  rr={'path':path,'receipt_commit':rc,'receipt_sha256':hashlib.sha256(bb.stdout).hexdigest(),'slice':d['slice'],'implementation_commits':d['implementation_commits'],'candidate_tree_sha':d['candidate_tree_sha'],'missing_required_fields':[k for k in MANDATORY if k not in d],'checks':[],'source_cells':[],'issues':[],'state':d.get('capability_state_or_finding_state'),'limitations':d.get('limitations_and_next_owner')}
  if rr['missing_required_fields']:rr['issues'].append({'code':'REQUIRED_FIELDS','fields':rr['missing_required_fields']})
  rr['property_missing_fields']=[k for k in ['statement','runtime_path','proxy_divergence','negative_controls'] if k not in d.get('property',{})]
  if rr['property_missing_fields']:rr['issues'].append({'code':'PROPERTY_SCHEMA','missing_fields':rr['property_missing_fields']})
  rr['forbidden_shared_paths']=[p for p in d['changed_paths'] if p.endswith('/generation_cycle.py') or p.endswith('/run_lifecycle.py') or p.endswith('/streaming.py')]
  last=d['implementation_commits'][-1]
  rr['base_ancestor']=git(wt,'merge-base','--is-ancestor',d['slice_base_sha'],last).returncode==0
  rr['implementation_ancestry']=[{'commit':c,'ancestor_of_receipt':git(wt,'merge-base','--is-ancestor',c,rc).returncode==0} for c in d['implementation_commits']]
  rr['tree_matches']=git(wt,'rev-parse',last+'^{tree}').stdout.decode().strip()==d['candidate_tree_sha']
  rr['split_implementation_receipt']=rc not in d['implementation_commits'] and git(wt,'merge-base','--is-ancestor',last,rc).returncode==0 and bool(git(wt,'diff',last,rc,'--',path).stdout)
  for field in ['base_ancestor','tree_matches','split_implementation_receipt']:
   if not rr[field]:rr['issues'].append({'code':'GIT_BINDING','field':field})
  if any(not x['ancestor_of_receipt'] for x in rr['implementation_ancestry']):rr['issues'].append({'code':'IMPLEMENTATION_ANCESTRY'})
  if rr['forbidden_shared_paths']:rr['issues'].append({'code':'LEASE_PATH','paths':rr['forbidden_shared_paths']})
  rr['receipt_commit_paths']=git(wt,'show','--format=','--name-only',rc).stdout.decode().splitlines()
  actual=git(wt,'diff','--name-only',d['slice_base_sha'],last).stdout.decode().splitlines();rr['actual_base_candidate_paths']=actual
  rr['changed_paths_missing']=sorted(set(actual)-set(d['changed_paths']));rr['changed_paths_extra']=sorted(set(d['changed_paths'])-set(actual))
  if rr['changed_paths_missing'] or rr['changed_paths_extra']:rr['issues'].append({'code':'FOOTPRINT','missing':rr['changed_paths_missing'],'extra':rr['changed_paths_extra']})
  for i,c in enumerate(d.get('checks',[])):
   ck={'index':i,'target_sha':c.get('target_sha'),'outcome':c.get('outcome'),'missing_fields':[k for k in ['command','target_sha','environment','input_closure','outcome','output'] if k not in c]}
   ck['target_object_exists']=git(wt,'cat-file','-e',str(c.get('target_sha'))+'^{commit}').returncode==0
   ck['environment_present']=bool(c.get('environment'));ck['input_closure_present']=bool(c.get('input_closure'))
   env_source=c.get('environment',{}).get('source_ref') if isinstance(c.get('environment'),dict) else None
   if isinstance(env_source,str) and len(env_source)==40 and env_source!=c.get('target_sha'):
    rr['issues'].append({'code':'ENVIRONMENT_SOURCE_IDENTITY','check':i,'environment_source_ref':env_source,'check_target_sha':c.get('target_sha'),'detail':'Unqualified environment source snapshot differs from executed check target; explicitly name final snapshot custody or bind actual executed source.'})
   env=c.get('environment',{})
   if isinstance(env,dict):
    for module,origin in env.get('module_origins',{}).items():
     if isinstance(origin,dict) and origin.get('sha256') and isinstance(origin.get('path'),str) and origin['path'].startswith(str(wt)+'/policy-engine/src/'):
      source_path=origin['path'][len(str(wt))+1:];source_blob=blob(wt,str(c.get('target_sha')),source_path)
      actual_hash=hashlib.sha256(source_blob.stdout).hexdigest()
      if source_blob.returncode or origin['sha256']!=actual_hash:rr['issues'].append({'code':'EXECUTED_MODULE_HASH','check':i,'module':module,'source_path':source_path,'target_sha':c.get('target_sha'),'declared':origin['sha256'],'git_source_sha256':actual_hash,'detail':'Executed module file hash must match actual check target; final custody snapshots need explicit separate labels.'})
   out=c.get('output');fp=out.get('path') if isinstance(out,dict) else out if isinstance(out,str) and out.startswith('policy-engine/') and '\n' not in out else None
   if fp:
    ob=blob(wt,head,fp);ck['output_path']=fp;ck['output_committed']=ob.returncode==0;ck['output_sha256']=hashlib.sha256(ob.stdout).hexdigest();ck['output_bytes']=len(ob.stdout)
    expect=out.get('sha256') if isinstance(out,dict) else c.get('output_sha256') or (c.get('input_closure',{}).get('log_sha256') if isinstance(c.get('input_closure'),dict) else None)
    ck['declared_hash']=expect;ck['hash_matches']=ck['output_sha256']==expect if expect else None
    if not ck['output_committed'] or ck['hash_matches'] is False:rr['issues'].append({'code':'OUTPUT_CUSTODY','check':i,'path':fp})
   else:ck['inline_output_sha256']=hashlib.sha256(str(out).encode()).hexdigest()
   try:
    command=c.get('command','');parsed=shlex.split(command) if isinstance(command,str) else command
    groups=parsed if parsed and isinstance(parsed[0],list) else [parsed]
    cwd=c.get('cwd') or (c.get('environment',{}).get('cwd') if isinstance(c.get('environment'),dict) else None)
    for tokens in groups:
     if '-c' in tokens and ('-m' not in tokens or tokens.index('-c')<tokens.index('-m')):compile(tokens[tokens.index('-c')+1],'receipt-command','exec')
     if cwd and '-c' not in tokens:
      for token in tokens:
       if isinstance(token,str) and token.endswith('.py') and token.startswith('policy-engine/') and str(cwd).endswith('/policy-engine'):
        rr['issues'].append({'code':'REPLAY_CWD','check':i,'command_path':token,'declared_cwd':cwd})
   except (SyntaxError,ValueError) as e:rr['issues'].append({'code':'REPLAY_COMMAND','check':i,'error':str(e)})
   if ck['missing_fields'] or not ck['target_object_exists'] or not ck['environment_present'] or not ck['input_closure_present']:
    rr['issues'].append({'code':'CHECK_BINDING','check':i,'missing_fields':ck['missing_fields'],'target_object_exists':ck['target_object_exists'],'environment_present':ck['environment_present'],'input_closure_present':ck['input_closure_present']})
   rr['checks'].append(ck)
  baseline_items=[]
  for item in d.get('baseline_cells',[]):
   if isinstance(item,dict) and item.get('reference'):
    path_ref,source_ref=item['reference'].rsplit('@',1);nav_blob=blob(wt,source_ref,path_ref)
    if nav_blob.returncode==0:
     nav=json.loads(nav_blob.stdout);resolved=nav.get('cells',[])
     rr.setdefault('baseline_locator_resolutions',[]).append({'reference':item['reference'],'blob_sha256':hashlib.sha256(nav_blob.stdout).hexdigest(),'cells':len(resolved),'expected':item.get('complete_denominator'),'matching_declared_denominator':len(resolved)==item.get('complete_denominator')})
     if len(resolved)!=item.get('complete_denominator'):rr['issues'].append({'code':'BASELINE_LOCATOR_DENOMINATOR'})
     baseline_items.extend(resolved)
    else:rr['issues'].append({'code':'BASELINE_LOCATOR_UNRESOLVED','reference':item['reference']})
   else:baseline_items.append(item)
  for c in baseline_items:
   cid=c if isinstance(c,str) else c.get('id') or c.get('cell_id');c={} if isinstance(c,str) else c;seen.add(cid);source=cells.get(cid);errs=[]
   if source:
    for k in ['source_sha','path','job','state','receipt_status','source_file','source_line']:
     if k in c and str(c[k])!=str(source[k]):errs.append(k)
    if c.get('reported_state') and c['reported_state']!=source['state']:errs.append('reported_state')
    refs=c.get('source_ref');refs=refs if isinstance(refs,list) else [refs] if refs else []
    if not set(refs).issubset({x['source_ref'] for x in routes if x['cell_id']==cid}):errs.append('source_ref')
   else:errs.append('unknown_cell')
   rr['source_cells'].append({'id':cid,'identity_matches':not errs,'mismatches':errs})
  if any(not x['identity_matches'] for x in rr['source_cells']):rr['issues'].append({'code':'BASELINE_CELL_IDENTITY','cells':[x for x in rr['source_cells'] if not x['identity_matches']]})
  for disp in d.get('finding_dispositions',d.get('finding_classification',[])):disps.add(disp.get('finding_id') or disp.get('id'))
  denom=d.get('baseline_denominator',{})
  if denom.get('complete_unique_routed_cells_resolved')==len(lr['expected_baseline_cells']) and 'routes.tsv@'+d['slice_base_sha'] in str(denom.get('source_refs')):
   rr['full_baseline_resolved_via_pinned_tsv']=True;seen.update(lr['expected_baseline_cells'])
  if lane=='cas' and rc=='36bc2f72f8cc8dab5c1aa2a51740f5945b1143f6':
   rr['issues'].extend([{'code':'BASE_OVERLAY_IDENTITY','check':1,'detail':'test_transfer_publication.py is absent on c40; input_closure says tracked tests at c40 while notes say overlay without immutable SHA/hash.'},{'code':'REMOVAL_DRIVER_IDENTITY','check':4,'detail':'Isolated source mutation is named but no exact committed driver/patch/bytes identity is provided for reproduction.'}])
  if lane=='dur' and rc=='2452879b07672aeb8cce4f0369f18ac6c0d793f2':rr['issues'].append({'code':'INPUT_CLOSURE','check':1,'detail':'Temporary SQLite worker/acquisition state and FallbackWorkflowRunner are actual inputs; copied ledger/no-DB prose is false. Correction staged and normal checkout hook dependency pending.'})
  rr['nested_artifacts']=[]
  def artifact_walk(value,location):
   if isinstance(value,dict):
    if isinstance(value.get('path'),str) and value['path'].startswith('policy-engine/') and value.get('sha256') and '@' not in value['path']:
     artifact=blob(wt,head,value['path']);observed=hashlib.sha256(artifact.stdout).hexdigest()
     declared_untransferred=value.get('available_in_git') is False or any(word in str(value.get('transfer','')).lower() for word in ['not transferred','ignored'])
     check={'declared_untransferred':declared_untransferred,'location':location,'path':value['path'],'committed':artifact.returncode==0,'sha256_matches':observed==value['sha256'],'bytes_matches':len(artifact.stdout)==value['bytes'] if 'bytes' in value else None}
     rr['nested_artifacts'].append(check)
     if not declared_untransferred and (not check['committed'] or not check['sha256_matches'] or check['bytes_matches'] is False):rr['issues'].append({'code':'NESTED_ARTIFACT_CUSTODY',**check})
    for key,nested in value.items():artifact_walk(nested,location+'.'+key)
   elif isinstance(value,list):
    for index,nested in enumerate(value):artifact_walk(nested,location+'['+str(index)+']')
  artifact_walk(d,'$')
  rr['verdict']='correction_required' if rr['issues'] else 'metadata_custody_pass_bounded'
  for issue in rr['issues']:audit['blocking_mismatches'].append({'lane':lane,'receipt_commit':rc,'slice':d['slice'],**issue})
  lr['receipts'].append(rr)
 lr['baseline_cells_union']=sorted(seen);lr['baseline_cells_missing']=sorted(set(lr['expected_baseline_cells'])-seen);lr['finding_dispositions_present']=sorted(disps);lr['finding_dispositions_missing']=sorted(set(assignment[lane])-disps)
 lr['finding_dispositions_unexpected']=sorted(disps-set(assignment[lane]))
 if lr['finding_dispositions_missing'] or lr['baseline_cells_missing'] or lr['finding_dispositions_unexpected']:
  audit['blocking_mismatches'].append({'lane':lane,'code':'DENOMINATOR','missing_findings':lr['finding_dispositions_missing'],'missing_cells':lr['baseline_cells_missing'],'unexpected_findings':lr['finding_dispositions_unexpected']})
 lr['verdict']='pending_receipt' if not lr['receipts'] else 'correction_required' if any(x['issues'] for x in lr['receipts']) else 'metadata_custody_pass_bounded'
 audit['lanes'].append(lr)
audit['overall_verdict']='partial_audit_corrections_and_pending' if audit['blocking_mismatches'] or any(x['verdict']=='pending_receipt' for x in audit['lanes']) else 'metadata_custody_pass_bounded'
fp=OUT/'receipt-audit.json';fp.write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'path':str(fp),'sha256':hashlib.sha256(fp.read_bytes()).hexdigest(),'denominator':audit['denominator']['assignment_counts'],'lanes':[{k:x[k] for k in ['lane','frozen_head','verdict','finding_dispositions_missing','baseline_cells_missing']} for x in audit['lanes']],'blocking_mismatches':audit['blocking_mismatches']},ensure_ascii=False))
