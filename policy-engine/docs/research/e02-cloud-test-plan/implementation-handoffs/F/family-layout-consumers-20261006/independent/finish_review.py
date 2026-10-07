"""Read-only evidence/source custody audit; writes only independent scratch review."""
from pathlib import Path
from html.parser import HTMLParser
import hashlib, json, subprocess
ROOT=Path('/workspace/e02-F-fry-20261006')
OUT=Path('/tmp/e02-F-continuation-20261006/fit-fry-review')
AUTHOR=Path('/tmp/e02-F-continuation-20261006/foundry')
SHA='7f05b6259e0c78fac81a0baa4bff41e648a9d771'
TREE='d1b9a51e9ac48bf79251a53a0478cad7305da41a'
def git(*args): return subprocess.check_output(['git',*args],cwd=ROOT)
def h(data): return hashlib.sha256(data).hexdigest()
def file_ref(p):
 p=Path(p); data=p.read_bytes(); return dict(path=str(p),bytes=len(data),sha256=h(data))
def git_ref(ref,path):
 data=git('show',f'{ref}:{path}')
 return dict(git_ref=ref,path=path,git_blob=git('rev-parse',f'{ref}:{path}').decode().strip(),bytes=len(data),sha256=h(data))
def verify_ref(ref):
 actual=file_ref(ref['path'])
 assert actual['bytes']==ref['bytes'] and actual['sha256']==ref['sha256'],(ref,actual)
 return actual
def load(p): return json.loads(Path(p).read_text())
def binding(path,declared):
 rel=str(Path(path).relative_to(ROOT)); exact=git_ref(SHA,rel)
 assert exact['sha256']==declared['sha256'] and exact['bytes']==declared['bytes']
 assert Path(path).read_bytes()==git('show',f'{SHA}:{rel}')
 return exact
assert git('rev-parse','HEAD').decode().strip()==SHA
assert git('rev-parse','HEAD^{tree}').decode().strip()==TREE
assert not git('status','--porcelain=v1')
native=load(OUT/'native40.json'); compiler=load(OUT/'compiled1.json'); negative=load(OUT/'negative3.json')
for run,expected in [(native,('PASS',0,40,0)),(compiler,('PASS',0,1,0)),(negative,('FAIL',1,0,3))]:
 assert (run['outcome'],run['exit_code'],run['counts']['passed'],run['counts']['failed'])==expected
 assert run['counts']['skipped']==run['counts']['errors']==run['counts']['warnings']==0
 verify_ref(run['output_ref']); verify_ref(run['stderr_ref'])
 for item in run['input_closure']:
  assert git_ref(SHA,item['path'])==item
source_inputs=native['input_closure']
card_path='policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/FRY-01.md'
card=git_ref(SHA,card_path)
docs=load(AUTHOR/'state-docs.json'); supplement=load(AUTHOR/'state-docs-reconciled.json')
assert docs['source']==SHA and docs['exit_code']==0 and docs['outcome']=='PASS'
assert supplement['source']==SHA
for key in ['config','stdout','stderr','rendered_output']: verify_ref(docs[key])
verify_ref(supplement['original_run']);verify_ref(supplement['rendered_output'])
docs_bindings=[binding(x['path'],x) for x in docs['source_inputs']+supplement['additional_directive_source_inputs']]
install=load(AUTHOR/'docs-install-inputs.json');verify_ref(docs['environment']['installation_input'])
assert install['source_sha']==SHA and len(install['packages'])==33
assert git_ref(SHA,'policy-engine/uv.lock')['sha256']==install['uv_lock_sha256']
assert git_ref(SHA,'policy-engine/pyproject.toml')['sha256']==install['pyproject_sha256']
assert file_ref(AUTHOR/'docs-locked-requirements.txt')['sha256']==install['requirements_sha256']
class IDs(HTMLParser):
 def __init__(self): super().__init__(); self.ids=set()
 def handle_starttag(self,tag,attrs):
  for key,value in attrs:
   if key=='id' and value is not None:self.ids.add(value)
