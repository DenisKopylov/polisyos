"""Run both commissioned instruments and retain actual CAS/event readback evidence."""
from __future__ import annotations

import hashlib
import json
import runpy
from collections import Counter
from pathlib import Path

import polisyos.runtime.http.services.control  # noqa: F401
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.lex.knowledge.multilingual_assurance import (
    read_assurance_result,
    read_source_content,
    run_assurance,
    run_source_content,
)
from polisyos.runtime.http.services.control_plane_store import ControlPlaneStore
from polisyos.runtime.quality.event_log import RuntimeDiagnosticEventLog
from polisyos.runtime.quality.operator_comprehension import (
    read_instrument_result,
    run_instrument,
)

root = Path(__file__).resolve().parents[5]
output = Path(__file__).resolve().parent / 'raw/demonstration'
output.mkdir(parents=True, exist_ok=True)
operator_harness = runpy.run_path(root / 'tests/unit/runtime/quality/test_operator_comprehension.py')
corpus = operator_harness['corpus']()
operator_events = operator_harness['events'](corpus)
log = RuntimeDiagnosticEventLog(
    store=ControlPlaneStore(backend='sqlite', sqlite_path=output/'operator.sqlite3'),
    artifact_store=FileSystemCAS(output/'operator-cas'),
)
receipt = run_instrument(corpus, operator_events, design=operator_harness['design'](), event_log=log)
result = read_instrument_result(log, receipt.event_id)
partitions = Counter(item.partition for item in corpus.items)
# Independently crosscheck the raw full item denominator and the required factorial.
raw_corpus = json.loads((root/'tests/fixtures/runtime_quality/operator_comprehension.json').read_text())
assert len(raw_corpus['items']) == sum(partitions.values()) == len({i.item_id for i in corpus.items})
assert partitions['sealed'] == len(corpus.mandatory_constructs) * len(corpus.modalities)
assert len(operator_events) == sum(1 for _ in operator_events)
assert result.human_comprehension_established is False
assert all(cell['upper_bound'] is None for cell in result.projection()['safety_cells'])

cas = FileSystemCAS(output/'multilingual-cas')
packets = json.loads((root/'tests/fixtures/lex/multilingual_assurance.json').read_text())['cases']
ml_results = []
for packet in packets:
    emitted = run_assurance(packet, cas=cas)
    consumed = read_assurance_result(cas, emitted.artifact_ref,
        proposition_id=packet['proposition_id'], purpose=packet['purpose'],
        context_id=packet['contexts'][0], qualified_holder=None)
    assert not consumed.equivalence_established and consumed.signer is None
    ml_results.append({'artifact_ref': emitted.artifact_ref, **consumed.projection()})
assert len(ml_results) == len({packet['proposition_id'] for packet in packets})
rtl_receipt = run_source_content({'jurisdiction':'IL-Hebr', 'language':'he', 'script':'Hebr',
    'source_text':'טקסט מועמד בלבד \u2066claim-17\u2069: אין סמכות משפטית.'}, cas=cas)
rtl = read_source_content(cas, rtl_receipt.artifact_ref,
                         jurisdiction='IL-Hebr', language='he', script='Hebr')
print(json.dumps({
    'cb1': {'event_id':receipt.event_id, 'payload_ref':receipt.payload_ref,
            'raw_event_denominator': len(operator_events), 'item_denominator': len(corpus.items),
            'partition_counts': dict(partitions), 'corpus_seal':corpus.seal,
            'result':result.result, 'human_comprehension_established':False,
            'upper_bounds_withheld_by':'WP-09', 'cas':str(output/'operator-cas'),
            'partition_independence':result.projection()['partition_independence'],
            'semantic_independence':result.projection()['semantic_independence'],
            'limitations':result.projection()['limitations']},
    'ml1': {'proposition_denominator':len(packets), 'results':ml_results,
            'rtl_artifact_ref':rtl_receipt.artifact_ref,
            'rtl_source_digest':rtl['source_digest'],
            'rtl_evidence_slots_unfilled':list(rtl['evidence_requirements']),
            'cas':str(output/'multilingual-cas')},
    'source_files': {str(path.relative_to(root)):hashlib.sha256(path.read_bytes()).hexdigest()
                     for path in [root/'tests/fixtures/runtime_quality/operator_comprehension.json',
                                  root/'tests/fixtures/lex/multilingual_assurance.json']},
}, ensure_ascii=False, indent=2))
