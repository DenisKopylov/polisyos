"""Native TMLE numerical results cross the selected typed CAS consumer."""

import copy
import os
import subprocess
import sys

import numpy as np
import pytest

from polisyos.core.artifacts import PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.foundry.methods.catalog.causal.protocols import HTEObservationalData
from polisyos.foundry.methods.catalog.causal.treatment_effects import TMLEEstimator
from polisyos.foundry.methods.registry import MethodRegistry
from polisyos.ir.analytics.causal import CausalEffectReport, EstimationStatus
from polisyos.scientist.compute.job_spec import JobSpec
from polisyos.scientist.nodes.builtins.simulate.run_causal_evaluation import (
    _load_observational_data,
    _run_primary_causal_job,
    _verify_selected_tmle_projection,
)


def _fixture(ctx, state):
    rng = np.random.default_rng(811)
    n = 400
    x = rng.normal(size=n)
    w = rng.normal(size=n)
    a = rng.binomial(1, 0.5, size=n).astype(float)
    y = rng.binomial(1, 0.25 + 0.05 * np.sign(x + w) + 0.3 * a).astype(float)
    data = HTEObservationalData(
        outcome=y,
        treatment=a,
        covariates=x[:, None],
        confounders=w[:, None],
        feature_names=["x"],
        sample_ids=np.arange(n),
    )
    params = dict(
        propensity_backend="logistic",
        outcome_backend="linear",
        calibration_mode="none",
        outcome_scaling="raw",
        crossfit_folds=3,
        n_repeats=2,
        random_seed=18,
        coverage_guard="off",
    )
    ref = ctx.store.put_json(
        data.model_dump(mode="json"),
        PutOptions(kind="tests.tmle_source", media_type="application/json"),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    MethodRegistry.get_instance().register(TMLEEstimator, override=True)
    return data, params, state.model_copy(update={"observational_data_ref": ref}), ref


@pytest.mark.parametrize("profile", ["regular_iid", "clustered"])
def test_actual_primary_tmle_job_typed_cas_and_fresh_reader(
    execution_context, minimal_state, profile
):
    data, params, state, source = _fixture(execution_context, minimal_state)
    params["inference_profile"] = profile
    loaded = _load_observational_data(execution_context, state, TMLEEstimator.signature.fqn)
    assert isinstance(loaded, HTEObservationalData)
    result = _run_primary_causal_job(
        ctx=execution_context,
        state=state,
        observational_data=loaded,
        spec=JobSpec(
            job_kind="method", method_fqn=TMLEEstimator.signature.fqn, method_params=params, seed=18
        ),
    )
    assert not result.issues
    saved = from_canonical_bytes(execution_context.store.get_bytes(result.method_result_ref))
    report = CausalEffectReport.model_validate(saved["report"])
    assert report.status is (
        EstimationStatus.SUCCESS if profile == "regular_iid" else EstimationStatus.ASSUMPTION_FAILED
    )
    assert not report.to_uncertainty_envelope().gate_eligible
    assert "ate" in saved["result"]
    if profile != "regular_iid":
        assert report.point_estimate is None and report.confidence_interval is None
    reader = """
import json,sys
from polisyos.core.artifacts import FileSystemCAS,ArtifactRef
from polisyos.core.canon import from_canonical_bytes
from polisyos.foundry.methods.catalog.causal.protocols import HTEObservationalData
from polisyos.scientist.nodes.builtins.simulate.run_causal_evaluation import _verify_selected_tmle_projection
store=FileSystemCAS(sys.argv[1])
data=HTEObservationalData.model_validate(from_canonical_bytes(store.get_bytes(ArtifactRef.model_validate_json(sys.argv[2]))))
saved=from_canonical_bytes(store.get_bytes(ArtifactRef.model_validate_json(sys.argv[3])))
_verify_selected_tmle_projection(saved,observational_data=data,params=json.loads(sys.argv[4]))
assert saved['envelope']['gate_eligible'] is False
print('PASS selected typed source/native result/report/fresh reader; production admission UNRUN')
"""
    import json

    child = subprocess.run(
        [
            sys.executable,
            "-c",
            reader,
            str(execution_context.store.root),
            source.model_dump_json(),
            result.method_result_ref.model_dump_json(),
            json.dumps(params),
        ],
        capture_output=True,
        text=True,
        env=os.environ.copy(),
        check=False,
    )
    assert child.returncode == 0, child.stdout + child.stderr


def test_actual_primary_job_refuses_changed_adjustment_source(execution_context, minimal_state):
    data, params, state, _ = _fixture(execution_context, minimal_state)
    stale = data.model_copy(update={"confounders": -data.confounders})
    with pytest.raises(ValueError, match="materialization/source mismatch"):
        _run_primary_causal_job(
            ctx=execution_context,
            state=state,
            observational_data=stale,
            spec=JobSpec(
                job_kind="method",
                method_fqn=TMLEEstimator.signature.fqn,
                method_params=params,
                seed=18,
            ),
        )


@pytest.mark.parametrize("mutation", ["se", "sample", "profile", "interval"])
def test_actual_persisted_reader_refuses_peer_report_change_retaining_result(
    execution_context, minimal_state, mutation
):
    data, params, _, _ = _fixture(execution_context, minimal_state)
    output = copy.deepcopy(TMLEEstimator.pure_step(data, params))
    report = output["report"].model_dump(mode="json")
    if mutation == "se":
        report["standard_error"] *= 2
    elif mutation == "sample":
        report["sample_size"] += 1
    elif mutation == "profile":
        report["method_params"]["inference_profile"] = "clustered"
    else:
        report["confidence_interval"][1] += 0.1
    assert report["status"] == "success"
    output["report"] = report
    output["envelope"] = CausalEffectReport.model_validate(report).to_uncertainty_envelope()
    ref = execution_context.store.put_json(
        output,
        PutOptions(kind="tests.tmle_output", media_type="application/json"),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    saved = from_canonical_bytes(execution_context.store.get_bytes(ref))
    with pytest.raises(ValueError, match="numerical report projection mismatch"):
        _verify_selected_tmle_projection(saved, observational_data=data, params=params)