p=IDs();p.feed(Path(docs['rendered_output']['path']).read_text())
counts={namespace:sum(i.startswith(namespace) for i in p.ids) for namespace in docs['api_directives']}
assert counts==supplement['rendered_directive_namespace_anchor_counts'],counts
for anchor in docs['rendered_native_layout_anchors']+supplement['rendered_state_and_executor_anchors']:assert anchor in p.ids,anchor
installed=load(AUTHOR/'layout-installed-equivalence.json')
assert installed['source']==SHA
installed_bindings=[]
for item in installed['source_equivalence']:
 rows=[git_ref(ref,item['path']) for ref in item['sources']]
 for row in rows:
  expected=item['sources'][row['git_ref']]
  assert all(row[k]==expected[k] for k in ['git_blob','sha256','bytes'])
 assert rows[0]['sha256']==rows[1]['sha256']
 installed_bindings.extend(rows)
original=installed['original_installed_receipt']; receipt_ref=git_ref(original['git_sha'],original['path'])
assert all(receipt_ref[k]==original[k] for k in ['sha256','bytes'])
installed_logs=[]
for check in installed['reconciled_existing_checks']:
 actual=git_ref(original['git_sha'],check['output'])
 assert actual['sha256']==check['output_sha256'] and actual['bytes']==check['output_bytes']
 data=git('show',f"{original['git_sha']}:{check['output']}").decode()
 assert all(line in data for line in check['observed_census_lines'])
 installed_logs.append(actual)
author=load(AUTHOR/'family-layout-frozen-checks.json')
author_verified=[]
for check in author['checks']:
 assert check['target_sha']==SHA
 for key in ['stdout','stderr']:author_verified.append(verify_ref(check[key]))
assert author['checks'][-1]['outcome']=='ERROR' and author['checks'][-1]['exit_code']==1
assert not git('status','--porcelain=v1') and git('rev-parse','HEAD').decode().strip()==SHA
custody=dict(source_inputs=source_inputs,original_card=card,docs_inputs=docs_bindings,docs_run=file_ref(AUTHOR/'state-docs.json'),docs_supplement=file_ref(AUTHOR/'state-docs-reconciled.json'),rendered_output=docs['rendered_output'],namespace_anchors=counts,installed_source_bindings=installed_bindings,existing_git_files=installed_logs+[receipt_ref],author_output_byte_checks=author_verified)
(OUT/'evidence-custody-audit.json').write_text(json.dumps(custody,indent=2)+'\n')
checks=[]
for name,run in [('independent_native40',native),('real_compile_scientist_cas_freshreader',compiler),('layout_path_corruption_after_real_cas',negative)]:
 checks.append(dict(name=name,outcome=run['outcome'],command=run['command'],target_sha=SHA,output=run['output'],output_ref=run['output_ref'],execution_ref=file_ref(OUT/(run['mode']+'.json')),counts=run['counts'],exit_code=run['exit_code']))
checks.extend([
 dict(name='full_state_page_docs_custody_and_native_directives',outcome='PASS',command='Read-only full byte/hash/source and rendered HTML ID verification; original real MkDocs command in referenced run',target_sha=SHA,output=str(OUT/'evidence-custody-audit.json'),output_ref=file_ref(OUT/'evidence-custody-audit.json'),actual_namespace_anchor_counts=counts,original_run=file_ref(AUTHOR/'state-docs.json'),original_backend_preflight='ERROR: MkDocs missing in application environment; preserved separately, never promoted'),
 dict(name='installed_layout_source_equivalence_and_full_deciding_output_custody',outcome='PASS',command='git show exactsource:path and committed installed receipt/output full-byte verification; no installed rerun',target_sha=SHA,output=str(OUT/'evidence-custody-audit.json'),output_ref=file_ref(OUT/'evidence-custody-audit.json'),existing_git_files=installed_logs,scope='Only unchanged IR slot owner and two compatibility facades, original wheel/sdist 13+13 tests; no new full FRY installed composition'),
 dict(name='global_production_and_unknown_external_retirement',outcome='UNRUN',command='Not executed: outside original bounded migration criterion and current admitted review inputs',target_sha=SHA,output='Full-project docs/global IC/admitted production studies/unknown third-party wrapper retirement not established')])
