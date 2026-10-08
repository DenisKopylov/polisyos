import json,pathlib,subprocess,hashlib,collections
O=pathlib.Path(__file__).parent;REPO='/workspace/e02-F-graph-20261006';BASE='198076863e143dea9f89f02734b13d50dae3eed5';P='policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/F/'
G=lambda *a:subprocess.check_output(['git',*a],cwd=REPO)
report=json.loads((O/'F-published-protocol-audit.json').read_text());parts=report['primary_components']+report['companion_components']+report['ancillary_components'];heads=sorted({x['head'] for x in parts});registered={x['primary']['path'] for x in parts};found=collections.defaultdict(list);candidate_files=0
for h in heads:
 paths=G('diff','--name-only',BASE,h,'--',P).decode().splitlines()
 for p in paths:
  if not p.startswith(P) or '/' in p[len(P):] or not p.endswith('.json'):continue
  candidate_files+=1;raw=G('show',h+':'+p)
  try:j=json.loads(raw)
  except ValueError:continue
  if isinstance(j,dict) and j.get('schema')=='policyos.e02.implementation_handoff.v1' and j.get('unit')=='F':found[p].append({'sha':h,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'role':j.get('receipt_role','implementation'),'candidate_sha':j.get('candidate_sha',j.get('implementation_sha',(j.get('implementation_commits') or [None])[-1]))})
result={'schema':'policyos.e02.canonical-receipt-inventory.v1','source_base_sha':BASE,'topic_head_denominator':len(heads),'introduced_direct_F_json_files_examined_per_head_sum':candidate_files,'canonical_unique_path_count':len(found),'registered_component_count':len(parts),'introduced_canonical_receipt_paths':dict(sorted(found.items())),'registered_paths':sorted(registered),'missing_registered_paths':sorted(registered-set(found)),'unregistered_canonical_paths':sorted(set(found)-registered),'check':'PASS' if set(found)==registered else 'FAIL','scope':'Complete direct F JSON paths introduced since freshbase198 on every actual registered published topic head; scientific/primary decision mapping remains separately35/17. Canonical schema files only; raw/review manifests excluded by actual schema, not filename guess.'}
p=O/'canonical-receipt-inventory.json';p.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:result[k] for k in ['topic_head_denominator','canonical_unique_path_count','registered_component_count','check','missing_registered_paths','unregistered_canonical_paths']}))
