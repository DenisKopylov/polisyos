"""Prepare explicit additive transport inputs; no semantic/root/Git writes."""
from pathlib import Path
import hashlib,json,subprocess
R=Path('/tmp/e02-F-continuation-20261007');D=R/'fit-tmle/root-final-transport-design';repo='/workspace/e02-F-closeout-20261006'
def binding(p):
 h=hashlib.sha256();n=0
 with p.open('rb') as s:
  while b:=s.read(1<<20):n+=len(b);h.update(b)
 return {'bytes':n,'sha256':h.hexdigest()}
def write(name,o):
 p=D/name
 with p.open('xb') as s:s.write((json.dumps(o,indent=2)+'\n').encode())
 return p
# Complete ROOT execution observations; five curated fragment source bodies are
# immutable tracked inputs and referenced at source519 rather than copied again.
files=[];excluded=[]
for folder in ['root-quality-final','root-quality-final-retry']:
 for p in sorted((R/folder).rglob('*')):
  if not p.is_file():continue
  if 'fragments' in p.relative_to(R/folder).parts:
   relative='policy-engine/release-fragments/unreleased/'+p.name
   b=subprocess.check_output(['git','-C',repo,'show','519e4822f608cbe4e7ac1ee7b01f6c29cb84bc82:'+relative]);assert binding(p)=={'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
   excluded.append({'original_path':str(p),'git_ref':'519e4822f608cbe4e7ac1ee7b01f6c29cb84bc82','path':relative,**binding(p),'reason':'Tracked source input, exactly reproducible from published source; no duplicate body.'})
  else:files.append({'path':str(p),**binding(p)})
q=write('quality-519-execution-selection.json',{'schema':'policyos.e02.explicit_transport_selection.v1','files':files,'excluded_tracked_inputs':excluded,'source_sha':'519e4822f608cbe4e7ac1ee7b01f6c29cb84bc82','meaning':'Complete actual ROOT quality stdout/stderr/execution files, including both SIGKILL ERROR attempts. Original first runner FAIL classification stays historical and corrected by final-scanner-termination-correction; no complete scanner JSON exists. Independent economic delta review is pending, no implied scientific PASS.'})
prefix='policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/F/catalog-default-resources-20261007';ref='ffae9fa4b45c23c3d2dca5c1bbf78d18418a7634';remote='refs/remotes/origin/codex/e02-F-graph-20261006';head=subprocess.check_output(['git','-C',repo,'rev-parse',remote],text=True).strip();assert head==ref
paths=[prefix+'.json',prefix+'/outputs.json',prefix+'/execution-to-git-locators.json',prefix+'/fit-design/review.json',prefix+'/fit-design/transfer-selection.json']
rows=[]
for p in paths:
 b=subprocess.check_output(['git','-C',repo,'show',ref+':'+p]);rows.append({'git_ref':ref,'path':p,'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest(),'remote_ref':remote,'remote_head':head,'extension_id':'packaged-resource-owner-receipt','role':'Published canonical Graph resource owner complete receipt and existing FIT proposal/review locators; no duplicate owner evidence/source.'})
g=write('published-graph-ffae-spec.json',{'files':rows,'network_readback_scope':'Existing origin-tracking ref plus ROOT fetch-exact-refs outputs; no fresh network probe by leaf.'})
write('recovered-519-cli-inputs.json',{'schema':'policyos.e02.transport_cli_inputs.v1','source_sha':'519e4822f608cbe4e7ac1ee7b01f6c29cb84bc82','source_tree':'750d28da94f372848fe6b2db5f88db95b94cb57d','root_source_or_Git_writes':False,'refresh_command':['python3',str(D/'refresh_selection_v3.py'),'--seed-selection',str(D/'selection-draft.json'),'--prior-manifest',str(D/'staged-draft/policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/F/continuation-closeout-20261007/artifact-transports.json'),'--prior-staging-root',str(D/'staged-draft'),'--repository',repo,'--final-source-sha','519e4822f608cbe4e7ac1ee7b01f6c29cb84bc82','--refresh-directory',str(R/'root-integration'),'--include-directory','root-recovery='+str(R/'root-recovery'),'--include-selection','quality-519-execution='+str(q),'--existing-git-spec',str(g),'--resolve-pending','packaged-resource-owner-receipt','--include-file',str(D/'recovered_validate.py'),'--include-file',str(D/'recovered-validation.json'),'--include-file',str(D/'recovered-validation.stdout.json'),'--include-file',str(D/'recovered-validation.stderr.txt'),'--include-file',str(D/'prepare_recovered_inputs.py'),'--output',str(D/'selection-recovered-519-v3.json')],'pending_named_packets':[{'id':'new-final-root-quality','needed':'Complete final source-bound independent economic scanner/quality ERROR classification + full selected outputs, exact frozen transfer selection. Both raw SIGKILL attempts are currently available and included; no missing full scanner JSON represented as PASS.'},{'id':'new-final-installed-composition','needed':'Actual published Foundry519 wheel/sdist91+six-removal/fresh-child receipt, immutable carrier/primary/outputs full size/hash and observed origin head. Source-reported or local-only object is insufficient.'},{'id':'later-G-merge-recovery-records','needed':'Actual later G855 ordinary merge/reconciliation/checkpoint full commands/status/readback/source identity. Include only after execution; this is an additive custody input, no future event/SHA.'}],'validation_command':['python3',str(D/'publish_transport_v3.py'),'--selection',str(D/'selection-recovered-519-v3.json'),'--repository',repo],'materialization_rule':'ROOT only: append --materialize --destination <authorized destination>; primary optional only ROOT-adjudicated exact actual primary with canonical check strings. This leaf has no ROOT source/docs/Git write lease.'})
print(json.dumps({'quality':{'path':str(q),**binding(q),'files':len(files),'source_refs':len(excluded)},'graph_spec':{'path':str(g),**binding(g),'published_refs':len(rows)}},indent=2))
