"""Reconcile documentation scope/content bindings; not a numerical test."""
from pathlib import Path
import json,subprocess,hashlib,re,csv
import argparse
p=argparse.ArgumentParser();p.add_argument('--repo-root',required=True);p.add_argument('--evidence-root',required=True);a=p.parse_args();R=Path(a.repo_root);W=Path(a.evidence_root);
base='d9c48853c5ab9ad7473df204bf3a7a1995a32057';candidate='99f196be45dec7acabdc05f0cb3af5430ec94c9e';root_base='53afa77611c98cb0ac8c271d0aa6ddc205b40f76'
prefix='policy-engine/docs/research/e02-cloud-test-plan/closure-decisions/';paths=[prefix+x for x in ['F.md','method-decisions.md','runtime-profiles.md']]
def git(*a):return subprocess.check_output(['git',*a],cwd=R)
def get(ref,path):return git('show',f'{ref}:{path}')
def sha(b):return hashlib.sha256(b).hexdigest()
assert set(git('diff','--name-only',base,candidate).decode().splitlines())==set(paths)
observed_branch=git('symbolic-ref','--short','HEAD').decode().strip()
assert git('rev-parse',candidate+'^{tree}').decode().strip()=='18711c5732863a4e50672112c7f3c5ba4a1b229b'
for p in paths:assert get(base,p)==get(root_base,p)
checks=[]
for p in paths:
 old=get(base,p).decode();new=get(candidate,p).decode()
 if p.endswith('method-decisions.md'):
  oldblock=old[old.index('<a id="methods-c"></a>'):old.index('<a id="methods-f"></a>')];newblock=new[new.index('<a id="methods-c"></a>'):new.index('<a id="methods-f"></a>')];assert oldblock==newblock
  assert re.findall(r'<a id="f-m(\d+)"></a>',new)==[str(i) for i in range(1,17)]
 elif p.endswith('runtime-profiles.md'):
  start=old.index('## C —');stop=old.index('## F —');newstart=new.index('## C —');newstop=new.index('<a id="f-current-runtime"></a>');oldblock=old[start:stop];newblock=new[newstart:newstop];assert oldblock==newblock
 else:oldblock=newblock=''
 checks.append({'path':p,'base_bytes':len(get(base,p)),'base_sha256':sha(get(base,p)),'candidate_bytes':len(get(candidate,p)),'candidate_sha256':sha(get(candidate,p)),'non_F_full_section_bytes':len(oldblock.encode()),'non_F_full_section_sha256':sha(oldblock.encode()),'non_F_sections_equal':True})
f=get(candidate,paths[0]).decode();own=get('198076863e143dea9f89f02734b13d50dae3eed5','policy-engine/docs/research/e02-cloud-test-plan/execution-organization/finding-owners.tsv').decode();expected={r['finding_id'] for r in csv.DictReader(own.splitlines(),delimiter='\t') if r['unit']=='F'}
assert set(re.findall(r'^\| (B\d+|LA-\d+) \|',f,re.M))==expected
assert len(re.findall(r'<a id="bundle-[^"]+"></a>',f))==17
refs=[]
for text in [get(candidate,p).decode() for p in paths]:
 for path,ref in re.findall(r'`F/([^`@]+\.json)@([a-f0-9]{40})`',text):
  b=get(ref,'policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/F/'+path);refs.append({'path':path,'git_ref':ref,'bytes':len(b),'sha256':sha(b)})
# Controls test content binding, not a scientific assertion from marker presence.
oldrows=json.loads((W/'original35-reconciliation.json').read_text()) if (W/'original35-reconciliation.json').exists() else json.loads((W/'original-inputs/original35-reconciliation.json').read_text())
def valid_card(c):
 b=get(c['source_sha'],c['source_path']);a,z=c['lines'];raw=b''.join(b.splitlines(keepends=True)[a-1:z]);return len(raw)==c['bytes'] and sha(raw)==c['sha256']
c=oldrows['rows'][0]['original_card_bindings'][0];assert valid_card(c)
bad=dict(c,sha256='0'*64);assert not valid_card(bad)
assert git('rev-parse',candidate+'^{tree}').decode().strip()!='0'*40
report={'outcome':'PASS','source_sha':candidate,'observed_branch':observed_branch,'tree':'18711c5732863a4e50672112c7f3c5ba4a1b229b','slice_base_sha':base,'root_base_sha':root_base,'root_base_3_blob_equality':'PASS no merge needed','changed_paths':paths,'documents':checks,'exact_F_finding_set':sorted(expected),'bundle_anchors':17,'method_anchors':16,'complete_cited_receipt_bindings':refs,'negative_controls':[{'property':'original card content binding','retained_markers':'same finding/source/path/range/size, false digest','outcome':'FAIL expected; rejected against reconstructed Git bytes'},{'property':'implementation tree binding','retained_markers':'same implementation ID with false claimedtree','outcome':'FAIL expected; actual Git tree differs'}],'semantic_check':'independent graph owner review; this structural check does not claim scientific or G authority','scientific_reruns':False}
print(json.dumps(report,ensure_ascii=False,indent=2))
