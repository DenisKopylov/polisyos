import gzip
import hashlib
import json
import pathlib
import subprocess

ROOT = pathlib.Path('/workspace/e02-F-closeout-20261006')
SCRATCH = pathlib.Path('/tmp/e02-F-continuation-20261007/intake')
PREFIX = pathlib.Path('policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/F')
TARGET = ROOT/PREFIX/'continuation-intake-20261007'
PIN = '072d45a56d1119fe3e7665cec2cbbdca015d2934'
G = '9a187afa4ef75af4a7b01ca49f1cc8194f7b6fe7'
sha=lambda b:hashlib.sha256(b).hexdigest()
def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT)

assert git('rev-parse','HEAD').decode().strip()==PIN
assert git('branch','--show-current').decode().strip()=='codex/e02-F-closeout-20261006'
assert not git('diff','--name-only') and not git('diff','--cached','--name-only')
TARGET.mkdir(exist_ok=False)

# Complete closeout transport is part of the mandatory input read, independently of scientific status.
old_transport='policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/F/continuation-closeout-20261006/transport.json'
old=json.loads(git('show',PIN+':'+old_transport)); old_checks=[]
for r in old['files']:
 b=git('show',PIN+':'+r['path']); assert len(b)==r['bytes'] and sha(b)==r['sha256']
 z=gzip.decompress(b) if r['encoding']=='gzip' else b
 assert len(z)==r['decoded_bytes'] and sha(z)==r['decoded_sha256']
 old_checks.append(r|{'source_sha':PIN,'stored_check':'PASS','decoded_check':'PASS'})
(SCRATCH/'closeout-full-transport-read.json').write_text(json.dumps({'source_sha':PIN,'files':old_checks,'count':len(old_checks),'check':'PASS','scientific_check':False},ensure_ascii=False,indent=2)+'\n')

docs=['AGENTS.md','policy-engine/CONTRIBUTING.md','policy-engine/tools/devx/workspace/README.md']
E='policy-engine/docs/research/e02-cloud-test-plan/'
docs += [E+p for p in ['execution-prompts/HANDOFF.md','execution-organization/README.md','results/README.md','results/verification.json','closure-decisions/README.md','closure-decisions/F.md','closure-decisions/coverage.json','closure-decisions/method-decisions.md','closure-decisions/runtime-profiles.md','closure-decisions/cross-unit-contracts.md','closure-decisions/semantic-decisions.md','closure-decisions/execution-sequence.md','closure-decisions/verification-and-closeout.md','integration/reviews/F-pr65-continuation-audit-2026-10-06.md','implementation-handoffs/F/graph-intake-review-20261006.json']]
docs+=['policy-engine/docs/reference/policy-design-case-failure-patterns.md']
doc_refs=[]
for p in docs:
 b=git('show',PIN+':'+p);doc_refs.append({'source_sha':PIN,'path':p,'bytes':len(b),'sha256':sha(b),'git_blob':git('rev-parse',PIN+':'+p).decode().strip()})
cpath=E+'execution-prompts/continuation-2026-10-07/COMMON.md'; cb=git('show',G+':'+cpath)
assert cb==(SCRATCH/'COMMON.md').read_bytes();doc_refs.append({'source_sha':G,'path':cpath,'bytes':len(cb),'sha256':sha(cb),'git_blob':git('rev-parse',G+':'+cpath).decode().strip()})

files=[]
for n,p in enumerate(sorted(SCRATCH.rglob('*'))):
 if not p.is_file():continue
 b=p.read_bytes(); rel=p.relative_to(SCRATCH); enc='gzip' if len(b)>65536 else 'raw'
 target=TARGET/(str(rel)+('.gz' if enc=='gzip' else ''));target.parent.mkdir(parents=True,exist_ok=True)
 z=gzip.compress(b,mtime=0) if enc=='gzip' else b;target.write_bytes(z)
 files.append({'path':str(target.relative_to(ROOT)),'bytes':len(z),'sha256':sha(z),'encoding':enc,'decoded_bytes':len(b),'decoded_sha256':sha(b),'original_execution_path':str(p),'role':'Full read-only startup/protocol/query output. Not a current scientific PASS.'})
