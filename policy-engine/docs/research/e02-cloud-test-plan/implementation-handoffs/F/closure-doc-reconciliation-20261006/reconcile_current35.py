"""Read-only source/card/receipt reconciliation; no scientific reruns."""
from pathlib import Path
import subprocess, json, hashlib, csv, collections
import argparse
p=argparse.ArgumentParser();p.add_argument('--repo-root',required=True);p.add_argument('--evidence-root',required=True);p.add_argument('--outdir',required=True);a=p.parse_args()
ROOT=Path(a.repo_root);EVIDENCE=Path(a.evidence_root);OUT=Path(a.outdir);OUT.mkdir(parents=True,exist_ok=True)
ORIGINAL=EVIDENCE/'original-inputs/original35-reconciliation.json'
def git(*args): return subprocess.check_output(['git',*args],cwd=ROOT)
def digest(b): return hashlib.sha256(b).hexdigest()
def blob(ref,path): return git('show',f'{ref}:{path}')
def check_binding(ref,path,size,sha):
 b=blob(ref,path); assert len(b)==size and digest(b)==sha,(ref,path);return b
old=json.loads(ORIGINAL.read_bytes())
selection=json.loads((EVIDENCE/'original-inputs/original35-reconciliation.selection.json').read_bytes())
for f in selection['items']:
 b=(EVIDENCE/'original-inputs'/Path(f['path']).name).read_bytes();assert len(b)==f['bytes'] and digest(b)==f['sha256']
registries=json.loads((EVIDENCE/'source-receipts.json').read_text())
receipts={}
for a in registries:
 d=json.loads(check_binding(a['git_ref'],a['path'],a['bytes'],a['sha256']));receipts[a['key']]=d
 assert d['unit']=='F' and d['schema']=='policyos.e02.implementation_handoff.v1'
 assert git('rev-parse',d['implementation_commits'][-1]+'^{tree}').decode().strip()==d['candidate_tree_sha']
 for c in d['checks']:
  assert all(k in c for k in ('command','target_sha','environment','input_closure','outcome','output'))
  assert c['outcome'] in ('PASS','FAIL','ERROR','SKIP','UNRUN') and isinstance(c['output'],str)
  git('cat-file','-e',c['target_sha']+'^{commit}')
  if c['output'].startswith('policy-engine/'):
   path=c['output'].split('#',1)[0];outref=c.get('output_git_sha',a['git_ref']);b=blob(outref,path)
   if 'output_sha256' in c:assert digest(b)==c['output_sha256'] and len(b)==c['output_bytes']
