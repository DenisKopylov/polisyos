"""Independent full model-field denominator and operational cache discriminators."""
import importlib.util
import json
from pathlib import Path
import pytest
from polisyos.ir.analytics.cross_graph import CompositionCertificate, load_composition_certificate, persist_composition_certificate
from polisyos.scientist.nodes.builtins.causal.reconcile_causal_graph import ReconcileCausalGraphNode
from polisyos.scientist.nodes.builtins.state_keys import ARTIFACT_COMPOSITION_CERTIFICATE_REF

spec=importlib.util.spec_from_file_location('independent647original',Path(__file__).with_name('test_current_source_guards.py'))
helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
FAKE='sha256:'+'f'*64
UPDATES={
 'schema_version':'1.3',
 'structure_status':'invalid',
 'review_status':'pending_review',
 'status':'broken',
 'composed_graph_ref':FAKE,
 'interface_mapping_ref':FAKE,
 'alignment_report_ref':FAKE,
 'newly_required_assumptions':['independent-unproved-change'],
 'structural_assumptions':['independent-unproved-change'],
 'alignment_assumptions':['independent-unproved-change'],
 'source_fragment_refs':{'a':FAKE},
 'source_fragment_graph_refs':{'a':FAKE},
 'witness_ref':'unproved://changed-witness',
 'blocking_reasons':['independent-blocking-change'],
 'metadata':{'graph_type':'dag','completeness_scope':'unproved','nested':{'changed':True}},
}
OPERATIONAL={'checked_queries','query_certificates','failure_card_bundle_ref'}

def test_complete_model_field_denominator():
 assert set(UPDATES)==set(CompositionCertificate.model_fields)-OPERATIONAL
 print(json.dumps({'full_fields':sorted(CompositionCertificate.model_fields),'source_semantic_fields':sorted(UPDATES),'operational_fields':sorted(OPERATIONAL)}))

@pytest.mark.parametrize('field',sorted(UPDATES))
def test_every_semantic_certificate_field_is_reconciled(tmp_path,field):
 ctx,state,_=helper.case(tmp_path)
 actual=load_composition_certificate(ctx.store,state.artifacts_index[ARTIFACT_COMPOSITION_CERTIFICATE_REF])
 payload=actual.model_dump(mode='json');payload[field]=UPDATES[field]
 changed=CompositionCertificate.model_validate(payload)
 assert changed.model_dump(mode='json')!=actual.model_dump(mode='json')
 state.artifacts_index[ARTIFACT_COMPOSITION_CERTIFICATE_REF]=persist_composition_certificate(ctx.store,changed)
 outcome=ReconcileCausalGraphNode().execute(ctx,state)
 print(json.dumps({'field':field,'node_status':outcome.status,'artifacts':len(outcome.artifacts),'error':outcome.error.message if outcome.error else None}))
 assert outcome.status=='fail' and not outcome.artifacts

def test_orphan_and_altered_operational_cache_is_recomputed(tmp_path):
 ctx,state,_=helper.case(tmp_path)
 first=ReconcileCausalGraphNode().execute(ctx,state)
 assert first.status=='ok',first.error
 original=load_composition_certificate(ctx.store,first.state.artifacts_index[ARTIFACT_COMPOSITION_CERTIFICATE_REF])
 assert original.query_certificates
 sample=next(iter(original.query_certificates.values()))
 changed=original.model_copy(update={'checked_queries':{**dict.fromkeys(original.checked_queries,'broken'),'orphan-unrequested-fingerprint':'preserved'},'query_certificates':{**{k:v.model_copy(update={'status':'broken'}) for k,v in original.query_certificates.items()},'orphan-unrequested-fingerprint':sample}})
 next_state=first.state.model_copy(deep=True)
 next_state.artifacts_index[ARTIFACT_COMPOSITION_CERTIFICATE_REF]=persist_composition_certificate(ctx.store,changed)
 outcome=ReconcileCausalGraphNode().execute(ctx,next_state)
 assert outcome.status=='ok',outcome.error
 result=load_composition_certificate(ctx.store,outcome.state.artifacts_index[ARTIFACT_COMPOSITION_CERTIFICATE_REF])
 assert result==original
 assert 'orphan-unrequested-fingerprint' not in result.checked_queries
 assert 'orphan-unrequested-fingerprint' not in result.query_certificates
 print(json.dumps({'operation':'cache_reset','old_orphan':True,'recomputed_whole_certificate_equal':result==original,'statuses':result.checked_queries}))
