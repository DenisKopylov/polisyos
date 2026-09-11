"""Pinned read-only blocked-B evidence, with complete AST and demand denominators.

Bodies are printed only into gitignored deciding output, not copied into a tracked
receipt. A name match discovers a candidate; human reading decides its property.
"""
import ast
from collections import Counter
import importlib.util
import json
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('survey_tree', HERE.parent / 'open/inspect_tree.py')
owner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(owner)
GROUPS = {
 'w5': {
  'query': r'NonDataAcquisition|GapShapeAssessment|AcquisitionType|NonDataRequest|non_data_acquisition|acquisition_assurance|operator_comprehension|score_trials|run_instrument|read_instrument|adaptation_transition|AdaptationTransition|AdaptationDecision|RestartEvidence|KPIControl|constrained_response|ConstrainedResponse|multilingual_assurance|run_assurance|read_assurance_result|run_source_content|CandidateSourceContent|AssurancePacket|CandidateAssurance|RTLSourcePack|legal_authority|applicability|coauthentic|co_authentic',
  'files': ['src/polisyos/fabric/evidence/non_data_acquisition.py', 'src/polisyos/fabric/evidence/acquisition_assurance.py', 'src/polisyos/fabric/evidence/ceiling_relations.py', 'src/polisyos/runtime/quality/non_data_acquisition.py', 'src/polisyos/runtime/quality/adaptation_transition.py', 'src/polisyos/runtime/quality/operator_comprehension.py', 'src/polisyos/lex/knowledge/multilingual_assurance.py', 'src/polisyos/runtime/quality/constrained_response.py', 'tools/quality/validation/check_canonical_vocabulary_crosswalk.py'],
  'docs': r'W5-(?:R[23456]|O5)-Q(?:02|04|05|06|08|09|10|13)|WP-(?:08|09|11|12|13)|GY-(?:AQ1|CB1|CR1|ML1)|GapAcquisitionCase|GapShapeAssessment|institutional_family_reconciliation'},
 'epoch': {
  'query': r'EpochValidityTransitionProducer|produce_and_persist|NoEpochTransitionSigningAuthority|EpochValidityGateProducer|resolve_transition_manifests|EpochValiditySubject|derive.*subject|register_decision_packet|decision_packet_lineage|current_decision_packet|epoch_validity_prior_binding|PolicyAdmission|policy_admission',
  'files': ['src/polisyos/runtime/quality/epoch_validity_cascade.py', 'src/polisyos/runtime/http/dependencies.py', 'src/polisyos/runtime/quality/semantic_epoch.py', 'src/polisyos/runtime/http/services/temporal.py', 'src/polisyos/scientist/nodes/builtins/decide/decision_packet/builder.py'],
  'docs': r'GY-DEF23|gy-n12-epoch-|GY-N12|policy_admission_missing|epoch_transition_signer_not_established|current_decision_packet_ref'},
 'lex': {'query': r'amendment|lex_chronology|chronology.*lex', 'files': ['src/polisyos/lex/knowledge/store.py'], 'docs': r'gy-n12-lex-amendment|valid.effect.*amendment|declared_amendment_count|152.?636|156.?196'},
 'gaps': {'query': r'ConfidenceRiskBudgetScope|PredictableClaimSpec|cross_scope|ReleaseFamily|release_family|CycleBoard|cycle_board|movement_family|recursive_cycle|enumerate.*cycle', 'files': ['src/polisyos/runtime/http/services/cycle_board_contracts.py', 'src/polisyos/runtime/http/services/cycle_board_service.py', 'src/polisyos/runtime/quality/confidence_ledger.py'], 'docs': r'GY-GAP[2356]|PV-K07|controlled.release.family|movement.family|cross.scope.composition'},
 'ds15': {'query': r'AcquisitionAdmissionBundle|AgentActionAdmissionBundle|admission_signing|admission_bundle|AcquisitionExecutionPort|AcquisitionActionService|ProductionAcquisition|metric_residual|GapAcquisitionCase|GapShapeAssessment|run_non_data_acquisition', 'files': ['src/polisyos/runtime/http/services/acquisition_admission_bundle.py', 'src/polisyos/runtime/http/services/acquisition_action_service.py', 'src/polisyos/runtime/quality/non_data_acquisition.py'], 'docs': r'ds15-|INT-R2|GapAcquisitionCase|metric_residual_granularity|GY-AQ1'},
 'public': {'query': r'GlobalCase|CaseIndex|case_index|case_provider|CaseDiscovery|public_decision|promoted_record|build_public_export_bundle|PublicDecisionVerification', 'files': ['src/polisyos/runtime/http/routes/public_decisions.py', 'src/polisyos/runtime/http/services/public_decision_verification_contracts.py', 'src/polisyos/runtime/http/services/public_decision_verification.py', 'src/polisyos/runtime/quality/global_case_index.py', 'src/polisyos/runtime/quality/capability_discovery.py', 'src/polisyos/runtime/http/services/control_registry_providers.py'], 'docs': r'ds8-global-case-index|ds8-signed-public-decision|global.case.index|PV-K01|public.decision.rendering|DS12'},
 'promotion': {'query': r'_effect_obligation|_measurement_obligation|_eval_safety_obligation|_refusal_reasons|persist_effect_obligation|persist_measurement_root|run_canonical_promotion|decide_evaluation_safety_core|promotion_authority|ValueGateReceipt|compose.*value', 'files': ['src/polisyos/runtime/quality/promotion_sequence.py'], 'docs': r'GY-O0-NC-01|gy-promotion-obligations-scope-insufficient|promotion.authority|first.promotion.candidate|GY-PR1|O_effect'},
}

