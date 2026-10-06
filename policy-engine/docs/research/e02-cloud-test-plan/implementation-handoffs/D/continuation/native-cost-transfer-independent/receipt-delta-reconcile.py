"""Independent read-only receipt publication delta; no product execution/source copies."""
import base64,gzip,hashlib,json,subprocess
from datetime import datetime,timezone
from pathlib import Path
import xml.etree.ElementTree as ET
REPO=Path('/workspace/e02-D-published-root')
OUT=Path('/tmp/e02-D-cost-transfer-independent-20261006')
SOURCE='4ac49418289a31e77329bf92b1c2bf990cf2a087'
RECEIPT='4fff9e8089bfba442e2ec8710cda45bfd9b6959c'
E02='policy-engine/docs/research/e02-cloud-test-plan/'
RP=E02+'implementation-handoffs/D/continuation/transfer-selection-criteria.json'
def sha(b): return hashlib.sha256(b).hexdigest()
def git(*a): return subprocess.check_output(['git',*a],cwd=REPO)
def blob(s,p): return git('show',s+':'+p)
receipt_bytes=blob(RECEIPT,RP); r=json.loads(receipt_bytes)
assert sha(receipt_bytes)=='f266455a686de71a5e59f900a8913a9b33a0739f980b49afb17f165850236b6d'
assert r['source_sha']==SOURCE and r['source_tree']==git('rev-parse',SOURCE+'^{tree}').decode().strip()
assert r['G_accepted'] is False and r['closure_ids']==[]
changed=git('diff','--name-status',SOURCE,RECEIPT).decode().splitlines()
assert sorted(changed)==sorted(['A\t'+RP,'A\t'+r['output_payload']['path']])
archive=blob(RECEIPT,r['output_payload']['path']); raw=gzip.decompress(archive); packet=json.loads(raw)
assert sha(archive)==r['output_payload']['raw_file_sha256'] and len(archive)==r['output_payload']['compressed_bytes'] and len(raw)==r['output_payload']['uncompressed_bytes']
assert packet['source_sha']==SOURCE
files={}; file_records=[]; roots=[Path('/workspace/e02-D3-receipts/transfer-criteria-review'),Path('/tmp/e02-transfer-criteria-f3f900ae578842bea2f7e75fa688f05a')]
for name,entry in packet['files'].items():
 assert entry['encoding']=='base64'
 data=base64.b64decode(entry['content'],validate=True)
 assert sha(data)==entry['sha256'] and len(data)==entry['bytes'],name
 files[name]=data
 candidates=[root/name for root in roots if (root/name).is_file()]
 assert candidates and any(path.read_bytes()==data for path in candidates),name
 file_records.append({'name':name,'bytes':len(data),'sha256':sha(data),'retained_matching_paths':[str(p) for p in candidates if p.read_bytes()==data]})
assert len(files)==31
material={}
for digest,encoded in packet['material_input_bytes_base64_by_sha256'].items():
 data=base64.b64decode(encoded,validate=True); assert sha(data)==digest
 material[digest]=data
assert len(material)==155
path_records=[]
for path,entry in packet['material_input_paths'].items():
 data=material[entry['raw_file_sha256']]
 assert len(data)==entry['bytes'] and Path(path).read_bytes()==data,path
 path_records.append({'path':path,'bytes':len(data),'sha256':sha(data)})
assert len(path_records)==708
source_records=[]
for entry in r['source_identities']+r['full_original_cards_read']:
 data=blob(entry['source_sha'],entry['path'])
 assert len(data)==entry['bytes'] and sha(data)==entry['raw_file_sha256'],entry['path']
 source_records.append({'source_sha':entry['source_sha'],'path':entry['path'],'git_blob':git('rev-parse',entry['source_sha']+':'+entry['path']).decode().strip(),'bytes':len(data),'sha256':sha(data)})
original=json.loads(blob('cae5589aa7080b628e93d594eeb4ff7c2fc2414d',E02+'implementation-handoffs/D/published-final-criterion-accounting.json'))
original={row['finding_id']:row for row in original['criterion_occurrences'] if row['finding_id'].startswith('B1')}
criterion_records=[]
for row in r['findings']:
 c=row['original_criterion']; assert row['G_accepted'] is False
 assert c['acceptance_text']==original[row['id']]['canonical_content']['text']
 assert sha(c['acceptance_text'].encode())==c['acceptance_sha256']==original[row['id']]['canonical_content']['sha256']
 assert c['acceptance_text'] in blob(SOURCE,c['path']).decode()
 criterion_records.append({'finding_id':row['id'],'card':c['card'],'acceptance_sha256':c['acceptance_sha256'],'author_proposal':row['author_status'],'G_accepted':False})
