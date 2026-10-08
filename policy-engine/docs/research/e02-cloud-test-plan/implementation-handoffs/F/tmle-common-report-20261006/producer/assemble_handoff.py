from pathlib import Path
import hashlib,json,subprocess,sys
ROOT=Path("/workspace/e02-F-tmle-20261006"); OUT=Path(__file__).parent
REF="6c711bd2d4f1b6bf851c42a5f3d22b795efb020d"; TREE="e035bb5cdf9bde154fe08bcb72a0341cfeb2a970"
BASE=Path("policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/F/tmle-common-report-20261006")
def git(*args):return subprocess.check_output(["git",*args],cwd=ROOT).decode().strip()
def sha(data):return hashlib.sha256(data).hexdigest()
def bind(path,ref=REF):
 data=subprocess.check_output(["git","show",f"{ref}:{path}"],cwd=ROOT)
 return dict(git_ref=ref,path=path,git_blob=git("rev-parse",f"{ref}:{path}"),bytes=len(data),sha256=sha(data))
assert git("rev-parse","HEAD")==REF
own=json.loads((OUT/"producer-transfer-pre-review.json").read_text())
indroot=Path("/tmp/e02-F-continuation-20261006/cau/tmle-review")
ind=json.loads((indroot/"transfer-selection.json").read_text())
files=own["files"]+[dict(row,group="independent") for row in ind["files"]]
# Also preserve the reviewer selection itself; all33full companions remain byte-bound.
for path,group in [(indroot/"transfer-selection.json","independent"),(OUT/"producer-transfer-pre-review.json","producer"),(OUT/"assemble_handoff.py","producer")]:
 data=path.read_bytes();files.append(dict(path=str(path),group=group,bytes=len(data),sha256=sha(data)))
assert len({row["path"] for row in files})==len(files)
artifacts=[];mapping={}
for row in files:
 source=Path(row["path"]);data=source.read_bytes();assert len(data)==row["bytes"] and sha(data)==row["sha256"]
 relative=BASE/row["group"]/source.name
 encoded=source.suffix==".txt"
 if encoded:
  relative=Path(str(relative)+".json")
  stored=(json.dumps({"schema":"policyos.e02.lossless_utf8_output.v1","text":data.decode("utf-8")},ensure_ascii=False,indent=2)+"\n").encode()
  assert json.loads(stored)["text"].encode()==data
 else:stored=data
 target=ROOT/relative;target.parent.mkdir(parents=True,exist_ok=True);assert not target.exists();target.write_bytes(stored)
 artifact=dict(path=str(relative),bytes=len(stored),sha256=sha(stored),original_path=str(source),decoded_bytes=len(data),decoded_sha256=sha(data),lossless_utf8_json=encoded)
 artifacts.append(artifact);mapping[str(source)]=artifact
assert len({x["path"] for x in artifacts})==len(artifacts)
def output(path):return mapping[str(Path(path))]["path"]
def execution(name,outcome,summary,folder=OUT,counts=None):
 raw=json.loads((folder/name).read_text())
 argv=raw.get("argv",raw.get("command",name));stdout=raw.get("output",raw.get("stdout"));stderr=raw.get("stderr")
 row=dict(command=argv,outcome=outcome,output=output(stdout) if stdout and str(stdout) in mapping else output(folder/name),execution_receipt=output(folder/name),summary=summary,exit_code=raw.get("exit_code"),source_sha=raw.get("source_sha",raw.get("candidate_sha")),source_tree=raw.get("source_tree",raw.get("candidate_tree")),cwd=raw.get("cwd"),environment=raw.get("environment"))
 if stderr and str(stderr) in mapping:row["stderr"]=output(stderr)
 if counts:row["actual_counts"]=counts
 return row
