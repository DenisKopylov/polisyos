"""Numerical consumer identities, separately from attempted-evaluation authority."""

from __future__ import annotations

import copy
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
import statsmodels.api as sm

from polisyos.core.artifacts.store import PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.foundry.methods.catalog.causal.did import StaggeredDifferenceInDifferences
from polisyos.foundry.methods.catalog.causal.dowhy_identify_estimate import DoWhyIdentifyEstimate
from polisyos.foundry.methods.catalog.causal.protocols import (
    GraphCausalData,
    PanelObservationalData,
)
from polisyos.foundry.methods.components.io import dematerialize_method_output
from polisyos.foundry.methods.registry import MethodRegistry
from polisyos.ir.analytics.causal import CausalEffectReport, EstimationStatus
from polisyos.scientist.compute.job_spec import JobSpec
from polisyos.scientist.nodes.builtins.simulate.run_causal_evaluation import (
    RunCausalEvaluationNode,
    _run_primary_causal_job,
    _verify_selected_did_target,
)


def _admit_source(ctx, state, data, method):
    ref = ctx.store.put_json(
        data.model_dump(mode="json"),
        PutOptions(kind="tests.selected_causal_input", media_type="application/json"),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    MethodRegistry.get_instance().register(method, override=True)
    return state.model_copy(
        update={"observational_data_ref": ref, "causal_method_fqn": method.signature.fqn}
    ), ref


def _panel():
    timing = np.array([2, 2, 4, 4, 4, 4, -1, -1, -1, -1, -1, -1])
    y = np.tile(np.arange(6, dtype=float), (12, 1))
    y[:2, 2:] += [1, 2, 3, 4]
    y[2:6, 4:] += [8, 10]
    y[:2, 2:] += np.array([-1.0, 1.0])[:, None]
    y[2:6, 4:] += np.array([-1.5, -0.5, 0.5, 1.5])[:, None]
    y[6:, 2:] += np.arange(-2.5, 3.0)[:, None] * 0.2
    return PanelObservationalData(
        outcome=y,
        treatment=(timing >= 0).astype(int),
        time_treatment=2,
        treatment_timing=timing,
        unit_ids=np.arange(12),
    )


def _graph_data():
    rng = np.random.default_rng(19)
    x = rng.normal(size=500)
    a = rng.binomial(1, 1 / (1 + np.exp(-x)))
    y = 2 * a + 1.5 * x + rng.normal(size=500)
    return GraphCausalData(
        data=np.column_stack([a, y, x]),
        column_names=["A", "Y", "X"],
        treatment="A",
        outcome="Y",
        covariates=["X"],
        graph_dot="digraph { X -> A; X -> Y; A -> Y; }",
    )


def test_selected_scalar_job_persisted_target_fresh_reader(execution_context, minimal_state):
    data = _panel()
    state, source = _admit_source(
        execution_context, minimal_state, data, StaggeredDifferenceInDifferences
    )
    params = {"n_bootstrap": 399}
    result = _run_primary_causal_job(
        ctx=execution_context,
        state=state,
        observational_data=data,
        spec=JobSpec(
            job_kind="method", method_fqn=state.causal_method_fqn, method_params=params, seed=19
        ),
    )
    assert not result.issues
    report = CausalEffectReport.model_validate(result.final_state["report"])
    assert report.status is EstimationStatus.SUCCESS
    assert report.point_estimate == pytest.approx((2.5 + 2 * 9) / 3)
    projected = dematerialize_method_output(
        method_class=StaggeredDifferenceInDifferences,
        signature=StaggeredDifferenceInDifferences.signature,
        output=result.final_state,
    )
    assert set(projected) == StaggeredDifferenceInDifferences.signature.output_slot_names
    assert projected["result"] is result.final_state["report"]
    assert str(source.artifact_id) in {
        str(row.artifact_id)
        for row in execution_context.store.get_manifest(result.method_result_ref).inputs
    }
    reader = """
import json,sys
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.canon import from_canonical_bytes
from polisyos.foundry.methods.catalog.causal.protocols import PanelObservationalData
from polisyos.scientist.nodes.builtins.simulate.run_causal_evaluation import _verify_selected_did_target
store=FileSystemCAS(sys.argv[1])
source=ArtifactRef.model_validate(json.loads(sys.argv[2]))
result=ArtifactRef.model_validate(json.loads(sys.argv[3]))
data=PanelObservationalData.model_validate(from_canonical_bytes(store.get_bytes(source)))
output=from_canonical_bytes(store.get_bytes(result))
_verify_selected_did_target(output,observational_data=data,params={'n_bootstrap':399})
assert output['report']['estimand']=='theta_sel'
assert abs(output['report']['point_estimate']-41/6)<1e-12
print('PASS source-bound fixed theta_sel in fresh numerical reader; no evaluation authority')
"""
    fresh = subprocess.run(
        [
            sys.executable,
            "-c",
            reader,
            str(execution_context.store.root),
            source.model_dump_json(),
            result.method_result_ref.model_dump_json(),
        ],
        capture_output=True,
        text=True,
        env=os.environ.copy(),
        check=False,
    )
    assert fresh.returncode == 0, fresh.stdout + fresh.stderr


@pytest.mark.parametrize("mutation", ["periods", "binding", "data", "estimand"])
def test_target_markers_do_not_admit_a_different_scalar(mutation):
    data = _panel()
    params = {"n_bootstrap": 399, "__rng__": np.random.default_rng(19)}
    output = StaggeredDifferenceInDifferences.pure_step(data, params)
    _verify_selected_did_target(output, observational_data=data, params=params)
    changed = copy.deepcopy(output)
    if mutation == "data":
        data = data.model_copy(deep=True)
        data.outcome[0, -1] += 0.25
    else:
        report = changed["report"]
        if mutation == "periods":
            report.method_params["target_contract"]["eligible_periods"]["2"] = [2]
        elif mutation == "binding":
            report.method_params["target_binding"] = "0" * 64
        else:
            changed["report"] = report.model_copy(update={"estimand": "theta_W"})
    with pytest.raises(ValueError, match="target does not bind"):
        _verify_selected_did_target(changed, observational_data=data, params=params)


def test_real_dowhy_primary_binding_and_canonical_consumer(
    execution_context,
    minimal_state,
    monkeypatch,
):
    worker = os.environ.get("E02_TEST_DOWHY_WORKER_PYTHON")
    assert worker and Path(worker).is_file(), "selected backend is required; absence is no PASS"
    monkeypatch.setenv("POLISYOS_DOWHY_WORKER_PYTHON", worker)
    data = _graph_data()
    state, source = _admit_source(execution_context, minimal_state, data, DoWhyIdentifyEstimate)
    result = _run_primary_causal_job(
        ctx=execution_context,
        state=state,
        observational_data=data,
        spec=JobSpec(job_kind="method", method_fqn=state.causal_method_fqn, seed=13),
    )
    assert not result.issues
    report = CausalEffectReport.model_validate(result.final_state["report"])
    assert report.status is EstimationStatus.SUCCESS, report.status_reason
    ols = sm.OLS(
        data.data[:, 1], np.column_stack([np.ones(500), data.data[:, 0], data.data[:, 2]])
    ).fit()
    assert report.point_estimate == pytest.approx(ols.params[1], abs=1e-10)
    assert report.confidence_interval == pytest.approx(ols.conf_int(alpha=0.05)[1], abs=1e-10)
    assert report.confidence_level == 0.95
    projected = dematerialize_method_output(
        method_class=DoWhyIdentifyEstimate,
        signature=DoWhyIdentifyEstimate.signature,
        output=result.final_state,
    )
    assert set(projected) == {"causal_effect_report"}
    assert projected["causal_effect_report"] is result.final_state["report"]
    saved = from_canonical_bytes(execution_context.store.get_bytes(result.method_result_ref))
    assert saved["report"]["metadata"]["worker"]["source"]["artifact_ref"] == (
        source.model_dump(mode="json")
    )


def test_source_collision_refused_and_node_still_requires_admission(
    execution_context,
    minimal_state,
):
    data = _graph_data()
    state, source = _admit_source(execution_context, minimal_state, data, DoWhyIdentifyEstimate)
    other = execution_context.store.put_json(
        {"different": True}, PutOptions(kind=source.kind, media_type=source.media_type)
    )
    with pytest.raises(ValueError, match="source reference mismatch"):
        _run_primary_causal_job(
            ctx=execution_context,
            state=state,
            observational_data=data,
            spec=JobSpec(
                job_kind="method",
                method_fqn=state.causal_method_fqn,
                input_refs={"dowhy_observational_data": other},
            ),
        )
    outcome = RunCausalEvaluationNode().execute(execution_context, state)
    assert outcome.status == "fail"
    assert outcome.error.details["blocker_codes"] == [
        "polisyos.eval_safety.execution_context_missing@1.0.0"
    ]
