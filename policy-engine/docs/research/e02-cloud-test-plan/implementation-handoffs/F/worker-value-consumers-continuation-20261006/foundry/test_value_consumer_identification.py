"""Real native producers, fresh CAS readers and the existing value consumer."""

from __future__ import annotations

from dataclasses import replace
import json

import numpy as np
import pytest

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
from polisyos.foundry.methods.backends.protocol import MethodResult
from polisyos.foundry.methods.catalog.causal.protocols import RDDObservationalData
from polisyos.foundry.methods.catalog.causal.rdd import RegressionDiscontinuity
from polisyos.foundry.methods.catalog.econometrics.protocols import EconometricResult, TimeSeriesData
from polisyos.foundry.methods.catalog.econometrics.timeseries import TimeSeriesEstimator
from polisyos.foundry.methods.components.consensus import EstimandSpec
from polisyos.foundry.methods.components.value_evidence import (
    MethodValueEvidence,
    MethodValueRefusal,
    project_method_value_evidence,
)
from polisyos.foundry.methods.selection.history import SelectionHistoryStore
from polisyos.ir.analytics.causal import (
    CausalEffectReport,
    EstimationStatus,
    ProofBundle,
    load_causal_effect_report,
    load_proof_bundle,
    persist_causal_effect_report,
    persist_proof_bundle,
)
from polisyos.ir.analytics.causal_graph import CausalGraphModel, GraphType, persist_causal_graph_model
from polisyos.ir.analytics.uncertainty import NativeValueEstimandBinding
from polisyos.ir.artifacts import get_json_artifact, put_json_artifact
from polisyos.ir.model_layer.canon import CanonSpec


def _log(**values: object) -> None:
    print(json.dumps(values, sort_keys=True))


@pytest.fixture(scope='module')
def rdd_native() -> MethodResult:
    x = np.linspace(-1.0, 1.0, 400)
    y = 0.2 + 0.6*x + np.where(x < 0.0, 1.2*x*x, 2.5 + 4.1*x*x) + 0.12*np.sin(57*x)
    data = RDDObservationalData(running_variable=x, outcome=y, cutoff=0.0)
    result = MethodDispatcher(runtime_history=SelectionHistoryStore()).dispatch(
        method_class=RegressionDiscontinuity, signature=RegressionDiscontinuity.signature,
        state=data, params={'bias_correction':True, 'bandwidth':0.45, 'bias_bandwidth':0.65,
                            'polynomial_order':1, 'bias_polynomial_order':2, 'kernel':'triangular',
                            'vce':'hc0', 'masspoints':'off', 'bandwidth_selector':'fixed',
                            'design':'sharp', 'confidence_level':0.95, 'manipulation_test':False},
        seed=20261006,
    )
    assert isinstance(result.slot_outputs['causal_effect_report'], CausalEffectReport)
    assert result.slot_outputs['causal_effect_report'].status is EstimationStatus.SUCCESS
    return result


@pytest.mark.parametrize('basis', ['missing', 'present_fake', 'swapped_real_cas'])
def test_success_ci_real_report_cas_remains_refused(rdd_native, tmp_path, basis):
    native = rdd_native.slot_outputs['causal_effect_report']
    writer = FileSystemCAS(tmp_path)
    native_ref = persist_causal_effect_report(writer, native)
    graph_ref = persist_causal_graph_model(
        writer, CausalGraphModel(graph_type=GraphType.DAG, nodes=['running', 'Y'], edges=[])
    )
    payload = native.model_dump(mode='json')
    payload['graph_ref'] = str(graph_ref.artifact_id)
    metadata = {**payload['metadata'], 'gate_eligible':True, 'causal_identification_verified':True}
    if basis == 'present_fake':
        metadata['identification_admission'] = {
            'proof_status':'identified', 'predicate_provenance':'recomputed',
            'verifier_role':'system_verifier', 'proof_ref':'sha256:'+'f'*64,
            'source_report_ref':str(native_ref.artifact_id), 'graph_ref':str(graph_ref.artifact_id),
        }
    elif basis == 'swapped_real_cas':
        other_graph = persist_causal_graph_model(
            writer, CausalGraphModel(graph_type=GraphType.DAG, nodes=['unrelated', 'Z'], edges=[])
        )
        other_query = put_json_artifact(
            writer, {'estimand':'E[Z|do(unrelated=1)]', 'target':'different-population'},
            kind='test.causal_query', schema_name='test.causal_query', schema_version='1.0',
        )
        proof = ProofBundle(
            proof_status='identified', proof_stratum='A0_trusted', theorem_family='backdoor',
            completeness_regime='complete', implementation_coverage='declared',
            graph_ref=str(other_graph.artifact_id), query_ref=str(other_query['artifact_id']),
            metadata={'predicate_provenance':'recomputed', 'verifier_role':'system_verifier'},
        )
        proof_ref = persist_proof_bundle(writer, proof)
        reopened_proof = load_proof_bundle(FileSystemCAS(tmp_path), proof_ref)
        assert reopened_proof.graph_ref != payload['graph_ref']
        metadata['identification_admission'] = {
            'proof_status':'identified', 'predicate_provenance':'recomputed',
            'verifier_role':'system_verifier', 'proof_ref':str(proof_ref.artifact_id),
            'source_report_ref':str(native_ref.artifact_id), 'graph_ref':payload['graph_ref'],
        }
    payload['metadata'] = metadata
    candidate = CausalEffectReport.model_validate(payload)
    candidate_ref = persist_causal_effect_report(writer, candidate)
    reopened = load_causal_effect_report(FileSystemCAS(tmp_path), candidate_ref)
    assert reopened is not candidate and reopened.model_dump(mode='json') == payload
    assert reopened.status is EstimationStatus.SUCCESS
    assert reopened.confidence_interval == native.confidence_interval
    assert reopened.point_estimate == native.point_estimate
    assert reopened.metadata['gate_eligible'] is True  # Retained deceptive marker.
    envelope = reopened.to_uncertainty_envelope()
    assert envelope is not None
    assert envelope.confidence_interval == tuple(envelope.numeric_policy.canonicalize(x) for x in native.confidence_interval)
    assert envelope.gate_eligible is False
    assert envelope.metadata['gate_eligibility_reason'] == 'causal_identification_admission_not_established'
    estimand = EstimandSpec(
        query_id='native-sharp-rd-value-consumer', estimand_id=native.estimand,
        outcome='Y', treatment_or_exposure='running>=0', population='synthetic400',
        unit='Y', target_role='causal',
    )
    result = replace(rdd_native, slot_outputs={'causal_effect_report':reopened},
                     output={'causal_effect_report':reopened})
    refusal = project_method_value_evidence(
        method_signature=RegressionDiscontinuity.signature, method_result=result,
        estimand=estimand, selected_output_slot='causal_effect_report',
    )
    assert isinstance(refusal, MethodValueRefusal)
    assert refusal.reason_code == 'method_output_contract_unresolved'
    _log(case=basis, native_report_ref=str(native_ref.artifact_id), candidate_report_ref=str(candidate_ref.artifact_id),
         native_numerical_status=reopened.status.value, confidence_interval=reopened.confidence_interval,
         retained_marker=True, envelope_gate_eligible=envelope.gate_eligible,
         value_consumer_refusal=refusal.reason_code, value_guard_312_reached=False,
         proof_authority='consumer_asserted' if basis != 'missing' else 'not_established')