transport={'schema':'policyos.e02.complete-output-transport.v1','files':files,'stored_files':len(files),'stored_bytes':sum(r['bytes'] for r in files),'decoded_bytes':sum(r['decoded_bytes'] for r in files),'historical_failed_attempts_preserved':True}
tp=TARGET/'transport.json';tp.write_text(json.dumps(transport,ensure_ascii=False,indent=2)+'\n')
pack=json.loads((SCRATCH/'current-pack-read.json').read_bytes()); results=json.loads((SCRATCH/'result-pack-and-owner-read.json').read_bytes())
receipt={'schema':'policyos.e02.continuation_intake.v1','unit':'F','slice':'continuation-20261007-intake','branch':'codex/e02-F-closeout-20261006','worktree_root':str(ROOT),'pull_request':'https://github.com/DenisKopylov/polisyos/pull/65','slice_base_sha':PIN,'slice_base_tree_sha':git('rev-parse',PIN+'^{tree}').decode().strip(),'root_carrier_is_not_unified_product_source':True,'product_source_sha':'8236d9c368336a5ea20c1586f29aea7321db6536','product_source_tree':'724a77c88d4e6699ffead58a5e3e3990fb88640a','fresh_G_checkpoint_sha':G,'fresh_G_checkpoint_tree':git('rev-parse',G+'^{tree}').decode().strip(),'fresh_G_relation':json.loads((SCRATCH/'ancestry.json').read_bytes()),'workspace_admission':'All seven exact existing branch/path resume pairs admitted/complete; full JSON in transport. No new checkout.','mandatory_document_refs':doc_refs,'baseline_import_check':json.loads((SCRATCH/'import-check.stdout').read_bytes()),'baseline_pack_role':'transfer_and_navigation_only; raw archives0; oldPASSs not current candidate proof','full_result_pack_read_ref':next(r for r in files if r['original_execution_path'].endswith('/result-pack-and-owner-read.json')),'full_current_pack_read_ref':next(r for r in files if r['original_execution_path'].endswith('/current-pack-read.json')),'current_pack_read_denominator':{'IDs':35,'bundles':17,'original_bindings':36,'stored_material_records':len(pack['transport_checks']),'decoded_material_records':sum('decoded_bytes' in r for r in pack['transport_checks']),'closeout_transport_records':len(old_checks)},'failure_queries':'failures-only30 fullmatching3; three exactcells +35findingdetails executed. Full outputs/commands/returncodes in transport.','findings_closed_by_this_intake':[],'formal_G_acceptance':False,'historical_outcomes_are_preserved':True,'superseded_criterion_extensions':['LA-035 unchanged equivalent relocation does not require a new optimizer/normative objective packet; COMMON controls.'],'current_ownership':'Graph sole producer+reconcile writer; FIT/API/ECO narrow consumer tests; independent CAU/Foundry/API reviewers; ROOT sole common ledger/docs writer. Six direct helpers, no grandchildren.','process_quotas_added':False,'production_data_uploaded':False,'no_main_or_G_integration_write':True,'cleanup':'Native Trash unavailable; no permanent deletion. Active Git/worker/environment symlinks preserved. Exact scratch candidates only at closeout.','full_output_transport':str(tp.relative_to(ROOT)),'known_startup_errors':'Initial remote own-ref was absent until explicit ordinary fetch; first two input-reader decoders did not support legacy wrappers and exited ERROR; full versions/stdout/stderr retained, corrected complete3532 record check PASS. One tool cwd typo failed before execution; no source mutation.','patterns':['P01','P02','P05','P09','P10','P14','P27','P29','P32','P35','P36','P37','P38','P40','P41'],'P41':'not_established; no inherited-red waiver by this intake.'}
(ROOT/PREFIX/'continuation-intake-20261007.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'receipt':str(PREFIX/'continuation-intake-20261007.json'),'transport_files':len(files),'closeout_records':len(old_checks),'stored_bytes':transport['stored_bytes'],'decoded_bytes':transport['decoded_bytes']}))