checks=[]
checks.append(execution("native-frozen.json","PASS","Frozen6file native suite; every configured/default fold executes, original cache/binary/EIF laws and noncausal Confidence profiles retained. Known synthetic DGP only.",counts=dict(passed=167,failed=0,errors=0,skipped=0,warnings=127,warning_kinds="126 native sklearn/LGBM feature-name; one existing ValidationProfile deprecation")))
checks.append(execution("baseline-red-v2.json","FAIL","Genuine baseline configured MethodJob rejects undeclared parameters before fitting; original baseline admission/refusal, not candidate PASS.",counts=dict(failed=1,passed=0,errors=0)))
for mode,summary in [("adjustment_basis","Removing typed confounders retains class/signature/slots and real fit; adjustment basis assertion fails."),("native_interval","Widening only report CI retains SUCCESS/profile/core results and ABI; exact native interval consumer fails."),("limited_disposition","Promoting actual clustered limited result to SUCCESS with fabricated CI retains markers; point-free disposition consumer fails.")]:
 checks.append(execution("removal-"+mode+".json","FAIL",summary,counts=dict(failed=1,passed=0,errors=0,warnings=1)))
checks.append(execution("native.execution.json","FAIL","Independent original50selectors:49PASS and1 own tuple/list JSON comparison harnessFAIL; full127warnings retained. No product defect inferred.",folder=indroot,counts=dict(passed=49,failed=1,errors=0,skipped=0,warnings=127)))
checks.append(execution("native-corrected.execution.json","PASS","Four independent real-consumer selectors; separatePythonCASreader; NormalDist95% and independent EIF SE. Actual two optional-adapter CanonViolation artifact_write_failed stderr diagnostics retained.",folder=indroot,counts=dict(passed=4,failed=0,errors=0,skipped=0)))
for name,summary in [("removal-se-corrected.execution.json","Same ABI: real projected SE doubled, independent EIF law rejects it."),("removal-order-corrected.execution.json","Same4columnshape: W-before-X order changes2400values; actual requested adjustment basis rejects it.")]:
 checks.append(execution(name,"FAIL",summary,folder=indroot,counts=dict(failed=1,passed=0,errors=0,warnings=1)))