@pytest.fixture(scope='module')
def arima_native() -> MethodResult:
    rng = np.random.default_rng(914)
    data = TimeSeriesData(endog=2.0 + rng.normal(0.0, 0.4, 96))
    result = MethodDispatcher(runtime_history=SelectionHistoryStore()).dispatch(
        method_class=TimeSeriesEstimator, signature=TimeSeriesEstimator.signature, state=data,
        params={'model':'arima', 'p':0, 'd':0, 'q':0, 'confidence_level':0.95}, seed=914,
    )
    assert type(result.slot_outputs['result']) is EconometricResult
    assert result.slot_outputs['result'].model_info['library'] == 'statsmodels'
    return result


@pytest.mark.parametrize('coverage_tier', [None, 'HEURISTIC_POST_SELECTION'])
def test_existing_native_noncausal_value_profile(arima_native, tmp_path, coverage_tier):
    native = arima_native.slot_outputs['result']
    payload = native.model_dump(mode='json')
    payload['coverage_guarantee_tier'] = coverage_tier
    candidate = EconometricResult.model_validate(payload)
    ref = put_json_artifact(
        FileSystemCAS(tmp_path), candidate.model_dump(mode='json'), kind='test.econometric_result',
        schema_name=EconometricResult.contract_id, schema_version='2.0', canon_spec=CanonSpec(forbid_floats=False),
    )
    reopened = EconometricResult.model_validate(get_json_artifact(FileSystemCAS(tmp_path), ref['artifact_id']))
    assert reopened is not native and reopened == candidate
    estimand = EstimandSpec(query_id='native-arima-value-consumer', estimand_id='const', outcome='observed_series',
                            population='synthetic96', time_horizon='observed96', unit='series', target_role='estimate')
    binding = NativeValueEstimandBinding.from_estimand(
        estimand=estimand, native_contract_id=EconometricResult.contract_id,
        producer_method_fqn=TimeSeriesEstimator.signature.fqn,
        projection_input_content_hash=str(ref['artifact_id']),
    )
    result = replace(arima_native, output={'result':reopened}, slot_outputs={'result':reopened})
    evidence = project_method_value_evidence(
        method_signature=TimeSeriesEstimator.signature, method_result=result, estimand=estimand,
        selected_output_slot='result', projection_binding=binding,
    )
    if coverage_tier is None:
        assert isinstance(evidence, MethodValueEvidence)
        assert evidence.status == 'contract_projection_ready'
        assert evidence.envelope.confidence_interval == tuple(evidence.envelope.numeric_policy.canonicalize(x) for x in native.confidence_intervals['const'])
        assert evidence.envelope.gate_eligible is True
        assert evidence.production_value_eligible is False
        assert evidence.authority_scope == 'contract_only_nonproduction'
        verdict = evidence.status
    else:
        assert isinstance(evidence, MethodValueRefusal)
        assert evidence.reason_code == 'method_uncertainty_not_gate_eligible'
        verdict = evidence.reason_code
    _log(case='native_statsmodels_arima', artifact_ref=str(ref['artifact_id']), coverage_tier=coverage_tier,
         actual_consumer=verdict, production_value_eligible=False, value_guard_312_reached=True,
         interval=native.confidence_intervals['const'], projection_basis='caller_constructible_contract_only')
