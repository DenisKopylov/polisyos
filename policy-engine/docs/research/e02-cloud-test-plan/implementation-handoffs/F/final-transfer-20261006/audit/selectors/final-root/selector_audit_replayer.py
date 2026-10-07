from pathlib import Path
import argparse,ast,hashlib,json,re,shlex,subprocess
parser=argparse.ArgumentParser();parser.add_argument('--repo',default='/workspace/polisyos');parser.add_argument('--scratch',default='/workspace/e02-F-20261006-receipts/final-root');args=parser.parse_args();repo=Path(args.repo);base='198076863e143dea9f89f02734b13d50dae3eed5';scratch=Path(args.scratch);out=scratch/'selector-audit-navigation.json';snapshot=json.loads((scratch/'selector-audit-owner-snapshot.json').read_text())
coverage_path='policy-engine/docs/research/e02-cloud-test-plan/closure-decisions/coverage.json';manifest_path='policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundle_manifest.json'
def git(*a):return subprocess.check_output(['git',*a],cwd=repo)
def read(ref,path):
 p=subprocess.run(['git','show',ref+':'+path],cwd=repo,capture_output=True);return p.stdout if p.returncode==0 else None
def binding(ref,path):
 b=read(ref,path)
 if b is None:return {'path':path,'present':False,'source_sha':ref}
 return {'path':path,'present':True,'source_sha':ref,'git_blob':git('rev-parse',ref+':'+path).decode().strip(),'sha256':hashlib.sha256(b).hexdigest(),'bytes':len(b)}
cov=json.loads(read(base,coverage_path));man=json.loads(read(base,manifest_path));expected=[b['id'] for b in cov['bundles'] if b['unit']=='F'];assert len(expected)==17
owners={
 'API-01':('/workspace/e02-F-api-20261006','api-20261006'),
 'CAU-01':('/workspace/e02-F-cau-20261006','did-selected-cohort-20261006'),
 'CAU-02':('/workspace/e02-F-cau-20261006','did-selected-cohort-20261006'),
 'CAU-05':('/workspace/e02-F-cau-20261006','did-selected-cohort-20261006'),
 'CAU-03':('/workspace/e02-F-rdd-20261006','rdd-sharp-rbc-20261006'),
 'CAU-04':('/workspace/e02-F-dowhy-20261006','dowhy-worker-20261006'),
 'ECO-01':('/workspace/e02-F-economics-20261006','economic-science-profiles-20261006'),
 'FRY-03':('/workspace/e02-F-economics-20261006','economic-science-profiles-20261006'),
 'FRY-01':('/workspace/e02-F-fry-20261006','treasury-execution-20261006'),
 'FIT-01':('/workspace/e02-F-tmle-20261006','tmle-20261006'),
 'LEX-01':('/workspace/e02-F-lex-20261006','lex-pass-plan-20261006'),
 **{x:('/workspace/e02-F-graph-20261006','scm-source-bound-20261006') for x in ['GRF-01','GRF-02','GRF-03','SCM-01','SCM-02','SCM-03']}}