checks.append(execution("alias.execution.json","PASS","Actual canonical public/catalog producer class/factory identity, real factory invoke and trusted-function pickle.",folder=indroot))
checks.append(execution("metadata-frozen.json","PASS","Owned structured fragment0errors0findings, Ruff, testformat, actual schema enum36→37. Existing base report doc-description differs from older snapshot; no new field/schema-version delta."))
invest=Path("/tmp/e02-F-continuation-20261006/tmle-bridge-investigation")
checks.append(execution("pool-v2.json","PASS","Historical exact4a real registered commonNode/LocalWorkerPool refusal twice with execution_context_missing;0folds. This PASS describes refusal investigation, not production admission.",folder=invest))
checks.append(execution("jobdefault-v3.json","PASS","Historical exact4a genuine default15fold MethodJob and fresh normalized CAS result; old result-only producer. No all-deployment budget or accuracy claim.",folder=invest))
checks.append(dict(command="Current admitted Runtime common TMLE study with actual appointed context/verifier, workload and deployment budget",outcome="UNRUN",output=output(invest/"feasibility-packet.json"),summary="B56 limited; owner packet and actual current common-node admission/wait/resource trace missing."))
checks.append(dict(command="Existing accepted source/graph/estimand/target identification issuer/verifier fresh challenge",outcome="UNRUN",output="No legitimate identification issuer/verification bridge supplied; numerical SUCCESS/CI remains candidate/non-gating."))
checks.append(dict(command="Root actual Node HTE intake/report reconciliation +generated schema/catalog +composed integration/installed production",outcome="UNRUN",output="Separate root/metadata companion ownership; this producer receipt establishes no common-node positive, installed fullgraph or full architecture verdict."))
checks.append(execution("baseline-red.json","ERROR","Originalpytestbasetemp parent absent; setupERROR preserved. Corrected actual baseline-red-v2 is1FAIL.",counts=dict(errors=1)))
checks.append(execution("native-draft.json","FAIL","42PASS1own tuple/list JSON-roundtrip comparisonFAIL; corrected canonical JSON comparison in frozen source.",counts=dict(passed=42,failed=1,errors=0)))
checks.append(dict(command=["/workspace/e02-F-closeout-20261006/policy-engine/.venv/bin/python",str(OUT/"check_metadata.py")],outcome="ERROR",output=output(OUT/"metadata-v1-recaptured.stderr.txt"),execution_receipt=output(OUT/"metadata-v1-recaptured.json"),summary="Whole snapshot comparator differs only pre-existing admitted report documentation description; v2 binds unchanged base description and checks exact enum-only new producer footprint."))
recovery=OUT/"recovery"
checks.append(dict(command=["python3",str(recovery/"finish_forward_recovery.py")],outcome="PASS",output=output(recovery/"forward-recovery.json"),summary="Storage interrupted merge recovered forward only; original385partial files snapshotted, exact1115Git targetpaths completed/staged, index tree equals47a, ordinary recovery+merge commits; no deletion/reset/rewrite."))
checks.append(execution("admission-resume-v2-execution.json","PASS","Actual exactbranch/path doctorresume admitted after forward recovery.",folder=recovery))
checks.append(execution("admission-resume-execution.json","ERROR","Initialdirectdoctor script invokedrelativeimports incorrectly; module invocation separately admitted.",folder=recovery))
paths=git("diff","--name-only",REF+"^",REF).splitlines()
packet=json.loads((invest/"feasibility-packet.json").read_text());review=json.loads((indroot/"review.json").read_text())
card="policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundles/FIT-01.md";manifest="policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundle_manifest.json";owners="policy-engine/docs/research/e02-cloud-test-plan/execution-organization/finding-owners.tsv"
prior=json.loads((ROOT/"policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/F/tmle-20261006.json").read_text())
handoff=dict(schema="policyos.e02.implementation_handoff.v1",unit="F",slice="tmle-common-report-20261006",closure_ids=[],finding_ids=["B54","B56"],related_finding_ids=["B54","B56"],bundle_ids=["FIT-01"],slice_base_sha="66588374da9f407a870880be675b5c751aef44da",original_topic_sha="d23f004d4f0ed442bc00dae634ed73c6b80275d5",implementation_commits=[REF],candidate_tree_sha=TREE,branch="codex/e02-F-tmle-20261006",pull_request="https://github.com/DenisKopylov/polisyos/pull/50",changed_paths=paths,source_identity=[bind(path) for path in paths],criterion_inputs=[bind(card),bind(manifest),bind(owners)],environment=json.loads((OUT/"native-frozen.json").read_text())["environment"],checks=checks,property="Native configured cross-sectional TMLE MethodJob emits preserved descriptive result plus canonical candidate/point-free failure report and envelope; trueHTEadjustmentbasis, public32defaults, exactnativeEIF and actualCASreaders, no new authority or scheduler.",predicate_basis="Native numerical property on known randomized synthetic DGP and actual persisted consumer ABI; no admitted real-data identification or sampling authority.",capability_state_or_finding_state="Producer/common-report seam implemented and independently boundedGO; B54 prior technical closure freshly revalidated; B56 actual admitted production workload/budget limited.",per_id=[dict(finding_id="B54",criterion="Diagnostic-only policy refresh preserves fitting; changed data/seed/split/config requires correct refit; returned reader cannot change future hits; content hashes and access scope retained.",outcome="PASS",state="prior technical closure revalidated; no new closure claim",check_refs=[0],prior_primary_receipt="policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/F/tmle-20261006.json@f460bd81b8124be58f890f59a53e2aba9e7ceb76",numerical_core_unchanged=output(OUT/"unchanged-neighbor-proof.json")),dict(finding_id="B56",criterion="Under the actual admitted shared study resource, total admitted work is bounded and waits without lost results; identical folds/repeats/seeds execute and numerical/provenance results agree, with active/wait/wall/memory measurements.",outcome="UNRUN",state="limited",implemented_companion="Actual typedHTE/configuredMethodJob→numericalresult/canonicalreport/envelope→CAS/freshPythonreader",check_refs=[0,6,11,12,13],next_owner="Runtime/C/G canonical actual context/verifier/workload/deploymentbudget; root current commonNode consumer")],independent_review=dict(decision=review["decision"],output=output(indroot/"review.json"),source_sha=REF,original_native_outcome="FAIL",corrected_native_outcome="PASS",limitations=review["limitations"]),owner_packet=packet["minimum_owner_packet"],falsifier=packet["falsifier"],limitations_and_next_owner=["Regular IID/exchangeability/populationpositivity/consistency are caller asserted; observed positivity and syntheticDGP do not admit realdata.","Unsupportedprofiles preserve actual descriptiveresult but report is point-freeASSUMPTION_FAILED/NUMERICAL_FAILURE; failureenvelope is heuristic sentinel, not manufacturedCI.","Runtime actualcommonpool ports/workload missing; historicalsameclass refusal before0fits retained, productionB56UNRUN.","Newenumreader/schema/catalog coherent deployment required; oldenumreaders cannot read newtmle reports. Root companion not claimed by this primary.","Independent correctedstdoutPASS contains two optionaladapter artifact_write_failed/CanonViolation stderr diagnostics; actualmethodresult/evidence/freshreader succeed. No globalzeroERROR/ABI/architecture claim."],baseline_cells=prior["baseline_cells"],baseline_source_grade="Navigation-only compact source; raw archives absent, routes not candidate PASS. Original source SHA/backendmarkers preserved in prior query artifacts.",artifacts=artifacts,artifact_policy="Complete moderate decidinglogs/rawwarnings/errors and scratchreplayers transported byte-for-byte or losslessUTF8JSON; hashes decoded/stored. Trackedsource/card bodies and Gitderivedtargetviews referenced immutably, not copied. Temporarypartial recovery backups remain /tmp, unique snapshot classifications/hash custody retained.",recovery=dict(output=output(recovery/"forward-recovery.json"),merge_commit="66588374da9f407a870880be675b5c751aef44da",target_root="47a2ff90186628afafa4c01ecf7158325b0026fc",target_tree="d7f5e47193b7049fd06b7a59e0a759b796e0934a",first_add_ignored_paths="Retained actualexit1; scopedforce-add onlyGit-targetpaths completed exacttargettree, no unrelatedfiles."),closure_id_semantics="Empty: companion bridge does not close actualproductionB56 and does not republish existingB54technicalclosure.",further_verification="G runs exact final integratedcandidate with actualowneradmitted input/study/budget packet locally; retain full folds/seeds/configs/competingjobtrace and current Runtime context plus sourcebound freshreader. Fullproductioninputs remain local.")
for row in checks:
 assert isinstance(row["output"],str) and row["outcome"] in {"PASS","FAIL","UNRUN","ERROR"}
target=ROOT/Path(str(BASE)+".json");target.write_text(json.dumps(handoff,ensure_ascii=False,indent=2)+"\n")
selection=dict(schema="policyos.e02.transfer_selection.v1",source_sha=REF,artifacts=artifacts,primary_path=str(target.relative_to(ROOT)))
(OUT/"published-transport.json").write_text(json.dumps(selection,indent=2)+"\n")
print(json.dumps(dict(primary=str(target.relative_to(ROOT)),primary_bytes=target.stat().st_size,primary_sha256=sha(target.read_bytes()),artifacts=len(artifacts),decoded_bytes=sum(x["decoded_bytes"] for x in artifacts),stored_bytes=sum(x["bytes"] for x in artifacts))))
