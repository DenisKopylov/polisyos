"""Independent native observation/CAS/analytic projection oracles, no fake pool."""
from __future__ import annotations
import importlib.util
import json
import math
import os
import pathlib
import pickle
import subprocess
import sys
from dataclasses import fields, replace
from statistics import NormalDist

import numpy as np
import pytest

from polisyos.common.serialization import to_python_data
from polisyos.foundry.methods.catalog.causal import tmle_core as core
from polisyos.foundry.methods.catalog.causal.treatment_effects import TMLEEstimator
from polisyos.foundry.methods.components.io import dematerialize_method_output
from polisyos.ir.analytics.causal import CausalEffectReport, CausalMethod, EstimationStatus
from polisyos.ir.analytics.uncertainty import UncertaintyEnvelope

SOURCE_ROOT = pathlib.Path(os.environ['E02_TMLE_SOURCE_ROOT'])
SPEC = importlib.util.spec_from_file_location(
    '_frozen_tmle_owner_fixture',
    SOURCE_ROOT/'tests/unit/foundry/methods/catalog/causal/test_tmle_common_report.py',
)
OWNER = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(OWNER)


def test_actual_job_full_adjustment_order_defaults_and_independent_eif_projection(tmp_path, monkeypatch):
    data = OWNER._data()
    # Distinct source columns make a same-shape reordered basis distinguishable.
    x = np.column_stack((data.covariates, np.linspace(2, 5, len(data.outcome))))
    w = np.column_stack((np.sin(np.arange(len(data.outcome))), np.linspace(-3, -1, len(data.outcome))))
    data = data.model_copy(update={'covariates':x, 'feature_names':['original','second'],
                                   'confounders':w, 'confounder_names':['sine','negative']})
    expected_basis = np.column_stack((x,w))
    calls=[]
    real_fit=core._fit_crossfit_fold

    def observe(**kwargs):
        # Actual canonical fitter input, rather than dimensions or feature labels.
        np.testing.assert_array_equal(kwargs['X'], expected_basis)
        calls.append((kwargs['rep_seed'],kwargs['fold_id'],kwargs['test_idx'].copy()))
        return real_fit(**kwargs)

    monkeypatch.setattr(core,'_SHARED_NUISANCE_CACHE',{})
    monkeypatch.setattr(core,'_SHARED_NUISANCE_CACHE_ORDER',[])
    monkeypatch.setattr(core,'_fit_crossfit_fold',observe)
    params=OWNER._params()
    saved,job=OWNER._run(tmp_path,data,params)
    assert len(calls)==6
    for seed in (18,1015):
        assert sorted(i for s,_,held in calls if s==seed for i in held)==list(range(len(data.outcome)))
    result=saved['result'];report=CausalEffectReport.model_validate(saved['report'])
    assert report.status is EstimationStatus.SUCCESS
    # Standard-library Gaussian quantile and sample-size formula do not call the projector.
    expected_se=float(result['eif_standard_deviation'])/math.sqrt(len(data.outcome))
    expected_half_width=NormalDist().inv_cdf(.975)*expected_se
    assert report.standard_error==pytest.approx(expected_se,abs=1e-14)
    assert report.point_estimate==result['ate']
    assert report.confidence_interval==pytest.approx((result['ate']-expected_half_width,
                                                    result['ate']+expected_half_width),abs=1e-13)
    assert report.identified_estimand is None and report.graph_ref is None
    assert report.to_uncertainty_envelope().gate_eligible is False
    assert report.metadata['assumption_basis']=='consumer_asserted'
    declared={p.name:p.default for p in TMLEEstimator.signature.parameters}
    effective=core.ATENuisanceContract.from_params({})
    assert set(declared)=={f.name for f in fields(core.ATENuisanceContract)}
    for field in fields(core.ATENuisanceContract):
        assert declared[field.name]==getattr(effective,field.name)
    assert report.method_params==to_python_data(core.ATENuisanceContract.from_params(params).as_contract_payload(),sort_keys=True)
    # An existing raw result reader receives exactly its native numerical artifact.
    legacy=TMLEEstimator.pure_step(OWNER._legacy(data),params)
    assert to_python_data(legacy['result'],sort_keys=True)==result and len(calls)==6
    mapped=dematerialize_method_output(method_class=TMLEEstimator,signature=TMLEEstimator.signature,output=legacy)
    assert set(mapped)=={'result','report','envelope'}
    assert all(mapped[k] is legacy[k] for k in mapped)
    historical_signature=replace(TMLEEstimator.signature,
        output_slots=frozenset(s for s in TMLEEstimator.signature.output_slots if s.name=='result'))
    historical=dematerialize_method_output(method_class=TMLEEstimator,signature=historical_signature,output=legacy)
    assert historical=={'result':legacy['result']} and historical['result'] is legacy['result']
    factory=TMLEEstimator.report_from_result
    assert pickle.loads(pickle.dumps(factory)) is factory
    # A separate native interpreter consumes actual MethodJob result bytes.
    reader='''import json,sys
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.canon import from_canonical_bytes
from polisyos.ir.analytics.causal import CausalEffectReport,CausalMethod,EstimationStatus
from polisyos.ir.analytics.uncertainty import UncertaintyEnvelope
ref=ArtifactRef.model_validate_json(sys.argv[2])
saved=from_canonical_bytes(FileSystemCAS(sys.argv[1]).get_bytes(ref))
report=CausalEffectReport.model_validate(saved['report'])
envelope=UncertaintyEnvelope.model_validate(saved['envelope'])
assert report.method is CausalMethod.TMLE and report.status is EstimationStatus.SUCCESS
assert report.point_estimate==saved['result']['ate']
assert report.standard_error==saved['result']['standard_error']
assert report.confidence_interval==tuple([saved['result']['ci_lower'],saved['result']['ci_upper']])
assert report.to_uncertainty_envelope()==envelope and not envelope.gate_eligible
assert report.identified_estimand is None
print(json.dumps({'fresh_process':True,'method':report.method.value,'point':report.point_estimate,
                  'se':report.standard_error,'ci':report.confidence_interval,
                  'gate_eligible':envelope.gate_eligible,'identity_claim':False}))
'''
    completed=subprocess.run([sys.executable,'-c',reader,str(tmp_path/'cas'),job.method_result_ref.model_dump_json()],
                             capture_output=True,text=True,check=False)
    print(completed.stdout,end='');print(completed.stderr,end='')
    assert completed.returncode==0


@pytest.mark.parametrize('changes,reason,status',[
    ({'inference_profile':'clustered'},'unsupported_inference_profile',EstimationStatus.ASSUMPTION_FAILED),
    ({'propensity_trimming':.48,'weak_overlap_mode':'trim'},'trimmed_target_not_population_ate',EstimationStatus.ASSUMPTION_FAILED),
    ({'max_targeting_iter':1,'targeting_step_limit':1e-10},'targeting_score_not_converged',EstimationStatus.NUMERICAL_FAILURE),
])
def test_actual_limited_result_never_becomes_fake_success_interval(tmp_path,changes,reason,status):
    saved,_=OWNER._run(tmp_path,OWNER._data(),OWNER._params(**changes))
    report=CausalEffectReport.model_validate(saved['report'])
    envelope=UncertaintyEnvelope.model_validate(saved['envelope'])
    assert report.status is status and reason in saved['result']['inference_limitations']
    assert np.isfinite(saved['result']['ate'])
    assert report.point_estimate is None and report.standard_error is None
    assert report.confidence_interval is None and report.confidence_level is None
    assert not envelope.gate_eligible and envelope.is_heuristic_ci
    assert envelope.metadata['failure_envelope'] is True
    assert envelope==report.to_uncertainty_envelope()