rows=[];blocks=[]
for id in sorted(expected):
 b=next(b for b in man['bundles'] if b['id']==id);cp='policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/'+b['artifact_path'];card=read(base,cp).decode();cardsource=binding(base,cp)
 for match in re.finditer(r'<!-- SOURCE_BEGIN (B|LA):([^ ]+) -->\n(.*?)<!-- SOURCE_END \1:\2 -->',card,re.S):blocks.append({'bundle':id,'id':match[2],'body_sha256':hashlib.sha256(match[3].encode()).hexdigest(),'body_bytes':len(match[3].encode()),'card_ref':cardsource})
 wd,slice=owners[id];head=snapshot['owner_receipt_heads'][id];hp='policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/F/'+slice+'.json';h=json.loads(read(head,hp));commits=h.get('implementation_commits',[]);impl=h.get('implementation_sha') or commits[-1];tree=git('rev-parse',impl+'^{tree}').decode().strip();assert tree==h['candidate_tree_sha'],(id,impl,tree,h['candidate_tree_sha'])
 actual=[]
 handoffs=[(hp,h)]
 if id.startswith(('GRF','SCM')):
  secondary='policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/F/graph-native-20261006.json'
  handoffs.append((secondary,json.loads(read(head,secondary))))
 combined=[(path,index,c) for path,hh in handoffs for index,c in enumerate(hh.get('checks',[]))]
 for receipt_path,index,c in combined:
  cmd=c.get('command',[]);text=' '.join(str(p) for p in cmd) if isinstance(cmd,list) else str(cmd)
  if 'pytest' not in text and not any(k in text for k in ['final_launch.py','installed_launch.py']):continue
  selectors=sorted(set(re.findall(r'(?:policy-engine/)?tests/[A-Za-z0-9_./-]+\.py(?:::[A-Za-z0-9_]+)*',text)))
  for sel in selectors:
   path=sel.split('::')[0];path=path if path.startswith('policy-engine/') else 'policy-engine/'+path
   if 'workers/dowhy' in text and path=='policy-engine/tests/test_worker.py':path='policy-engine/workers/dowhy-014/tests/test_worker.py'
   target=c.get('target_sha') or impl
   target_valid=bool(re.fullmatch(r'[0-9a-f]{40}',str(target)))
   target_input_basis='explicit_per_check_sha' if c.get('target_sha') else 'owner_receipt_candidate_header'
   if not target_valid:target=str(target)
   file=binding(impl,path);tested=binding(target,path);same=file.get('sha256')==tested.get('sha256') and file['present'] and tested['present']
   actual.append({'selector':sel,'path':path,'check_receipt':binding(head,receipt_path),'check_index':index,'target_input_basis':target_input_basis,'outcome':c.get('outcome'),'original_target_sha':c.get('target_sha'),'resolved_tested_tree':target,'candidate_test_file':file,'tested_test_file':tested,'candidate_test_bytes_match_tested':same,'command':cmd,'output':c.get('output')})
 paths=[]
 for path in b['test_paths']:
  cb=binding(impl,path);baseb=binding(base,path);full=read(impl,path)
  functions=[]
  if full:
   tree_ast=ast.parse(full)
   functions=[{'name':n.name,'line':n.lineno,'end_line':n.end_lineno,'function_sha256':hashlib.sha256(ast.get_source_segment(full.decode(),n).encode()).hexdigest()} for n in ast.walk(tree_ast) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name.startswith('test_')]
  matches=[a for a in actual if a['path']==path];paths.append({'declared_selector':path,'main198':baseb,'candidate':cb,'test_functions':functions,'actual_handoff_selector_receipts':matches})
 rows.append({'bundle':id,'finding_ids':next(x['finding_ids'] for x in cov['bundles'] if x['id']==id),'manifest_test_paths':b['test_paths'],'manifest_source_test_refs':b.get('source_test_refs',[]),'manifest_tests':b['tests'],'card':cardsource,'owner_branch':h['branch'],'owner_receipt_head':head,'owner_receipt':binding(head,hp),'candidate_implementation':impl,'candidate_tree':tree,'declared_test_paths':paths,'actual_tested_selectors':actual})
result={'schema':'policyos.e02.selector_equivalence_audit.navigation.v1','base':base,'coverage':binding(base,coverage_path),'manifest':binding(base,manifest_path),'denominator':{'expected_bundles':17,'finding_unique':len({id for r in rows for id in r['finding_ids']}),'original_source_card_blocks':len(blocks),'blocks_unique':len({x['id'] for x in blocks})},'source_card_blocks':blocks,'coverage_missing_test_paths':{'count':sum('test_paths' not in b for b in cov['bundles'] if b['unit']=='F'),'documented_generator_outcome':'ERROR','reason':"verification-and-closeout documented command b['test_paths'] raises KeyError; canonical manifest supplies declared proposed selectors. No tracked input rewrite."},'bundles':rows}
out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'denominator':result['denominator'],'declared_selectors':sum(len(r['declared_test_paths']) for r in rows),'missing':{r['bundle']:[p['declared_selector'] for p in r['declared_test_paths'] if not p['candidate']['present']] for r in rows if any(not p['candidate']['present'] for p in r['declared_test_paths'])},'navigation':str(out)},indent=2))
