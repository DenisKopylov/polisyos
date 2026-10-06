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
from polisyos.ir.analytics.uncertainty import UncertaintyEnvelope
from polisyos.scientist.compute.job_spec import JobSpec
from polisyos.scientist.nodes.builtins.simulate import run_causal_evaluation as owner
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


@pytest.mark.parametrize("point_only", [False, True])
def test_actual_worker_result_cannot_be_replaced_by_consistent_report_projections(
    execution_context, minimal_state, monkeypatch, point_only
):
    """Preserve real backend/source markers while falsifying consumed quantities."""
    worker = os.environ.get("E02_TEST_DOWHY_WORKER_PYTHON")
    assert worker and Path(worker).is_file()
    monkeypatch.setenv("POLISYOS_DOWHY_WORKER_PYTHON", worker)
    if point_only:
        from polisyos.foundry.methods.catalog.causal import _dowhy_worker as bridge

        original_popen = subprocess.Popen
        script = str(bridge._worker_directory() / "worker.py")
        program = """
import runpy,sys
from dowhy import CausalModel
original=CausalModel.estimate_effect
def controlled(self,*args,**kwargs):
    actual=original(self,*args,**kwargs)
    actual.get_confidence_intervals=lambda **kwargs:None
    actual.get_standard_error=lambda:None
    return actual
CausalModel.estimate_effect=controlled
runpy.run_path(sys.argv[1],run_name='__main__')
"""

        def launch(args, **kwargs):
            if args == [worker, "-I", script]:
                args = [worker, "-I", "-c", program, script]
            return original_popen(args, **kwargs)

        monkeypatch.setattr(subprocess, "Popen", launch)
    data = _graph_data()
    state, _ = _admit_source(execution_context, minimal_state, data, DoWhyIdentifyEstimate)
    spec = JobSpec(job_kind="method", method_fqn=state.causal_method_fqn, seed=13)
    genuine = _run_primary_causal_job(
        ctx=execution_context, state=state, spec=spec, observational_data=data
    )
    original = from_canonical_bytes(execution_context.store.get_bytes(genuine.method_result_ref))
    report = CausalEffectReport.model_validate(original["report"])
    assert report.status is (
        EstimationStatus.NUMERICAL_FAILURE if point_only else EstimationStatus.SUCCESS
    )
    if point_only:
        assert report.confidence_interval is None
        assert not report.to_uncertainty_envelope().gate_eligible
    mutations = {
        "point_estimate": report.point_estimate + 0.05,
        "standard_error": 0.25,
        "p_value": 1e-12,
        "identified_estimand": "different identified quantity",
        "estimand": "different target",
        "estimand_type": "different target type",
        "inference_method": "different inference law",
        "sample_size": report.sample_size + 1,
        "n_treated": report.n_treated + 1,
        "n_control": report.n_control + 1,
        "pre_periods": 1,
        "post_periods": 1,
        "graph_ref": "different graph",
        "assumptions": {"unknown graph law": "established"},
        "status_reason": "different computation status",
        "diagnostics": {"fake passed test": True},
        "method_params": {"method_name": "different estimator"},
    }
    if not point_only:
        mutations["confidence_interval"] = tuple(x + 0.01 for x in report.confidence_interval)
        mutations["confidence_level"] = 0.9
    for field, value in mutations.items():
        payload = copy.deepcopy(original)
        changed = report.model_copy(update={field: value})
        payload["report"] = changed.model_dump(mode="json")
        payload["envelope"] = changed.to_uncertainty_envelope().model_dump(mode="json")
        _offer_corrupted_job(monkeypatch, execution_context, genuine, payload)
        with pytest.raises(ValueError, match="does not project"):
            _run_primary_causal_job(
                ctx=execution_context, state=state, spec=spec, observational_data=data
            )
    for field in ["authority", "inference_status", "execution_profile"]:
        payload = copy.deepcopy(original)
        payload["report"]["metadata"][field] = "different declaration"
        _offer_corrupted_job(monkeypatch, execution_context, genuine, payload)
        with pytest.raises(ValueError, match="does not project"):
            _run_primary_causal_job(
                ctx=execution_context, state=state, spec=spec, observational_data=data
            )
    payload = copy.deepcopy(original)
    payload["envelope"]["point_estimate"] += 0.01
    payload["envelope"]["confidence_interval"] = [
        x + 0.01 for x in payload["envelope"]["confidence_interval"]
    ]
    _offer_corrupted_job(monkeypatch, execution_context, genuine, payload)
    with pytest.raises(ValueError, match="uncertainty projection"):
        _run_primary_causal_job(
            ctx=execution_context, state=state, spec=spec, observational_data=data
        )


def _offer_corrupted_job(monkeypatch, ctx, genuine, payload):
    manifest = ctx.store.get_manifest(genuine.method_result_ref)
    ref = ctx.store.put_json(
        payload,
        PutOptions(
            kind=manifest.kind,
            media_type=manifest.media_type,
            schema=manifest.artifact_schema,
            inputs=manifest.inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    offered = genuine.model_copy(deep=True)
    offered.method_result_ref = ref
    offered.final_state["report"] = CausalEffectReport.model_validate(payload["report"])
    offered.final_state["envelope"] = UncertaintyEnvelope.model_validate(payload["envelope"])
    monkeypatch.setattr(owner, "run_job", lambda *args, **kwargs: offered)


def test_selected_did_peer_and_actual_source_must_match(
    execution_context, minimal_state, monkeypatch
):
    data = _panel()
    state, _ = _admit_source(
        execution_context, minimal_state, data, StaggeredDifferenceInDifferences
    )
    spec = JobSpec(
        job_kind="method", method_fqn=state.causal_method_fqn, method_params={"n_bootstrap": 399}
    )
    genuine = _run_primary_causal_job(
        ctx=execution_context, state=state, spec=spec, observational_data=data
    )
    offered = genuine.model_copy(deep=True)
    offered.final_state["report"].point_estimate += 0.01
    monkeypatch.setattr(owner, "run_job", lambda *args, **kwargs: offered)
    with pytest.raises(ValueError, match="persisted/offered report"):
        _run_primary_causal_job(
            ctx=execution_context, state=state, spec=spec, observational_data=data
        )
    monkeypatch.setattr(owner, "run_job", lambda *args, **kwargs: genuine)
    changed = data.model_copy(deep=True)
    changed.outcome[0, -1] += 0.25
    with pytest.raises(ValueError, match="target does not bind"):
        _run_primary_causal_job(
            ctx=execution_context, state=state, spec=spec, observational_data=changed
        )
