#!/usr/bin/env python3
"""Freeze the unique independent reviewer output selection; scratch writes only."""
import collections
import gzip
import hashlib
import json
import pathlib
import platform
import subprocess
import sys

HERE=pathlib.Path(__file__).resolve().parent
OLD=HERE.parent/'root-current35-review'
REPO='/workspace/e02-F-closeout-20261006'
PRIMARY='46cc03546f2572986962555ddf04d858163c1cf6'
FINAL='cdf61b4500e355a27db14260e80ce673ddf8869e'
CONTROLS=['remove-original-binding','wrong-card-hash','missing-ID','wrong-source-tree','wrong-owner','stale-per-ID-hash']

def sha(raw):return hashlib.sha256(raw).hexdigest()
def spec(path,relative=None):
    path=pathlib.Path(path);raw=path.read_bytes()
    return {'path':str(path),'relative_path':str(relative or path.name),'bytes':len(raw),'sha256':sha(raw)}
def obj(name):return json.loads((HERE/name).read_bytes())
def git(*args):return subprocess.check_output(['git',*args],cwd=REPO,stderr=subprocess.PIPE)
def main():
    positive=obj('final-ledger-positive.json'); addendum=obj('final-caption-addendum.json')
    assert positive['check']=='PASS' and positive['issues']==[] and addendum['check']=='PASS'
    assert positive['target']['sha']==PRIMARY and addendum['target']['sha']==FINAL
    negatives=[]
    for control in CONTROLS:
        data=obj('negative-'+control+'.json');execution=obj('negative-'+control+'.execution.json')
        assert data['check']=='FAIL' and data['negative_harness_outcome']=='PASS' and execution['exit']==1
        negatives.append({'control':control,'actual_check':'FAIL','actual_exit':execution['exit'],'harness_check':'PASS','reason':data['issues'],'complete_observation':spec(HERE/('negative-'+control+'.json')),'execution':spec(HERE/('negative-'+control+'.execution.json'))})
    compressed=[]
    for name in ['full35-baseline-candidate-join-v2.json','final-ledger-positive.json']:
        source=HERE/name;raw=source.read_bytes();destination=HERE/(name+'.gz')
        encoded=gzip.compress(raw,mtime=0);destination.write_bytes(encoded)
        assert gzip.decompress(destination.read_bytes())==raw
        compressed.append({**spec(destination),'encoding':'gzip-lossless','decoded_bytes':len(raw),'decoded_sha256':sha(raw),'original_scratch':spec(source)})
    current_original_counts=positive['recommendations']
    semantic=[
      {'requirement':'Complete original criterion denominator','check':'PASS','basis':'All36 actual card block byte/hash/title/criterion-ID bindings, full282finding/127bundle TSV input and35/17 Fowner bijection; LA016 two byte-identical bindings count oneID.'},
      {'requirement':'Four decision axes','check':'PASS','basis':'Per-ID original check34PASS/1UNRUN, F-original33closed/2limited, technical-original33closed/2limited, Gformal0/notissued; historical07225/9/1 andtechnical30/4/1+checks33/2 remain dated, not retagged519.'},
      {'requirement':'B214 and B56 exact original residuals','check':'PASS','basis':'B214 remains limited for supported sound partial/conditional extension route, not invented institutional authority. B56 actual DurableControlWorker→RunLifecycle→run_experiment→sync_run_causal_full competing admitted budget/study workload remains UNRUN; attemptedpool execution_context_missing before0fits and bounded4study fixture/defaultconfigured folds preserved.'},
      {'requirement':'Originalfiniteproof versus realadmission','check':'PASS','basis':'B204pretrend invalid/not_testable and nonrejection notidentification; B207–209 selectedshareIF/Mammen/null/anticipation known-DGP proofs remain oldsource; B212point-only selectedgenuine3.12backend/B213estimand_type/contrast/target distinctfrom baseline3.14backend exclusions.'},
      {'requirement':'LA035 corrected scope','check':'PASS','basis':'Exactoriginalhistorical normalizedincome/budget equivalentrelocation isclosedbounded; no new optimizer/norm/welfare prerequisite. New193 Fraction32panels×eager/JIT=64 plus2grad belongsbaseline, notGini. 9007trackedsource/config literal/FQN search and10matchingfiles do not prove external/constructed/untracked consumers absent.'},
      {'requirement':'LA004 and Gini distinct','check':'PASS','basis':'LA004 actualtwo native/plugin models matched+deliberately divergentlaws; notGini. Actual C/G9a ActorCritic/labor/tax→bridge/currentmetric/metric-enabledPPO signedactivewealth typedrefusal isseparate syntheticnative property; notrealpolicycalibration. Historical532 arithmetic oracle isnotwholeproviderblob equivalence.'},
      {'requirement':'Scientific subcriteria keep original meaning','check':'PASS','basis':'B206both DiD/RDD;B216do/sigma/IDC andlatentDAG;B218lag/export/staticrefusal notuniversal temporalID;B220internalstable;B222conditionalexistingpolyhelper→SCM/CAS/query/twin notnewdefaultfitter;B223target/baseline/queryrefs/samearm0/do2-do0=6 primary;B225independentmath.erfc;LA002catalog/IC notfournewkernels;LA007/019 absentbase198;LA016maintaineddedicatedFQN/flags/slots;LA017normdiff/issue/pass/report/CAS/CLI notdedupealone/currentlaw;LA037actualIR/compiler/registry/docs/install.'},
      {'requirement':'Assembled readiness not original criterion outcome','check':'PASS','basis':'Current519 onlyaffected91wheel/91rebuilt-sdist with6expectedrawFAIL and separateONEwheel differentPID child. Old8236each199 andfailedb5each130PASS32FAIL remain respective sources; no repeat162/FIT53/ECO28/TMLE160/RDD4000 or newglobalPASS.'},
      {'requirement':'Publication and caption identity','check':'PASS','basis':'Ten primaryGitbytes/tree refs, sourceorder6fulltopic footprints, 44doc-only authoredpaths/full406746B patch exact. Three currentcaption providers retain source-specific science/ref boundaries; staleREPORT onceavailable wasobserved46cc andonlyonesentence repairedcdf; complete2257? actualpatch2215B boundaddendum suppliesexactdigest.'},
      {'requirement':'Partial custody and globalred preserved','check':'PASS','basis':'Unavailable175c fourhistorical non-deciding refs remainUNRUN. Oldrawcustody notindependently rewalked. Source5957 scannerfirst+retry -9 ERROR/incomplete notPASS;Ruff103FAIL/publicsurface38FAIL;P41notestablished. Runtime/PDCsemantic/statisticalidentification/TMLEvalue/currentlaw/Aprotectedbridge input refs/commands null andno self-issued authority.'},
    ]
    # Keep prose exact; no accidental invented patch count from freeform note.
    semantic[8]['basis']=semantic[8]['basis'].replace('complete2257? actualpatch2215B','completepatch2215B')
    queries=[]
    for directory in ['baseline-queries','baseline-cells']:
        for path in sorted((HERE/directory).glob('*.execution.json')):
            data=json.loads(path.read_bytes());assert data['exit']==0
            queries.append({'execution':spec(path,path.relative_to(HERE)), 'command':data['command'],'actual_exit':data['exit']})
    assert len(queries)==169
    baseline_join=obj('full35-baseline-candidate-join-v2.json')
    importer=obj('baseline-import-check.execution.json');assert importer['exit']==0
    manual_doc_refs=[]
    for path in ['closure-decisions/F.md','closure-decisions/method-decisions.md','closure-decisions/runtime-profiles.md','implementation-handoffs/F/continuation-transfer-20261007/REPORT.md']:
        full='policy-engine/docs/research/e02-cloud-test-plan/'+path;raw=git('show',FINAL+':'+full)
        manual_doc_refs.append({'git_ref':FINAL,'path':full,'bytes':len(raw),'sha256':sha(raw),'review':'completecurrentF captions+deltafrompriorfullreview; F-M1..15 byteunchanged except separately scoped nonFerrata, currentF-M16 source519 installedaddendum read'})
    review={
      'schema':'F-final-original35-independent-ledger-review/v1','check':'PASS','verdict':'GO_BOUNDED',
      'target':addendum['target'],'full_metadata_target':positive['target'],
      'product_source':positive['product_source'],
      'denominator':positive['denominator'],'recommendations':current_original_counts,
      'formal_G_acceptance':False,'specification_review':'PASS_BOUNDED','metadata_engineering_review':'PASS_BOUNDED','issues':[],
      'resolved_observation':{'location':'REPORT.md prior46cc currentcaption onceavailable','severity':'low','state':'fixedbyrootcdf exactone-sentence delta; no scientific change'},
      'independent_semantic_matrix':semantic,
      'negative_controls':negatives,
      'complete_positive_metadata_observation':compressed[1],
      'caption_addendum':spec(HERE/'final-caption-addendum.json'),
      'manual_current_caption_inputs':manual_doc_refs,
      'fresh_baseline_navigation':{'importer':spec(HERE/'baseline-import-check.execution.json'),'exact_import_command':importer['command'],'actual_check':'PASS onlyimmutable importednavigation consistency','source_reported_scope':'No full VMrawarchives; baseline source_reported SKIP/ERROR/FAIL andactualSHA/backend/input boundaries retained, no newcandidatePASS by routing','per_finding_and_failure_queries':36,'full_unique_cell_queries':118,'full_source_job_context_queries':15,'exact_complete_query_commands':queries,'baseline_candidate_join':compressed[0],'join_denominator':baseline_join.get('denominator')},
      'metadata_measurement_counts':{'artifacts':len(positive['primary_and_card_metadata_artifacts_verified']),'deciding_check_pointers':positive['complete_deciding_check_pointer_count'],'ten_current_primary_receipts':10,'declared_manifest_metadata_inputs':len(positive['complete_current_manifest_metadata']),'source_order_topics':6,'authored_doc_paths':44,'original36card_bindings':36},
      'scope':'Independent originalcriterion/caption/metadata source-binding review. No numerical rerun or old1659/480 rawbody rewalk. Manifestmetadata isnot fresh fullrawcustody; priorchecks remain exactoldsource, delegatednewinstalledrawreceipts areboundprimary evidence, not mynewruntimeexecutions.',
      'independence_limit':'OwnCAUmethod author/reviewer conflict remains originalper-ID explicit; thispass independentlyreviewsROOTmetadata/census/rationale andobservedcorruptionbehavior, doesnotself-certifynewscientificmeasurements.',
      'portable_replay':{'script':spec(HERE/'replay_final_ledger_delta.py'),'input_dependencies':['validate_final_ledger_delta.py','validate_root_current35.py','expected-original35-compact.json'],'authored_patch_reconstruction':['git','diff','--no-ext-diff',PRIMARY+'^',PRIMARY],'delta_review_target':PRIMARY,'caption_addendum_target':FINAL,'how':'Fetch original immutable histories; reconstruct authoredpatch inuniquescratch, pass--input-dir/--authored-patch/--repo/--output. Useeach--control foractualreject. Separatecaption replayer validatesonlycdfdelta. No checkouts/authority/methodtests needed.'},
      'limitations':positive['limitations'],
      'environment':{'python':platform.python_version(),'executable':sys.executable,'stdlib_only':True},
      'observed_own_branch_head':subprocess.check_output(['git','rev-parse','HEAD'],cwd='/workspace/e02-F-cau-20261006').decode().strip(),
    }
    output=HERE/'independent-final-ledger-review.json';output.write_text(json.dumps(review,ensure_ascii=False,indent=2)+'\n')
    paths=[]
    # All169fullrawqueries/cell/jobcontext executions andactualcommands.
    for directory in ['baseline-queries','baseline-cells']:
        paths += sorted((HERE/directory).iterdir())
    top=['expected-original35-compact.json','prepare_expected_criteria.py','capture_baseline_queries.py','capture_full_cells.py','join_full35.py','validate_final_ledger_delta.py','replay_final_ledger_delta.py','review_caption_addendum.py','freeze_review_selection.py','independent-final-ledger-review.json','full35-baseline-candidate-join-v2.json.gz','final-ledger-positive.json.gz']
    for stem in ['baseline-import-check','expected-original35-compact','full35-baseline-candidate-join-v2','final-ledger-positive','final-caption-addendum',*['negative-'+c for c in CONTROLS]]:
        top += [stem+suffix for suffix in ['.stdout','.stderr','.execution.json']]
        if stem.startswith('negative-') or stem=='final-caption-addendum':top += [stem+'.json']
    paths += [HERE/name for name in top]
    paths += [OLD/'validate_root_current35.py',OLD/'capture_metadata_check.py']
    items=[]
    compressed_by_path={q['path']:q for q in compressed}
    for path in paths:
        assert path.is_file(), 'selected unique output missing:'+str(path)
        relative=path.relative_to(HERE) if path.is_relative_to(HERE) else pathlib.Path(path.name)
        entry=spec(path,relative)
        if str(path) in compressed_by_path:
            entry.update({k:v for k,v in compressed_by_path[str(path)].items() if k in ['encoding','decoded_bytes','decoded_sha256']})
        items.append(entry)
    assert len(items)==len({q['path'] for q in items})
    fidelity={'originals_not_deleted':True,'excluded_reconstructable_or_superseded_scratch':['historicalverboseexpected-original35.json view (100181B; finalcompact589? exact57856B bound)','joinv1 output remains historical; v2 separates124referenceoccurrences/72JSONpointers; no droppedactualFAIL/ERROR','copiedtrackedsource/cardtext/TSV/fullpatch views absent fromselection; reconstruct exactGitlocators','rawuncompressedJSON source andlosslessgzip both remain localscratch; onlyencodedGittransport body selected'],'all_actual_positive_and_six_negative_stdout_stderr_execution':'selectedcomplete','all169requestedqueryrawstdout_stderr_execution':'selectedcomplete','historicalcapturerstderr_empty':'selectedemptyfiles preserved','not_inherited_P41':True}
    fidelity['excluded_reconstructable_or_superseded_scratch'][0]=fidelity['excluded_reconstructable_or_superseded_scratch'][0].replace('589? exact57856B','57856B')
    selection={'schema':'F-independent-review-transfer-selection/v1','status':'FROZEN','target':addendum['target'],'full_metadata_target':positive['target'],'product_source':{'sha':positive['product_source']['sha'],'tree':positive['product_source']['tree']},'items':items,'files':len(items),'stored_bytes':sum(q['bytes'] for q in items),'decoded_gzip_files':len(compressed),'decoded_gzip_bytes':sum(q['decoded_bytes'] for q in compressed),'fidelity':fidelity,'report':spec(output)}
    path=HERE/'final-review-transfer-selection.json';path.write_text(json.dumps(selection,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'check':'PASS','review':spec(output),'selection':spec(path),'files':selection['files'],'stored_bytes':selection['stored_bytes'],'decoded_gzip_files':2,'decoded_gzip_bytes':selection['decoded_gzip_bytes'],'original_check_counts':current_original_counts['check_results'],'F_original_counts':current_original_counts['F_original_finding_recommendation'],'negative_controls':len(negatives),'query_processes':169},indent=2))
    return 0
if __name__=='__main__':raise SystemExit(main())