run_summaries=[]
for name in ('trn-original-base','trn-cas-hnsw-only','trn-cas-hnsw-tmp','trn-discovery-property-removal'):
 meta=json.loads(files[name+'.json'])
 assert sha(files[name+'.txt'])==meta['output_sha256']
 xml=ET.fromstring(files[name+'.xml']); suites=list(xml.iter('testsuite'))
 attrs={k:sum(int(s.attrib.get(k,0)) for s in suites) for k in ('tests','failures','errors','skipped')}
 run_summaries.append({'name':name,'source_sha':meta['before']['sha'],'tree':meta['before']['tree'],'exit_code':meta['exit_code'],'wall_seconds':meta['wall_seconds'],'junit':attrs,'output_sha256':meta['output_sha256']})
remote=git('ls-remote','origin','refs/heads/codex/e02-D-published-transfer').decode().strip()
assert remote.split()[0]==RECEIPT
oldreview=OUT/'review.json'
result={
 'schema':'policyos.e02.independent_review_receipt_delta.v1','unit':'D','reviewer':'cost_transfer_review','recorded_at':datetime.now(timezone.utc).isoformat(),
 'prior_independent_review':{'path':str(oldreview),'sha256':sha(oldreview.read_bytes())},
 'immutable_source':{'sha':SOURCE,'tree':r['source_tree']},'receipt':{'sha':RECEIPT,'tree':git('rev-parse',RECEIPT+'^{tree}').decode().strip(),'path':RP,'bytes':len(receipt_bytes),'sha256':sha(receipt_bytes),'remote_readback':remote},
 'complete_changed_paths_since_source':changed,'production_and_test_delta_since_source':[],
 'independent_checks':{'archive_compressed_bytes':len(archive),'archive_compressed_sha256':sha(archive),'archive_uncompressed_bytes':len(raw),'archive_uncompressed_sha256':sha(raw),'complete_output_members':len(files),'all31_members_match_declared_hash_size_and_actual_retained_bytes':True,'material_path_bindings':len(path_records),'deduplicated_actual_material_byte_contents':len(material),'all708_paths_match_actual_retained_bytes_and155_deduplicated_content_hashes':True,'source_and_full_original_card_bindings':len(source_records),'all_source_card_hashes_match_exact_Git':True,'all10_original_acceptance_bindings_exact':True},
 'complete_output_member_bindings':file_records,'source_card_bindings':source_records,'original_criteria':criterion_records,'deciding_run_summaries':run_summaries,
 'material_bindings_lossless_pointer':RECEIPT+':'+r['output_payload']['path']+'#/material_input_paths and /material_input_bytes_base64_by_sha256',
 'independent_verdict':'published receipt losslessly matches previously independently reviewed bounded cost/transfer evidence; no new own-fixable blocker found',
 'scope_and_limits':[
 'No new test/backend run was performed by this reviewer; independently decoded/recomputed author deciding outputs and actual retained bytes.',
 '32 native HNSW/CAS-only checks and1expectedFAIL/1healthyPASS property removal are exact4ac. Torch/BoTorch/GPyTorch are explicitly denied for this profile; installed-distribution absence and GP properties are not established.',
 'The ENOSPC28ERROR/4PASS and two SIGKILL runs remain errors without successful verdict; complete error outputs are preserved.',
 'A changed query(None) native generation reader has a bounded barrier test; prior >1000 two-process native checks retain prior source bindings and are not rerun at4ac.',
 'B128/B129/B130/B133/B134 current mechanism proposals were independently reviewed as described in prior review; B132/B136 full historical lineage adjudication remains outside this new code delta review. B135 new contextual equivalence tests were reviewed. Author eight closed_proposed are not G acceptance.',
 'B134 original local native failure/shape/capacity/coherence criterion is distinct from B131 live tenant/split authority and B137 authorized revalidation; live issuer input must not be added to B134 merely to block its original local criterion.',
 'No inherited-red waiver made: characterization058 is not the original continuation slice base.'
 ],
 'G_accepted':False,'closure_ids':[],'author_proposals':r['author_closure_proposed_ids'],'author_held':r['held_ids'],
 'own_fixable_blockers':[],'repository_writes':[],'product_or_test_writes':[]
}
(OUT/'receipt-delta-review.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'output':str(OUT/'receipt-delta-review.json'),'bytes':(OUT/'receipt-delta-review.json').stat().st_size,'sha256':sha((OUT/'receipt-delta-review.json').read_bytes()),'verified_output_members':len(files),'verified_actual_material_paths':len(path_records),'verified_deduplicated_contents':len(material),'source_card_bindings':len(source_records),'original_acceptance_bindings':len(criterion_records),'run_summaries':run_summaries},indent=2))
