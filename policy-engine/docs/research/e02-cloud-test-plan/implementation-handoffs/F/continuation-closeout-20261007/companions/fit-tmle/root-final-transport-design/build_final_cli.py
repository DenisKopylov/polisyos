"""Build explicit final transport CLI from immutable original seed/prior pair.
No source/Git writes; only this authorized transport scratch receives new files.
"""
from pathlib import Path
import hashlib,json,sys
D=Path('/tmp/e02-F-continuation-20261007/fit-tmle/root-final-transport-design');S=D.parent.parent
R='/workspace/e02-F-closeout-20261006';CDF='cdf61b4500e355a27db14260e80ce673ddf8869e';PREFIX='policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/F/continuation-closeout-20261007'
def binding(p):
 n=0;h=hashlib.sha256()
 with p.open('rb') as f:
  while b:=f.read(1<<20):n+=len(b);h.update(b)
 return {'bytes':n,'sha256':h.hexdigest()}
def write(name,obj):
 p=D/name
 with p.open('xb') as f:f.write((json.dumps(obj,indent=2)+'\n').encode())
 return p
# Freeze explicit helper inputs. Tiny materialized manifests/recipes are actual
# test outputs; already duplicated helper/fixture bodies are skipped by path and
# retain their exact original input carriers. No old staging or recursive root scan.
files=[p for p in sorted(D.iterdir()) if p.is_file()]
excluded=[]
for dirname in ['utility-probe','v4-codec-probe','v5-codec-probe']:
 folder=D/dirname
 if not folder.exists():continue
 for p in sorted(folder.rglob('*')):
  if not p.is_file() or '__pycache__' in p.parts:continue
  staged=any(x.endswith('-stage') for x in p.relative_to(folder).parts)
  if staged and p.name not in ['artifact-transports.json','selection-final.json']:
   excluded.append({'path':str(p),'binding':binding(p),'reason':'Tiny materialized duplicate body; full original helper/fixture input + deciding manifest/recipe retained. No scientific source or output dropped.'});continue
  files.append(p)
prior=D/'staged-draft'/PREFIX/'artifact-transports.json';files.append(prior)
assert len({str(p) for p in files})==len(files)
own=write('own-helper-final-selection.json',{'schema':'policyos.e02.explicit_transport_selection.v1','files':[{'path':str(p),**binding(p)} for p in files],'explicit_skipped_tiny_materialized_duplicate_bodies':excluded,'scope':'Complete original/refreshed helper scripts, commands, actual stdout/stderr and fixture bytes; old V4 NO-GO and old draft scopes unchanged. Prior staging is not recursively scanned; original171MB is a single existing raw input plus old verified gzip custody.'})
incs=[('quality-519-execution',D/'quality-519-execution-selection.json'),('new-final-root-quality',D/'economic-quality-v3-adapter.json'),('graph-root-G-review',S/'graph/root519-G855-review/transfer-selection.json'),('final-cau-ledger',S/'cau/ledger-recovery-review/final-review-transfer-selection.json'),('historical-v4-codec',S/'api/transport-v4-independent/transfer-selection.json'),('final-v5-codec',S/'api/transport-v5-independent/transfer-selection.json'),('own-frozen-helper-inputs',own)]
expected={'historical-v4-codec':(19009,'a2f86e70676dfb0e1a9e6710312435b5a2e38e23ee0b26992f4371cd0d72f821'),'final-v5-codec':(69097,'df28e09fe6297fba3e92761bf7f59b1893c1c55f1b6c7d0441b8e4c3be548258'),'final-cau-ledger':(164923,'58885bdbb9bd1c366dedf1b1cce0695e4505ee3f07f6e53bbc9405a09d747ee7'),'graph-root-G-review':(13972,'664e03368ab39b6a28206906af574d557d69c125195e5f6d21df9807779cd1b2')}
for ident,p in incs:
 assert p.is_file(),p
 if ident in expected:
  n,h=expected[ident];assert binding(p)=={'bytes':n,'sha256':h},(p,binding(p))
selection=D/'selection-final-cdf-v5.json'
argv=[sys.executable,str(D/'refresh_selection_v5.py'),'--seed-selection',str(D/'selection-draft.json'),'--prior-manifest',str(prior),'--prior-staging-root',str(D/'staged-draft'),'--repository',R,'--final-source-sha',CDF,'--refresh-directory',str(S/'root-integration'),'--include-directory','root-recovery='+str(S/'root-recovery')]
for ident,p in incs:argv+=['--include-selection',ident+'='+str(p)]
for name in ['published-graph-ffae-spec.json','published-installed-de197-final-cdf-spec.json','published-installed-c4dd-final-cdf-spec.json','economic-quality-pure-git-final-cdf-spec.json']:argv+=['--existing-git-spec',str(D/name)]
for ident in ['new-final-root-quality','new-final-installed-composition','packaged-resource-owner-receipt']:argv+=['--resolve-pending',ident]
argv+=['--publisher',str(D/'publish_transport_v5.py'),'--output',str(selection)]
validate=[sys.executable,str(D/'publish_transport_v5.py'),'--selection',str(selection),'--repository',R]
cli=write('final-cdf-v5-cli-inputs.json',{'schema':'policyos.e02.exact_cli_inputs.v1','actual_document_source':{'sha':CDF,'tree':'a08083a193d4621a5d5c59bf31a94916e8323a0a'},'numerical_installed_source':{'sha':'519e4822f608cbe4e7ac1ee7b01f6c29cb84bc82','tree':'750d28da94f372848fe6b2db5f88db95b94cb57d'},'refresh_argv':argv,'validation_argv':validate,'ROOT_materialization_argv_append_only':['--materialize','--destination','<ROOT-exact-authorized-stage>','--primary-template','<ROOT-final-reviewed-cdf-primary>'],'selection_output':str(selection),'independent_v5_review':{'path':str(S/'api/transport-v5-independent/review.json'),**binding(S/'api/transport-v5-independent/review.json')},'explicit_selection_inputs':[{'id':i,'path':str(p),**binding(p)} for i,p in incs],'prior_manifest':{'path':str(prior),**binding(prior)},'frozen_helper_sources':[{'path':str(D/n),**binding(D/n)} for n in ['refresh_selection_v5.py','publish_transport_v5.py','transport_text_policy.py']],'late_deciding_refresh_validation_stdout':'Created only after this selection is frozen. ROOT must preserve complete exact execution outputs/replayer in its companion without recursively including a selection/manifest in itself. They are not future PASS inputs here.','no_source_writes':True,'no_Git_writes':True,'science_tests_run':False})
print(json.dumps({'cli':{'path':str(cli),**binding(cli)},'own_helper_selection':{'path':str(own),**binding(own)},'logical_own_inputs':len(files),'tiny_materialized_duplicate_bodies_not_recopied':len(excluded)},indent=2))
