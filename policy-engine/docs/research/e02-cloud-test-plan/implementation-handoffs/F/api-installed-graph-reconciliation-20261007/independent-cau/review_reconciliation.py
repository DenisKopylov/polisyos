from __future__ import annotations
import ast,hashlib,json,pathlib,subprocess
P=pathlib.Path('/tmp/e02-F-continuation-20261007/cau/api-review');R='/workspace/e02-F-api-20261006'
F='6f39b0edc48ec59db3731fa917c615b9f97e4dc0';prod='8236d9c368336a5ea20c1586f29aea7321db6536';comp='3dde887e22592cdd7c1fe8865707afdfd72dc6fb';old='ab56a0f3414c6e903f7dcdaaa7b7ed540b1923c5'
git=lambda *args:subprocess.check_output(['git',*args],cwd=R)
bind=lambda p:{'path':str(p),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
a=json.loads(pathlib.Path('/tmp/e02-F-continuation-20261007/api/source-reconciliation.json').read_bytes());issues=[]
commits=git('rev-list','--reverse',old+'..'+comp).decode().splitlines();assert len(commits)==9;assert commits==[x['sha'] for x in a['all_nine_commit_deltas']]
actual=git('diff','--name-status',old,comp).decode().splitlines();expected=[x['status']+'\t'+x['path'] for x in a['complete_ab56_to_3dde_delta']];assert actual==expected and len(actual)==221
for row in a['contract_blob_delta_table']:
 for name,b in row['bindings'].items():
  ref=a['refs'][name]['sha'];p=row['path']
  if b['present']:
   raw=git('show',ref+':'+p);assert len(raw)==b['bytes'] and hashlib.sha256(raw).hexdigest()==b['sha256'];assert git('rev-parse',ref+':'+p).decode().strip()==b['oid']
  else:assert subprocess.run(['git','cat-file','-e',ref+':'+p],cwd=R,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode!=0
path='policy-engine/src/polisyos/ir/analytics/causal_graph.py';seen=set()
for ref in [old,*commits,prod]:seen.add(git('rev-parse',ref+':'+path).decode().strip())
assert seen==set(a['every_defining_IR_blob']['unique_blobs'])
canon=git('show',prod+':'+path);compraw=git('show',comp+':'+path)
assert ast.dump(ast.parse(canon),include_attributes=False)==ast.dump(ast.parse(compraw),include_attributes=False)
newpaths=git('diff','--name-only','90c72b51155321684c788cd5a03fbb70fc001d53',F).decode().splitlines();assert len(newpaths)==3 and not any('/src/' in x for x in newpaths)
for patch in a['full_product_patches']:
 f=pathlib.Path(patch['path']);assert len(f.read_bytes())==patch['bytes'] and hashlib.sha256(f.read_bytes()).hexdigest()==patch['sha256']
pos=json.loads((P/'final-positive.execution.json').read_bytes());neg=json.loads((P/'final-removal.execution.json').read_bytes());proofs=[]
for name in ['final-wheel-proof-positive.json','final-wheel-proof-remove_row_isolation.json']:
 x=json.loads((P/name).read_bytes());assert x['site_bytes_unchanged'] and x['site_files_before_and_after']==3459 and x['test_carrier_sha']==F and x['distribution_source_sha']==prod;proofs.append(bind(P/name))
assert pos['exit']==0 and neg['exit']==1
assert '2 passed' in (P/'final-positive.stdout').read_text() and '2 failed' in (P/'final-removal.stdout').read_text()
assert (P/'final-removal.stderr').read_bytes()==b''
report={'schema':'F-independent-installed-graph-reconciliation-review/2026-10-07','reviewer':'/root/cau','review_target':{'sha':F,'tree':git('rev-parse',F+'^{tree}').decode().strip(),'defining_new_paths':newpaths},'distribution':{'sha':prod,'tree':git('rev-parse',prod+'^{tree}').decode().strip(),'isolated_wheel_only_independent_replay':True,'sdist_author_results_separate':True},'check':'PASS','bounded_verdict':'GO','issues':issues,'source_reconciliation':{'all_commits':commits,'all_changed_paths_count':221,'evidence_paths':214,'defining_source_test_docs_fragment_paths':7,'all7x5_present_or_absent_Git_bindings_verified':True,'unique_IR_blobs':sorted(seen),'canonical_competing_whole_module_AST_equal':True,'test_carrier_zero_prod_delta':True},'native':{'positive':pos,'retained_property_removal':neg,'proofs':proofs},'oracle':'Independent Git complete-history/path/blob/AST reconciliation plus real installed parameter/CSV/CAS/fresh-isolated-reader output agreement. Full graph payload, parallel marks/lag/multiplicity and domain-specific temporal refusal compared directly; updated zero-lag graph warms ancestry before copy.','negative':'Delete detached edge-row values only, retaining class/schema/private JSON preparation/installed files and native output declarations. Both actual cases reject shared mutable row alias at behavioral assertion; no harness precondition error in final removal.','historical_errors':{'independent7f_positive':json.loads((P/'positive.execution.json').read_bytes()),'classification':'2 actual pytest FAIL after semantic freshreader assertions due test-only ArtifactID JSON observer error, not a product failure and not PASS; full raw retained. Author3bfc temporal static-domain harness errors remain separately recorded by author.'},'limitations':['Real parameter recorder is plain-dictionary consumer ABI, not live Kuzu database.','Existing199x2 installed evidence remains exact8236 product/oldtest profile, not a whole3dde or newtestcarrier PASS.','This review independently executes wheel2 only; source-backed author sdist2 is distinct.','No observational causal authority, backend scientific law, universal external-client absence, or formalG finding closure.','38 incomplete static declarations/computed external consumers remain unknown, no false zero denominator.']}
(P/'independent-review.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'check':'PASS','verdict':'GO','target':F,'report':bind(P/'independent-review.json'),'commits':9,'paths':221,'native':'2PASS','removal':'2FAIL','sitefiles':3459}))
