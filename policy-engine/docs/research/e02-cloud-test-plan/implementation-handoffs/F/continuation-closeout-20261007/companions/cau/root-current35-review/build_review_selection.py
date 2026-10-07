"""Package unique independent observations; output only in reviewer scratch."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
def ref(path):
    value = path.read_bytes()
    return dict(path=str(path),bytes=len(value),sha256=hashlib.sha256(value).hexdigest())
def load(name): return json.loads((ROOT/name).read_text())
material = load('d833-complete-material-final-review.json')
captions = load('d833-source-order-captions-review.json')
assert material['check'] == captions['check'] == 'PASS'
assert material['target'] == captions['target']
assert len(material['verified_artifacts']) == 1659
assert len(material['verified_decoded_artifacts']) == 480
assert sum(m['records'] for m in material['complete_current_manifests']) == 653
assert all(c['validator_check']=='FAIL' and c['harness_check']=='PASS' for c in material['negative_controls'])

historical = [
    dict(report='da59-material-review.json',classification='Reviewer encoding harness ERROR rendered FAIL by its metadata checker: explicit lossless_utf8_json not implemented. No owner artifact or product defect; full actual streams preserved.'),
    dict(report='da59-material-v2-review.json',classification='Reviewer schema harness ERROR rendered FAIL: zero-dependence claim belongs to immutable072 INDEX, not AUDIT. Actual old bytes/pointers retained; no owner defect.'),
    dict(report='6a39-material-review.json',classification='Reviewer alias handling ERROR rendered FAIL: explicit decoding=gzip was missed by encoding-only lookup. Actual stored/decoded Git bytes match declaration; corrected in forward checker.'),
    dict(report='6a39-material-v2-review.json',classification='PASS on1359/369 measured artifact footprint, qualified incomplete current manifest traversal. Never broad complete-footprint PASS; final walker independently follows nested Graph223 and own52 bodies.'),
    dict(report='d833-complete-material-review.json',classification='PASS full raw/decode traversal1659/480; initial manifest_record_occurrences373 was a reviewer count-field omission for records lists/inline ECO. Final653 count fixed with explicit denominator assertion, no byte/property change.'),
]
for item in historical:
    item['output_ref'] = ref(ROOT/item['report'])
review = dict(
    schema='e02.F.independent-root-original35-final-metadata-review.v1',
    target=material['target'],check='PASS',recommendation='GO_BOUNDED',issues=[],
    material_review=ref(ROOT/'d833-complete-material-final-review.json'),
    source_order_caption_review=ref(ROOT/'d833-source-order-captions-review.json'),
    original_denominator=material['denominator'],
    current_F_recommendation=dict(closed=33,limited=2,held=0,limited_ids=['B214','B56']),
    checks=dict(PASS=34,UNRUN=1,UNRUN_ids=['B56']),
    formal_G_finding_acceptance='not_issued/zero formal closures',
    raw_material_denominator=dict(unique_artifacts=1659,decoded_bindings=480,current_manifest_record_occurrences=653,current_manifest_counts=material['complete_current_manifests'],complete_historical_check_records=566,per_ID_raw_check_pointer_count=446),
    negative_controls=material['negative_controls'],
    complete_source_order_topics=6,complete_current_minimal_owner_packets=7,
    product_source=material['product_source'],
    semantic_read_scope='All35 full original card blocks and owners/17bundle TSV/36 bindings plus current per-ID producer/artifact/bridge/consumer/actual surfaces, exact source/tree/owner receipts/full check pointers. Full REPORT and ROOT F.md/F-M1..16/runtime captions read; exact documents are bound in caption review. Scientific prior independent card review is actualpublished4d; current ROOT decisions remain ROOT recommendations.',
    criterion_corrections_checked=['B206 bothDiD/RDD','B207-209 finite selectedDGP/diagnostic contract separateinstitutional admission','B212 point-only versusrealinterval','B213 estimand_type/contrast/target identify/estimate','B214 limitedconditionalcapability','B216 actualdo/sigma/IDC','B220 internalstable','B222 conditionalhelperpayload notnewdefaultfit','B223 attributiontarget/baseline/queryrefs primary','B225 independentmath.erfc','LA002 catalog/IC notnewfamilysolver','LA003 separatedABMdiagnosticFAIL/P41notestablished','LA004 distinctmatched/divergentmodels notGini','LA007/019 absentbase198 notnewdeletion','LA016 oneID/twobindings dedicatedmaintainedFQN','LA017 fullnormdiff/LegalPass/issues/report/CAS/CLI notdedupealone','LA035 unchangedhistoricalrelocation no newoptimizerprerequisite','LA037 actualIR/compiler/docs/installed'],
    locator_resolution=dict(initial_issue='6a G-source-order pointed to old minimal-owner-inputs.json',corrected_commit=material['target']['sha'],current_locator='G-local-causal-reruns.json',check='PASS',scope='Two packet documents only, no per-ID/source/check/outcome change'),
    bounded_limits=captions['remaining'],
    historical_custody=dict(missing175c_provenance_occurrences=4,check='UNRUN',deciding_dependency=False,full_raw_absent_check_records=20,full_raw_absent_check='UNRUN',no_reclassification_as_measured_PASS=True),
    historical_reviewer_harness_attempts=historical,
    no_source_or_ledger_writes=True,no_scientific_rerun=True,no_new_checkout_or_agents=True,no_new_authority_or_G_decision=True,
    future_metadata_delta='New exact installed/quality carrier references require only finite material/caption delta revalidation; old8236 wave never presented as currentb5 whole-product witness.',
    self_packaging='This script only assembles already independently executed reviewer observations and their exact full byte references; it supplies no new independent or scientific test result.',
)
(ROOT/'independent-root-current35-review.json').write_text(json.dumps(review,ensure_ascii=False,indent=2)+'\n')
items = []
for path in sorted(ROOT.rglob('*')):
    if not path.is_file() or path.name == 'transfer-selection.json' or '__pycache__' in path.parts: continue
    item = ref(path)
    item['role'] = 'unique independent reviewer full structured observation, raw stream, execution or source replayer; historical attempts preserved' if path.suffix != '.py' else 'unique reviewer replayer/version; no tracked source copy'
    items.append(item)
selection = dict(schema='e02.independent-review-transfer-selection.v1',target=material['target'],items=items,files=len(items),stored_bytes=sum(i['bytes'] for i in items),scope='Complete unique reviewer observations/replayers/streams/executions only. No copied ROOT index/card/source footprint or running status. Full prior FAIL/harness attempts and partial measured denominators preserved.',no_source_writes=True)
(ROOT/'transfer-selection.json').write_text(json.dumps(selection,indent=2)+'\n')
print(json.dumps(dict(review=ref(ROOT/'independent-root-current35-review.json'),selection=ref(ROOT/'transfer-selection.json'),files=len(items),bytes=selection['stored_bytes'],target=material['target']),indent=2))
