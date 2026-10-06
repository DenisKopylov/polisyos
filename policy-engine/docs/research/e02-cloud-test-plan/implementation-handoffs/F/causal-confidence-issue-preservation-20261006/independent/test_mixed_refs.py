"""Independent degraded CAS references never erase the offered consumer role."""
from dataclasses import replace
import json
from pathlib import Path

import pytest

from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.contracts.foundry import ExecPlanRef, MetricsRef, SimulationResult, SimulationResultRef
from polisyos.core.governance.passes.base import IssueSeverity, PassContext
from polisyos.core.governance.profiles import ValidationProfile
from polisyos.ir.analytics.uncertainty import UncertaintyEnvelope, persist_uncertainty_envelope
from polisyos.scientist.governance.passes.confidence_pass import ConfidencePass


def context(reader, refs):
    profile = ValidationProfile.strict()
    profile = replace(profile, thresholds={**profile.thresholds,
        'uncertainty_min_gate_eligible_ratio': 0.0})
    return PassContext(ir=None, state={'_store': reader, **refs}, registry_bundle=None,
        profile=profile, run_id='independent-mixed-cas')


def offered(writer):
    return persist_uncertainty_envelope(writer, UncertaintyEnvelope(
        point_estimate=8.0, confidence_interval=(7.99, 8.01), source='ensemble',
        gate_eligible=True, metadata={'proof_status': 'identified',
        'identification_verified': True, 'verifier_role': 'system_verifier'}))


def healthy(writer):
    plan = writer.put_json({'order': []}, PutOptions(kind='foundry.exec_plan', media_type='application/json'))
    metrics = writer.put_json({'values': {}}, PutOptions(kind='foundry.metrics', media_type='application/json'))
    value = SimulationResult(exec_plan_ref=ExecPlanRef(artifact_id=plan.artifact_id),
        metrics_ref=MetricsRef(artifact_id=metrics.artifact_id))
    return writer.put_json(value, PutOptions(kind='foundry.simulation_result', media_type='application/json'))


def codes(issues):
    print(json.dumps([issue.model_dump(mode='json') for issue in issues], sort_keys=True))
    return {(issue.code, issue.severity, tuple(issue.path)) for issue in issues}


@pytest.mark.parametrize('failure', ['absent', 'json', 'schema'])
def test_string_simulation_id_with_offered_causal_ref_retains_blocker(tmp_path: Path, failure):
    writer = FileSystemCAS(tmp_path)
    if failure == 'absent':
        bad_id = 'sha256:' + 'e' * 64
    elif failure == 'json':
        bad_id = str(writer.put_bytes(b'\x00{', PutOptions(kind='foundry.simulation_result', media_type='application/json')).artifact_id)
    else:
        bad_id = str(writer.put_json(False, PutOptions(kind='foundry.simulation_result', media_type='application/json')).artifact_id)
    causal = offered(writer)
    reader = FileSystemCAS(tmp_path)
    assert reader is not writer
    issues = ConfidencePass().validate(context(reader, {
        'causal_envelope_ref': causal, 'simulation_result_ref': bad_id}))
    assert codes(issues) == {
        ('CONFIDENCE_GATE_ELIGIBILITY_LOW', IssueSeverity.BLOCKER,
         ('artifacts_index', 'causal_envelope_ref')),
        ('CONFIDENCE_SIM_RESULT_LOAD_FAILED', IssueSeverity.WARNING,
         ('artifacts_index', 'simulation_result_ref'))}
    assert len(issues) == 2


def test_index_bad_simulation_takes_priority_over_healthy_top_level_reference(tmp_path: Path):
    writer = FileSystemCAS(tmp_path)
    malformed = writer.put_json([], PutOptions(kind='foundry.simulation_result', media_type='application/json'))
    top_good = healthy(writer)
    refs = {'artifacts_index': {'causal_envelope_ref': offered(writer),
            'simulation_result_ref': SimulationResultRef(artifact_id=malformed.artifact_id)},
            'simulation_result_ref': str(top_good.artifact_id)}
    issues = ConfidencePass().validate(context(FileSystemCAS(tmp_path), refs))
    assert codes(issues) == {
        ('CONFIDENCE_GATE_ELIGIBILITY_LOW', IssueSeverity.BLOCKER,
         ('artifacts_index', 'causal_envelope_ref')),
        ('CONFIDENCE_SIM_RESULT_LOAD_FAILED', IssueSeverity.WARNING,
         ('artifacts_index', 'simulation_result_ref'))}
    assert len(issues) == 2


def test_noncausal_healthy_string_reference_remains_supported(tmp_path: Path):
    writer = FileSystemCAS(tmp_path)
    refs = {'simulation_result_ref': str(healthy(writer).artifact_id)}
    issues = ConfidencePass().validate(context(FileSystemCAS(tmp_path), refs))
    assert codes(issues) == set()
    assert issues == []