review=dict(schema='policyos.e02.independent-review.v1',reviewer='F/fit_tmle independent of foundry author',source_sha=SHA,source_tree=TREE,specification_verdict='GO within original LA002/LA037 migration criteria',engineering_quality_verdict='GO for exact three-path consumer/docs completion; no blocking defect found',closure_decision='Root/G decides canonical closure; this review does not widen source or install scope',checks=checks,per_id=[
 dict(id='LA-002',verdict='bounded GO',criterion='Canonical four family declarations preserve IDs/parameters/assumptions/unknown-ID behavior; IR owns certificates; real finite PolicySpec→CAS→IC service/certificate consumers and registered method loading distinguish declarations from runtime mechanisms',deciding_checks=[0],limitations='No universal IC statement, no catalog membership as certificate, no four newly invented family→runtime state maps; five runtime classes loaded, only income_tax executes in added state test'),
 dict(id='LA-037',verdict='bounded GO',criterion='Canonical IR five-object layout identity, existing facades direct to owner, slot IDs/registry/unbound/order/family semantics and actual compile→Scientist→CAS/freshreader + kernel→PatchOps→state CAS readback retained; maintained state docs actual three native API directives render',deciding_checks=[0,1,2,3,4],limitations='Two known compatibility facades retained; unknown external retirement and whole-project docs/full latest installed FRY composition not established'),
 dict(id='LA-001',verdict='not re-adjudicated',criterion='Previously implemented source-bound RNG/Treasury migration remains separate prior receipt; no fresh RNG acceptance claim from these tests',deciding_checks=[],limitations='No new random-stream law changes in exact three-path review')],test_quality_observations=[
 'The selected trinity unit happy path mocks pipeline construction. Fresh independent compile_artifact_contracts native selector supplies genuine current compiler outputs, Scientist consumer, stable repeats and CAS readback.',
 'New income_tax test uses real registered kernel and actual PatchOps/state/CAS, but constructs PatchOps directly rather than executing compile_trinity. Kept distinct from separate actual compiler consumer.',
 'Independent negative keeps canonical function identity/types/slot IDs/registry and changes only government.balance state path to tax_rate; all three addresses fail after actual CAS readback (0 versus independently expected 16). Marker/census or reflection alone cannot pass this oracle.'
 ],limits=['Synthetic finite properties are not admitted production/global certificate authority','Default Python3.14 DoWhy/EconML marker absence is not positive backend evidence','Full architecture/full integration/full docs not run; no generic inherited failure attribution','Scoped real docs warnings and initial missing-backend ERROR retained separately'],input_custody=file_ref(OUT/'evidence-custody-audit.json'),source_worktree='clean, attached, unchanged exact7f before/after independent execution and audit',production_writes=False)
(OUT/'review.json').write_text(json.dumps(review,indent=2)+'\n')
selected=['replay_review.py','layout_readback_removal.py','finish_review.py','native40.json','native40.stdout.txt','native40.stderr.txt','compiled1.json','compiled1.stdout.txt','compiled1.stderr.txt','negative3.json','negative3.stdout.txt','negative3.stderr.txt','evidence-custody-audit.json','review.json']
selection=dict(schema='policyos.e02.transfer-selection.v1',source_sha=SHA,files=[file_ref(OUT/name) for name in selected],existing_git_files=installed_logs+[receipt_ref],exclusions=['No copied tracked card/source bodies or redundant installed deciding logs','Caches/temp CAS/test stores excluded; no unique deciding observation omitted'],sanitation='None: complete original native/negative stdout retained; if transported as lossless JSON/gzip preserve decoded SHA256/bytes',total_unique_bytes=sum(file_ref(OUT/name)['bytes'] for name in selected))
(OUT/'transfer-selection.json').write_text(json.dumps(selection,indent=2)+'\n')
print(json.dumps(dict(verdict='bounded GO',review=file_ref(OUT/'review.json'),selection=file_ref(OUT/'transfer-selection.json'),source=SHA,native=40,compiled=1,negative_fail=3,docs_native_anchors=counts)))