# The source TSV, not a row-count proxy, supplies the owner denominator.
owner_path='policy-engine/docs/research/e02-cloud-test-plan/execution-organization/finding-owners.tsv'
owners=list(csv.DictReader(blob('198076863e143dea9f89f02734b13d50dae3eed5',owner_path).decode().splitlines(),delimiter='\t'))
expected={r['finding_id'] for r in owners if r['unit']=='F'}
assert {r['finding_id'] for r in old['rows']}==expected and len(expected)==35
cards=[];new=[]
registry={a['key']:a for a in registries}
keys={**{f'B{i}':['cau_science','cau','root'] for i in range(204,210)},'B206':['cau_science','cau','rdd','root'],'B210':['rdd'],'B211':['rdd'],'B214':['scm_static'],'B216':['scm_static'],'B217':['scm_static'],'B218':['scm_static'],'B220':['scm_static'],'B222':['scm_poly','scm_version'],'B221':['scm_version'],'B223':['scm_version'],'B224':['scm_version'],'B225':['scm_version'],'LA-016':['cau','root'],'LA-001':['fry'],'LA-002':['fry'],'LA-037':['fry'],'LA-003':['eco','eco_dtype'],'LA-004':['eco'],'LA-035':['eco']}
for r in old['rows']:
 fid=r['finding_id']
 parts=[]
 for f in r['original_card_bindings']:
  source=blob(f['source_sha'],f['source_path']);a,z=f['lines'];b=b''.join(source.splitlines(keepends=True)[a-1:z]);assert len(b)==f['bytes'] and digest(b)==f['sha256'],fid
  assert git('rev-parse',f"{f['source_sha']}:{f['source_path']}").decode().strip()==f['document_git_blob']
  parts.append(b)
  cards.append((f['source_sha'],f['source_path'],a,z,f['sha256']))
 reconstructed=b'\n'.join(parts);assert len(reconstructed)==r['scratch_card']['bytes'] and digest(reconstructed)==r['scratch_card']['sha256']
 # Validate every old primary binding; it remains historical, not replaced by a carrier HEAD.
 p=r['primary_receipt'];check_binding(p['head'],p['path'],p['bytes'],p['sha256'])
 current=r['current_continuation_outcome_recommendation'];technical=r['technical_original_criterion_recommendation'];remainder=r['original_criterion_remainder']
 if fid=='LA-004':current=technical='closed';remainder='None for original finite matched/deliberately distinct model profile. Universal replacement/calibration/real authority not claimed.'
 if fid=='LA-003':remainder='Actual canonical registry/spec/compiler/CAS PatchMap migration passes; .10 fiscal budget precision remains FAIL, so original whole migration limited. Forward carry fixes have their own c003 source; not a fiscal-law correction.'
 if fid=='B214':remainder='Latest shared518 static entry admission and reverse normalization are measured. Canonical DAG Scientist node profile does not claim arbitrary PAG/CPDAG completion or protected readiness. Keep current limited without a new original-per-ID authority decision.'
 if fid=='B218':remainder='Lag/self-lag representation/export and typed compact-temporal refusal retained. Latest518 broad static consumers measured; no time-unrolled causal estimator or protected readiness claimed. Keep current limited.'
 pending=fid in ['B56','LA-007','LA-019','LA-020']
 row={k:r[k] for k in ['finding_id','original_titles','original_card_bindings','bundle','actual_consumer','source_scope','oracle_and_negative','technical_historical_baseline_profile_outcome']}
 row.update({'technical_original_criterion_recommendation':technical,'current_continuation_outcome_recommendation':current,'authority_or_G_acceptance':'UNRUN','recommendation_is_G_accepted':False,'original_criterion_remainder':remainder,'separate_unavailable_inputs_or_authority':r['separate_unavailable_inputs_or_authority'],'historical_421_primary_receipt':p,'historical_421_deciding_refs':r['deciding_check_refs_at421'],'current_supplement_receipts':[registry[k] for k in keys.get(fid,[])],'latest_owner_packet':'pending API generic-guard/finite consumer closure or TMLE study-resource continuation; do not promote from uncommitted or failed independent review' if pending else 'published source receipts above; root/G re-adjudication remains separate','next_owner':'F API owner / root then G' if fid in ['LA-007','LA-019','LA-020'] else ('F TMLE resource owner / root then G' if fid=='B56' else ('@foundry-owners objective intent + named optimizer consumer' if fid=='LA-035' else 'F root criterion reconciliation; G code/admitted-input acceptance'))})
 if fid=='LA-004':row['actual_consumer']='Native fiscal/labor registry→PatchMap/apply_patch_map/GlobalState versus EconomicsPlugin.get_mechanisms→CompositeExecutor/EconomicState; actual matched and deliberately distinct finite laws'
 if fid in ['LA-002','LA-037']:row['original_criterion_remainder']='None in original supported finite catalog/IC/native IR/direct caller/docs/install migration; optional new family state kernels and full compatibility retirement are not original acceptance prerequisites.'
 if fid=='B225':row['oracle_and_negative']='Independent math.erfc Normal CDF; positive-tail survival-function differences; original test_scm_result_semantics.py@6dcb lines222–250. No same-SciPy-CDF independence claim.'
 new.append(row)
counts=lambda k:dict(collections.Counter(r[k] for r in new))
draft={'schema':'F-current35-doc-ledger-draft/1','role':'scratch-only root table proposal; not tracked common index, no authority/G acceptance','document_slice_base_sha':git('rev-parse','HEAD').decode().strip(),'input_reconciliation':{'path':str(ORIGINAL),'bytes':ORIGINAL.stat().st_size,'sha256':digest(ORIGINAL.read_bytes()),'selection_file_count':len(selection['items'])},'original_owner_tsv':{'source_sha':'198076863e143dea9f89f02734b13d50dae3eed5','path':owner_path,'bytes':len(blob('198076863e143dea9f89f02734b13d50dae3eed5',owner_path)),'sha256':digest(blob('198076863e143dea9f89f02734b13d50dae3eed5',owner_path))},'denominator':{'finding_ids':35,'bundle_ids':len({r['bundle'] for r in new}),'original_card_bindings':len(cards),'unique_original_card_blocks':len(set(cards)),'LA016_duplicate_binding':'two coverage bindings to the SAME source block, not two different cards'},'current_receipt_registry':registries,'rows':new,'technical_proposal_counts':counts('technical_original_criterion_recommendation'),'current_continuation_proposal_counts':counts('current_continuation_outcome_recommendation'),'pending_API_TMLE':True,'scientific_reruns':False,'G_acceptance':'UNRUN'}
assert len(cards)==36 and len(set(cards))==35
path=OUT/'current35-doc-ledger-draft.json';path.write_text(json.dumps(draft,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'outcome':'PASS','draft_path':str(path),'bytes':path.stat().st_size,'sha256':digest(path.read_bytes()),'denominator':draft['denominator'],'technical':draft['technical_proposal_counts'],'current':draft['current_continuation_proposal_counts'],'current_receipts_verified':len(registries),'checks_verified':sum(len(d['checks']) for d in receipts.values()),'scientific_reruns':False},ensure_ascii=False,indent=2))