def main():
 name = sys.argv[1]
 config = GROUPS[name]
 inventory = owner.ast_inventory()
 records = inventory['records']
 selected = [r for r in records if re.search(config['query'], r['name'], re.I)]
 bodies = []
 for path in config['files']:
  if path in inventory['paths']:
   bodies.append({'path': path, 'source_at': f'{path}@{owner.BASE}', 'body': (owner.ROOT/path).read_text()})
  else:
   bodies.append({'path':path, 'exists':False})
 tracked = owner.tracked()
 doc_paths = [p for p in tracked if p.startswith(('docs/plans/active/', 'docs/reference/', 'docs/research/', 'docs/system-design-decisions/')) and p.endswith(('.md','.json','.yaml','.yml')) and not p.endswith(('/DEBT-REGISTER.md','/LEDGER.md'))]
 docs = [{'path':p, 'line':n, 'text':line} for p in doc_paths for n,line in enumerate((owner.ROOT/p).read_text().splitlines(),1) if re.search(config['docs'],line,re.I)]
 print(json.dumps({'group':name,'base':owner.BASE,'python_files':len(inventory['paths']),'source_python_files':sum(p.startswith('src/') for p in inventory['paths']),'file_enumeration':'git ls-tree identity equals os.walk; path SHA '+inventory['path_sha256'],'node_enumeration':'ast.walk identity equals independent NodeVisitor; FunctionDef + AsyncFunctionDef + ClassDef + Call','parse_errors':inventory['ambiguities'],'ast_query':config['query'],'definition_distribution':dict(sorted(Counter(r['path'].split('/')[2] if r['path'].startswith('src/') else r['path'].split('/')[0] for r in records if r['kind'] in ('FunctionDef','AsyncFunctionDef','ClassDef')).items())),'matched_module_distribution':dict(sorted(Counter(r['path'] for r in selected).items())),'matches':selected,'selected_source_bodies':bodies,'demand_denominator':{'file_types':['.md','.json','.yaml','.yml'],'paths':doc_paths,'excluded_subjects':['DEBT-REGISTER.md','LEDGER.md']},'demand_query':config['docs'],'demand_matches':docs},indent=2,ensure_ascii=False))

if __name__ == '__main__':
 main()
