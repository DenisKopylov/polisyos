"""Publish moderate immutable independent harness receipt; never execute wave."""
from pathlib import Path
import hashlib, importlib.metadata, importlib.util, json, os, subprocess, sys, types
R=Path('/workspace/e02-E-continuation-20261006');P=R/'policy-engine';O=Path(__file__).parent
REF='4758d495abb81aa51fea8e28cd071ca9ff989155'
W=P/'docs/research/e02-cloud-test-plan/implementation-handoffs/E/continuation-20261006/pr38-r2/wave-controls'
s=importlib.util.spec_from_file_location('harness_freeze_plan',W/'plan_wave.py');m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m)
a=types.SimpleNamespace(repo=R,candidate=REF,output_root=O/'snapshot-unexecuted-wave',comparison_base='198076863e143dea9f89f02734b13d50dae3eed5',no_owner_packets=False)
plan=m.prepare(a)
assert plan['execution_state']=='NOT_RUN'
assert len(plan['changed_python_lint_paths'])==211
assert sum(x.startswith('docs/') for x in plan['changed_python_lint_paths'])==109
(O/'plan-snapshot.json').write_text(json.dumps(plan,indent=2)+'\n')
def ref(path):
 data=path.read_bytes();return {'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)}
inputs=[str(p.relative_to(R)) for p in W.glob('*.py')]+[str((W/'README.md').relative_to(R)),str((W/'proposal.json').relative_to(R)),str((W/'original-wave-groups.json').relative_to(R)),'policy-engine/pytest.ini','policy-engine/ruff.toml','policy-engine/pyproject.toml','policy-engine/uv.lock','policy-engine/tools/devx/workspace/ci_parity.py','policy-engine/tools/devx/workspace/verify.py','policy-engine/tools/devx/workspace/_common.py','policy-engine/apps/runtime-dashboard/package.json','policy-engine/pnpm-lock.yaml']
source_inputs={}
for name in inputs:
 path=R/name
 data=subprocess.check_output(['git','show',REF+':'+name],cwd=R)
 assert path.read_bytes()==data, name
 source_inputs[name]=ref(path)
patch=Path('/workspace/e02-E-pr38-r2-receipts/harness-configured-repair-7bc65f73-20261006/v2/wave-controls-configured-repair-v2.patch')
assert ref(patch)['sha256']=='935428d3f81693dd80a3f9f89f0b1d1ff21a1c689666950c7ef59c00624cadbb'
modules=['pytest','ruff','defusedxml','pytest-benchmark','playwright']
versions={}
for n in modules:
 try:versions[n]=importlib.metadata.version(n)
 except importlib.metadata.PackageNotFoundError:versions[n]='not-a-Python-package; JS identity in browser receipt' if n=='playwright' else 'UNAVAILABLE'
commands=[{'argv':[str(P/'.venv/bin/python'),str(O/'harness_review.py')],'cwd':str(P),'environment':{'UV_NO_SYNC':'1'},'stdout':'harness-review.stdout','exit_code':0,'scope':'Independent metadata/native mocked-safety/JUnit controls only; no numeric/CI process.'}]
py_files=[str(x.relative_to(P)) for x in W.glob('*.py')]
for option,output in [('check','configured-ruff.stdout'),('format','configured-format.stdout')]:
 argv=[str(P/'.venv/bin/python'),'-m','ruff',option]
 if option=='format':argv+=['--check']
 argv+=['--no-cache',*py_files]
 commands.append({'argv':argv,'cwd':str(P),'environment':{'UV_NO_SYNC':'1'},'stdout':output,'exit_code':0,'scope':'Three changed harness files only with actual repo ruff.toml; not full changed-Python gate.'})
review={'schema':'policyos.e02.independent_harness_review.v1','candidate':REF,'tree':'c10843f74311d6973ccefea609cd7bf34bc828fe','base':'c79de1a8779482cf485317039fe12e3570ae2273','reviewer':'E DoE author, independent from root/FRC harness writers; read-only, no source edits/children','verdict':'GO-bounded-owned-harness-readiness-and-preservation','source_inputs':source_inputs,'author_patch':{'path':str(patch),**ref(patch)},'property_controls':'harness-independent-review.json','denominator_correction':'denominator-correction.json','commands':commands,'environment':{'interpreter':sys.executable,'python':sys.version,'packages':versions,'capability_receipt':'browser-capability-receipt.json','runtime_plan_selected_environment':plan['environment']},'input_denominators':{'native_test_paths':120,'A_owner_packet_paths':2,'total_test_file_inputs':122,'native_groups':7,'planned_Ruff_changed_Python_exact4758':211,'docs_witnesses_in_Ruff_denominator_exact4758':109,'focused_configured_Ruff_files':3,'runtime_test_cases':'UNRUN until actual JUnit; parametrization cannot be inferred from AST count'},'predicate_basis':{'scratch_admission':'Path.exists OR Path.is_symlink before prepare/output exclusive mkdir; every numerical basetemp admitted before marker/importer and immediately before run. Negative removes actual function code while retaining names and identity, with fake process spy only.','pytest_defaults':'Actual repository pytest.ini importlib/strict-markers/cacheprovider kept, per-group cache_dir and benchmark storage overridden only to fresh unique paths.','stages':'Exact original numerical files preserved plus owned deltas/dependencies; canonical verify/ci-parity command factories retain doctor/backend/runtime/docs/frontend/browser according to actual declared options.','JUnit':'Actual defusedxml parser recomputes four independently supplied outcomes; DTD refusal checked.','browser':'Actual installed dashboard Playwright1.59.1 persistent Chromium147 launches and renders text4; binary/hash/package/native stdout recorded.'},'limitations':['No numeric or full CI stage launched. Browser capability is not doctor, browser-suite, full CI or finding closure.','Actual common freeze candidate will include later receipt-only files; root must recompute full changed-Python denominator on that candidate. No inherited-red attribution or waiver.','Seven cloud numerical groups run without artificial caps; shared canonical generator/build/npm caches use serialized gate schedule. Atomic Hypothesis cache and post-command observer limitations remain in root final wave receipt.','All historical scripts/stdout preserved. Initial docs-count summary0 was reviewer prefix error corrected to109 without changing plan selection.','B194/B197/B201/B202 held and other historical finding ledger statuses are not changed by harness GO.'], 'next_owner':{'E_root':'Copy moderate immutable packet, freeze one reviewed clean candidate and run common numerical/global wave once, recording native JUnit/fail-fast/UNRUN outcomes separately.','G':'Review code admission separately from original criterion/finding owner decisions; exact production history checks remain local read-only.'},'cleanup':{'native_trash_available':False,'permanent_deletion_performed':False,'candidates_after_deciding_receipts_and_no_active_users':[str(O/'chromium-profile'),str(O/'preservation-controls')],'preserve':[str(O),'product code/docs/source/law identities; original stdout and unique receipt data'],'large_profile_excluded_from_Git':True}}
(O/'review.json').write_text(json.dumps(review,indent=2)+'\n')
print(json.dumps({'review_sha256':ref(O/'review.json')['sha256'],'source_inputs':len(source_inputs),'numeric_wave':'UNRUN','verdict':review['verdict']}))
