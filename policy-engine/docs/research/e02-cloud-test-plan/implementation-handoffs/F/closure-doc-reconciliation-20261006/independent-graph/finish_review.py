"""Finalize independent bounded doc review and full deciding-output transport selection."""
import hashlib,json,pathlib,subprocess
D=pathlib.Path(__file__).resolve().parent
R=pathlib.Path('/workspace/e02-F-economics-20261006')
SHA='99f196be45dec7acabdc05f0cb3af5430ec94c9e';TREE='18711c5732863a4e50672112c7f3c5ba4a1b229b';BASE='d9c48853c5ab9ad7473df204bf3a7a1995a32057'
def ref(p):
 p=pathlib.Path(p);b=p.read_bytes();return {'path':str(p),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest(),'full':True}
z=json.loads((D/'deciding-output.json').read_text());assert z['check']=='PASS' and z['candidate_sha']==SHA
coverage=json.loads((D/'coverage.stdout.txt').read_text());assert coverage['bundles']==127 and coverage['findings']==282 and coverage['count_preserving_controls_rejected']==4
report={
 'role':'independent_read_only_documentation_semantic_review','reviewer':'graph_scm','check':'PASS','decision':'GO_bounded_docs_only','outcome':'limited',
 'candidate_sha':SHA,'candidate_tree':TREE,'slice_base_sha':BASE,'source_refs':z['source_refs'],'changed_paths':z['changed_paths'],'findings':[],
 'property':'Three F closure-decision documents reconcile their explicit current bounded scientific/consumer recommendations to actual immutable original criteria/source-specific receipts while preserving historical G97/C–E and separating acceptance/authority/unavailable inputs.',
 'predicate_basis':'independently_reconciled','source_begin_end_stable':True,
 'semantic_decisions':[
  {'subject':'Original LA004 vs new Gini property','check':'PASS','basis':'Original LA_r09:167–197 explicitly distinguishes fiscal/labor model laws; document requires equal regimes/deliberate divergence/accounting/seed/outputs and keeps Gini current-domain semantics separate. No welfare choice or Gini law substitutes for LA004. LA035 formula/intent held; LA003 fiscal decimal precision limited.'},
  {'subject':'F-M5 fixed estimand, estimated shares, Mammen/null/test inversion','check':'PASS','basis':'Pinned cebe source score ratio term, decimal integer threshold and actual closed effect-scale tail inversion inspected. Real head-DGP rawdecoded result has160datasets/arm,154covered/arm,6nullrejects and160alternativerejects. Source0b diagnostic/caller work is explicitly not a new160-DGP wave.'},
  {'subject':'F-M6 actual native RDD vs external development oracle','check':'PASS','basis':'Full immutable RDD15a source/output JSON and product source inspected. Clean-room native module imports no rdrobust;4036actualdifferentialcases,1879/2000 and1877/2000coverage, maxCI3.658229275060876e-11. Corrected noRBC removal full4036has12108differencefailures and1687/1676coverage. Native .8/.95/.99 consumer profile bound; no invented .90/external mandatory runtime extra. GPL concerns external product bundling only.'},
  {'subject':'B225 independent stochastic-tail oracle','check':'PASS','basis':'Exact6d test uses math.erfc NormalCDF and positive-tail survival differences, includes8..9 and-12..-10. Independent of SciPy sampler, no same-library-CDF independence assertion.'},
  {'subject':'Historical G97 and nonF sections/anchors','check':'PASS','basis':'All3base blobs match root53afa776. Full C/D/E method and runtime section bytes unchanged; C/D/E profile rows unchanged; all16F-M anchors/17Fbundleanchors retained. Historical34partial+B219held plan is explicitly historical, no backdated acceptance.'},
  {'subject':'Current criterion/source bindings and residual split','check':'PASS','basis':'Exact35IDs/36originalbindings/35uniqueblocks; tablecurrent21closed/13limited/1held matches complete draft. Technical26/8/1 recommendation remains separately labelled. All10registryJSONs/148checks byte/tree-bound;16explicit receipt carriers plus graph-cache explicit samecarrier context actuallyread. No prefix-only source inference.'},
  {'subject':'Pending API/TMLE, native profiles, G and real authority','check':'PASS','basis':'Pending new packets never promoted toPASS; Python3.14DoWhy/EconML marker omissions notwitnesses; installed profiles retainedexactsource; G_acceptance=UNRUN all35. SyntheticDGP and cache/ABI outcomes do not acquire real data/causal authority.'}
 ],
 'checks':[
  {'command':['python3',str(D/'review_docs.py')],'target_sha':SHA,'environment':'SystemPython scratch read-onlyGit/docs/JSON; no imported numericalbackend/sourcewrites','input_closure':'Complete3changed docs, full35originalcard hashes,10current148checkreceipts,17citation bindings, actualDID/RDD rawoutputs and exactoracle source','outcome':'PASS','output':str(D/'deciding-output.json'),'execution_stdout':ref(D/'reconciliation.stdout.txt'),'execution_stderr':ref(D/'reconciliation.stderr.txt')},
  {'command':['/workspace/e02-F-closeout-20261006/policy-engine/.venv/bin/python','policy-engine/docs/research/e02-cloud-test-plan/closure-decisions/validate_coverage.py','--self-check'],'target_sha':SHA,'environment':'Readonly applicationPython3.14.7; PYTHONDONTWRITEBYTECODE1; cwd /workspace/e02-F-economics-20261006','input_closure':'Existing full canonical planningcoverage127bundles282IDs291sourcebindings +all6taskdocs; bookkeeping only, not scientificproof','outcome':'PASS','output':str(D/'coverage.stdout.txt'),'stdout_ref':ref(D/'coverage.stdout.txt'),'stderr_ref':ref(D/'coverage.stderr.txt'),'count_preserving_controls_rejected':4}
 ],
 'complete_deciding_output_ref':ref(D/'deciding-output.json'),
 'harness_history':[{'check':'ERROR','scope':'Initial reviewer whole-worktree cleanliness assertion wrongly included newly untracked author receipt pack; frozen3tracked doc bytes/HEAD/tree remained99f196. Corrected tracked-source admission only; source mutation not alleged.','stdout_ref':ref(D/'reconciliation-initial.stdout.txt'),'stderr_ref':ref(D/'reconciliation-initial.stderr.txt')},{'check':'ERROR','scope':'Reviewer guessed17literalpath@SHA citations; actual16plus docexplicit graph-cache samecarrier context. Corrected all16literal actualrefs+1named samecarrier locator; no dropped reference or author documentation defect.','stdout_ref':ref(D/'reconciliation-citation-harness.stdout.txt'),'stderr_ref':ref(D/'reconciliation-citation-harness.stderr.txt')}],
 'scientific_reruns':False,'product_writes':False,'environment_mutations':False,'closure_ids':[],
 'limits':['Docs-only source99f196 recommendation; no new composed-runtime or CI/architecture/schema/productionPASS.','No ledgerGclosure or real causal/semantic owner adjudication.','Portable originalCAU235804/full9companion pack is author-owned separate append; this review binds its actual original scratch bytes but does not claim publication accepted before carrier receipt readback.','Existing scientific waves stay source-specific and are not relabelled on this docs branch.','No global P41 inherited-red assertion inferred.'],
 'author_hold_release':'Frozen3document source reads complete. Author may append own receipt/portable transport as authorized; no new scientific execution requested.'
}
(D/'review.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
files=[D/'review.json',D/'deciding-output.json',D/'review_docs.py',D/'finish_review.py']
for stem in ['coverage','reconciliation','reconciliation-initial','reconciliation-citation-harness']:
 for stream in ['stdout','stderr']:files.append(D/(stem+'.'+stream+'.txt'))
selection={'candidate_sha':SHA,'candidate_tree':TREE,'check':'PASS','decision':'GO_bounded_docs_only','unique_full_files':len(files),'items':[ref(p) for p in files]};selection['full_bytes']=sum(x['bytes'] for x in selection['items']);(D/'transfer-selection.json').write_text(json.dumps(selection,indent=2)+'\n')
print(json.dumps({'review':ref(D/'review.json'),'transfer_selection':ref(D/'transfer-selection.json'),'files':len(files),'full_bytes':selection['full_bytes']}))
